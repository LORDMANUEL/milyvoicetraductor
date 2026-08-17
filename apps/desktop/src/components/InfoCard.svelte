<script lang="ts">
  export let title: string;
  export let value: string;
  export let detail = '';
  export let icon = '•';
</script>

<article class="info-card">
  <div class="info-icon" aria-hidden="true">{icon}</div>
  <div>
    <span class="card-title">{title}</span>
    <strong>{value}</strong>
    {#if detail}<small>{detail}</small>{/if}
  </div>
</article>
