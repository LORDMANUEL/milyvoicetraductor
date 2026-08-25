import { TtsQueueController } from './tts/controller.js';

/**
 * Adapter local de síntesis: usa únicamente voces expuestas por Chrome/Edge/Windows.
 * MilyVoice controla su propia cola para que la voz nunca acumule retraso ilimitado.
 */
const queue = new TtsQueueController({ maxPending: 3, maxAgeMs: 4000 });
let nativeActive = false;
let sequence = 0;

function validSpeakerId(value) {
  const normalized = String(value || '');
  return /^speaker-[a-z]$/.test(normalized) ? normalized : null;
}

function clampDucking(value) {
  return Math.min(1, Math.max(0.05, Number(value ?? 0.25) || 0.25));
}

function targetLanguage(value) {
  const raw = String(value || 'es').trim();
  const lower = raw.toLowerCase();
  if (!raw || lower === 'es') return 'es-ES';
  if (lower === 'en') return 'en-US';
  if (lower === 'zh' || lower === 'zh-cn' || lower === 'zh-hans') return 'zh-CN';
  if (/^[a-z]{2,3}(?:-[a-z0-9]{2,8})+$/i.test(raw)) return raw;
  return 'es-ES';
}

function reasonForEvent(type) {
  if (type === 'end') return 'END';
  if (type === 'cancelled') return 'CANCELLED';
  if (type === 'interrupted') return 'INTERRUPTED';
  return 'RUNTIME_ERROR';
}

function safeLifecycle(callback, payload) {
  try { callback?.(payload); } catch (_) {}
}

function pumpQueue() {
  if (nativeActive) return;
  const job = queue.takeNext();
  if (!job) return;

  nativeActive = true;
  let started = false;
  let terminal = false;

  const finish = (reason) => {
    if (terminal) return;
    terminal = true;
    nativeActive = false;
    const finished = queue.finish(reason);
    if (finished !== job) return;

    const event = {
      requestId: job.requestId,
      utteranceId: job.utteranceId,
      speakerId: job.speakerId,
      reason,
      duckingEnabled: job.duckingEnabled,
      duckingLevel: job.duckingLevel
    };
    safeLifecycle(job.lifecycle?.onEnd, event);
    if (reason !== 'END') safeLifecycle(job.lifecycle?.onFallback, event);
    pumpQueue();
  };

  const options = {
    lang: job.targetLanguage,
    rate: 1.08,
    pitch: 1.0,
    volume: 1.0,
    enqueue: false,
    onEvent(event) {
      if (event.type === 'start' && !started) {
        started = true;
        safeLifecycle(job.lifecycle?.onStart, {
          requestId: job.requestId,
          utteranceId: job.utteranceId,
          text: job.text,
          speakerId: job.speakerId,
          duckingEnabled: job.duckingEnabled,
          duckingLevel: job.duckingLevel
        });
        return;
      }
      if (['end', 'error', 'cancelled', 'interrupted'].includes(event.type)) {
        finish(reasonForEvent(event.type));
      }
    }
  };
  if (job.voiceName) options.voiceName = job.voiceName;

  try {
    chrome.tts.speak(job.text, options, () => {
      if (chrome.runtime?.lastError) finish('RUNTIME_ERROR');
    });
  } catch (_) {
    finish('RUNTIME_ERROR');
  }
}

export async function speakTranslation(payload, lifecycle = {}) {
  const text = String(payload?.translation || '').trim();
  if (!text) {
    safeLifecycle(lifecycle.onFallback, { reason: 'EMPTY' });
    return false;
  }

  const settings = await chrome.storage.local.get([
    'outputMode', 'ttsEnabled', 'ttsVoiceName', 'speakerVoiceNames',
    'duckingEnabled', 'duckingLevel'
  ]);
  const outputMode = settings.outputMode || (settings.ttsEnabled ? 'subtitles-voice' : 'subtitles');
  if (outputMode === 'subtitles') {
    safeLifecycle(lifecycle.onFallback, { reason: 'DISABLED' });
    return false;
  }

  const speakerId = validSpeakerId(payload?.speakerId);
  const speakerVoice = speakerId && settings.speakerVoiceNames && typeof settings.speakerVoiceNames === 'object'
    ? String(settings.speakerVoiceNames[speakerId] || '')
    : '';
  const voiceName = speakerVoice || String(settings.ttsVoiceName || '');
  const duckingEnabled = settings.duckingEnabled !== false;
  const duckingLevel = clampDucking(settings.duckingLevel);
  const requestId = String(payload?.requestId || `tts-${Date.now()}-${++sequence}`);
  const utteranceId = String(payload?.utteranceId || requestId);

  queue.enqueue({
    requestId,
    utteranceId,
    text,
    speakerId,
    targetLanguage: targetLanguage(payload?.targetLanguage),
    voiceName,
    duckingEnabled,
    duckingLevel,
    createdAt: Date.now(),
    lifecycle
  });
  pumpQueue();
  return true;
}

export async function stopSpeech(reason = 'CANCELLED') {
  const cleared = queue.reset(reason);
  nativeActive = false;
  try { chrome?.tts?.stop?.(); } catch (_) {}

  if (cleared.active) {
    const event = {
      requestId: cleared.active.requestId,
      utteranceId: cleared.active.utteranceId,
      speakerId: cleared.active.speakerId,
      reason
    };
    safeLifecycle(cleared.active.lifecycle?.onEnd, event);
    safeLifecycle(cleared.active.lifecycle?.onFallback, event);
  }
  for (const pending of cleared.pending) {
    safeLifecycle(pending.lifecycle?.onDrop, {
      requestId: pending.requestId,
      utteranceId: pending.utteranceId,
      speakerId: pending.speakerId,
      reason
    });
  }
  return queue.snapshot();
}

export function ttsSnapshot() {
  return queue.snapshot();
}
