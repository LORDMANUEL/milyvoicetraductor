/** Overlay aislado con Shadow DOM para no depender de la estructura interna del sitio. */
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
    .caption.visible { display: block; }
    .original { color: #9fb8dc; font-size: 14px; margin-bottom: 5px; }
    .translated { font-size: clamp(20px,2.4vw,30px); line-height: 1.25; font-weight: 700; letter-spacing: -.01em; }
    .brand { margin-top: 7px; color: #6fe0bd; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em; }
  </style>
  <div class="box"><div class="caption" role="status" aria-live="polite">
    <div class="original"></div><div class="translated"></div><div class="brand">MilyVoiceTraductor · local</div>
  </div></div>`;

const caption = root.querySelector('.caption');
const original = root.querySelector('.original');
const translated = root.querySelector('.translated');
let hideTimer = null;

async function showSubtitle(payload) {
  const { showOriginal = true } = await chrome.storage.local.get('showOriginal');
  original.textContent = showOriginal ? (payload.original || '') : '';
  original.style.display = showOriginal && payload.original ? 'block' : 'none';
  translated.textContent = payload.translation || '';
  caption.classList.toggle('visible', Boolean(payload.translation));
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => caption.classList.remove('visible'), 9000);
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === 'MILYVOICE_SUBTITLE') showSubtitle(message.payload || {});
});
