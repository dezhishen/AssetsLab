import { test, expect } from '@playwright/test'

// 物种管理全量 E2E：列表 / 详情 / 骨架预览(渲染+相机) / 动作编辑器(预览+拖拽+GIF 导出)
test.describe('物种管理（全量 E2E）', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/species')
  })

  test('物种列表加载并显示 human', async ({ page }) => {
    await expect(page.locator('.list-item .item-name', { hasText: '人类骨骼拓扑' })).toBeVisible()
  })

  test('选择物种 → 详情统计卡 + 骨骼拓扑 tab', async ({ page }) => {
    await page.locator('.list-item .item-main', { hasText: '人类骨骼拓扑' }).click()
    await expect(page.locator('.crumb-now', { hasText: '人类骨骼拓扑' })).toBeVisible()
    // 统计卡：36 关节 / 35 骨(bones_3d) / 1 动作
    await expect(page.locator('.stat-card .stat-val', { hasText: '36' }).first()).toBeVisible()
    await expect(page.locator('.stat-card .stat-val', { hasText: '35' })).toBeVisible()
    // 关节链内容（spine 链）
    await expect(page.locator('.chain-row', { hasText: 'spine' }).first()).toBeVisible()
    // 参数链表
    await expect(page.locator('.el-table', { hasText: 'head_scale' }).first()).toBeVisible()
  })

  test('骨架预览：渲染 → 快捷视角 → 相机收纳面板', async ({ page }) => {
    await page.locator('.list-item .item-main', { hasText: '人类骨骼拓扑' }).click()
    await page.locator('.el-tabs__item', { hasText: '骨架预览' }).click()
    // 点渲染生成骨架图
    await page.locator('button', { hasText: '渲染' }).click()
    await expect(page.locator('.skel-draggable img')).toBeVisible({ timeout: 30_000 })
    // 快捷视角按钮：点侧面 → 高亮 + 自动重渲染
    await page.locator('button', { hasText: '侧面' }).click()
    await expect(page.locator('button', { hasText: '侧面' })).toHaveClass(/primary/)
    // 相机面板（收纳）：弹出细调滑块
    await page.locator('button', { hasText: '相机' }).click()
    await expect(page.locator('.cam-panel-title', { hasText: '相机设置' })).toBeVisible()
    await expect(page.locator('.cam-row', { hasText: '水平角' })).toBeVisible()
    // 重置按钮
    await page.locator('.cam-panel button', { hasText: '重置' }).click()
    await page.locator('button', { hasText: '正面' }).click()
    await expect(page.locator('button', { hasText: '正面' })).toHaveClass(/primary/)
  })

  test('动作管理：打开 walk3d 编辑器 → 动作预览渲染 → GIF 导出下载', async ({ page }) => {
    await page.locator('.list-item .item-main', { hasText: '人类骨骼拓扑' }).click()
    await page.locator('.el-tabs__item', { hasText: '动作管理' }).click()
    await expect(page.locator('.cell-title', { hasText: 'Walk 3D' })).toBeVisible()
    // 动作表格内的「编辑」按钮（非 sidebar 的物种编辑）
    await page.locator('.el-table button', { hasText: '编辑' }).first().click()
    // 动作编辑器（面包屑 walk3d）
    await expect(page.locator('.crumb-now', { hasText: 'walk3d' })).toBeVisible({ timeout: 20_000 })
    // 动作 JSON 定义区（el-input textarea，class 在 wrapper）
    await expect(page.locator('.json-editor')).toBeVisible()
    // 动作预览自动渲染（帧播放，播放按钮启用）
    await expect(page.locator('.mp-img')).toBeVisible({ timeout: 40_000 })
    await expect(page.locator('button', { hasText: '播放' })).toBeEnabled()
    // 帧计数徽章 1/16
    await expect(page.locator('.mp-badge', { hasText: '16' })).toBeVisible()
    // GIF 导出（触发浏览器下载）
    const dl = page.waitForEvent('download', { timeout: 60_000 })
    await page.locator('button', { hasText: '导出 GIF' }).click()
    const download = await dl
    expect(download.suggestedFilename()).toMatch(/\.gif$/)
  })

  test('动作预览：拖拽旋转视角（轨道相机）', async ({ page }) => {
    await page.locator('.list-item .item-main', { hasText: '人类骨骼拓扑' }).click()
    await page.locator('.el-tabs__item', { hasText: '动作管理' }).click()
    await expect(page.locator('.cell-title', { hasText: 'Walk 3D' })).toBeVisible()
    await page.locator('.el-table button', { hasText: '编辑' }).first().click()
    await expect(page.locator('.mp-img')).toBeVisible({ timeout: 40_000 })
    // 初始：正面应高亮（openAction 默认 yaw=0）
    await expect(page.locator('button', { hasText: '正面' })).toHaveClass(/primary/)
    // 在预览图上拖拽（水平 +70px → yaw 增加，离开快捷预设角度）
    const stage = page.locator('.mp-stage')
    await stage.scrollIntoViewIfNeeded()
    const box = await stage.boundingBox()
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width / 2 + 70, box.y + box.height / 2 + 20, { steps: 8 })
    await page.mouse.up()
    // 拖拽后正面取消高亮（相机已旋转到自定义角度）
    await expect(page.locator('button', { hasText: '正面' })).not.toHaveClass(/primary/, { timeout: 5_000 })
  })
})
