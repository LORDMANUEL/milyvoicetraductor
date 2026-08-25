import test from 'node:test';
import assert from 'node:assert/strict';
import { clampDuckingLevel, setDuckingGain, restoreGain } from './ducking.js';

test('ducking level is clamped to a safe audible range', () => {
  assert.equal(clampDuckingLevel(0), 0.05);
  assert.equal(clampDuckingLevel(-1), 0.05);
  assert.equal(clampDuckingLevel(2), 1);
  assert.equal(clampDuckingLevel(0.3), 0.3);
  assert.equal(clampDuckingLevel('bad'), 0.25);
});

test('enabled ducking reduces playback gain without muting capture', () => {
  const gain = { value: 1 };
  const applied = setDuckingGain(gain, true, 0.2);
  assert.equal(applied, 0.2);
  assert.equal(gain.value, 0.2);
});

test('disabled ducking and restore always return playback to unity', () => {
  const gain = { value: 0.2 };
  assert.equal(setDuckingGain(gain, false, 0.1), 1);
  assert.equal(gain.value, 1);
  gain.value = 0.15;
  assert.equal(restoreGain(gain), 1);
  assert.equal(gain.value, 1);
});

test('missing gain node is a harmless no-op', () => {
  assert.equal(setDuckingGain(null, true, 0.2), null);
  assert.equal(restoreGain(null), null);
});
