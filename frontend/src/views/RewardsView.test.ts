import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RewardsView from '@/views/RewardsView.vue'
import { useAuthStore } from '@/stores/auth'
import type { RewardRow } from '@/types'

const sampleReward: RewardRow = {
  id: 1,
  employment_id: 10,
  full_name: 'Иванов Иван',
  reward_type: 'Благодарность',
  status: 'not_delivered',
  status_changed_date: '2026-01-01',
  directive_text: null,
  delivered_date: null,
  notes: null,
  updated_at: '2026-01-01T00:00:00',
}

const { rewards, createReward, updateReward, employees } = vi.hoisted(() => ({
  rewards: vi.fn(async () => ({
    items: [sampleReward],
    total: 1,
    page: 1,
    per_page: 25,
    pages: 1,
  })),
  createReward: vi.fn(async () => ({})),
  updateReward: vi.fn(async () => ({})),
  employees: vi.fn(async () => ({
    items: [{ id: 10, full_name: 'Иванов Иван' }],
    total: 1,
    page: 1,
    per_page: 200,
    pages: 1,
  })),
}))

vi.mock('@/api/client', () => ({
  api: {
    rewards,
    createReward,
    updateReward,
    employees,
  },
}))

describe('RewardsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    rewards.mockClear()
    createReward.mockClear()
    updateReward.mockClear()
    employees.mockClear()
    document.body.innerHTML = ''
  })

  async function mountView(role: 'admin' | 'hr' | 'viewer' = 'hr') {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
    const wrapper = mount(RewardsView, {
      attachTo: document.body,
      global: {
        stubs: {
          teleport: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  it('shows add button for hr and hides form until clicked', async () => {
    const wrapper = await mountView('hr')
    expect(wrapper.get('header .btn').text()).toBe('Добавить новое поощрение')
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('hides add button for viewer', async () => {
    const wrapper = await mountView('viewer')
    expect(wrapper.find('header .btn').exists()).toBe(false)
  })

  it('opens create modal on add button click', async () => {
    const wrapper = await mountView('hr')
    await wrapper.get('header .btn').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Новое поощрение')
    expect(document.body.textContent).toContain('Вид поощрения')
  })

  it('opens edit modal from row action', async () => {
    const wrapper = await mountView('hr')
    await wrapper.get('.btn.secondary').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Редактирование поощрения')
  })
})
