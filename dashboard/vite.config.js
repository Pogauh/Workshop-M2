import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En développement : le moteur de remédiation écoute sur le réseau Docker ; publiez son port pour tester (voir README).
export default defineConfig({
  plugins: [react()],
  server: { port: 5174, proxy: { '/state': 'http://localhost:9000' } },
  build: { sourcemap: false, target: 'es2020' },
})
