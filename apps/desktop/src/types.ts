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
  tier: 'lite' | 'balanced' | 'quality' | 'experimental' | string;
  routes: string[];
  /** Huella declarada del motor/modelos, sin Desktop ni bridge. */
  ramMb: number;
  vramMb: number;
  /** Memoria de sistema compartida por iGPU que cuenta contra los 2 GiB. */
  sharedGpuMb: number;
  /** Reserva fija para Desktop Tauri + Native Messaging bridge. */
  productReserveMb: number;
  /** Motor + iGPU compartida + reserva base del producto. */
  estimatedTotalProductMb: number;
  engine: string;
  supportedBackends: string[];
  resourceAllowed: boolean;
  resourceReason: string;
  externalAllowed: boolean;
  measuredEngineRamMb?: number;
  measuredTotalProductMb?: number;
  resourceMode?: string;
  benchmark?: Record<string, unknown> | null;
}

export interface AutoSelectionResult {
  selected: string;
  backend: string;
  score: number;
  rejected: Record<string, string>;
  benchmarks: Record<string, unknown>;
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

export interface CpuFeatures {
  sse42: boolean;
  avx: boolean;
  avx2: boolean;
  fma: boolean;
  avx512f: boolean;
  neon: boolean;
}

export interface SystemSnapshot {
  operatingSystem: string;
  architecture: string;
  cpuBrand: string;
  logicalCpus: number;
  physicalCpus: number;
  totalMemoryMb: number;
  availableMemoryMb: number;
  cpuFeatures: CpuFeatures;
  gpu: string | null;
}

export type ComputeBackend = 'cpu' | 'cuda' | 'directMl' | 'openVino' | 'vulkan';

export interface BackendCapability {
  backend: ComputeBackend;
  runtimeDetected: boolean;
  adapterReady: boolean;
  evidence: string[];
}

export interface HardwareAdvisor {
  system: SystemSnapshot;
  backends: BackendCapability[];
  recommendedBackend: ComputeBackend;
  recommendedProfile: 'legacy' | 'balanced' | 'performance' | string;
  legacyHaswellCompatible: boolean;
  benchmarkRequired: boolean;
  message: string;
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
  activeModelPack: string;
  showOriginalSubtitle: boolean;
}

export type SessionMode = 'meeting' | 'education' | 'karaoke' | 'compact';
export type SpeakerFocusMode = 'all' | 'dominant' | 'fixed';
export type AudioSourceMode = 'browser_tab' | 'microphone' | 'media_file' | 'system_loopback';

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
  sessionMode?: SessionMode;
  sourceMode?: AudioSourceMode;
  speakerDetection?: boolean;
  speakerId?: string | null;
  focusMode?: SpeakerFocusMode;
  rms?: number;
  peak?: number;
  silentMs?: number;
  speech?: boolean;
  pressure?: 'healthy' | 'pressure' | 'catch_up' | 'catchUp' | 'rescue';
  audioQueueMs?: number;
  translationQueueAgeMs?: number;
  processMemoryMb?: number;
  memoryHeadroomMb?: number;
  realTimeFactor?: number;
  asrP50Ms?: number;
  asrP95Ms?: number;
  translationP50Ms?: number;
  translationP95Ms?: number;
  translationQueueDepth?: number;
  cpuProfile?: string;
  physicalCores?: number;
  asrThreads?: number;
  translationThreads?: number;
  parallelStages?: boolean;
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
