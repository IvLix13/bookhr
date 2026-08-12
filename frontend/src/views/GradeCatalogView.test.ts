import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import GradeCatalogView from '@/views/GradeCatalogView.vue'

vi.mock('@/api/client', () => ({
  api: {
    gradeCatalog: vi.fn(async () => [
      { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
      { id: 2, name: 'Middle', rank: 2, min_years: 1.5, is_active: false },
    ]),
    createGradeCatalog: vi.fn(async (body) => ({ id: 3, is_active: true, ...body })),
    updateGradeCatalog: vi.fn(async (id, body) => ({
      id,
      name: 'Updated',
      rank: 1,
      min_years: 1,
      is_active: true,
      ...body,
    })),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAdmin: () => true,
  }),
}))

describe('GradeCatalogView', () => {
  it('renders catalog form and inactive status label', async () => {
    const wrapper = mount(GradeCatalogView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          DataTable: {
            props: ['rows'],
            template: '<div class="table-stub">{{ rows.length }} rows</div>',
          },
        },
      },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('Справочник грейдов')
    expect(wrapper.text()).toContain('Мин. лет до следующего грейда')
    expect(wrapper.text()).toContain('2 rows')
    expect(wrapper.text()).toContain('К грейдам')
  })
})
