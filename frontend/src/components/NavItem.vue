<script setup lang="ts">
defineProps<{
  name: string
  label: string
  active?: boolean
  expanded?: boolean
}>()
</script>

<template>
  <RouterLink
    :to="{ name }"
    class="nav-item"
    :class="{ active, expanded }"
    :title="expanded ? undefined : label"
  >
    <slot />
    <span v-if="expanded" class="nav-label">{{ label }}</span>
  </RouterLink>
</template>

<style scoped>
.nav-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.85rem 0.35rem;
  border-radius: 12px;
  color: var(--muted);
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.nav-item.expanded {
  justify-content: flex-start;
  padding-left: 1.25rem;
  gap: 0.65rem;
}

.nav-item :deep(.icon) {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  display: block;
}

.nav-item:hover,
.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  transform: translateY(-1px);
}

.nav-label {
  font-size: 0.9rem;
  line-height: 1.2;
  white-space: nowrap;
}
</style>
