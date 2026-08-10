<script setup lang="ts">
import IconBase from './IconBase.vue'

defineProps<{ size?: number }>()
</script>

<template>
  <IconBase :size="size">
    <path
      d="M2 8h12v1a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V8zm2-2a1 1 0 0 1 1-1h1V4a1 1 0 1 1 2 0v1h2V4a1 1 0 1 1 2 0v1h1a1 1 0 0 1 1 1v1H4V6zm1 5a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2H5z"
    />
  </IconBase>
</template>
