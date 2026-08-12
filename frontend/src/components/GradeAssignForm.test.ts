import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import GradeAssignForm from '@/components/GradeAssignForm.vue'
import type { Grade, GradeRow } from '@/types'

const grades: Grade[] = [
  { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
  { id: 2, name: 'Middle', rank: 2, min_years: 1.5, is_active: false },
]

const row: GradeRow = {
  employment_id: 10,
  full_name: 'Иван Иванов',
  grade: null,
  grade_date: null,
  next_grade: null,
  eligible_date: null,
  days_left: null,
}

const { assignGrade } = vi.hoisted(() => ({
  assignGrade: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', () => ({
  api: {
    gradeCatalog: vi.fn(async () => grades),
    assignGrade,
  },
}))

describe('GradeAssignForm', () => {
  it('requires grade and date before submit', async () => {
    const wrapper = mount(GradeAssignForm, {
      props: { initial: row },
    })

    await flushPromises()
    const options = wrapper.findAll('select option')
    expect(options.some((option) => option.text().includes('Middle'))).toBe(false)
    expect(options.some((option) => option.text().includes('Junior'))).toBe(true)

    await wrapper.find('form').trigger('submit.prevent')
    expect(assignGrade).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Выберите грейд и укажите дату назначения')
  })

  it('submits active grade assignment', async () => {
    assignGrade.mockClear()
    const wrapper = mount(GradeAssignForm, {
      props: { initial: row },
    })

    await flushPromises()
    await wrapper.find('select').setValue('1')
    await wrapper.find('input[type="date"]').setValue('2025-06-01')
    await wrapper.find('form').trigger('submit.prevent')

    expect(assignGrade).toHaveBeenCalledWith({
      employment_id: 10,
      grade_id: 1,
      assigned_date: '2025-06-01',
      basis: undefined,
    })
  })
})
