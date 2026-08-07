<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>🎨 预设管理</h2>
        <p class="page-desc">预设 = 基于物种的具体实例：调整骨骼尺寸（体型参数）+ 各动作幅度（动作参数）。参数面板由物种派生 schema 自动渲染。</p>
      </div>
      <el-button type="primary" icon="Plus" @click="startCreate">新建预设</el-button>
    </div>

    <div class="layout">
      <!-- 左侧：预设列表（独立入口，预设角色专用） -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <span>预设列表</span>
          <el-tag size="small" type="info" effect="plain">{{ presetList.length }}</el-tag>
        </div>
        <div v-if="loading" class="panel-loading"><el-skeleton :rows="5" animated /></div>
        <div v-else class="sidebar-list">
          <div v-for="p in presetList" :key="p.preset_id" class="list-item"
               :class="{ active: current?.preset_id === p.preset_id }" @click="openPreset(p)">
            <div class="item-main">
              <span class="item-name">🎨 {{ p.title || p.preset_id }}</span>
              <span class="item-id">{{ p.preset_id }}</span>
            </div>
            <div class="item-meta">
              <span class="meta-chip">🦴 {{ p.species }}</span>
              <span class="meta-chip">{{ p.description }}</span>
            </div>
            <div class="item-actions">
              <el-button size="small" text type="danger" @click.stop="confirmDelete(p)">删除</el-button>
            </div>
          </div>
          <div v-if="!presetList.length" class="empty-list"><p>暂无预设，点击「新建预设」</p></div>
        </div>
      </aside>

      <!-- 右侧 -->
      <section class="content">
        <!-- 新建：先选物种（schema 来源） -->
        <div v-if="creating" class="panel">
          <h4 class="panel-title">新建预设 — 选择物种</h4>
          <p class="hint">物种提供体型参数 schema（骨骼尺寸）与各动作参数 schema（动作幅度）。</p>
          <div class="create-row">
            <el-select v-model="newSpeciesId" placeholder="选择物种" style="width: 300px" filterable>
              <el-option v-for="s in speciesList" :key="s.id"
                         :label="`${s.title} (${s.id}) · ${(s.actions||[]).length} 动作`" :value="s.id" />
            </el-select>
            <el-button type="primary" :disabled="!newSpeciesId" @click="initNew" icon="Right">初始化预设</el-button>
            <el-button @click="creating = false">取消</el-button>
          </div>
        </div>

        <!-- 编辑 -->
        <div v-else-if="current" class="panel">
          <div class="content-header">
            <div class="crumb"><span class="crumb-root">预设</span><span class="crumb-sep">/</span><span class="crumb-now">{{ current.title || current.preset_id }}</span></div>
            <div class="content-actions">
              <el-button @click="close">关闭</el-button>
              <el-button type="primary" @click="save" :loading="saving" icon="Check">保存预设</el-button>
            </div>
          </div>

          <el-form label-position="top" class="form-grid">
            <el-form-item label="预设 ID"><el-input v-model="current.preset_id" :disabled="!isNew" placeholder="如 model_male" /></el-form-item>
            <el-form-item label="名称"><el-input v-model="current.title" placeholder="如 模特男" /></el-form-item>
            <el-form-item label="描述"><el-input v-model="current.description" /></el-form-item>
            <el-form-item label="物种（schema 来源）"><el-tag effect="plain">🦴 {{ current.species }}</el-tag></el-form-item>
          </el-form>

          <el-tabs v-model="tab">
            <!-- 体型参数：调整骨骼尺寸 -->
            <el-tab-pane label="📐 体型参数" name="body">
              <p class="hint">调整骨骼尺寸（来自物种骨架 param_chains 派生 schema，default 为物种默认）。</p>
              <div v-if="bodyParamItems.length" class="param-grid">
                <div v-for="it in bodyParamItems" :key="it.key" class="param-item">
                  <div class="param-head">
                    <label :title="it.key">{{ it.label }}</label>
                    <span class="val">{{ round(current.body[it.key] ?? it.def) }}</span>
                  </div>
                  <el-slider :min="it.min" :max="it.max" :step="it.step" :show-tooltip="false"
                             :model-value="current.body[it.key] ?? it.def" @update:model-value="setBody(it.key, $event)" />
                </div>
              </div>
              <div v-else class="preview-empty"><p>该物种没有体型参数</p></div>
            </el-tab-pane>

            <!-- 动作参数：调整动作幅度 -->
            <el-tab-pane label="🏃 动作幅度" name="actions">
              <p class="hint">调整各动作幅度（来自动作 JSON params 派生，default 为真实数据值）。</p>
              <div v-for="(a, aid) in schema.actions" :key="aid" class="action-card">
                <div class="action-head"><span>{{ a.title || aid }}</span><span class="mono">{{ aid }}</span></div>
                <div v-if="Object.keys(a.params||{}).length" class="param-grid">
                  <div v-for="(spec, pkey) in a.params" :key="pkey" class="param-item">
                    <div class="param-head">
                      <label :title="pkey">{{ spec.label || pkey }}</label>
                      <span class="val">{{ round((current.actions[aid]||{})[pkey] ?? spec.default) }}</span>
                    </div>
                    <el-slider :min="spec.min" :max="spec.max" :step="spec.step||0.01" :show-tooltip="false"
                               :model-value="(current.actions[aid]||{})[pkey] ?? spec.default"
                               @update:model-value="setAction(aid, pkey, $event)" />
                  </div>
                </div>
                <span v-else class="no-params">该动作无可调参数（数据驱动，无预设可调项）</span>
              </div>
            </el-tab-pane>

            <!-- 预览 -->
            <el-tab-pane label="👁 预览" name="preview">
              <div class="preview-controls">
                <CameraControls v-model="cam" />
                <el-select v-model="previewAction" placeholder="骨架（应用体型）" clearable filterable style="width: 200px">
                  <el-option v-for="(a, aid) in schema.actions" :key="aid" :label="`动作：${a.title||aid}`" :value="aid" />
                </el-select>
              </div>
              <div class="preview-stage" :class="{ dragging }" @mousedown="onDragDown">
                <img v-if="previewSrc" :src="previewSrc" class="preview-img" />
                <div v-else class="preview-empty"><p>{{ rendering ? '渲染中…' : '调整参数自动渲染预览' }}</p></div>
                <span v-if="dragging" class="orbit-hint">拖动旋转视角…</span>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <div v-else class="panel empty-state">
          <div class="empty-icon">🎨</div>
          <h3>选择或创建预设</h3>
          <p>预设是基于物种的具体实例：调体型（骨骼尺寸）+ 调动作（幅度）。</p>
          <el-button type="primary" @click="startCreate">新建预设</el-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import CameraControls from '../components/CameraControls.vue'
import { useOrbitDrag } from '../composables/useOrbitDrag.js'

const loading = ref(true)
const saving = ref(false)
const presetList = ref([])
const speciesList = ref([])
const current = ref(null)
const isNew = ref(false)
const creating = ref(false)
const newSpeciesId = ref('')
const tab = ref('body')

// 预览
const cam = ref({ yaw: 30, pitch: 12, dist: 600, zoom: 1, panX: 0, panY: 0 })
const previewAction = ref('')
const previewUrl = ref(null)
const previewFrames = ref([])
const previewFrameIndex = ref(0)
const rendering = ref(false)
let renderTimer = null
let playTimer = null

const camQS = () => `yaw=${cam.value.yaw}&pitch=${cam.value.pitch}&dist=${cam.value.dist}&zoom=${cam.value.zoom}&pan_x=${cam.value.panX}&pan_y=${cam.value.panY}`

const schema = computed(() => current.value?.schema_info || { body_params: {}, actions: {} })
const bodyParamItems = computed(() => {
  const bp = schema.value.body_params || {}
  return Object.entries(bp).map(([key, spec]) => ({
    key, label: spec.label || key, min: spec.min, max: spec.max,
    step: spec.step || 0.01, def: spec.default ?? 1.0,
  }))
})
const previewSrc = computed(() => previewFrames.value?.[previewFrameIndex.value] ?? previewUrl.value)

const round = (v) => (typeof v === 'number' ? Math.round(v * 100) / 100 : v)

onMounted(async () => {
  await Promise.all([loadPresets(), loadSpecies()])
  loading.value = false
})

async function loadPresets() {
  try { const r = await api.presets(); presetList.value = r.presets || [] }
  catch (e) { ElMessage.error('加载预设失败: ' + e.message) }
}
async function loadSpecies() {
  try { const r = await api.species(); speciesList.value = r.species || [] }
  catch (e) { ElMessage.error('加载物种失败: ' + e.message) }
}

// -- CRUD --

async function openPreset(p) {
  creating.value = false
  isNew.value = false
  try {
    current.value = await api.presetDetail(p.preset_id)
    tab.value = 'body'
    previewAction.value = ''
    previewFrames.value = []
    previewUrl.value = null
  } catch (e) { ElMessage.error(e.message) }
}

function startCreate() { creating.value = true; newSpeciesId.value = '' }

async function initNew() {
  if (!newSpeciesId.value) return
  try {
    current.value = await api.presetNew(newSpeciesId.value)
    isNew.value = true
    creating.value = false
    tab.value = 'body'
    previewAction.value = ''
  } catch (e) { ElMessage.error(e.message) }
}

function close() { current.value = null; isNew.value = false; previewFrames.value = []; previewUrl.value = null }

async function save() {
  if (!current.value?.preset_id) { ElMessage.warning('预设 ID 不能为空'); return }
  saving.value = true
  try {
    const data = JSON.parse(JSON.stringify(current.value))
    if (isNew.value) await api.createPreset(data)
    else await api.updatePreset(current.value.preset_id, data)
    ElMessage.success('预设已保存')
    await loadPresets()
  } catch (e) { ElMessage.error('保存失败: ' + e.message) }
  saving.value = false
}

async function confirmDelete(p) {
  try {
    await ElMessageBox.confirm(`确定删除预设「${p.title || p.preset_id}」吗？`, '确认', { type: 'warning' })
    await api.deletePreset(p.preset_id)
    if (current.value?.preset_id === p.preset_id) current.value = null
    await loadPresets()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || e) }
}

// -- 参数更新 --

function setBody(key, val) {
  current.value.body = { ...(current.value.body || {}), [key]: val }
}
function setAction(aid, pkey, val) {
  current.value.actions = {
    ...(current.value.actions || {}),
    [aid]: { ...((current.value.actions || {})[aid] || {}), [pkey]: val },
  }
}

// -- 实时预览（body/actions/cam/action 变化 → live 渲染） --

watch([() => current.value?.body, () => current.value?.actions, cam, previewAction],
      () => { scheduleRender() }, { deep: true })

function scheduleRender() {
  if (!current.value) return
  if (renderTimer) clearTimeout(renderTimer)
  renderTimer = setTimeout(renderLive, 500)
}

async function renderLive() {
  const c = current.value
  if (!c || !c.species) return
  rendering.value = true
  try {
    const body = encodeURIComponent(JSON.stringify(c.body || {}))
    const actions = encodeURIComponent(JSON.stringify(c.actions || {}))
    let qs = `species=${encodeURIComponent(c.species)}&body=${body}&actions=${actions}&${camQS()}`
    if (previewAction.value) qs += `&action=${encodeURIComponent(previewAction.value)}&frames=1`
    const r = await api.preset3dLive(qs)
    if (previewAction.value) {
      previewFrames.value = r.frames || []
      previewUrl.value = null
    } else {
      previewUrl.value = r.data_url
      previewFrames.value = []
    }
  } catch (e) { ElMessage.error(e.message) }
  rendering.value = false
}

// 动作帧轮播
watch(previewFrames, (f) => {
  if (playTimer) { clearInterval(playTimer); playTimer = null }
  previewFrameIndex.value = 0
  if (f && f.length > 1) playTimer = setInterval(() => {
    previewFrameIndex.value = (previewFrameIndex.value + 1) % f.length
  }, 160)
})

// 轨道相机：预览图拖拽旋转
const { onMouseDown: onDragDown, isDragging } = useOrbitDrag({
  getCam: () => cam.value,
  setCam: (c) => { cam.value = c },
})
const dragging = isDragging

onBeforeUnmount(() => {
  if (renderTimer) clearTimeout(renderTimer)
  if (playTimer) clearInterval(playTimer)
})
</script>

<style scoped>
.page { max-width: 1280px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; }
.page-desc { color: #909399; font-size: .85rem; margin: 0; }
.layout { display: grid; grid-template-columns: 260px 1fr; gap: 16px; align-items: start; }

.sidebar { background: #fff; border-radius: 10px; border: 1px solid #e4e7ed; overflow: hidden; position: sticky; top: 76px; }
.sidebar-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-weight: 600; }
.panel-loading { padding: 14px; }
.sidebar-list { max-height: calc(100vh - 180px); overflow-y: auto; }
.list-item { padding: 10px 14px; border-bottom: 1px solid #f5f5f5; cursor: pointer; }
.list-item:hover { background: #f7f9fc; }
.list-item.active { background: #ecf5ff; }
.item-main { display: flex; align-items: center; gap: 6px; }
.item-name { font-weight: 600; font-size: .9rem; }
.item-id { font-size: .72rem; color: #909399; }
.item-meta { display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
.meta-chip { font-size: .7rem; color: #909399; background: #f5f7fa; padding: 1px 8px; border-radius: 999px; }
.item-actions { margin-top: 6px; }
.empty-list { padding: 30px; text-align: center; color: #c0c4cc; }

.content { background: #fff; border-radius: 10px; border: 1px solid #e4e7ed; padding: 16px 20px; min-height: 480px; }
.panel { }
.panel-title { margin: 0 0 8px; }
.content-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.crumb { color: #909399; font-size: .85rem; }
.crumb-root, .crumb-sep { color: #c0c4cc; }
.crumb-now { color: #303133; font-weight: 600; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 20px; }
.hint { color: #909399; font-size: .8rem; margin: 0 0 12px; }
.create-row { display: flex; gap: 8px; align-items: center; margin-top: 8px; }

.param-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px 24px; }
.param-item { padding: 8px 10px; border: 1px solid #f0f0f0; border-radius: 8px; }
.param-head { display: flex; justify-content: space-between; align-items: center; }
.param-head label { font-size: .85rem; color: #606266; }
.val { font-family: monospace; color: #909399; font-size: .75rem; }
.action-card { border: 1px solid #f0f0f0; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; }
.action-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: 8px; }
.mono { font-family: monospace; font-size: .72rem; color: #909399; }
.no-params { color: #c0c4cc; font-size: .8rem; }

.preview-controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.preview-stage { position: relative; display: flex; justify-content: center; min-height: 320px; cursor: grab; user-select: none; border: 1px solid #111827; border-radius: 8px; background: #111827; overflow: hidden; }
.preview-stage.dragging { cursor: grabbing; }
.preview-img { max-width: 100%; max-height: 560px; pointer-events: none; }
.orbit-hint { position: absolute; left: 50%; top: 12px; transform: translateX(-50%); background: rgba(0,0,0,.65); color: #fff; font-size: .75rem; padding: 3px 10px; border-radius: 999px; }
.preview-empty { text-align: center; color: #c0c4cc; padding: 40px; }

.empty-state { text-align: center; padding: 60px 20px; }
.empty-state .empty-icon { font-size: 3rem; }
.empty-state h3 { margin: 8px 0 6px; }
.empty-state p { color: #909399; margin-bottom: 14px; }
</style>
