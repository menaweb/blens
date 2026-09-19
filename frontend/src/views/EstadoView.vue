<script setup lang="ts">
import { onMounted } from 'vue'

import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
onMounted(() => session.comprobarApi())
</script>

<template>
  <section>
    <h1>BLENS</h1>
    <p v-if="session.error" role="alert">Sin conexión con la API: {{ session.error }}</p>
    <p v-else-if="session.estado">
      API {{ session.estado.version }} · estado {{ session.estado.status }} · base de datos
      {{ session.estado.database }}
    </p>
    <p v-else>Comprobando la API…</p>
  </section>
</template>
