/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Allow the dev-server port to be overridden via VITE_PORT so that Playwright
// (and any scripts that need a predictable URL) can stay in sync when the
// default port 3000 is busy.  strictPort stays false — Vite will still
// auto-increment if the chosen port is taken, but callers can pin a port they
// know is free by exporting VITE_PORT=3003 before running `npm run dev`.
const DEV_PORT = parseInt(process.env.VITE_PORT ?? '3000', 10)

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['src/__tests__/e2e/**', 'node_modules/**'],
    coverage: {
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/__tests__/**'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: DEV_PORT,
    strictPort: false,
    host: true,
    headers: {
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy': 'camera=(), microphone=(self), geolocation=()',
    },
    proxy: {
      '/api':       { target: 'http://localhost:8081', changeOrigin: true },
      '/providers': { target: 'http://localhost:8081', changeOrigin: true },
      '/metrics':   { target: 'http://localhost:8081', changeOrigin: true },
      '/status':    { target: 'http://localhost:8081', changeOrigin: true },
      '/logs':      { target: 'http://localhost:8081', changeOrigin: true },
      '/telemetry': { target: 'http://localhost:8081', changeOrigin: true },
      '/repair':    { target: 'http://localhost:8081', changeOrigin: true },
      '/auth':      { target: 'http://localhost:8081', changeOrigin: true },
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
    rollupOptions: {
      input: 'index.html',
    },
    // Warn if any chunk exceeds 600 KB — catches accidental bundle bloat
    chunkSizeWarningLimit: 600,
  },
})
