import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import SettingsLayout from '@/views/settings/SettingsLayout.vue'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    RouterView: { template: '<div class="router-view-stub" />' },
    RouterLink: {
      props: ['to'],
      template: '<a><slot /></a>',
    },
    useRoute: () => ({ name: 'settings-users' }),
  }
})

describe('SettingsLayout', () => {
  it('renders settings tabs', () => {
    const wrapper = mount(SettingsLayout)
    expect(wrapper.text()).toContain('Пользователи и роли')
    expect(wrapper.text()).toContain('Настройки бота')
    expect(wrapper.find('.router-view-stub').exists()).toBe(true)
  })
})
