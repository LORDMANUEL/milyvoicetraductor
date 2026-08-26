<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import LiveTranslation from './LiveTranslation.svelte';
  import { desktopApi } from '../lib/api';
  import {
    installTargetAwareSpeechSynthesis,
    setTier1TargetLanguage,
    type Tier1TargetLanguage
  } from '../lib/tier1-route';
  import type { AppConfig, ModelPackInfo } from '../types';

  export let config: AppConfig;
  export let onChanged: () => void;

  interface RoutePlan {
    route: 'en-es' | 'es-en' | 'es-zh';
    preferredPack: 'lite-en-es' | 'lite-es-en' | 'lite-es-zh';
    sourceLabel: string;
    targetLabel: string;
  }

  const ROUTES: Record<Tier1TargetLanguage, RoutePlan> = {
    es: { route: 'en-es', preferredPack: 'lite-en-es', sourceLabel: 'Inglés / Chino', targetLabel: 'Español' },
    en: { route: 'es-en', preferredPack: 'lite-es-en', sourceLabel: 'Español', targetLabel: 'Inglés' },
    zh: { route: 'es-zh', preferredPack: 'lite-es-zh', sourceLabel: 'Español', targetLabel: 'Chino mandarín' }
  };

  let targetLanguage: Tier1TargetLanguage = 'es';
  let activeTargetLanguage: Tier1TargetLanguage = 'es';
  let preparing = false;
  let routeError = '';
  let routeMessage = 'Ruta de recepción lista.';
  let restoreSpeech = () => undefined;

  function packFor(catalog: ModelPackInfo[], id: string): ModelPackInfo | undefined {
    return catalog.find((pack) => pack.id === id);
  }

  async function ensurePreferredPack(plan: RoutePlan): Promise<void> {
    let catalog = await desktopApi.getModelCatalog();
    let preferred = packFor(catalog, plan.preferredPack);
    if (!preferred) {
      throw new Error(`El catálogo local no contiene ${plan.preferredPack}.`);
    }
    if (!preferred.resourceAllowed) {
      throw new Error('El pack recomendado excede el presupuesto de recursos de este equipo.');
    }
    if (!preferred.installed) {
      routeMessage = `Descargando ${plan.sourceLabel} → ${plan.targetLabel}…`;
      await desktopApi.installModel(plan.preferredPack);
      catalog = await desktopApi.getModelCatalog();
      preferred = packFor(catalog, plan.preferredPack);
      if (!preferred?.installed) {
        throw new Error('La descarga terminó sin dejar el pack disponible.');
      }
      if (!preferred.resourceAllowed) {
        throw new Error('El pack descargado excede el presupuesto de recursos medido.');
      }
    }
  }

  async function prepareTarget(): Promise<void> {
    if (preparing) return;
    const requested = targetLanguage;
    const plan = ROUTES[requested];
    preparing = true;
    routeError = '';
    routeMessage = `Preparando ${plan.sourceLabel} → ${plan.targetLabel}…`;
    try {
      await ensurePreferredPack(plan);
      routeMessage = 'Midiendo motores instalados y eligiendo la ruta más segura…';
      const selection = await desktopApi.optimizeModels(plan.route, false);
      if (!selection?.selected) {
        throw new Error('Engine Hub no devolvió un motor compatible.');
      }
      setTier1TargetLanguage(requested);
      activeTargetLanguage = requested;
      routeMessage = `${plan.sourceLabel} → ${plan.targetLabel} listo · ${selection.selected} · ${selection.backend}.`;
      onChanged?.();
    } catch (caught) {
      targetLanguage = activeTargetLanguage;
      setTier1TargetLanguage(activeTargetLanguage);
      routeError = caught instanceof Error ? caught.message : 'No se pudo preparar esta ruta.';
      routeMessage = 'Se conservó la última ruta funcional.';
    } finally {
      preparing = false;
    }
  }

  onMount(() => {
    targetLanguage = config.targetLanguage === 'es' ? 'es' : 'es';
    activeTargetLanguage = targetLanguage;
    setTier1TargetLanguage(targetLanguage);
    restoreSpeech = installTargetAwareSpeechSynthesis();
  });

  onDestroy(() => restoreSpeech());
</script>

<div class:outbound={activeTargetLanguage !== 'es'} class:preparing class="tier1-live">
  <section class="tier1-route-bar" aria-label="Ruta de traducción Tier 1">
    <div>
      <p class="eyebrow">RUTA DE SESIÓN · TIER 1</p>
      <strong>{ROUTES[activeTargetLanguage].sourceLabel} → {ROUTES[activeTargetLanguage].targetLabel}</strong>
      <small>
        {activeTargetLanguage === 'es'
          ? 'Engine Hub conserva los perfiles Lite de recepción y selecciona el más seguro.'
          : 'Salida bidireccional 2.1 con pack Lite local, benchmark y límite total de 2 GB.'}
      </small>
      <span class:error={Boolean(routeError)} class="route-status">{routeError || routeMessage}</span>
    </div>
    {#if activeTargetLanguage !== 'es'}
      <div class="source-lock"><span>ORIGEN</span><b>Español</b><small>Fijado para esta ruta</small></div>
    {/if}
    <label>Destino
      <select bind:value={targetLanguage} on:change={prepareTarget} disabled={preparing}>
        <option value="es">Español</option>
        <option value="en">Inglés</option>
        <option value="zh">Chino mandarín</option>
      </select>
    </label>
  </section>

  <LiveTranslation />
</div>

<style>
  .tier1-route-bar {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 14px;
    align-items: end;
    padding: 14px 16px;
    margin-bottom: 14px;
    border: 1px solid var(--mily-border);
    border-radius: 16px;
    background: #f7fbff;
  }
  .tier1-route-bar > div { display: grid; gap: 3px; }
  .tier1-route-bar strong { color: var(--mily-navy); font-size: 15px; }
  .tier1-route-bar small { color: var(--mily-muted); }
  .eyebrow { margin: 0; font-size: 10px; font-weight: 900; letter-spacing: .08em; color: var(--mily-emerald-dark); }
  .tier1-route-bar label { display: grid; gap: 5px; color: var(--mily-muted); font-size: 12px; font-weight: 700; }
  .tier1-route-bar select { min-width: 160px; border: 1px solid var(--mily-border); border-radius: 10px; background: #fff; padding: 9px; color: var(--mily-navy); }
  .source-lock { padding: 8px 12px; border-radius: 10px; background: #eef8f4; }
  .source-lock span { font-size: 9px; font-weight: 900; color: var(--mily-emerald-dark); }
  .source-lock b { color: var(--mily-navy); }
  .route-status { margin-top: 4px; font-size: 11px; color: var(--mily-emerald-dark); }
  .route-status.error { color: #a32626; }
  :global(.tier1-live.outbound .controls-panel .control-grid > label:first-child) { display: none; }
  :global(.tier1-live.preparing .main-action) { pointer-events: none; opacity: .55; }
  @media (max-width: 900px) {
    .tier1-route-bar { grid-template-columns: 1fr; align-items: stretch; }
    .tier1-route-bar select { width: 100%; }
  }
</style>
