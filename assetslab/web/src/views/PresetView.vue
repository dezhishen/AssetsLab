<template>
  <div class="page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2>🏷 预设管理</h2>
        <p class="page-desc">预设 = 基于物种的具体体型（关节坐标 + 体型参数值）。一个物种可有多个预设。</p>
      </div>
      <el-button type="primary" @click="openCreate" icon="Plus">新建预设</el-button>
    </div>

    <div class="layout">
      <!-- 左侧：预设列表 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <span>预设列表</span>
          <el-tag size="small" type="info" effect="plain">{{ presets.length }}</el-tag>
        </div>
        <div v-if="loading" class="panel-loading"><el-skeleton :rows="5" animated /></div>
        <div v-else class="sidebar-list">
          <div v-for="p in presets" :key="p.id" class="list-item"
               :class="{ active: selectedPreset?.id===p.id }" @click="selectPreset(p)">
            <div class="item-main">
              <span class="item-name">🏷 {{ p.title || p.id }}</span>
              <span class="item-id">{{ p.id }}</span>
            </div>
            <div class="item-meta">
              <el-tag size="small" type="info" effect="plain">{{ p.species }}</el-tag>
              <span class="item-views">{{ (p.views||[]).join(' / ') }}</span>
            </div>
          </div>
          <div v-if="presets.length===0" class="empty-list">
            <div class="empty-icon">🏷</div>
            <p>暂无预设</p>
            <el-button size="small" type="primary" @click="openCreate">创建第一个预设</el-button>
          </div>
        </div>
      </aside>

      <!-- 右侧：详情 -->
      <section class="content" v-if="selectedPreset">
        <div class="content-header">
          <div class="crumb">
            <span class="crumb-root">预设</span>
            <span class="crumb-sep">/</span>
            <span class="crumb-now">{{ presetDetail?.title || selectedPreset.title }}</span>
          </div>
          <div class="content-actions">
            <el-button @click="savePreset" :loading="saving" type="primary" plain icon="Check">保存</el-button>
            <el-button @click="confirmDelete" type="danger" plain icon="Delete">删除</el-button>
          </div>
        </div>

        <!-- 工作区：左侧控制面板 + 右侧大预览画布 -->
        <div class="workspace">
          <!-- 左侧控制面板（参数调节） -->
          <div class="control-panel">
            <el-tabs v-model="activeTab" class="control-tabs">
              <!-- 体型参数 -->
              <el-tab-pane label="🎛 体型" name="params">
            <div class="section" v-if="presetDetail?.params">
              <div class="section-head">
                <h4>体型参数</h4>
                <el-button size="small" text @click="resetAllParams">重置全部</el-button>
              </div>
              <div class="param-grid">
                <div v-for="(spec, name) in presetDetail.params" :key="name" class="param-card">
                  <div class="param-head">
                    <span class="param-label">{{ spec.label || name }}</span>
                    <span class="param-key">{{ name }}</span>
                    <el-button size="small" text circle @click="body[name]=spec.default" title="重置">
                      <span class="reset-icon">↺</span>
                    </el-button>
                  </div>
                  <div class="param-val">{{ (body[name] ?? spec.default).toFixed(2) }}</div>
                  <el-slider :min="spec.min" :max="spec.max" :step="spec.step" v-model="body[name]" :format-tooltip="v=>v.toFixed(2)" size="small" />
                  <div class="param-range"><span>{{ spec.min }}</span><span>{{ spec.max }}</span></div>
                </div>
              </div>
            </div>

            <div class="section" v-if="presetDetail?.canvas">
              <div class="section-head"><h4>画布设置</h4></div>
              <div class="canvas-grid">
                <div class="canvas-item"><span>宽度</span><el-input-number v-model="presetDetail.canvas.width" size="small" :min="100" :max="2000" controls-position="right"/></div>
                <div class="canvas-item"><span>高度</span><el-input-number v-model="presetDetail.canvas.height" size="small" :min="100" :max="2000" controls-position="right"/></div>
                <div class="canvas-item"><span>地面 Y</span><el-input-number v-model="presetDetail.canvas.floor_y" size="small" :min="100" :max="2000" controls-position="right"/></div>
                <div class="canvas-item"><span>头半径</span><el-input-number v-model="presetDetail.head_radius" size="small" :min="5" :max="100" controls-position="right"/></div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 动作 -->
          <el-tab-pane label="🎬 动作" name="motions">
            <div class="section">
              <div class="section-head"><h4>选择动作（{{ motions3d.length }}）</h4></div>
              <div class="motion-grid">
                <div v-for="m in motions3d" :key="m.motion_id" class="motion-card"
                     :class="{ active: selectedMotion===m.motion_id }" @click="selectAndRenderMotion(m.motion_id)">
                  <div class="motion-name">🎬 {{ m.title || m.motion_id }}
                    <el-tag size="small" type="success" effect="plain" style="margin-left:4px">3D</el-tag>
                  </div>
                  <div class="motion-meta">
                    <span class="motion-id">{{ m.motion_id }}</span>
                    <span v-if="m.params && Object.keys(m.params).length" class="motion-params">{{ Object.keys(m.params).length }} 参数</span>
                  </div>
                </div>
                <div v-if="motions3d.length===0" class="empty-inline">该物种暂无 3D 动作定义</div>
              </div>

              <!-- 动作参数调节 -->
              <div class="section" v-if="selectedMotion && motionParams && Object.keys(motionParams).length">
                <div class="section-head">
                  <h4>🎛 动作参数</h4>
                  <div class="preview-controls">
                    <el-button size="small" text @click="resetMotionParams">重置</el-button>
                    <el-button size="small" type="primary" @click="renderMotion" :loading="motionLoading" icon="Refresh">应用并渲染</el-button>
                  </div>
                </div>
                <div class="param-grid">
                  <div v-for="(val, name) in motionParams" :key="name" class="param-card">
                    <div class="param-head">
                      <span class="param-label" :class="{ 'master': name==='intensity' }">{{ (selectedMotionParams[name]?.label) || name }}</span>
                      <span class="param-key">{{ name }}</span>
                    </div>
                    <div class="param-val">{{ val.toFixed(2) }}</div>
                    <el-slider :min="selectedMotionParams[name]?.min ?? 0" :max="selectedMotionParams[name]?.max ?? 2"
                               :step="selectedMotionParams[name]?.step ?? 0.05" v-model="motionParams[name]"
                               :format-tooltip="v=>v.toFixed(2)" size="small" />
                  </div>
                </div>
                <div class="coord-hint" v-if="selectedMotionParams?.intensity">💡 「力度协调」为主参数：调节它会同步改变步幅 / 起伏 / 摆臂的整体强度。</div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 3D -->
          <el-tab-pane label="🧊 3D" name="preview3d">
            <div class="section">
              <div class="section-head"><h4>视角与相机</h4></div>
              <CameraControls v-model="cam" />
              <div class="section-head" style="margin-top:14px"><h4>3D 动作</h4></div>
              <el-select v-model="selectedMotion" size="small" style="width:100%">
                <el-option v-for="m in motions3d" :key="m.motion_id" :label="m.title" :value="m.motion_id" />
              </el-select>
              <div class="coord-hint" style="margin-top:8px">💡 预设视角一键切换；yaw 绕 Y 旋转、pitch 俯仰、distance 透视近大远小、pan 移动相机位置。</div>
            </div>
          </el-tab-pane>
            </el-tabs>
          </div>

          <!-- 右侧：大预览画布 -->
          <div class="canvas">
            <div class="canvas-head">
              <h4>{{ canvasTitle }}</h4>
              <div class="preview-controls" v-if="activeTab==='motions'">
                <CameraControls v-model="cam" compact />
                <el-button size="small" @click="renderMotion" :loading="motionLoading" icon="Refresh">重新渲染</el-button>
              </div>
              <div class="preview-controls" v-if="activeTab==='params'">
                <el-button size="small" @click="renderAllViews" :loading="previewLoading" icon="Refresh">渲染三视图</el-button>
              </div>
            </div>

            <div class="canvas-body" :class="canvasBodyClass">
              <!-- 体型 → 三视图骨架 -->
              <template v-if="activeTab==='params'">
                <template v-if="hasAnyPreview">
                  <div class="preview-cell" v-for="v in ['front','side','back']" :key="v">
                    <template v-if="previews[v]">
                      <div class="preview-title">{{ {front:'正面',side:'侧面',back:'背面'}[v] }}</div>
                      <img :src="previews[v]" />
                    </template>
                  </div>
                </template>
                <div v-else class="canvas-empty"><p>在左侧调节体型参数，右侧实时查看体形三视图</p></div>
              </template>

              <!-- 动作 → 动作帧大图 -->
              <template v-else-if="activeTab==='motions'">
                <img v-if="motionPreview" :src="motionPreview" class="fit-img" />
                <div v-else class="canvas-empty"><p>在左侧选择一个动作开始预览</p></div>
              </template>

              <!-- 3D → 3D 骨架 + 动作 -->
              <template v-else>
                <template v-if="preview3d.skeleton || preview3d.motion">
                  <div class="preview-cell">
                    <div class="preview-title">3D 骨架</div>
                    <img v-if="preview3d.skeleton" :src="preview3d.skeleton" class="fit-img" />
                  </div>
                  <div class="preview-cell">
                    <div class="preview-title">3D 动作</div>
                    <img v-if="preview3d.motion" :src="preview3d.motion" class="fit-img" />
                  </div>
                </template>
                <div v-else class="canvas-empty"><p>调节左侧相机参数，右侧实时预览 3D 骨架与动作</p></div>
              </template>
            </div>
          </div>
        </div>
      </section>

      <section class="content empty" v-else>
        <div class="empty-state">
          <div class="empty-icon">🏷</div>
          <h3>选择或创建预设</h3>
          <p>从左侧列表选择一个预设，或新建一个预设开始调整体型。</p>
          <el-button type="primary" @click="openCreate">新建预设</el-button>
        </div>
      </section>
    </div>

    <!-- 创建对话框 -->
    <el-dialog v-model="createDialog" title="新建预设" width="460px" :close-on-click-modal="false">
      <el-form label-position="top" size="default">
        <el-form-item label="基于物种" required>
          <el-select v-model="createForm.species" style="width:100%">
            <el-option v-for="s in speciesList" :key="s.id" :label="`${s.title} (${s.id}) · ${s.joint_count}关节`" :value="s.id" />
          </el-select>
          <div class="form-hint">选择物种后，将自动生成该物种的骨骼参数和关节骨架</div>
        </el-form-item>
        <el-form-item label="预设 ID（英文标识）" required>
          <el-input v-model="createForm.preset_id" placeholder="如 dwarf, child, elf" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="createForm.title" placeholder="如 矮人 / 儿童 / 精灵" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog=false">取消</el-button>
        <el-button type="primary" @click="createPreset" :loading="saving" :disabled="!createForm.preset_id.trim()">创建预设</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import CameraControls from '../components/CameraControls.vue'

const loading = ref(true)
const presets = ref([])
const speciesList = ref([])
const selectedPreset = ref(null)
const presetDetail = ref(null)
const activeTab = ref('params')
const createDialog = ref(false)
const createForm = ref({ preset_id:'', title:'', species:'', description:'' })
const saving = ref(false)
const previews = ref({})
const previewLoading = ref(false)
const body = ref({})
// 动作预览：统一使用 3D 动作（actions3d/）+ 3D 相机渲染
const selectedMotion = ref('walk3d')
const selectedMotionParams = ref({})
const motionParams = ref({})
const motionPreview = ref(null)
const motionLoading = ref(false)

const hasAnyPreview = () => Object.values(previews.value).some(Boolean)

// 右侧画布标题 / 布局（跟随当前 tab）
const canvasTitle = computed(() => ({
  params: '👁 体形三视图', motions: '🎬 动作帧预览', preview3d: '🧊 3D 预览',
}[activeTab.value] || ''))
const canvasBodyClass = computed(() => ({
  params: 'grid-3', motions: 'single', preview3d: 'grid-2',
}[activeTab.value] || 'single'))

// 当前体型参数覆盖（供骨架/2D 动作渲染实时使用，无需先保存）
const bodyOverrides = () => {
  const ov = {}
  for (const [name, spec] of Object.entries(presetDetail.value?.params || {})) {
    ov[name] = body.value[name] ?? spec.default
  }
  return ov
}

const PARAM_LABELS = {
  head_scale:'头大小', neck_length:'脖子长度', upper_torso_length:'上躯干长',
  lower_torso_length:'下躯干长', shoulder_width:'肩宽', hip_width:'髋宽',
  upper_arm_length:'上臂长', forearm_length:'前臂长', thigh_length:'大腿长',
  shin_length:'小腿长', overall_height:'整体身高',
}

onMounted(async () => {
  await Promise.all([loadPresets(), loadSpecies()])
  loading.value = false
  await loadMotions3d()
})

async function loadPresets() {
  try { presets.value = (await api.presets()).skeletons || [] } catch(e) { ElMessage.error(e.message) }
}

async function loadSpecies() {
  try { speciesList.value = (await api.species()).species || [] } catch(e) { ElMessage.error(e.message) }
}

function openCreate() {
  createForm.value = { preset_id:'', title:'', species: speciesList.value[0]?.id || '', description:'' }
  createDialog.value = true
}

async function createPreset() {
  if (!createForm.value.preset_id.trim()) { ElMessage.warning('请输入预设 ID'); return }
  saving.value = true
  try {
    const sp = await api.speciesDetail(createForm.value.species)
    const positions = {}
    const params = {}
    const bodyVals = {}
    for (const [key, chain] of Object.entries(sp.param_chains || {})) {
      if (!params[chain.param]) {
        params[chain.param] = { default: 1.0, min: 0.5, max: 1.6, step: 0.05, label: PARAM_LABELS[chain.param] || chain.param, desc: '' }
        bodyVals[chain.param] = 1.0
      }
    }
    const allJoints = new Set()
    for (const grp of Object.values(sp.joints || {})) {
      if (Array.isArray(grp)) grp.forEach(j => allJoints.add(j))
    }
    for (const view of ['front','side','back']) {
      positions[view] = {}
      for (const j of allJoints) positions[view][j] = [480, 300]
    }
    const data = {
      preset_id: createForm.value.preset_id.trim(),
      schema: 'assetslab_preset_v3',
      title: createForm.value.title.trim() || createForm.value.preset_id.trim(),
      description: createForm.value.description.trim(),
      species: createForm.value.species,
      head_radius: 24,
      canvas: { width: 960, height: 600, floor_y: 470 },
      params, body: bodyVals, positions,
    }
    await api.createPreset(data)
    ElMessage.success('预设创建成功')
    createDialog.value = false
    await loadPresets()
    const created = presets.value.find(p => p.id === data.preset_id)
    if (created) await selectPreset(created)
  } catch(e) { ElMessage.error('创建失败: ' + e.message) }
  saving.value = false
}

async function selectPreset(p) {
  selectedPreset.value = p
  previews.value = {}
  motionPreview.value = null
  selectedMotion.value = null
  preview3d.value = { skeleton: null, motion: null }
  activeTab.value = 'params'
  try {
    presetDetail.value = await api.presetDetail(p.id)
    body.value = {}
    for (const [name, spec] of Object.entries(presetDetail.value.params || {})) {
      body.value[name] = presetDetail.value.body?.[name] ?? spec.default
    }
    selectedMotion.value = 'walk3d'
    motionParams.value = {}
    selectedMotionParams.value = {}
  } catch(e) { ElMessage.error(e.message) }
}

async function savePreset() {
  saving.value = true
  try {
    const data = { ...presetDetail.value, body: { ...(presetDetail.value.body||{}), ...body.value } }
    await api.savePreset(selectedPreset.value.id, data)
    ElMessage.success('预设已保存')
  } catch(e) { ElMessage.error(e.message) }
  saving.value = false
}

async function confirmDelete() {
  try {
    await ElMessageBox.confirm(`确定删除预设「${selectedPreset.value.id}」吗？`, '确认删除', { type:'warning', confirmButtonText:'删除', cancelButtonText:'取消' })
    await api.deletePreset(selectedPreset.value.id)
    ElMessage.success('已删除')
    selectedPreset.value = null
    presetDetail.value = null
    await loadPresets()
  } catch(e) { if (e !== 'cancel') ElMessage.error(e.message || e) }
}

function resetAllParams() {
  for (const [name, spec] of Object.entries(presetDetail.value?.params||{})) {
    body.value[name] = spec.default
  }
  ElMessage.success('参数已重置')
}

function selectPreset3dInit() { resetPreview3d() }

async function renderAllViews() {
  if (!selectedPreset.value) return
  previewLoading.value = true
  try {
    // 体型参数实时覆盖渲染，无需先保存预设
    const bodyOv = bodyOverrides()
    for (const view of ['front','side','back']) {
      const r = await api.renderSkeleton(selectedPreset.value.id, { view, body: bodyOv })
      previews.value[view] = r.data_url
    }
  } catch(e) { ElMessage.error(e.message) }
  previewLoading.value = false
}

function initMotionParams(mid) {
  const m = motions3d.value.find(x => x.motion_id === mid)
  selectedMotionParams.value = m?.params || {}
  motionParams.value = {}
  for (const [name, spec] of Object.entries(selectedMotionParams.value)) {
    motionParams.value[name] = spec.default ?? 1.0
  }
}

async function selectAndRenderMotion(mid) {
  selectedMotion.value = mid
  initMotionParams(mid)
  await renderMotion()
}

function resetMotionParams() {
  for (const [name, spec] of Object.entries(selectedMotionParams.value)) {
    motionParams.value[name] = spec.default ?? 1.0
  }
  ElMessage.success('动作参数已重置')
  renderMotion()
}

async function renderMotion() {
  if (!selectedMotion.value) return
  motionLoading.value = true
  try {
    // 动作统一用 3D 相机渲染（任意角度 + 参数）
    const r = await api.renderMotion3d(selectedMotion.value, camQS() + '&gif=1' + paramQS())
    motionPreview.value = r.gif || r.data_url
  } catch(e) { ElMessage.error(e.message) }
  motionLoading.value = false
}

// 滑块调节 → 防抖自动重新渲染动画（实时预览生效）
let motionParamTimer = null
watch(motionParams, () => {
  if (!selectedMotion.value) return
  clearTimeout(motionParamTimer)
  motionParamTimer = setTimeout(() => renderMotion(), 400)
}, { deep: true })

// 体型参数 → 防抖自动重新渲染三视图（实时预览体形）
let bodyTimer = null
watch(body, () => {
  if (!selectedPreset.value || activeTab.value !== 'params') return
  clearTimeout(bodyTimer)
  bodyTimer = setTimeout(renderAllViews, 300)
}, { deep: true })

// ---- 3D 预览（角度 + 距离 + 平移） ----
const cam = ref({ yaw: 30, pitch: 12, dist: 600, zoom: 1, panX: 0, panY: 0 })
const preview3d = ref({ skeleton: null, motion: null })
const motions3d = ref([])
const camQS = () => `yaw=${cam.value.yaw}&pitch=${cam.value.pitch}&dist=${cam.value.dist}&zoom=${cam.value.zoom}&pan_x=${cam.value.panX}&pan_y=${cam.value.panY}`
const paramQS = () => Object.entries(motionParams.value).map(([k, v]) => `${k}=${v}`).join('&')

async function loadMotions3d() {
  try { motions3d.value = (await api.motions3d()).motions3d || [] } catch (e) { /* 静默 */ }
}

async function render3d() {
  if (!selectedPreset.value) return
  try {
    const sk = await api.renderSkeleton3d(selectedPreset.value.id, camQS())
    preview3d.value.skeleton = sk.data_url
    const mo = await api.renderMotion3d(selectedMotion.value, camQS() + '&gif=1')
    preview3d.value.motion = mo.gif || mo.data_url
  } catch (e) { /* 3D 预览失败静默 */ }
}

watch(selectedMotion, () => {
  initMotionParams(selectedMotion.value)
  if (preview3d.value.motion) render3d()
  else if (motionPreview.value) renderMotion()
})

let camTimer = null
watch(cam, () => {
  clearTimeout(camTimer)
  camTimer = setTimeout(() => {
    // 动作预览 tab → 刷新动作帧；否则刷新 3D 骨架/动作
    if (activeTab.value === 'motions' && motionPreview.value) renderMotion()
    else if (selectedPreset.value) render3d()
  }, 300)
}, { deep: true })

// 进入各 tab 时自动渲染一次（无需先手动触发）
watch(activeTab, (t) => {
  if (t === 'preview3d' && selectedPreset.value && !preview3d.value.skeleton) render3d()
  if (t === 'params' && selectedPreset.value && !hasAnyPreview()) renderAllViews()
})

function resetPreview3d() {
  preview3d.value = { skeleton: null, motion: null }
}
</script>

<style scoped>
.page { max-width: 1680px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 1.4rem; }
.page-desc { color: #909399; font-size: .85rem; margin: 0; }
.layout { display: flex; gap: 20px; min-height: 70vh; }

/* 侧边栏 */
.sidebar { width: 240px; flex-shrink: 0; background: #fff; border: 1px solid #e4e7ed; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.sidebar-header { padding: 12px 16px; font-weight: 600; font-size: .9rem; border-bottom: 1px solid #ebeef5; display: flex; justify-content: space-between; align-items: center; }
.panel-loading { padding: 20px; }
.sidebar-list { flex: 1; overflow-y: auto; max-height: calc(100vh - 220px); }
.list-item { padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f0f2f5; transition: background .15s; }
.list-item:hover { background: #f5f7fa; }
.list-item.active { background: #ecf5ff; border-left: 3px solid #409eff; }
.item-main { display: flex; align-items: center; gap: 8px; }
.item-name { font-weight: 600; font-size: .9rem; }
.item-id { color: #909399; font-size: .72rem; font-family: monospace; }
.item-meta { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.item-views { font-size: .72rem; color: #c0c4cc; }
.empty-list { padding: 40px 20px; text-align: center; color: #c0c4cc; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.empty-icon { font-size: 2rem; }

/* 内容区 */
.content { flex: 1; background: #fff; border: 1px solid #e4e7ed; border-radius: 10px; padding: 20px 24px; display: flex; flex-direction: column; overflow-y: auto; max-height: calc(100vh - 160px); box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.content.empty { display: flex; align-items: center; justify-content: center; }
.content-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.crumb { display: flex; align-items: center; gap: 6px; font-size: .85rem; }
.crumb-root { color: #909399; } .crumb-sep { color: #c0c4cc; } .crumb-now { font-weight: 600; color: #303133; }
.content-actions { display: flex; gap: 8px; }

/* 工作区：左侧控制面板 + 右侧大画布 */
.workspace { display: flex; gap: 18px; flex: 1; min-height: 0; }
.control-panel { width: 380px; flex-shrink: 0; overflow-y: auto; padding-right: 12px; }
.canvas { flex: 1; min-width: 0; display: flex; flex-direction: column; background: #111827; border: 1px solid #111827; border-radius: 10px; padding: 14px 16px; min-height: calc(100vh - 320px); }
.canvas-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.canvas-head h4 { margin: 0; color: #e5e7eb; font-size: .95rem; }
.canvas .cam-mini { color: #d1d5db; }
.canvas-body { flex: 1; display: flex; gap: 12px; min-height: 0; }
.canvas-body.grid-3 .preview-cell,
.canvas-body.grid-2 .preview-cell { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.canvas-body.single { align-items: center; justify-content: center; }
.canvas-body .preview-title { color: #9ca3af; font-size: .78rem; margin-bottom: 6px; text-align: center; }
.canvas-body img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px; background: #1f2937; }
.canvas-body.grid-3 img, .canvas-body.grid-2 img { width: 100%; }
.canvas-empty { display: flex; align-items: center; justify-content: center; color: #6b7280; flex: 1; padding: 30px; text-align: center; }
.canvas-empty p { margin: 0; font-size: .85rem; }

/* 统计卡片 */
.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: #f8fafc; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 16px; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 700; color: #409eff; }
.stat-label { font-size: .75rem; color: #909399; margin-top: 2px; }

/* 区块 */
.section { margin-top: 4px; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 0 0 12px; }
.section-head h4 { margin: 0; font-size: .95rem; color: #606266; }

/* 参数卡片网格 */
.param-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.param-card { border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 14px 6px; background: #fafbfc; }
.param-head { display: flex; align-items: center; gap: 8px; }
.param-label { font-weight: 600; font-size: .85rem; }
.param-key { color: #909399; font-family: monospace; font-size: .72rem; flex: 1; }
.reset-icon { color: #c0c4cc; font-size: .9rem; }
.param-val { text-align: right; font-family: monospace; font-size: .85rem; color: #409eff; font-weight: 600; margin: 2px 0; }
.param-range { display: flex; justify-content: space-between; font-size: .68rem; color: #c0c4cc; padding: 0 2px; }

/* 画布 */
.canvas-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.canvas-item { display: flex; justify-content: space-between; align-items: center; border: 1px solid #ebeef5; border-radius: 8px; padding: 8px 12px; background: #fafbfc; font-size: .85rem; }

/* 预览 */
.preview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.preview-cell { text-align: center; }
.preview-title { font-size: .8rem; color: #909399; margin-bottom: 6px; font-weight: 600; }
.preview-cell img { width: 100%; border: 1px solid #111827; border-radius: 8px; background: #111827; }
.preview-empty { text-align: center; color: #c0c4cc; padding: 40px; border: 2px dashed #e4e7ed; border-radius: 8px; }

/* 3D 相机控制 */
.cam-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px 20px; margin-bottom: 14px; }
.cam-item { border: 1px solid #ebeef5; border-radius: 8px; padding: 8px 12px; background: #fafbfc; }
.cam-label { display: flex; justify-content: space-between; font-size: .8rem; color: #606266; margin-bottom: 4px; }
.cam-key { font-family: monospace; color: #409eff; font-weight: 600; }
.cam-mini { display: inline-flex; align-items: center; gap: 4px; font-size: .75rem; color: #909399; }

/* 动作 */
.motion-grid { display: flex; flex-wrap: wrap; gap: 10px; }.motion-card { padding: 12px 16px; border: 1px solid #e4e7ed; border-radius: 8px; cursor: pointer; min-width: 150px; transition: all .15s; }
.motion-card:hover { border-color: #409eff; box-shadow: 0 2px 6px rgba(64,158,255,.12); }
.motion-card.active { border-color: #409eff; background: #ecf5ff; }
.motion-name { font-weight: 600; font-size: .85rem; }
.motion-meta { display: flex; gap: 8px; margin-top: 4px; }
.motion-id { color: #909399; font-size: .72rem; font-family: monospace; }
.motion-params { color: #67c23a; font-size: .72rem; }
.empty-inline { color: #c0c4cc; padding: 20px; }
.preview-controls { display: flex; gap: 8px; align-items: center; }
.motion-preview { display: flex; justify-content: center; }
.motion-preview img { max-width: 100%; border: 1px solid #111827; border-radius: 8px; background: #111827; }

/* 空状态 */
.empty-state { text-align: center; color: #909399; }
.empty-state .empty-icon { font-size: 3rem; margin-bottom: 12px; }
.empty-state h3 { margin: 0 0 8px; color: #303133; }
.empty-state p { margin: 0 0 16px; font-size: .85rem; }

.form-hint { font-size: .72rem; color: #909399; margin-top: 4px; width: 100%; }
.coord-hint { margin-top: 8px; padding: 8px 12px; background: #f0f9eb; border: 1px solid #e1f3d8; border-radius: 6px; font-size: .75rem; color: #67c23a; }
.param-label.master { color: #67c23a; }
</style>
