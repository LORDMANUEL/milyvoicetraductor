import type { OnboardingStatus } from '../types';

export type OnboardingStep = 'runtime' | 'model' | 'ready';

/**
 * El onboarding bloquea únicamente si el runtime privado no está listo o si
 * el bootstrap falló. Los modelos se administran después, dentro de Engine Hub.
 */
export function needsOnboarding(status: OnboardingStatus): boolean {
  return !status.runtimeReady || status.bootstrapState === 'failed';
}

export function onboardingStep(status: OnboardingStatus): OnboardingStep {
  if (!status.runtimeReady || status.bootstrapState === 'failed') return 'runtime';
  return 'ready';
}

export function bytesLabel(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}
