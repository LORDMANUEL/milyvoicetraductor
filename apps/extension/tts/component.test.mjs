import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function jsonAt(relative) {
  return JSON.parse(await readFile(new URL(relative, import.meta.url), 'utf8'));
}

test('TTS component metadata is promoted to 1.0.0 candidate', async () => {
  const component = await jsonAt('./COMPONENT.json');
  assert.equal(component.id, 'tts');
  assert.equal(component.version, '1.0.0');
  assert.equal(component.contract, 'tts/v1');
  assert.equal(component.stage, 'candidate');
});

test('alpha.4 dev.4 composition pins optional TTS without removing prior modules', async () => {
  const manifest = await jsonAt('../../../manifests/milyvoice-3.components.json');
  assert.equal(manifest.product.name, 'MilyVoiceTraductor');
  assert.equal(manifest.product.version, '3.0.0-alpha.4-dev.4');

  const expected = ['supervisor', 'compute', 'audio', 'realtime', 'engine-host', 'asr', 'linguistic', 'mt', 'tts'];
  assert.deepEqual(manifest.components.map((item) => item.id), expected);

  const tts = manifest.components.find((item) => item.id === 'tts');
  assert.deepEqual(tts, {
    id: 'tts',
    version: '1.0.0',
    contract: 'tts/v1',
    stage: 'candidate',
    required: false
  });
});
