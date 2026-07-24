<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
    <path d="M12 15v6M9 18h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
    <path d="M4 8.5A8 8 0 0 1 12 4a8 8 0 0 1 8 4.5" stroke="currentColor" stroke-width="1.6" />
  </svg>
</template>
