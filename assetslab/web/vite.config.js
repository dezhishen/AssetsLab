import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Dev 模式（热更新）：
//   - 前端：pnpm run dev        → Vite dev server (http://localhost:5173)
//   - 后端：pnpm run dev:api    → python server.py --dev (http://127.0.0.1:8765, 含 CORS)
//   - /api、/run 请求经 proxy 转发到后端（避免 CORS，热更新即时生效）
// 生产：npm run build 输出 dist/，由 Python server 直接静态服务。
const API_TARGET = process.env.API_TARGET || 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/run': { target: API_TARGET, changeOrigin: true },
    },
  },
})
