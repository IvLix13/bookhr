<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { GradeRow } from '@/types'

const rows = ref<GradeRow[]>([])

onMounted(async () => {
  rows.value = (await api.grades()) as GradeRow[]
})
</script>

<template>
  <section class="card page">
    <header><h2>Грейды</h2></header>
    <table class="table">
      <thead>
        <tr>
          <th>ФИО</th>
          <th>Текущий грейд</th>
          <th>Дата выдачи</th>
          <th>Следующий грейд</th>
          <th>Дата доступности</th>
          <th>Осталось дней</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.employment_id">
          <td>{{ row.full_name }}</td>
          <td>{{ row.grade?.name ?? '—' }}</td>
          <td>{{ row.grade_date ?? '—' }}</td>
          <td>{{ row.next_grade?.name ?? '—' }}</td>
          <td>{{ row.eligible_date ?? '—' }}</td>
          <td>{{ row.days_left ?? '—' }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.page { padding: 1rem; }
</style>
