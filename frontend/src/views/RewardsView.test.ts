import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RewardsView from '@/views/RewardsView.vue'
import { ApiError } from '@/api/errors'
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

const statisticsPayload = {
  items: [
    { status: 'not_delivered', label: 'Не вручено', count: 2 },
    { status: 'in_hr', label: 'В кадрах', count: 0 },
    { status: 'delivered', label: 'Вручено', count: 1 },
    { status: 'extra_1', label: 'Доп. статус 1', count: 0 },
    { status: 'extra_2', label: 'Доп. статус 2', count: 0 },
    { status: 'extra_3', label: 'Доп. статус 3', count: 0 },
  ],
  total: 3,
}

const { rewards, createReward, updateReward, employees, rewardStatistics, downloadRewardStatistics } = vi.hoisted(() => ({
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
  rewardStatistics: vi.fn(async () => statisticsPayload),
  downloadRewardStatistics: vi.fn(async () => undefined),
}))

vi.mock('@/api/client', () => ({
  api: {
    rewards,
    createReward,
    updateReward,
    employees,
    rewardStatistics,
    downloadRewardStatistics,
  },
}))

describe('RewardsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    rewards.mockClear()
    createReward.mockClear()
    updateReward.mockClear()
    employees.mockClear()
    rewardStatistics.mockClear()
    downloadRewardStatistics.mockClear()
    rewardStatistics.mockResolvedValue(statisticsPayload)
    downloadRewardStatistics.mockResolvedValue(undefined)
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
    expect(wrapper.get('header').text()).toContain('Добавить новое поощрение')
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('shows statistics for viewer and hides adding', async () => {
    const wrapper = await mountView('viewer')
    expect(wrapper.get('header').text()).toContain('Статистика')
    expect(wrapper.get('header').text()).not.toContain('Добавить новое поощрение')
  })

  it('opens create modal on add button click', async () => {
    const wrapper = await mountView('hr')
    await wrapper.findAll('header button').find(button => button.text() === 'Добавить новое поощрение')!.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Новое поощрение')
    expect(document.body.textContent).toContain('Вид поощрения')
  })

  it('opens edit modal from row action', async () => {
    const wrapper = await mountView('hr')
    await wrapper.findAll('.btn.secondary').find(button => button.text() === 'Изменить')!.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Редактирование поощрения')
  })

  it('opens status counts and downloads them', async () => {
    const wrapper = await mountView('viewer')
    await wrapper.findAll('button').find(button => button.text() === 'Статистика')!.trigger('click')
    await flushPromises()
    expect(rewardStatistics).toHaveBeenCalledOnce()
    expect(document.body.textContent).toContain('Статистика поощрений')
    expect(document.body.textContent).toContain('Не вручено')
    expect(document.body.textContent).toContain('Всего')
    const download = wrapper.findAll('button').find(button => button.text() === 'Скачать Excel')!
    await download.trigger('click')
    await flushPromises()
    expect(downloadRewardStatistics).toHaveBeenCalledOnce()

    downloadRewardStatistics.mockRejectedValueOnce(new ApiError('Ошибка выгрузки', 500))
    await download.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Ошибка выгрузки')
    wrapper.unmount()
  })
})
