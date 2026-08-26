export type Tier1SourceLanguage = 'auto' | 'en' | 'es' | 'zh';
export type Tier1TargetLanguage = 'es' | 'en' | 'zh';

let targetLanguage: Tier1TargetLanguage = 'es';

const LOCALES: Record<Tier1TargetLanguage, string> = {
  es: 'es-ES',
  en: 'en-US',
  zh: 'zh-CN'
};

export function setTier1TargetLanguage(value: Tier1TargetLanguage): void {
  targetLanguage = value;
}

export function getTier1TargetLanguage(): Tier1TargetLanguage {
  return targetLanguage;
}

export function normalizeTier1SourceLanguage(
  source: Tier1SourceLanguage,
  target: Tier1TargetLanguage = targetLanguage
): Tier1SourceLanguage {
  return target === 'es' ? source : 'es';
}

export function targetLocale(target: Tier1TargetLanguage = targetLanguage): string {
  return LOCALES[target];
}

export function installTargetAwareSpeechSynthesis(): () => void {
  if (!('speechSynthesis' in window)) return () => undefined;
  const synth = window.speechSynthesis;
  const originalSpeak = synth.speak.bind(synth);
  const patchedSpeak = (utterance: SpeechSynthesisUtterance) => {
    const target = getTier1TargetLanguage();
    const locale = targetLocale(target);
    utterance.lang = locale;
    if (target !== 'es') {
      const prefix = target.toLowerCase();
      const voices = synth.getVoices();
      const localMatch = voices.find(
        (voice) => voice.lang.toLowerCase().startsWith(prefix) && voice.localService !== false
      );
      const anyMatch = voices.find((voice) => voice.lang.toLowerCase().startsWith(prefix));
      const selected = localMatch || anyMatch;
      if (selected) utterance.voice = selected;
    }
    originalSpeak(utterance);
  };
  synth.speak = patchedSpeak;
  return () => {
    synth.speak = originalSpeak;
  };
}
