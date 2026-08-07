import { defineConfig } from '@playwright/test'

// E2E 全量测试（前端）：自动起 后端(8765, --dev 含 CORS) + 前端 Vite(5173, proxy /api→8765)。
// 运行：pnpm run test:e2e
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  retries: 0,
  workers: 1,
  globalSetup: './e2e/global-setup.mjs',
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      // 后端 API（dev 模式：CORS + 默认 8765，数据目录用 test-data/，测试不污染真实 data/）
      command: '../../.venv/bin/python ../server.py --dev --port 8765 --data-dir ../../test-data',
      url: 'http://127.0.0.1:8765/api/species',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      // 前端 Vite dev（proxy /api → 8765）
      command: 'pnpm dev --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
