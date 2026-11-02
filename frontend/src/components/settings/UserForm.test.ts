import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import UserForm from '@/components/settings/UserForm.vue'

vi.mock('@/api/client', () => ({
  api: {
    employees: vi.fn(async () => ({ items: [{ id: 151, full_name: 'Петров Пётр', title: 'Специалист', formal_department_short_name: '01' }], pages: 2 })),
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
  it('saves an explicit employment binding and supports later pages', async () => {
    const wrapper = mount(UserForm)
    await flushPromises()
    await wrapper.find('input[autocomplete="off"]').setValue('viewer_new')
    await wrapper.find('input[type="password"]').setValue('StrongPass123')
    await wrapper.findAll('input')[2]!.setValue('Петров Пётр')
    await wrapper.find('select[aria-label="Сотрудник для календаря отдела"]').setValue(151)
    await wrapper.findAll('button').find(b => b.text() === 'Далее')!.trigger('click')
    await flushPromises()
    expect(api.employees).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(api.createUser).toHaveBeenLastCalledWith(expect.objectContaining({ employment_id: 151 }))
  })

})
