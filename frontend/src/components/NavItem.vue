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
    :aria-current="active ? 'page' : undefined"
  >
    <slot />
    <span v-if="expanded" class="nav-label">{{ label }}</span>
  </RouterLink>
</template>

<style scoped>
.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.85rem 0.35rem;
  border-radius: 12px;
  color: var(--muted);
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 50%;
  width: 3px;
  height: 60%;
  border-radius: 3px;
  background: var(--accent);
  transform: translateY(-50%) scaleY(0);
  transform-origin: center;
  transition: transform var(--transition-slow) var(--ease-out);
}

.nav-item.active::before {
  transform: translateY(-50%) scaleY(1);
}

.nav-item :deep(.icon) {
  transition: transform var(--transition);
}

.nav-item:hover :deep(.icon),
.nav-item.active :deep(.icon) {
  transform: scale(1.12);
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
  animation: nav-label-in var(--transition-slow) var(--ease-out) both;
}

@keyframes nav-label-in {
  from {
    opacity: 0;
    transform: translateX(-6px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
