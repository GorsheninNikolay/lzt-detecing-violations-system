import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: { proxy: { '/api': {
    target: loadEnv(mode, '.', 'API_PROXY_TARGET').API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    rewrite: path => path.replace(/^\/api/, ''),
  } } },
  test: { environment: 'jsdom' },
}))
