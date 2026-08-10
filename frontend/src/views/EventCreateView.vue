<script setup lang="ts">
import EventForm from '@/components/EventForm.vue'
import { useToast } from '@/composables/useToast'
import { formatLocalDate } from '@/utils/dates'

const toast = useToast()

function onCreated() {
  toast.success('Событие создано')
}
</script>

<template>
  <section class="card page">
    <header><h2>Добавить событие</h2></header>
    <EventForm :initial-date="formatLocalDate(new Date())" @created="onCreated" />
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
