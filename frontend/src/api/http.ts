/**
 * Llamadas a la API, con lo que comparten todas: la cookie de sesión va incluida,
 * el CSRF se manda en las escrituras y el error del servidor llega con su texto.
 *
 * El token de acceso **no se toca desde aquí**: vive en una cookie HttpOnly que el
 * navegador no puede leer (D1). Por eso `credentials: 'include'` y nada de cabeceras
 * de autorización.
 */
const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ErrorApi extends Error {
  constructor(
    mensaje: string,
    readonly estado: number,
  ) {
    super(mensaje)
  }
}

function cookie(nombre: string): string {
  const par = document.cookie.split('; ').find((c) => c.startsWith(`${nombre}=`))
  return par ? decodeURIComponent(par.slice(nombre.length + 1)) : ''
}

async function enviar<T>(url: string, opciones: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`${BASE}${url}`, { credentials: 'include', ...opciones })
  if (respuesta.status === 204) return undefined as T
  const cuerpo = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    // Django Ninja manda el motivo en `detail`; si no lo hay, algo se rompió de verdad.
    const detalle =
      (cuerpo && (cuerpo.detail || cuerpo.message)) ??
      'No hemos podido completar la operación. Inténtalo de nuevo.'
    throw new ErrorApi(String(detalle), respuesta.status)
  }
  return cuerpo as T
}

export const pedir = <T>(url: string) => enviar<T>(url)

export const mandar = <T>(url: string, datos?: unknown, metodo = 'POST') =>
  enviar<T>(url, {
    method: metodo,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
    body: datos === undefined ? undefined : JSON.stringify(datos),
  })

export const borrar = <T>(url: string) =>
  enviar<T>(url, { method: 'DELETE', headers: { 'X-CSRFToken': cookie('csrftoken') } })
