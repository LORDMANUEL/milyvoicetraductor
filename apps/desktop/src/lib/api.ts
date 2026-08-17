import { invoke } from '@tauri-apps/api/core';
import type { AppConfig, AppStatus, CacheStatus, SystemSnapshot } from '../types';

const defaultConfig: AppConfig = {
  schemaVersion: 1,
  interfaceLanguage: 'es',
  sourceLanguage: 'auto',
  targetLanguage: 'es',
  theme: 'system',
  autoStartEngine: false,
  cacheLimitMb: 256,
  logLevel: 'info',
  microphoneConsent: false
};

/** Detecta Tauri sin depender de APIs privadas durante SSR/tests. */
export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

/** Gateway único hacia Rust. En navegador ofrece un preview explícitamente local/dev. */
export class DesktopApi {
  async getAppStatus(): Promise<AppStatus> {
    if (!isTauriEnvironment()) {
      return {
        version: '0.1.0-web-preview',
        engine: 'notInstalled',
        models: 'notInstalled',
        installedModels: 0,
        extensionConnected: false
      };
    }
    return invoke<AppStatus>('get_app_status');
  }

  async getSystemInfo(): Promise<SystemSnapshot> {
    if (!isTauriEnvironment()) {
      return {
        operatingSystem: 'Vista previa web',
        architecture: 'N/D',
        cpuBrand: 'Disponible únicamente en Tauri',
        logicalCpus: 0,
        totalMemoryMb: 0,
        gpu: null
      };
    }
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
}

export const desktopApi = new DesktopApi();
