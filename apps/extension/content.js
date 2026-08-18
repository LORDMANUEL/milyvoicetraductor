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
        width: min(900px, 88vw); pointer-events: none; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
      .caption { display: none; background: rgba(16,36,62,.94); color: #f7f4ea; border: 1px solid rgba(0,168,120,.7);
        box-shadow: 0 14px 50px rgba(0,0,0,.28); border-radius: 18px; padding: 14px 18px; text-align: center; }
      .caption.visible { display: grid; gap: 5px; }
      .speaker { display: none; font-size: 11px; font-weight: 800; letter-spacing: .04em; }
      .speaker.visible { display: block; }
      .speaker.s0 { color:#57b9ff; } .speaker.s1 { color:#65e5ae; } .speaker.s2 { color:#ffac68; }
      .speaker.s3 { color:#bf96ff; } .speaker.s4 { color:#ff83b3; } .speaker.s5 { color:#b7c1ca; }
      .original { color: #9fb8dc; font-size: 14px; margin-bottom: 2px; }
      .translated { font-size: clamp(20px,2.4vw,30px); line-height: 1.25; font-weight: 700; letter-spacing: -.01em; }
      .caption.education .translated, .caption.karaoke .translated { order: 2; }
      .caption.education .original, .caption.karaoke .original { order: 3; }
      .caption .speaker { order: 1; }
      .caption .brand { order: 4; }
      .karaoke-word { border-radius: 4px; padding: 0 1px; transition: color .08s linear, background .08s linear; }
      .karaoke-word.active { color: #10243e; background: #6fe0bd; }
      .caption.karaoke .original { border-bottom: 3px solid #6fe0bd; padding-bottom: 4px; }
      .brand { margin-top: 7px; color: #6fe0bd; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em; }
    </style>
    <div class="box"><div class="caption" role="status" aria-live="polite">
      <div class="speaker"></div><div class="original"></div><div class="translated"></div><div class="brand">MilyVoiceTraductor · local</div>
    </div></div>`;

  const caption = root.querySelector('.caption');
  const speaker = root.querySelector('.speaker');
  const original = root.querySelector('.original');
  const translated = root.querySelector('.translated');
  let hideTimer = null;
  let frame = 0;
  let currentWords = [];
  let currentMode = 'meeting';
  let currentPressure = 'healthy';
  let sessionStartedAt = Date.now();
  let currentSpeakerId = null;

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

  function animate() {
    renderKaraokeWords();
    frame = requestAnimationFrame(animate);
  }

  async function showSubtitle(payload, context = {}) {
    const { showOriginal = true } = await chrome.storage.local.get('showOriginal');
    currentMode = context.sessionMode || currentMode || 'meeting';
    sessionStartedAt = Number(context.sessionStartedAt || sessionStartedAt || Date.now());
    if (payload.type === 'pipeline.metrics') {
      currentPressure = payload.pressure || 'healthy';
      if (currentPressure !== 'healthy') renderOriginalText(payload.original || original.textContent || '');
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

    caption.classList.remove('meeting', 'education', 'karaoke', 'compact');
    caption.classList.add(currentMode);
    const originalText = payload.original || '';
    const translatedText = payload.translation || '';
    if (showOriginal) {
      if (currentMode === 'karaoke' && currentPressure === 'healthy' && currentWords.length) renderKaraokeWords();
      else renderOriginalText(originalText);
    } else {
      renderOriginalText('');
    }
    original.style.display = showOriginal && (originalText || currentWords.length) ? 'block' : 'none';
    if (translatedText) translated.textContent = translatedText;
    translated.style.display = translated.textContent ? 'block' : 'none';
    caption.classList.toggle('visible', Boolean(originalText || translatedText || translated.textContent));
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => caption.classList.remove('visible'), 9000);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === 'MILYVOICE_SUBTITLE') {
      showSubtitle(message.payload || {}, {
        sessionMode: message.sessionMode,
        sessionStartedAt: message.sessionStartedAt
      });
    }
  });

  frame = requestAnimationFrame(animate);
  window.addEventListener('pagehide', () => cancelAnimationFrame(frame), { once: true });
})();
