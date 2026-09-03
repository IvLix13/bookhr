import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import ContractsView from '@/views/ContractsView.vue'
import { useAuthStore } from '@/stores/auth'

const { contracts, updateContract } = vi.hoisted(() => ({
  contracts: vi.fn(async () => ({
    items: [
      {
        id: 1,
        employment_id: 4,
        full_name: 'Иван Иванов',
        start_date: '2024-12-01',
        end_date: '2027-12-01',
        term_years: 3,
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
        start_date: '2025-10-01',
        end_date: '2027-10-01',
        term_years: 2,
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
  updateContract: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', () => ({
  api: { contracts, updateContract },
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

describe('ContractsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    contracts.mockClear()
    updateContract.mockClear()
  })

  async function mountView(role: 'admin' | 'hr' | 'viewer' = 'hr') {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
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

  it('shows edit button for hr and hides it for viewer', async () => {
    const hrView = await mountView('hr')
    expect(hrView.wrapper.findAll('button').some((item) => item.text() === 'Изменить')).toBe(true)
    hrView.wrapper.unmount()

    const viewerView = await mountView('viewer')
    expect(viewerView.wrapper.findAll('button').some((item) => item.text() === 'Изменить')).toBe(
      false,
    )
    expect(viewerView.wrapper.findAll('button').some((item) => item.text() === 'Мероприятие')).toBe(
      true,
    )
  })

  it('opens the contract form and saves term plus end date', async () => {
    const { wrapper } = await mountView('hr')
    const editButton = wrapper.findAll('button').find((item) => item.text() === 'Изменить')
    expect(editButton).toBeTruthy()
    await editButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Редактирование договора: Иван Иванов')
    expect(wrapper.text()).toContain('1 декабря 2024 г.')

    await wrapper.get('select').setValue('2')
    await wrapper.get('input[type="date"]').setValue('2027-06-01')
    expect(wrapper.text()).toContain('1 июня 2025 г.')

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateContract).toHaveBeenCalledWith(1, {
      term_years: 2,
      end_date: '2027-06-01',
    })
    expect(contracts.mock.calls.length).toBeGreaterThan(0)
  })
})
