<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import { bytesLabel, onboardingStep } from '../lib/onboarding';
  import { modelErrorCode, modelErrorMessage } from '../lib/modelErrors';
  import type { OnboardingStatus } from '../types';

  export let onReady: () => Promise<void> | void;

  let state: OnboardingStatus = {
    runtimeReady: false,
    bridgeReady: false,
    extensionDetected: false,
    modelState: 'notInstalled',
    downloadedBytes: 0,
    totalBytes: null,
    bootstrapState: 'unknown',
    errorCode: null,
    errorMessage: null
  };
  let installing = false;
  let repairing = false;
  let errorCode = '';
  let errorMessage = '';
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let completed = false;

  async function refresh() {
    state = await desktopApi.getOnboardingStatus();
    if (state.runtimeReady && state.modelState === 'ready' && !completed) {
      completed = true;
      stopPolling();
      await onReady();
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => refresh().catch(() => undefined), 1000);
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function prepareModel() {
    errorCode = '';
    errorMessage = '';
    await refresh();
    if (!state.runtimeReady || state.bootstrapState === 'failed' || state.modelState === 'ready') return;

    installing = true;
    startPolling();
    try {
      await desktopApi.installModel('business-qwen');
      await refresh();
    } catch (error) {
      errorCode = modelErrorCode(error);
      errorMessage = modelErrorMessage(error);
      await refresh().catch(() => undefined);
    } finally {
      installing = false;
      stopPolling();
    }
  }

  async function repair() {
    repairing = true;
    errorCode = '';
    errorMessage = '';
    try {
      await desktopApi.repairInstallation();
      await refresh();
      if (state.runtimeReady && state.bootstrapState !== 'failed' && state.modelState !== 'ready') {
        await prepareModel();
      }
    } catch (error) {
      errorCode = 'REPAIR_FAILED';
      const candidate = error && typeof error === 'object' && 'message' in error ? String((error as { message?: unknown }).message || '') : '';
      errorMessage = candidate || 'No se pudo reparar la instalación automáticamente. Ejecuta nuevamente el instalador si el problema continúa.';
    } finally {
      repairing = false;
    }
  }

  async function retry() {
    await prepareModel();
  }

  onMount(() => {
    prepareModel().catch((error) => {
      errorCode = 'MODEL_RUNTIME_ERROR';
      errorMessage = modelErrorMessage(error);
      installing = false;
      stopPolling();
    });
  });
  onDestroy(stopPolling);

  $: step = onboardingStep(state);
</script>

<section class="onboarding-shell" aria-live="polite">
  <div class="onboarding-card">
    <div class="onboarding-brand">
      <div class="onboarding-mark">MV</div>
      <div>
        <p class="eyebrow">Primera preparación</p>
        <h1>MilyVoiceTraductor se configura solo</h1>
        <p>Runtime, motor y sincronización local ya vienen con la aplicación. Solo descargamos una vez los modelos de IA.</p>
      </div>
    </div>

    <div class="onboarding-steps">
      <article class:done={state.runtimeReady} class:error={!state.runtimeReady && state.bootstrapState === 'failed'}>
        <span class="step-index">1</span>
        <div><strong>Runtime privado</strong><small>{state.runtimeReady ? 'Python y dependencias listos' : repairing ? 'Reparando componentes incluidos…' : 'Verificando componentes incluidos…'}</small></div>
        <b>{state.runtimeReady ? '✓' : step === 'runtime' && state.bootstrapState === 'failed' ? '!' : '…'}</b>
      </article>
      <article class:done={state.bridgeReady}>
        <span class="step-index">2</span>
        <div><strong>Enlace con Chromium</strong><small>{state.bridgeReady ? 'Native Messaging instalado' : 'Preparando bridge local…'}</small></div>
        <b>{state.bridgeReady ? '✓' : '…'}</b>
      </article>
      <article class:done={state.modelState === 'ready'} class:active={step === 'model'}>
        <span class="step-index">3</span>
        <div>
          <strong>Modelo Business Qwen</strong>
          <small>{state.modelState === 'ready' ? 'Modelo verificado y activo' : installing ? `Descargando · ${bytesLabel(state.downloadedBytes)} guardados` : 'Pendiente de preparación'}</small>
        </div>
        <b>{state.modelState === 'ready' ? '✓' : installing ? '↓' : '…'}</b>
      </article>
      <article class:done={state.extensionDetected}>
        <span class="step-index">4</span>
        <div><strong>Extensión del navegador</strong><small>{state.extensionDetected ? 'Extensión reconocida automáticamente' : 'Al abrir la extensión se reconocerá sin token ni puerto'}</small></div>
        <b>{state.extensionDetected ? '✓' : '○'}</b>
      </article>
    </div>

    {#if installing}
      <div class="download-progress" aria-label="Descargando modelos"><span></span></div>
      <p class="onboarding-note">Puedes dejar esta ventana abierta. Si Internet se corta, Reintentar continuará usando los archivos válidos ya descargados.</p>
    {/if}

    {#if state.bootstrapState === 'failed' || !state.runtimeReady}
      <div class="onboarding-error" role="alert">
        <strong>{state.errorCode || 'RUNTIME_NOT_READY'}</strong>
        <span>{state.errorMessage || 'El runtime local necesita reparación antes de descargar modelos.'}</span>
        <button class="primary" onclick={repair} disabled={repairing || installing}>{repairing ? 'Reparando…' : 'Reparar instalación'}</button>
      </div>
    {:else if errorMessage}
      <div class="onboarding-error" role="alert">
        <strong>{errorCode}</strong>
        <span>{errorMessage}</span>
        <button class="primary" onclick={retry} disabled={installing || repairing}>Reintentar</button>
      </div>
    {/if}

    <footer class="onboarding-footer">
      <span>🔒 Audio y credenciales permanecen en este equipo.</span>
      {#if !installing && !repairing && state.runtimeReady && state.modelState !== 'ready' && !errorMessage}
        <button class="primary" onclick={retry}>Preparar ahora</button>
      {/if}
    </footer>
  </div>
</section>

<style>
  .onboarding-shell{min-height:100vh;display:grid;place-items:center;padding:32px;background:radial-gradient(circle at 12% 15%,rgba(0,168,120,.12),transparent 28%),radial-gradient(circle at 88% 18%,rgba(23,105,224,.12),transparent 30%),#f7f4ea;color:#10243e}
  .onboarding-card{width:min(820px,100%);background:rgba(255,255,255,.94);border:1px solid #dce6e8;border-radius:26px;padding:32px;box-shadow:0 22px 70px rgba(16,36,62,.12)}
  .onboarding-brand{display:flex;gap:18px;align-items:flex-start;margin-bottom:28px}.onboarding-brand h1{margin:4px 0 8px;font-size:30px;letter-spacing:-.03em}.onboarding-brand p{margin:0;color:#58708f;line-height:1.55}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:800;color:#087f61!important}.onboarding-mark{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;flex:0 0 auto;background:linear-gradient(135deg,#00a878,#1769e0);color:white;font-weight:900;box-shadow:0 10px 25px rgba(23,105,224,.18)}
  .onboarding-steps{display:grid;gap:10px}.onboarding-steps article{display:grid;grid-template-columns:40px 1fr 28px;gap:12px;align-items:center;padding:15px 16px;border:1px solid #dde5ea;border-radius:15px;background:#fbfcfa;transition:.2s}.onboarding-steps article.done{border-color:rgba(0,168,120,.32);background:rgba(0,168,120,.055)}.onboarding-steps article.active{border-color:rgba(23,105,224,.35);background:rgba(23,105,224,.055)}.onboarding-steps article.error{border-color:#e6aaaa;background:#fff4f4}.step-index{width:32px;height:32px;border-radius:10px;background:#eaf0f3;display:grid;place-items:center;font-weight:800}.done .step-index{background:#dff6ed;color:#087f61}.onboarding-steps strong,.onboarding-steps small{display:block}.onboarding-steps small{margin-top:3px;color:#62768b}.onboarding-steps b{font-size:20px;text-align:center;color:#1769e0}.done b{color:#00a878}
  .download-progress{height:8px;background:#e9eef0;border-radius:999px;overflow:hidden;margin-top:20px}.download-progress span{display:block;width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#00a878,#1769e0);animation:loading 1.35s ease-in-out infinite alternate}.onboarding-note{font-size:12px;color:#62768b;line-height:1.5}.onboarding-error{margin-top:18px;padding:14px 16px;border:1px solid #efc1c1;border-radius:14px;background:#fff4f4;color:#8e2525;display:grid;gap:7px}.onboarding-error strong{font-size:12px;letter-spacing:.04em}.onboarding-error .primary{justify-self:start;margin-top:4px}.onboarding-footer{display:flex;gap:16px;justify-content:space-between;align-items:center;margin-top:22px;color:#62768b;font-size:12px}.primary{border:0;border-radius:12px;padding:11px 16px;background:linear-gradient(135deg,#00a878,#1769e0);color:#fff;font-weight:800;cursor:pointer}.primary:disabled{opacity:.55;cursor:wait}@keyframes loading{from{transform:translateX(-35%)}to{transform:translateX(190%)}}
</style>
