import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import GradeCatalogView from '@/views/GradeCatalogView.vue'

const { deleteGradeCatalog } = vi.hoisted(() => ({
  deleteGradeCatalog: vi.fn(async () => ({ id: 2 })),
}))

vi.mock('@/api/client', () => ({
  api: {
    gradeCatalog: vi.fn(async () => [
      { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true, in_use_count: 0 },
      { id: 2, name: 'Middle', rank: 2, min_years: 1.5, is_active: false, in_use_count: 3 },
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
    deleteGradeCatalog,
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    canEdit: () => true,
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
          ConfirmDialog: true,
        },
      },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('Справочник грейдов')
    expect(wrapper.text()).toContain('Мин. лет до следующего грейда')
    expect(wrapper.text()).toContain('2 rows')
    expect(wrapper.text()).toContain('К грейдам')
  })

  it('warns when deleting a grade that is in use', async () => {
    const wrapper = mount(GradeCatalogView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          DataTable: {
            props: ['rows'],
            template: `
              <div>
                <div v-for="row in rows" :key="row.id">
                  <slot name="cell-actions" :row="row" />
                </div>
              </div>
            `,
          },
          ConfirmDialog: {
            props: ['open', 'title', 'message'],
            template:
              '<div v-if="open" class="confirm-stub">{{ title }} {{ message }}</div>',
          },
        },
      },
    })

    await flushPromises()
    const deleteButtons = wrapper.findAll('button').filter((button) => button.text() === 'Удалить')
    expect(deleteButtons.length).toBeGreaterThan(1)
    await deleteButtons[1].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Удалить грейд «Middle»?')
    expect(wrapper.text()).toContain('используется у 3 сотрудников')
    expect(wrapper.text()).toContain('в поле грейда у сотрудников будет «—»')
    expect(deleteGradeCatalog).not.toHaveBeenCalled()
  })
})
