/** Síntesis española opcional usando únicamente voces expuestas por Chrome/Windows. */
export async function speakTranslation(payload, lifecycle = {}) {
  const text = String(payload?.translation || '').trim();
  if (!text) return false;
  const settings = await chrome.storage.local.get(['ttsEnabled', 'ttsVoiceName', 'speakerVoiceNames']);
  if (!settings.ttsEnabled) return false;

  const speakerId = /^speaker-[a-z]$/.test(String(payload?.speakerId || '')) ? String(payload.speakerId) : null;
  const speakerVoice = speakerId && settings.speakerVoiceNames && typeof settings.speakerVoiceNames === 'object'
    ? settings.speakerVoiceNames[speakerId]
    : '';
  const voiceName = speakerVoice || settings.ttsVoiceName || '';
  let finished = false;
  const finish = (reason) => {
    if (finished) return;
    finished = true;
    lifecycle.onEnd?.({ speakerId, reason });
  };

  const options = {
    lang: 'es-ES',
    rate: 1.08,
    pitch: 1.0,
    volume: 1.0,
    enqueue: false,
    onEvent(event) {
      if (['end', 'error', 'cancelled', 'interrupted'].includes(event.type)) finish(event.type);
    }
  };
  if (voiceName) options.voiceName = voiceName;

  chrome.tts.stop();
  lifecycle.onStart?.({ text, speakerId });
  chrome.tts.speak(text, options, () => {
    if (chrome.runtime.lastError) finish('runtime-error');
  });
  return true;
}
