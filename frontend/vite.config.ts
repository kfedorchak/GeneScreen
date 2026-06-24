import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build into the FastAPI app's static dir so the whole thing deploys as one
// service. In dev, proxy /api to the uvicorn server on :8000.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
