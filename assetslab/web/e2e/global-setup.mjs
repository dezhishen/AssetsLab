import { cpSync, mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// E2E 前置：准备干净的 test-data/（复制 data/species，避免污染真实 data/）。
// 后端（playwright webServer）以 --data-dir ../../test-data 启动，测试读写都在 test-data/。
export default async function globalSetup() {
  const here = path.dirname(fileURLToPath(import.meta.url)) // assetslab/web/e2e
  const repoRoot = path.resolve(here, '..', '..', '..')
  const testData = path.join(repoRoot, 'test-data')

  rmSync(testData, { recursive: true, force: true })
  cpSync(path.join(repoRoot, 'data', 'species'), path.join(testData, 'species'), { recursive: true })
  mkdirSync(path.join(testData, 'presets'), { recursive: true })
}

// 直接运行（node global-setup.mjs）时也执行，方便手动准备 test-data；playwright 走 import + 调用 default export。
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  globalSetup().catch((err) => { console.error(err); process.exit(1) })
}
