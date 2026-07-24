<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Employee, Paginated } from '@/types'

const employees = ref<Employee[]>([])
const loading = ref(true)

onMounted(async () => {
  const data = (await api.employees('?per_page=200')) as Paginated<Employee>
  employees.value = data.items
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header>
      <h2>Общая таблица сотрудников</h2>
    </header>
    <div v-if="loading">Загрузка...</div>
    <div v-else class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>№</th>
            <th>ФИО</th>
            <th>Должность</th>
            <th>Грейд по должности</th>
            <th>Фактический грейд</th>
            <th>ВУЗ</th>
            <th>Окончание договора</th>
            <th>Дата грейда</th>
            <th>Начало работы</th>
            <th>Стаж</th>
            <th>Паспорт</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(employee, index) in employees" :key="employee.id">
            <td>{{ index + 1 }}</td>
            <td>{{ employee.full_name }}</td>
            <td>{{ employee.title }}</td>
            <td>{{ employee.position_grade?.name ?? '—' }}</td>
            <td>{{ employee.actual_grade?.name ?? '—' }}</td>
            <td>{{ employee.has_university ? 'Да' : 'Нет' }}</td>
            <td>{{ employee.contract_end ?? '—' }}</td>
            <td>{{ employee.grade_date ?? '—' }}</td>
            <td>{{ employee.hire_date }}</td>
            <td>{{ employee.tenure_years }} лет</td>
            <td>
              <span class="badge" :class="employee.passport_status">{{ employee.passport_until ?? '—' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}

.table-wrap {
  overflow: auto;
}
</style>
