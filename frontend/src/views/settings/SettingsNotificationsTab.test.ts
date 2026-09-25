import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsNotificationsTab from '@/views/settings/SettingsNotificationsTab.vue'

const mock = vi.hoisted(() => ({
  rules: vi.fn(),
  searchUsers: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  testNotification: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    notificationRules: mock.rules,
    searchNextcloudUsers: mock.searchUsers,
    createNotificationRule: mock.createRule,
    updateNotificationRule: mock.updateRule,
    testNotification: mock.testNotification,
  },
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: mock.success, error: mock.error }),
}))

beforeEach(() => {
  vi.resetAllMocks()
  mock.rules.mockResolvedValue([])
  mock.searchUsers.mockResolvedValue([
    { user_id: 'ivanov', display_name: 'Иванов Иван Иванович' },
    { user_id: 'ivanova', display_name: 'Иванова Ирина Игоревна' },
  ])
  mock.createRule.mockResolvedValue({})
  mock.testNotification.mockResolvedValue({})
})

describe('Nextcloud 26 notification recipients', () => {
  it('searches a person, selects the exact user and sends a test message', async () => {
    const wrapper = mount(SettingsNotificationsTab)
    await flushPromises()

    const searchInput = wrapper.get('input[placeholder="Введите ФИО"]')
    await searchInput.setValue('Иванов')
    const searchButton = wrapper.findAll('button').find((button) => button.text() === 'Найти')!
    await searchButton.trigger('click')
    await flushPromises()

    expect(mock.searchUsers).toHaveBeenCalledWith('Иванов')
    expect(wrapper.text()).toContain('Иванов Иван Иванович')

    const result = wrapper.findAll('[role="option"]').find((item) => item.text().includes('ivanov'))!
    await result.trigger('click')
    expect(wrapper.text()).toContain('Выбран: Иванов Иван Иванович (ivanov)')

    const testButton = wrapper.findAll('button').find((button) => button.text() === 'Отправить тест')!
    expect(testButton.attributes('disabled')).toBeUndefined()
    await testButton.trigger('click')
    await flushPromises()

    expect(mock.testNotification).toHaveBeenCalledWith({
      recipient_user_id: 'ivanov',
      message: 'Тестовое уведомление · Учет кадровых событий',
    })
  })

  it('does not search until at least two characters are entered', async () => {
    const wrapper = mount(SettingsNotificationsTab)
    await flushPromises()

    await wrapper.get('input[placeholder="Введите ФИО"]').setValue('И')
    const searchButton = wrapper.findAll('button').find((button) => button.text() === 'Найти')!
    await searchButton.trigger('click')

    expect(mock.searchUsers).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Введите минимум 2 символа ФИО')
  })
})
