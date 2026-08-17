<script lang="ts">
  export let label: string;
  export let tone: 'ok' | 'muted' | 'warning' | 'danger' = 'muted';
</script>

<span class="status-badge {tone}"><span class="status-dot"></span>{label}</span>
