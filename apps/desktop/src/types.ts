/** Tipos públicos equivalentes a los DTOs serializados por Rust. */
export type ComponentState = 'ready' | 'stopped' | 'notInstalled' | 'error';

export interface AppStatus {
  version: string;
  engine: ComponentState;
  models: ComponentState;
  installedModels: number;
  extensionConnected: boolean;
}

export interface SystemSnapshot {
  operatingSystem: string;
  architecture: string;
  cpuBrand: string;
  logicalCpus: number;
  totalMemoryMb: number;
  gpu: string | null;
}

export interface AppConfig {
  schemaVersion: number;
  interfaceLanguage: string;
  sourceLanguage: 'auto' | 'en' | 'zh';
  targetLanguage: 'es';
  theme: 'system' | 'light' | 'dark';
  autoStartEngine: boolean;
  cacheLimitMb: number;
  logLevel: 'error' | 'warn' | 'info' | 'debug';
  microphoneConsent: boolean;
}

export interface CacheStatus {
  bytes: number;
  entries: number;
  maxBytes: number;
}

export interface PublicError {
  code: string;
  message: string;
}
