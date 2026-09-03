import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GradesView from '@/views/GradesView.vue'
import { useAuthStore } from '@/stores/auth'

const { grades, gradeCatalog, assignGrade } = vi.hoisted(() => ({
  grades: vi.fn(async () => ({
    items: [
      {
        employment_id: 1,
        full_name: 'Доступный Иван',
        grade: { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
        grade_date: '2020-01-01',
        next_grade: { id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true },
        next_grade_candidates: [{ id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true }],
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
        next_grade_candidates: [{ id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true }],
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
        next_grade_candidates: [],
        eligible_date: null,
        days_left: null,
        is_available: false,
      },
    ],
    total: 3,
    page: 1,
    per_page: 25,
  })),
  gradeCatalog: vi.fn(async () => [
    { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
    { id: 2, name: 'Middle', rank: 2, min_years: 2, is_active: true },
  ]),
  assignGrade: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', () => ({
  api: {
    grades,
    gradeCatalog,
    assignGrade,
  },
}))

function rowText(wrapper: ReturnType<typeof mount>, name: string): string {
  const row = wrapper.findAll('tr').find((item) => item.text().includes(name))
  return row?.text() ?? ''
}

describe('GradesView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    grades.mockClear()
    gradeCatalog.mockClear()
    assignGrade.mockClear()
    document.body.innerHTML = ''
  })

  async function mountView(role: 'admin' | 'hr' | 'viewer' | null = null) {
    if (role) {
      const auth = useAuthStore()
      auth.user = {
        id: 1,
        username: role,
        full_name: role,
        role,
      }
    }
    const wrapper = mount(GradesView, {
      attachTo: document.body,
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          teleport: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  it('requests nearest eligible date sort by default', async () => {
    await mountView()
    expect(grades).toHaveBeenCalledWith(
      expect.objectContaining({
        sort: 'eligible_date_nearest',
        direction: 'asc',
      }),
    )
  })

  it('marks rows where the next grade is already available', async () => {
    const wrapper = await mountView()
    expect(rowText(wrapper, 'Доступный Иван')).toContain('Доступен')
    expect(rowText(wrapper, 'Ждущий Пётр')).not.toContain('Доступен')
  })

  it('shows no eligible date when the position grade is already reached', async () => {
    const wrapper = await mountView()
    const row = rowText(wrapper, 'На Пике Анна')
    expect(row).toContain('—')
    expect(row).not.toContain('Доступен')
  })

  it('opens the grade form from a row click for hr and hides the action button', async () => {
    const wrapper = await mountView('hr')
    expect(wrapper.findAll('button').some((item) => item.text() === 'Изменить грейд')).toBe(false)
    expect(wrapper.findAll('button').some((item) => item.text() === 'Назначить грейд')).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)

    await wrapper.get('.data-table-row').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Изменить грейд')
    expect(wrapper.text()).toContain('Доступный Иван')
    expect(wrapper.find('form').exists()).toBe(true)
  })

  it('does not open the grade form for a viewer row click', async () => {
    const wrapper = await mountView('viewer')
    await wrapper.get('.data-table-row').trigger('click')
    await flushPromises()
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('saves a grade assignment from the row modal', async () => {
    const wrapper = await mountView('hr')
    await wrapper.get('.data-table-row').trigger('click')
    await flushPromises()

    await wrapper.get('form select').setValue('2')
    await wrapper.get('input[type="date"]').setValue('2026-09-01')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(assignGrade).toHaveBeenCalledWith({
      employment_id: 1,
      grade_id: 2,
      assigned_date: '2026-09-01',
      basis: undefined,
    })
    expect(grades.mock.calls.length).toBeGreaterThan(0)
  })
})
