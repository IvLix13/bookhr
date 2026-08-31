import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AwardsView from '@/views/AwardsView.vue'
import { useAuthStore } from '@/stores/auth'
import type { TenureRow } from '@/types'

const sampleRow: TenureRow = {
  employment_id: 1,
  full_name: 'Иванов Иван',
  tenure_years: 12,
  continuous_tenure_years: 6,
  awards: {
    '10': {
      id: 101,
      milestone_years: 10,
      milestone_date: '2020-03-01',
      is_received: false,
      received_date: null,
    },
    '15': {
      id: 102,
      milestone_years: 15,
      milestone_date: '2025-03-01',
      is_received: true,
      received_date: '2025-06-01',
    },
    '20': {
      id: 103,
      milestone_years: 20,
      milestone_date: '2030-03-01',
      is_received: false,
      received_date: null,
    },
  },
}

const { tenure, updateTenureAward } = vi.hoisted(() => ({
  tenure: vi.fn(async () => ({
    items: [sampleRow],
    total: 1,
    page: 1,
    per_page: 25,
    pages: 1,
  })),
  updateTenureAward: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', () => ({
  api: {
    tenure,
    updateTenureAward,
  },
}))

describe('AwardsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    tenure.mockClear()
    updateTenureAward.mockClear()
  })

  async function mountView(role: 'admin' | 'hr' | 'viewer' = 'hr') {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
    const wrapper = mount(AwardsView)
    await flushPromises()
    return wrapper
  }

  it('shows edit button for hr', async () => {
    const wrapper = await mountView('hr')
    expect(wrapper.find('.btn.secondary').text()).toBe('Изменить')
  })

  it('hides edit button for viewer', async () => {
    const wrapper = await mountView('viewer')
    expect(wrapper.find('.btn.secondary').exists()).toBe(false)
  })

  it('opens edit form and saves awards', async () => {
    const wrapper = await mountView('hr')
    await wrapper.get('.btn.secondary').trigger('click')
    expect(wrapper.text()).toContain('Награды за стаж: Иванов Иван')

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    await checkboxes[0].setValue(true)

    await wrapper.get('form .btn').trigger('submit')
    await flushPromises()

    expect(updateTenureAward).toHaveBeenCalled()
    expect(tenure).toHaveBeenCalledTimes(2)
  })

  it('shows received awards with checkmark and date without the word Получено', async () => {
    const wrapper = await mountView('hr')
    const row = wrapper.find('.data-table-row')
    expect(row.text()).toContain('✓')
    expect(row.text()).toContain('01.06.2025')
    expect(row.text()).not.toContain('Получено')
    expect(row.find('.award-cell-received').exists()).toBe(true)
  })
})
