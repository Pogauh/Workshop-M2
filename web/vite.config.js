import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En développement, l'API et l'authentification sont servies par le WAF de la plateforme (docker compose up).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8080', '/auth': 'http://localhost:8080' } },
  build: { sourcemap: false, target: 'es2020' },
})
