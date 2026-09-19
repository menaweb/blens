/**
 * Cuentas, sesión y miembros (M0). Los tipos salen del OpenAPI (§15).
 */
import { borrar, mandar, pedir } from './http'
import type { paths } from './schema'

type Cuerpo<R> = R extends { requestBody?: { content: { 'application/json': infer B } } }
  ? B
  : never
type Respuesta<R, C extends number> = R extends {
  responses: Record<C, { content: { 'application/json': infer T } }>
}
  ? T
  : never

export type Alta = Cuerpo<paths['/api/auth/register']['post']>
export type AltaHecha = Respuesta<paths['/api/auth/register']['post'], 201>
export type Sesion = Respuesta<paths['/api/auth/login']['post'], 200>
export type Yo = Respuesta<paths['/api/auth/me']['get'], 200>
export type Membresia = Yo['membresias'][number]
export type MfaAlta = Respuesta<paths['/api/auth/mfa/setup']['post'], 200>
export type Invitacion = Respuesta<paths['/api/auth/invitation/{token}']['get'], 200>
export type Miembro = Respuesta<paths['/api/members']['get'], 200>[number]
export type InvitacionPendiente = Respuesta<
  paths['/api/members/invitations']['get'],
  200
>[number]
export type InvitacionEmitida = Respuesta<paths['/api/members/invitations']['post'], 201>
export type Actividad = Respuesta<paths['/api/me/activity']['get'], 200>[number]

// --- Cuenta y sesión ---
export const crearCuenta = (datos: Alta) => mandar<AltaHecha>('/api/auth/register', datos)

export const confirmarCorreo = (email: string, codigo: string) =>
  mandar('/api/auth/confirm', { email, codigo })

export const reenviarCodigo = (email: string) => mandar('/api/auth/resend', { email })

export const entrar = (email: string, password: string) =>
  mandar<Sesion>('/api/auth/login', { email, password })

export const responderMfa = (email: string, codigo: string, sesion: string) =>
  mandar<Sesion>('/api/auth/mfa/challenge', { email, codigo, sesion })

export const salir = () => mandar('/api/auth/logout')

export const quienSoy = () => pedir<Yo>('/api/auth/me')

export const pedirCodigoContrasena = (email: string) =>
  mandar('/api/auth/password/forgot', { email })

export const cambiarContrasena = (email: string, codigo: string, password: string) =>
  mandar('/api/auth/password/reset', { email, codigo, password })

// --- Segundo factor ---
export const empezarMfa = () => mandar<MfaAlta>('/api/auth/mfa/setup')
export const confirmarMfa = (codigo: string) => mandar('/api/auth/mfa/verify', { codigo })

// --- Invitaciones ---
export const verInvitacion = (token: string) =>
  pedir<Invitacion>(`/api/auth/invitation/${encodeURIComponent(token)}`)

export const aceptarInvitacion = (token: string, password: string, nombre: string) =>
  mandar(`/api/auth/invitation/${encodeURIComponent(token)}/accept`, { password, nombre })

// --- Miembros ---
export const pedirMiembros = () => pedir<Miembro[]>('/api/members')
export const pedirInvitaciones = () => pedir<InvitacionPendiente[]>('/api/members/invitations')

export const invitar = (datos: {
  email: string
  role: string
  membership_dias?: number | null
}) => mandar<InvitacionEmitida>('/api/members/invitations', datos)

export const revocarInvitacion = (id: number) => borrar(`/api/members/invitations/${id}`)

export const cambiarRol = (id: number, role: string) =>
  mandar<Miembro>(`/api/members/${id}`, { role }, 'PATCH')

export const revocarMiembro = (id: number) => mandar<Miembro>(`/api/members/${id}/revoke`)

export const transferirPropiedad = (id: number) =>
  mandar<Miembro>(`/api/members/${id}/transfer-ownership`)

export const restablecerMfaDe = (id: number) => mandar(`/api/members/${id}/reset-mfa`)

export const miActividad = () => pedir<Actividad[]>('/api/me/activity')
