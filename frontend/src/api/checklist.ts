/**
 * Checklist de medidas (M4). Los tipos salen del OpenAPI de Django Ninja,
 * nunca se escriben a mano (§15).
 */
import type { paths } from './schema'

type Get = paths['/api/systems/{system_id}/checklist']['get']
export type Checklist = Get['responses'][200]['content']['application/json']
export type Fila = Checklist['medidas'][number]
export type Indice = Checklist['sistema_indice']

type Patch = paths['/api/systems/{system_id}/checklist/{code}']['patch']
export type CambioMedida = NonNullable<Patch['requestBody']>['content']['application/json']

const BASE = import.meta.env.VITE_API_BASE ?? ''

function cookie(nombre: string): string {
  const par = document.cookie.split('; ').find((c) => c.startsWith(`${nombre}=`))
  return par ? decodeURIComponent(par.slice(nombre.length + 1)) : ''
}

async function respuesta<T>(peticion: Promise<Response>): Promise<T> {
  const r = await peticion
  if (!r.ok) throw new Error(`La API respondió ${r.status}`)
  return r.json() as Promise<T>
}

export const pedirChecklist = (systemId: number) =>
  respuesta<Checklist>(fetch(`${BASE}/api/systems/${systemId}/checklist`, { credentials: 'include' }))

export const guardarMedida = (systemId: number, code: string, cambio: CambioMedida) =>
  respuesta<Checklist>(
    fetch(`${BASE}/api/systems/${systemId}/checklist/${code}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
      body: JSON.stringify(cambio),
    }),
  )
