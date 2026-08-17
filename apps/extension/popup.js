const token = document.querySelector('#token');
const source = document.querySelector('#source');
const port = document.querySelector('#port');
const persist = document.querySelector('#persist');
const showOriginal = document.querySelector('#showOriginal');
const toggle = document.querySelector('#toggle');
const status = document.querySelector('#status');

async function loadSettings() {
  const saved = await chrome.storage.local.get(['pairingToken', 'sourceLanguage', 'persistTranscript', 'showOriginal', 'enginePort']);
  token.value = saved.pairingToken || '';
  source.value = saved.sourceLanguage || 'auto';
  port.value = String(saved.enginePort || 8765);
  persist.checked = Boolean(saved.persistTranscript);
  showOriginal.checked = saved.showOriginal !== false;
  const session = await chrome.storage.session.get(['captureState', 'engineEvent']);
  renderCapture(Boolean(session.captureState?.active));
  renderEngineEvent(session.engineEvent);
}

function renderCapture(active) {
  toggle.dataset.active = active ? '1' : '0';
  toggle.textContent = active ? 'Detener traducción' : 'Iniciar traducción';
  toggle.classList.toggle('stop', active);
}

function renderEngineEvent(event) {
  status.classList.remove('error');
  if (!event) { status.textContent = 'Motor: sin conexión todavía'; return; }
  if (event.type === 'engine.ready' || event.type === 'connected') status.textContent = 'Motor local conectado';
  else if (event.type === 'engine.loading') status.textContent = 'Cargando modelos locales…';
  else if (event.type === 'session.started') status.textContent = 'Traduciendo reunión';
  else if (event.type === 'engine.error' || event.type === 'error') { status.textContent = event.message || 'Error del motor local'; status.classList.add('error'); }
  else if (event.type === 'disconnected') status.textContent = 'Motor desconectado';
}

async function saveSettings() {
  await chrome.storage.local.set({
    pairingToken: token.value.trim(),
    sourceLanguage: source.value,
    persistTranscript: persist.checked,
    showOriginal: showOriginal.checked,
    enginePort: Math.min(65535, Math.max(1024, Number(port.value) || 8765))
  });
}

for (const element of [token, port, source, persist, showOriginal]) element.addEventListener('change', saveSettings);

toggle.addEventListener('click', async () => {
  await saveSettings();
  const active = toggle.dataset.active === '1';
  toggle.disabled = true;
  const response = await chrome.runtime.sendMessage(active
    ? { type: 'STOP_CAPTURE' }
    : { type: 'START_CAPTURE', options: { sourceLanguage: source.value, persistTranscript: persist.checked, enginePort: Number(port.value) || 8765 } });
  toggle.disabled = false;
  if (!response?.ok) {
    status.textContent = response?.error || 'No se pudo ejecutar la acción.';
    status.classList.add('error');
    return;
  }
  renderCapture(!active);
});

chrome.storage.onChanged.addListener((_changes, areaName) => {
  if (areaName === 'session') loadSettings();
});
loadSettings();
