import test from 'node:test';
import assert from 'node:assert/strict';
import { TtsQueueController } from './controller.js';

function job(id, createdAt = 0, lifecycle = {}) {
  return {
    requestId: `req-${id}`,
    utteranceId: `utt-${id}`,
    text: `texto ${id}`,
    speakerId: 'speaker-a',
    targetLanguage: 'es-ES',
    voiceName: '',
    duckingEnabled: true,
    duckingLevel: 0.25,
    createdAt,
    lifecycle
  };
}

test('constructor rejects invalid bounds', () => {
  assert.throws(() => new TtsQueueController({ maxPending: 0 }), /maxPending/);
  assert.throws(() => new TtsQueueController({ maxAgeMs: 0 }), /maxAgeMs/);
});

test('queue keeps one active plus at most three pending and drops oldest pending', () => {
  let now = 1000;
  const drops = [];
  const queue = new TtsQueueController({ maxPending: 3, maxAgeMs: 4000, now: () => now });

  queue.enqueue(job('a', now));
  assert.equal(queue.takeNext().utteranceId, 'utt-a');

  queue.enqueue(job('b', now, { onDrop: (event) => drops.push(event) }));
  queue.enqueue(job('c', now));
  queue.enqueue(job('d', now));
  queue.enqueue(job('e', now));

  const snapshot = queue.snapshot();
  assert.equal(snapshot.active, true);
  assert.equal(snapshot.pendingCount, 3);
  assert.equal(snapshot.droppedCount, 1);
  assert.equal(snapshot.health, 'degraded');
  assert.equal(drops.length, 1);
  assert.equal(drops[0].utteranceId, 'utt-b');
  assert.equal(drops[0].reason, 'QUEUE_OVERFLOW');

  queue.finish('END');
  assert.equal(queue.takeNext().utteranceId, 'utt-c');
});

test('stale pending utterances are skipped instead of spoken late', () => {
  let now = 0;
  const drops = [];
  const queue = new TtsQueueController({ maxPending: 3, maxAgeMs: 4000, now: () => now });
  queue.enqueue(job('old', 0, { onDrop: (event) => drops.push(event) }));
  now = 5001;

  assert.equal(queue.takeNext(), null);
  assert.equal(drops.length, 1);
  assert.equal(drops[0].reason, 'STALE');
  assert.equal(queue.snapshot().pendingCount, 0);
  assert.equal(queue.snapshot().droppedCount, 1);
});

test('finish releases active utterance and successful completion restores healthy state', () => {
  let now = 100;
  const queue = new TtsQueueController({ now: () => now });
  queue.enqueue(job('a', now));
  queue.enqueue(job('b', now));
  assert.equal(queue.takeNext().utteranceId, 'utt-a');
  queue.markDegraded('RUNTIME_ERROR');
  assert.equal(queue.snapshot().health, 'degraded');

  const finished = queue.finish('END');
  assert.equal(finished.utteranceId, 'utt-a');
  assert.equal(queue.snapshot().health, 'healthy');
  assert.equal(queue.snapshot().lastErrorReason, 'NONE');
  assert.equal(queue.takeNext().utteranceId, 'utt-b');
});

test('reset clears active and pending state without unbounding memory', () => {
  const queue = new TtsQueueController({ now: () => 1 });
  queue.enqueue(job('a', 1));
  queue.enqueue(job('b', 1));
  queue.takeNext();
  const cleared = queue.reset('CANCELLED');

  assert.equal(cleared.active.utteranceId, 'utt-a');
  assert.deepEqual(cleared.pending.map((item) => item.utteranceId), ['utt-b']);
  assert.deepEqual(queue.snapshot(), {
    active: false,
    pendingCount: 0,
    droppedCount: 0,
    health: 'healthy',
    lastErrorReason: 'NONE'
  });
});
