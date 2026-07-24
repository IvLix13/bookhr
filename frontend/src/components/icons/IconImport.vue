<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 3v18M5 8h14M5 16h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
    <rect x="4" y="4" width="16" height="16" rx="3" stroke="currentColor" stroke-width="1.6" />
  </svg>
</template>
