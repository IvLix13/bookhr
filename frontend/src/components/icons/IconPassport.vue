<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="5" y="4" width="14" height="16" rx="2" stroke="currentColor" stroke-width="1.6" />
    <circle cx="12" cy="11" r="3" stroke="currentColor" stroke-width="1.6" />
  </svg>
</template>
