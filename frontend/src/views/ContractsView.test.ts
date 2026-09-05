import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import ContractsView from '@/views/ContractsView.vue'
import { useAuthStore } from '@/stores/auth'

const defaultContractsPayload = {
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
}

const { contracts, updateContract } = vi.hoisted(() => ({
  contracts: vi.fn(),
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
    contracts.mockReset()
    contracts.mockResolvedValue(defaultContractsPayload)
    updateContract.mockClear()
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
      attachTo: document.body,
      global: {
        plugins: [router],
        stubs: { EventDetailModal: modalStub, teleport: true },
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

  it('opens the contract form from a row click and hides the edit button', async () => {
    const hrView = await mountView('hr')
    expect(hrView.wrapper.findAll('button').some((item) => item.text() === 'Изменить')).toBe(false)
    expect(hrView.wrapper.find('form').exists()).toBe(false)

    await hrView.wrapper.get('.data-table-row').trigger('click')
    await flushPromises()
    expect(hrView.wrapper.text()).toContain('Редактирование договора: Иван Иванов')
    hrView.wrapper.unmount()

    const viewerView = await mountView('viewer')
    expect(viewerView.wrapper.findAll('button').some((item) => item.text() === 'Изменить')).toBe(
      false,
    )
    expect(viewerView.wrapper.findAll('button').some((item) => item.text() === 'Мероприятие')).toBe(
      true,
    )
    await viewerView.wrapper.get('.data-table-row').trigger('click')
    await flushPromises()
    expect(viewerView.wrapper.find('form').exists()).toBe(false)
  })

  it('does not open the contract form when the report button is clicked', async () => {
    const { wrapper } = await mountView('hr')
    const button = wrapper.findAll('button').find((item) => item.text() === 'Мероприятие')
    await button!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.modal-event-id').text()).toBe('55')
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('opens the contract form and saves term plus end date', async () => {
    const { wrapper } = await mountView('hr')
    await wrapper.get('.data-table-row').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Редактирование договора: Иван Иванов')
    expect(wrapper.text()).toContain('1 декабря 2024 г.')

    await wrapper.get('form select').setValue('2')
    await wrapper.get('input[name="end_date"]').setValue('2027-06-01')
    expect(wrapper.text()).toContain('1 июня 2025 г.')
    await wrapper.get('input[name="report_date"]').setValue('2027-01-15')

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateContract).toHaveBeenCalledWith(1, {
      term_years: 2,
      end_date: '2027-06-01',
      report_date: '2027-01-15',
    })
    expect(contracts.mock.calls.length).toBeGreaterThan(0)
  })

  it('reloads after saving a contract without a report and shows the event button', async () => {
    const rowWithoutEvent = {
      id: 3,
      employment_id: 6,
      full_name: 'Анна Безрапорта',
      start_date: '2024-12-01',
      end_date: '2027-12-01',
      term_years: 3,
      days_left: 80,
      is_active: true,
      renewal_report_event: null,
    }
    const rowWithEvent = {
      ...rowWithoutEvent,
      renewal_report_event: {
        id: 99,
        event_date: '2027-08-01',
        completed_date: null,
        status: 'planned',
        effective_status: 'planned',
      },
    }
    contracts.mockResolvedValue({
      items: [rowWithoutEvent],
      total: 1,
      page: 1,
      per_page: 25,
    })

    const { wrapper } = await mountView('hr')
    expect(wrapper.findAll('button').some((item) => item.text() === 'Мероприятие')).toBe(false)

    await wrapper.get('.data-table-row').trigger('click')
    await flushPromises()

    contracts.mockResolvedValue({
      items: [rowWithEvent],
      total: 1,
      page: 1,
      per_page: 25,
    })
    contracts.mockClear()

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateContract).toHaveBeenCalledWith(3, {
      term_years: 3,
      end_date: '2027-12-01',
      report_date: '2027-08-01',
    })
    expect(contracts).toHaveBeenCalled()
    expect(wrapper.findAll('button').some((item) => item.text() === 'Мероприятие')).toBe(true)
  })
})
