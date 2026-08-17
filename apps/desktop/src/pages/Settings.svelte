<script lang="ts">
  import type { AppConfig, CacheStatus } from '../types';
  export let config: AppConfig;
  export let cache: CacheStatus;
  export let onSave: (value: AppConfig) => Promise<void>;
  export let onClearCache: () => Promise<void>;

  let draft: AppConfig = { ...config };
  let message = '';
  let saving = false;

  async function save() {
    saving = true;
    message = '';
    try {
      await onSave({ ...draft });
      message = 'Ajustes guardados.';
    } catch {
      message = 'No se pudieron guardar los ajustes.';
    } finally {
      saving = false;
    }
  }

  async function clearCache() {
    await onClearCache();
    message = 'Caché limpiada.';
  }
</script>

<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Configuración local</p><h1>Ajustes</h1><p>Preferencias persistentes con valores limitados y seguros.</p></div></header>
  <div class="two-columns">
    <article class="panel-card form-card">
      <label>Idioma de origen<select bind:value={draft.sourceLanguage}><option value="auto">Automático</option><option value="en">Inglés</option><option value="zh">Chino</option></select></label>
      <label>Idioma de destino<select bind:value={draft.targetLanguage}><option value="es">Español</option></select></label>
      <label>Tema<select bind:value={draft.theme}><option value="system">Sistema</option><option value="light">Claro</option><option value="dark">Oscuro</option></select></label>
      <label>Nivel de log<select bind:value={draft.logLevel}><option value="error">Error</option><option value="warn">Advertencia</option><option value="info">Información</option><option value="debug">Depuración</option></select></label>
      <label>Límite de caché (MB)<input type="number" min="64" max="4096" step="64" bind:value={draft.cacheLimitMb} /></label>
      <label class="switch-row"><input type="checkbox" bind:checked={draft.microphoneConsent} /><span>Permitir micrófono cuando exista la función</span></label>
      <button class="primary" onclick={save} disabled={saving}>{saving ? 'Guardando…' : 'Guardar ajustes'}</button>
      {#if message}<p class="form-message" aria-live="polite">{message}</p>{/if}
    </article>
    <article class="panel-card">
      <span class="card-title">Caché regenerable</span><strong class="big-value small">{cache.entries} entradas</strong><p>Puede borrarse sin perder datos importantes.</p>
      <button class="secondary" onclick={clearCache}>Limpiar caché</button>
    </article>
  </div>
</section>
