<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 4l2.4 4.8 5.3.8-3.8 3.7 1 5.3L12 16.8 7.1 18.6l1-5.3L4.3 9.6l5.3-.8L12 4z" stroke="currentColor" stroke-width="1.4" />
  </svg>
</template>
