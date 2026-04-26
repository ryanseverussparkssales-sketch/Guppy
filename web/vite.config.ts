/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

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
    port: 3000,
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
