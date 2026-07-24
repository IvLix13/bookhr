<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Grade } from '@/types'

const grades = ref<Grade[]>([])

onMounted(async () => {
  grades.value = (await api.gradeCatalog()) as Grade[]
})
</script>

<template>
  <section class="card page">
    <header><h2>Справочник грейдов</h2></header>
    <table class="table">
      <thead>
        <tr>
          <th>Название</th>
          <th>Ранг</th>
          <th>Мин. месяцев</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="grade in grades" :key="grade.id">
          <td>{{ grade.name }}</td>
          <td>{{ grade.rank }}</td>
          <td>{{ grade.min_months }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.page { padding: 1rem; }
</style>
