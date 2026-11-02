<script setup lang="ts">
import { computed, onMounted, ref, watch, onUnmounted } from 'vue'
import { api } from '@/api/client'
import type { RoleItem, UserListItem, UserRole } from '@/types'

const props = defineProps<{
  initial?: UserListItem | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const employeeId = ref<number | null>(props.initial?.employment_id ?? null)
const employeeQuery = ref('')
const employeePage = ref(1)
const employeePages = ref(0)
const employeeOptions = ref<Array<{ id: number; full_name: string; title?: string; formal_department_short_name?: string }>>([])
const searchError = ref('')
let searchVersion = 0
let searchTimer: ReturnType<typeof setTimeout> | undefined
async function searchEmployees() {
  const version = ++searchVersion
  try {
    const result = await api.employees({ q: employeeQuery.value, page: employeePage.value, per_page: 20, status: 'active' })
    if (version !== searchVersion) return
    employeeOptions.value = result.items as typeof employeeOptions.value
    employeePages.value = result.pages
    searchError.value = ''
  } catch { if (version === searchVersion) searchError.value = 'Не удалось загрузить сотрудников' }
}
watch(employeeQuery, () => {
  employeePage.value = 1
  ++searchVersion
  clearTimeout(searchTimer)
  searchTimer = setTimeout(searchEmployees, 350)
})
watch(employeePage, searchEmployees)
onUnmounted(() => { clearTimeout(searchTimer); ++searchVersion })
const roles = ref<RoleItem[]>([])
const submitting = ref(false)
const error = ref('')
const resetPassword = ref('')

const form = ref({
  username: '',
  password: '',
  full_name: '',
  role: 'viewer' as UserRole,
})

const isEdit = computed(() => Boolean(props.initial))
const isLocal = computed(() => props.initial?.auth_source === 'local')

watch(
  () => props.initial,
  (value) => {
    resetPassword.value = ''
    employeeId.value = value?.employment_id ?? null
    if (!value) {
      form.value = {
        username: '',
        password: '',
        full_name: '',
        role: 'viewer',
      }
      return
    }
    form.value = {
      username: value.username,
      password: '',
      full_name: value.full_name,
      role: value.role,
    }
  },
  { immediate: true },
)

onMounted(async () => {
  roles.value = (await api.roles()) as RoleItem[]
  void searchEmployees()
})

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    if (props.initial) {
      await api.updateUser(props.initial.id, {
        employment_id: employeeId.value,
        full_name: form.value.full_name.trim(),
        role: form.value.role,
      })
      if (resetPassword.value && isLocal.value) {
        await api.resetUserPassword(props.initial.id, resetPassword.value)
      }
    } else {
      if (!form.value.username.trim() || !form.value.password || !form.value.full_name.trim()) {
        throw new Error('Заполните логин, пароль и ФИО')
      }
      await api.createUser({
        username: form.value.username.trim(),
        password: form.value.password,
        employment_id: employeeId.value,
        full_name: form.value.full_name.trim(),
        role: form.value.role,
      })
    }
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось сохранить пользователя'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form card" @submit.prevent="submit">
    <header class="form-header">
      <h3>{{ isEdit ? 'Редактировать пользователя' : 'Новый пользователь' }}</h3>
      <p v-if="initial">
        {{ initial.username }} · {{ initial.auth_source === 'ldap' ? 'LDAP' : 'Локальный' }}
      </p>
    </header>

    <label v-if="!isEdit">
      Логин
      <input v-model="form.username" required autocomplete="off" />
    </label>

    <label v-if="!isEdit">
      Пароль
      <input v-model="form.password" type="password" required autocomplete="new-password" />
    </label>

    <label>
      ФИО
      <input v-model="form.full_name" required />
    </label>

    <label>
      Роль
      <select v-model="form.role" required>
        <option v-for="role in roles" :key="role.id" :value="role.name">
          {{ role.name }}
        </option>
      </select>
    </label>

    <fieldset>
      <legend>Сотрудник для календаря отдела</legend>
      <label>Поиск сотрудника<input v-model="employeeQuery" type="search" placeholder="ФИО" /></label>
      <select v-model="employeeId" aria-label="Сотрудник для календаря отдела">
        <option :value="null">Не привязан</option>
        <option v-if="employeeId && !employeeOptions.some(e => e.id === employeeId)" :value="employeeId">Текущая привязка №{{ employeeId }}</option>
        <option v-for="employee in employeeOptions" :key="employee.id" :value="employee.id">{{ employee.full_name }} · {{ employee.title }} · {{ employee.formal_department_short_name || 'Отдел не указан' }}</option>
      </select>
      <div class="actions"><button type="button" class="btn secondary" :disabled="employeePage <= 1" @click="employeePage--">Назад</button><span>{{ employeePage }} / {{ employeePages || 1 }}</span><button type="button" class="btn secondary" :disabled="employeePage >= employeePages" @click="employeePage++">Далее</button></div>
      <p v-if="searchError" role="alert">{{ searchError }}</p>
    </fieldset>
    <label v-if="isEdit && isLocal">
      Новый пароль
      <input
        v-model="resetPassword"
        type="password"
        autocomplete="new-password"
        placeholder="Оставьте пустым, если не меняете"
      />
    </label>

    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : isEdit ? 'Сохранить изменения' : 'Создать пользователя' }}
      </button>
      <button v-if="isEdit" class="btn secondary" type="button" @click="emit('cancel')">
        Отмена
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.form {
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}

.form-header h3 {
  margin: 0;
}

.form-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

label {
  display: grid;
  gap: 0.35rem;
}

input,
select {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.error {
  color: var(--danger);
  margin: 0;
}
</style>
