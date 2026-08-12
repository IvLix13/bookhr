import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UserForm from '@/components/settings/UserForm.vue'

vi.mock('@/api/client', () => ({
  api: {
    roles: vi.fn(async () => [
      { id: 1, name: 'admin' },
      { id: 2, name: 'hr' },
      { id: 3, name: 'viewer' },
    ]),
    createUser: vi.fn(async () => ({})),
    updateUser: vi.fn(async () => ({})),
    resetUserPassword: vi.fn(async () => ({})),
  },
}))

describe('UserForm', () => {
  it('requires credentials for new local user', async () => {
    const wrapper = mount(UserForm, { props: { initial: null } })
    await flushPromises()
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.text()).toContain('Заполните логин, пароль и ФИО')
  })
})
