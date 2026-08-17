/**
 * Orquestador Manifest V3. La captura solo empieza como consecuencia de una
 * acción explícita del usuario desde el popup.
 */

const OFFSCREEN_URL = chrome.runtime.getURL('offscreen.html');

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

async function setCaptureState(state) {
  await chrome.storage.session.set({ captureState: state });
}

async function startCapture(options) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error('No hay una pestaña activa.');
  if (!/^https:\/\/(meet\.google\.com|([^/]+\.)?teams\.microsoft\.com|([^/]+\.)?zoom\.us)\//.test(tab.url || '')) {
    throw new Error('Abre Google Meet, Microsoft Teams Web o Zoom Web.');
  }

  const { pairingToken = '' } = await chrome.storage.local.get('pairingToken');
  if (!pairingToken || pairingToken.length < 40) {
    throw new Error('Empareja la extensión con el token de la aplicación.');
  }

  await ensureOffscreenDocument();
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
  await chrome.runtime.sendMessage({
    target: 'offscreen',
    type: 'START_CAPTURE',
    streamId,
    tabId: tab.id,
    token: pairingToken,
    sourceLanguage: options.sourceLanguage || 'auto',
    persistTranscript: Boolean(options.persistTranscript),
    enginePort: Math.min(65535, Math.max(1024, Number(options.enginePort) || 8765))
  });
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
