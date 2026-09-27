import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { demoPlugin } from './demo/server'

export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'demo' ? [demoPlugin()] : [])],
  server: { proxy: mode === 'demo' ? undefined : { '/api': {
    target: loadEnv(mode, '.', 'API_PROXY_TARGET').API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    rewrite: path => path.replace(/^\/api/, ''),
  } } },
  test: { environment: 'jsdom' },
}))
