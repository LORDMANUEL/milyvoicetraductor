const source = document.querySelector('#source');
const sessionMode = document.querySelector('#sessionMode');
const persist = document.querySelector('#persist');
const showOriginal = document.querySelector('#showOriginal');
const speakerDetection = document.querySelector('#speakerDetection');
const speakerControls = document.querySelector('#speakerControls');
const speakerFocus = document.querySelector('#speakerFocus');
const fixedSpeakerWrap = document.querySelector('#fixedSpeakerWrap');
const fixedSpeaker = document.querySelector('#fixedSpeaker');
const ttsEnabled = document.querySelector('#ttsEnabled');
const ttsVoiceWrap = document.querySelector('#ttsVoiceWrap');
const ttsVoice = document.querySelector('#ttsVoice');
const speakerVoiceList = document.querySelector('#speakerVoiceList');
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
let knownSpeakers = [];
let availableVoices = [];
let speakerVoiceNames = {};

function setDot(element, state) {
  element.classList.toggle('ok', state === 'ok');
  element.classList.toggle('warn', state === 'warn');
  element.classList.toggle('error', state === 'error');
}

function speakerLabel(id) {
  return /^speaker-[a-z]$/.test(String(id || '')) ? `Hablante ${id.slice(-1).toUpperCase()}` : String(id || '');
}

function renderBridge(state, connected = true) {
  // El motor puede estar detenido cuando se abre el popup. START_CAPTURE usa
  // Native Messaging `hello`, que lo arranca y entrega la credencial efímera.
  bridgeReady = Boolean(connected && state?.modelPack);
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
  source.disabled = active;
  sessionMode.disabled = active;
  speakerDetection.disabled = active;
}

function renderSpeakerControls() {
  speakerControls.hidden = !speakerDetection.checked;
  fixedSpeakerWrap.hidden = !speakerDetection.checked || speakerFocus.value !== 'fixed';
}

function populateSpeakerSelect() {
  const selected = fixedSpeaker.value;
  fixedSpeaker.replaceChildren(new Option('Seleccione…', ''));
  for (const id of knownSpeakers) fixedSpeaker.appendChild(new Option(speakerLabel(id), id));
  fixedSpeaker.value = knownSpeakers.includes(selected) ? selected : '';
}

function makeVoiceOptions(select, selected) {
  select.replaceChildren(new Option('Voz predeterminada', ''));
  for (const voice of availableVoices) {
    const label = `${voice.voiceName || voice.name || 'Voz'} · ${voice.lang || 'es'}`;
    select.appendChild(new Option(label, voice.voiceName || voice.name || ''));
  }
  select.value = selected || '';
}

function renderSpeakerVoices() {
  speakerVoiceList.hidden = !ttsEnabled.checked || knownSpeakers.length === 0;
  speakerVoiceList.replaceChildren();
  if (speakerVoiceList.hidden) return;
  for (const id of knownSpeakers) {
    const label = document.createElement('label');
    label.textContent = `${speakerLabel(id)} · voz`;
    const select = document.createElement('select');
    makeVoiceOptions(select, speakerVoiceNames[id] || '');
    select.addEventListener('change', async () => {
      speakerVoiceNames = { ...speakerVoiceNames, [id]: select.value };
      await chrome.storage.local.set({ speakerVoiceNames });
    });
    label.appendChild(select);
    speakerVoiceList.appendChild(label);
  }
}

function renderTtsControls() {
  ttsVoiceWrap.hidden = !ttsEnabled.checked;
  renderSpeakerVoices();
}

function renderEngineEvent(event) {
  if (!event) return;
  status.classList.remove('error');
  if (event.type === 'engine.ready' || event.type === 'connected') status.textContent = 'Motor local conectado';
  else if (event.type === 'engine.loading') status.textContent = event.phase === 'warming' ? 'Precalentando modelos locales…' : 'Cargando modelos locales…';
  else if (event.type === 'session.started') status.textContent = event.sessionMode === 'karaoke' ? 'Karaoke activo · escuchando audio…' : 'Escuchando audio…';
  else if (event.type === 'speaker.changed' && event.speakerId) status.textContent = `${speakerLabel(event.speakerId)} activo`;
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
    sessionMode: sessionMode.value,
    persistTranscript: persist.checked,
    showOriginal: showOriginal.checked,
    speakerDetection: speakerDetection.checked,
    speakerFocusMode: speakerFocus.value,
    speakerId: fixedSpeaker.value || null,
    ttsEnabled: ttsEnabled.checked,
    ttsVoiceName: ttsVoice.value,
    speakerVoiceNames
  });
}

async function refreshBridge() {
  status.textContent = 'Detectando MilyVoiceTraductor…';
  const response = await chrome.runtime.sendMessage({ type: 'GET_BRIDGE_STATUS' });
  renderBridge(response?.state, Boolean(response?.ok));
}

async function loadVoices() {
  availableVoices = await new Promise((resolve) => chrome.tts.getVoices((voices) => resolve(voices || [])));
  makeVoiceOptions(ttsVoice, ttsVoice.value);
  renderSpeakerVoices();
}

async function loadSettings() {
  const saved = await chrome.storage.local.get([
    'sourceLanguage', 'sessionMode', 'persistTranscript', 'showOriginal',
    'speakerDetection', 'speakerFocusMode', 'speakerId', 'ttsEnabled', 'ttsVoiceName', 'speakerVoiceNames'
  ]);
  source.value = saved.sourceLanguage || 'auto';
  sessionMode.value = saved.sessionMode || 'meeting';
  persist.checked = Boolean(saved.persistTranscript);
  showOriginal.checked = saved.showOriginal !== false;
  speakerDetection.checked = Boolean(saved.speakerDetection);
  speakerFocus.value = saved.speakerFocusMode || 'all';
  ttsEnabled.checked = Boolean(saved.ttsEnabled);
  speakerVoiceNames = saved.speakerVoiceNames && typeof saved.speakerVoiceNames === 'object' ? saved.speakerVoiceNames : {};
  const session = await chrome.storage.session.get(['captureState', 'engineEvent', 'bridgeState', 'knownSpeakers']);
  knownSpeakers = Array.isArray(session.knownSpeakers) ? session.knownSpeakers : [];
  populateSpeakerSelect();
  fixedSpeaker.value = saved.speakerId && knownSpeakers.includes(saved.speakerId) ? saved.speakerId : '';
  renderSpeakerControls();
  await loadVoices();
  ttsVoice.value = saved.ttsVoiceName || '';
  renderTtsControls();
  if (session.bridgeState) renderBridge(session.bridgeState, session.bridgeState.connected !== false);
  renderCapture(Boolean(session.captureState?.active));
  renderEngineEvent(session.engineEvent);
  await refreshBridge();
}

for (const element of [source, sessionMode, persist, showOriginal, ttsVoice]) {
  element.addEventListener('change', savePreferences);
}

speakerDetection.addEventListener('change', async () => {
  renderSpeakerControls();
  await savePreferences();
});

ttsEnabled.addEventListener('change', async () => {
  renderTtsControls();
  await savePreferences();
});

async function changeSpeakerFocus() {
  renderSpeakerControls();
  await savePreferences();
  if (toggle.dataset.active !== '1') return;
  if (speakerFocus.value === 'fixed' && !fixedSpeaker.value) return;
  const response = await chrome.runtime.sendMessage({
    type: 'SET_SPEAKER_FOCUS',
    options: { speakerFocusMode: speakerFocus.value, speakerId: fixedSpeaker.value || null }
  });
  if (!response?.ok) {
    status.textContent = response?.error || 'No se pudo cambiar el foco de hablante.';
    status.classList.add('error');
  }
}

speakerFocus.addEventListener('change', changeSpeakerFocus);
fixedSpeaker.addEventListener('change', changeSpeakerFocus);

toggle.addEventListener('click', async () => {
  await savePreferences();
  const active = toggle.dataset.active === '1';
  if (!active && speakerDetection.checked && speakerFocus.value === 'fixed' && !fixedSpeaker.value) {
    status.textContent = 'Detecta primero hablantes o selecciona Todos/Voz dominante.';
    status.classList.add('error');
    return;
  }
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
            sessionMode: sessionMode.value,
            persistTranscript: persist.checked,
            speakerDetection: speakerDetection.checked,
            speakerFocusMode: speakerFocus.value,
            speakerId: fixedSpeaker.value || null
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
    chrome.storage.session.get(['captureState', 'engineEvent', 'bridgeState', 'knownSpeakers']).then((session) => {
      if (session.bridgeState) renderBridge(session.bridgeState, session.bridgeState.connected !== false);
      knownSpeakers = Array.isArray(session.knownSpeakers) ? session.knownSpeakers : [];
      const selected = fixedSpeaker.value;
      populateSpeakerSelect();
      if (knownSpeakers.includes(selected)) fixedSpeaker.value = selected;
      renderSpeakerVoices();
      renderCapture(Boolean(session.captureState?.active));
      renderEngineEvent(session.engineEvent);
    });
  }
});

loadSettings().catch((error) => {
  renderBridge(null, false);
  status.textContent = error?.message || 'No se pudo detectar MilyVoiceTraductor.';
});
