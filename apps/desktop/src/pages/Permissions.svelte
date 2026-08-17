<script lang="ts">import type { AppStatus } from '../types'; export let status: AppStatus;</script>
<section class="page-stack">
  <header class="page-header"><div><p class="eyebrow">Menor privilegio</p><h1>Permisos</h1><p>Separación entre escritorio y extensión para reducir superficie de acceso.</p></div></header>
  <article class="panel-card">
    <div class="permission-row"><div><strong>Archivos de aplicación</strong><small>Configuración, caché, logs, modelos y sesiones propias.</small></div><span class="pill ok">Local</span></div>
    <div class="permission-row"><div><strong>Micrófono</strong><small>No se captura por defecto. La primera versión usa audio de pestaña.</small></div><span class="pill muted">Opcional</span></div>
    <div class="permission-row"><div><strong>Audio de pestaña</strong><small>La extensión Chromium lo solicita solo después de pulsar Iniciar.</small></div><span class="pill" class:ok={status.extensionConnected}>{status.extensionConnected ? 'Conectada' : 'No conectada'}</span></div>
    <div class="permission-row"><div><strong>Red externa</strong><small>Solo se usa al descargar modelos o actualizaciones por acción explícita.</small></div><span class="pill muted">No usada al traducir</span></div>
    <div class="permission-row"><div><strong>Telemetría</strong><small>No existe servicio de analítica ni envío de contenido.</small></div><span class="pill ok">Desactivada</span></div>
  </article>
</section>
