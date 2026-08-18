export function shouldUseProtectedSystemAudioFallback(code?: string): boolean {
  return code === 'LOOPBACK_UNAVAILABLE' || code === 'LOOPBACK_DEVICE';
}
