<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import type { ImportJob } from '@/types'

const file = ref<File | null>(null)
const job = ref<ImportJob | null>(null)
const message = ref('')

async function upload() {
  if (!file.value) return
  message.value = ''
  job.value = (await api.uploadImport(file.value)) as ImportJob
}

async function confirm() {
  if (!job.value) return
  job.value = (await api.confirmImport(job.value.id, {})) as ImportJob
  message.value = 'Импорт подтверждён'
}
</script>

<template>
  <section class="card page">
    <header><h2>Импорт из Excel</h2></header>
    <div class="actions">
      <input type="file" accept=".xlsx" @change="(e) => file = (e.target as HTMLInputElement).files?.[0] ?? null" />
      <button class="btn" :disabled="!file" @click="upload">Проверить файл</button>
      <button class="btn secondary" :disabled="!job || job.status !== 'validated'" @click="confirm">
        Подтвердить импорт
      </button>
    </div>
    <p v-if="message">{{ message }}</p>
    <div v-if="job" class="summary">
      <p>Файл: {{ job.filename }}</p>
      <p>Статус: {{ job.status }}</p>
      <pre>{{ job.summary }}</pre>
      <table class="table">
        <thead>
          <tr>
            <th>Строка</th>
            <th>Действие</th>
            <th>UUID</th>
            <th>Ошибки</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in job.rows" :key="row.id">
            <td>{{ row.row_number }}</td>
            <td>{{ row.action }}</td>
            <td>{{ row.person_uuid ?? '—' }}</td>
            <td>{{ row.errors?.join(', ') ?? row.warnings?.join(', ') ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}
</style>
