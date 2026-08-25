import test from 'node:test';
import assert from 'node:assert/strict';
import { speakTranslation, stopSpeech, ttsSnapshot } from '../tts.js';

function installChrome(settings = {}) {
  const calls = [];
  let stopCount = 0;
  globalThis.chrome = {
    storage: {
      local: {
        async get() {
          return { outputMode: 'subtitles-voice', duckingEnabled: true, duckingLevel: 0.25, ...settings };
        }
      }
    },
    tts: {
      speak(text, options, callback) {
        calls.push({ text, options });
        callback?.();
      },
      stop() { stopCount += 1; }
    },
    runtime: { lastError: null }
  };
  return { calls, get stopCount() { return stopCount; } };
}

async function reset() {
  try { await stopSpeech('CANCELLED'); } catch (_) {}
}

test('subtitles-only mode never calls native TTS', async () => {
  const mock = installChrome({ outputMode: 'subtitles' });
  await reset();
  const spoken = await speakTranslation({ translation: 'Hola', targetLanguage: 'es' });
  assert.equal(spoken, false);
  assert.equal(mock.calls.length, 0);
});

test('speaker voice wins over global voice and Chromium queue is disabled', async () => {
  const mock = installChrome({
    ttsVoiceName: 'Global Voice',
    speakerVoiceNames: { 'speaker-a': 'Speaker A Voice' }
  });
  await reset();
  const started = [];
  const spoken = await speakTranslation(
    { translation: 'Hola', targetLanguage: 'es', speakerId: 'speaker-a' },
    { onStart: (event) => started.push(event) }
  );
  assert.equal(spoken, true);
  assert.equal(mock.calls.length, 1);
  assert.equal(mock.calls[0].options.voiceName, 'Speaker A Voice');
  assert.equal(mock.calls[0].options.lang, 'es-ES');
  assert.equal(mock.calls[0].options.enqueue, false);
  mock.calls[0].options.onEvent({ type: 'start' });
  assert.equal(started.length, 1);
  await reset();
});

test('global voice is used when speaker has no explicit mapping', async () => {
  const mock = installChrome({ ttsVoiceName: 'Global Voice', speakerVoiceNames: {} });
  await reset();
  await speakTranslation({ translation: 'Hello', targetLanguage: 'en', speakerId: 'speaker-b' });
  assert.equal(mock.calls[0].options.voiceName, 'Global Voice');
  assert.equal(mock.calls[0].options.lang, 'en-US');
  await reset();
});

test('module owns a bounded queue instead of enqueueing unbounded Chromium speech', async () => {
  const mock = installChrome();
  await reset();
  const drops = [];
  for (const id of ['a', 'b', 'c', 'd', 'e']) {
    await speakTranslation(
      { translation: `texto ${id}`, targetLanguage: 'es', utteranceId: id },
      { onDrop: (event) => drops.push(event) }
    );
  }

  assert.equal(mock.calls.length, 1, 'only the active utterance may reach chrome.tts');
  assert.equal(ttsSnapshot().pendingCount, 3);
  assert.equal(drops.length, 1);
  assert.equal(drops[0].reason, 'QUEUE_OVERFLOW');

  mock.calls[0].options.onEvent({ type: 'end' });
  assert.equal(mock.calls.length, 2);
  assert.equal(mock.calls[1].text, 'texto c', 'oldest pending b must have been dropped');
  await reset();
});

test('runtime errors degrade TTS but invoke subtitle fallback hook and continue queue', async () => {
  const mock = installChrome();
  await reset();
  const fallback = [];
  globalThis.chrome.tts.speak = (text, options, callback) => {
    mock.calls.push({ text, options });
    globalThis.chrome.runtime.lastError = { message: 'voice missing' };
    callback?.();
    globalThis.chrome.runtime.lastError = null;
  };

  await speakTranslation(
    { translation: 'Hola', targetLanguage: 'es' },
    { onFallback: (event) => fallback.push(event) }
  );
  assert.equal(fallback.length, 1);
  assert.equal(fallback[0].reason, 'RUNTIME_ERROR');
  assert.equal(ttsSnapshot().health, 'degraded');
  await reset();
});

test('stopSpeech clears active and pending speech without requiring capture shutdown', async () => {
  const mock = installChrome();
  await reset();
  await speakTranslation({ translation: 'uno' });
  await speakTranslation({ translation: 'dos' });
  assert.equal(ttsSnapshot().active, true);
  assert.equal(ttsSnapshot().pendingCount, 1);

  await stopSpeech('CANCELLED');
  assert.ok(mock.stopCount >= 1);
  assert.equal(ttsSnapshot().active, false);
  assert.equal(ttsSnapshot().pendingCount, 0);
});
