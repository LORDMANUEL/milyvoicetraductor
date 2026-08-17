import { describe, expect, it } from 'vitest';
import { DesktopApi } from './api';

describe('browser development fallback', () => {
  it('returns honest not-installed states outside Tauri', async () => {
    const status = await new DesktopApi().getAppStatus();
    expect(status.engine).toBe('notInstalled');
    expect(status.models).toBe('notInstalled');
    expect(status.extensionConnected).toBe(false);
  });
});
