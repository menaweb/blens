import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getHealth, type Health } from '@/api/client'

/** Estado de la sesión. En F0 solo comprueba que la API responde. */
export const useSessionStore = defineStore('session', () => {
  const estado = ref<Health | null>(null)
  const error = ref<string | null>(null)

  async function comprobarApi() {
    error.value = null
    try {
      estado.value = await getHealth()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error desconocido'
    }
  }

  return { estado, error, comprobarApi }
})
