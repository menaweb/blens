import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChecklistView from '@/views/ChecklistView.vue'

function fila(extra: Record<string, unknown> = {}) {
  return {
    code: 'op.exp.6',
    nombre: 'Protección frente a código dañino',
    marco: 'op',
    familia: 'op.exp',
    aplica: true,
    motivo: 'categoría MEDIA',
    madurez: 2,
    objetivo: 3,
    delta: -1,
    semaforo: 'AMARILLO',
    madurez_pct: 50,
    cumplimiento_pct: 62.5,
    no_soportada: false,
    responsable: 'Marta Ruiz',
    responsable_id: 3,
    fecha_limite: '2027-01-31',
    notas: '',
    ...extra,
  }
}

const CHECKLIST = {
  system_id: 1,
  sistema: 'Sede electrónica',
  categoria: 'MEDIA',
  objetivo_categoria: 3,
  escala: { L0: 'inexistente', L3: 'definido' },
  medidas: [
    fila(),
    fila({
      code: 'org.1',
      nombre: 'Política de seguridad',
      familia: 'org',
      marco: 'org',
      madurez: 4,
      delta: 1,
      semaforo: 'VERDE',
      cumplimiento_pct: 100,
      no_soportada: true,
    }),
    fila({
      code: 'op.nub.1',
      nombre: 'Protección de servicios en la nube',
      familia: 'op.nub',
      aplica: false,
      madurez: null,
      delta: null,
      semaforo: 'GRIS',
    }),
  ],
  sistema_indice: {
    clave: 'MEDIA',
    medidas: 2,
    con_datos: 2,
    en_objetivo: 0,
    no_soportadas: 1,
    madurez: 50,
    cumplimiento: 62.5,
    madurez_media: 70,
    peor: 'op.exp.6',
  },
  por_marco: {},
  por_familia: {},
  brechas: ['op.exp.6'],
}

function respuesta(cuerpo: unknown) {
  return { ok: true, json: async () => cuerpo }
}

/** Los códigos de las filas visibles de la tabla, sin el ruido del resto de la página. */
function codigos(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('tbody .medida code').map((c) => c.text())
}

async function montar() {
  const wrapper = mount(ChecklistView, { props: { systemId: 1 } })
  await vi.waitFor(() => expect(wrapper.text()).toContain('op.exp.6'))
  return wrapper
}

describe('ChecklistView', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(CHECKLIST)))
  })

  it('enseña el índice como el peor componente y dice quién lo marca', async () => {
    const wrapper = await montar()
    expect(wrapper.text()).toContain('62.5%')
    expect(wrapper.text()).toContain('peor componente')
    expect(wrapper.text()).toContain('op.exp.6')
  })

  it('marca la madurez no soportada y explica por qué no suma', async () => {
    const wrapper = await montar()
    expect(wrapper.text()).toContain('sin evidencia validada, no suma al indicador')
  })

  it('pinta el delta con el semáforo que da el motor', async () => {
    const wrapper = await montar()
    const deltas = wrapper.findAll('.delta')
    expect(deltas[0].classes()).toContain('amarillo')
    expect(deltas[0].text()).toBe('-1')
    expect(deltas[1].text()).toBe('+1')
  })

  it('una medida que no aplica no enseña delta y se ve aparte', async () => {
    const wrapper = await montar()
    await wrapper.findAll('.filtro')[4].trigger('click')
    const delta = wrapper.find('.delta')
    expect(delta.classes()).toContain('gris')
    expect(delta.text()).toBe('—')
  })

  it('filtra y recalcula los contadores', async () => {
    const wrapper = await montar()
    const filtros = wrapper.findAll('.filtro')
    // «Todas» son las aplicables: las que no aplican tienen su propio filtro.
    expect(filtros[0].text()).toContain('2')
    expect(filtros[2].text()).toContain('1') // madurez no soportada
    expect(filtros[4].text()).toContain('1') // no aplican

    await filtros[4].trigger('click')
    expect(codigos(wrapper)).toEqual(['op.nub.1'])
  })

  it('busca por código y por nombre', async () => {
    const wrapper = await montar()
    await wrapper.find('.buscador').setValue('política')
    expect(codigos(wrapper)).toEqual(['org.1'])

    await wrapper.find('.buscador').setValue('op.exp')
    expect(codigos(wrapper)).toEqual(['op.exp.6'])
  })

  it('guarda la madurez y avisa de lo que ha hecho', async () => {
    const wrapper = await montar()
    const enviar = vi.fn().mockResolvedValue(respuesta(CHECKLIST))
    vi.stubGlobal('fetch', enviar)

    await wrapper.findAll('.selector')[0].setValue('4')
    await vi.waitFor(() => expect(enviar).toHaveBeenCalled())

    const [url, opciones] = enviar.mock.calls[0]
    expect(url).toContain('/api/systems/1/checklist/op.exp.6')
    expect(opciones.method).toBe('PATCH')
    expect(JSON.parse(opciones.body)).toEqual({ maturity_level: 4 })
    await vi.waitFor(() => expect(wrapper.text()).toContain('madurez L4 · guardado'))
  })

  it('permite volver a dejar una medida sin valorar', async () => {
    const wrapper = await montar()
    const enviar = vi.fn().mockResolvedValue(respuesta(CHECKLIST))
    vi.stubGlobal('fetch', enviar)

    await wrapper.findAll('.selector')[0].setValue('')
    await vi.waitFor(() => expect(enviar).toHaveBeenCalled())
    expect(JSON.parse(enviar.mock.calls[0][1].body)).toEqual({ limpiar: ['maturity_level'] })
  })

  it('al marcar no aplicable recuerda que falta justificarlo', async () => {
    const wrapper = await montar()
    const enviar = vi.fn().mockResolvedValue(respuesta(CHECKLIST))
    vi.stubGlobal('fetch', enviar)

    await wrapper.findAll('.chip')[0].trigger('click')
    await vi.waitFor(() => expect(enviar).toHaveBeenCalled())
    expect(JSON.parse(enviar.mock.calls[0][1].body)).toEqual({ applies: false })
    await vi.waitFor(() => expect(wrapper.text()).toContain('falta la justificación en la DdA'))
  })

  it('avisa con salida cuando la API falla', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    const wrapper = mount(ChecklistView, { props: { systemId: 1 } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('La API respondió 500'))
    expect(wrapper.find('[role="alert"]').text()).toContain('Reintentar')
  })
})
