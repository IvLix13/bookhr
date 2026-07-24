<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M4 6h16v12H4z" stroke="currentColor" stroke-width="1.6" />
    <path d="M4 10h16M8 6V4M16 6V4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
  </svg>
</template>
