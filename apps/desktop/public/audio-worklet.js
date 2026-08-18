/** Convierte audio float32 del WebView a PCM16 en bloques de 100 ms. */
class MilyVoiceDesktopPcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.targetSamples = 1600;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (let index = 0; index < channel.length; index += 1) {
      const value = Math.max(-1, Math.min(1, channel[index]));
      this.pending.push(value < 0 ? value * 32768 : value * 32767);
    }
    while (this.pending.length >= this.targetSamples) {
      const samples = this.pending.splice(0, this.targetSamples);
      const pcm = new Int16Array(samples.length);
      for (let index = 0; index < samples.length; index += 1) pcm[index] = samples[index];
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('milyvoice-desktop-pcm', MilyVoiceDesktopPcmProcessor);
