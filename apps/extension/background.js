/**
 * Orquestador Manifest V3. Desktop y extensión se descubren mediante Native
 * Messaging; ninguna credencial se guarda en chrome.storage.local.
 */

const OFFSCREEN_URL = chrome.runtime.getURL('offscreen.html');
const NATIVE_HOST = 'com.milyvoice.traductor';
const MEETING_URL = /^https:\/\/(meet\.google\.com|([^/]+\.)?teams\.microsoft\.com|([^/]+\.)?zoom\.us)\//;

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

async function setCaptureState(state) {
  await chrome.storage.session.set({ captureState: state });
}

async function startCapture(options) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error('No hay una pestaña activa.');
  if (!MEETING_URL.test(tab.url || '')) {
    throw new Error('Abre Google Meet, Microsoft Teams Web o Zoom Web.');
  }

  // `hello` pide al bridge arrancar el motor si está detenido y emitir una
  // credencial efímera. Esa credencial solo vive en memoria y en el offscreen.
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

  await ensureOffscreenDocument();
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
  const response = await chrome.runtime.sendMessage({
    target: 'offscreen',
    type: 'START_CAPTURE',
    streamId,
    tabId: tab.id,
    credential: bridge.credential,
    sourceLanguage: options.sourceLanguage || 'auto',
    persistTranscript: Boolean(options.persistTranscript),
    enginePort: bridge.port
  });
  if (!response?.ok) throw new Error(response?.error || 'No se pudo iniciar la captura.');
  await setCaptureState({ active: true, tabId: tab.id, startedAt: Date.now() });
  return { ok: true };
}

async function stopCapture() {
  await ensureOffscreenDocument();
  await chrome.runtime.sendMessage({ target: 'offscreen', type: 'STOP_CAPTURE' });
  await setCaptureState({ active: false, tabId: null, startedAt: null });
  return { ok: true };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target === 'offscreen') return false;

  if (message?.type === 'GET_BRIDGE_STATUS') {
    requestBridge('hello', 7000)
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

  if (message?.type === 'TRANSLATION_EVENT' && Number.isInteger(message.tabId)) {
    chrome.tabs.sendMessage(message.tabId, {
      type: 'MILYVOICE_SUBTITLE',
      payload: message.payload
    }).catch(() => undefined);
    return false;
  }

  if (message?.type === 'ENGINE_EVENT') {
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
