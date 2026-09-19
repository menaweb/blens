/**
 * Carpeta de evidencias (M5). Tipos del OpenAPI, igual que el resto (§15).
 */
import { mandar, pedir, subir } from './http'
import type { paths } from './schema'

type Get = paths['/api/systems/{system_id}/evidence']['get']
export type Carpeta = Get['responses'][200]['content']['application/json']
export type Requisito = Carpeta['requisitos'][number]
export type Evidencia = Requisito['evidencias'][number]

export const pedirCarpeta = (systemId: number) =>
  pedir<Carpeta>(`/api/systems/${systemId}/evidence`)

export const aportarEvidencia = (systemId: number, requisitoId: number, datos: FormData) =>
  subir<Carpeta>(`/api/systems/${systemId}/evidence/${requisitoId}/evidencias`, datos)

export const validarEvidencia = (systemId: number, evidenciaId: number) =>
  mandar<Carpeta>(`/api/systems/${systemId}/evidencias/${evidenciaId}/validar`)

export const rechazarEvidencia = (systemId: number, evidenciaId: number, motivo: string) =>
  mandar<Carpeta>(`/api/systems/${systemId}/evidencias/${evidenciaId}/rechazar`, { motivo })

export const noAplica = (systemId: number, requisitoId: number, justificacion: string) =>
  mandar<Carpeta>(`/api/systems/${systemId}/evidence/${requisitoId}/no-aplica`, { justificacion })
