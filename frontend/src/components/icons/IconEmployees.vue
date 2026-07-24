<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="9" cy="9" r="3" stroke="currentColor" stroke-width="1.6" />
    <path d="M4 19c1.5-3 3.5-4.5 5-4.5S12.5 16 14 19" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
    <path d="M15 8h5M15 12h5M15 16h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
  </svg>
</template>
