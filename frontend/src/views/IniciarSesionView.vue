<script setup lang="ts">
/**
 * P17 · Iniciar sesión y segundo factor.
 *
 * Los errores no distinguen «ese correo no existe» de «esa contraseña no es»: el
 * mensaje lo da la API y aquí no se adorna. La cuenta bloqueada por intentos tiene su
 * propio estado, con qué hacer a continuación.
 */
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { entrar, responderMfa } from '@/api/auth'
import { ErrorApi } from '@/api/http'
import { useCuentaStore } from '@/stores/cuenta'

const router = useRouter()
const ruta = useRoute()
const cuenta = useCuentaStore()

const email = ref(String(ruta.query.correo ?? ''))
const password = ref('')
const codigo = ref('')
const sesionMfa = ref('')
const error = ref('')
const bloqueada = ref(false)
const enviando = ref(false)

async function terminar() {
  await cuenta.cargar()
  router.push(cuenta.mfaPendiente ? { name: 'perfil' } : { name: 'estado' })
}

async function acceder() {
  error.value = ''
  bloqueada.value = false
  enviando.value = true
  try {
    const sesion = await entrar(email.value, password.value)
    if (sesion.mfa_requerido) {
      sesionMfa.value = sesion.sesion
      return
    }
    await terminar()
  } catch (e) {
    if (e instanceof ErrorApi) {
      error.value = e.message
      bloqueada.value = e.estado === 429
    } else {
      error.value = 'No hemos podido entrar.'
    }
  } finally {
    enviando.value = false
  }
}

async function verificar() {
  error.value = ''
  enviando.value = true
  try {
    await responderMfa(email.value, codigo.value, sesionMfa.value)
    await terminar()
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido verificar el código.'
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <section class="entrar">
    <h1>Entrar en BLENS</h1>

    <form v-if="!sesionMfa" @submit.prevent="acceder">
      <label>
        Correo
        <input v-model="email" type="email" required autocomplete="username" />
      </label>
      <label>
        Contraseña
        <input v-model="password" type="password" required autocomplete="current-password" />
      </label>
      <p v-if="bloqueada" class="bloqueada" role="alert">
        {{ error }} Por seguridad hemos parado los intentos un rato. Si no recuerdas la
        contraseña, cámbiala y entras en un minuto.
      </p>
      <p v-else-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="enviando">{{ enviando ? 'Entrando…' : 'Entrar' }}</button>
      <RouterLink :to="{ name: 'recuperar', query: { correo: email } }">
        No recuerdo mi contraseña
      </RouterLink>
    </form>

    <form v-else @submit.prevent="verificar">
      <p>Abre tu aplicación de códigos y escribe el que aparece para BLENS.</p>
      <label>
        Código de seis cifras
        <input v-model="codigo" required inputmode="numeric" autocomplete="one-time-code" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="enviando">Verificar</button>
      <p class="ayuda">
        ¿Has perdido el móvil? No hay códigos de recuperación: pídele a quien tenga la
        propiedad de tu organización que te lo restablezca.
      </p>
    </form>
  </section>
</template>

<style scoped>
.entrar {
  max-width: 420px;
  margin: 0 auto;
  padding: 48px 16px;
}
form {
  display: grid;
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 24px;
}
label {
  display: grid;
  gap: 4px;
  font-weight: 500;
}
input {
  font: inherit;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radio);
}
button {
  background: var(--brand-700);
  color: #fff;
  border: 0;
  border-radius: var(--radio);
  padding: 12px 16px;
  font-size: 1rem;
  cursor: pointer;
}
.error {
  color: var(--nivel-alto-fg);
  margin: 0;
}
.bloqueada {
  background: var(--nivel-medio-bg);
  color: var(--nivel-medio-fg);
  border-radius: var(--radio);
  padding: 12px;
  margin: 0;
}
.ayuda {
  color: var(--ink-600);
  font-size: 0.9rem;
  margin: 0;
}
</style>
