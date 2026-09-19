<script setup lang="ts">
/**
 * Checklist de medidas (M4). Tabla densa con edición en línea.
 * Layout, columnas, filtros y textos según design/README_handoff.md §Pantallas 6.
 *
 * Los números no se calculan aquí: llegan del motor a través de la API. Esta pantalla
 * solo los enseña y manda los cambios, para que no haya dos aritméticas que mantener.
 */
import { computed, onMounted, ref } from 'vue'

import { guardarMedida, pedirChecklist, type Checklist, type Fila } from '@/api/checklist'

const props = defineProps<{ systemId: number }>()

const datos = ref<Checklist | null>(null)
const error = ref<string | null>(null)
const cargando = ref(true)
const filtro = ref<Criterio>('todas')
const comoda = ref(false)
const busqueda = ref('')
const ultimo = ref<string | null>(null)
const guardando = ref<string | null>(null)

const NIVELES = [0, 1, 2, 3, 4, 5]

type Criterio = 'todas' | 'gap' | 'soporte' | 'objetivo' | 'noaplica'

const FILTROS: { criterio: Criterio; nombre: string }[] = [
  { criterio: 'todas', nombre: 'Todas' },
  { criterio: 'gap', nombre: 'Por debajo del objetivo' },
  { criterio: 'soporte', nombre: 'Madurez no soportada' },
  { criterio: 'objetivo', nombre: 'En objetivo' },
  { criterio: 'noaplica', nombre: 'No aplican' },
]

function cumple(fila: Fila, criterio: Criterio): boolean {
  if (criterio === 'noaplica') return !fila.aplica
  if (!fila.aplica) return false
  if (criterio === 'gap') return fila.delta !== null && fila.delta < 0
  if (criterio === 'soporte') return fila.no_soportada
  if (criterio === 'objetivo') return fila.delta !== null && fila.delta >= 0 && !fila.no_soportada
  return true
}

const todas = computed(() => datos.value?.medidas ?? [])

const visibles = computed(() => {
  const texto = busqueda.value.trim().toLowerCase()
  return todas.value.filter(
    (fila) =>
      cumple(fila, filtro.value) &&
      (!texto ||
        fila.code.toLowerCase().includes(texto) ||
        fila.nombre.toLowerCase().includes(texto)),
  )
})

/** Los contadores se recalculan al editar: es la regla de la pantalla 6. */
const contadores = computed(() =>
  Object.fromEntries(
    FILTROS.map(({ criterio }) => [criterio, todas.value.filter((f) => cumple(f, criterio)).length]),
  ),
)

const conteo = computed(() =>
  visibles.value.length === 1
    ? '1 medida'
    : `${visibles.value.length} medidas de ${todas.value.length}`,
)

const indice = computed(() => datos.value?.sistema_indice ?? null)

function textoDelta(fila: Fila): string {
  if (!fila.aplica || fila.delta === null) return '—'
  return fila.delta > 0 ? `+${fila.delta}` : String(fila.delta)
}

async function cargar() {
  cargando.value = true
  error.value = null
  try {
    datos.value = await pedirChecklist(props.systemId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudo cargar el checklist'
  } finally {
    cargando.value = false
  }
}

async function cambiar(fila: Fila, cambio: Parameters<typeof guardarMedida>[2], aviso: string) {
  guardando.value = fila.code
  error.value = null
  try {
    datos.value = await guardarMedida(props.systemId, fila.code, cambio)
    ultimo.value = aviso
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudo guardar'
  } finally {
    guardando.value = null
  }
}

function cambiarMadurez(fila: Fila, valor: string) {
  if (valor === '') {
    cambiar(fila, { limpiar: ['maturity_level'] }, `${fila.code} · sin valorar · guardado`)
    return
  }
  const nivel = Number(valor)
  cambiar(fila, { maturity_level: nivel }, `${fila.code} · madurez L${nivel} · guardado`)
}

function alternarAplica(fila: Fila) {
  cambiar(
    fila,
    { applies: !fila.aplica },
    fila.aplica
      ? `${fila.code} · marcada como no aplicable, falta la justificación en la DdA`
      : `${fila.code} · vuelve a ser aplicable`,
  )
}

onMounted(cargar)
</script>

<template>
  <div class="pagina">
    <header class="cabecera">
      <div class="titulo">
        <h1>Medidas</h1>
        <p v-if="datos" class="contexto">
          {{ datos.sistema }} · categoría {{ datos.categoria.toLowerCase() }} · umbral L{{
            datos.objetivo_categoria
          }}
        </p>
      </div>
      <div class="acciones">
        <button type="button" class="secundario" @click="comoda = !comoda">
          {{ comoda ? 'Vista densa' : 'Vista cómoda' }}
        </button>
      </div>
    </header>

    <p v-if="cargando" class="estado">Cargando el checklist…</p>
    <p v-else-if="error" class="estado alerta" role="alert">
      {{ error }}
      <button type="button" class="secundario" @click="cargar">Reintentar</button>
    </p>

    <template v-else-if="datos">
      <section v-if="indice" class="indices" aria-label="Índices de cumplimiento">
        <p class="indice">
          <span class="cifra">{{ indice.cumplimiento }}%</span>
          <span class="etiqueta">Cumplimiento del sistema</span>
          <span class="pie-indice">
            Es el <strong>peor componente</strong>, no la media<template v-if="indice.peor">
              · ahora mismo lo marca {{ indice.peor }}</template
            >.
          </span>
        </p>
        <p class="indice">
          <span class="cifra">{{ indice.en_objetivo }} / {{ indice.medidas }}</span>
          <span class="etiqueta">Medidas en objetivo</span>
          <span class="pie-indice">{{ indice.con_datos }} valoradas.</span>
        </p>
        <p v-if="indice.no_soportadas" class="indice aviso">
          <span class="cifra">{{ indice.no_soportadas }}</span>
          <span class="etiqueta">
            {{ indice.no_soportadas === 1 ? 'Madurez no soportada' : 'Madurez no soportada' }}
          </span>
          <span class="pie-indice">Sin evidencia validada no suma al indicador.</span>
        </p>
      </section>

      <div class="filtros">
        <input v-model="busqueda" type="text" placeholder="Buscar medida" class="buscador" />
        <button
          v-for="f in FILTROS"
          :key="f.criterio"
          type="button"
          class="filtro"
          :class="{ activo: filtro === f.criterio }"
          @click="filtro = f.criterio"
        >
          {{ f.nombre }} <span class="n">{{ contadores[f.criterio] }}</span>
        </button>
      </div>

      <div class="escala">
        <span class="etiqueta">Escala de madurez</span>
        <span v-for="(texto, nivel) in datos.escala" :key="nivel" class="nivel">
          <code>{{ nivel }}</code> {{ texto }}
        </span>
      </div>

      <section class="tabla-caja">
        <table :class="{ comoda }">
          <thead>
            <tr>
              <th>Medida</th>
              <th class="estrecha">Aplicable</th>
              <th class="estrecha">Actual</th>
              <th class="estrecha">Objetivo</th>
              <th class="estrecha">Delta</th>
              <th class="ancha">Responsable</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="fila in visibles"
              :key="fila.code"
              :class="{ 'no-aplica': !fila.aplica, 'sin-soporte': fila.no_soportada }"
            >
              <td class="texto">
                <span class="medida">
                  <code>{{ fila.code }}</code>
                  <span class="nombre">{{ fila.nombre }}</span>
                </span>
                <span v-if="fila.no_soportada" class="aviso-soporte">
                  madurez no soportada: sin evidencia validada, no suma al indicador
                </span>
                <span v-else-if="fila.motivo" class="motivo">{{ fila.motivo }}</span>
              </td>
              <td>
                <button
                  type="button"
                  class="chip"
                  :class="fila.aplica ? 'si' : 'no'"
                  :disabled="guardando === fila.code"
                  @click="alternarAplica(fila)"
                >
                  {{ fila.aplica ? 'sí' : 'no aplica' }}
                </button>
              </td>
              <td>
                <select
                  class="selector"
                  :value="fila.madurez ?? ''"
                  :disabled="!fila.aplica || guardando === fila.code"
                  :aria-label="`Madurez de ${fila.code}`"
                  @change="cambiarMadurez(fila, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">—</option>
                  <option v-for="n in NIVELES" :key="n" :value="n">L{{ n }}</option>
                </select>
              </td>
              <td class="num">L{{ fila.objetivo }}</td>
              <td>
                <span class="delta" :class="fila.aplica ? fila.semaforo.toLowerCase() : 'gris'">
                  {{ textoDelta(fila) }}
                </span>
              </td>
              <td class="fin">
                <span class="responsable">{{ fila.responsable || '—' }}</span>
                <span class="fecha">{{ fila.fecha_limite ?? '—' }}</span>
              </td>
            </tr>
            <tr v-if="!visibles.length">
              <td colspan="6" class="vacio">Ninguna medida cumple este filtro.</td>
            </tr>
          </tbody>
        </table>
        <div class="pie-tabla">
          <span>{{ conteo }}</span>
          <span class="ayuda">
            Se puede recorrer y editar con el teclado: tabulador entre celdas editables.
          </span>
        </div>
      </section>

      <p v-if="ultimo" class="ultimo" role="status">{{ ultimo }}</p>
    </template>
  </div>
</template>

<style scoped>
.pagina {
  max-width: 1240px;
  margin: 0 auto;
  padding: 24px 28px 64px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cabecera {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.contexto,
.ayuda,
.etiqueta,
.motivo,
.pie-indice {
  color: var(--ink-600);
  font-size: 12px;
  margin: 2px 0 0;
}

.estado {
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  font-size: 14px;
}

.alerta {
  color: var(--nivel-alto-fg);
  background: var(--nivel-alto-bg);
  border-color: var(--nivel-alto-fg);
}

.indices {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.indice {
  flex: 1 1 220px;
  margin: 0;
  padding: 12px 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.indice.aviso {
  border-left: 3px solid var(--nivel-medio-fg);
}

.cifra {
  font-size: 24px;
  font-weight: 600;
}

.filtros {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.buscador {
  flex: 1 1 200px;
  min-width: 0;
  font: inherit;
  font-size: 13px;
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
}

.filtro,
.secundario,
.chip {
  font: inherit;
  cursor: pointer;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-600);
  white-space: nowrap;
}

.filtro {
  font-size: 12px;
  font-weight: 500;
  padding: 6px 10px;
}

.filtro.activo {
  border-color: var(--brand-700);
  background: var(--brand-50);
  color: var(--brand-900);
}

.filtro .n {
  opacity: 0.7;
}

.secundario {
  font-size: 13px;
  font-weight: 500;
  padding: 7px 11px;
}

.escala {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 11px 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  font-size: 12px;
  color: var(--ink-600);
}

.escala .nivel code,
.medida code,
.num,
.delta,
.fecha {
  font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", monospace;
  font-size: 12px;
}

.tabla-caja {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

thead th {
  text-align: left;
  padding: 9px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-600);
  background: var(--surface-alt);
  border-bottom: 1px solid var(--line);
}

thead th:first-child,
tbody td:first-child {
  padding-left: 16px;
}

thead th:last-child,
tbody td:last-child {
  padding-right: 16px;
}

.estrecha {
  width: 88px;
  white-space: nowrap;
}

.ancha {
  width: 130px;
  white-space: nowrap;
}

tbody td {
  padding: 8px;
  border-bottom: 1px solid var(--surface-alt);
  vertical-align: middle;
  line-height: 1.45;
}

table.comoda tbody td {
  padding: 13px 8px;
}

tbody tr.no-aplica {
  background: var(--surface-alt);
}

tbody tr.sin-soporte {
  background: var(--nivel-medio-bg);
}

.texto {
  max-width: 0;
}

.medida {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.medida code {
  color: var(--ink-600);
}

.nombre {
  font-weight: 500;
}

.aviso-soporte {
  display: block;
  font-size: 12px;
  color: var(--nivel-medio-fg);
}

.chip {
  font-size: 12px;
  font-weight: 500;
  padding: 3px 8px;
}

.chip.si {
  color: var(--nivel-bajo-fg);
  background: var(--nivel-bajo-bg);
}

.chip.no {
  color: var(--nivel-na-fg);
  background: var(--nivel-na-bg);
}

.selector {
  font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", monospace;
  font-size: 13px;
  padding: 4px 6px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  cursor: pointer;
}

.num {
  color: var(--ink-600);
}

.delta {
  display: inline-flex;
  font-size: 12px;
  font-weight: 500;
  border-radius: 5px;
  padding: 3px 8px;
}

.delta.verde {
  color: var(--nivel-bajo-fg);
  background: var(--nivel-bajo-bg);
}

.delta.amarillo {
  color: var(--nivel-medio-fg);
  background: var(--nivel-medio-bg);
}

.delta.rojo {
  color: var(--nivel-alto-fg);
  background: var(--nivel-alto-bg);
}

.delta.gris {
  color: var(--nivel-na-fg);
  background: var(--nivel-na-bg);
}

.fin {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.responsable {
  font-size: 13px;
  white-space: nowrap;
}

.fecha {
  color: var(--ink-600);
}

.vacio {
  padding: 24px 16px;
  text-align: center;
  color: var(--ink-600);
  font-size: 13px;
}

.pie-tabla {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--ink-600);
}

.ultimo {
  margin: 0;
  font-size: 12px;
  color: var(--ink-600);
}
</style>
