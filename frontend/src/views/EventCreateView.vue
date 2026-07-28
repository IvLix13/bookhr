<script setup lang="ts">
import { ref } from 'vue'
import EventForm from '@/components/EventForm.vue'
import { formatLocalDate } from '@/utils/dates'

const message = ref('')

function onCreated() {
  message.value = 'Событие создано'
}
</script>

<template>
  <section class="card page">
    <header><h2>Добавить событие</h2></header>
    <EventForm :initial-date="formatLocalDate(new Date())" @created="onCreated" />
    <p v-if="message">{{ message }}</p>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}

p {
  margin-top: 1rem;
}
</style>
