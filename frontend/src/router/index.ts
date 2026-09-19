import { createRouter, createWebHistory } from 'vue-router'

import AceptarInvitacionView from '@/views/AceptarInvitacionView.vue'
import CarpetaEvidenciasView from '@/views/CarpetaEvidenciasView.vue'
import CategorizacionView from '@/views/CategorizacionView.vue'
import ChecklistView from '@/views/ChecklistView.vue'
import CrearCuentaView from '@/views/CrearCuentaView.vue'
import EstadoView from '@/views/EstadoView.vue'
import IniciarSesionView from '@/views/IniciarSesionView.vue'
import PerfilView from '@/views/PerfilView.vue'
import PerfiladoView from '@/views/PerfiladoView.vue'
import RecuperarView from '@/views/RecuperarView.vue'
import UsuariosView from '@/views/UsuariosView.vue'
import { useCuentaStore } from '@/stores/cuenta'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // La categorización es la puerta del producto y se usa sin cuenta (M1).
    { path: '/', name: 'categorizacion', component: CategorizacionView },
    { path: '/estado', name: 'estado', component: EstadoView, meta: { sesion: true } },
    // Cuenta y acceso (M0). Fuera de la aplicación: sin barra lateral y sin sesión.
    { path: '/crear-cuenta', name: 'crear-cuenta', component: CrearCuentaView },
    { path: '/entrar', name: 'entrar', component: IniciarSesionView },
    { path: '/recuperar', name: 'recuperar', component: RecuperarView },
    { path: '/invitacion/:token', name: 'invitacion', component: AceptarInvitacionView },
    { path: '/usuarios', name: 'usuarios', component: UsuariosView, meta: { sesion: true } },
    { path: '/perfil', name: 'perfil', component: PerfilView, meta: { sesion: true } },
    // Checklist de medidas (M4). El sistema viene en la ruta: un tenant puede tener varios.
    {
      path: '/sistemas/:systemId/medidas',
      name: 'checklist',
      component: ChecklistView,
      props: (ruta) => ({ systemId: Number(ruta.params.systemId) }),
    },
    // Perfilado (M11) y carpeta de evidencias (M5): el eje del producto.
    {
      path: '/sistemas/:systemId/perfilado',
      name: 'perfilado',
      component: PerfiladoView,
      meta: { sesion: true },
      props: (ruta) => ({ systemId: Number(ruta.params.systemId) }),
    },
    {
      path: '/sistemas/:systemId/evidencias',
      name: 'evidencias',
      component: CarpetaEvidenciasView,
      meta: { sesion: true },
      props: (ruta) => ({ systemId: Number(ruta.params.systemId) }),
    },
  ],
})

/**
 * Guarda de sesión. No sustituye a la comprobación del servidor —el permiso lo decide
 * `can()` en la API—, solo evita enseñar pantallas vacías a quien no ha entrado.
 */
router.beforeEach(async (destino) => {
  if (!destino.meta.sesion) return true
  const cuenta = useCuentaStore()
  if (!cuenta.comprobado) await cuenta.cargar()
  if (!cuenta.autenticado) return { name: 'entrar', query: { siguiente: destino.fullPath } }
  // Con el segundo factor pendiente solo se puede ir a activarlo.
  if (cuenta.mfaPendiente && destino.name !== 'perfil') return { name: 'perfil' }
  return true
})
