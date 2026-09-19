import { createRouter, createWebHistory } from 'vue-router'

import EstadoView from '@/views/EstadoView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'estado', component: EstadoView }],
})
