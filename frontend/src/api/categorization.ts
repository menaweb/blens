import type { Nivel } from '@/data/dimensiones'
import type { paths } from './schema'

type Preview = paths['/api/categorization/preview']['post']
export type Categorizacion = Preview['responses'][200]['content']['application/json']
export type Niveles = Record<'C' | 'I' | 'T' | 'A' | 'D', Nivel>

type Report = paths['/api/categorization/report']['post']
export type Informe = Report['responses'][200]['content']['application/json']

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function pedir<T>(ruta: string, cuerpo: unknown): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo),
  })
  if (!respuesta.ok) throw new Error(`La API respondió ${respuesta.status}`)
  return respuesta.json() as Promise<T>
}

export const categorizar = (niveles: Niveles) =>
  pedir<Categorizacion>('/api/categorization/preview', niveles)

export const pedirInforme = (niveles: Niveles, organizacion: string, alcance: string) =>
  pedir<Informe>('/api/categorization/report', { ...niveles, organizacion, alcance })
