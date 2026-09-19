import { createRouter, createWebHistory } from 'vue-router'

import CategorizacionView from '@/views/CategorizacionView.vue'
import EstadoView from '@/views/EstadoView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // La categorización es la puerta del producto y se usa sin cuenta (M1).
    { path: '/', name: 'categorizacion', component: CategorizacionView },
    { path: '/estado', name: 'estado', component: EstadoView },
  ],
})
