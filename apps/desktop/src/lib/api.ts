import { invoke } from '@tauri-apps/api/core';
import type {
  AppConfig, AppStatus, CacheStatus, EngineRuntimeStatus, ModelPackInfo,
  OnboardingStatus, RuntimeLocations, SessionSummary, SystemSnapshot
} from '../types';

export const defaultConfig: AppConfig = {
  schemaVersion: 2,
  interfaceLanguage: 'es',
  sourceLanguage: 'auto',
  targetLanguage: 'es',
  theme: 'system',
  autoStartEngine: false,
  cacheLimitMb: 256,
  logLevel: 'info',
  microphoneConsent: false,
  persistTranscripts: false,
  computeProfile: 'auto',
  enginePort: 8765,
  activeModelPack: 'realtime-m2m100',
  showOriginalSubtitle: true
};

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

/** Gateway único hacia Rust. El fallback web nunca simula disponibilidad. */
export class DesktopApi {
  async getAppStatus(): Promise<AppStatus> {
    if (!isTauriEnvironment()) return {
      version: '1.0.5-web-preview', engine: 'notInstalled', models: 'notInstalled',
      installedModels: 0, extensionConnected: false, activeModelPack: null
    };
    return invoke<AppStatus>('get_app_status');
  }

  async getOnboardingStatus(): Promise<OnboardingStatus> {
    if (!isTauriEnvironment()) return {
      runtimeReady: false,
      bridgeReady: false,
      extensionDetected: false,
      modelState: 'notInstalled',
      downloadedBytes: 0,
      totalBytes: null,
      modelPhase: 'idle',
      modelMessage: null,
      bootstrapState: 'unknown',
      errorCode: null,
      errorMessage: null
    };
    return invoke<OnboardingStatus>('get_onboarding_status');
  }

  async repairInstallation(): Promise<void> {
    if (!isTauriEnvironment()) return;
    return invoke<void>('repair_installation');
  }

  async getSystemInfo(): Promise<SystemSnapshot> {
    if (!isTauriEnvironment()) return {
      operatingSystem: 'Vista previa web', architecture: 'N/D',
      cpuBrand: 'Disponible únicamente en Tauri', logicalCpus: 0, totalMemoryMb: 0, gpu: null
    };
    return invoke<SystemSnapshot>('get_system_info');
  }

  async getConfig(): Promise<AppConfig> {
    if (!isTauriEnvironment()) return { ...defaultConfig };
    return invoke<AppConfig>('get_config');
  }

  async saveConfig(config: AppConfig): Promise<AppConfig> {
    if (!isTauriEnvironment()) return { ...config };
    return invoke<AppConfig>('save_config', { config });
  }

  async getCacheStatus(): Promise<CacheStatus> {
    if (!isTauriEnvironment()) return { bytes: 0, entries: 0, maxBytes: 256 * 1024 * 1024 };
    return invoke<CacheStatus>('get_cache_status');
  }

  async clearCache(): Promise<CacheStatus> {
    if (!isTauriEnvironment()) return { bytes: 0, entries: 0, maxBytes: 256 * 1024 * 1024 };
    return invoke<CacheStatus>('clear_cache');
  }

  async getEngineStatus(): Promise<EngineRuntimeStatus> {
    if (!isTauriEnvironment()) return { state: 'notInstalled', pid: null, port: 8765, message: 'Vista previa web' };
    return invoke<EngineRuntimeStatus>('get_engine_status');
  }

  async startEngine(): Promise<EngineRuntimeStatus> {
    if (!isTauriEnvironment()) return this.getEngineStatus();
    return invoke<EngineRuntimeStatus>('start_engine');
  }

  async stopEngine(): Promise<EngineRuntimeStatus> {
    if (!isTauriEnvironment()) return this.getEngineStatus();
    return invoke<EngineRuntimeStatus>('stop_engine');
  }

  async getModelCatalog(): Promise<ModelPackInfo[]> {
    if (!isTauriEnvironment()) return [];
    return invoke<ModelPackInfo[]>('get_model_catalog');
  }

  async installModel(packId: string): Promise<ModelPackInfo> {
    return invoke<ModelPackInfo>('install_model', { packId });
  }

  async verifyModel(packId: string, version: string): Promise<boolean> {
    if (!isTauriEnvironment()) return false;
    return invoke<boolean>('verify_model', { packId, version });
  }

  async removeModel(packId: string, version: string): Promise<void> {
    return invoke<void>('remove_model', { packId, version });
  }

  async rollbackModel(): Promise<ModelPackInfo> {
    return invoke<ModelPackInfo>('rollback_model');
  }

  async listSessions(): Promise<SessionSummary[]> {
    if (!isTauriEnvironment()) return [];
    return invoke<SessionSummary[]>('list_sessions');
  }

  async getSessionExport(sessionId: string, format: 'txt' | 'srt'): Promise<string> {
    return invoke<string>('get_session_export', { sessionId, format });
  }

  async deleteSession(sessionId: string): Promise<void> {
    return invoke<void>('delete_session', { sessionId });
  }

  async getRuntimeLocations(): Promise<RuntimeLocations> {
    if (!isTauriEnvironment()) return { models: 'N/D', sessions: 'N/D', extension: 'N/D' };
    return invoke<RuntimeLocations>('get_runtime_locations');
  }
}

export const desktopApi = new DesktopApi();
