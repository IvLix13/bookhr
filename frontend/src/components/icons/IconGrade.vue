<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M4 18l4-4 3 3 5-6 4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
    <path d="M4 20h16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
  </svg>
</template>
