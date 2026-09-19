<script setup lang="ts">
/** P17 · Recuperar contraseña. Misma respuesta exista o no la cuenta. */
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { cambiarContrasena, pedirCodigoContrasena } from '@/api/auth'
import { ErrorApi } from '@/api/http'

const ruta = useRoute()
const router = useRouter()

const email = ref(String(ruta.query.correo ?? ''))
const codigo = ref('')
const password = ref('')
const paso = ref<'pedir' | 'cambiar'>('pedir')
const error = ref('')
const enviando = ref(false)

async function pedirCodigo() {
  enviando.value = true
  await pedirCodigoContrasena(email.value).catch(() => undefined)
  enviando.value = false
  paso.value = 'cambiar'
}

async function cambiar() {
  error.value = ''
  enviando.value = true
  try {
    await cambiarContrasena(email.value, codigo.value, password.value)
    router.push({ name: 'entrar', query: { correo: email.value } })
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido cambiar la contraseña.'
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <section class="recuperar">
    <h1>Cambiar la contraseña</h1>

    <form v-if="paso === 'pedir'" @submit.prevent="pedirCodigo">
      <label>
        Correo
        <input v-model="email" type="email" required autocomplete="username" />
      </label>
      <button type="submit" :disabled="enviando">Enviarme un código</button>
    </form>

    <form v-else @submit.prevent="cambiar">
      <p>Si ese correo tiene cuenta, le hemos enviado un código. Escríbelo aquí.</p>
      <label>
        Código
        <input v-model="codigo" required inputmode="numeric" autocomplete="one-time-code" />
      </label>
      <label>
        Nueva contraseña
        <input
          v-model="password"
          type="password"
          required
          minlength="12"
          autocomplete="new-password"
        />
        <small>Doce caracteres o más.</small>
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="enviando">Cambiar la contraseña</button>
    </form>
  </section>
</template>

<style scoped>
.recuperar {
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
small {
  color: var(--ink-600);
  font-weight: 400;
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
</style>
