<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { ContractRow } from '@/types'

const rows = ref<ContractRow[]>([])

onMounted(async () => {
  rows.value = (await api.contracts()) as ContractRow[]
})
</script>

<template>
  <section class="card page">
    <header><h2>Контракты</h2></header>
    <table class="table">
      <thead>
        <tr>
          <th>ФИО</th>
          <th>Окончание</th>
          <th>Осталось дней</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.full_name }}</td>
          <td>{{ row.end_date }}</td>
          <td>
            <span class="badge" :class="row.days_left <= 120 ? 'warning' : ''">{{ row.days_left }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.page { padding: 1rem; }
</style>
