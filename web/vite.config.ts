/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // maplibre-gl v6 loads its worker module relative to itself; pre-bundling breaks that URL.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  build: { chunkSizeWarningLimit: 2000 },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], testTimeout: 30000 },
})
