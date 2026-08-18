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
    bootstrapState: 'ready',
    errorCode: null,
    errorMessage: null,
    ...overrides
  };
}

describe('automatic onboarding', () => {
  it('starts automatically when the model is missing', () => {
    expect(needsOnboarding(state({ modelState: 'notInstalled' }))).toBe(true);
    expect(onboardingStep(state({ modelState: 'notInstalled' }))).toBe('model');
  });

  it('stays in recovery when the embedded runtime is broken', () => {
    const broken = state({ runtimeReady: false, bootstrapState: 'failed', errorCode: 'RUNTIME_IMPORT_FAILED' });
    expect(needsOnboarding(broken)).toBe(true);
    expect(onboardingStep(broken)).toBe('runtime');
  });

  it('does not block translation after runtime and model are ready', () => {
    expect(needsOnboarding(state({ extensionDetected: false }))).toBe(false);
    expect(onboardingStep(state({ extensionDetected: false }))).toBe('ready');
  });
});
