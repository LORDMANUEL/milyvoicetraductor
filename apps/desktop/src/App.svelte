<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './components/Sidebar.svelte';
  import Panel from './pages/Panel.svelte';
  import LiveTranslation from './pages/LiveTranslation.svelte';
  import Sessions from './pages/Sessions.svelte';
  import Models from './pages/Models.svelte';
  import Permissions from './pages/Permissions.svelte';
  import Devices from './pages/Devices.svelte';
  import Settings from './pages/Settings.svelte';
  import Help from './pages/Help.svelte';
  import About from './pages/About.svelte';
  import { desktopApi } from './lib/api';
  import type { PageId } from './lib/navigation';
  import type { AppConfig, AppStatus, CacheStatus, SystemSnapshot } from './types';

  let activePage: PageId = 'panel';
  let loading = true;
  let error = '';
  let status: AppStatus = { version: '0.1.0', engine: 'notInstalled', models: 'notInstalled', installedModels: 0, extensionConnected: false };
  let system: SystemSnapshot = { operatingSystem: 'Cargando…', architecture: '', cpuBrand: '', logicalCpus: 0, totalMemoryMb: 0, gpu: null };
  let cache: CacheStatus = { bytes: 0, entries: 0, maxBytes: 256 * 1024 * 1024 };
  let config: AppConfig = { schemaVersion: 1, interfaceLanguage: 'es', sourceLanguage: 'auto', targetLanguage: 'es', theme: 'system', autoStartEngine: false, cacheLimitMb: 256, logLevel: 'info', microphoneConsent: false };

  async function load() {
    loading = true;
    error = '';
    try {
      [status, system, cache, config] = await Promise.all([
        desktopApi.getAppStatus(), desktopApi.getSystemInfo(), desktopApi.getCacheStatus(), desktopApi.getConfig()
      ]);
    } catch {
      error = 'No se pudo cargar el estado local. Revisa los logs sanitizados de la aplicación.';
    } finally {
      loading = false;
    }
  }

  async function saveConfig(value: AppConfig) {
    config = await desktopApi.saveConfig(value);
  }

  async function clearCache() {
    cache = await desktopApi.clearCache();
  }

  onMount(load);
</script>

<div class="app-shell">
  <Sidebar {activePage} onNavigate={(page) => (activePage = page)} />
  <main class="main-content">
    {#if loading}
      <div class="loading" role="status"><span></span><p>Cargando servicios locales…</p></div>
    {:else if error}
      <div class="error-banner" role="alert">{error}<button onclick={load}>Reintentar</button></div>
    {:else}
      {#if activePage === 'panel'}<Panel {status} {system} {cache} />
      {:else if activePage === 'live'}<LiveTranslation />
      {:else if activePage === 'sessions'}<Sessions />
      {:else if activePage === 'models'}<Models installedModels={status.installedModels} />
      {:else if activePage === 'permissions'}<Permissions />
      {:else if activePage === 'devices'}<Devices {system} />
      {:else if activePage === 'settings'}<Settings {config} {cache} onSave={saveConfig} onClearCache={clearCache} />
      {:else if activePage === 'help'}<Help />
      {:else}<About version={status.version} />{/if}
    {/if}
  </main>
</div>
