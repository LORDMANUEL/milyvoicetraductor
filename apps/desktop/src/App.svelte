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
  import Onboarding from './pages/Onboarding.svelte';
  import { defaultConfig, desktopApi } from './lib/api';
  import { needsOnboarding } from './lib/onboarding';
  import type { PageId } from './lib/navigation';
  import type { AppConfig, AppStatus, CacheStatus, OnboardingStatus, SystemSnapshot } from './types';

  let activePage: PageId = 'panel';
  let loading = true;
  let error = '';
  let initialRouteResolved = false;
  let status: AppStatus = { version: '2.0.2', engine: 'notInstalled', models: 'notInstalled', installedModels: 0, extensionConnected: false, activeModelPack: null };
  let onboarding: OnboardingStatus = { runtimeReady: false, bridgeReady: false, extensionDetected: false, modelState: 'notInstalled', downloadedBytes: 0, totalBytes: null, bootstrapState: 'unknown', errorCode: null, errorMessage: null };
  let system: SystemSnapshot = { operatingSystem: 'Cargando…', architecture: '', cpuBrand: '', logicalCpus: 0, totalMemoryMb: 0, gpu: null };
  let cache: CacheStatus = { bytes: 0, entries: 0, maxBytes: 256 * 1024 * 1024 };
  let config: AppConfig = { ...defaultConfig };

  async function load() {
    loading = true;
    error = '';
    try {
      [status, onboarding, system, cache, config] = await Promise.all([
        desktopApi.getAppStatus(), desktopApi.getOnboardingStatus(), desktopApi.getSystemInfo(),
        desktopApi.getCacheStatus(), desktopApi.getConfig()
      ]);

      // Una instalación válida debe abrir el shell aunque todavía no exista un
      // modelo. En ese caso aterriza en Model Manager y la descarga queda bajo
      // control explícito del usuario.
      if (!initialRouteResolved) {
        initialRouteResolved = true;
        if (onboarding.modelState !== 'ready') activePage = 'models';
      }
    } catch {
      error = 'No se pudo cargar el estado local. Revisa los logs sanitizados de la aplicación.';
    } finally {
      loading = false;
    }
  }

  async function finishOnboarding() {
    await load();
    if (!needsOnboarding(onboarding)) {
      activePage = onboarding.modelState === 'ready' ? 'live' : 'models';
    }
  }

  async function saveConfig(value: AppConfig) {
    config = await desktopApi.saveConfig(value);
    cache = await desktopApi.getCacheStatus();
  }

  async function clearCache() { cache = await desktopApi.clearCache(); }
  async function refreshStatus() {
    [status, onboarding] = await Promise.all([desktopApi.getAppStatus(), desktopApi.getOnboardingStatus()]);
  }

  onMount(load);
  $: onboardingRequired = needsOnboarding(onboarding);
</script>

{#if loading}
  <div class="loading" role="status"><span></span><p>Cargando servicios locales…</p></div>
{:else if error}
  <div class="error-banner" role="alert">{error}<button onclick={load}>Reintentar</button></div>
{:else if onboardingRequired}
  <Onboarding onReady={finishOnboarding} />
{:else}
  <div class="app-shell" data-theme={config.theme}>
    <Sidebar {activePage} onNavigate={(page) => (activePage = page)} />
    <main class="main-content">
      {#if activePage === 'panel'}<Panel {status} {system} {cache} />
      {:else if activePage === 'live'}<LiveTranslation {config} onChanged={refreshStatus} />
      {:else if activePage === 'sessions'}<Sessions />
      {:else if activePage === 'models'}<Models onChanged={refreshStatus} />
      {:else if activePage === 'permissions'}<Permissions {status} />
      {:else if activePage === 'devices'}<Devices {system} />
      {:else if activePage === 'settings'}<Settings {config} {cache} onSave={saveConfig} onClearCache={clearCache} />
      {:else if activePage === 'help'}<Help />
      {:else}<About version={status.version} />{/if}
    </main>
  </div>
{/if}
