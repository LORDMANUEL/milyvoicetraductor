import { describe, expect, it } from 'vitest';
import { shouldUseProtectedSystemAudioFallback } from './audio-source-policy';

describe('system audio fallback policy', () => {
  it('falls back only when native WASAPI cannot be opened', () => {
    expect(shouldUseProtectedSystemAudioFallback('LOOPBACK_UNAVAILABLE')).toBe(true);
    expect(shouldUseProtectedSystemAudioFallback('LOOPBACK_DEVICE')).toBe(true);
    expect(shouldUseProtectedSystemAudioFallback('LOOPBACK_CAPTURE')).toBe(false);
    expect(shouldUseProtectedSystemAudioFallback('PIPELINE_INIT')).toBe(false);
    expect(shouldUseProtectedSystemAudioFallback(undefined)).toBe(false);
  });
});
