<script setup lang="ts">
defineProps<{
  name: string
  label: string
  active?: boolean
}>()
</script>

<template>
  <RouterLink
    :to="{ name }"
    class="nav-item"
    :class="{ active }"
    :title="label"
  >
    <slot />
    <span class="nav-label">{{ label }}</span>
  </RouterLink>
</template>

<style scoped>
.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 0.85rem 0.35rem;
  border-radius: 12px;
  color: var(--muted);
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.nav-item:hover,
.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  transform: translateY(-1px);
}

.nav-label {
  font-size: 0.68rem;
  text-align: center;
  line-height: 1.1;
}
</style>
