import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5175,
    // El backend de desarrollo escucha en 8001 (puertos no estándar del proyecto).
    proxy: { '/api': { target: 'http://localhost:8001', changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
