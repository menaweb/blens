import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CarpetaEvidenciasView from '@/views/CarpetaEvidenciasView.vue'

function requisito(extra: Record<string, unknown> = {}) {
  return {
    id: 1,
    code: 'EV-mp.if.1-01',
    measure: 'mp.if.1',
    familia: 'mp.if',
    marco: 'mp',
    titulo: 'Registro de entradas y salidas del CPD',
    instrucciones: 'Aporta el registro del último trimestre, con fecha y nombre de quien entra.',
    tipo: 'REGISTRO',
    formatos: ['pdf', 'xlsx'],
    criterios_aceptacion: ['Se ve la fecha', 'Se ve quién entra y quién autoriza'],
    rechazos_tipicos: ['Registro sin fechas', 'Hoja en blanco firmada a posteriori'],
    pistas: ['Consola del control de accesos → Informes → Exportar'],
    obligatoria: true,
    generable: false,
    vigencia_dias: 180,
    carpeta_paquete: '06_[mp]/mp.if.1',
    estado: 'PENDIENTE',
    motivo: 'la medida mp.if.1 aplica a un sistema de categoría MEDIA',
    origen: { preguntas: ['mp.if.areas'], hechos: { instalacion_cpd: true } },
    option_group: 'mp.if.1.acceso',
    alternativas: ['EV-mp.if.1-02'],
    cubierto_por_grupo: false,
    responsable_id: null,
    fecha_limite: null,
    proxima_renovacion: null,
    justificacion: '',
    evidencias: [],
    ...extra,
  }
}

const CARPETA = {
  system_id: 1,
  sistema: 'Sede electrónica',
  categoria: 'MEDIA',
  requisitos: [
    requisito(),
    requisito({
      id: 2,
      code: 'EV-mp.if.1-02',
      titulo: 'Captura del control de accesos',
      estado: 'PENDIENTE',
      cubierto_por_grupo: true,
      alternativas: ['EV-mp.if.1-01'],
    }),
    requisito({
      id: 3,
      code: 'EV-org.1-01',
      measure: 'org.1',
      familia: 'org',
      marco: 'org',
      titulo: 'Política de seguridad aprobada',
      carpeta_paquete: '00_Gobernanza',
      estado: 'VALIDADA',
      rechazos_tipicos: [],
      evidencias: [
        {
          id: 9,
          titulo: 'Política firmada',
          nombre_original: 'politica.pdf',
          fecha_evidencia: '2026-03-02',
          estado: 'VALIDADA',
          motivo_rechazo: '',
          aportada_por: 'Marta Ruiz',
          url: '/media/politica.pdf',
        },
      ],
    }),
  ],
  huecos: 1,
  obligatorios: 3,
  completitud: 66.6,
  por_familia: { 'mp.if': { total: 2, huecos: 1 }, org: { total: 1, huecos: 0 } },
}

function respuesta(cuerpo: unknown) {
  return { ok: true, status: 200, json: async () => cuerpo }
}

async function montar() {
  const wrapper = mount(CarpetaEvidenciasView, { props: { systemId: 1 } })
  await vi.waitFor(() => expect(wrapper.text()).toContain('Registro de entradas'))
  return wrapper
}

describe('CarpetaEvidenciasView', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(CARPETA)))
  })

  it('enseña lo que falta sin maquillarlo', async () => {
    const wrapper = await montar()
    expect(wrapper.text()).toContain('66.6%')
    expect(wrapper.text()).toContain('no redondea al alza')
    expect(wrapper.text()).toContain('la conformidad la declara el auditor')
  })

  it('avisa de los rechazos típicos antes de la zona de subida', async () => {
    const wrapper = await montar()
    const texto = wrapper.find('.detalle').text()
    expect(texto).toContain('Por esto se suele rechazar')
    expect(texto.indexOf('Por esto se suele rechazar')).toBeLessThan(texto.indexOf('Aportar'))
    expect(texto).toContain('Registro sin fechas')
  })

  it('cada hueco dice por qué se pide y de qué respuesta sale', async () => {
    const wrapper = await montar()
    const texto = wrapper.find('.detalle').text()
    expect(texto).toContain('la medida mp.if.1 aplica')
    expect(texto).toContain('mp.if.areas')
    expect(texto).toContain('Con una de estas basta')
  })

  it('lo que ya cubre otra alternativa no cuenta como hueco', async () => {
    const wrapper = await montar()
    // El filtro de «lo que falta» deja fuera al hermano cubierto y a lo ya validado.
    expect(wrapper.findAll('.requisito')).toHaveLength(1)

    await wrapper.findAll('.filtro')[5].trigger('click')
    expect(wrapper.findAll('.requisito')).toHaveLength(3)
    expect(wrapper.text()).toContain('Cubierto por otra opción')
  })

  it('no se sube nada sin fichero y sin la fecha del hecho', async () => {
    const wrapper = await montar()
    expect(wrapper.find('.subida .primario').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('no cuándo lo subes')
  })

  it('marcar como no aplica exige justificación', async () => {
    const wrapper = await montar()
    const boton = wrapper.find('.descartar .secundario')
    expect(boton.attributes('disabled')).toBeDefined()

    const fetchMock = vi.fn().mockResolvedValue(respuesta(CARPETA))
    vi.stubGlobal('fetch', fetchMock)
    await wrapper.find('.descartar input').setValue('La sala no tiene ventanas al exterior')
    await wrapper.find('.descartar .secundario').trigger('click')

    const [url, opciones] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/systems/1/evidence/1/no-aplica')
    expect(JSON.parse(opciones.body).justificacion).toContain('ventanas')
  })

  it('el filtro de validadas enseña lo aportado con su fecha', async () => {
    const wrapper = await montar()
    await wrapper.findAll('.filtro')[2].trigger('click')
    expect(wrapper.text()).toContain('Política de seguridad aprobada')

    await wrapper.findAll('.requisito')[0].trigger('click')
    const texto = wrapper.find('.detalle').text()
    expect(texto).toContain('Política firmada')
    expect(texto).toContain('2026-03-02')
    expect(texto).toContain('Quien aporta una evidencia no puede validarla')
  })
})
