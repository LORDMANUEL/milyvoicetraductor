<script lang="ts">
  import { onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import { modelErrorCode, modelErrorMessage } from '../lib/modelErrors';
  import type { HardwareAdvisor, ModelPackInfo } from '../types';

  export let onChanged: () => Promise<void>;

  let packs: ModelPackInfo[] = [];
  let advisor: HardwareAdvisor | null = null;
  let busy = '';
  let message = '';
  let lastErrorCode = '';
  let lastFailedPack = '';

  async function load() {
    const [catalog, hardware] = await Promise.all([
      desktopApi.getModelCatalog(),
      desktopApi.getHardwareAdvisor()
    ]);
    packs = catalog;
    advisor = hardware;
  }

  async function install(pack: ModelPackInfo) {
    busy = pack.id;
    lastErrorCode = '';
    lastFailedPack = '';
    message = 'Descargando y verificando archivos del modelo…';
    try {
      await desktopApi.installModel(pack.id);
      message = 'Pack instalado, verificado y activado.';
      await load();
      await onChanged();
    } catch (error) {
      lastErrorCode = modelErrorCode(error);
      lastFailedPack = pack.id;
      message = modelErrorMessage(error);
    } finally {
      busy = '';
    }
  }

  async function verify(pack: ModelPackInfo) {
    busy = `verify:${pack.id}`;
    message = 'Verificando integridad SHA-256 del pack local…';
    try {
      const ok = await desktopApi.verifyModel(pack.id, pack.version);
      message = ok
        ? 'Integridad del pack verificada.'
        : 'El pack no pasó la verificación. Reinstálalo antes de usarlo.';
    } catch (error) {
      lastErrorCode = modelErrorCode(error);
      message = modelErrorMessage(error);
    } finally {
      busy = '';
    }
  }

  async function remove(pack: ModelPackInfo) {
    if (pack.active) return;
    busy = `remove:${pack.id}`;
    message = 'Eliminando pack local…';
    try {
      await desktopApi.removeModel(pack.id, pack.version);
      message = 'Pack eliminado del equipo.';
      await load();
      await onChanged();
    } catch (error) {
      lastErrorCode = modelErrorCode(error);
      message = modelErrorMessage(error);
    } finally {
      busy = '';
    }
  }

  async function rollback() {
    busy = 'rollback';
    try {
      await desktopApi.rollbackModel();
      message = 'Se restauró el pack anterior.';
      await load();
      await onChanged();
    } catch (error) {
      lastErrorCode = modelErrorCode(error);
      message = modelErrorMessage(error);
    } finally {
      busy = '';
    }
  }

  function backendStatus(runtimeDetected: boolean, adapterReady: boolean): string {
    if (adapterReady) return 'Listo';
    if (runtimeDetected) return 'Detectado · falta benchmark/adaptador';
    return 'No validado';
  }

  onMount(load);
</script>

<section class="page-stack">
  <header class="page-header">
    <div>
      <p class="eyebrow">Model Manager</p>
      <h1>Modelos</h1>
      <p>Descarga reanudable, staging, verificación y activación segura.</p>
    </div>
    <button class="secondary" onclick={rollback} disabled={Boolean(busy)}>Rollback</button>
  </header>

  {#if advisor}
    <article class="panel-card model-card">
      <div class="panel-title">
        <div>
          <span class="card-title">Hardware Advisor</span>
          <h3>Recomendado para este equipo: {advisor.recommendedProfile}</h3>
        </div>
        <span class="pill" class:ok={advisor.legacyHaswellCompatible}>
          {advisor.legacyHaswellCompatible ? 'AVX2 listo' : 'Compatibilidad básica'}
        </span>
      </div>
      <p>{advisor.message}</p>
      <div class="model-meta">
        <span>{advisor.system.cpuBrand}</span>
        <span>{advisor.system.physicalCpus} cores físicos · {advisor.system.logicalCpus} hilos</span>
        <span>{Math.round(advisor.system.availableMemoryMb / 1024)} / {Math.round(advisor.system.totalMemoryMb / 1024)} GB RAM disponible/total</span>
        <span>AVX2: {advisor.system.cpuFeatures.avx2 ? 'sí' : 'no'} · FMA: {advisor.system.cpuFeatures.fma ? 'sí' : 'no'}</span>
      </div>
      <div class="model-meta">
        {#each advisor.backends as backend}
          <span>
            {backend.backend}: {backendStatus(backend.runtimeDetected, backend.adapterReady)}
          </span>
        {/each}
      </div>
      {#if advisor.benchmarkRequired}
        <small>La selección GPU definitiva se hará únicamente después de una inferencia de benchmark real.</small>
      {/if}
    </article>
  {/if}

  <div class="model-grid">
    {#each packs as pack}
      <article class="panel-card model-card" class:active-pack={pack.active}>
        <div class="panel-title">
          <div>
            <span class="card-title">{pack.id} · {pack.version}</span>
            <h3>{pack.title}</h3>
          </div>
          <span class="pill" class:ok={pack.active}>
            {pack.active ? 'Activo' : pack.installed ? 'Instalado' : 'Disponible'}
          </span>
        </div>
        <p>{pack.licenseNote}</p>
        <div class="model-meta">
          <span>RAM sugerida: {pack.recommendedRamGb} GB</span>
          <span>{pack.commercialUse ? 'Perfil permisivo/comercial' : 'Uso no comercial según modelo'}</span>
        </div>
        <div class="button-row">
          <button class="primary" onclick={() => install(pack)} disabled={pack.active || busy === pack.id}>
            {busy === pack.id
              ? 'Preparando…'
              : pack.active
                ? 'Activo'
                : lastFailedPack === pack.id
                  ? 'Reintentar'
                  : pack.installed
                    ? 'Activar/reinstalar'
                    : 'Descargar e instalar'}
          </button>
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

  {#if message}
    <div class:error-state={Boolean(lastErrorCode)} class="model-operation-message" aria-live="polite">
      <strong>{lastErrorCode ? 'No se completó la operación' : 'Estado'}</strong>
      <p>{message}</p>
      {#if lastErrorCode}<small>Código: {lastErrorCode}</small>{/if}
    </div>
  {/if}
</section>
