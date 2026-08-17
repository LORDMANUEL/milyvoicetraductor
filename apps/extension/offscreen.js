/**
 * Documento offscreen: recibe el stream de la pestaña, lo normaliza a 16 kHz,
 * conserva la reproducción local y transmite únicamente PCM al localhost.
 */
let mediaStream = null;
let audioContext = null;
let workletNode = null;
let websocket = null;
let activeTabId = null;
let stopping = false;

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

async function cleanup() {
  stopping = true;
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(JSON.stringify({ protocol: 1, type: 'audio.stop', sourceLanguage: 'auto', targetLanguage: 'es' }));
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  try { websocket?.close(1000, 'user stop'); } catch (_) {}
  try { workletNode?.disconnect(); } catch (_) {}
  try { await audioContext?.close(); } catch (_) {}
  for (const track of mediaStream?.getTracks?.() || []) track.stop();
  websocket = null;
  workletNode = null;
  audioContext = null;
  mediaStream = null;
  activeTabId = null;
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

  audioContext = new AudioContext({ sampleRate: 16000, latencyHint: 'interactive' });
  await audioContext.audioWorklet.addModule('audio-worklet.js');
  const source = audioContext.createMediaStreamSource(mediaStream);
  workletNode = new AudioWorkletNode(audioContext, 'milyvoice-pcm', {
    numberOfInputs: 1,
    numberOfOutputs: 0,
    channelCount: 1
  });
  source.connect(workletNode);

  // tabCapture puede silenciar la salida original; este enlace mantiene audible la reunión.
  const playbackGain = audioContext.createGain();
  playbackGain.gain.value = 1;
  source.connect(playbackGain).connect(audioContext.destination);

  const localPort = Math.min(65535, Math.max(1024, Number(message.enginePort) || 8765));
  const wsUrl = `ws://127.0.0.1:${localPort}/ws?token=${encodeURIComponent(message.credential)}`;
  websocket = new WebSocket(wsUrl);
  websocket.addEventListener('open', () => {
    websocket.send(JSON.stringify({
      protocol: 1,
      type: 'client.hello',
      sourceLanguage: message.sourceLanguage || 'auto',
      targetLanguage: 'es',
      persistTranscript: Boolean(message.persistTranscript)
    }));
    publishEngineEvent({ type: 'connected' });
  });
  websocket.addEventListener('message', (event) => {
    let payload;
    try { payload = JSON.parse(event.data); } catch (_) { return; }
    if (payload.type === 'translation.final') publishTranslation(payload);
    publishEngineEvent(payload);
  });
  websocket.addEventListener('close', () => {
    if (!stopping) publishEngineEvent({ type: 'disconnected' });
  });
  websocket.addEventListener('error', () => publishEngineEvent({ type: 'error', message: 'No se pudo conectar al motor local.' }));

  workletNode.port.onmessage = (event) => {
    if (websocket?.readyState !== WebSocket.OPEN) return;
    websocket.send(JSON.stringify({
      protocol: 1,
      type: 'audio.chunk',
      sourceLanguage: message.sourceLanguage || 'auto',
      targetLanguage: 'es',
      sampleRate: 16000,
      audioBase64: arrayBufferToBase64(event.data)
    }));
  };
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
  return false;
});
