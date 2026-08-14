import crypto from 'crypto'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

if (typeof crypto.hash !== 'function') {
  // Node < 21.7 / < 20.12: Vite calls crypto.hash during the build.
  crypto.hash = ((algorithm, data, outputEncoding) => {
    const digest = crypto.createHash(algorithm).update(data)
    const encoding =
      typeof outputEncoding === 'string'
        ? outputEncoding
        : outputEncoding && typeof outputEncoding === 'object'
          ? outputEncoding.outputEncoding
          : undefined
    if (encoding && encoding !== 'buffer') {
      return digest.digest(encoding)
    }
    return digest.digest()
  }) as typeof crypto.hash
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    pool: 'threads',
    testTimeout: 30000,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3005',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
