const source = document.querySelector('#source');
const persist = document.querySelector('#persist');
const showOriginal = document.querySelector('#showOriginal');
const toggle = document.querySelector('#toggle');
const status = document.querySelector('#status');
const downloadApp = document.querySelector('#downloadApp');
const appState = document.querySelector('#appState');
const engineState = document.querySelector('#engineState');
const modelState = document.querySelector('#modelState');
const appDot = document.querySelector('#appDot');
const engineDot = document.querySelector('#engineDot');
const modelDot = document.querySelector('#modelDot');

let bridgeReady = false;

function setDot(element, state) {
  element.classList.toggle('ok', state === 'ok');
  element.classList.toggle('warn', state === 'warn');
  element.classList.toggle('error', state === 'error');
}

function renderBridge(state, connected = true) {
  bridgeReady = Boolean(connected && state?.engine === 'ready' && state?.modelPack);
  appState.textContent = connected ? 'Detectada' : 'No instalada';
  engineState.textContent = state?.engine === 'ready' ? 'Activo' : state?.engine === 'stopped' ? 'Detenido' : 'No disponible';
  modelState.textContent = state?.modelPack ? 'Listo' : connected ? 'Preparando…' : 'No disponible';
  setDot(appDot, connected ? 'ok' : 'error');
  setDot(engineDot, state?.engine === 'ready' ? 'ok' : connected ? 'warn' : 'error');
  setDot(modelDot, state?.modelPack ? 'ok' : connected ? 'warn' : 'error');
  downloadApp.hidden = connected;

  const active = toggle.dataset.active === '1';
  if (!active) {
    toggle.disabled = !bridgeReady;
    toggle.textContent = bridgeReady ? 'Iniciar traducción' : connected ? 'Preparando modelo…' : 'Aplicación no detectada';
  }
  status.classList.toggle('error', !connected);
  status.textContent = state?.message || (connected ? 'MilyVoiceTraductor conectado.' : 'Instala MilyVoiceTraductor y vuelve a abrir la extensión.');
}

function renderCapture(active) {
  toggle.dataset.active = active ? '1' : '0';
  toggle.textContent = active ? 'Detener traducción' : bridgeReady ? 'Iniciar traducción' : 'Preparando…';
  toggle.classList.toggle('stop', active);
  toggle.disabled = active ? false : !bridgeReady;
}

function renderEngineEvent(event) {
  if (!event) return;
  status.classList.remove('error');
  if (event.type === 'engine.ready' || event.type === 'connected') status.textContent = 'Motor local conectado';
  else if (event.type === 'engine.loading') status.textContent = event.phase === 'warming' ? 'Precalentando modelos locales…' : 'Cargando modelos locales…';
  else if (event.type === 'session.started') status.textContent = 'Escuchando audio…';
  else if (event.type === 'transcription.partial') status.textContent = 'Transcribiendo en tiempo real…';
  else if (event.type === 'translation.partial') status.textContent = 'Traduciendo frase…';
  else if (event.type === 'translation.final') status.textContent = 'Traducción al día';
  else if (event.type === 'audio.level') {
    if (event.speech) status.textContent = 'Audio detectado · escuchando…';
    else if (Number(event.silentMs || 0) >= 3000) {
      status.textContent = 'No se detecta audio en esta fuente.';
      status.classList.add('error');
    } else status.textContent = 'Silencio · esperando voz…';
  } else if (event.type === 'pipeline.metrics') {
    if (event.pressure === 'overloaded') {
      status.textContent = 'CPU al límite · priorizando frases finales.';
      status.classList.add('error');
    } else if (event.pressure === 'pressure') {
      status.textContent = 'CPU ocupada · reduciendo parciales.';
    }
  } else if (event.type === 'engine.error' || event.type === 'error') {
    status.textContent = event.message || 'Error del motor local';
    status.classList.add('error');
  } else if (event.type === 'disconnected') status.textContent = 'Motor desconectado';
}

async function savePreferences() {
  await chrome.storage.local.set({
    sourceLanguage: source.value,
    persistTranscript: persist.checked,
    showOriginal: showOriginal.checked
  });
}

async function refreshBridge() {
  status.textContent = 'Detectando MilyVoiceTraductor…';
  const response = await chrome.runtime.sendMessage({ type: 'GET_BRIDGE_STATUS' });
  renderBridge(response?.state, Boolean(response?.ok));
}

async function loadSettings() {
  const saved = await chrome.storage.local.get(['sourceLanguage', 'persistTranscript', 'showOriginal']);
  source.value = saved.sourceLanguage || 'auto';
  persist.checked = Boolean(saved.persistTranscript);
  showOriginal.checked = saved.showOriginal !== false;
  const session = await chrome.storage.session.get(['captureState', 'engineEvent', 'bridgeState']);
  if (session.bridgeState) renderBridge(session.bridgeState, session.bridgeState.connected !== false);
  renderCapture(Boolean(session.captureState?.active));
  renderEngineEvent(session.engineEvent);
  await refreshBridge();
}

for (const element of [source, persist, showOriginal]) {
  element.addEventListener('change', savePreferences);
}

toggle.addEventListener('click', async () => {
  await savePreferences();
  const active = toggle.dataset.active === '1';
  toggle.disabled = true;
  status.classList.remove('error');
  status.textContent = active ? 'Deteniendo…' : 'Preparando sesión local…';

  const response = await chrome.runtime.sendMessage(
    active
      ? { type: 'STOP_CAPTURE' }
      : {
          type: 'START_CAPTURE',
          options: {
            sourceLanguage: source.value,
            persistTranscript: persist.checked
          }
        }
  );

  if (!response?.ok) {
    status.textContent = response?.error || 'No se pudo ejecutar la acción.';
    status.classList.add('error');
    toggle.disabled = !bridgeReady;
    return;
  }
  renderCapture(!active);
  status.textContent = active ? 'Traducción detenida.' : 'Escuchando esta pestaña.';
});

chrome.storage.onChanged.addListener((_changes, areaName) => {
  if (areaName === 'session') {
    chrome.storage.session.get(['captureState', 'engineEvent', 'bridgeState']).then((session) => {
      if (session.bridgeState) renderBridge(session.bridgeState, session.bridgeState.connected !== false);
      renderCapture(Boolean(session.captureState?.active));
      renderEngineEvent(session.engineEvent);
    });
  }
});

loadSettings().catch((error) => {
  renderBridge(null, false);
  status.textContent = error?.message || 'No se pudo detectar MilyVoiceTraductor.';
});
