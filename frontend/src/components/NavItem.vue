<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  name: string
  label: string
  active?: boolean
  expanded?: boolean
  background?: string
  backgroundActive?: string
}>()

const showBackground = computed(() => Boolean(props.expanded && props.active && props.background))

/**
 * The image stays declared for every expanded item so the background can also
 * slide back out when the item stops being the active one.
 */
const navStyle = computed(() => {
  if (!props.expanded || !props.background) return undefined

  return {
    '--nav-item-bg': `url(${props.backgroundActive ?? props.background})`,
  }
})

/**
 * The slide-in animation must only play when the active route changes, never
 * when the sidebar itself expands or collapses. Transitions stay switched off
 * until the layout settled after an `expanded` change.
 */
const animated = ref(false)
let pendingFrames: number[] = []

function cancelPendingFrames() {
  pendingFrames.forEach((handle) => cancelAnimationFrame(handle))
  pendingFrames = []
}

function enableAnimationAfterLayout() {
  cancelPendingFrames()
  void nextTick(() => {
    pendingFrames.push(
      requestAnimationFrame(() => {
        pendingFrames.push(
          requestAnimationFrame(() => {
            animated.value = true
          }),
        )
      }),
    )
  })
}

watch(
  () => props.expanded,
  () => {
    animated.value = false
    enableAnimationAfterLayout()
  },
)

onMounted(enableAnimationAfterLayout)
onBeforeUnmount(cancelPendingFrames)
</script>

<template>
  <RouterLink
    :to="{ name }"
    class="nav-item"
    :class="{ active, expanded, 'has-bg': showBackground, animated }"
    :style="navStyle"
    :title="expanded ? undefined : label"
    :aria-current="active ? 'page' : undefined"
  >
    <span class="nav-bg" aria-hidden="true" />
    <span class="nav-icon">
      <slot />
    </span>
    <span v-if="expanded" class="nav-label">{{ label }}</span>
  </RouterLink>
</template>

<style scoped>
.nav-item {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.85rem 0.35rem;
  border-radius: var(--radius-lg);
  color: var(--muted);
  background-color: transparent;
  transition:
    background-color var(--transition),
    color var(--transition),
    transform var(--transition),
    filter var(--transition);
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 50%;
  width: 3px;
  height: 60%;
  border-radius: var(--radius-xs);
  background: var(--accent);
  transform: translateY(-50%) scaleY(0);
  transform-origin: center;
  transition: transform var(--transition-slow) var(--ease-out);
  z-index: 2;
}

.nav-item.active::before {
  transform: translateY(-50%) scaleY(1);
}

/* PNG layer that slides in from the right edge of the button. */
.nav-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image: var(--nav-item-bg, none);
  background-repeat: no-repeat;
  background-position: center;
  background-size: 100% 100%;
  opacity: 0;
  transform: translateX(100%);
}

.nav-item.has-bg .nav-bg {
  opacity: 1;
  transform: translateX(0);
}

.nav-item.animated .nav-bg {
  transition:
    transform var(--transition-slow) var(--ease-out),
    opacity var(--transition-slow) var(--ease-out);
}

.nav-icon {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  overflow: hidden;
}

.nav-item :deep(.icon) {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  display: block;
  transition: transform var(--transition);
}

.nav-item:hover :deep(.icon),
.nav-item.active :deep(.icon) {
  transform: scale(1.12);
}

.nav-item.expanded {
  justify-content: flex-start;
  padding-left: 1.25rem;
}

.nav-item.expanded .nav-icon {
  margin-right: 0.65rem;
}

/* Active + expanded: the icon collapses to the left and the label follows it. */
.nav-item.expanded.has-bg .nav-icon {
  width: 0;
  margin-right: 0;
  opacity: 0;
  transform: translateX(-10px);
}

.nav-item.animated .nav-icon {
  transition:
    width var(--transition-slow) var(--ease-out),
    margin-right var(--transition-slow) var(--ease-out),
    opacity var(--transition) var(--ease-out),
    transform var(--transition-slow) var(--ease-out);
}

.nav-item:not(.expanded):hover,
.nav-item:not(.expanded).active {
  background-color: var(--accent-soft);
  color: var(--accent);
  transform: translateY(-1px);
}

.nav-item.expanded:hover {
  background-color: var(--accent-soft);
  color: var(--accent);
  transform: translateY(-1px);
}

.nav-item.expanded.has-bg,
.nav-item.expanded.has-bg:hover {
  background-color: transparent;
}

.nav-item.expanded.has-bg {
  color: var(--accent);
}

.nav-item.expanded.has-bg:hover {
  filter: brightness(1.03);
  transform: translateY(-1px);
}

.nav-label {
  position: relative;
  z-index: 1;
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
