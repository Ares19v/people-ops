import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || `http://127.0.0.1:${process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || process.env.PORT || '38290'}`,
        changeOrigin: true,
      },
    },
  },
})
