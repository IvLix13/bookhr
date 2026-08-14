import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import UpcomingPanel from '@/components/UpcomingPanel.vue'
import type { EventItem } from '@/types'

const events: EventItem[] = [
  {
    id: 11,
    title: 'Подготовить рапорт на продление Договора',
    event_type: 'report',
    description: null,
    event_date: '2026-08-20',
    status: 'planned',
    source: 'rule',
    employment_id: 4,
    employee_name: 'Иван Иванов',
    created_by: null,
    created_at: null,
    completed_at: null,
    completion_comment: null,
  },
]

const modalStub = {
  props: ['open', 'eventId'],
  emits: ['close', 'changed'],
  template: `
    <div v-if="open" class="event-modal-stub">
      <span class="modal-event-id">{{ eventId }}</span>
      <button type="button" class="modal-complete" @click="$emit('changed')">Выполнить</button>
    </div>
  `,
}

function mountPanel() {
  return mount(UpcomingPanel, {
    props: { events },
    global: { stubs: { EventDetailModal: modalStub } },
  })
}

describe('UpcomingPanel', () => {
  it('opens an event in a modal instead of navigating', async () => {
    const wrapper = mountPanel()

    expect(wrapper.find('a').exists()).toBe(false)
    await wrapper.find('button.item').trigger('click')
    await flushPromises()

    expect(wrapper.find('.modal-event-id').text()).toBe('11')
  })

  it('reports a change so the parent can refresh the list', async () => {
    const wrapper = mountPanel()

    await wrapper.find('button.item').trigger('click')
    await flushPromises()
    await wrapper.find('.modal-complete').trigger('click')

    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
