<script setup lang="ts">
/**
 * Categorización del Anexo I (M1): asistente de cinco pasos que se usa sin cuenta.
 * Layout y textos según design/README_handoff.md §Pantallas 1.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { categorizar, pedirInforme, type Categorizacion, type Niveles } from '@/api/categorization'
import { DIMENSIONES, type Nivel } from '@/data/dimensiones'

const paso = ref(0)
const respuestas = ref<(Nivel | null)[]>(DIMENSIONES.map(() => null))
const resultado = ref<Categorizacion | null>(null)
const cargando = ref(false)
const error = ref<string | null>(null)
const descarga = ref<string | null>(null)
/** Token del informe guardado: lo hereda la pantalla de crear cuenta. */
const informeToken = ref('')

// En los tests de la vista no hay router montado: el alta solo existe dentro de la app.
const router = useRouter()

const actual = computed(() => DIMENSIONES[paso.value])
const elegida = computed(() => respuestas.value[paso.value])
const esUltima = computed(() => paso.value === DIMENSIONES.length - 1)

const niveles = computed<Niveles>(() => {
  const salida = { C: 'NA', I: 'NA', T: 'NA', A: 'NA', D: 'NA' } as Niveles
  DIMENSIONES.forEach((d, i) => {
    salida[d.dim] = respuestas.value[i] ?? 'NA'
  })
  return salida
})

const nombresQueMarcan = computed(() =>
  (resultado.value?.dimensiones ?? [])
    .filter((d) => d.marca_categoria)
    .map((d) => d.nombre.toLowerCase())
    .join(', '),
)

const etiquetaCategoria = computed(() => {
  const categoria = resultado.value?.categoria
  return categoria ? categoria.charAt(0) + categoria.slice(1).toLowerCase() : 'Sin determinar'
})

function elegir(nivel: Nivel) {
  respuestas.value[paso.value] = nivel
}

async function siguiente() {
  if (!esUltima.value) {
    paso.value += 1
    return
  }
  cargando.value = true
  error.value = null
  try {
    resultado.value = await categorizar(niveles.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error desconocido'
  } finally {
    cargando.value = false
  }
}

function rehacer() {
  resultado.value = null
  descarga.value = null
  informeToken.value = ''
  paso.value = 0
}

/** Guarda el resultado y devuelve su token. Se crea una vez y sirve para el PDF y el alta. */
async function asegurarInforme(): Promise<string> {
  if (informeToken.value) return informeToken.value
  const informe = await pedirInforme(niveles.value, '', '')
  informeToken.value = informe.token
  descarga.value = informe.descarga
  return informe.token
}

async function descargarPdf() {
  cargando.value = true
  try {
    await asegurarInforme()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudo generar el PDF'
  } finally {
    cargando.value = false
  }
}

/**
 * El puente entre el gancho y el producto: se guarda el resultado y se llega al alta con
 * su token, para que la pantalla de crear cuenta pueda enseñar arriba lo que se guarda.
 */
async function crearCuenta() {
  cargando.value = true
  try {
    const token = await asegurarInforme()
    router?.push({ name: 'crear-cuenta', query: { resultado: token } })
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudo guardar el resultado'
  } finally {
    cargando.value = false
  }
}

function claseNivel(nivel: string) {
  return `chip nivel-${nivel.toLowerCase()}`
}
</script>

<template>
  <div class="pagina">
    <div class="columna">
      <p class="antetitulo">Categorización orientativa · sin registro · 2 minutos</p>

      <!-- Asistente -->
      <template v-if="!resultado">
        <div class="segmentos" role="progressbar" :aria-valuenow="paso + 1" aria-valuemin="1" :aria-valuemax="DIMENSIONES.length">
          <span
            v-for="(d, i) in DIMENSIONES"
            :key="d.dim"
            class="segmento"
            :class="{ hecho: respuestas[i] !== null, activo: i === paso }"
          />
        </div>

        <section class="tarjeta">
          <p class="paso">Dimensión {{ paso + 1 }} de {{ DIMENSIONES.length }} · {{ actual.nombre }}</p>
          <h1>{{ actual.pregunta }}</h1>
          <p class="ayuda">{{ actual.ayuda }}</p>

          <fieldset class="opciones">
            <legend class="visualmente-oculto">{{ actual.pregunta }}</legend>
            <label
              v-for="opcion in actual.opciones"
              :key="opcion.nivel"
              class="opcion"
              :class="{ marcada: elegida === opcion.nivel }"
            >
              <input
                type="radio"
                :name="`dim-${actual.dim}`"
                :value="opcion.nivel"
                :checked="elegida === opcion.nivel"
                @change="elegir(opcion.nivel)"
              />
              <span>
                <strong>{{ opcion.etiqueta }}</strong>
                <span class="ejemplo">{{ opcion.ejemplo }}</span>
              </span>
            </label>
          </fieldset>
        </section>

        <div class="pie">
          <button type="button" class="secundario" :disabled="paso === 0" @click="paso -= 1">
            Atrás
          </button>
          <button type="button" class="primario" :disabled="!elegida || cargando" @click="siguiente">
            {{ esUltima ? 'Ver el resultado' : 'Siguiente' }}
          </button>
        </div>
        <p class="nota">La categoría del sistema es la más alta de sus cinco dimensiones.</p>
      </template>

      <!-- Resultado -->
      <section v-else class="tarjeta resultado">
        <template v-if="resultado.sin_determinar">
          <h1 class="categoria">Sin determinar</h1>
          <p class="aviso">{{ resultado.aviso }}</p>
          <p class="ayuda">Revisa el alcance antes de seguir.</p>
        </template>

        <template v-else>
          <p class="paso">Categoría del sistema</p>
          <h1 class="categoria">{{ etiquetaCategoria }}</h1>
          <p class="razon">por {{ nombresQueMarcan }}</p>

          <p class="implicacion">
            Exige un nivel de madurez mínimo <strong>L{{ resultado.madurez_minima }}</strong> y
            <template v-if="resultado.requiere_certificacion">
              <strong>certificación</strong> por una entidad acreditada, con auditoría al menos cada
              dos años.
            </template>
            <template v-else>
              permite acreditar la conformidad mediante <strong>autoevaluación</strong>.
            </template>
          </p>

          <div class="cifras">
            <div class="cifra">
              <span class="valor">{{ resultado.resumen.medidas }}</span>
              <span class="etiqueta">medidas aplicables</span>
            </div>
            <div class="cifra">
              <span class="valor">{{ resultado.resumen.evidencias_estimadas }}</span>
              <span class="etiqueta">evidencias estimadas</span>
            </div>
            <div class="cifra">
              <span class="valor">{{ resultado.resumen.documentos_generables }}</span>
              <span class="etiqueta">documentos que genera BLENS</span>
            </div>
          </div>

          <ul class="desglose">
            <li v-for="d in resultado.dimensiones" :key="d.dim">
              <span>{{ d.nombre }}</span>
              <span :class="claseNivel(d.nivel)">{{ d.nivel.toLowerCase() }}</span>
              <span v-if="d.marca_categoria" class="marca">marca la categoría</span>
            </li>
          </ul>

          <div class="guardar">
            <p class="titulo-guardar">Guarda el resultado y sigue</p>
            <p>
              Al crear la cuenta se conserva esta categorización, se genera tu Declaración de
              Aplicabilidad y se abre el perfilado con las preguntas que te tocan.
            </p>
            <div class="acciones">
              <button type="button" class="claro" :disabled="cargando" @click="crearCuenta">
                Crear cuenta y guardar
              </button>
              <a v-if="descarga" class="enlace-pdf" :href="descarga">Descargar el PDF</a>
              <button v-else type="button" class="fantasma" :disabled="cargando" @click="descargarPdf">
                {{ cargando ? 'Generando…' : 'Descargar en PDF' }}
              </button>
            </div>
          </div>
        </template>

        <div class="pie">
          <button type="button" class="secundario" @click="rehacer">Revisar las respuestas</button>
          <span class="nota derecha">
            Resultado orientativo. La categorización definitiva la aprueba el responsable del
            sistema y puede variar según el alcance.
          </span>
        </div>
      </section>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  justify-content: center;
  padding: 40px 16px 64px;
}
.columna {
  width: 100%;
  max-width: var(--col);
}
.antetitulo {
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-600);
  margin: 0 0 16px;
}
.segmentos {
  display: flex;
  gap: 6px;
  margin-bottom: 20px;
}
.segmento {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--line);
}
.segmento.hecho {
  background: var(--brand-500);
}
.segmento.activo {
  background: var(--brand-700);
}
.tarjeta {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 28px;
}
.paso {
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-600);
  margin: 0 0 8px;
}
h1 {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.3;
  margin: 0 0 8px;
}
.ayuda {
  font-size: 14px;
  color: var(--ink-600);
  margin: 0 0 20px;
}
.opciones {
  border: 0;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}
.opcion {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  border: 1px solid var(--line);
  border-radius: var(--radio);
  padding: 14px 16px;
  cursor: pointer;
}
.opcion:hover {
  border-color: var(--brand-500);
}
.opcion.marcada {
  border-color: var(--brand-700);
  background: var(--brand-50);
}
.opcion input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--brand-700);
}
.opcion strong {
  display: block;
  font-size: 14px;
  font-weight: 600;
}
.ejemplo {
  display: block;
  font-size: 13px;
  color: var(--ink-600);
}
.pie {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 20px;
}
.primario,
.secundario,
.claro,
.fantasma,
.enlace-pdf {
  font-size: 14px;
  font-weight: 500;
  border-radius: 6px;
  padding: 10px 16px;
  cursor: pointer;
  border: 1px solid transparent;
  text-decoration: none;
  display: inline-block;
}
.primario {
  background: var(--brand-700);
  color: #fff;
}
.primario:disabled {
  background: var(--ink-400);
  cursor: not-allowed;
}
.secundario {
  background: var(--surface);
  color: var(--brand-700);
  border-color: var(--brand-700);
}
.secundario:disabled {
  color: var(--ink-400);
  border-color: var(--line);
  cursor: not-allowed;
}
.nota {
  font-size: 12px;
  color: var(--ink-600);
  margin: 12px 0 0;
}
.nota.derecha {
  max-width: 420px;
  text-align: right;
  margin: 0;
}
.categoria {
  font-size: 32px;
  letter-spacing: -0.02em;
  margin: 0;
}
.razon {
  color: var(--ink-600);
  margin: 4px 0 16px;
}
.implicacion {
  font-size: 14px;
  margin: 0 0 20px;
}
.cifras {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.cifra {
  flex: 1 1 160px;
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radio);
  padding: 14px;
}
.valor {
  display: block;
  font-size: 24px;
  font-weight: 600;
  color: var(--brand-900);
}
.etiqueta {
  font-size: 12px;
  color: var(--ink-600);
}
.desglose {
  list-style: none;
  margin: 0 0 20px;
  padding: 0;
  display: grid;
  gap: 8px;
  font-size: 14px;
}
.desglose li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 12px;
  align-items: center;
  border-bottom: 1px solid var(--surface-alt);
  padding-bottom: 6px;
}
.chip {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 10px;
}
.nivel-na {
  color: var(--nivel-na-fg);
  background: var(--nivel-na-bg);
}
.nivel-bajo {
  color: var(--nivel-bajo-fg);
  background: var(--nivel-bajo-bg);
}
.nivel-medio {
  color: var(--nivel-medio-fg);
  background: var(--nivel-medio-bg);
}
.nivel-alto {
  color: var(--nivel-alto-fg);
  background: var(--nivel-alto-bg);
}
.marca {
  font-size: 12px;
  color: var(--ink-600);
}
.guardar {
  background: var(--brand-900);
  color: #fff;
  border-radius: var(--radio);
  padding: 20px;
  font-size: 14px;
}
.titulo-guardar {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 6px;
}
.acciones {
  display: flex;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.claro {
  background: #fff;
  color: var(--brand-900);
  font-weight: 600;
}
.fantasma,
.enlace-pdf {
  background: transparent;
  color: #fff;
  border-color: rgba(255, 255, 255, 0.4);
}
.aviso {
  background: var(--surface-alt);
  border-left: 3px solid var(--ink-400);
  padding: 12px;
  color: var(--ink-600);
  font-size: 14px;
}
.error {
  color: var(--nivel-alto-fg);
  font-size: 14px;
}
.visualmente-oculto {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
