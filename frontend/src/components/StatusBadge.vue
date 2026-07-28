<script setup lang="ts">
import type { BadgeVariant } from '@/utils/statuses'

defineProps<{
  label: string
  variant?: BadgeVariant
}>()
</script>

<template>
  <span class="badge" :class="variant">{{ label }}</span>
</template>
