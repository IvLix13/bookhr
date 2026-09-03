import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportSummary from '@/components/ImportSummary.vue'
import type { ImportJob } from '@/types'

const job: ImportJob = {
  id: 3,
  filename: 'employees.xlsx',
  import_type: 'employees',
  status: 'validated',
  summary: { create: 1 },
  unknown_grades: [],
  error_message: null,
  created_at: '2026-07-24T10:15:00',
  rows: [],
}

describe('ImportSummary', () => {
  it('formats created_at as a human-readable Russian date', () => {
    const wrapper = mount(ImportSummary, { props: { job } })
    expect(wrapper.text()).toContain('Загружен: 24 июля 2026 г.')
    expect(wrapper.text()).not.toContain('2026-07-24')
  })
})
