<script lang="ts">
  import type { AppConfig, CacheStatus } from '../types';
  export let config: AppConfig;
  export let cache: CacheStatus;
  export let onSave: (value: AppConfig) => Promise<void>;
  export let onClearCache: () => Promise<void>;
  let draft: AppConfig = { ...config };
  let message = '';
  let saving = false;
  async function save() { saving = true; message = ''; try { await onSave({ ...draft }); message = 'Ajustes guardados y sincronizados con el motor.'; } catch { message = 'No se pudieron guardar los ajustes.'; } finally { saving = false; } }
  async function clearCache() { await onClearCache(); message = 'Caché regenerable limpiada.'; }
</script>
<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Configuración local</p><h1>Ajustes</h1><p>Privacidad, rendimiento y modelos con defaults conservadores.</p></div></header>
  <div class="two-columns">
    <article class="panel-card form-card">
      <label>Idioma de origen<select bind:value={draft.sourceLanguage}><option value="auto">Automático</option><option value="en">Inglés</option><option value="zh">Chino</option></select></label>
      <label>Idioma de destino<select bind:value={draft.targetLanguage}><option value="es">Español</option></select></label>
      <label>Perfil de cómputo<select bind:value={draft.computeProfile}><option value="auto">Automático (recomendado)</option><option value="cpu">Solo CPU</option><option value="gpu">Forzar GPU</option></select></label>
      <label>Pack preferido<select bind:value={draft.activeModelPack}><option value="realtime-m2m100">Tiempo Real INT8 (recomendado)</option><option value="business-qwen">Business Qwen</option><option value="lite-nllb">Lite NLLB</option></select></label>
      <label>Tema<select bind:value={draft.theme}><option value="system">Sistema</option><option value="light">Claro</option><option value="dark">Oscuro</option></select></label>
      <label>Nivel de log<select bind:value={draft.logLevel}><option value="error">Error</option><option value="warn">Advertencia</option><option value="info">Información</option><option value="debug">Depuración</option></select></label>
      <label>Límite de caché (MB)<input type="number" min="64" max="4096" step="64" bind:value={draft.cacheLimitMb}></label>
      <label class="switch-row"><input type="checkbox" bind:checked={draft.autoStartEngine}><span>Iniciar motor al abrir la aplicación</span></label>
      <label class="switch-row"><input type="checkbox" bind:checked={draft.persistTranscripts}><span>Guardar transcripciones localmente</span></label>
      <label class="switch-row"><input type="checkbox" bind:checked={draft.showOriginalSubtitle}><span>Mostrar texto original en subtítulos</span></label>
      <label class="switch-row"><input type="checkbox" bind:checked={draft.microphoneConsent}><span>Permitir micrófono cuando se habilite esa captura</span></label>
      <button class="primary" onclick={save} disabled={saving}>{saving ? 'Guardando…' : 'Guardar ajustes'}</button>
      {#if message}<p class="form-message" aria-live="polite">{message}</p>{/if}
    </article>
    <article class="panel-card"><span class="card-title">Caché regenerable</span><strong class="big-value small">{cache.entries} entradas</strong><p>Los modelos y transcripciones no se borran con esta acción.</p><button class="secondary" onclick={clearCache}>Limpiar caché</button><hr><h3>Conexión automática</h3><p>El puerto y las credenciales del motor se administran internamente. La extensión se enlaza mediante Native Messaging sin copiar tokens ni configurar puertos.</p><hr><h3>Privacidad</h3><p>El audio no se guarda. La persistencia de texto está desactivada hasta que la habilites.</p></article>
  </div>
</section>
