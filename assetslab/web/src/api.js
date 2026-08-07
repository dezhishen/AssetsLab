/**
 * AssetsLab API 层
 *
 * 类型参考：assetslab/models.py / assetslab/interfaces.ts
 * @module api
 */

const BASE = ''  // 同源

/**
 * 底层请求
 * @template T
 * @param {string} path
 * @param {RequestInit} [opts]
 * @returns {Promise<T>}
 */
async function raw(path, opts = {}) {
  const res = await fetch(BASE + path, opts)
  const body = await res.json().catch(() => ({}))
  if (body.ok === false) throw new Error(body.error || JSON.stringify(body))
  return /** @type {T} */ (body)
}

/** JSON 请求辅助 */
const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})
const json_put = (body) => ({
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// =========================================================================
// API 方法
// =========================================================================

export const api = {
  // -- 物种 Species --

  /** 物种列表 @returns {Promise<{species: import('../../models').SpeciesListItem[]}>} */
  species: () => raw('/api/species'),

  /** 物种详情（含动作） @returns {Promise<import('../../models').SpeciesDetail>} */
  speciesDetail: (id) => raw(`/api/species/${encodeURIComponent(id)}`),

  /** 物种预设 schema（随物种自动派生，创建预设的清单） @returns {Promise<object>} */
  presetSchema: (id) => raw(`/api/species/${encodeURIComponent(id)}/preset_schema`),

  /** 创建物种 */
  createSpecies: (data) => raw('/api/species', json(data)),

  /** 更新物种 */
  updateSpecies: (id, data) => raw(`/api/species/${encodeURIComponent(id)}`, json_put(data)),

  /** 删除物种 */
  deleteSpecies: (id) => raw(`/api/species/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  // -- 物种动作 Action --

  /** 动作详情 @returns {Promise<import('../../models').Motion>} */
  actionDetail: (speciesId, actionId) => raw(`/api/species/${encodeURIComponent(speciesId)}/actions/${encodeURIComponent(actionId)}`),

  /** 创建动作 */
  createAction: (speciesId, data) => raw(`/api/species/${encodeURIComponent(speciesId)}/actions`, json(data)),

  /** 更新动作 */
  updateAction: (speciesId, actionId, data) => raw(`/api/species/${encodeURIComponent(speciesId)}/actions/${encodeURIComponent(actionId)}`, json_put(data)),

  /** 删除动作 */
  deleteAction: (speciesId, actionId) => raw(`/api/species/${encodeURIComponent(speciesId)}/actions/${encodeURIComponent(actionId)}`, { method: 'DELETE' }),

  // -- 物种默认参数（物种自带姿态/体型；动作与骨架预览的基础） --

  /** 读物种默认参数 @returns {Promise<object>} */
  speciesDefault: (id) => raw(`/api/species/${encodeURIComponent(id)}/default`),

  /** 保存物种默认参数 */
  saveSpeciesDefault: (id, data) => raw(`/api/species/${encodeURIComponent(id)}/default`, json(data)),

  // -- 3D 预览（3D 坐标 + 投影；基于物种默认参数） --

  /** 3D 骨架：任意角度(yaw/pitch) + 距离(透视) 渲染 PNG（species_id 路径） */
  renderSkeleton3d: (id, qs) => raw(`/api/skeleton3d/${encodeURIComponent(id)}?${qs}`),

  /** 3D 动作：任意角度 + 距离 单帧渲染 PNG（动作按 species 获取与渲染） */
  renderMotion3d: (id, qs) => raw(`/api/motion3d/${encodeURIComponent(id)}?${qs}`),

  // -- 预设 Preset（独立入口：预设 = 物种实例，调整体型 + 动作幅度） --

  /** 预设列表 @returns {Promise<{presets: import('../../models').PresetSummary[]}>} */
  presets: () => raw('/api/presets'),

  /** 预设详情（预设值 + schema_info） @returns {Promise<import('../../models').PresetDetail>} */
  presetDetail: (id) => raw(`/api/presets/${encodeURIComponent(id)}`),

  /** 新建预设空白表单（含 schema） */
  presetNew: (speciesId) => raw(`/api/presets/new?species=${encodeURIComponent(speciesId)}`),

  /** 创建预设 */
  createPreset: (data) => raw('/api/presets', json(data)),

  /** 更新预设 */
  updatePreset: (id, data) => raw(`/api/presets/${encodeURIComponent(id)}`, json_put(data)),

  /** 删除预设 */
  deletePreset: (id) => raw(`/api/presets/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  /** 预设渲染：骨架/动作（应用体型 + 动作参数） */
  preset3dRender: (id, qs) => raw(`/api/preset3d/${encodeURIComponent(id)}?${qs}`),

  /** 预设实时渲染（live：未保存的 body/actions 预览） */
  preset3dLive: (qs) => raw(`/api/preset3d/live?${qs}`),
}
