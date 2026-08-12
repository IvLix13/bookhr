import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ImportLayout from '@/views/import/ImportLayout.vue'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    RouterView: { template: '<div class="router-view-stub" />' },
    RouterLink: {
      props: ['to'],
      template: '<a><slot /></a>',
    },
    useRoute: () => ({ name: 'import-employees' }),
  }
})

describe('ImportLayout', () => {
  it('renders import tabs for employees and rewards', () => {
    const wrapper = mount(ImportLayout)
    expect(wrapper.text()).toContain('Импорт из Excel')
    expect(wrapper.text()).toContain('Общая таблица')
    expect(wrapper.text()).toContain('Поощрения')
    expect(wrapper.find('.router-view-stub').exists()).toBe(true)
  })
})
