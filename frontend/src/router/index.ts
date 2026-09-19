import { createRouter, createWebHistory } from 'vue-router'

import CategorizacionView from '@/views/CategorizacionView.vue'
import ChecklistView from '@/views/ChecklistView.vue'
import EstadoView from '@/views/EstadoView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // La categorización es la puerta del producto y se usa sin cuenta (M1).
    { path: '/', name: 'categorizacion', component: CategorizacionView },
    { path: '/estado', name: 'estado', component: EstadoView },
    // Checklist de medidas (M4). El sistema viene en la ruta: un tenant puede tener varios.
    {
      path: '/sistemas/:systemId/medidas',
      name: 'checklist',
      component: ChecklistView,
      props: (ruta) => ({ systemId: Number(ruta.params.systemId) }),
    },
  ],
})
