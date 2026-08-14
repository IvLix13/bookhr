import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import AttentionPanel from '@/components/AttentionPanel.vue'

const { attention } = vi.hoisted(() => ({
  attention: vi.fn(async () => ({
    total: 4,
    counts: { events: 1, grades: 1, contracts: 1, tenure: 1 },
    items: [
      {
        category: 'events',
        id: 42,
        title: 'Просроченное мероприятие',
        subtitle: 'Иван Иванов',
        due_date: '2026-07-01',
        severity: 'danger',
        route: '/?event=42',
        event_id: 42,
      },
      {
        category: 'grades',
        id: 88,
        title: 'Рассмотреть повышение грейда',
        subtitle: 'Иван Иванов',
        due_date: '2026-07-10',
        severity: 'warning',
        route: '/?event=88',
        event_id: 88,
      },
      {
        category: 'contracts',
        id: 7,
        title: 'Истекает договор',
        severity: 'warning',
        route: '/contracts',
        event_id: 71,
      },
      {
        category: 'tenure',
        id: 3,
        title: 'Поощрение за 10 лет',
        severity: 'warning',
        route: '/awards',
        event_id: null,
      },
    ],
  })),
}))

vi.mock('@/api/client', () => ({
  api: { attention },
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

async function mountPanel() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'calendar', component: { template: '<div />' } },
      { path: '/events', name: 'events', component: { template: '<div />' } },
      { path: '/contracts', name: 'contracts', component: { template: '<div />' } },
      { path: '/awards', name: 'awards', component: { template: '<div />' } },
    ],
  })
  await router.push({ name: 'calendar' })
  await router.isReady()
  const replaceSpy = vi.spyOn(router, 'replace')
  const pushSpy = vi.spyOn(router, 'push')

  const wrapper = mount(AttentionPanel, {
    global: {
      plugins: [router],
      stubs: { EventDetailModal: modalStub },
    },
  })
  await flushPromises()
  return { wrapper, replaceSpy, pushSpy }
}

function itemButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button.attention-link').find((button) => button.text().includes(text))
}

describe('AttentionPanel', () => {
  it('opens an event in a modal without navigating away', async () => {
    const { wrapper, replaceSpy, pushSpy } = await mountPanel()

    const button = itemButton(wrapper, 'Просроченное мероприятие')
    expect(button).toBeTruthy()
    await button!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.modal-event-id').text()).toBe('42')
    expect(replaceSpy).not.toHaveBeenCalled()
    expect(pushSpy).not.toHaveBeenCalled()
  })

  it('opens a grade item in a modal', async () => {
    const { wrapper } = await mountPanel()

    await itemButton(wrapper, 'Рассмотреть повышение грейда')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.modal-event-id').text()).toBe('88')
  })

  it('opens a contract item through its related event', async () => {
    const { wrapper } = await mountPanel()

    await itemButton(wrapper, 'Истекает договор')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.modal-event-id').text()).toBe('71')
  })

  it('navigates for items that have no related event', async () => {
    const { wrapper } = await mountPanel()

    expect(itemButton(wrapper, 'Поощрение за 10 лет')).toBeUndefined()
    const link = wrapper
      .findAll('a.attention-link')
      .find((anchor) => anchor.text().includes('Поощрение за 10 лет'))
    expect(link!.attributes('href')).toBe('/awards')
  })

  it('reloads the list and reports the change after completing an event', async () => {
    const { wrapper } = await mountPanel()
    attention.mockClear()

    await itemButton(wrapper, 'Просроченное мероприятие')!.trigger('click')
    await flushPromises()
    await wrapper.find('.modal-complete').trigger('click')
    await flushPromises()

    expect(attention).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
