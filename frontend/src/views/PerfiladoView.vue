<script setup lang="ts">
/**
 * Perfilado del sistema (M11). La pantalla que más veces verá el usuario.
 * Layout, apoyos de cada pregunta y textos: design/README_handoff.md §Pantallas 2.
 *
 * Qué se pregunta y en qué orden lo decide el servidor (y detrás, el motor). Aquí no hay
 * ni una condición interpretada: si esta pantalla decidiera por su cuenta qué enseñar,
 * habría dos cuestionarios distintos, el del navegador y el de la auditoría.
 */
import { computed, onMounted, ref, watch } from 'vue'

import {
  delegarPregunta,
  pedirCuestionario,
  responderPregunta,
  type Cuestionario,
  type Pregunta,
} from '@/api/perfilado'

const props = defineProps<{ systemId: number }>()

const datos = ref<Cuestionario | null>(null)
const error = ref<string | null>(null)
const cargando = ref(true)
const bloqueActivo = ref<string | null>(null)
const indice = ref(0)
/** Tres estados de guardado, como pide el handoff: activo, guardando y guardado a las HH:MM. */
const guardado = ref<{ estado: 'listo' | 'guardando' | 'hecho'; hora: string }>({
  estado: 'listo',
  hora: '',
})
const aviso = ref<string | null>(null)
const delegando = ref(false)
const correo = ref('')
const nota = ref('')
/** Borrador de la respuesta que se está componiendo (múltiple, texto, tabla…). */
const borrador = ref<unknown>(null)

const bloques = computed(() => datos.value?.bloques ?? [])

const delBloque = computed(() =>
  (datos.value?.preguntas ?? []).filter((p) => p.bloque === bloqueActivo.value),
)

const actual = computed<Pregunta | null>(() => delBloque.value[indice.value] ?? null)

const tituloBloque = computed(
  () => bloques.value.find((b) => b.bloque === bloqueActivo.value)?.titulo ?? '',
)

const seleccion = computed<string[]>(() => {
  const valor = borrador.value
  if (Array.isArray(valor)) return valor.map(String)
  return valor === null || valor === undefined || valor === '' ? [] : [String(valor)]
})

/** Hay respuesta cuando hay algo marcado, escrito o rellenado: una lista vacía no cuenta. */
const puedeGuardar = computed(() => {
  const valor = borrador.value
  if (Array.isArray(valor)) return valor.length > 0
  if (valor && typeof valor === 'object')
    return Object.values(valor).some((v) => v !== '' && v !== null && v !== undefined)
  return valor !== null && valor !== undefined && valor !== ''
})

onMounted(cargar)

async function cargar() {
  try {
    datos.value = await pedirCuestionario(props.systemId)
    if (!bloqueActivo.value) bloqueActivo.value = primerBloquePendiente()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No hemos podido cargar el cuestionario.'
  } finally {
    cargando.value = false
  }
}

function primerBloquePendiente(): string | null {
  const pendiente = bloques.value.find((b) => b.respondidas < b.total)
  return (pendiente ?? bloques.value[0])?.bloque ?? null
}

watch([bloqueActivo, actual], () => {
  borrador.value = actual.value?.valor ?? (actual.value?.tipo === 'MULTI' ? [] : null)
})

function irAlBloque(code: string) {
  bloqueActivo.value = code
  indice.value = 0
  aviso.value = null
}

function marcar(code: string) {
  if (actual.value?.tipo === 'MULTI') {
    const actuales = seleccion.value
    borrador.value = actuales.includes(code)
      ? actuales.filter((c) => c !== code)
      : [...actuales, code]
  } else {
    borrador.value = code
  }
}

/** Guardar es responder: no hay botón de «enviar el cuestionario» que se quede a medias. */
async function guardar() {
  const pregunta = actual.value
  if (!pregunta || !puedeGuardar.value) return

  guardado.value = { estado: 'guardando', hora: '' }
  try {
    const cambio = await responderPregunta(props.systemId, pregunta.code, borrador.value)
    datos.value = cambio.cuestionario
    aviso.value = resumen(cambio.requisitos_nuevos.length, cambio.requisitos_fuera_de_alcance.length)
    guardado.value = {
      estado: 'hecho',
      hora: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }),
    }
    siguiente()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No hemos podido guardar la respuesta.'
    guardado.value = { estado: 'listo', hora: '' }
  }
}

/** Responder tiene consecuencias y se dicen: es lo que distingue esto de un formulario. */
function resumen(nuevos: number, apartados: number): string | null {
  const partes: string[] = []
  if (nuevos) partes.push(`${nuevos} ${nuevos === 1 ? 'evidencia nueva' : 'evidencias nuevas'}`)
  if (apartados)
    partes.push(
      `${apartados} ${apartados === 1 ? 'requisito que ya no aplica' : 'requisitos que ya no aplican'}`,
    )
  return partes.length ? `Con esta respuesta, tu carpeta cambia: ${partes.join(' y ')}.` : null
}

function siguiente() {
  if (indice.value < delBloque.value.length - 1) indice.value += 1
  else bloqueActivo.value = primerBloquePendiente()
}

function anterior() {
  if (indice.value > 0) indice.value -= 1
}

async function delegar() {
  const pregunta = actual.value
  if (!pregunta || !correo.value.trim()) return
  try {
    await delegarPregunta(props.systemId, pregunta.code, {
      email: correo.value.trim(),
      nota: nota.value,
    })
    delegando.value = false
    correo.value = ''
    nota.value = ''
    datos.value = await pedirCuestionario(props.systemId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No hemos podido crear la tarea.'
  }
}
</script>

<template>
  <div v-if="cargando" class="cargando">Cargando el cuestionario…</div>
  <p v-else-if="error" class="error" role="alert">{{ error }}</p>

  <div v-else-if="datos" class="pantalla">
    <aside class="bloques" aria-label="Bloques del cuestionario">
      <h2>Perfilado</h2>
      <p class="restante">
        {{ datos.pendientes }} {{ datos.pendientes === 1 ? 'pregunta' : 'preguntas' }} por responder
      </p>
      <ul>
        <li v-for="bloque in bloques" :key="bloque.bloque">
          <button
            class="bloque"
            :class="{ activo: bloque.bloque === bloqueActivo, hecho: bloque.respondidas === bloque.total }"
            @click="irAlBloque(bloque.bloque)"
          >
            <span class="nombre">{{ bloque.titulo }}</span>
            <span class="cuenta">{{ bloque.respondidas }}/{{ bloque.total }}</span>
            <span class="barra"><i :style="{ width: `${(bloque.respondidas / bloque.total) * 100}%` }" /></span>
            <span class="minutos">{{ bloque.minutos }} min</span>
          </button>
        </li>
      </ul>
    </aside>

    <main class="columna">
      <header class="migas">
        <span>{{ datos.sistema }} · {{ datos.categoria }}</span>
        <span class="guardado" :class="guardado.estado">
          <i />
          <template v-if="guardado.estado === 'guardando'">Guardando…</template>
          <template v-else-if="guardado.estado === 'hecho'">Guardado a las {{ guardado.hora }}</template>
          <template v-else>Se guarda solo</template>
        </span>
      </header>

      <article v-if="actual" class="ficha">
        <p class="antetitulo">
          {{ tituloBloque }} · pregunta {{ indice + 1 }} de {{ delBloque.length }}
        </p>
        <h1>{{ actual.texto }}</h1>

        <section v-if="actual.por_que" class="apoyo">
          <h3>Por qué se pregunta</h3>
          <p>{{ actual.por_que }}</p>
        </section>
        <section v-if="actual.como_saberlo" class="apoyo">
          <h3>Cómo saberlo</h3>
          <p>{{ actual.como_saberlo }}</p>
        </section>

        <dl v-if="Object.keys(actual.glosario).length" class="glosario">
          <div v-for="(definicion, termino) in actual.glosario" :key="termino">
            <dt :title="definicion">{{ termino }}</dt>
            <dd>{{ definicion }}</dd>
          </div>
        </dl>

        <div v-if="actual.opciones.length" class="opciones">
          <button
            v-for="opcion in actual.opciones"
            :key="opcion.code"
            class="opcion"
            :class="{ marcada: seleccion.includes(opcion.code) }"
            :aria-pressed="seleccion.includes(opcion.code)"
            @click="marcar(opcion.code)"
          >
            {{ opcion.label }}
          </button>
          <p v-if="actual.tipo === 'MULTI'" class="pista">Marca todas las que apliquen.</p>
        </div>

        <div v-else-if="actual.campos.length" class="campos">
          <label v-for="campo in actual.campos" :key="campo.code">
            <span>{{ campo.label }}</span>
            <input
              :value="((borrador as Record<string, unknown>) ?? {})[campo.code] ?? ''"
              @input="
                borrador = {
                  ...((borrador as Record<string, unknown>) ?? {}),
                  [campo.code]: ($event.target as HTMLInputElement).value,
                }
              "
            />
          </label>
        </div>

        <div v-else class="campos">
          <label>
            <span>Tu respuesta</span>
            <input
              :type="actual.tipo === 'DATE' ? 'date' : actual.tipo === 'NUMBER' ? 'number' : 'text'"
              :value="(borrador as string) ?? ''"
              @input="borrador = ($event.target as HTMLInputElement).value"
            />
          </label>
        </div>

        <p v-if="aviso" class="aviso">{{ aviso }}</p>
        <p v-if="actual.delegada_a" class="delegada">
          Se la has preguntado a {{ actual.delegada_a }}. Puedes responder tú igualmente.
        </p>

        <footer class="acciones">
          <button class="secundario" :disabled="indice === 0" @click="anterior">Atrás</button>
          <button class="terciario" @click="delegando = !delegando">
            Preguntárselo a otra persona
          </button>
          <button class="primario" :disabled="!puedeGuardar" @click="guardar">
            Guardar y seguir
          </button>
        </footer>

        <!-- No existe la opción «no lo sé»: se le pregunta a alguien, con nombre (§4 M11). -->
        <section v-if="delegando" class="delegar">
          <h3>¿Quién lo sabe?</h3>
          <label>
            <span>Correo de la persona</span>
            <input v-model="correo" type="email" placeholder="alguien@tuorganizacion.es" />
          </label>
          <label>
            <span>Nota (opcional)</span>
            <input v-model="nota" placeholder="Es para la auditoría del ENS" />
          </label>
          <button class="primario" :disabled="!correo.trim()" @click="delegar">
            Crear tarea y seguir
          </button>
        </section>
      </article>

      <p v-else class="hecho-todo">
        Has respondido todo lo que toca en este bloque. Elige otro en la columna de la
        izquierda: las preguntas nuevas aparecen solas cuando tus respuestas las abren.
      </p>
    </main>
  </div>
</template>

<style scoped>
.pantalla {
  display: grid;
  grid-template-columns: 296px minmax(0, var(--col));
  gap: 32px;
  padding: 24px;
}

.bloques {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 16px;
  height: fit-content;
}

.bloques h2 {
  font-size: 16px;
  margin: 0;
}

.restante {
  color: var(--ink-600);
  font-size: 13px;
  margin: 4px 0 12px;
}

.bloques ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.bloque {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 8px;
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
  border-radius: var(--radio);
  padding: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--ink-900);
}

.bloque:hover {
  background: var(--surface-alt);
}

.bloque.activo {
  background: var(--brand-50);
}

.bloque.hecho .cuenta {
  color: var(--nivel-bajo-fg);
}

.nombre {
  font-weight: 600;
}

.cuenta {
  color: var(--ink-600);
  font-variant-numeric: tabular-nums;
}

.barra {
  grid-column: 1 / -1;
  height: 4px;
  background: var(--line);
  border-radius: 2px;
  overflow: hidden;
}

.barra i {
  display: block;
  height: 100%;
  background: var(--brand-500);
}

.minutos {
  grid-column: 1 / -1;
  color: var(--ink-400);
  font-size: 12px;
}

.columna {
  min-width: 0;
}

.migas {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--ink-600);
  font-size: 13px;
  margin-bottom: 12px;
}

.guardado {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.guardado i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-400);
}

.guardado.guardando i {
  background: var(--nivel-medio-fg);
}

.guardado.hecho i {
  background: var(--nivel-bajo-fg);
}

.ficha {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 24px;
}

.antetitulo {
  color: var(--ink-600);
  font-size: 13px;
  margin: 0 0 8px;
}

.ficha h1 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 16px;
}

.apoyo {
  background: var(--surface-alt);
  border-radius: var(--radio);
  padding: 12px 16px;
  margin-bottom: 12px;
}

.apoyo h3 {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-600);
  margin: 0 0 4px;
}

.apoyo p {
  margin: 0;
  font-size: 14px;
}

.glosario {
  margin: 0 0 16px;
  font-size: 13px;
}

.glosario dt {
  font-weight: 600;
  border-bottom: 1px dotted var(--ink-400);
  display: inline-block;
  cursor: help;
}

.glosario dd {
  margin: 2px 0 8px;
  color: var(--ink-600);
}

.opciones {
  display: grid;
  gap: 8px;
  margin: 16px 0;
}

.opcion {
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease;
}

.opcion:hover {
  border-color: var(--brand-500);
}

.opcion.marcada {
  border-color: var(--brand-700);
  background: var(--brand-50);
}

.pista,
.aviso,
.delegada {
  font-size: 13px;
  color: var(--ink-600);
  margin: 0 0 8px;
}

.aviso {
  background: var(--brand-50);
  border-left: 3px solid var(--brand-500);
  padding: 8px 12px;
  color: var(--ink-900);
}

.campos {
  display: grid;
  gap: 12px;
  margin: 16px 0;
}

.campos label,
.delegar label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-600);
}

.campos input,
.delegar input {
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 8px 12px;
  font-size: 14px;
  font-family: inherit;
}

.acciones {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 16px;
}

.primario,
.secundario,
.terciario {
  border-radius: var(--radio);
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.primario {
  background: var(--brand-700);
  color: #fff;
  margin-left: auto;
}

.primario:disabled {
  background: var(--ink-400);
  cursor: not-allowed;
}

.secundario {
  background: var(--surface);
  border-color: var(--line);
}

.terciario {
  background: none;
  color: var(--brand-700);
  text-decoration: underline;
}

.delegar {
  margin-top: 16px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
  display: grid;
  gap: 12px;
}

.delegar h3 {
  margin: 0;
  font-size: 14px;
}

.hecho-todo,
.cargando,
.error {
  padding: 24px;
  color: var(--ink-600);
}

.error {
  color: var(--nivel-alto-fg);
}
</style>
