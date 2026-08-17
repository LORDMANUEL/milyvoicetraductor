import { describe, expect, it } from 'vitest';
import { componentStateLabel, formatBytes } from './status';

describe('truthful component labels', () => {
  it('does not present a missing component as ready', () => {
    expect(componentStateLabel('notInstalled')).toBe('No instalado');
  });

  it('formats cache usage for humans', () => {
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB');
  });
});
