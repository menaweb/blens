/**
 * Pantallas de cuenta y acceso (P16-P20).
 *
 * Lo que se prueba es lo que decide si alguien entra o se queda fuera: que el alta
 * enseña lo que está guardando, que los estados incómodos (resultado caducado,
 * invitación que ya no vale) se explican, y que cuando el servidor dice que no se puede,
 * se enseña su motivo y no un «error».
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AceptarInvitacionView from '@/views/AceptarInvitacionView.vue'
import CrearCuentaView from '@/views/CrearCuentaView.vue'
import UsuariosView from '@/views/UsuariosView.vue'

const empujar = vi.fn()
let consulta: Record<string, string> = {}
let parametros: Record<string, string> = {}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: empujar }),
  useRoute: () => ({ query: consulta, params: parametros }),
  RouterLink: { template: '<a><slot /></a>' },
}))

function ok(cuerpo: unknown) {
  return { ok: true, status: 200, json: async () => cuerpo }
}

function fallo(estado: number, detalle: string) {
  return { ok: false, status: estado, json: async () => ({ detail: detalle }) }
}

beforeEach(() => {
  setActivePinia(createPinia())
  empujar.mockClear()
  consulta = {}
  parametros = {}
})

describe('P16 · Crear cuenta desde el resultado', () => {
  it('enseña arriba la categoría que se está guardando', async () => {
    consulta = { resultado: 'tok-1' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ok({ categoria: 'MEDIA', estado: 'LISTO' })),
    )

    const vista = mount(CrearCuentaView)
    await vi.waitFor(() => expect(vista.text()).toContain('Categoría MEDIA'))

    expect(vista.text()).toContain('Vas a guardar tu categorización')
  })

  it('si el resultado caducó lo dice sin bloquear el alta', async () => {
    consulta = { resultado: 'tok-viejo' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => fallo(404, 'El informe ha caducado.')),
    )

    const vista = mount(CrearCuentaView)
    await vi.waitFor(() => expect(vista.text()).toContain('ya no está disponible'))

    // El formulario sigue ahí: el alta no depende del resultado.
    expect(vista.find('form').exists()).toBe(true)
  })

  it('tras crear la cuenta pide el código del correo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ok({ email: 'a@b.test', organizacion: 'X', system_id: 1, aviso: '' })),
    )

    const vista = mount(CrearCuentaView)
    await vista.find('input[type="email"]').setValue('a@b.test')
    await vista.find('input[type="password"]').setValue('contrasena-larga')
    await vista.find('form').trigger('submit')
    await vi.waitFor(() => expect(vista.text()).toContain('Confirma tu correo'))

    expect(vista.text()).toContain('a@b.test')
  })
})

describe('P18 · Aceptar invitación', () => {
  it('dice quién invita, a qué organización y con qué papel', async () => {
    parametros = { token: 'tok' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        ok({
          organizacion: 'Ayuntamiento de Ejemplo',
          email: 'ana@ayto.test',
          role: 'TECNICO',
          role_nombre: 'Técnico',
          invitado_por: 'marta@ayto.test',
          caduca: '2026-10-01T00:00:00',
          tiene_cuenta: false,
        }),
      ),
    )

    const vista = mount(AceptarInvitacionView)
    await vi.waitFor(() => expect(vista.text()).toContain('Ayuntamiento de Ejemplo'))

    expect(vista.text()).toContain('Técnico')
    expect(vista.text()).toContain('marta@ayto.test')
    expect(vista.find('input[type="password"]').exists()).toBe(true)
  })

  it('a quien ya tiene cuenta no le pide contraseña', async () => {
    parametros = { token: 'tok' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        ok({
          organizacion: 'X',
          email: 'ana@ayto.test',
          role: 'CONSULTOR',
          role_nombre: 'Consultor',
          invitado_por: '',
          caduca: '2026-10-01T00:00:00',
          tiene_cuenta: true,
        }),
      ),
    )

    const vista = mount(AceptarInvitacionView)
    await vi.waitFor(() => expect(vista.text()).toContain('Ya tienes cuenta'))

    expect(vista.find('input[type="password"]').exists()).toBe(false)
  })

  it('una invitación que ya no vale explica la salida', async () => {
    parametros = { token: 'tok' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => fallo(410, 'Esta invitación ya se usó.')),
    )

    const vista = mount(AceptarInvitacionView)
    await vi.waitFor(() => expect(vista.text()).toContain('ya no vale'))

    expect(vista.text()).toContain('Esta invitación ya se usó.')
    expect(vista.text()).toContain('que te mande otra')
  })
})

describe('P19 · Usuarios y roles', () => {
  const MIEMBRO = {
    id: 7,
    email: 'marta@ayto.test',
    nombre: 'Marta',
    role: 'PROPIETARIO',
    role_nombre: 'Propietario',
    estado: 'ACTIVA',
    expires_at: '',
    caducada: false,
    mfa_activado: true,
    systems: [],
    bloques: [],
  }

  function servidor(respuestas: Record<string, unknown>) {
    return vi.fn(async (url: string) => {
      const clave = Object.keys(respuestas).find((k) => String(url).includes(k))
      return clave ? respuestas[clave] : ok([])
    })
  }

  it('marca con su fecha los accesos temporales', async () => {
    vi.stubGlobal(
      'fetch',
      servidor({
        '/api/members/invitations': ok([]),
        '/api/members': ok([
          { ...MIEMBRO, role: 'AUDITOR', role_nombre: 'Auditor', expires_at: '2026-12-31T00:00:00' },
        ]),
      }),
    )

    const vista = mount(UsuariosView)
    await vi.waitFor(() => expect(vista.text()).toContain('Caduca el'))
  })

  it('cuando el servidor impide dejar la organización sin propietario, enseña su motivo', async () => {
    const motivo =
      'Es la única propietaria de la organización. Transfiere antes la propiedad: si nadie ' +
      'la tiene, nadie puede gestionar usuarios ni facturación.'
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, opciones?: RequestInit) => {
        if (opciones?.method === 'PATCH') return fallo(409, motivo)
        if (String(url).includes('/api/members/invitations')) return ok([])
        return ok([MIEMBRO])
      }),
    )

    const vista = mount(UsuariosView)
    await vi.waitFor(() => expect(vista.text()).toContain('marta@ayto.test'))
    await vista.find('tbody select').setValue('TECNICO')
    await vi.waitFor(() => expect(vista.text()).toContain('Transfiere antes la propiedad'))
  })
})
