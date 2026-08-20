<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';

  type RepairStatus = 'started' | 'succeeded' | 'failed';
  type RepairEvent = {
    schemaVersion: number;
    incidentId: string;
    timestamp: number;
    status: RepairStatus;
    component: string;
    stage: string;
    code: string;
    message: string;
    action: string;
  };

  let events: RepairEvent[] = [];
  let loading = true;
  let repairing = false;
  let error = '';

  const statusLabel: Record<RepairStatus, string> = {
    started: 'En proceso',
    succeeded: 'Reparado',
    failed: 'Falló'
  };

  function formatTime(epochSeconds: number): string {
    if (!epochSeconds) return 'N/D';
    return new Date(epochSeconds * 1000).toLocaleString();
  }

  async function loadHistory() {
    loading = true;
    try {
      events = await invoke<RepairEvent[]>('get_repair_history', { limit: 50 });
    } catch {
      error = 'No se pudo leer el historial local de reparación.';
    } finally {
      loading = false;
    }
  }

  async function repair() {
    repairing = true;
    error = '';
    try {
      await invoke<void>('repair_installation');
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'La reparación no terminó correctamente.';
    } finally {
      repairing = false;
      await loadHistory();
    }
  }

  onMount(loadHistory);
</script>

<section class="diagnostics-page">
  <header class="page-heading">
    <div>
      <span class="eyebrow">Soporte local</span>
      <h1>Diagnóstico y reparación</h1>
      <p>Historial sanitizado de fallos e intentos de reparación. No guarda tokens, contraseñas, correos ni rutas privadas del usuario.</p>
    </div>
    <button class="primary-action" onclick={repair} disabled={repairing}>
      {repairing ? 'Reparando…' : 'Reparar instalación'}
    </button>
  </header>

  {#if error}<div class="diagnostic-error" role="alert">{error}</div>{/if}

  <div class="summary-grid">
    <article><strong>{events.filter((event) => event.status === 'failed').length}</strong><span>fallos registrados</span></article>
    <article><strong>{events.filter((event) => event.status === 'succeeded').length}</strong><span>reparaciones correctas</span></article>
    <article><strong>{new Set(events.map((event) => event.incidentId)).size}</strong><span>incidentes</span></article>
  </div>

  {#if loading}
    <p class="empty">Leyendo diagnóstico local…</p>
  {:else if events.length === 0}
    <div class="empty-card"><strong>Sin incidentes de reparación.</strong><span>Si la instalación falla, aquí aparecerá el código y la acción recomendada.</span></div>
  {:else}
    <div class="incident-list">
      {#each events as event}
        <article class:failed={event.status === 'failed'} class:succeeded={event.status === 'succeeded'}>
          <div class="incident-top">
            <span class="status">{statusLabel[event.status]}</span>
            <code>{event.code}</code>
            <time>{formatTime(event.timestamp)}</time>
          </div>
          <h3>{event.component} · {event.stage}</h3>
          <p>{event.message}</p>
          <small>Acción: {event.action}</small>
          <small class="incident-id">ID: {event.incidentId}</small>
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .diagnostics-page{display:grid;gap:24px}.page-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}.page-heading h1{margin:8px 0;font-size:34px}.page-heading p{max-width:720px;color:var(--text-muted,#66758a);line-height:1.6}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.1em;font-weight:800;color:#007b59}.primary-action{border:0;border-radius:12px;padding:12px 16px;background:#00a878;color:#fff;font-weight:800;cursor:pointer}.primary-action:disabled{opacity:.6;cursor:wait}.diagnostic-error{padding:14px 16px;border:1px solid #f1b8b8;background:#fff4f4;border-radius:12px;color:#8b1e1e}.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.summary-grid article{padding:18px;border:1px solid #dfe7e4;border-radius:16px;background:#fff;display:grid;gap:4px}.summary-grid strong{font-size:28px}.summary-grid span{color:#66758a;font-size:13px}.incident-list{display:grid;gap:12px}.incident-list article{border:1px solid #dfe7e4;border-left:4px solid #9aa9b8;border-radius:14px;padding:16px;background:#fff}.incident-list article.failed{border-left-color:#c64040}.incident-list article.succeeded{border-left-color:#00a878}.incident-top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.status{font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.05em}.incident-top code{padding:3px 7px;border-radius:6px;background:#f2f5f4;font-size:11px}.incident-top time{margin-left:auto;color:#66758a;font-size:12px}.incident-list h3{font-size:15px;margin:12px 0 6px}.incident-list p{margin:0 0 8px;line-height:1.5}.incident-list small{display:block;color:#66758a;line-height:1.5}.incident-id{margin-top:4px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.empty,.empty-card{color:#66758a}.empty-card{display:grid;gap:6px;padding:24px;border:1px dashed #cbd8d3;border-radius:16px}@media(max-width:760px){.page-heading{flex-direction:column}.summary-grid{grid-template-columns:1fr}.incident-top time{margin-left:0;width:100%}}
</style>
