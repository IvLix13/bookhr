import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import ContractsView from '@/views/ContractsView.vue'

const { contracts } = vi.hoisted(() => ({
  contracts: vi.fn(async () => ({
    items: [
      {
        id: 1,
        employment_id: 4,
        full_name: 'Иван Иванов',
        start_date: '2025-01-01',
        end_date: '2027-12-01',
        days_left: 100,
        is_active: true,
        renewal_report_event: {
          id: 55,
          event_date: '2027-08-01',
          completed_date: null,
          status: 'planned',
          effective_status: 'planned',
        },
      },
      {
        id: 2,
        employment_id: 5,
        full_name: 'Пётр Петров',
        start_date: '2025-01-01',
        end_date: '2027-10-01',
        days_left: 60,
        is_active: true,
        renewal_report_event: {
          id: 56,
          event_date: '2027-06-01',
          completed_date: '2027-05-20',
          status: 'completed',
          effective_status: 'completed',
        },
      },
    ],
    total: 2,
    page: 1,
    per_page: 25,
  })),
}))

vi.mock('@/api/client', () => ({
  api: { contracts },
}))

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

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/contracts', name: 'contracts', component: { template: '<div />' } },
      { path: '/events', name: 'events', component: { template: '<div />' } },
    ],
  })
  await router.push({ name: 'contracts' })
  await router.isReady()
  const pushSpy = vi.spyOn(router, 'push')

  const wrapper = mount(ContractsView, {
    global: {
      plugins: [router],
      stubs: { EventDetailModal: modalStub },
    },
  })
  await flushPromises()
  return { wrapper, pushSpy }
}

describe('ContractsView', () => {
  it('opens the renewal report in a modal without leaving the contracts tab', async () => {
    const { wrapper, pushSpy } = await mountView()

    const button = wrapper.findAll('button').find((item) => item.text() === 'Мероприятие')
    expect(button).toBeTruthy()
    await button!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.modal-event-id').text()).toBe('55')
    expect(pushSpy).not.toHaveBeenCalled()
  })

  it('shows the completion date as the report date once the report is done', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('20 мая 2027')
    // The planned report date is replaced by the date it was actually prepared.
    expect(wrapper.text()).not.toContain('1 июня 2027')
  })

  it('reloads the table after the report is completed', async () => {
    const { wrapper } = await mountView()
    contracts.mockClear()

    const button = wrapper.findAll('button').find((item) => item.text() === 'Мероприятие')
    await button!.trigger('click')
    await flushPromises()
    await wrapper.find('.modal-complete').trigger('click')
    await flushPromises()

    expect(contracts).toHaveBeenCalled()
  })
})
