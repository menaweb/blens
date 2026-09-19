import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import EstadoView from '@/views/EstadoView.vue'

describe('EstadoView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('muestra el estado que devuelve la API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok', version: '0.1.0', database: 'ok' }),
      }),
    )

    const wrapper = mount(EstadoView)
    await vi.waitFor(() => expect(wrapper.text()).toContain('API 0.1.0'))
    expect(wrapper.text()).toContain('base de datos ok')
  })

  it('avisa cuando la API no responde', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))

    const wrapper = mount(EstadoView)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Sin conexión con la API'))
  })
})
