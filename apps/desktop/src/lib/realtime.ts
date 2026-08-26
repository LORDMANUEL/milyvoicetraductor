import { desktopApi } from './api';
import { shouldUseProtectedSystemAudioFallback } from './audio-source-policy';
import type { AudioSourceMode, RealtimeEvent, SessionMode, SpeakerFocusMode } from '../types';

export type RealtimeEventHandler = (event: RealtimeEvent) => void;
export type RealtimeSourceLanguage = 'auto' | 'en' | 'es' | 'zh';
export type RealtimeTargetLanguage = 'es' | 'en' | 'zh';

export class LocalEngineError extends Error {
  constructor(public readonly code: string | undefined, message: string) {
    super(message);
    this.name = 'LocalEngineError';
  }
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

export class LocalRealtimeClient {
  private socket: WebSocket | null = null;
  private binaryPcm = false;
  private sourceLanguage: RealtimeSourceLanguage = 'auto';
  private targetLanguage: RealtimeTargetLanguage = 'es';
  private handler: RealtimeEventHandler;

  constructor(handler: RealtimeEventHandler) {
    this.handler = handler;
  }

  private sendControl(payload: Record<string, unknown>): void {
    const socket = this.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ protocol: 1, targetLanguage: this.targetLanguage, ...payload }));
  }

  async connect(
    sourceLanguage: RealtimeSourceLanguage,
    targetLanguage: RealtimeTargetLanguage,
    persistTranscript: boolean,
    sessionMode: SessionMode = 'meeting',
    sourceMode: AudioSourceMode = 'microphone',
    speakerDetection = false,
    speakerFocusMode: SpeakerFocusMode = 'all',
    speakerId: string | null = null,
    externalPcm = false
  ): Promise<void> {
    await this.close();
    const session = await desktopApi.getLocalEngineSession();
    this.sourceLanguage = sourceLanguage;
    this.targetLanguage = targetLanguage;
    const socket = new WebSocket(
      `ws://127.0.0.1:${session.port}/ws?token=${encodeURIComponent(session.credential)}`
    );
    this.socket = socket;

    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const timeout = window.setTimeout(() => {
        if (settled) return;
        settled = true;
        reject(new Error('El motor tardó demasiado en preparar la sesión local.'));
        try { socket.close(); } catch (_) { /* noop */ }
      }, 120_000);

      socket.addEventListener('open', () => {
        socket.send(JSON.stringify({
          protocol: 1,
          type: 'client.hello',
          sourceLanguage,
          targetLanguage,
          persistTranscript,
          sessionMode,
          sourceMode,
          externalPcm,
          speakerDetection,
          speakerFocusMode,
          speakerId,
          binaryPcm: true
        }));
      });

      socket.addEventListener('message', (message) => {
        let payload: RealtimeEvent;
        try {
          payload = JSON.parse(String(message.data)) as RealtimeEvent;
        } catch (_) {
          return;
        }
        this.handler(payload);
        if (payload.type === 'session.started') {
          this.binaryPcm = payload.binaryPcm === true;
          if (!settled) {
            settled = true;
            window.clearTimeout(timeout);
            resolve();
          }
        } else if (payload.type === 'engine.error' && !settled) {
          settled = true;
          window.clearTimeout(timeout);
          reject(new LocalEngineError(payload.code, payload.message || 'El motor local rechazó la sesión.'));
        }
      });

      socket.addEventListener('error', () => {
        if (!settled) {
          settled = true;
          window.clearTimeout(timeout);
          reject(new Error('No se pudo conectar con el motor local.'));
        }
      });

      socket.addEventListener('close', () => {
        this.binaryPcm = false;
        if (!settled) {
          settled = true;
          window.clearTimeout(timeout);
          reject(new Error('El motor cerró la conexión antes de iniciar la sesión.'));
        }
      });
    });
  }

  setSpeakerFocus(mode: SpeakerFocusMode, speakerId: string | null = null): void {
    this.sendControl({ type: 'speaker.focus', speakerFocusMode: mode, speakerId });
  }

  notifyTtsStarted(text: string, speakerId: string | null = null): void {
    this.sendControl({ type: 'tts.started', text, speakerId });
  }

  notifyTtsFinished(speakerId: string | null = null): void {
    this.sendControl({ type: 'tts.finished', speakerId });
  }

  sendPcm(buffer: ArrayBuffer): void {
    const socket = this.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    if (this.binaryPcm) {
      socket.send(buffer);
      return;
    }
    socket.send(JSON.stringify({
      protocol: 1,
      type: 'audio.chunk',
      sourceLanguage: this.sourceLanguage,
      targetLanguage: this.targetLanguage,
      sampleRate: 16000,
      audioBase64: arrayBufferToBase64(buffer)
    }));
  }

  async stop(): Promise<void> {
    const socket = this.socket;
    if (!socket) return;
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        protocol: 1,
        type: 'audio.stop',
        sourceLanguage: this.sourceLanguage,
        targetLanguage: this.targetLanguage
      }));
      await new Promise((resolve) => window.setTimeout(resolve, 300));
    }
    await this.close();
  }

  async close(): Promise<void> {
    const socket = this.socket;
    this.socket = null;
    this.binaryPcm = false;
    if (socket) {
      try { socket.close(1000, 'desktop stop'); } catch (_) { /* noop */ }
    }
  }
}

export type DesktopAudioSource = 'microphone' | 'system' | 'media';

export class DesktopAudioCapture {
  private client: LocalRealtimeClient;
  private context: AudioContext | null = null;
  private worklet: AudioWorkletNode | null = null;
  private stream: MediaStream | null = null;
  private elementSource: MediaElementAudioSourceNode | null = null;
  private playbackGain: GainNode | null = null;

  constructor(handler: RealtimeEventHandler) {
    this.client = new LocalRealtimeClient(handler);
  }

  /** Compatibilidad: ya no se descarta PCM durante TTS. */
  setOutputSuppressed(_suppressed: boolean): void {}

  setSpeakerFocus(mode: SpeakerFocusMode, speakerId: string | null = null): void {
    this.client.setSpeakerFocus(mode, speakerId);
  }

  notifyTtsStarted(text: string, speakerId: string | null = null): void {
    this.client.notifyTtsStarted(text, speakerId);
  }

  notifyTtsFinished(speakerId: string | null = null): void {
    this.client.notifyTtsFinished(speakerId);
  }

  setPlaybackGain(value: number): void {
    const gain = this.playbackGain;
    if (!gain || !this.context) return;
    gain.gain.setTargetAtTime(Math.max(0, Math.min(1, value)), this.context.currentTime, 0.03);
  }

  private async createAudioGraph(): Promise<AudioContext> {
    const context = new AudioContext({ sampleRate: 16000, latencyHint: 'interactive' });
    await context.audioWorklet.addModule('/audio-worklet.js');
    this.context = context;
    this.worklet = new AudioWorkletNode(context, 'milyvoice-desktop-pcm', {
      numberOfInputs: 1,
      numberOfOutputs: 0,
      channelCount: 1
    });
    this.worklet.port.onmessage = (message: MessageEvent<ArrayBuffer>) => {
      this.client.sendPcm(message.data);
    };
    return context;
  }

  async startMicrophone(
    sourceLanguage: RealtimeSourceLanguage,
    targetLanguage: RealtimeTargetLanguage,
    persistTranscript: boolean,
    sessionMode: SessionMode = 'meeting',
    speakerDetection = false,
    speakerFocusMode: SpeakerFocusMode = 'all',
    speakerId: string | null = null
  ): Promise<void> {
    await this.stop();
    await this.client.connect(sourceLanguage, targetLanguage, persistTranscript, sessionMode, 'microphone', speakerDetection, speakerFocusMode, speakerId);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });
      this.stream = stream;
      const context = await this.createAudioGraph();
      const source = context.createMediaStreamSource(stream);
      source.connect(this.worklet!);
    } catch (error) {
      await this.client.stop();
      throw error;
    }
  }

  async startSystemAudio(
    sourceLanguage: RealtimeSourceLanguage,
    targetLanguage: RealtimeTargetLanguage,
    persistTranscript: boolean,
    sessionMode: SessionMode = 'meeting',
    speakerDetection = false,
    speakerFocusMode: SpeakerFocusMode = 'all',
    speakerId: string | null = null
  ): Promise<void> {
    await this.stop();

    try {
      await this.client.connect(
        sourceLanguage,
        targetLanguage,
        persistTranscript,
        sessionMode,
        'system_loopback',
        speakerDetection,
        speakerFocusMode,
        speakerId,
        false
      );
      // El motor ya está capturando WASAPI. No crear otro stream PCM en Desktop.
      return;
    } catch (error) {
      const code = error instanceof LocalEngineError ? error.code : undefined;
      if (!shouldUseProtectedSystemAudioFallback(code)) throw error;
      await this.client.close();
    }

    // Recuperación explícita: el motor mantiene sourceMode=system_loopback pero
    // recibe PCM externo desde el selector protegido de Windows/WebView2.
    await this.client.connect(
      sourceLanguage,
      targetLanguage,
      persistTranscript,
      sessionMode,
      'system_loopback',
      speakerDetection,
      speakerFocusMode,
      speakerId,
      true
    );
    try {
      if (!navigator.mediaDevices.getDisplayMedia) {
        throw new Error('Este WebView no admite el selector alternativo de audio del sistema.');
      }
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true
      });
      const audioTracks = stream.getAudioTracks();
      if (audioTracks.length === 0) {
        stream.getTracks().forEach((track) => track.stop());
        throw new Error('No se compartió audio. Activa “Compartir audio del sistema” en el selector de Windows.');
      }
      stream.getVideoTracks().forEach((track) => track.stop());
      this.stream = new MediaStream(audioTracks);
      const context = await this.createAudioGraph();
      const source = context.createMediaStreamSource(this.stream);
      source.connect(this.worklet!);
    } catch (error) {
      await this.client.stop();
      throw error;
    }
  }

  async startMediaElement(
    element: HTMLMediaElement,
    sourceLanguage: RealtimeSourceLanguage,
    targetLanguage: RealtimeTargetLanguage,
    persistTranscript: boolean,
    sessionMode: SessionMode = 'meeting',
    speakerDetection = false,
    speakerFocusMode: SpeakerFocusMode = 'all',
    speakerId: string | null = null
  ): Promise<void> {
    await this.stop();
    await this.client.connect(sourceLanguage, targetLanguage, persistTranscript, sessionMode, 'media_file', speakerDetection, speakerFocusMode, speakerId);
    try {
      const context = await this.createAudioGraph();
      this.elementSource = context.createMediaElementSource(element);
      this.playbackGain = context.createGain();
      this.playbackGain.gain.value = 1;
      this.elementSource.connect(this.worklet!);
      this.elementSource.connect(this.playbackGain).connect(context.destination);
    } catch (error) {
      await this.client.stop();
      throw error;
    }
  }

  async stop(): Promise<void> {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    try { this.elementSource?.disconnect(); } catch (_) { /* noop */ }
    this.elementSource = null;
    try { this.playbackGain?.disconnect(); } catch (_) { /* noop */ }
    this.playbackGain = null;
    try { this.worklet?.disconnect(); } catch (_) { /* noop */ }
    this.worklet = null;
    if (this.context) {
      try { await this.context.close(); } catch (_) { /* noop */ }
    }
    this.context = null;
    await this.client.stop();
  }
}
