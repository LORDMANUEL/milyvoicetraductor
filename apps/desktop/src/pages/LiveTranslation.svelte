<script lang="ts">
  import { onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import { componentStateLabel } from '../lib/status';
  import type { AppConfig, EngineRuntimeStatus, RuntimeLocations } from '../types';

  export let config: AppConfig;
  export let onChanged: () => Promise<void>;

  let engine: EngineRuntimeStatus = { state: 'notInstalled', pid: null, port: config.enginePort, message: '' };
  let token = '';
  let showToken = false;
  let busy = false;
  let message = '';
  let locations: RuntimeLocations = { models: '', sessions: '', extension: '' };

  async function refresh() {
    [engine, locations] = await Promise.all([desktopApi.getEngineStatus(), desktopApi.getRuntimeLocations()]);
  }

  async function start() {
    busy = true; message = '';
    try { engine = await desktopApi.startEngine(); await onChanged(); }
    catch { message = 'No se pudo iniciar el motor. Instala primero el runtime local.'; }
    finally { busy = false; }
  }

  async function stop() {
    busy = true;
    try { engine = await desktopApi.stopEngine(); await onChanged(); }
    catch { message = 'No se pudo detener el motor.'; }
    finally { busy = false; }
  }

  async function revealToken() {
    try { token = await desktopApi.getPairingToken(); showToken = true; }
    catch { message = 'No se pudo generar el token de emparejamiento.'; }
  }

  async function copyToken() {
    if (!token) await revealToken();
    if (token) { await navigator.clipboard.writeText(token); message = 'Token copiado. Pégalo en la extensión.'; }
  }

  onMount(refresh);
</script>

<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Traducción local</p><h1>Traducción en vivo</h1><p>El navegador captura la reunión; el motor procesa todo en este equipo.</p></div></header>
  <div class="two-columns">
    <article class="panel-card">
      <div class="panel-title"><h3>Motor IA</h3><span class="pill" class:ok={engine.state === 'ready'}>{componentStateLabel(engine.state)}</span></div>
      <p>{engine.message || 'Consulta el estado del runtime local.'}</p>
      <dl class="details-list"><div><dt>Puerto</dt><dd>127.0.0.1:{engine.port}</dd></div><div><dt>Perfil</dt><dd>{config.computeProfile.toUpperCase()}</dd></div><div><dt>Modelo</dt><dd>{config.activeModelPack}</dd></div></dl>
      <div class="button-row">
        {#if engine.state === 'ready'}<button class="secondary" onclick={stop} disabled={busy}>Detener motor</button>
        {:else}<button class="primary" onclick={start} disabled={busy}>Iniciar motor</button>{/if}
        <button class="secondary" onclick={refresh}>Actualizar</button>
      </div>
    </article>
    <article class="panel-card">
      <div class="panel-title"><h3>Emparejar extensión</h3><span class="pill muted">Local</span></div>
      <p>El token autoriza únicamente conexiones al motor de esta instalación. No lo publiques.</p>
      <div class="token-box"><code>{showToken ? token : '••••••••••••••••••••••••••••••••'}</code></div>
      <div class="button-row"><button class="primary" onclick={copyToken}>Copiar token</button><button class="secondary" onclick={() => (showToken = !showToken)}>{showToken ? 'Ocultar' : 'Mostrar'}</button></div>
    </article>
  </div>
  <article class="panel-card">
    <h3>Flujo de uso</h3>
    <ol class="steps"><li>Instala un pack desde <strong>Modelos</strong>.</li><li>Inicia el motor local.</li><li>Carga la extensión de Chromium desde la carpeta instalada.</li><li>Pega el token y abre Meet, Teams Web o Zoom Web.</li><li>Pulsa <strong>Iniciar traducción</strong> en la extensión.</li></ol>
    {#if locations.extension}<p class="path-hint">Carpeta esperada de extensión: <code>{locations.extension}</code></p>{/if}
    {#if message}<p class="form-message" aria-live="polite">{message}</p>{/if}
  </article>
</section>
