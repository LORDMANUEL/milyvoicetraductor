import type { RealtimeSourceLanguage, RealtimeTargetLanguage } from './realtime';

let targetLanguage: RealtimeTargetLanguage = 'es';

const LOCALES: Record<RealtimeTargetLanguage, string> = {
  es: 'es-ES',
  en: 'en-US',
  zh: 'zh-CN'
};

export function setTier1TargetLanguage(value: RealtimeTargetLanguage): void {
  targetLanguage = value;
}

export function getTier1TargetLanguage(): RealtimeTargetLanguage {
  return targetLanguage;
}

export function normalizeTier1SourceLanguage(
  source: RealtimeSourceLanguage,
  target: RealtimeTargetLanguage = targetLanguage
): RealtimeSourceLanguage {
  return target === 'es' ? source : 'es';
}

export function targetLocale(target: RealtimeTargetLanguage = targetLanguage): string {
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
