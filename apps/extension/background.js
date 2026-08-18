import { speakTranslation } from './tts.js';

/**
 * Orquestador Manifest V3. Desktop y extensión se descubren mediante Native
 * Messaging; ninguna credencial se guarda en chrome.storage.local.
 */

const OFFSCREEN_URL = chrome.runtime.getURL('offscreen.html');
const NATIVE_HOST = 'com.milyvoice.traductor';
const WEB_URL = /^https?:\/\//i;
const PROTECTED_HOSTS = new Set([
  'chromewebstore.google.com',
  'chrome.google.com',
  'microsoftedge.microsoft.com'
]);
const SESSION_MODES = new Set(['meeting', 'education', 'karaoke', 'compact']);
const SPEAKER_FOCUS_MODES = new Set(['all', 'dominant', 'fixed']);

let nativePort = null;
let pendingBridgeRequest = null;

async function ensureOffscreenDocument() {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT'],
    documentUrls: [OFFSCREEN_URL]
  });
  if (contexts.length === 0) {
    await chrome.offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['USER_MEDIA'],
      justification: 'Procesar localmente el audio de la pestaña seleccionada para subtítulos.'
    });
  }
}

async function ensureOverlay(tabId) {
  try {
    await chrome.scripting.insertCSS({ target: { tabId }, files: ['overlay.css'] });
    await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
  } catch (_) {
    throw new Error('El navegador no permitió mostrar subtítulos sobre esta página protegida.');
  }
}

function publicBridgeState(message, connected = true) {
  return {
    connected,
    desktop: message?.desktop || (connected ? 'unknown' : 'notInstalled'),
    engine: message?.engine || 'notInstalled',
    modelPack: message?.modelPack || null,
    message: message?.message || (connected ? 'Consultando MilyVoiceTraductor…' : 'Aplicación no detectada.')
  };
}

async function persistPublicBridgeState(message, connected = true) {
  const bridgeState = publicBridgeState(message, connected);
  await chrome.storage.session.set({ bridgeState, bridgeStateAt: Date.now() });
  return bridgeState;
}

function disconnectNativePort() {
  try { nativePort?.disconnect(); } catch (_) {}
  nativePort = null;
  if (pendingBridgeRequest) {
    pendingBridgeRequest.reject(new Error('MilyVoiceTraductor no está disponible.'));
    pendingBridgeRequest = null;
  }
}

function connectNativeHost() {
  if (nativePort) return nativePort;
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST);
  } catch (_) {
    nativePort = null;
    return null;
  }

  nativePort.onMessage.addListener((message) => {
    persistPublicBridgeState(message, message?.type !== 'bridge.error').catch(() => undefined);
    if (pendingBridgeRequest) {
      const pending = pendingBridgeRequest;
      pendingBridgeRequest = null;
      if (message?.type === 'bridge.error') pending.reject(new Error(message.message || 'Error del bridge local.'));
      else pending.resolve(message);
    }
  });

  nativePort.onDisconnect.addListener(() => {
    const lastError = chrome.runtime.lastError?.message || '';
    nativePort = null;
    persistPublicBridgeState(null, false).catch(() => undefined);
    if (pendingBridgeRequest) {
      const pending = pendingBridgeRequest;
      pendingBridgeRequest = null;
      pending.reject(new Error(lastError || 'MilyVoiceTraductor no está instalado o el bridge no está registrado.'));
    }
  });
  return nativePort;
}

function requestBridge(type = 'status', timeoutMs = 3500) {
  return new Promise((resolve, reject) => {
    if (pendingBridgeRequest) {
      reject(new Error('El bridge local está atendiendo otra solicitud.'));
      return;
    }
    const port = connectNativeHost();
    if (!port) {
      reject(new Error('MilyVoiceTraductor no está instalado o el bridge no está registrado.'));
      return;
    }
    const timer = setTimeout(() => {
      if (pendingBridgeRequest?.resolve === resolve) pendingBridgeRequest = null;
      disconnectNativePort();
      reject(new Error('MilyVoiceTraductor no respondió a tiempo.'));
    }, timeoutMs);
    pendingBridgeRequest = {
      resolve: (message) => { clearTimeout(timer); resolve(message); },
      reject: (error) => { clearTimeout(timer); reject(error); }
    };
    try {
      port.postMessage({ protocol: 1, type });
    } catch (error) {
      clearTimeout(timer);
      pendingBridgeRequest = null;
      disconnectNativePort();
      reject(error);
    }
  });
}

function assertCapturableTab(tab) {
  const rawUrl = tab?.url || '';
  if (!WEB_URL.test(rawUrl)) {
    throw new Error('Esta página está protegida por el navegador y no permite captura. Abre un sitio web http/https.');
  }
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch (_) {
    throw new Error('La pestaña activa no tiene una URL capturable.');
  }
  const host = parsed.hostname.toLowerCase();
  if (PROTECTED_HOSTS.has(host) || (host === 'chrome.google.com' && parsed.pathname.startsWith('/webstore'))) {
    throw new Error('La tienda de extensiones es una página protegida y no permite captura de audio.');
  }
}

async function setCaptureState(state) {
  await chrome.storage.session.set({ captureState: state });
}

async function rememberSpeaker(speakerId) {
  if (!/^speaker-[a-z]$/.test(String(speakerId || ''))) return;
  const { knownSpeakers = [] } = await chrome.storage.session.get('knownSpeakers');
  if (!knownSpeakers.includes(speakerId)) {
    await chrome.storage.session.set({ knownSpeakers: [...knownSpeakers, speakerId] });
  }
}

async function startCapture(options) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error('No hay una pestaña activa.');
  assertCapturableTab(tab);

  const bridge = await requestBridge('hello', 7000);
  if (bridge.engine !== 'ready') {
    throw new Error(bridge.message || 'El motor local todavía no está listo.');
  }
  if (!bridge.modelPack) {
    throw new Error('MilyVoiceTraductor está preparando el modelo local.');
  }
  if (!bridge.credential || !bridge.port) {
    throw new Error('No se pudo crear una sesión segura con el motor local.');
  }

  await ensureOverlay(tab.id);
  await ensureOffscreenDocument();
  let streamId;
  try {
    streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
  } catch (_) {
    throw new Error('Chrome/Edge no permitió capturar el audio de esta pestaña. Prueba otra pestaña o usa Audio del sistema en MilyVoiceTraductor.');
  }
  const requestedMode = String(options.sessionMode || 'meeting');
  const sessionMode = SESSION_MODES.has(requestedMode) ? requestedMode : 'meeting';
  const requestedFocus = String(options.speakerFocusMode || 'all');
  const speakerFocusMode = SPEAKER_FOCUS_MODES.has(requestedFocus) ? requestedFocus : 'all';
  const speakerId = /^speaker-[a-z]$/.test(String(options.speakerId || '')) ? String(options.speakerId) : null;
  if (speakerFocusMode === 'fixed' && !speakerId) {
    throw new Error('Selecciona un hablante antes de usar el modo Fijado.');
  }
  const speakerDetection = Boolean(options.speakerDetection);
  const response = await chrome.runtime.sendMessage({
    target: 'offscreen',
    type: 'START_CAPTURE',
    streamId,
    tabId: tab.id,
    credential: bridge.credential,
    sourceLanguage: options.sourceLanguage || 'auto',
    sessionMode,
    speakerDetection,
    speakerFocusMode,
    speakerId,
    persistTranscript: Boolean(options.persistTranscript),
    enginePort: bridge.port
  });
  if (!response?.ok) throw new Error(response?.error || 'No se pudo iniciar la captura.');
  const startedAt = Date.now();
  await chrome.storage.session.set({ knownSpeakers: [] });
  await setCaptureState({ active: true, tabId: tab.id, startedAt, source: 'browser_tab', sessionMode, speakerDetection, speakerFocusMode, speakerId });
  return { ok: true };
}

async function stopCapture() {
  await ensureOffscreenDocument();
  chrome.tts.stop();
  await chrome.runtime.sendMessage({ target: 'offscreen', type: 'TTS_FINISHED', speakerId: null }).catch(() => undefined);
  await chrome.runtime.sendMessage({ target: 'offscreen', type: 'STOP_CAPTURE' });
  await setCaptureState({ active: false, tabId: null, startedAt: null, source: null, sessionMode: null, speakerDetection: false, speakerFocusMode: 'all', speakerId: null });
  await chrome.storage.session.set({ knownSpeakers: [] });
  return { ok: true };
}

async function setSpeakerFocus(options) {
  const mode = SPEAKER_FOCUS_MODES.has(String(options?.speakerFocusMode)) ? String(options.speakerFocusMode) : 'all';
  const speakerId = /^speaker-[a-z]$/.test(String(options?.speakerId || '')) ? String(options.speakerId) : null;
  if (mode === 'fixed' && !speakerId) throw new Error('Selecciona un hablante para fijarlo.');
  const response = await chrome.runtime.sendMessage({ target: 'offscreen', type: 'SET_SPEAKER_FOCUS', speakerFocusMode: mode, speakerId });
  if (!response?.ok) throw new Error('La sesión local todavía no está lista para cambiar el foco.');
  const { captureState } = await chrome.storage.session.get('captureState');
  if (captureState?.active) await setCaptureState({ ...captureState, speakerFocusMode: mode, speakerId });
  return { ok: true };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target === 'offscreen') return false;

  if (message?.type === 'GET_BRIDGE_STATUS') {
    requestBridge('status', 3500)
      .then((bridge) => sendResponse({ ok: true, state: publicBridgeState(bridge, true) }))
      .catch(async (error) => {
        const state = await persistPublicBridgeState(null, false);
        sendResponse({ ok: false, state, error: error.message || 'Aplicación no detectada.' });
      });
    return true;
  }

  if (message?.type === 'START_CAPTURE') {
    startCapture(message.options || {})
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error.message || 'No se pudo iniciar.' }));
    return true;
  }

  if (message?.type === 'STOP_CAPTURE') {
    stopCapture()
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error.message || 'No se pudo detener.' }));
    return true;
  }

  if (message?.type === 'SET_SPEAKER_FOCUS') {
    setSpeakerFocus(message.options || {})
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error.message || 'No se pudo cambiar el foco.' }));
    return true;
  }

  if (message?.type === 'TRANSLATION_EVENT' && Number.isInteger(message.tabId)) {
    if (message.payload?.speakerId) rememberSpeaker(message.payload.speakerId).catch(() => undefined);
    if (message.payload?.type === 'translation.final') {
      speakTranslation(message.payload, {
        onStart({ text, speakerId }) {
          chrome.runtime.sendMessage({ target: 'offscreen', type: 'TTS_STARTED', text, speakerId }).catch(() => undefined);
        },
        onEnd({ speakerId }) {
          chrome.runtime.sendMessage({ target: 'offscreen', type: 'TTS_FINISHED', speakerId }).catch(() => undefined);
        }
      }).catch(() => undefined);
    }
    chrome.storage.session.get('captureState').then(({ captureState }) => {
      chrome.tabs.sendMessage(message.tabId, {
        type: 'MILYVOICE_SUBTITLE',
        payload: message.payload,
        sessionMode: captureState?.sessionMode || 'meeting',
        sessionStartedAt: captureState?.startedAt || Date.now()
      }).catch(() => undefined);
    });
    return false;
  }

  if (message?.type === 'ENGINE_EVENT') {
    if (message.payload?.speakerId) rememberSpeaker(message.payload.speakerId).catch(() => undefined);
    chrome.storage.session.set({ engineEvent: message.payload, engineEventAt: Date.now() });
    return false;
  }

  return false;
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const { captureState } = await chrome.storage.session.get('captureState');
  if (captureState?.active && captureState.tabId === tabId) {
    await stopCapture().catch(() => undefined);
  }
});
