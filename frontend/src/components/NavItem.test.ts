import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import NavItem from '@/components/NavItem.vue'

const routes = [{ path: '/', name: 'calendar', component: { template: '<div />' } }]

async function createTestRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })
  await router.push('/')
  await router.isReady()
  return router
}

function frame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve(null)))
}

/** Lets the component re-enable its transitions after a layout change. */
async function settleLayout() {
  await nextTick()
  await frame()
  await frame()
  await frame()
  await nextTick()
}

describe('NavItem backgrounds', () => {
  it('applies PNG background only when expanded and active', async () => {
    const router = await createTestRouter()

    const collapsed = mount(NavItem, {
      props: {
        name: 'calendar',
        label: 'Календарь',
        expanded: false,
        active: true,
        background: '/test-bg.png',
      },
      global: { plugins: [router] },
    })
    expect(collapsed.classes()).not.toContain('has-bg')
    expect(collapsed.attributes('style')).toBeUndefined()

    const inactive = mount(NavItem, {
      props: {
        name: 'calendar',
        label: 'Календарь',
        expanded: true,
        active: false,
        background: '/test-bg.png',
      },
      global: { plugins: [router] },
    })
    expect(inactive.classes()).not.toContain('has-bg')

    const expanded = mount(NavItem, {
      props: {
        name: 'calendar',
        label: 'Календарь',
        expanded: true,
        background: '/test-bg.png',
        backgroundActive: '/test-bg-active.png',
        active: true,
      },
      global: { plugins: [router] },
    })
    expect(expanded.classes()).toContain('has-bg')
    expect(expanded.attributes('style')).toContain('url(/test-bg-active.png)')
  })

  it('keeps the icon slot mounted so it can animate out', async () => {
    const router = await createTestRouter()

    const wrapper = mount(NavItem, {
      props: {
        name: 'calendar',
        label: 'Календарь',
        expanded: true,
        active: true,
        background: '/test-bg.png',
      },
      slots: { default: '<svg class="icon" />' },
      global: { plugins: [router] },
    })

    expect(wrapper.find('.nav-icon .icon').exists()).toBe(true)
    expect(wrapper.find('.nav-bg').exists()).toBe(true)
  })
})

describe('NavItem animation gating', () => {
  it('animates a route change but not a sidebar expand', async () => {
    const router = await createTestRouter()

    const wrapper = mount(NavItem, {
      props: {
        name: 'calendar',
        label: 'Календарь',
        expanded: true,
        active: false,
        background: '/test-bg.png',
      },
      global: { plugins: [router] },
    })

    await settleLayout()
    expect(wrapper.classes()).toContain('animated')

    // Becoming the active item keeps transitions on: the icon slides out and
    // the background slides in.
    await wrapper.setProps({ active: true })
    expect(wrapper.classes()).toContain('animated')
    expect(wrapper.classes()).toContain('has-bg')

    // Collapsing and re-expanding the sidebar must snap straight to the final
    // look instead of replaying the animation.
    await wrapper.setProps({ expanded: false })
    expect(wrapper.classes()).not.toContain('animated')

    await settleLayout()
    await wrapper.setProps({ expanded: true })
    expect(wrapper.classes()).not.toContain('animated')
    expect(wrapper.classes()).toContain('has-bg')

    await settleLayout()
    expect(wrapper.classes()).toContain('animated')
  })
})
