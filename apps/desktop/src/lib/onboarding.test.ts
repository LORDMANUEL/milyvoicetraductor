import { describe, expect, it } from 'vitest';
import { needsOnboarding, onboardingStep } from './onboarding';
import type { OnboardingStatus } from '../types';

function state(overrides: Partial<OnboardingStatus> = {}): OnboardingStatus {
  return {
    runtimeReady: true,
    bridgeReady: true,
    extensionDetected: true,
    modelState: 'ready',
    downloadedBytes: 0,
    totalBytes: null,
    modelPhase: 'ready',
    modelMessage: 'Modelo de tiempo real listo.',
    bootstrapState: 'ready',
    errorCode: null,
    errorMessage: null,
    ...overrides
  };
}

describe('automatic onboarding', () => {
  it('opens the application when runtime is ready even if no model is installed', () => {
    const modelPending = state({ modelState: 'notInstalled', modelPhase: 'idle' });
    expect(needsOnboarding(modelPending)).toBe(false);
    expect(onboardingStep(modelPending)).toBe('ready');
  });

  it('stays in recovery when the embedded runtime is broken', () => {
    const broken = state({ runtimeReady: false, bootstrapState: 'failed', errorCode: 'RUNTIME_IMPORT_FAILED' });
    expect(needsOnboarding(broken)).toBe(true);
    expect(onboardingStep(broken)).toBe('runtime');
  });

  it('does not block the application after the runtime is ready', () => {
    expect(needsOnboarding(state({ extensionDetected: false }))).toBe(false);
    expect(onboardingStep(state({ extensionDetected: false }))).toBe('ready');
  });
});
