import type { OnboardingStatus } from '../types';

export type OnboardingStep = 'runtime' | 'model' | 'ready';

/**
 * El onboarding solo bloquea cuando falta el runtime o el modelo. La extensión
 * puede instalarse/abrirse después: al aparecer se autoreconoce vía Native Messaging.
 */
export function needsOnboarding(status: OnboardingStatus): boolean {
  return !status.runtimeReady || status.bootstrapState === 'failed' || status.modelState !== 'ready';
}

export function onboardingStep(status: OnboardingStatus): OnboardingStep {
  if (!status.runtimeReady || status.bootstrapState === 'failed') return 'runtime';
  if (status.modelState !== 'ready') return 'model';
  return 'ready';
}

export function bytesLabel(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}
