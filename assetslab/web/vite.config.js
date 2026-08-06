import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The build output (dist/) is served by the Python preview server
// (lan_preview_server.py) as plain static files, so use relative base and
// hash routing (no history fallback needed).
export default defineConfig({
  plugins: [vue()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/run': 'http://127.0.0.1:8765',
    },
  },
})
