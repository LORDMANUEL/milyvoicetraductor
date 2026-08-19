/** Reduce la copia para ASR a PCM16/16 kHz sin cambiar la reproducción audible. */
const TARGET_SAMPLE_RATE = 16000;
const TARGET_BLOCK_SAMPLES = 1600; // 100 ms a 16 kHz.

class MilyVoicePcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.input = [];
    this.readPosition = 0;
    this.pendingPcm = [];
    this.resampleRatio = sampleRate / TARGET_SAMPLE_RATE;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let index = 0; index < channel.length; index += 1) {
      this.input.push(Number(channel[index]));
    }

    // Interpolación lineal streaming: AudioContext conserva su frecuencia nativa
    // (normalmente 48 kHz en Teams) y solo esta copia se lleva a 16 kHz para ASR.
    while (this.readPosition + 1 < this.input.length) {
      const leftIndex = Math.floor(this.readPosition);
      const fraction = this.readPosition - leftIndex;
      const left = this.input[leftIndex];
      const right = this.input[leftIndex + 1];
      const resampled = left + (right - left) * fraction;
      const value = Math.max(-1, Math.min(1, resampled));
      this.pendingPcm.push(value < 0 ? value * 32768 : value * 32767);
      this.readPosition += this.resampleRatio;
    }

    // splice elimina como máximo input.length; restar exactamente esa misma
    // cantidad conserva la fase entre quantums de 128 frames del AudioWorklet.
    const consumed = Math.min(Math.floor(this.readPosition), this.input.length);
    if (consumed > 0) {
      this.input.splice(0, consumed);
      this.readPosition -= consumed;
    }

    while (this.pendingPcm.length >= TARGET_BLOCK_SAMPLES) {
      const samples = this.pendingPcm.splice(0, TARGET_BLOCK_SAMPLES);
      const pcm = new Int16Array(samples.length);
      for (let index = 0; index < samples.length; index += 1) pcm[index] = samples[index];
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('milyvoice-pcm', MilyVoicePcmProcessor);
