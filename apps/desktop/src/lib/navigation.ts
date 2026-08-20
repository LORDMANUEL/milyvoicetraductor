/** Identificadores estables de páginas; evitan rutas mágicas dispersas. */
export type PageId =
  | 'panel'
  | 'live'
  | 'sessions'
  | 'models'
  | 'permissions'
  | 'devices'
  | 'diagnostics'
  | 'settings'
  | 'help'
  | 'about';

export interface NavigationItem {
  id: PageId;
  label: string;
  icon: string;
}

export const navigationItems: readonly NavigationItem[] = [
  { id: 'panel', label: 'Panel', icon: '⌂' },
  { id: 'live', label: 'Traducción en vivo', icon: '◉' },
  { id: 'sessions', label: 'Sesiones guardadas', icon: '▣' },
  { id: 'models', label: 'Modelos', icon: '⬡' },
  { id: 'permissions', label: 'Permisos', icon: '◇' },
  { id: 'devices', label: 'Dispositivos', icon: '◌' },
  { id: 'diagnostics', label: 'Diagnóstico', icon: '!' },
  { id: 'settings', label: 'Ajustes', icon: '⚙' },
  { id: 'help', label: 'Ayuda', icon: '?' },
  { id: 'about', label: 'Acerca de', icon: 'i' }
] as const;
