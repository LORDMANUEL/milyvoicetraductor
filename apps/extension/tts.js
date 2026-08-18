/** Síntesis española opcional usando únicamente voces expuestas por Chrome/Windows. */
export async function speakTranslation(payload, lifecycle = {}) {
  const text = String(payload?.translation || '').trim();
  if (!text) return false;
  const settings = await chrome.storage.local.get([
    'outputMode', 'ttsEnabled', 'ttsVoiceName', 'speakerVoiceNames',
    'duckingEnabled', 'duckingLevel'
  ]);
  const outputMode = settings.outputMode || (settings.ttsEnabled ? 'subtitles-voice' : 'subtitles');
  if (outputMode === 'subtitles') return false;

  const speakerId = /^speaker-[a-z]$/.test(String(payload?.speakerId || '')) ? String(payload.speakerId) : null;
  const speakerVoice = speakerId && settings.speakerVoiceNames && typeof settings.speakerVoiceNames === 'object'
    ? settings.speakerVoiceNames[speakerId]
    : '';
  const voiceName = speakerVoice || settings.ttsVoiceName || '';
  const duckingEnabled = settings.duckingEnabled !== false;
  const duckingLevel = Math.min(1, Math.max(0.05, Number(settings.duckingLevel ?? 0.25)));
  let started = false;
  let finished = false;

  const finish = (reason) => {
    if (finished) return;
    finished = true;
    lifecycle.onEnd?.({ speakerId, reason, duckingEnabled, duckingLevel });
  };

  const options = {
    lang: 'es-ES',
    rate: 1.08,
    pitch: 1.0,
    volume: 1.0,
    enqueue: true,
    onEvent(event) {
      if (event.type === 'start' && !started) {
        started = true;
        lifecycle.onStart?.({ text, speakerId, duckingEnabled, duckingLevel });
      }
      if (['end', 'error', 'cancelled', 'interrupted'].includes(event.type)) finish(event.type);
    }
  };
  if (voiceName) options.voiceName = voiceName;

  chrome.tts.speak(text, options, () => {
    if (chrome.runtime.lastError) finish('runtime-error');
  });
  return true;
}
