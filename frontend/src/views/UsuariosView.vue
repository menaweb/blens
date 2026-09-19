<script setup lang="ts">
/**
 * P19 · Usuarios y roles.
 *
 * Las acciones delicadas piden confirmación explicando la consecuencia, no un «¿seguro?».
 * Y cuando el sistema impide algo —dejar la organización sin propietario—, se enseña el
 * motivo que da la API en lugar de limitarse a desactivar un botón.
 */
import { computed, onMounted, ref } from 'vue'

import {
  cambiarRol,
  invitar,
  pedirInvitaciones,
  pedirMiembros,
  restablecerMfaDe,
  revocarInvitacion,
  revocarMiembro,
  transferirPropiedad,
  type InvitacionPendiente,
  type Miembro,
} from '@/api/auth'
import { ErrorApi } from '@/api/http'

const ROLES = [
  ['PROPIETARIO', 'Propietario'],
  ['RSEG', 'Responsable de Seguridad'],
  ['TECNICO', 'Técnico'],
  ['COLABORADOR', 'Colaborador de bloque'],
  ['DIRECCION', 'Dirección'],
  ['AUDITOR', 'Auditor'],
  ['CONSULTOR', 'Consultor'],
] as const

const miembros = ref<Miembro[]>([])
const invitaciones = ref<InvitacionPendiente[]>([])
const error = ref('')
const aviso = ref('')
const enlaceNuevo = ref('')

const nuevoEmail = ref('')
const nuevoRol = ref<string>('TECNICO')
const dias = ref<number | null>(null)

const esTemporal = computed(() => ['AUDITOR', 'CONSULTOR'].includes(nuevoRol.value))

async function cargar() {
  error.value = ''
  try {
    ;[miembros.value, invitaciones.value] = await Promise.all([
      pedirMiembros(),
      pedirInvitaciones(),
    ])
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido cargar los usuarios.'
  }
}

onMounted(cargar)

async function ejecutar(accion: () => Promise<unknown>, exito = '') {
  error.value = ''
  aviso.value = ''
  try {
    await accion()
    aviso.value = exito
    await cargar()
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido completar la acción.'
  }
}

async function enviarInvitacion() {
  error.value = ''
  try {
    const emitida = await invitar({
      email: nuevoEmail.value,
      role: nuevoRol.value,
      membership_dias: dias.value,
    })
    enlaceNuevo.value = emitida.enlace
    nuevoEmail.value = ''
    await cargar()
  } catch (e) {
    error.value = e instanceof ErrorApi ? e.message : 'No hemos podido invitar.'
  }
}

function confirmarYRevocar(m: Miembro) {
  if (
    !confirm(
      `${m.email} perderá el acceso a BLENS inmediatamente. Lo que haya aportado se ` +
        `conserva con su autoría. ¿Seguimos?`,
    )
  )
    return
  ejecutar(() => revocarMiembro(m.id), `${m.email} ya no tiene acceso.`)
}

function confirmarYTransferir(m: Miembro) {
  if (
    !confirm(
      `${m.email} pasará a ser propietario de la organización y tú te quedarás como ` +
        `Responsable de Seguridad. Solo el propietario gestiona usuarios y facturación.`,
    )
  )
    return
  ejecutar(() => transferirPropiedad(m.id), `${m.email} es ahora el propietario.`)
}

function confirmarYRestablecerMfa(m: Miembro) {
  if (
    !confirm(
      `Vas a quitarle la verificación en dos pasos a ${m.email}. La próxima vez que ` +
        `entre tendrá que configurarla de nuevo. Queda registrado que lo has hecho tú.`,
    )
  )
    return
  ejecutar(() => restablecerMfaDe(m.id), 'Segundo factor restablecido.')
}
</script>

<template>
  <section class="usuarios">
    <h1>Usuarios y roles</h1>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="aviso" class="aviso" role="status">{{ aviso }}</p>

    <table>
      <thead>
        <tr>
          <th>Persona</th>
          <th>Rol</th>
          <th>Estado</th>
          <th>Dos pasos</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in miembros" :key="m.id">
          <td>
            <strong>{{ m.nombre || m.email }}</strong>
            <small>{{ m.email }}</small>
          </td>
          <td>
            <select
              :value="m.role"
              @change="
                ejecutar(
                  () => cambiarRol(m.id, ($event.target as HTMLSelectElement).value),
                  'Rol actualizado.',
                )
              "
            >
              <option v-for="[valor, nombre] in ROLES" :key="valor" :value="valor">
                {{ nombre }}
              </option>
            </select>
          </td>
          <td>
            <span v-if="m.estado !== 'ACTIVA'" class="revocada">{{ m.estado }}</span>
            <span v-else-if="m.expires_at" class="temporal">
              Caduca el {{ new Date(m.expires_at).toLocaleDateString('es-ES') }}
            </span>
            <span v-else>Activa</span>
          </td>
          <td>
            <span :class="m.mfa_activado ? 'si' : 'no'">
              {{ m.mfa_activado ? 'Sí' : 'Sin activar' }}
            </span>
          </td>
          <td class="acciones">
            <button type="button" @click="confirmarYTransferir(m)">Hacer propietario</button>
            <button type="button" @click="confirmarYRestablecerMfa(m)">
              Restablecer dos pasos
            </button>
            <button type="button" class="peligro" @click="confirmarYRevocar(m)">Revocar</button>
          </td>
        </tr>
      </tbody>
    </table>

    <h2>Invitar a alguien</h2>
    <form @submit.prevent="enviarInvitacion">
      <label>
        Correo
        <input v-model="nuevoEmail" type="email" required />
      </label>
      <label>
        Rol
        <select v-model="nuevoRol">
          <option v-for="[valor, nombre] in ROLES" :key="valor" :value="valor">
            {{ nombre }}
          </option>
        </select>
      </label>
      <label v-if="esTemporal">
        Días de acceso
        <input v-model.number="dias" type="number" min="1" placeholder="90" />
        <small>Los accesos de auditor y consultor caducan siempre.</small>
      </label>
      <button type="submit">Invitar</button>
    </form>

    <p v-if="enlaceNuevo" class="enlace" role="status">
      Invitación creada. Hazle llegar este enlace: <code>{{ enlaceNuevo }}</code>
    </p>

    <h2>Invitaciones pendientes</h2>
    <p v-if="!invitaciones.length">Ninguna.</p>
    <ul v-else>
      <li v-for="i in invitaciones" :key="i.id">
        {{ i.email }} · {{ i.role_nombre }} · caduca el
        {{ new Date(i.caduca).toLocaleDateString('es-ES') }}
        <button
          type="button"
          class="peligro"
          @click="ejecutar(() => revocarInvitacion(i.id), 'Invitación revocada.')"
        >
          Revocar
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.usuarios {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 16px;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
}
th,
td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
th {
  font-size: 0.85rem;
  color: var(--ink-600);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
td small {
  display: block;
  color: var(--ink-600);
}
.acciones {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
button {
  font: inherit;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 6px 10px;
  cursor: pointer;
}
button.peligro {
  color: var(--nivel-alto-fg);
  border-color: var(--nivel-alto-bg);
}
select,
input {
  font: inherit;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: var(--radio);
}
form {
  display: grid;
  gap: 12px;
  max-width: 420px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 16px;
}
label {
  display: grid;
  gap: 4px;
  font-weight: 500;
}
small {
  color: var(--ink-600);
  font-weight: 400;
}
.temporal {
  color: var(--nivel-medio-fg);
}
.revocada {
  color: var(--ink-400);
}
.si {
  color: var(--nivel-bajo-fg);
}
.no {
  color: var(--nivel-medio-fg);
}
.error {
  color: var(--nivel-alto-fg);
}
.aviso {
  color: var(--brand-700);
}
.enlace code {
  background: var(--surface-alt);
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
