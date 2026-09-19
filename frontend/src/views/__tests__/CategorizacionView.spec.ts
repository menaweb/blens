import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CategorizacionView from '@/views/CategorizacionView.vue'

const RESULTADO_MEDIA = {
  categoria: 'MEDIA',
  sin_determinar: false,
  aviso: '',
  madurez_minima: 3,
  requiere_certificacion: true,
  dimensiones: [
    { dim: 'C', nombre: 'Confidencialidad', nivel: 'MEDIO', marca_categoria: true },
    { dim: 'I', nombre: 'Integridad', nivel: 'BAJO', marca_categoria: false },
    { dim: 'T', nombre: 'Trazabilidad', nivel: 'NA', marca_categoria: false },
    { dim: 'A', nombre: 'Autenticidad', nivel: 'BAJO', marca_categoria: false },
    { dim: 'D', nombre: 'Disponibilidad', nivel: 'BAJO', marca_categoria: false },
  ],
  resumen: { medidas: 68, evidencias_estimadas: 112, documentos_generables: 31 },
}

function conRespuesta(cuerpo: unknown) {
  return vi.fn().mockResolvedValue({ ok: true, json: async () => cuerpo })
}

async function responderLasCinco(wrapper: ReturnType<typeof mount>) {
  for (let i = 0; i < 5; i += 1) {
    await wrapper.findAll('input[type="radio"]')[2].setValue() // tercera opción: Medio
    await wrapper.find('.primario').trigger('click')
  }
}

describe('CategorizacionView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('empieza en la primera dimensión con el botón bloqueado', () => {
    const wrapper = mount(CategorizacionView)
    expect(wrapper.text()).toContain('Dimensión 1 de 5 · Confidencialidad')
    expect(wrapper.find('.primario').attributes('disabled')).toBeDefined()
  })

  it('desbloquea el botón al elegir una opción', async () => {
    const wrapper = mount(CategorizacionView)
    await wrapper.findAll('input[type="radio"]')[1].setValue()
    expect(wrapper.find('.primario').attributes('disabled')).toBeUndefined()
  })

  it('avanza por las cinco dimensiones y enseña el resultado', async () => {
    vi.stubGlobal('fetch', conRespuesta(RESULTADO_MEDIA))
    const wrapper = mount(CategorizacionView)

    await responderLasCinco(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Media'))

    expect(wrapper.text()).toContain('por confidencialidad')
    expect(wrapper.text()).toContain('68')
    expect(wrapper.text()).toContain('L3')
    expect(wrapper.text()).toContain('certificación')
  })

  it('cuando no hay categoría avisa del alcance y no enseña cifras', async () => {
    vi.stubGlobal(
      'fetch',
      conRespuesta({
        ...RESULTADO_MEDIA,
        categoria: '',
        sin_determinar: true,
        aviso: 'Las cinco dimensiones están en «no aplica»: el alcance está mal delimitado.',
        resumen: {},
      }),
    )
    const wrapper = mount(CategorizacionView)

    await responderLasCinco(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Sin determinar'))

    expect(wrapper.text()).toContain('alcance')
    expect(wrapper.text()).not.toContain('medidas aplicables')
    expect(wrapper.text()).not.toContain('Crear cuenta y guardar')
  })

  it('pide el PDF y ofrece el enlace de descarga', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => RESULTADO_MEDIA })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ token: 'abc', categoria: 'MEDIA', estado: 'PENDIENTE', descarga: '/api/x.pdf' }),
      })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(CategorizacionView)

    await responderLasCinco(wrapper)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Media'))
    await wrapper.find('.fantasma').trigger('click')

    await vi.waitFor(() => expect(wrapper.find('.enlace-pdf').attributes('href')).toBe('/api/x.pdf'))
  })
})
