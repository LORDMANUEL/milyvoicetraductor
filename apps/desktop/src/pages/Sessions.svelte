<script lang="ts">
  import { onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import type { SessionSummary } from '../types';
  type ExportFormat = 'txt' | 'srt' | 'srt-bilingual' | 'vtt';
  let sessions: SessionSummary[] = [];
  let message = '';

  async function load() { sessions = await desktopApi.listSessions(); }
  function downloadText(name: string, text: string, mime: string) {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function exportSession(session: SessionSummary, format: ExportFormat) {
    try {
      const text = await desktopApi.getSessionExport(session.id, format);
      const extension = format === 'srt-bilingual' ? 'srt' : format;
      const suffix = format === 'srt-bilingual' ? '-bilingue' : '';
      const mime = extension === 'srt' ? 'application/x-subrip' : extension === 'vtt' ? 'text/vtt' : 'text/plain';
      downloadText(`milyvoice-${session.id}${suffix}.${extension}`, text, mime);
      message = '';
    } catch { message = 'No se pudo exportar la sesión.'; }
  }
  async function remove(session: SessionSummary) {
    if (!confirm('¿Eliminar esta transcripción local? Esta acción no se puede deshacer.')) return;
    try { await desktopApi.deleteSession(session.id); await load(); }
    catch { message = 'No se pudo eliminar la sesión.'; }
  }
  onMount(load);
</script>
<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Historial opt-in</p><h1>Sesiones guardadas</h1><p>Solo aparecen si activaste “Guardar transcripción local”.</p></div><button class="secondary" onclick={load}>Actualizar</button></header>
  {#if sessions.length === 0}
    <article class="empty-state"><div class="empty-icon">▣</div><h2>No hay transcripciones guardadas</h2><p>Por privacidad, el guardado está desactivado de forma predeterminada.</p></article>
  {:else}
    <div class="session-list">
      {#each sessions as session}
        <article class="panel-card session-row"><div><strong>{new Date(session.createdAt).toLocaleString()}</strong><p>{session.sourceLanguage.toUpperCase()} → ES · {session.segmentCount} segmentos · {session.durationSeconds.toFixed(1)} s</p></div><div class="button-row"><button class="secondary" onclick={() => exportSession(session,'txt')}>TXT bilingüe</button><button class="secondary" onclick={() => exportSession(session,'srt')}>SRT ES</button><button class="secondary" onclick={() => exportSession(session,'srt-bilingual')}>SRT bilingüe</button><button class="secondary" onclick={() => exportSession(session,'vtt')}>VTT</button><button class="danger-button" onclick={() => remove(session)}>Eliminar</button></div></article>
      {/each}
    </div>
  {/if}
  {#if message}<p class="form-message">{message}</p>{/if}
</section>
