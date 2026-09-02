import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import AttentionPanel from '@/components/AttentionPanel.vue'

const attentionPayload = {
  total: 5,
  counts: { events: 1, grades: 1, contracts: 1, passports: 1, tenure: 1 },
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
      category: 'passports',
      id: 9,
      title: 'Паспорт скоро истекает',
      severity: 'warning',
      route: '/passports',
      event_id: null,
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
}

const { attention } = vi.hoisted(() => ({
  attention: vi.fn(async (params?: { categories?: string; limit?: number }) => {
    const category = params?.categories
    if (category) {
      return {
        ...attentionPayload,
        total: attentionPayload.counts[category as keyof typeof attentionPayload.counts] ?? 0,
        counts: { [category]: attentionPayload.counts[category as keyof typeof attentionPayload.counts] ?? 0 },
        items: attentionPayload.items.filter((item) => item.category === category),
      }
    }
    return attentionPayload
  }),
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
      { path: '/passports', name: 'passports', component: { template: '<div />' } },
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

function categoryChip(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button.count-chip').find((button) => button.text().includes(label))
}

describe('AttentionPanel', () => {
  it('formats due_date as human-readable Russian date', async () => {
    const { wrapper } = await mountPanel()
    const button = itemButton(wrapper, 'Просроченное мероприятие')
    expect(button).toBeTruthy()
    expect(button!.text()).toContain('1 июля 2026 г.')
  })

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

  it('filters by category when a non-event item is clicked', async () => {
    const { wrapper, pushSpy } = await mountPanel()

    await itemButton(wrapper, 'Поощрение за 10 лет')!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.attention-item')).toHaveLength(1)
    expect(wrapper.text()).toContain('Поощрение за 10 лет')
    expect(categoryChip(wrapper, 'Награды за стаж')!.classes()).toContain('active')
    expect(pushSpy).not.toHaveBeenCalled()
    expect(attention).toHaveBeenLastCalledWith(
      expect.objectContaining({ categories: 'tenure', limit: 50 }),
    )
  })

  it('reloads the list and reports the change after completing an event', async () => {
    const { wrapper } = await mountPanel()
    attention.mockClear()

    await itemButton(wrapper, 'Просроченное мероприятие')!.trigger('click')
    await flushPromises()
    await wrapper.find('.modal-complete').trigger('click')
    await flushPromises()

    expect(attention).toHaveBeenCalled()
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it.each([
    ['Договоры', 'contracts', 'Истекает договор'],
    ['Мероприятия', 'events', 'Просроченное мероприятие'],
    ['Грейды', 'grades', 'Рассмотреть повышение грейда'],
    ['Паспорта', 'passports', 'Паспорт скоро истекает'],
    ['Награды за стаж', 'tenure', 'Поощрение за 10 лет'],
  ])('filters by %s chip without navigating away', async (label, category, visibleTitle) => {
    const { wrapper, pushSpy } = await mountPanel()
    attention.mockClear()

    const chip = categoryChip(wrapper, label)
    expect(chip).toBeTruthy()
    expect(wrapper.findAll('.attention-item')).toHaveLength(5)

    await chip!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.attention-item')).toHaveLength(1)
    expect(wrapper.text()).toContain(visibleTitle)
    expect(chip!.classes()).toContain('active')
    expect(pushSpy).not.toHaveBeenCalled()
    expect(attention).toHaveBeenLastCalledWith(
      expect.objectContaining({ categories: category, limit: 50 }),
    )

    await chip!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.attention-item')).toHaveLength(5)
    expect(chip!.classes()).not.toContain('active')
  })

  it('switches category filter when another chip is clicked', async () => {
    const { wrapper } = await mountPanel()

    await categoryChip(wrapper, 'Грейды')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Рассмотреть повышение грейда')
    expect(wrapper.text()).not.toContain('Истекает договор')

    await categoryChip(wrapper, 'Договоры')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Истекает договор')
    expect(wrapper.text()).not.toContain('Рассмотреть повышение грейда')
    expect(categoryChip(wrapper, 'Договоры')!.classes()).toContain('active')
    expect(categoryChip(wrapper, 'Грейды')!.classes()).not.toContain('active')
  })
})
