<script setup lang="ts">
withDefaults(
  defineProps<{ size?: number; viewBox?: string }>(),
  { size: 22, viewBox: '0 0 16 16' },
)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    :viewBox="viewBox"
    fill="currentColor"
    aria-hidden="true"
    class="icon"
  >
    <slot />
  </svg>
</template>
