<script setup lang="ts">
/**
 * P20 · Mi perfil y seguridad.
 *
 * Incluye «mi actividad», que es lo que convierte el registro encadenado en algo útil
 * para su dueño y no solo en un requisito de op.exp.8.
 */
import { onMounted, ref } from 'vue'

import { confirmarMfa, empezarMfa, miActividad, type Actividad, type MfaAlta } from '@/api/auth'
import { ErrorApi } from '@/api/http'
import { useCuentaStore } from '@/stores/cuenta'

const cuenta = useCuentaStore()
const alta = ref<MfaAlta | null>(null)
const codigo = ref('')
const error = ref('')
const aviso = ref('')
const actividad = ref<Actividad[]>([])

onMounted(async () => {
  if (!cuenta.comprobado) await cuenta.cargar()
  actividad.value = await miActividad().catch(() => [])
})

async function empezar() {
  error.value = ''
  try {
    alta.value = await empezarMfa()
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido empezar.'
  }
}

async function confirmar() {
  error.value = ''
  try {
    await confirmarMfa(codigo.value)
    alta.value = null
    aviso.value = 'Verificación en dos pasos activada.'
    await cuenta.cargar()
    actividad.value = await miActividad().catch(() => [])
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'El código no es correcto.'
  }
}
</script>

<template>
  <section class="perfil">
    <h1>Mi perfil y seguridad</h1>

    <dl v-if="cuenta.yo">
      <div><dt>Correo</dt><dd>{{ cuenta.yo.email }}</dd></div>
      <div v-if="cuenta.yo.nombre"><dt>Nombre</dt><dd>{{ cuenta.yo.nombre }}</dd></div>
      <div v-if="cuenta.membresia">
        <dt>Organización</dt>
        <dd>{{ cuenta.membresia.organizacion }} · {{ cuenta.membresia.role_nombre }}</dd>
      </div>
    </dl>

    <h2>Verificación en dos pasos</h2>
    <p v-if="cuenta.mfaPendiente" class="pendiente" role="alert">
      Tu rol la exige. Hasta que la actives no podemos dejarte operar: es cosa de un minuto.
    </p>
    <p v-else-if="cuenta.yo?.mfa_activado" class="activa" role="status">
      Activada. Cada vez que entres te pediremos el código.
    </p>

    <template v-if="!cuenta.yo?.mfa_activado">
      <button v-if="!alta" type="button" @click="empezar">Activar la verificación</button>
      <div v-else class="alta">
        <p>
          Escanea este código con tu aplicación de códigos, o escribe la clave a mano si no
          puedes escanear.
        </p>
        <p class="secreto"><code>{{ alta.secreto }}</code></p>
        <p><a :href="alta.otpauth_uri">Abrir en la aplicación de códigos</a></p>
        <p class="aviso-mfa">{{ alta.aviso }}</p>
        <form @submit.prevent="confirmar">
          <label>
            Código de seis cifras
            <input v-model="codigo" required inputmode="numeric" autocomplete="one-time-code" />
          </label>
          <button type="submit">Confirmar</button>
        </form>
      </div>
    </template>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="aviso" class="activa" role="status">{{ aviso }}</p>

    <h2>Mi actividad</h2>
    <p v-if="!actividad.length">Todavía no hay nada registrado.</p>
    <ul v-else class="actividad">
      <li v-for="(e, i) in actividad" :key="i">
        <time>{{ new Date(e.fecha).toLocaleString('es-ES') }}</time>
        <span>{{ e.accion }}</span>
      </li>
    </ul>
    <p class="pie">
      Este registro es tuyo y no se puede modificar: cada entrada encadena con la anterior.
    </p>
  </section>
</template>

<style scoped>
.perfil {
  max-width: var(--col);
  margin: 0 auto;
  padding: 32px 16px;
}
dl {
  display: grid;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--line);
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
.pendiente {
  background: var(--nivel-medio-bg);
  color: var(--nivel-medio-fg);
  border-radius: var(--radio);
  padding: 12px;
}
.activa {
  color: var(--nivel-bajo-fg);
}
.alta {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 16px;
}
.secreto code {
  font-size: 1.1rem;
  letter-spacing: 0.1em;
  background: var(--surface-alt);
  padding: 6px 10px;
  border-radius: 4px;
}
.aviso-mfa {
  color: var(--ink-600);
  font-size: 0.9rem;
}
form {
  display: grid;
  gap: 12px;
  max-width: 280px;
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
  font: inherit;
  background: var(--brand-700);
  color: #fff;
  border: 0;
  border-radius: var(--radio);
  padding: 10px 14px;
  cursor: pointer;
}
.actividad {
  list-style: none;
  padding: 0;
  display: grid;
  gap: 4px;
}
.actividad li {
  display: flex;
  gap: 12px;
  border-bottom: 1px solid var(--line);
  padding: 6px 0;
}
time {
  color: var(--ink-600);
  min-width: 190px;
}
.pie {
  color: var(--ink-600);
  font-size: 0.9rem;
}
.error {
  color: var(--nivel-alto-fg);
}
</style>
