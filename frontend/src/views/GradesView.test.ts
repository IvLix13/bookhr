import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import GradesView from '@/views/GradesView.vue'

vi.mock('@/api/client', () => ({
  api: {
    grades: vi.fn(async () => ({
      items: [
        {
          employment_id: 1,
          full_name: 'Доступный Иван',
          grade: { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
          grade_date: '2020-01-01',
          next_grade: { id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true },
          eligible_date: '2021-01-01',
          days_left: -400,
          is_available: true,
        },
        {
          employment_id: 2,
          full_name: 'Ждущий Пётр',
          grade: { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
          grade_date: '2026-01-01',
          next_grade: { id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true },
          eligible_date: '2027-01-01',
          days_left: 300,
          is_available: false,
        },
        {
          employment_id: 3,
          full_name: 'На Пике Анна',
          grade: { id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true },
          grade_date: '2024-01-01',
          next_grade: null,
          eligible_date: null,
          days_left: null,
          is_available: false,
        },
      ],
      total: 3,
      page: 1,
      per_page: 25,
    })),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ canEdit: () => false, isAdmin: () => false }),
}))

function rowText(wrapper: ReturnType<typeof mount>, name: string): string {
  const row = wrapper.findAll('tr').find((item) => item.text().includes(name))
  return row?.text() ?? ''
}

describe('GradesView', () => {
  it('marks rows where the next grade is already available', async () => {
    const wrapper = mount(GradesView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' }, GradeAssignForm: true } },
    })
    await flushPromises()

    expect(rowText(wrapper, 'Доступный Иван')).toContain('Доступен')
    expect(rowText(wrapper, 'Ждущий Пётр')).not.toContain('Доступен')
  })

  it('shows no eligible date when the position grade is already reached', async () => {
    const wrapper = mount(GradesView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' }, GradeAssignForm: true } },
    })
    await flushPromises()

    const row = rowText(wrapper, 'На Пике Анна')
    expect(row).toContain('—')
    expect(row).not.toContain('Доступен')
  })
})
