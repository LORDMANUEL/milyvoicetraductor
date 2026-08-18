import { desktopApi } from './api';
import type { RealtimeEvent } from '../types';

export type RealtimeEventHandler = (event: RealtimeEvent) => void;

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
  private sourceLanguage: 'auto' | 'en' | 'zh' = 'auto';
  private handler: RealtimeEventHandler;

  constructor(handler: RealtimeEventHandler) {
    this.handler = handler;
  }

  async connect(
    sourceLanguage: 'auto' | 'en' | 'zh',
    persistTranscript: boolean
  ): Promise<void> {
    await this.close();
    const session = await desktopApi.getLocalEngineSession();
    this.sourceLanguage = sourceLanguage;
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
          targetLanguage: 'es',
          persistTranscript,
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
          reject(new Error(payload.message || 'El motor local rechazó la sesión.'));
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
      targetLanguage: 'es',
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
        targetLanguage: 'es'
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
  private outputSuppressed = false;

  constructor(handler: RealtimeEventHandler) {
    this.client = new LocalRealtimeClient(handler);
  }

  setOutputSuppressed(suppressed: boolean): void {
    this.outputSuppressed = suppressed;
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
      if (!this.outputSuppressed) this.client.sendPcm(message.data);
    };
    return context;
  }

  async startMicrophone(
    sourceLanguage: 'auto' | 'en' | 'zh',
    persistTranscript: boolean
  ): Promise<void> {
    await this.stop();
    await this.client.connect(sourceLanguage, persistTranscript);
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
    sourceLanguage: 'auto' | 'en' | 'zh',
    persistTranscript: boolean
  ): Promise<void> {
    await this.stop();
    await this.client.connect(sourceLanguage, persistTranscript);
    try {
      if (!navigator.mediaDevices.getDisplayMedia) {
        throw new Error('Este WebView no admite captura de audio del sistema.');
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
    sourceLanguage: 'auto' | 'en' | 'zh',
    persistTranscript: boolean
  ): Promise<void> {
    await this.stop();
    await this.client.connect(sourceLanguage, persistTranscript);
    try {
      const context = await this.createAudioGraph();
      this.elementSource = context.createMediaElementSource(element);
      this.elementSource.connect(this.worklet!);
      this.elementSource.connect(context.destination);
    } catch (error) {
      await this.client.stop();
      throw error;
    }
  }

  async stop(): Promise<void> {
    this.outputSuppressed = false;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    try { this.elementSource?.disconnect(); } catch (_) { /* noop */ }
    this.elementSource = null;
    try { this.worklet?.disconnect(); } catch (_) { /* noop */ }
    this.worklet = null;
    if (this.context) {
      try { await this.context.close(); } catch (_) { /* noop */ }
    }
    this.context = null;
    await this.client.stop();
  }
}
