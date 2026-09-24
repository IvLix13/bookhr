import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StatisticsView from '@/views/StatisticsView.vue'

const mock = vi.hoisted(() => ({ stats: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { stats: mock.stats } }))
vi.mock('@/api/manualStatistics', () => ({
  manualStatisticsApi: { get: vi.fn(), upload: vi.fn(), downloadTemplate: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ canEdit: () => true }) }))

const ChartStub = defineComponent({
  name: 'VChart',
  props: { option: { type: Object, required: true } },
  template: '<div class="chart-stub" />',
})

beforeEach(() => {
  vi.resetAllMocks()
  mock.stats.mockResolvedValue({
    period: { from: '2026-01-01', to: '2026-12-31' },
    employees: { active: 3, hired_in_period: 0, dismissed_in_period: 0 },
    events: { planned: 0, overdue: 0, completed: 0, cancelled: 0, completion_rate: 0, by_type: {}, monthly: [] },
    contracts: { active: 0, expired: 0, expiring_120d: 0 },
    grades: {
      distribution: [
        { name: 'Junior', rank: 1, count: 1 },
        { name: 'Middle', rank: 2, count: 1 },
        { name: 'Senior', rank: 3, count: 1 },
      ],
      without_grade: 0,
      eligible_now: 0,
      eligible_30d: 0,
      assigned_in_period: 0,
    },
    tenure: { pending: {}, received: {}, received_in_period: 0 },
    passports: { ok: 0, requires_preparation: 0, expired: 0, missing: 0, expiring_90d: 0 },
  })
})

describe('Automatic statistics charts', () => {
  it('renders grade categories in the rank order supplied by the API', async () => {
    const wrapper = mount(StatisticsView, { global: { stubs: { Echarts: ChartStub } } })
    await flushPromises()

    const charts = wrapper.findAllComponents(ChartStub)
    const grades = charts.find((chart) => {
      const option = chart.props('option') as { xAxis?: { data?: string[] } }
      return option.xAxis?.data?.includes('Junior')
    })
    expect(grades).toBeDefined()
    expect((grades!.props('option') as { xAxis: { data: string[] } }).xAxis.data).toEqual([
      'Junior', 'Middle', 'Senior',
    ])
    wrapper.unmount()
  })
})
