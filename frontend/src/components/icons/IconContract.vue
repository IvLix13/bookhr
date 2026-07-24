<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M6 8h12v10H6z" stroke="currentColor" stroke-width="1.6" />
    <path d="M9 8V6h6v2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
  </svg>
</template>
