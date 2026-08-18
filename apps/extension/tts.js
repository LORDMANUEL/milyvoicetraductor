/** Síntesis española opcional usando únicamente voces expuestas por Chrome/Windows. */
export async function speakTranslation(payload) {
  const text = String(payload?.translation || '').trim();
  if (!text) return;
  const settings = await chrome.storage.local.get(['ttsEnabled', 'ttsVoiceName']);
  if (!settings.ttsEnabled) return;

  const options = {
    lang: 'es-ES',
    rate: 1.08,
    pitch: 1.0,
    volume: 1.0,
    enqueue: false
  };
  if (settings.ttsVoiceName) options.voiceName = settings.ttsVoiceName;
  chrome.tts.stop();
  chrome.tts.speak(text, options, () => {
    // Leer lastError evita warnings no atendidos si una voz desaparece del SO.
    void chrome.runtime.lastError;
  });
}
