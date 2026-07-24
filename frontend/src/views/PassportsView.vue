<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { PassportRow } from '@/types'

const rows = ref<PassportRow[]>([])

onMounted(async () => {
  rows.value = (await api.passports()) as PassportRow[]
})
</script>

<template>
  <section class="card page">
    <header><h2>Паспорта</h2></header>
    <table class="table">
      <thead>
        <tr>
          <th>ФИО</th>
          <th>Действителен до</th>
          <th>Осталось дней</th>
          <th>Статус</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.person_uuid">
          <td>{{ row.full_name }}</td>
          <td>{{ row.valid_until ?? '—' }}</td>
          <td>{{ row.days_left ?? '—' }}</td>
          <td>
            <span
              class="badge"
              :class="{
                warning: row.status === 'requires_preparation',
                danger: row.status === 'expired',
                success: row.status === 'ok',
              }"
            >
              {{ row.status ?? '—' }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.page { padding: 1rem; }
</style>
