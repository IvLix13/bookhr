<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { TenureRow } from '@/types'

const rows = ref<TenureRow[]>([])

onMounted(async () => {
  rows.value = (await api.tenure()) as TenureRow[]
})
</script>

<template>
  <section class="card page">
    <header><h2>Поощрения</h2></header>
    <table class="table">
      <thead>
        <tr>
          <th>ФИО</th>
          <th>Стаж</th>
          <th>10 лет</th>
          <th>15 лет</th>
          <th>20 лет</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.employment_id">
          <td>{{ row.full_name }}</td>
          <td>{{ row.tenure_years }}</td>
          <td>{{ row.awards['10']?.is_received ? 'Получено' : '—' }}</td>
          <td>{{ row.awards['15']?.is_received ? 'Получено' : '—' }}</td>
          <td>{{ row.awards['20']?.is_received ? 'Получено' : '—' }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.page { padding: 1rem; }
</style>
