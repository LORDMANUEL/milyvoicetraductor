<script lang="ts">
  import { onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import type { ModelPackInfo } from '../types';
  export let onChanged: () => Promise<void>;

  let packs: ModelPackInfo[] = [];
  let busy = '';
  let message = '';

  async function load() { packs = await desktopApi.getModelCatalog(); }
  async function install(pack: ModelPackInfo) {
    busy = pack.id; message = 'Descargando y verificando archivos del modelo…';
    try { await desktopApi.installModel(pack.id); message = 'Pack instalado y activado.'; await load(); await onChanged(); }
    catch { message = 'No se pudo instalar el pack. Revisa conexión, espacio libre y licencia.'; }
    finally { busy = ''; }
  }
  async function verify(pack: ModelPackInfo) {
    busy = `verify:${pack.id}`; message = 'Verificando integridad SHA-256 del pack local…';
    try {
      const ok = await desktopApi.verifyModel(pack.id, pack.version);
      message = ok ? 'Integridad del pack verificada.' : 'El pack no pasó la verificación. Reinstálalo antes de usarlo.';
    } catch { message = 'No se pudo completar la verificación del pack.'; }
    finally { busy = ''; }
  }
  async function remove(pack: ModelPackInfo) {
    if (pack.active) return;
    busy = `remove:${pack.id}`; message = 'Eliminando pack local…';
    try { await desktopApi.removeModel(pack.id, pack.version); message = 'Pack eliminado del equipo.'; await load(); await onChanged(); }
    catch { message = 'No se pudo eliminar el pack. El pack activo está protegido.'; }
    finally { busy = ''; }
  }
  async function rollback() {
    busy = 'rollback';
    try { await desktopApi.rollbackModel(); message = 'Se restauró el pack anterior.'; await load(); await onChanged(); }
    catch { message = 'No existe un pack anterior válido para restaurar.'; }
    finally { busy = ''; }
  }
  onMount(load);
</script>
<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Model Manager</p><h1>Modelos</h1><p>Descarga a staging, activa al completar y permite rollback.</p></div><button class="secondary" onclick={rollback} disabled={Boolean(busy)}>Rollback</button></header>
  <div class="model-grid">
    {#each packs as pack}
      <article class="panel-card model-card" class:active-pack={pack.active}>
        <div class="panel-title"><div><span class="card-title">{pack.id} · {pack.version}</span><h3>{pack.title}</h3></div><span class="pill" class:ok={pack.active}>{pack.active ? 'Activo' : pack.installed ? 'Instalado' : 'Disponible'}</span></div>
        <p>{pack.licenseNote}</p>
        <div class="model-meta"><span>RAM sugerida: {pack.recommendedRamGb} GB</span><span>{pack.commercialUse ? 'Perfil permisivo/comercial' : 'Uso no comercial según modelo'}</span></div>
        <div class="button-row">
          <button class="primary" onclick={() => install(pack)} disabled={pack.active || busy === pack.id}>{busy === pack.id ? 'Instalando…' : pack.active ? 'Activo' : pack.installed ? 'Activar/reinstalar' : 'Descargar e instalar'}</button>
          {#if pack.installed}<button class="secondary" onclick={() => verify(pack)} disabled={Boolean(busy)}>{busy === `verify:${pack.id}` ? 'Verificando…' : 'Verificar SHA-256'}</button>{/if}
          {#if pack.installed && !pack.active}<button class="danger-button" onclick={() => remove(pack)} disabled={Boolean(busy)}>{busy === `remove:${pack.id}` ? 'Eliminando…' : 'Eliminar local'}</button>{/if}
        </div>
      </article>
    {/each}
    {#if packs.length === 0}<article class="empty-state"><h2>Catálogo no disponible en vista web</h2><p>Ábrelo desde la aplicación Tauri para administrar modelos locales.</p></article>{/if}
  </div>
  {#if message}<p class="form-message" aria-live="polite">{message}</p>{/if}
</section>
