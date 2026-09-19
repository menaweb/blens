/**
 * Perfilado del sistema (M11). Los tipos salen del OpenAPI de Django Ninja,
 * nunca se escriben a mano (§15).
 */
import { mandar, pedir } from './http'
import type { paths } from './schema'

type Get = paths['/api/systems/{system_id}/profiling']['get']
export type Cuestionario = Get['responses'][200]['content']['application/json']
export type Pregunta = Cuestionario['preguntas'][number]
export type Bloque = Cuestionario['bloques'][number]

type Put = paths['/api/systems/{system_id}/profiling/{code}']['put']
export type Respuesta = Put['responses'][200]['content']['application/json']

type Delegacion = paths['/api/systems/{system_id}/profiling/{code}/delegar']['post']
export type Delegado = Delegacion['responses'][200]['content']['application/json']

export const pedirCuestionario = (systemId: number) =>
  pedir<Cuestionario>(`/api/systems/${systemId}/profiling`)

export const responderPregunta = (systemId: number, code: string, valor: unknown) =>
  mandar<Respuesta>(`/api/systems/${systemId}/profiling/${code}`, { valor }, 'PUT')

export const delegarPregunta = (
  systemId: number,
  code: string,
  datos: { usuario_id?: number | null; email?: string; nota?: string },
) => mandar<Delegado>(`/api/systems/${systemId}/profiling/${code}/delegar`, datos)
