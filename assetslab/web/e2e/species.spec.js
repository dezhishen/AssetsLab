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

  test('物种 CRUD：新建 → 详情 → 编辑改名称 → 删除', async ({ page }) => {
    const sid = `e2e_sp_${Date.now()}`
    // 新建物种（最小合法骨架：joints + bones_3d + chains + 默认参数）
    // 注意：.page-header 与右侧空状态区都有「新建物种」按钮，用 .page-header 限定
    await page.locator('.page-header button', { hasText: '新建物种' }).click()
    await expect(page.locator('.crumb-now', { hasText: '新建' })).toBeVisible()
    await page.locator('.el-form-item', { hasText: '物种 ID' }).locator('input').fill(sid)
    await page.locator('.el-form-item', { hasText: '名称' }).locator('input').fill('E2E 测试物种')
    await page.locator('.el-form-item', { hasText: '关节组 (JSON)' }).locator('textarea')
      .fill('{"core":["root","mid"]}')
    await page.locator('.el-form-item', { hasText: '骨骼连接 3D' }).locator('textarea')
      .fill('[["root","mid"]]')
    await page.locator('.el-form-item', { hasText: '关节链 (JSON)' }).locator('textarea')
      .fill('{"main":["root","mid"]}')
    await page.locator('.el-form-item', { hasText: '默认参数' }).locator('textarea')
      .fill('{"positions_3d":{"root":[0,0,0],"mid":[0,10,0]},"head_radius":5}')
    await page.locator('button', { hasText: '创建' }).click()
    await expect(page.locator('.list-item .item-name', { hasText: 'E2E 测试物种' })).toBeVisible({ timeout: 10_000 })

    // 详情：统计卡（2 关节 / 1 骨 / 1 链）
    await page.locator('.list-item .item-main', { hasText: 'E2E 测试物种' }).click()
    await expect(page.locator('.crumb-now', { hasText: 'E2E 测试物种' })).toBeVisible()
    await expect(page.locator('.stat-card .stat-val', { hasText: '2' }).first()).toBeVisible()
    await expect(page.locator('.stat-card .stat-val', { hasText: '1' }).first()).toBeVisible()

    // 编辑：改名称
    await page.locator('button', { hasText: '编辑物种' }).click()
    await expect(page.locator('.crumb-now', { hasText: '编辑' })).toBeVisible()
    await page.locator('.el-form-item', { hasText: '名称' }).locator('input').fill('E2E 物种改名')
    await page.locator('button', { hasText: '保存' }).click()
    await expect(page.locator('.list-item .item-name', { hasText: 'E2E 物种改名' })).toBeVisible({ timeout: 10_000 })

    // 删除（hover 显示操作 → 删除 → 确认弹窗）
    const item = page.locator('.list-item', { hasText: 'E2E 物种改名' })
    await item.hover()
    await item.locator('button', { hasText: '删除' }).click()
    await page.locator('.el-message-box__btns button', { hasText: '删除' }).click()
    await expect(page.locator('.list-item .item-name', { hasText: 'E2E 物种改名' })).toHaveCount(0)
  })

  test('动作 CRUD：新建动作 → 保存 → 列表 → 删除', async ({ page }) => {
    const aid = `e2e_act_${Date.now()}`
    await page.locator('.list-item .item-main', { hasText: '人类骨骼拓扑' }).click()
    await page.locator('.el-tabs__item', { hasText: '动作管理' }).click()
    await expect(page.locator('.cell-title', { hasText: 'Walk 3D' })).toBeVisible()
    // 新建动作（startCreateAction 预填模板，改 motion_id）
    await page.locator('button', { hasText: '新建动作' }).click()
    await expect(page.locator('.crumb-now', { hasText: '新动作' })).toBeVisible()
    const motion = {
      schema: 'assetslab_motion3d_v1', motion_id: aid, title: 'E2E 动作', description: '',
      species: 'human', frame_count: 8, params: {}, root3d: { dy: { phase: true } }, offsets3d: {}, ik3d: {},
    }
    await page.locator('.json-editor textarea').fill(JSON.stringify(motion, null, 2))
    await page.locator('button', { hasText: '保存动作' }).click()
    // 列表出现新动作
    await expect(page.locator('.cell-title', { hasText: 'E2E 动作' })).toBeVisible({ timeout: 10_000 })
    // 删除
    const row = page.locator('.el-table__row', { hasText: 'E2E 动作' })
    await row.locator('button', { hasText: '删除' }).click()
    await page.locator('.el-message-box__btns button', { hasText: '确定' }).click()
    await expect(page.locator('.cell-title', { hasText: 'E2E 动作' })).toHaveCount(0)
  })
})
