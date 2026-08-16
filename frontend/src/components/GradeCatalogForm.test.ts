import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import GradeCatalogForm from '@/components/GradeCatalogForm.vue'

const { createGradeCatalog, updateGradeCatalog, gradeCatalog } = vi.hoisted(() => ({
  gradeCatalog: vi.fn(async () => [
    { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
  ]),
  createGradeCatalog: vi.fn(async (body: { name: string; rank: number; min_years: number }) => ({
    id: 3,
    is_active: true,
    ...body,
  })),
  updateGradeCatalog: vi.fn(async (id: number, body: Record<string, unknown>) => ({
    id,
    name: 'Updated',
    rank: 1,
    min_years: 1,
    is_active: true,
    ...body,
  })),
}))

vi.mock('@/api/client', () => ({
  api: {
    gradeCatalog,
    createGradeCatalog,
    updateGradeCatalog,
  },
}))

describe('GradeCatalogForm', () => {
  it('submits a trimmed name and emits saved', async () => {
    const wrapper = mount(GradeCatalogForm, {
      props: { mode: 'create', initialName: '  Лид  ' },
    })

    await flushPromises()
    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('Лид')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createGradeCatalog).toHaveBeenCalledWith({
      name: 'Лид',
      rank: 2,
      min_years: 1,
      extra_year_without_university: false,
    })
    expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({
      id: 3,
      name: 'Лид',
      rank: 2,
    })
  })
})
