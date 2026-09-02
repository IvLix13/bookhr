import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import NavItem from '@/components/NavItem.vue'

const routes = [{ path: '/', name: 'calendar', component: { template: '<div />' } }]

describe('NavItem backgrounds', () => {
  it('applies PNG background only when expanded', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    await router.push('/')
    await router.isReady()

    const collapsed = mount(NavItem, {
      props: {
        name: 'calendar',
        label: 'Календарь',
        expanded: false,
        background: '/test-bg.png',
      },
      global: { plugins: [router] },
    })
    expect(collapsed.classes()).not.toContain('has-bg')
    expect(collapsed.attributes('style')).toBeUndefined()

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
})
