import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ImportWorkflow from '@/components/ImportWorkflow.vue'
import { useAuthStore } from '@/stores/auth'
import type { ImportJob } from '@/types'

const unknownJob: ImportJob = {
  id: 11,
  filename: 'employees.xlsx',
  import_type: 'employees',
  status: 'validated',
  summary: { create: 1 },
  unknown_grades: [{ name: 'Лид', count: 2 }],
  error_message: null,
  created_at: null,
  rows: [
    {
      id: 21,
      row_number: 2,
      action: 'create',
      person_uuid: null,
      full_name: 'Новиков Новик Новикович',
      errors: null,
      warnings: ['Грейд «Лид» не найден в справочнике'],
    },
  ],
}

const { uploadImport, confirmImport, revalidateImport } = vi.hoisted(() => ({
  uploadImport: vi.fn(async () => unknownJob),
  confirmImport: vi.fn(async () => ({ ...unknownJob, status: 'confirmed', unknown_grades: [] })),
  revalidateImport: vi.fn(async () => ({ ...unknownJob, unknown_grades: [] })),
}))

vi.mock('@/api/client', () => ({
  api: {
    uploadImport,
    confirmImport,
    revalidateImport,
    downloadImportTemplate: vi.fn(async () => undefined),
  },
}))

describe('ImportWorkflow unknown grades', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    uploadImport.mockClear()
    confirmImport.mockClear()
    revalidateImport.mockClear()
  })

  async function mountWorkflow(role: 'admin' | 'hr' = 'admin') {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
    const wrapper = mount(ImportWorkflow, {
      props: { importType: 'employees' },
      global: {
        stubs: {
          DataTable: { template: '<div class="table-stub" />' },
          ImportSummary: { template: '<div class="summary-stub" />' },
          GradeCreateModal: {
            props: ['open', 'initialName'],
            template: '<div v-if="open" class="grade-modal-stub" />',
          },
        },
      },
    })

    const file = new File(['xlsx'], 'employees.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    wrapper.findComponent({ name: 'ImportDropzone' }).vm.$emit('select', file)
    await flushPromises()
    const checkButton = wrapper.findAll('button').find((button) => button.text().includes('Проверить файл'))
    expect(checkButton).toBeTruthy()
    await checkButton!.trigger('click')
    await flushPromises()
    return wrapper
  }

  it('blocks confirm until unknown grades are skipped', async () => {
    const wrapper = await mountWorkflow('admin')

    expect(wrapper.text()).toContain('Неизвестные грейды')
    expect(wrapper.text()).toContain('Лид')
    expect(wrapper.text()).toContain('Завести в справочнике')
    expect(wrapper.text()).toContain('Разрешите неизвестные грейды перед подтверждением импорта.')

    const confirmButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Подтвердить импорт'))
    expect(confirmButton?.attributes('disabled')).toBeDefined()

    await wrapper.get('.unknown-actions .btn.secondary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Разрешите неизвестные грейды перед подтверждением импорта.')
    expect(confirmButton?.attributes('disabled')).toBeUndefined()
  })

  it('shows create action for hr', async () => {
    const wrapper = await mountWorkflow('hr')
    expect(wrapper.text()).toContain('Неизвестные грейды')
    expect(wrapper.text()).toContain('Завести в справочнике')
    expect(wrapper.text()).not.toContain('Завести грейд может только администратор')
  })
})
