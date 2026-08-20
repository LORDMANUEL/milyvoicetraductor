<script lang="ts">
  import { onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import { modelErrorCode, modelErrorMessage } from '../lib/modelErrors';
  import type { AutoSelectionResult, HardwareAdvisor, ModelPackInfo } from '../types';

  export let onChanged: () => Promise<void>;

  let packs: ModelPackInfo[] = [];
  let advisor: HardwareAdvisor | null = null;
  let busy = '';
  let message = '';
  let lastErrorCode = '';
  let lastFailedPack = '';
  let externalPackPath = '';
  let externalPackUrl = '';
  let lastSelection: AutoSelectionResult | null = null;

  async function load() {
    const [catalog, hardware] = await Promise.all([
      desktopApi.getModelCatalog(),
      desktopApi.getHardwareAdvisor()
    ]);
    packs = catalog;
    advisor = hardware;
  }

  function begin(operation: string, status: string) {
    busy = operation;
    lastErrorCode = '';
    lastFailedPack = '';
    message = status;
  }

  function fail(error: unknown, packId = '') {
    lastErrorCode = modelErrorCode(error);
    lastFailedPack = packId;
    message = modelErrorMessage(error);
  }

  async function install(pack: ModelPackInfo) {
    begin(`download:${pack.id}`, 'Descargando, optimizando y verificando el modelo…');
    try {
      await desktopApi.installModel(pack.id);
      message = 'Modelo guardado y verificado. No se cargó todavía en memoria.';
      await load();
      await onChanged();
    } catch (error) {
      fail(error, pack.id);
    } finally {
      busy = '';
    }
  }

  async function activate(pack: ModelPackInfo) {
    begin(`activate:${pack.id}`, 'Comprobando el presupuesto total y activando el modelo…');
    try {
      await desktopApi.activateModel(pack.id, pack.version);
      message = 'Modelo activado. Solo este ASR y este traductor quedarán residentes.';
      await load();
      await onChanged();
    } catch (error) {
      fail(error, pack.id);
    } finally {
      busy = '';
    }
  }

  async function optimize() {
    begin('optimize', 'Midiendo velocidad, RTF y memoria total de los modelos instalados…');
    lastSelection = null;
    try {
      lastSelection = await desktopApi.optimizeModels('en-es', true);
      message = `Seleccionado ${lastSelection.selected} sobre ${lastSelection.backend}.`;
      await load();
      await onChanged();
    } catch (error) {
      fail(error);
    } finally {
      busy = '';
    }
  }

  async function importExternal() {
    const path = externalPackPath.trim();
    if (!path) {
      lastErrorCode = 'MODEL_EXTERNAL_PATH';
      message = 'Escribe la ruta local de un archivo .mmpack.';
      return;
    }
    begin('import', 'Aislando y verificando el pack externo…');
    try {
      const pack = await desktopApi.importModelPack(path);
      message = `Pack externo ${pack.id} importado y verificado. Actívalo manualmente o ejecuta el benchmark automático.`;
      externalPackPath = '';
      await load();
      await onChanged();
    } catch (error) {
      fail(error);
    } finally {
      busy = '';
    }
  }

  async function importExternalUrl() {
    const url = externalPackUrl.trim();
    if (!url) {
      lastErrorCode = 'MODEL_EXTERNAL_SOURCE';
      message = 'Escribe una URL HTTPS de GitHub o Hugging Face que termine en .mmpack.';
      return;
    }
    begin('import-url', 'Descargando a cuarentena y verificando el repositorio externo…');
    try {
      const pack = await desktopApi.importModelPackUrl(url);
      message = `Repositorio ${pack.id} descargado y verificado. No se activó automáticamente.`;
      externalPackUrl = '';
      await load();
      await onChanged();
    } catch (error) {
      fail(error);
    } finally {
      busy = '';
    }
  }

  async function verify(pack: ModelPackInfo) {
    begin(`verify:${pack.id}`, 'Verificando integridad SHA-256 del pack local…');
    try {
      const ok = await desktopApi.verifyModel(pack.id, pack.version);
      message = ok
        ? 'Integridad del pack verificada.'
        : 'El pack no pasó la verificación. Reinstálalo antes de usarlo.';
    } catch (error) {
      fail(error);
    } finally {
      busy = '';
    }
  }

  async function remove(pack: ModelPackInfo) {
    if (pack.active) return;
    begin(`remove:${pack.id}`, 'Eliminando pack local…');
    try {
      await desktopApi.removeModel(pack.id, pack.version);
      message = 'Pack eliminado del equipo.';
      await load();
      await onChanged();
    } catch (error) {
      fail(error);
    } finally {
      busy = '';
    }
  }

  async function rollback() {
    begin('rollback', 'Restaurando el modelo anterior…');
    try {
      await desktopApi.rollbackModel();
      message = 'Se restauró el pack anterior.';
      await load();
      await onChanged();
    } catch (error) {
      fail(error);
    } finally {
      busy = '';
    }
  }

  function backendStatus(runtimeDetected: boolean, adapterReady: boolean): string {
    if (adapterReady) return 'Listo';
    if (runtimeDetected) return 'Detectado · pendiente de benchmark';
    return 'No validado';
  }

  function totalProductMb(pack: ModelPackInfo): number {
    return Math.round(
      pack.measuredTotalProductMb
        ?? pack.estimatedTotalProductMb
        ?? (pack.ramMb + pack.sharedGpuMb + pack.productReserveMb)
    );
  }

  function memoryLabel(pack: ModelPackInfo): string {
    const total = `${totalProductMb(pack)} MiB producto`;
    const engine = ` · motor/modelo ${pack.ramMb} MiB`;
    const shared = pack.sharedGpuMb > 0 ? ` · iGPU compartida ${pack.sharedGpuMb} MiB` : '';
    const vram = pack.vramMb > 0 ? ` · VRAM ${pack.vramMb} MiB` : ' · sin GPU obligatoria';
    return total + engine + shared + vram;
  }

  onMount(load);
</script>

<section class="page-stack">
  <header class="page-header">
    <div>
      <p class="eyebrow">Mily Engine Hub</p>
      <h1>Modelos y motores</h1>
      <p>Descarga varios modelos, pero mantiene solo un ASR y un traductor en memoria.</p>
    </div>
    <div class="button-row">
      <button class="primary" onclick={optimize} disabled={Boolean(busy)}>
        {busy === 'optimize' ? 'Midiendo…' : 'Optimizar automáticamente'}
      </button>
      <button class="secondary" onclick={rollback} disabled={Boolean(busy)}>Rollback</button>
    </div>
  </header>

  <article class="panel-card model-card active-pack">
    <div class="panel-title">
      <div>
        <span class="card-title">Contrato de recursos</span>
        <h3>Máximo 2 GB para todo MilyVoice</h3>
      </div>
      <span class="pill ok">512 MB VRAM compatible</span>
    </div>
    <p>El límite de 2,048 MiB suma motor, modelos, sidecars, memoria compartida de iGPU y una reserva de 320 MiB para Desktop y Native Messaging. La VRAM dedicada se limita a 384 MiB para dejar margen a Windows y Chrome.</p>
    <div class="model-meta">
      <span>Reserva Desktop/bridge: 320 MiB</span>
      <span>Lite estable: ≤ 1,200 MiB</span>
      <span>Pico Lite: ≤ 1,536 MiB</span>
      <span>Rescate antes de 2 GB</span>
      <span>CPU siempre disponible</span>
    </div>
  </article>

  {#if advisor}
    <article class="panel-card model-card">
      <div class="panel-title">
        <div>
          <span class="card-title">Hardware Advisor</span>
          <h3>Recomendado: {advisor.recommendedProfile}</h3>
        </div>
        <span class="pill" class:ok={advisor.legacyHaswellCompatible}>
          {advisor.legacyHaswellCompatible ? 'AVX2 listo' : 'Compatibilidad básica'}
        </span>
      </div>
      <p>{advisor.message}</p>
      <div class="model-meta">
        <span>{advisor.system.cpuBrand}</span>
        <span>{advisor.system.physicalCpus} cores · {advisor.system.logicalCpus} hilos</span>
        <span>{Math.round(advisor.system.availableMemoryMb / 1024)} / {Math.round(advisor.system.totalMemoryMb / 1024)} GB RAM disponible/total</span>
        <span>GPU: {advisor.system.gpu ?? 'no detectada'}</span>
      </div>
      <div class="model-meta">
        {#each advisor.backends as backend}
          <span>{backend.backend}: {backendStatus(backend.runtimeDetected, backend.adapterReady)}</span>
        {/each}
      </div>
    </article>
  {/if}

  <article class="panel-card model-card">
    <div class="panel-title">
      <div>
        <span class="card-title">Modelos externos</span>
        <h3>Importar o descargar un pack verificado</h3>
      </div>
      <span class="pill">.mmpack</span>
    </div>
    <p>Solo se aceptan manifiestos, modelos y tokenizadores. Scripts, EXE, DLL y proveedores desconocidos se bloquean. Importar o descargar nunca activa el modelo automáticamente.</p>
    <div class="button-row">
      <input bind:value={externalPackPath} placeholder="C:\Modelos\mi-modelo.mmpack" aria-label="Ruta del pack externo" />
      <button class="secondary" onclick={importExternal} disabled={Boolean(busy)}>
        {busy === 'import' ? 'Verificando…' : 'Importar archivo'}
      </button>
    </div>
    <div class="button-row">
      <input bind:value={externalPackUrl} placeholder="https://github.com/.../modelo.mmpack" aria-label="URL del repositorio externo" />
      <button class="secondary" onclick={importExternalUrl} disabled={Boolean(busy)}>
        {busy === 'import-url' ? 'Descargando…' : 'Agregar repositorio'}
      </button>
    </div>
    <small>Orígenes permitidos: GitHub y Hugging Face mediante HTTPS. La URL debe apuntar a un archivo .mmpack.</small>
  </article>

  <div class="model-grid">
    {#each packs as pack}
      <article class="panel-card model-card" class:active-pack={pack.active}>
        <div class="panel-title">
          <div>
            <span class="card-title">{pack.id} · {pack.version} · {pack.tier}</span>
            <h3>{pack.title}</h3>
          </div>
          <span class="pill" class:ok={pack.active}>
            {pack.active ? 'Activo' : pack.installed ? 'Instalado' : 'Disponible'}
          </span>
        </div>
        <p>{pack.licenseNote}</p>
        <div class="model-meta">
          <span>{memoryLabel(pack)}</span>
          <span>Reserva base: {pack.productReserveMb} MiB</span>
          <span>Ruta: {pack.routes.join(', ')}</span>
          <span>Motor: {pack.engine}</span>
          <span>Backends: {pack.supportedBackends.join(', ')}</span>
          <span>{pack.commercialUse ? 'Uso comercial permitido' : 'Uso restringido/no comercial'}</span>
        </div>
        {#if !pack.resourceAllowed}
          <div class="error-state">
            <strong>No se activará en este equipo</strong>
            <p>Motivo: {pack.resourceReason}. Estimación total: {totalProductMb(pack)} MiB; límite: 2,048 MiB RAM / 384 MiB VRAM.</p>
          </div>
        {/if}
        <div class="button-row">
          {#if !pack.installed}
            <button class="primary" onclick={() => install(pack)} disabled={Boolean(busy)}>
              {busy === `download:${pack.id}` ? 'Descargando…' : lastFailedPack === pack.id ? 'Reintentar' : 'Descargar'}
            </button>
          {:else if !pack.active}
            <button class="primary" onclick={() => activate(pack)} disabled={Boolean(busy) || !pack.resourceAllowed}>
              {busy === `activate:${pack.id}` ? 'Activando…' : 'Activar'}
            </button>
          {:else}
            <button class="primary" disabled>Activo</button>
          {/if}
          {#if pack.installed}
            <button class="secondary" onclick={() => verify(pack)} disabled={Boolean(busy)}>
              {busy === `verify:${pack.id}` ? 'Verificando…' : 'Verificar SHA-256'}
            </button>
          {/if}
          {#if pack.installed && !pack.active}
            <button class="danger-button" onclick={() => remove(pack)} disabled={Boolean(busy)}>
              {busy === `remove:${pack.id}` ? 'Eliminando…' : 'Eliminar local'}
            </button>
          {/if}
        </div>
      </article>
    {/each}
    {#if packs.length === 0}
      <article class="empty-state">
        <h2>Catálogo no disponible</h2>
        <p>El runtime local todavía no está preparado.</p>
      </article>
    {/if}
  </div>

  {#if lastSelection}
    <article class="panel-card model-card active-pack">
      <span class="card-title">Resultado del benchmark</span>
      <h3>{lastSelection.selected} · {lastSelection.backend}</h3>
      <p>Puntuación: {lastSelection.score.toFixed(3)}. Los modelos rechazados no se cargaron.</p>
    </article>
  {/if}

  {#if message}
    <div class:error-state={Boolean(lastErrorCode)} class="model-operation-message" aria-live="polite">
      <strong>{lastErrorCode ? 'No se completó la operación' : 'Estado'}</strong>
      <p>{message}</p>
      {#if lastErrorCode}<small>Código: {lastErrorCode}</small>{/if}
    </div>
  {/if}
</section>
