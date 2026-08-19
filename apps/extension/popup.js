const source = document.querySelector('#source');
const sessionMode = document.querySelector('#sessionMode');
const subtitleTheme = document.querySelector('#subtitleTheme');
const tutorControls = document.querySelector('#tutorControls');
const tutorVoice = document.querySelector('#tutorVoice');
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
  const engineStartable = state?.engine === 'ready' || state?.engine === 'stopped';
  bridgeReady = Boolean(connected && engineStartable && state?.modelPack);
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

function renderTutorControls() {
  const enabled = sessionMode.value === 'tutor';
  tutorControls.hidden = !enabled;
  if (enabled) showOriginal.checked = true;
}

function populateSpeakerSelect() {
  const selected = fixedSpeaker.value;
  fixedSpeaker.replaceChildren(new Option('Seleccione…', ''));
  for (const id of knownSpeakers) fixedSpeaker.appendChild(new Option(speakerLabel(id), id));
  fixedSpeaker.value = knownSpeakers.includes(selected) ? selected : '';
}

function voiceLanguagePrefix(voice) {
  return String(voice.lang || '').toLowerCase().slice(0, 2);
}

function voicesFor(prefixes) {
  const wanted = new Set(prefixes);
  const filtered = availableVoices.filter((voice) => wanted.has(voiceLanguagePrefix(voice)));
  return filtered.length ? filtered : availableVoices;
}

function makeVoiceOptions(select, selected, voices = availableVoices, emptyLabel = 'Voz predeterminada') {
  select.replaceChildren(new Option(emptyLabel, ''));
  for (const voice of voices) {
    const label = `${voice.voiceName || voice.name || 'Voz'} · ${voice.lang || ''}`;
    select.appendChild(new Option(label, voice.voiceName || voice.name || ''));
  }
  select.value = selected || '';
}

function renderSpeakerVoices() {
  speakerVoiceList.hidden = !ttsEnabled.checked || knownSpeakers.length === 0;
  speakerVoiceList.replaceChildren();
  if (speakerVoiceList.hidden) return;
  const spanishVoices = voicesFor(['es']);
  for (const id of knownSpeakers) {
    const label = document.createElement('label');
    label.textContent = `${speakerLabel(id)} · voz`;
    const select = document.createElement('select');
    makeVoiceOptions(select, speakerVoiceNames[id] || '', spanishVoices);
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

function refreshVoiceOptions() {
  makeVoiceOptions(ttsVoice, ttsVoice.value, voicesFor(['es']), 'Voz española automática');
  const sourcePrefix = source.value === 'auto' ? ['en', 'zh', 'es'] : [source.value];
  makeVoiceOptions(tutorVoice, tutorVoice.value, voicesFor(sourcePrefix), 'Voz automática');
  renderSpeakerVoices();
}

function renderEngineEvent(event) {
  if (!event) return;
  status.classList.remove('error');
  if (event.type === 'engine.ready' || event.type === 'connected') status.textContent = 'Motor local conectado';
  else if (event.type === 'engine.loading') status.textContent = event.phase === 'warming' ? 'Precalentando modelos locales…' : 'Cargando modelos locales…';
  else if (event.type === 'session.started') status.textContent = sessionMode.value === 'tutor' ? 'Tutor activo · escuchando y preparando práctica…' : event.sessionMode === 'karaoke' ? 'Karaoke activo · escuchando audio…' : 'Escuchando audio…';
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
    subtitleTheme: subtitleTheme.value,
    tutorVoiceName: tutorVoice.value,
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
  refreshVoiceOptions();
}

async function loadSettings() {
  const saved = await chrome.storage.local.get([
    'sourceLanguage', 'sessionMode', 'subtitleTheme', 'tutorVoiceName', 'persistTranscript', 'showOriginal',
    'speakerDetection', 'speakerFocusMode', 'speakerId', 'ttsEnabled', 'ttsVoiceName', 'speakerVoiceNames'
  ]);
  source.value = saved.sourceLanguage || 'auto';
  sessionMode.value = saved.sessionMode || 'meeting';
  subtitleTheme.value = saved.subtitleTheme || 'auto';
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
  renderTutorControls();
  await loadVoices();
  ttsVoice.value = saved.ttsVoiceName || '';
  tutorVoice.value = saved.tutorVoiceName || '';
  refreshVoiceOptions();
  renderTtsControls();
  if (session.bridgeState) renderBridge(session.bridgeState, session.bridgeState.connected !== false);
  renderCapture(Boolean(session.captureState?.active));
  renderEngineEvent(session.engineEvent);
  await refreshBridge();
}

for (const element of [persist, showOriginal, ttsVoice, subtitleTheme, tutorVoice]) {
  element.addEventListener('change', savePreferences);
}

source.addEventListener('change', async () => {
  refreshVoiceOptions();
  await savePreferences();
});

sessionMode.addEventListener('change', async () => {
  renderTutorControls();
  await savePreferences();
});

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
            sessionMode: sessionMode.value === 'tutor' ? 'education' : sessionMode.value,
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
  status.textContent = active ? 'Traducción detenida.' : sessionMode.value === 'tutor' ? 'Tutor activo sobre esta pestaña.' : 'Escuchando esta pestaña.';
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
