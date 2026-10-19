import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // preview against a hidden Cloud Run revision: API_TARGET=https://<tag>---redstring-api-....run.app
    proxy: { '/api': { target: process.env.API_TARGET ?? 'http://localhost:8080', changeOrigin: true } },
  },
})
