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
  modelPhase: 'idle' | 'prepare' | 'download' | 'optimize' | 'verify' | 'ready' | 'failed' | string;
  modelMessage: string | null;
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

export interface LocalEngineSession {
  port: number;
  credential: string;
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
  activeModelPack: 'realtime-m2m100' | 'lite-nllb' | 'business-qwen';
  showOriginalSubtitle: boolean;
}

export interface RealtimeWord {
  start: number;
  end: number;
  text: string;
}

export interface RealtimeEvent {
  protocol: number;
  type: string;
  start?: number;
  end?: number;
  original?: string;
  translation?: string;
  language?: string;
  words?: RealtimeWord[];
  sessionMode?: 'meeting' | 'education' | 'karaoke' | 'compact';
  rms?: number;
  peak?: number;
  silentMs?: number;
  speech?: boolean;
  pressure?: 'healthy' | 'pressure' | 'overloaded';
  audioQueueMs?: number;
  realTimeFactor?: number;
  asrP50Ms?: number;
  translationP50Ms?: number;
  message?: string;
  code?: string;
  binaryPcm?: boolean;
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
