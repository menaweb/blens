<script setup lang="ts">
/**
 * Carpeta de evidencias (M5) y detalle de cada requisito.
 * Estructura, filtros y textos: design/README_handoff.md §Pantallas 3 y 4.
 *
 * Dos reglas de la pantalla que no son adorno: los **rechazos típicos van antes** de la
 * zona de subida (avisar después de subir no sirve de nada) y la completitud **no
 * redondea al alza**, que la calcula el servidor y aquí solo se enseña.
 */
import { computed, onMounted, ref, watch } from 'vue'

import {
  aportarEvidencia,
  noAplica,
  pedirCarpeta,
  rechazarEvidencia,
  validarEvidencia,
  type Carpeta,
  type Requisito,
} from '@/api/evidencias'

const props = defineProps<{ systemId: number }>()

const datos = ref<Carpeta | null>(null)
const cargando = ref(true)
const error = ref<string | null>(null)
const filtro = ref<Criterio>('huecos')
const seleccionado = ref<number | null>(null)
const criteriosMarcados = ref<string[]>([])
const fichero = ref<File | null>(null)
const fechaEvidencia = ref('')
const justificacion = ref('')
const motivoRechazo = ref('')

type Criterio = 'todos' | 'huecos' | 'revision' | 'validados' | 'caducados' | 'descartados'

const FILTROS: { criterio: Criterio; nombre: string }[] = [
  { criterio: 'huecos', nombre: 'Lo que falta' },
  { criterio: 'revision', nombre: 'Aportado, sin validar' },
  { criterio: 'validados', nombre: 'Validado' },
  { criterio: 'caducados', nombre: 'Caducado' },
  { criterio: 'descartados', nombre: 'No aplica o fuera de alcance' },
  { criterio: 'todos', nombre: 'Todo' },
]

function cumple(requisito: Requisito, criterio: Criterio): boolean {
  if (criterio === 'todos') return true
  if (criterio === 'huecos')
    return (
      !requisito.cubierto_por_grupo &&
      ['PENDIENTE', 'CADUCADA'].includes(requisito.estado)
    )
  if (criterio === 'revision') return requisito.estado === 'APORTADA'
  if (criterio === 'validados') return requisito.estado === 'VALIDADA'
  if (criterio === 'caducados') return requisito.estado === 'CADUCADA'
  return ['NO_APLICA_JUSTIFICADO', 'FUERA_DE_ALCANCE'].includes(requisito.estado)
}

const todos = computed(() => datos.value?.requisitos ?? [])

const visibles = computed(() => todos.value.filter((r) => cumple(r, filtro.value)))

const contadores = computed(() =>
  Object.fromEntries(
    FILTROS.map(({ criterio }) => [criterio, todos.value.filter((r) => cumple(r, criterio)).length]),
  ),
)

/** Las carpetas del paquete 808 (§10): el auditor las reconoce, el cliente aprende dónde va todo. */
const porCarpeta = computed(() => {
  const grupos = new Map<string, Requisito[]>()
  for (const requisito of visibles.value) {
    const carpeta = requisito.carpeta_paquete.split('/')[0] || 'Sin carpeta'
    grupos.set(carpeta, [...(grupos.get(carpeta) ?? []), requisito])
  }
  return [...grupos.entries()].sort(([a], [b]) => a.localeCompare(b))
})

const actual = computed<Requisito | null>(
  () => todos.value.find((r) => r.id === seleccionado.value) ?? null,
)

/** El origen llega como JSON libre: el esquema no puede tiparlo, pero sí sabemos qué trae. */
const preguntasDeOrigen = computed(
  () => (actual.value?.origen as { preguntas?: string[] } | undefined)?.preguntas ?? [],
)

const ESTADOS: Record<string, string> = {
  PENDIENTE: 'Pendiente',
  APORTADA: 'Aportada, sin validar',
  VALIDADA: 'Validada',
  CADUCADA: 'Caducada',
  FUERA_DE_ALCANCE: 'Fuera de alcance',
  NO_APLICA_JUSTIFICADO: 'No aplica, justificado',
}

onMounted(cargar)

watch(actual, () => {
  criteriosMarcados.value = []
  fichero.value = null
  fechaEvidencia.value = ''
  justificacion.value = ''
  motivoRechazo.value = ''
})

async function cargar() {
  try {
    datos.value = await pedirCarpeta(props.systemId)
    seleccionado.value ??= visibles.value[0]?.id ?? null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No hemos podido cargar la carpeta.'
  } finally {
    cargando.value = false
  }
}

async function conError(accion: () => Promise<Carpeta>) {
  try {
    datos.value = await accion()
    error.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No hemos podido completar la operación.'
  }
}

function elegirFichero(evento: Event) {
  fichero.value = (evento.target as HTMLInputElement).files?.[0] ?? null
}

function alternarCriterio(criterio: string) {
  criteriosMarcados.value = criteriosMarcados.value.includes(criterio)
    ? criteriosMarcados.value.filter((c) => c !== criterio)
    : [...criteriosMarcados.value, criterio]
}

async function subir() {
  const requisito = actual.value
  if (!requisito || !fichero.value || !fechaEvidencia.value) return
  const formulario = new FormData()
  formulario.append('fichero', fichero.value)
  formulario.append('fecha_evidencia', fechaEvidencia.value)
  formulario.append('titulo', requisito.titulo)
  formulario.append('criterios', criteriosMarcados.value.join('|'))
  await conError(() => aportarEvidencia(props.systemId, requisito.id, formulario))
}

async function descartar() {
  const requisito = actual.value
  if (!requisito || !justificacion.value.trim()) return
  await conError(() => noAplica(props.systemId, requisito.id, justificacion.value))
}
</script>

<template>
  <div v-if="cargando" class="cargando">Cargando la carpeta…</div>
  <p v-else-if="error && !datos" class="error" role="alert">{{ error }}</p>

  <div v-else-if="datos" class="pantalla">
    <header class="cabecera">
      <div>
        <h1>Carpeta de evidencias</h1>
        <p class="sistema">{{ datos.sistema }} · categoría {{ datos.categoria }}</p>
      </div>
      <dl class="totales">
        <div>
          <dt>Requisitos</dt>
          <dd>{{ datos.requisitos.length }}</dd>
        </div>
        <div class="marcado">
          <dt>Te falta</dt>
          <dd>{{ datos.huecos }}</dd>
        </div>
        <div>
          <dt>Obligatorios</dt>
          <dd>{{ datos.obligatorios }}</dd>
        </div>
        <div>
          <dt>Completitud</dt>
          <dd>{{ datos.completitud }}%</dd>
        </div>
      </dl>
      <p class="nota">
        La completitud no redondea al alza, y esto no es una declaración de conformidad:
        la conformidad la declara el auditor.
      </p>
    </header>

    <nav class="filtros" aria-label="Filtros de la carpeta">
      <button
        v-for="opcion in FILTROS"
        :key="opcion.criterio"
        class="filtro"
        :class="{ activo: filtro === opcion.criterio }"
        @click="filtro = opcion.criterio"
      >
        {{ opcion.nombre }} <span class="cuenta">{{ contadores[opcion.criterio] }}</span>
      </button>
    </nav>

    <div class="cuerpo">
      <section class="listado">
        <article v-for="[carpeta, requisitos] in porCarpeta" :key="carpeta" class="carpeta">
          <h2>{{ carpeta }} <span class="cuenta">{{ requisitos.length }}</span></h2>
          <ul>
            <li v-for="requisito in requisitos" :key="requisito.id">
              <button
                class="requisito"
                :class="{ activo: requisito.id === seleccionado }"
                @click="seleccionado = requisito.id"
              >
                <span class="titulo">{{ requisito.titulo }}</span>
                <code>{{ requisito.measure }}</code>
                <span class="estado" :class="requisito.estado.toLowerCase()">
                  {{ requisito.cubierto_por_grupo ? 'Cubierto por otra opción' : ESTADOS[requisito.estado] }}
                </span>
              </button>
            </li>
          </ul>
        </article>
        <p v-if="!visibles.length" class="vacio">Aquí no queda nada. Prueba otro filtro.</p>
      </section>

      <aside v-if="actual" class="detalle">
        <p class="antetitulo">
          {{ actual.measure }} · {{ actual.carpeta_paquete }}
          <span v-if="actual.obligatoria" class="obligatoria">obligatoria</span>
        </p>
        <h2>{{ actual.titulo }}</h2>
        <p class="motivo">{{ actual.motivo }}</p>
        <p v-if="preguntasDeOrigen.length" class="origen">
          Te lo pedimos por lo que respondiste en: <em>{{ preguntasDeOrigen.join(', ') }}</em>
        </p>

        <section class="bloque">
          <h3>Qué aportar</h3>
          <p>{{ actual.instrucciones }}</p>
          <p v-if="actual.formatos.length" class="pista">
            Formatos: {{ actual.formatos.join(', ') }}
            <template v-if="actual.vigencia_dias"> · caduca a los {{ actual.vigencia_dias }} días</template>
          </p>
        </section>

        <section v-if="actual.alternativas.length" class="bloque alternativas">
          <h3>Con una de estas basta</h3>
          <p>
            Esta es la más sólida ante el auditor. También valen:
            <code v-for="otra in actual.alternativas" :key="otra">{{ otra }}</code>
          </p>
        </section>

        <section v-if="actual.pistas.length" class="bloque">
          <h3>Dónde sacarlo</h3>
          <p v-for="pista in actual.pistas" :key="pista" class="ruta">{{ pista }}</p>
        </section>

        <section v-if="actual.criterios_aceptacion.length" class="bloque">
          <h3>
            Qué tiene que verse
            <span class="cuenta">{{ criteriosMarcados.length }}/{{ actual.criterios_aceptacion.length }}</span>
          </h3>
          <label v-for="criterio in actual.criterios_aceptacion" :key="criterio" class="criterio">
            <input
              type="checkbox"
              :checked="criteriosMarcados.includes(criterio)"
              @change="alternarCriterio(criterio)"
            />
            <span>{{ criterio }}</span>
          </label>
        </section>

        <!-- Antes de la zona de subida, no después: avisar tarde no evita el rechazo. -->
        <section v-if="actual.rechazos_tipicos.length" class="bloque rechazos">
          <h3>Por esto se suele rechazar</h3>
          <ul>
            <li v-for="rechazo in actual.rechazos_tipicos" :key="rechazo">{{ rechazo }}</li>
          </ul>
        </section>

        <section class="bloque subida">
          <h3>Aportar</h3>
          <label class="campo">
            <span>Fichero</span>
            <input type="file" @change="elegirFichero" />
          </label>
          <label class="campo">
            <span>Fecha del hecho</span>
            <input v-model="fechaEvidencia" type="date" />
          </label>
          <p class="pista">
            La fecha del hecho es cuándo ocurrió (la prueba, la captura), no cuándo lo subes:
            es la que mira el auditor y la que manda la caducidad.
          </p>
          <button class="primario" :disabled="!fichero || !fechaEvidencia" @click="subir">
            Subir evidencia
          </button>
        </section>

        <section v-if="actual.evidencias.length" class="bloque">
          <h3>Lo aportado</h3>
          <ul class="evidencias">
            <li v-for="evidencia in actual.evidencias" :key="evidencia.id">
              <span class="titulo">{{ evidencia.titulo || evidencia.nombre_original }}</span>
              <span class="estado" :class="evidencia.estado.toLowerCase()">{{ evidencia.estado }}</span>
              <span class="fecha">{{ evidencia.fecha_evidencia }}</span>
              <span v-if="evidencia.motivo_rechazo" class="rechazo">{{ evidencia.motivo_rechazo }}</span>
              <span v-if="evidencia.estado === 'APORTADA'" class="revision">
                <button class="secundario" @click="conError(() => validarEvidencia(systemId, evidencia.id))">
                  Validar
                </button>
                <input v-model="motivoRechazo" placeholder="Motivo del rechazo" />
                <button
                  class="secundario"
                  :disabled="!motivoRechazo.trim()"
                  @click="conError(() => rechazarEvidencia(systemId, evidencia.id, motivoRechazo))"
                >
                  Rechazar
                </button>
              </span>
            </li>
          </ul>
          <p class="pista">Quien aporta una evidencia no puede validarla, aunque su rol se lo permita.</p>
        </section>

        <section class="bloque descartar">
          <h3>Marcar como no aplica</h3>
          <input v-model="justificacion" placeholder="Por qué no aplica a este sistema" />
          <button class="secundario" :disabled="!justificacion.trim()" @click="descartar">
            No aplica
          </button>
          <p class="pista">Sin justificación no se puede: el auditor verá esta frase.</p>
        </section>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.pantalla {
  padding: 24px;
}

.cabecera {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.cabecera h1 {
  font-size: 20px;
  margin: 0;
}

.sistema,
.nota {
  color: var(--ink-600);
  font-size: 13px;
  margin: 0;
}

.totales {
  display: flex;
  gap: 24px;
  margin: 8px 0 0;
}

.totales div {
  padding-left: 12px;
  border-left: 3px solid var(--line);
}

.totales .marcado {
  border-left-color: var(--nivel-medio-fg);
}

.totales dt {
  font-size: 12px;
  color: var(--ink-600);
}

.totales dd {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.filtros {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.filtro {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.filtro.activo {
  background: var(--brand-50);
  border-color: var(--brand-700);
  color: var(--brand-900);
}

.cuenta {
  color: var(--ink-600);
  font-variant-numeric: tabular-nums;
}

.cuerpo {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 24px;
  align-items: start;
}

.listado,
.detalle {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 16px;
}

.carpeta h2 {
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--ink-600);
  margin: 12px 0 4px;
}

.carpeta ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.requisito {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 8px;
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
  border-radius: var(--radio);
  padding: 8px;
  cursor: pointer;
  font-size: 14px;
}

.requisito:hover {
  background: var(--surface-alt);
}

.requisito.activo {
  background: var(--brand-50);
}

.requisito .titulo {
  font-weight: 600;
  min-width: 0;
}

.requisito code {
  font-size: 12px;
  color: var(--ink-600);
}

.estado {
  grid-column: 1 / -1;
  font-size: 12px;
  color: var(--ink-600);
}

.estado.validada {
  color: var(--nivel-bajo-fg);
}

.estado.caducada,
.estado.rechazada {
  color: var(--nivel-alto-fg);
}

.estado.pendiente {
  color: var(--nivel-medio-fg);
}

.antetitulo {
  font-size: 12px;
  color: var(--ink-600);
  margin: 0 0 4px;
}

.obligatoria {
  background: var(--brand-100);
  color: var(--brand-900);
  border-radius: 999px;
  padding: 1px 8px;
  margin-left: 4px;
}

.detalle h2 {
  font-size: 16px;
  margin: 0 0 4px;
}

.motivo,
.origen {
  font-size: 13px;
  color: var(--ink-600);
  margin: 0 0 8px;
}

.bloque {
  border-top: 1px solid var(--line);
  padding-top: 12px;
  margin-top: 12px;
}

.bloque h3 {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-600);
  margin: 0 0 6px;
}

.bloque p {
  font-size: 14px;
  margin: 0 0 6px;
}

.pista {
  font-size: 12px;
  color: var(--ink-600);
}

.ruta {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  background: var(--surface-alt);
  border-radius: var(--radio);
  padding: 6px 8px;
}

.alternativas code {
  font-size: 12px;
  margin-right: 6px;
}

.criterio {
  display: flex;
  gap: 8px;
  align-items: start;
  font-size: 13px;
  margin-bottom: 4px;
}

.rechazos {
  background: var(--nivel-alto-bg);
  border-radius: var(--radio);
  padding: 12px;
  border-top: 0;
}

.rechazos h3 {
  color: var(--nivel-alto-fg);
}

.rechazos ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
}

.campo {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-600);
  margin-bottom: 8px;
}

.evidencias {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 13px;
  display: grid;
  gap: 8px;
}

.evidencias .rechazo {
  grid-column: 1 / -1;
  color: var(--nivel-alto-fg);
}

.revision {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.descartar input,
.revision input {
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 6px 10px;
  font-size: 13px;
  font-family: inherit;
  width: 100%;
  margin-bottom: 6px;
}

.primario,
.secundario {
  border-radius: var(--radio);
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.primario {
  background: var(--brand-700);
  color: #fff;
}

.primario:disabled,
.secundario:disabled {
  background: var(--ink-400);
  color: #fff;
  cursor: not-allowed;
}

.secundario {
  background: var(--surface);
  border-color: var(--line);
}

.vacio,
.cargando {
  color: var(--ink-600);
  font-size: 14px;
}

.error {
  color: var(--nivel-alto-fg);
  font-size: 13px;
}
</style>
