/**
 * Cliente de la API. Los tipos salen del OpenAPI de Django Ninja
 * (`pnpm gen:api`), nunca se escriben a mano (§15).
 */
import type { paths } from './schema'

export type Health = paths['/api/health']['get']['responses'][200]['content']['application/json']

const BASE = import.meta.env.VITE_API_BASE ?? ''

export async function getHealth(): Promise<Health> {
  const respuesta = await fetch(`${BASE}/api/health`)
  if (!respuesta.ok) throw new Error(`La API respondió ${respuesta.status}`)
  return respuesta.json() as Promise<Health>
}
