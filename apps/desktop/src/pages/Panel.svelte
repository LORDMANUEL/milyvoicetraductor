<script lang="ts">
  import InfoCard from '../components/InfoCard.svelte';
  import StatusBadge from '../components/StatusBadge.svelte';
  import { componentStateLabel, formatBytes } from '../lib/status';
  import type { AppStatus, CacheStatus, SystemSnapshot } from '../types';

  export let status: AppStatus;
  export let system: SystemSnapshot;
  export let cache: CacheStatus;
</script>

<section class="page-stack">
  <header class="page-header">
    <div><p class="eyebrow">Fundación local</p><h1>Panel</h1><p>Estado real de MilyVoiceTraductor en este equipo.</p></div>
    <StatusBadge label="Aplicación activa" tone="ok" />
  </header>

  <div class="hero-card">
    <div>
      <span class="hero-kicker">MilyVoiceTraductor {status.version}</span>
      <h2>Preparado para crecer sin exponer tus reuniones.</h2>
      <p>La Fase 1 administra la plataforma local. El motor de voz y los modelos se integrarán como componentes independientes.</p>
    </div>
    <div class="hero-mark" aria-hidden="true">声 → ES</div>
  </div>

  <div class="card-grid">
    <InfoCard title="Motor IA" value={componentStateLabel(status.engine)} detail="Se integrará en Fase 2" icon="AI" />
    <InfoCard title="Modelos" value={`${status.installedModels} instalados`} detail={componentStateLabel(status.models)} icon="M" />
    <InfoCard title="Extensión" value={status.extensionConnected ? 'Conectada' : 'No instalada'} detail="Chromium · Fase 3" icon="↗" />
    <InfoCard title="Caché" value={formatBytes(cache.bytes)} detail={`${cache.entries} entradas · límite ${formatBytes(cache.maxBytes)}`} icon="C" />
  </div>

  <div class="two-columns">
    <article class="panel-card">
      <div class="panel-title"><h3>Equipo</h3><StatusBadge label="CPU compatible" tone="ok" /></div>
      <dl class="details-list">
        <div><dt>Sistema</dt><dd>{system.operatingSystem}</dd></div>
        <div><dt>Arquitectura</dt><dd>{system.architecture}</dd></div>
        <div><dt>Procesador</dt><dd>{system.cpuBrand}</dd></div>
        <div><dt>CPU lógicas</dt><dd>{system.logicalCpus || 'N/D'}</dd></div>
        <div><dt>RAM</dt><dd>{system.totalMemoryMb ? `${system.totalMemoryMb} MB` : 'N/D'}</dd></div>
        <div><dt>GPU</dt><dd>{system.gpu ?? 'No requerida / no detectada'}</dd></div>
      </dl>
    </article>

    <article class="panel-card">
      <div class="panel-title"><h3>Privacidad de Fase 1</h3><StatusBadge label="Local" tone="ok" /></div>
      <ul class="check-list">
        <li><span>✓</span>No se captura audio.</li>
        <li><span>✓</span>No se almacenan transcripciones.</li>
        <li><span>✓</span>No existe telemetría.</li>
        <li><span>✓</span>Logs sanitizados antes de escribirse.</li>
        <li><span>✓</span>La aplicación funciona sin GPU.</li>
      </ul>
    </article>
  </div>
</section>
