<script lang="ts">import type { SystemSnapshot } from '../types'; export let system: SystemSnapshot;</script>
<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Hardware</p><h1>Dispositivos</h1><p>Diagnóstico ligero; no mantiene polling en segundo plano.</p></div></header>
  <article class="panel-card">
    <dl class="details-list">
      <div><dt>CPU</dt><dd>{system.cpuBrand}</dd></div>
      <div><dt>Hilos lógicos</dt><dd>{system.logicalCpus || 'N/D'}</dd></div>
      <div><dt>Memoria</dt><dd>{system.totalMemoryMb ? `${system.totalMemoryMb} MB` : 'N/D'}</dd></div>
      <div><dt>Aceleración GPU</dt><dd>{system.gpu ?? 'Opcional; no detectada'}</dd></div>
    </dl>
  </article>
</section>
