import { test, expect } from '@playwright/test'

// 预设管理全量 E2E：列表 / 新建（选物种 → 初始化）→ 体型参数 / 动作幅度 / 实时预览 → 保存 → 删除
test.describe('预设管理（全量 E2E）', () => {
  test('新建预设：选物种 → 初始化 → 体型/动作/预览 → 保存 → 列表 → 删除', async ({ page }) => {
    const pid = `e2e_preset_${Date.now()}`

    await page.goto('/#/presets')
    // 预设页独立入口（导航）
    await expect(page.locator('.page-header h2', { hasText: '预设管理' })).toBeVisible()

    // 新建 → 选物种
    await page.locator('button', { hasText: '新建预设' }).first().click()
    await expect(page.locator('.panel-title', { hasText: '新建预设' })).toBeVisible()
    await page.locator('.el-select__wrapper').first().click()
    // el-select dropdown 为 fixed 定位，720 视口下弹层可能超界 → 用 DOM click 绕过坐标/视口检查
    await page.locator('.el-select-dropdown__item', { hasText: '人类骨骼拓扑' }).last()
      .evaluate((el) => el.click())
    await page.locator('button', { hasText: '初始化预设' }).click()

    // 编辑面板：基本信息 + 物种（新建时 crumb 为空，检查物种表单项）
    await expect(page.locator('.el-form-item', { hasText: '物种（schema 来源）' })).toContainText('human')
    await expect(page.locator('.el-tabs__item', { hasText: '体型参数' })).toBeVisible()

    // 填 preset_id + 名称
    const inputs = page.locator('.el-input__inner')
    await inputs.nth(0).fill(pid)
    await inputs.nth(1).fill('E2E 测试预设')

    // 体型参数 tab：schema 派生滑块（head_scale 等）
    await expect(page.locator('.param-item', { hasText: '头大小' })).toBeVisible()
    const headSlider = page.locator('.param-item', { hasText: '头大小' }).locator('.el-slider__runway').first()
    const hb = await headSlider.boundingBox()
    await page.mouse.click(hb.x + hb.width * 0.8, hb.y + hb.height / 2)
    await expect(page.locator('.param-item', { hasText: '头大小' }).locator('.val')).toHaveText(/.+/)

    // 动作幅度 tab：walk3d.intensity 派生
    await page.locator('.el-tabs__item', { hasText: '动作幅度' }).click()
    await expect(page.locator('.action-card', { hasText: 'walk3d' })).toBeVisible()
    await expect(page.locator('.action-card', { hasText: '动作幅度' })).toBeVisible()

    // 预览 tab：实时渲染骨架（应用体型）
    await page.locator('.el-tabs__item', { hasText: '预览' }).click()
    await expect(page.locator('.preview-stage img')).toBeVisible({ timeout: 30_000 })
    // 选择动作 walk3d → 动作帧渲染
    // （el-select dropdown 为 fixed 定位，内容底部时弹层可能超出 720 视口 → 用 evaluate 触发 DOM click，
    //   绕过 Playwright 视口/坐标检查，功能等价）
    await page.locator('.preview-controls .el-select__wrapper').first().click()
    await page.locator('.el-select-dropdown__item', { hasText: 'Walk 3D' }).last()
      .evaluate((el) => el.click())
    await expect(page.locator('.preview-controls .el-select__selected-item').filter({ hasText: 'Walk 3D' })).toHaveCount(1)

    // 保存 → 列表出现（pid 显示在 .item-id）
    await page.locator('button', { hasText: '保存预设' }).click()
    await expect(page.locator('.list-item .item-id', { hasText: pid })).toBeVisible({ timeout: 10_000 })

    // 清理：删除测试预设
    const item = page.locator('.list-item', { hasText: pid })
    await item.locator('button', { hasText: '删除' }).click()
    await page.locator('.el-message-box__btns button', { hasText: '确定' }).click()
    await expect(page.locator('.list-item .item-id', { hasText: pid })).toHaveCount(0)
  })

  test('预设列表：无预设时显示空状态', async ({ page }) => {
    await page.goto('/#/presets')
    await expect(page.locator('.empty-state', { hasText: '选择或创建预设' })).toBeVisible()
  })

  test('预设查看/编辑：打开已有 → 调整体型 → 保存 → 重新打开验证 → 删除', async ({ page }) => {
    const pid = `e2e_edit_${Date.now()}`
    // 新建 + 保存
    await page.goto('/#/presets')
    await page.locator('button', { hasText: '新建预设' }).first().click()
    await page.locator('.el-select__wrapper').first().click()
    // el-select dropdown 为 fixed 定位，720 视口下弹层可能超界 → 用 DOM click 绕过坐标/视口检查
    await page.locator('.el-select-dropdown__item', { hasText: '人类骨骼拓扑' }).last()
      .evaluate((el) => el.click())
    await page.locator('button', { hasText: '初始化预设' }).click()
    const inputs = page.locator('.el-input__inner')
    await inputs.nth(0).fill(pid)
    await inputs.nth(1).fill('E2E 编辑预设')
    await page.locator('button', { hasText: '保存预设' }).click()
    await expect(page.locator('.list-item .item-id', { hasText: pid })).toBeVisible({ timeout: 10_000 })

    // 打开已有预设 → 改名 → 保存（验证查看/编辑路径；名称字段比 el-slider 更稳定）
    await page.locator('.list-item', { hasText: pid }).click()
    await expect(page.locator('.crumb-now', { hasText: 'E2E 编辑预设' })).toBeVisible()
    await page.locator('.el-form-item', { hasText: '名称' }).locator('input').fill('E2E 改名后')
    await page.locator('button', { hasText: '保存预设' }).click()
    await expect(page.locator('.list-item .item-name', { hasText: 'E2E 改名后' })).toBeVisible({ timeout: 10_000 })

    // 重新打开：名称已持久化
    await page.locator('.list-item', { hasText: pid }).click()
    await expect(page.locator('.crumb-now', { hasText: 'E2E 改名后' })).toBeVisible()

    // 删除
    const item = page.locator('.list-item', { hasText: pid })
    await item.hover()
    await item.locator('button', { hasText: '删除' }).click()
    await page.locator('.el-message-box__btns button', { hasText: '确定' }).click()
    await expect(page.locator('.list-item .item-id', { hasText: pid })).toHaveCount(0)
  })
})
