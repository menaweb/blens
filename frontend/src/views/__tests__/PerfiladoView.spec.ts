import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PerfiladoView from '@/views/PerfiladoView.vue'

function pregunta(extra: Record<string, unknown> = {}) {
  return {
    code: 'mp.if.areas',
    bloque: 'B04',
    tipo: 'MULTI',
    texto: '¿Dónde están los equipos que sostienen el servicio?',
    por_que: 'Marca qué hay que proteger físicamente.',
    como_saberlo: 'Piensa dónde están los servidores y el rack.',
    a_quien_preguntar: 'Quien lleva el mantenimiento del edificio',
    glosario: { CPD: 'La sala donde están los servidores' },
    campos: [],
    opciones: [
      { code: 'cpd', label: 'Sala o CPD propio dedicado' },
      { code: 'proveedor', label: 'En instalaciones de un proveedor o en la nube' },
    ],
    minutos_estimados: 1,
    respondida: false,
    valor: null,
    delegada_a: null,
    ...extra,
  }
}

const CUESTIONARIO = {
  system_id: 1,
  sistema: 'Sede electrónica',
  categoria: 'MEDIA',
  bloques: [
    { bloque: 'B04', titulo: 'Instalaciones propias', total: 2, respondidas: 0, minutos: 4 },
    { bloque: 'B07', titulo: 'Inventario y arquitectura', total: 3, respondidas: 3, minutos: 0 },
  ],
  preguntas: [pregunta(), pregunta({ code: 'mp.if.acceso', texto: '¿Cómo se entra?' })],
  pendientes: 2,
}

const RESPUESTA = {
  hechos: { instalacion_cpd: true },
  requisitos_nuevos: ['EV-mp.if.1-01', 'EV-mp.if.1-02'],
  requisitos_fuera_de_alcance: [],
  cuestionario: {
    ...CUESTIONARIO,
    pendientes: 1,
    bloques: [
      { bloque: 'B04', titulo: 'Instalaciones propias', total: 2, respondidas: 1, minutos: 2 },
      { bloque: 'B07', titulo: 'Inventario y arquitectura', total: 3, respondidas: 3, minutos: 0 },
    ],
  },
}

function respuesta(cuerpo: unknown) {
  return { ok: true, status: 200, json: async () => cuerpo }
}

async function montar() {
  const wrapper = mount(PerfiladoView, { props: { systemId: 1 } })
  await vi.waitFor(() => expect(wrapper.text()).toContain('¿Dónde están los equipos'))
  return wrapper
}

describe('PerfiladoView', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(CUESTIONARIO)))
  })

  it('cada pregunta llega con sus apoyos para poder contestarla', async () => {
    const wrapper = await montar()
    expect(wrapper.text()).toContain('Por qué se pregunta')
    expect(wrapper.text()).toContain('Marca qué hay que proteger físicamente')
    expect(wrapper.text()).toContain('Cómo saberlo')
    expect(wrapper.text()).toContain('La sala donde están los servidores')
  })

  it('no existe la opción «no lo sé»: se le pregunta a alguien con nombre', async () => {
    const wrapper = await montar()
    const opciones = wrapper.findAll('.opcion').map((o) => o.text().toLowerCase())
    expect(opciones.some((o) => o.includes('no lo sé'))).toBe(false)

    await wrapper.find('.terciario').trigger('click')
    expect(wrapper.text()).toContain('¿Quién lo sabe?')
    // Sin destinatario no se crea la tarea.
    expect(wrapper.find('.delegar .primario').attributes('disabled')).toBeDefined()
  })

  it('el bloque dice cuánto queda y cuánto se tarda', async () => {
    const wrapper = await montar()
    expect(wrapper.text()).toContain('Instalaciones propias')
    expect(wrapper.text()).toContain('0/2')
    expect(wrapper.text()).toContain('4 min')
    expect(wrapper.text()).toContain('2 preguntas por responder')
  })

  it('responder cuenta lo que cambia en la carpeta', async () => {
    const wrapper = await montar()
    const fetchMock = vi.fn().mockResolvedValue(respuesta(RESPUESTA))
    vi.stubGlobal('fetch', fetchMock)

    await wrapper.findAll('.opcion')[0].trigger('click')
    await wrapper.find('.acciones .primario').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('2 evidencias nuevas'))

    const [url, opciones] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/systems/1/profiling/mp.if.areas')
    expect(opciones.method).toBe('PUT')
    expect(JSON.parse(opciones.body)).toEqual({ valor: ['cpd'] })
    expect(wrapper.text()).toContain('Guardado a las')
  })

  it('sin responder nada no se puede guardar', async () => {
    const wrapper = await montar()
    expect(wrapper.find('.acciones .primario').attributes('disabled')).toBeDefined()
  })
})
