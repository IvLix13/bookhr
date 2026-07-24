<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'

const form = ref({
  title: '',
  event_type: 'manual',
  event_date: new Date().toISOString().slice(0, 10),
  description: '',
})
const message = ref('')

async function submit() {
  await api.createEvent(form.value)
  message.value = 'Событие создано'
  form.value.title = ''
  form.value.description = ''
}
</script>

<template>
  <section class="card page">
    <header><h2>Добавить событие</h2></header>
    <form class="form" @submit.prevent="submit">
      <label>Название<input v-model="form.title" required /></label>
      <label>
        Тип
        <select v-model="form.event_type">
          <option value="contract">Договор</option>
          <option value="grade">Грейд</option>
          <option value="award">Поощрение</option>
          <option value="report">Рапорт</option>
          <option value="passport">Паспорт</option>
          <option value="manual">Другое</option>
        </select>
      </label>
      <label>Дата<input v-model="form.event_date" type="date" required /></label>
      <label>Описание<textarea v-model="form.description" rows="4" /></label>
      <button class="btn" type="submit">Сохранить</button>
      <p v-if="message">{{ message }}</p>
    </form>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}

.form {
  display: grid;
  gap: 0.85rem;
  max-width: 520px;
}

label {
  display: grid;
  gap: 0.35rem;
}

input,
select,
textarea {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem 0.9rem;
}
</style>
