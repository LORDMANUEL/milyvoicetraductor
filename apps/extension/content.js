/** Overlay aislado con Shadow DOM para cualquier pestaña web capturable. */
(() => {
  if (document.getElementById('milyvoice-overlay-host')) return;

  const host = document.createElement('div');
  host.id = 'milyvoice-overlay-host';
  document.documentElement.appendChild(host);
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      .box { position: fixed; z-index: 2147483647; left: 50%; bottom: 7vh; transform: translateX(-50%);
        width: min(900px, 88vw); font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
      .caption { display: none; color: #f7f4ea; border-radius: 18px; padding: 14px 18px; text-align: center;
        background: rgba(16,36,62,.94); border: 1px solid rgba(0,168,120,.7); box-shadow: 0 14px 50px rgba(0,0,0,.28); }
      .caption.visible { display: grid; gap: 5px; }
      .caption.theme-mily { background: rgba(16,36,62,.94); color:#f7f4ea; border-color:rgba(0,168,120,.7); }
      .caption.theme-cinema { background: rgba(5,7,11,.96); color:#fff; border-color:rgba(255,255,255,.16); }
      .caption.theme-class { background: rgba(250,252,255,.97); color:#10243e; border-color:#b9d5ff; box-shadow:0 14px 40px rgba(16,36,62,.18); }
      .caption.theme-class .original { color:#4b6688; }
      .caption.theme-contrast { background:#000; color:#fff; border:3px solid #fff; box-shadow:none; }
      .caption.theme-contrast .original,.caption.theme-contrast .brand { color:#fff; }
      .caption.theme-neon { background:rgba(6,10,18,.95); color:#f5fbff; border-color:#6fe0bd; box-shadow:0 0 28px rgba(111,224,189,.24); }
      .speaker { display: none; font-size: 11px; font-weight: 800; letter-spacing: .04em; }
      .speaker.visible { display: block; }
      .speaker.s0 { color:#57b9ff; } .speaker.s1 { color:#65e5ae; } .speaker.s2 { color:#ffac68; }
      .speaker.s3 { color:#bf96ff; } .speaker.s4 { color:#ff83b3; } .speaker.s5 { color:#b7c1ca; }
      .original { color: #9fb8dc; font-size: 14px; margin-bottom: 2px; }
      .translated { font-size: clamp(20px,2.4vw,30px); line-height: 1.25; font-weight: 700; letter-spacing: -.01em; }
      .caption.education .translated, .caption.karaoke .translated, .caption.tutor .translated { order: 2; }
      .caption.education .original, .caption.karaoke .original, .caption.tutor .original { order: 3; }
      .caption .speaker { order: 1; }
      .caption .tutor-tools { order: 4; }
      .caption .brand { order: 5; }
      .karaoke-word { border-radius: 4px; padding: 0 1px; transition: color .08s linear, background .08s linear; }
      .karaoke-word.active { color: #10243e; background: #6fe0bd; }
      .caption.karaoke .original { border-bottom: 3px solid #6fe0bd; padding-bottom: 4px; }
      .tutor-tools { display:none; justify-content:center; margin-top:6px; pointer-events:auto; }
      .caption.tutor .tutor-tools { display:flex; }
      .tutor-repeat { border:1px solid currentColor; border-radius:999px; padding:6px 11px; background:transparent; color:inherit;
        font:600 12px Inter,ui-sans-serif,system-ui,sans-serif; cursor:pointer; opacity:.9; }
      .tutor-repeat:hover { opacity:1; }
      .brand { margin-top: 7px; color: #6fe0bd; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em; }
      .caption.theme-class .brand { color:#1769e0; }
    </style>
    <div class="box"><div class="caption" role="status" aria-live="polite">
      <div class="speaker"></div><div class="original"></div><div class="translated"></div>
      <div class="tutor-tools"><button class="tutor-repeat" type="button">🔊 Repetir original</button></div>
      <div class="brand">MilyVoiceTraductor · local</div>
    </div></div>`;

  const caption = root.querySelector('.caption');
  const speaker = root.querySelector('.speaker');
  const original = root.querySelector('.original');
  const translated = root.querySelector('.translated');
  const tutorRepeat = root.querySelector('.tutor-repeat');
  let hideTimer = null;
  let karaokeFrame = 0;
  let currentWords = [];
  let currentMode = 'meeting';
  let currentPressure = 'healthy';
  let sessionStartedAt = Date.now();
  let currentSpeakerId = null;
  let currentOriginalText = '';
  let currentLanguage = 'en';
  let settings = { showOriginal: true, subtitleTheme: 'auto', tutorVoiceName: '', sessionMode: 'meeting' };

  function speakerLabel(id) {
    if (!/^speaker-[a-z]$/.test(String(id || ''))) return '';
    return `Hablante ${id.slice(-1).toUpperCase()}`;
  }

  function speakerClass(id) {
    if (!/^speaker-[a-z]$/.test(String(id || ''))) return '';
    return `s${(id.charCodeAt(id.length - 1) - 97) % 6}`;
  }

  function renderSpeaker() {
    const label = speakerLabel(currentSpeakerId);
    speaker.textContent = label;
    speaker.className = `speaker ${label ? 'visible' : ''} ${speakerClass(currentSpeakerId)}`;
  }

  function renderOriginalText(text) {
    original.replaceChildren();
    original.textContent = text || '';
  }

  function resolvedTheme() {
    if (settings.subtitleTheme && settings.subtitleTheme !== 'auto') return settings.subtitleTheme;
    if (currentMode === 'karaoke') return 'neon';
    if (currentMode === 'education' || currentMode === 'tutor') return 'class';
    if (currentMode === 'compact') return 'cinema';
    return 'mily';
  }

  function applyClasses() {
    caption.classList.remove(
      'meeting', 'education', 'karaoke', 'compact', 'tutor',
      'theme-mily', 'theme-cinema', 'theme-class', 'theme-contrast', 'theme-neon'
    );
    caption.classList.add(currentMode, `theme-${resolvedTheme()}`);
  }

  function renderKaraokeWords() {
    if (currentMode !== 'karaoke' || currentPressure !== 'healthy' || !currentWords.length) return;
    const seconds = Math.max(0, (Date.now() - sessionStartedAt) / 1000);
    original.replaceChildren();
    for (const word of currentWords) {
      const span = document.createElement('span');
      span.className = 'karaoke-word';
      if (seconds >= Number(word.start || 0) && seconds < Number(word.end || 0)) span.classList.add('active');
      span.textContent = `${word.text || ''} `;
      original.appendChild(span);
    }
  }

  function stopKaraokeLoop() {
    if (karaokeFrame) cancelAnimationFrame(karaokeFrame);
    karaokeFrame = 0;
  }

  function karaokeTick() {
    if (currentMode !== 'karaoke' || currentPressure !== 'healthy' || !caption.classList.contains('visible')) {
      stopKaraokeLoop();
      return;
    }
    renderKaraokeWords();
    karaokeFrame = requestAnimationFrame(karaokeTick);
  }

  function startKaraokeLoop() {
    if (karaokeFrame || currentMode !== 'karaoke' || currentPressure !== 'healthy' || !currentWords.length) return;
    karaokeFrame = requestAnimationFrame(karaokeTick);
  }

  function scheduleHide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      caption.classList.remove('visible');
      stopKaraokeLoop();
    }, currentMode === 'tutor' ? 15000 : 9000);
  }

  async function showSubtitle(payload, context = {}) {
    currentMode = settings.sessionMode === 'tutor' ? 'tutor' : (context.sessionMode || currentMode || 'meeting');
    sessionStartedAt = Number(context.sessionStartedAt || sessionStartedAt || Date.now());
    applyClasses();
    if (payload.type === 'pipeline.metrics') {
      currentPressure = payload.pressure || 'healthy';
      if (currentPressure !== 'healthy') {
        stopKaraokeLoop();
        renderOriginalText(payload.original || original.textContent || '');
      } else startKaraokeLoop();
      return;
    }
    if (payload.type === 'speaker.changed') {
      currentSpeakerId = payload.speakerId || currentSpeakerId;
      renderSpeaker();
      return;
    }
    if (payload.speakerId) currentSpeakerId = payload.speakerId;
    if (payload.words?.length) currentWords = payload.words;
    renderSpeaker();

    const originalText = payload.original || '';
    const translatedText = payload.translation || '';
    if (originalText) currentOriginalText = originalText;
    if (payload.language) currentLanguage = payload.language;
    if (settings.showOriginal) {
      if (currentMode === 'karaoke' && currentPressure === 'healthy' && currentWords.length) renderKaraokeWords();
      else renderOriginalText(originalText);
    } else {
      renderOriginalText('');
    }
    original.style.display = settings.showOriginal && (originalText || currentWords.length) ? 'block' : 'none';
    if (translatedText) translated.textContent = translatedText;
    translated.style.display = translated.textContent ? 'block' : 'none';
    caption.classList.toggle('visible', Boolean(originalText || translatedText || translated.textContent));
    if (currentMode === 'karaoke') startKaraokeLoop();
    else stopKaraokeLoop();
    scheduleHide();
  }

  tutorRepeat.addEventListener('click', () => {
    if (!currentOriginalText || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(currentOriginalText);
    utterance.lang = String(currentLanguage || '').startsWith('zh') ? 'zh-CN' : String(currentLanguage || '').startsWith('es') ? 'es-ES' : 'en-US';
    utterance.rate = 0.92;
    if (settings.tutorVoiceName) {
      const voice = window.speechSynthesis.getVoices().find((item) => item.name === settings.tutorVoiceName);
      if (voice) utterance.voice = voice;
    }
    window.speechSynthesis.speak(utterance);
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === 'MILYVOICE_SUBTITLE') {
      showSubtitle(message.payload || {}, {
        sessionMode: message.sessionMode,
        sessionStartedAt: message.sessionStartedAt
      });
    }
  });

  chrome.storage.local.get(['showOriginal', 'subtitleTheme', 'tutorVoiceName', 'sessionMode']).then((saved) => {
    settings = {
      showOriginal: saved.showOriginal !== false,
      subtitleTheme: saved.subtitleTheme || 'auto',
      tutorVoiceName: saved.tutorVoiceName || '',
      sessionMode: saved.sessionMode || 'meeting'
    };
    applyClasses();
  }).catch(() => undefined);

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== 'local') return;
    if (changes.showOriginal) settings.showOriginal = changes.showOriginal.newValue !== false;
    if (changes.subtitleTheme) settings.subtitleTheme = changes.subtitleTheme.newValue || 'auto';
    if (changes.tutorVoiceName) settings.tutorVoiceName = changes.tutorVoiceName.newValue || '';
    if (changes.sessionMode) settings.sessionMode = changes.sessionMode.newValue || 'meeting';
    applyClasses();
  });

  window.addEventListener('pagehide', () => stopKaraokeLoop(), { once: true });
})();
