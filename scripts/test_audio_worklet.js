'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

let Processor = null;
globalThis.AudioWorkletProcessor = class {
  constructor() {
    this.port = { postMessage() {} };
  }
};
globalThis.registerProcessor = (name, implementation) => {
  assert.equal(name, 'milyvoice-pcm');
  Processor = implementation;
};
globalThis.sampleRate = 48000;
require(path.join(__dirname, '..', 'apps', 'extension', 'audio-worklet.js'));
assert.ok(Processor, 'audio-worklet.js debe registrar milyvoice-pcm');

function verifyRate(sourceRate, blockCount = 2000, blockSize = 128) {
  globalThis.sampleRate = sourceRate;
  const processor = new Processor();
  let postedSamples = 0;
  processor.port = {
    postMessage(buffer) {
      assert.ok(buffer instanceof ArrayBuffer);
      postedSamples += buffer.byteLength / Int16Array.BYTES_PER_ELEMENT;
    },
  };

  for (let block = 0; block < blockCount; block += 1) {
    assert.equal(processor.process([[new Float32Array(blockSize)]]), true);
  }

  const inputSamples = blockCount * blockSize;
  const expectedSamples = Math.ceil((inputSamples - 1) / (sourceRate / 16000));
  const producedSamples = postedSamples + processor.pendingPcm.length;
  assert.ok(
    Math.abs(producedSamples - expectedSamples) <= 1,
    `${sourceRate} Hz perdió continuidad: produjo ${producedSamples}, esperaba ${expectedSamples}`,
  );
  assert.ok(
    processor.input.length <= 1,
    `${sourceRate} Hz acumuló ${processor.input.length} muestras fuente sin consumir`,
  );
}

for (const sourceRate of [44100, 48000, 96000]) verifyRate(sourceRate);
console.log('AudioWorklet resampling continuity: OK');
