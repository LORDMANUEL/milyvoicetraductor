<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import LiveTranslation from './LiveTranslation.svelte';
  import {
    installTargetAwareSpeechSynthesis,
    setTier1TargetLanguage,
    type Tier1TargetLanguage
  } from '../lib/tier1-route';
  import type { AppConfig } from '../types';

  export let config: AppConfig;
  export let onChanged: () => void;

  let targetLanguage: Tier1TargetLanguage = 'es';
  let restoreSpeech = () => undefined;

  function applyTarget() {
    setTier1TargetLanguage(targetLanguage);
  }

  onMount(() => {
    applyTarget();
    restoreSpeech = installTargetAwareSpeechSynthesis();
  });

  onDestroy(() => restoreSpeech());
</script>

<div class:outbound={targetLanguage !== 'es'} class="tier1-live">
  <section class="tier1-route-bar" aria-label="Ruta de traducción Tier 1">
    <div>
      <p class="eyebrow">RUTA DE SESIÓN · TIER 1</p>
      <strong>{targetLanguage === 'es' ? 'Inglés / Chino → Español' : targetLanguage === 'en' ? 'Español → Inglés' : 'Español → Chino'}</strong>
      <small>
        {targetLanguage === 'es'
          ? 'Los perfiles Lite siguen disponibles para recepción rápida.'
          : 'Salida bidireccional 2.1 mediante el pack Quality Whisper Small + M2M100.'}
      </small>
    </div>
    {#if targetLanguage !== 'es'}
      <div class="source-lock"><span>ORIGEN</span><b>Español</b><small>Fijado para esta ruta</small></div>
    {/if}
    <label>Destino
      <select bind:value={targetLanguage} on:change={applyTarget}>
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
  :global(.tier1-live.outbound .controls-panel .control-grid > label:first-child) { display: none; }
  @media (max-width: 900px) {
    .tier1-route-bar { grid-template-columns: 1fr; align-items: stretch; }
    .tier1-route-bar select { width: 100%; }
  }
</style>
