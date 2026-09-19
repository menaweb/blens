<script setup lang="ts">
/**
 * P18 · Aceptar una invitación.
 *
 * La ve alguien que no conoce BLENS y a quien un compañero ha metido en esto: antes de
 * pedirle nada, se le dice quién le invita, a qué organización y con qué papel. Los tres
 * estados malos (caducada, usada, revocada) llegan como 410 y salen con su salida.
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { aceptarInvitacion, verInvitacion, type Invitacion } from '@/api/auth'
import { ErrorApi } from '@/api/http'

const ruta = useRoute()
const router = useRouter()
const token = String(ruta.params.token ?? '')

const invitacion = ref<Invitacion | null>(null)
const noSirve = ref('')
const password = ref('')
const nombre = ref('')
const error = ref('')
const enviando = ref(false)

onMounted(async () => {
  try {
    invitacion.value = await verInvitacion(token)
  } catch (e) {
    noSirve.value =
      e instanceof ErrorApi ? e.message : 'No hemos podido abrir esta invitación.'
  }
})

async function aceptar() {
  error.value = ''
  enviando.value = true
  try {
    await aceptarInvitacion(token, password.value, nombre.value)
    router.push({ name: 'entrar', query: { correo: invitacion.value?.email } })
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido aceptar la invitación.'
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <section class="invitacion">
    <div v-if="noSirve" class="caducada" role="alert">
      <h1>Esta invitación ya no vale</h1>
      <p>{{ noSirve }}</p>
      <p>Pídele a quien te invitó que te mande otra: se hace en un clic.</p>
    </div>

    <template v-else-if="invitacion">
      <h1>Te han invitado a {{ invitacion.organizacion }}</h1>
      <dl>
        <div><dt>Organización</dt><dd>{{ invitacion.organizacion }}</dd></div>
        <div><dt>Tu papel</dt><dd>{{ invitacion.role_nombre }}</dd></div>
        <div v-if="invitacion.invitado_por">
          <dt>Te invita</dt>
          <dd>{{ invitacion.invitado_por }}</dd>
        </div>
        <div><dt>Tu correo</dt><dd>{{ invitacion.email }}</dd></div>
      </dl>
      <p class="que-es">
        BLENS es donde tu organización lleva el cumplimiento del Esquema Nacional de
        Seguridad. Como {{ invitacion.role_nombre.toLowerCase() }}, te pedirán responder
        preguntas sobre el sistema y aportar evidencias.
      </p>

      <form @submit.prevent="aceptar">
        <template v-if="!invitacion.tiene_cuenta">
          <label>
            Tu nombre
            <input v-model="nombre" autocomplete="name" />
          </label>
          <label>
            Elige una contraseña
            <input
              v-model="password"
              type="password"
              required
              minlength="12"
              autocomplete="new-password"
            />
            <small>Doce caracteres o más.</small>
          </label>
        </template>
        <p v-else>Ya tienes cuenta en BLENS, así que no hace falta contraseña nueva.</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" :disabled="enviando">Aceptar la invitación</button>
      </form>
    </template>

    <p v-else>Abriendo la invitación…</p>
  </section>
</template>

<style scoped>
.invitacion {
  max-width: var(--col);
  margin: 0 auto;
  padding: 48px 16px;
}
dl {
  display: grid;
  gap: 8px;
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radio);
  padding: 16px;
}
dl div {
  display: flex;
  gap: 12px;
}
dt {
  color: var(--ink-600);
  min-width: 140px;
}
dd {
  margin: 0;
  font-weight: 500;
}
.que-es {
  color: var(--ink-600);
}
.caducada {
  background: var(--surface);
  border-left: 3px solid var(--nivel-medio-fg);
  padding: 16px;
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
