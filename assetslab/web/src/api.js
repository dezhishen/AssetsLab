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

  // -- 预设 Preset --

  /** 预设列表 @returns {Promise<{skeletons: import('../../models').PresetListItem[]}>} */
  presets: () => raw('/api/skeletons'),

  /** 预设详情（合并物种数据） @returns {Promise<import('../../models').PresetDetail>} */
  presetDetail: (id) => raw(`/api/skeletons/${encodeURIComponent(id)}`),

  /** 创建预设 */
  createPreset: (data) => raw('/api/skeletons', json(data)),

  /** 保存预设 */
  savePreset: (id, data) => raw(`/api/skeletons/${encodeURIComponent(id)}/save`, json(data)),

  /** 删除预设 */
  deletePreset: (id) => raw(`/api/skeletons/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  /** 骨架预览渲染 */
  renderSkeleton: (id, body) => raw(`/api/skeletons/${encodeURIComponent(id)}/render`, json(body)),

  // -- 3D 预览（阶段 1/2：3D 坐标 + 投影） --

  /** 3D 骨架：任意角度(yaw/pitch) + 距离(透视) 渲染 PNG */
  renderSkeleton3d: (id, qs) => raw(`/api/skeleton3d/${encodeURIComponent(id)}?${qs}`),

  /** 3D 动作列表（从 species actions3d 扫描） */
  motions3d: () => raw('/api/motions3d'),

  /** 3D 动作：任意角度 + 距离 单帧渲染 PNG */
  renderMotion3d: (id, qs) => raw(`/api/motion3d/${encodeURIComponent(id)}?${qs}`),

  // -- 动作 Motion --

  /** 动作列表 @returns {Promise<{motions: import('../../models').MotionListItem[]}>} */
  motions: () => raw('/api/motions'),

  /** 动作帧渲染 */
  renderMotion: (id, body) => raw(`/api/motions/${encodeURIComponent(id)}/render`, json(body)),
}
