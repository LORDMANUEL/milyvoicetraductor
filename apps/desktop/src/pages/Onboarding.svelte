<script lang="ts">
  import { onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import type { OnboardingStatus } from '../types';

  export let onReady: () => Promise<void> | void;

  let state: OnboardingStatus = {
    runtimeReady: false,
    bridgeReady: false,
    extensionDetected: false,
    modelState: 'notInstalled',
    downloadedBytes: 0,
    totalBytes: null,
    modelPhase: 'idle',
    modelMessage: null,
    bootstrapState: 'unknown',
    errorCode: null,
    errorMessage: null
  };
  let repairing = false;
  let errorCode = '';
  let errorMessage = '';
  let completed = false;

  async function refresh() {
    state = await desktopApi.getOnboardingStatus();
    if (state.runtimeReady && state.bootstrapState !== 'failed' && !completed) {
      completed = true;
      await onReady();
    }
  }

  async function repair() {
    repairing = true;
    errorCode = '';
    errorMessage = '';
    try {
      await desktopApi.repairInstallation();
      await refresh();
    } catch (error) {
      errorCode = 'REPAIR_FAILED';
      const candidate = error && typeof error === 'object' && 'message' in error
        ? String((error as { message?: unknown }).message || '')
        : '';
      errorMessage = candidate || 'No se pudo reparar la instalación automáticamente. Ejecuta nuevamente el instalador si el problema continúa.';
    } finally {
      repairing = false;
    }
  }

  onMount(() => {
    refresh().catch((error) => {
      errorCode = 'BOOTSTRAP_STATUS_ERROR';
      errorMessage = error && typeof error === 'object' && 'message' in error
        ? String((error as { message?: unknown }).message || '')
        : 'No se pudo leer el estado del runtime local.';
    });
  });
</script>

<section class="onboarding-shell" aria-live="polite">
  <div class="onboarding-card">
    <div class="onboarding-brand">
      <div class="onboarding-mark">MV</div>
      <div>
        <p class="eyebrow">Preparación local</p>
        <h1>Preparando MilyVoiceTraductor</h1>
        <p>El instalador prepara el runtime privado, el motor y Native Messaging. Los modelos se eligen y descargan después, dentro de Mily Engine Hub.</p>
      </div>
    </div>

    <div class="onboarding-steps">
      <article class:done={state.runtimeReady} class:error={!state.runtimeReady && state.bootstrapState === 'failed'}>
        <span class="step-index">1</span>
        <div><strong>Runtime privado</strong><small>{state.runtimeReady ? 'Python y dependencias incluidos listos' : repairing ? 'Reparando componentes incluidos…' : 'Verificando componentes incluidos…'}</small></div>
        <b>{state.runtimeReady ? '✓' : state.bootstrapState === 'failed' ? '!' : '…'}</b>
      </article>
      <article class:done={state.bridgeReady}>
        <span class="step-index">2</span>
        <div><strong>Enlace con Chromium</strong><small>{state.bridgeReady ? 'Native Messaging instalado' : 'Preparando bridge local…'}</small></div>
        <b>{state.bridgeReady ? '✓' : '…'}</b>
      </article>
      <article>
        <span class="step-index">3</span>
        <div><strong>Modelos compatibles</strong><small>Se mostrarán dentro de Mily Engine Hub según CPU, RAM y aceleradores disponibles.</small></div>
        <b>→</b>
      </article>
      <article class:done={state.extensionDetected}>
        <span class="step-index">4</span>
        <div><strong>Extensión del navegador</strong><small>{state.extensionDetected ? 'Extensión reconocida automáticamente' : 'Se reconocerá automáticamente al abrirla'}</small></div>
        <b>{state.extensionDetected ? '✓' : '○'}</b>
      </article>
    </div>

    {#if state.bootstrapState === 'failed' || !state.runtimeReady}
      <div class="onboarding-error" role="alert">
        <strong>{state.errorCode || errorCode || 'RUNTIME_NOT_READY'}</strong>
        <span>{state.errorMessage || errorMessage || 'El runtime local necesita reparación antes de abrir MilyVoiceTraductor.'}</span>
        <button class="primary" onclick={repair} disabled={repairing}>{repairing ? 'Reparando…' : 'Reparar instalación'}</button>
      </div>
    {:else if errorMessage}
      <div class="onboarding-error" role="alert">
        <strong>{errorCode}</strong>
        <span>{errorMessage}</span>
        <button class="primary" onclick={refresh}>Reintentar comprobación</button>
      </div>
    {/if}

    <footer class="onboarding-footer">
      <span>🔒 Audio y credenciales permanecen en este equipo.</span>
      <span>Los modelos no se descargan durante la instalación.</span>
    </footer>
  </div>
</section>

<style>
  .onboarding-shell{min-height:100vh;display:grid;place-items:center;padding:32px;background:radial-gradient(circle at 12% 15%,rgba(0,168,120,.12),transparent 28%),radial-gradient(circle at 88% 18%,rgba(23,105,224,.12),transparent 30%),#f7f4ea;color:#10243e}
  .onboarding-card{width:min(820px,100%);background:rgba(255,255,255,.94);border:1px solid #dce6e8;border-radius:26px;padding:32px;box-shadow:0 22px 70px rgba(16,36,62,.12)}
  .onboarding-brand{display:flex;gap:18px;align-items:flex-start;margin-bottom:28px}.onboarding-brand h1{margin:4px 0 8px;font-size:30px;letter-spacing:-.03em}.onboarding-brand p{margin:0;color:#58708f;line-height:1.55}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:800;color:#087f61!important}.onboarding-mark{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;flex:0 0 auto;background:linear-gradient(135deg,#00a878,#1769e0);color:white;font-weight:900;box-shadow:0 10px 25px rgba(23,105,224,.18)}
  .onboarding-steps{display:grid;gap:10px}.onboarding-steps article{display:grid;grid-template-columns:40px 1fr 28px;gap:12px;align-items:center;padding:15px 16px;border:1px solid #dde5ea;border-radius:15px;background:#fbfcfa}.onboarding-steps article.done{border-color:rgba(0,168,120,.32);background:rgba(0,168,120,.055)}.onboarding-steps article.error{border-color:#e6aaaa;background:#fff4f4}.step-index{width:32px;height:32px;border-radius:10px;background:#eaf0f3;display:grid;place-items:center;font-weight:800}.done .step-index{background:#dff6ed;color:#087f61}.onboarding-steps strong,.onboarding-steps small{display:block}.onboarding-steps small{margin-top:3px;color:#62768b}.onboarding-steps b{font-size:20px;text-align:center;color:#1769e0}.done b{color:#00a878}
  .onboarding-error{margin-top:18px;padding:14px 16px;border:1px solid #efc1c1;border-radius:14px;background:#fff4f4;color:#8e2525;display:grid;gap:7px}.onboarding-error strong{font-size:12px;letter-spacing:.04em}.onboarding-error .primary{justify-self:start;margin-top:4px}.onboarding-footer{display:flex;gap:16px;justify-content:space-between;align-items:center;margin-top:22px;color:#62768b;font-size:12px}.primary{border:0;border-radius:12px;padding:11px 16px;background:linear-gradient(135deg,#00a878,#1769e0);color:#fff;font-weight:800;cursor:pointer}.primary:disabled{opacity:.55;cursor:wait}
</style>