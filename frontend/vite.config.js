import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: false,
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', changeOrigin: false, xfwd: true },
      '/health': 'http://127.0.0.1:8787',
      '/ready': 'http://127.0.0.1:8787',
      '/plugin-media': 'http://127.0.0.1:8787',
    },
  },
  build: {
    outDir: resolve(__dirname, '../src/plugin_market_backend/static'),
    emptyOutDir: true,
  },
})
