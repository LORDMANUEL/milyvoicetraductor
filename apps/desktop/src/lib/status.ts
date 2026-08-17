import type { ComponentState } from '../types';

/** Traduce estados técnicos a texto honesto para el usuario. */
export function componentStateLabel(state: ComponentState): string {
  switch (state) {
    case 'ready':
      return 'Listo';
    case 'stopped':
      return 'Detenido';
    case 'notInstalled':
      return 'No instalado';
    case 'error':
      return 'Error';
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}
