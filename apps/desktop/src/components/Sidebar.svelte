<script lang="ts">
  import { navigationItems, type PageId } from '../lib/navigation';

  export let activePage: PageId;
  export let onNavigate: (page: PageId) => void;
</script>

<aside class="sidebar" aria-label="Navegación principal">
  <div class="brand">
    <img src="/logo.svg" alt="Zebra con audífonos, logo de MilyVoiceTraductor" />
    <div>
      <strong><span>Mily</span><em>Voice</em>Traductor</strong>
      <small>IA local · Fase 1</small>
    </div>
  </div>

  <nav>
    {#each navigationItems as item}
      <button
        type="button"
        class:active={activePage === item.id}
        aria-current={activePage === item.id ? 'page' : undefined}
        onclick={() => onNavigate(item.id)}
      >
        <span class="nav-icon" aria-hidden="true">{item.icon}</span>
        <span>{item.label}</span>
      </button>
    {/each}
  </nav>

  <div class="privacy-note">
    <span class="dot"></span>
    <div>
      <strong>Privacidad local</strong>
      <small>Sin telemetría en Fase 1</small>
    </div>
  </div>
</aside>
