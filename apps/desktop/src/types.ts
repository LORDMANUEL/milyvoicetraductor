/** Tipos públicos equivalentes a los DTOs serializados por Rust. */
export type ComponentState = 'ready' | 'stopped' | 'notInstalled' | 'error';

export interface AppStatus {
  version: string;
  engine: ComponentState;
  models: ComponentState;
  installedModels: number;
  extensionConnected: boolean;
  activeModelPack: string | null;
}

export interface OnboardingStatus {
  runtimeReady: boolean;
  bridgeReady: boolean;
  extensionDetected: boolean;
  modelState: ComponentState;
  downloadedBytes: number;
  totalBytes: number | null;
  bootstrapState: 'ready' | 'model-pending' | 'installing' | 'failed' | 'unknown';
  errorCode: string | null;
  errorMessage: string | null;
}

export interface EngineRuntimeStatus {
  state: ComponentState;
  pid: number | null;
  port: number;
  message: string;
}

export interface ModelPackInfo {
  id: string;
  version: string;
  title: string;
  installed: boolean;
  active: boolean;
  recommendedRamGb: number;
  commercialUse: boolean;
  licenseNote: string;
}

export interface SessionSummary {
  id: string;
  createdAt: string;
  sourceLanguage: string;
  targetLanguage: string;
  durationSeconds: number;
  segmentCount: number;
}

export interface RuntimeLocations {
  models: string;
  sessions: string;
  extension: string;
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
  persistTranscripts: boolean;
  computeProfile: 'auto' | 'cpu' | 'gpu';
  enginePort: number;
  activeModelPack: 'lite-nllb' | 'business-qwen';
  showOriginalSubtitle: boolean;
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
