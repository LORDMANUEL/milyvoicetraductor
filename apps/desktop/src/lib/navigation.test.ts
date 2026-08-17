import { describe, expect, it } from 'vitest';
import { navigationItems } from './navigation';

 describe('navigationItems', () => {
  it('contains every Phase 1 view exactly once', () => {
    const ids = navigationItems.map((item) => item.id);
    expect(ids).toEqual([
      'panel', 'live', 'sessions', 'models', 'permissions', 'devices', 'settings', 'help', 'about'
    ]);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
