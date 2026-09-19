import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { quienSoy, salir, type Yo } from '@/api/auth'

/**
 * Quién está usando BLENS. La sesión vive en una cookie HttpOnly, así que aquí no se
 * guarda ningún token: solo lo que la API dice de quien llama.
 */
export const useCuentaStore = defineStore('cuenta', () => {
  const yo = ref<Yo | null>(null)
  const cargando = ref(false)
  /** Falso mientras no se ha preguntado: distinto de «no hay sesión». */
  const comprobado = ref(false)

  const autenticado = computed(() => yo.value !== null)
  const membresia = computed(() => yo.value?.membresias[0] ?? null)
  const rol = computed(() => membresia.value?.role ?? '')
  /** Tiene rol de los que exigen segundo factor y aún no lo ha activado. */
  const mfaPendiente = computed(() => yo.value?.mfa_pendiente ?? false)

  async function cargar() {
    cargando.value = true
    try {
      yo.value = await quienSoy()
    } catch {
      yo.value = null
    } finally {
      cargando.value = false
      comprobado.value = true
    }
  }

  async function cerrarSesion() {
    await salir().catch(() => undefined)
    yo.value = null
    comprobado.value = true
  }

  return { yo, cargando, comprobado, autenticado, membresia, rol, mfaPendiente, cargar, cerrarSesion }
})
