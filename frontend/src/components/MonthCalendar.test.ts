import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MonthCalendar from '@/components/MonthCalendar.vue'
import type { EventItem } from '@/types'

const sampleEvents: EventItem[] = [
  {
    id: 1,
    title: 'Test event',
    event_type: 'manual',
    description: null,
    event_date: '2026-07-24',
    status: 'planned',
    effective_status: 'planned',
    source: 'manual',
    employment_id: null,
    employee_name: null,
    created_by: null,
    created_at: null,
    completed_at: null,
    completion_comment: null,
  },
]

describe('MonthCalendar', () => {
  it('renders month label with lowercase г.', () => {
    const wrapper = mount(MonthCalendar, {
      props: {
        events: [],
        month: new Date(2026, 6, 1),
      },
    })

    expect(wrapper.find('header h2').text()).toBe('Июль 2026 г.')
  })

  it('emits selected day on click', async () => {
    const wrapper = mount(MonthCalendar, {
      props: {
        events: sampleEvents,
        month: new Date(2026, 6, 1),
      },
    })

    const dayButton = wrapper.find('button.day-button')
    await dayButton.trigger('click')

    expect(wrapper.emitted('selectDay')).toBeTruthy()
    const emittedDate = wrapper.emitted('selectDay')?.[0]?.[0] as Date
    expect(emittedDate.getDate()).toBe(1)
  })
})
