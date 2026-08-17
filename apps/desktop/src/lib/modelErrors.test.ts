import { describe, expect, it } from 'vitest';
import { modelErrorMessage } from './modelErrors';

describe('model error messages', () => {
  it('distinguishes network from disk and runtime failures', () => {
    expect(modelErrorMessage({ code: 'MODEL_NO_NETWORK', message: 'offline' })).toContain('conexión');
    expect(modelErrorMessage({ code: 'MODEL_NO_SPACE', message: 'disk' })).toContain('espacio');
    expect(modelErrorMessage({ code: 'MODEL_RUNTIME_ERROR', message: 'runtime' })).toContain('motor local');
  });

  it('prefers a safe public message supplied by the backend', () => {
    expect(modelErrorMessage({ code: 'MODEL_PROVIDER_ERROR', message: 'El proveedor está temporalmente ocupado.' }))
      .toBe('El proveedor está temporalmente ocupado.');
  });
});
