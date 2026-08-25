import { setDuckingGain, restoreGain } from './tts/ducking.js';

/**
 * Documento offscreen: recibe el stream de la pestaña, conserva la reproducción
 * a la frecuencia nativa del dispositivo y transmite una copia PCM16/16 kHz.
 */
let mediaStream = null;
let audioContext = null;
let workletNode = null;
let playbackGainNode = null;
let websocket = null;
let activeTabId = null;
let stopping = false;
let binaryPcmActive = false;
let sessionReady = false;

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

function publishEngineEvent(payload) {
  chrome.runtime.sendMessage({ type: 'ENGINE_EVENT', payload }).catch(() => undefined);
}

function publishTranslation(payload) {
  if (!activeTabId) return;
  chrome.runtime.sendMessage({ type: 'TRANSLATION_EVENT', tabId: activeTabId, payload }).catch(() => undefined);
}

function sendControl(type, fields = {}) {
  if (websocket?.readyState !== WebSocket.OPEN || !sessionReady) return false;
  websocket.send(JSON.stringify({ protocol: 1, type, targetLanguage: 'es', ...fields }));
  return true;
}

async function cleanup() {
  stopping = true;
  restoreGain(playbackGainNode?.gain);
  if (websocket && websocket.readyState === WebSocket.OPEN && sessionReady) {
    websocket.send(JSON.stringify({ protocol: 1, type: 'audio.stop', sourceLanguage: 'auto', targetLanguage: 'es' }));
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  try { websocket?.close(1000, 'user stop'); } catch (_) {}
  try { workletNode?.disconnect(); } catch (_) {}
  try { playbackGainNode?.disconnect(); } catch (_) {}
  try { await audioContext?.close(); } catch (_) {}
  for (const track of mediaStream?.getTracks?.() || []) track.stop();
  websocket = null;
  workletNode = null;
  playbackGainNode = null;
  audioContext = null;
  mediaStream = null;
  activeTabId = null;
  binaryPcmActive = false;
  sessionReady = false;
  stopping = false;
}

async function startCapture(message) {
  await cleanup();
  if (!message.credential || !message.enginePort) {
    throw new Error('No se recibió una sesión segura desde MilyVoiceTraductor.');
  }
  activeTabId = message.tabId;
  const constraints = {
    audio: {
      mandatory: {
        chromeMediaSource: 'tab',
        chromeMediaSourceId: message.streamId
      }
    },
    video: false
  };
  mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

  // No fijar el contexto a 16 kHz: tabCapture necesita reinyectar el audio de la
  // reunión y debe conservar la frecuencia nativa del dispositivo (habitualmente 48 kHz).
  // El worklet crea únicamente la copia 16 kHz que consume Whisper.
  audioContext = new AudioContext({ latencyHint: 'interactive' });
  await audioContext.audioWorklet.addModule('audio-worklet.js');
  const source = audioContext.createMediaStreamSource(mediaStream);
  workletNode = new AudioWorkletNode(audioContext, 'milyvoice-pcm', {
    numberOfInputs: 1,
    numberOfOutputs: 0,
    channelCount: 1
  });
  source.connect(workletNode);

  // tabCapture puede silenciar la salida original; esta rama conserva audible la
  // reunión con la frecuencia nativa, separada de la copia 16 kHz del ASR.
  // TTS solo modifica este GainNode de reproducción: nunca el worklet/captura ASR.
  playbackGainNode = audioContext.createGain();
  playbackGainNode.gain.value = 1;
  source.connect(playbackGainNode).connect(audioContext.destination);

  const localPort = Math.min(65535, Math.max(1024, Number(message.enginePort) || 8765));
  const wsUrl = `ws://127.0.0.1:${localPort}/ws?token=${encodeURIComponent(message.credential)}`;
  websocket = new WebSocket(wsUrl);

  const readyPromise = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      if (!sessionReady) reject(new Error('El motor local no confirmó la sesión de audio a tiempo.'));
    }, 8000);

    const failBeforeReady = (messageText) => {
      if (sessionReady) return;
      clearTimeout(timeout);
      reject(new Error(messageText));
    };

    websocket.addEventListener('open', () => {
      websocket.send(JSON.stringify({
        protocol: 1,
        type: 'client.hello',
        sourceLanguage: message.sourceLanguage || 'auto',
        targetLanguage: 'es',
        sessionMode: message.sessionMode || 'meeting',
        sourceMode: 'browser_tab',
        speakerDetection: Boolean(message.speakerDetection),
        speakerFocusMode: message.speakerFocusMode || 'all',
        speakerId: message.speakerId || null,
        persistTranscript: Boolean(message.persistTranscript),
        binaryPcm: true
      }));
    });

    websocket.addEventListener('message', (event) => {
      let payload;
      try { payload = JSON.parse(event.data); } catch (_) { return; }
      if (payload.type === 'session.started') {
        binaryPcmActive = payload.binaryPcm === true;
        sessionReady = true;
        clearTimeout(timeout);
        publishEngineEvent({ type: 'connected' });
        resolve(payload);
      }
      if (payload.type === 'engine.error' && !sessionReady) {
        failBeforeReady(payload.message || 'El motor local rechazó el inicio de la sesión.');
      }
      if (
        payload.type === 'translation.final' ||
        payload.type === 'translation.partial' ||
        payload.type === 'transcription.partial' ||
        payload.type === 'transcription.final' ||
        payload.type === 'pipeline.metrics' ||
        payload.type === 'speaker.changed'
      ) {
        publishTranslation(payload);
      }
      publishEngineEvent(payload);
    });

    websocket.addEventListener('close', () => {
      binaryPcmActive = false;
      const wasReady = sessionReady;
      sessionReady = false;
      if (!wasReady) failBeforeReady('El motor local cerró la conexión antes de iniciar la sesión.');
      if (!stopping) publishEngineEvent({ type: 'disconnected' });
    });

    websocket.addEventListener('error', () => {
      publishEngineEvent({ type: 'error', message: 'No se pudo conectar al motor local.' });
      failBeforeReady('No se pudo conectar al motor local.');
    });
  });

  workletNode.port.onmessage = (event) => {
    if (websocket?.readyState !== WebSocket.OPEN || !sessionReady) return;
    if (binaryPcmActive) {
      websocket.send(event.data);
      return;
    }
    websocket.send(JSON.stringify({
      protocol: 1,
      type: 'audio.chunk',
      sourceLanguage: message.sourceLanguage || 'auto',
      targetLanguage: 'es',
      sampleRate: 16000,
      audioBase64: arrayBufferToBase64(event.data)
    }));
  };

  try {
    await readyPromise;
  } catch (error) {
    await cleanup();
    throw error;
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target !== 'offscreen') return false;
  if (message.type === 'START_CAPTURE') {
    startCapture(message)
      .then(() => sendResponse({ ok: true }))
      .catch(async (error) => {
        await cleanup();
        sendResponse({ ok: false, error: error.message || 'No se pudo capturar el audio.' });
      });
    return true;
  }
  if (message.type === 'STOP_CAPTURE') {
    cleanup().then(() => sendResponse({ ok: true }));
    return true;
  }
  if (message.type === 'SET_SPEAKER_FOCUS') {
    const ok = sendControl('speaker.focus', {
      speakerFocusMode: message.speakerFocusMode || 'all',
      speakerId: message.speakerId || null
    });
    sendResponse({ ok });
    return false;
  }
  if (message.type === 'TTS_STARTED') {
    setDuckingGain(playbackGainNode?.gain, Boolean(message.duckingEnabled), message.duckingLevel);
    const ok = sendControl('tts.started', { text: message.text || '', speakerId: message.speakerId || null });
    sendResponse({ ok });
    return false;
  }
  if (message.type === 'TTS_FINISHED') {
    restoreGain(playbackGainNode?.gain);
    const ok = sendControl('tts.finished', { speakerId: message.speakerId || null });
    sendResponse({ ok });
    return false;
  }
  return false;
});
