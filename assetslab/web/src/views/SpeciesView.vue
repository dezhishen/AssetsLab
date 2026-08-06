<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>🦴 物种管理</h2>
        <p class="page-desc">物种 = 骨骼拓扑 + 动作。定义骨骼结构，预设基于物种生成体型。</p>
      </div>
      <el-button type="primary" @click="startCreate" icon="Plus">新建物种</el-button>
    </div>

    <div class="layout">
      <!-- 左侧：物种列表 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <span>物种列表</span>
          <el-tag size="small" type="info" effect="plain">{{ speciesList.length }}</el-tag>
        </div>
        <div v-if="loading" class="panel-loading"><el-skeleton :rows="5" animated /></div>
        <div v-else class="sidebar-list">
          <div v-for="sp in speciesList" :key="sp.id" class="list-item" :class="{ active: selectedSpecies?.id===sp.id }">
            <div class="item-main" @click="selectSpecies(sp)">
              <span class="item-name">🦴 {{ sp.title }}</span>
              <span class="item-id">{{ sp.id }}</span>
            </div>
            <div class="item-meta">
              <span class="meta-chip">{{ sp.joint_count }}关节</span>
              <span class="meta-chip">{{ sp.bone_count }}骨</span>
              <span class="meta-chip">{{ (sp.actions||[]).length }}动作</span>
            </div>
            <div class="item-actions">
              <el-button size="small" text type="primary" @click.stop="startEdit(sp)">编辑</el-button>
              <el-button size="small" text type="danger" @click.stop="confirmDelete(sp)">删除</el-button>
            </div>
          </div>
          <div v-if="speciesList.length===0" class="empty-list">
            <div class="empty-icon">🦴</div>
            <p>暂无物种</p>
            <el-button size="small" type="primary" @click="startCreate">创建第一个物种</el-button>
          </div>
        </div>
      </aside>

      <!-- 右侧内容 -->
      <section class="content" v-if="editMode">
        <!-- 编辑物种 -->
        <div class="content-header">
          <div class="crumb"><span class="crumb-root">物种</span><span class="crumb-sep">/</span><span class="crumb-now">{{ isCreating ? '新建' : '编辑' }}</span></div>
          <div class="content-actions">
            <el-button @click="editMode=null;selectedSpecies=null">取消</el-button>
            <el-button type="primary" @click="saveSpecies" :loading="saving">{{ isCreating ? '创建' : '保存' }}</el-button>
          </div>
        </div>
        <el-form label-position="top" size="default">
          <div class="form-grid">
            <el-form-item label="物种 ID（英文标识）">
              <el-input v-model="editForm.species_id" :disabled="!isCreating" placeholder="如 human, dog, bird" />
            </el-form-item>
            <el-form-item label="名称">
              <el-input v-model="editForm.title" placeholder="如 人类骨骼拓扑" />
            </el-form-item>
          </div>
          <el-form-item label="描述">
            <el-input v-model="editForm.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="关节组 (JSON)">
            <el-input v-model="editForm.jointsStr" type="textarea" :rows="5" class="mono" />
          </el-form-item>
          <el-form-item label="骨骼连接 (JSON)">
            <el-input v-model="editForm.bonesStr" type="textarea" :rows="5" class="mono" />
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="关节链 (JSON)">
              <el-input v-model="editForm.chainsStr" type="textarea" :rows="4" class="mono" />
            </el-form-item>
            <el-form-item label="参数链 (JSON)">
              <el-input v-model="editForm.paramChainsStr" type="textarea" :rows="4" class="mono" />
            </el-form-item>
          </div>
        </el-form>
      </section>

      <section class="content" v-else-if="actionEditor">
        <!-- 动作编辑器 -->
        <div class="content-header">
          <div class="crumb">
            <span class="crumb-root">物种</span><span class="crumb-sep">/</span>
            <span class="crumb-now">{{ selectedSpecies?.id }}</span><span class="crumb-sep">/</span>
            <span class="crumb-now">{{ actionEditor.motion_id || '新动作' }}</span>
          </div>
          <div class="content-actions">
            <el-button @click="actionEditor=null">关闭</el-button>
            <el-button type="primary" @click="saveAction" :loading="saving" icon="Check">保存动作</el-button>
          </div>
        </div>

        <div class="stat-cards">
          <div class="stat-card"><div class="stat-val">{{ actionEditor.motion_id || '-' }}</div><div class="stat-label">动作 ID</div></div>
          <div class="stat-card"><div class="stat-val">{{ actionEditor.frame_count || '-' }}</div><div class="stat-label">帧数</div></div>
          <div class="stat-card"><div class="stat-val">{{ Object.keys(actionEditor.params||{}).length }}</div><div class="stat-label">可调参数</div></div>
          <div class="stat-card"><div class="stat-val">{{ selectedSpecies?.id }}</div><div class="stat-label">所属物种</div></div>
        </div>

        <div class="section">
          <div class="section-head"><h4>动作 JSON 定义</h4></div>
          <el-input v-model="actionJson" type="textarea" :rows="18" class="mono json-editor" />
        </div>

        <div class="section">
          <div class="section-head">
            <h4>动作预览</h4>
            <div class="preview-controls">
              <CameraControls v-model="cam" compact />
              <el-button size="small" type="primary" @click="renderAction" :loading="motionRenderLoading" icon="Refresh">渲染</el-button>
            </div>
          </div>
          <div v-if="motionPreview" class="motion-preview"><img :src="motionPreview" /></div>
          <div v-else class="preview-empty"><p>保存动作后可预览</p></div>
        </div>
      </section>

      <section class="content" v-else-if="selectedSpecies">
        <!-- 物种详情 -->
        <div class="content-header">
          <div class="crumb">
            <span class="crumb-root">物种</span><span class="crumb-sep">/</span>
            <span class="crumb-now">{{ presetDetail?.title || selectedSpecies.title }}</span>
          </div>
          <div class="content-actions">
            <el-button type="primary" plain icon="Edit" @click="startEdit(selectedSpecies)">编辑物种</el-button>
          </div>
        </div>

        <div class="stat-cards">
          <div class="stat-card"><div class="stat-val">{{ selectedSpecies.joint_count }}</div><div class="stat-label">关节</div></div>
          <div class="stat-card"><div class="stat-val">{{ selectedSpecies.bone_count }}</div><div class="stat-label">骨骼</div></div>
          <div class="stat-card"><div class="stat-val">{{ selectedSpecies.chain_count }}</div><div class="stat-label">关节链</div></div>
          <div class="stat-card"><div class="stat-val">{{ (speciesDetail?.actions||[]).length }}</div><div class="stat-label">动作</div></div>
        </div>

        <el-tabs v-model="activeTab" class="content-tabs">
          <el-tab-pane label="🦴 骨骼拓扑" name="skeleton">
            <div class="section" v-if="speciesDetail?.joints">
              <div class="section-head"><h4>关节组</h4></div>
              <div class="tag-cloud">
                <el-tag v-for="(names, group) in speciesDetail.joints" :key="group" v-if="group!=='aliases' && Array.isArray(names)" size="small" effect="plain" class="joint-tag">
                  <span class="tag-group">{{ group }}</span>: {{ names.join(', ') }}
                </el-tag>
              </div>
            </div>
            <div class="section" v-if="speciesDetail?.chains">
              <div class="section-head"><h4>关节链</h4></div>
              <div class="chain-list">
                <div v-for="(chain, name) in speciesDetail.chains" :key="name" class="chain-row">
                  <el-tag size="small" type="primary" effect="plain">{{ name }}</el-tag>
                  <span class="chain-path">{{ chain.join(' → ') }}</span>
                </div>
              </div>
            </div>
            <div class="section" v-if="speciesDetail?.param_chains">
              <div class="section-head"><h4>参数链（体型参数分组）</h4></div>
              <el-table :data="paramChainRows" size="small" border>
                <el-table-column prop="name" label="链名" width="140"><template #default="{row}"><span class="mono">{{ row.name }}</span></template></el-table-column>
                <el-table-column prop="param" label="参数" width="160"><template #default="{row}"><span class="mono">{{ row.param }}</span></template></el-table-column>
                <el-table-column prop="anchor" label="锚点" width="100"/>
                <el-table-column prop="joints" label="影响关节"/>
              </el-table>
            </div>
          </el-tab-pane>

          <el-tab-pane :label="`🎬 动作管理 (${(speciesDetail?.actions||[]).length})`" name="actions">
            <div class="section">
              <div class="section-head">
                <h4>3D 动作（存放于 species/{{ selectedSpecies.id }}/actions3d/）</h4>
                <el-button size="small" type="primary" @click="startCreateAction" icon="Plus">新建动作</el-button>
              </div>
              <el-table :data="speciesDetail?.actions||[]" size="small" border>
                <el-table-column label="动作" min-width="180">
                  <template #default="{row}">
                    <div class="cell-main"><span class="cell-title">🎬 {{ row.title || row.motion_id }}</span><span class="cell-id mono">{{ row.motion_id }}</span></div>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip/>
                <el-table-column label="参数" width="180">
                  <template #default="{row}">
                    <el-tag v-for="p in Object.keys(row.params||{}).slice(0,3)" :key="p" size="small" effect="plain" class="param-tag">{{ p }}</el-tag>
                    <span v-if="Object.keys(row.params||{}).length>3" class="cell-id">+{{ Object.keys(row.params).length-3 }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="150" align="center">
                  <template #default="{row}">
                    <el-button size="small" text type="primary" @click="openAction(selectedSpecies, row.motion_id)">编辑</el-button>
                    <el-button size="small" text type="danger" @click="confirmDeleteAction(row.motion_id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <div v-if="!(speciesDetail?.actions||[]).length" class="empty-inline">该物种暂无动作，点击「新建动作」创建</div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="👁 骨架预览" name="preview">
            <div class="section">
              <div class="section-head">
                <h4>三视图预览（基于 standard 预设）</h4>
                <el-button size="small" type="primary" @click="renderAllViews" :loading="previewLoading" icon="Refresh">渲染三视图</el-button>
              </div>
              <div class="preview-grid" v-if="hasAnyPreview">
                <div class="preview-cell" v-for="v in ['front','side','back']" :key="v">
                  <template v-if="previews[v]">
                    <div class="preview-title">{{ {front:'正面',side:'侧面',back:'背面'}[v] }}</div>
                    <img :src="previews[v]" />
                  </template>
                </div>
              </div>
              <div class="preview-empty" v-else><p>点击「渲染三视图」生成骨架预览</p></div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </section>

      <section class="content empty" v-else>
        <div class="empty-state">
          <div class="empty-icon">🦴</div>
          <h3>选择或创建物种</h3>
          <p>物种定义骨骼拓扑和动作，是生成预设的基础。</p>
          <el-button type="primary" @click="startCreate">新建物种</el-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import CameraControls from '../components/CameraControls.vue'

const loading = ref(true)
const speciesList = ref([])
const selectedSpecies = ref(null)
const speciesDetail = ref(null)
const presetDetail = ref(null) // 兼容命名（详情数据）
const activeTab = ref('skeleton')
const editMode = ref(null)
const isCreating = ref(false)
const saving = ref(false)
const previews = ref({})
const previewLoading = ref(false)
const actionEditor = ref(null)
const actionJson = ref('')
const motionPreview = ref(null)
const motionRenderLoading = ref(false)
const cam = ref({ yaw: 30, pitch: 12, dist: 600, zoom: 1, panX: 0, panY: 0 })
const camQS = () => `yaw=${cam.value.yaw}&pitch=${cam.value.pitch}&dist=${cam.value.dist}&zoom=${cam.value.zoom}&pan_x=${cam.value.panX}&pan_y=${cam.value.panY}`

const editForm = ref({ species_id:'', title:'', description:'', jointsStr:'', bonesStr:'', chainsStr:'', paramChainsStr:'' })
const hasAnyPreview = () => Object.values(previews.value).some(Boolean)

const paramChainRows = computed(() => {
  const pc = speciesDetail.value?.param_chains || {}
  return Object.entries(pc).map(([name, spec]) => ({ name, param: spec.param||'-', anchor: spec.anchor||'-', joints: (spec.joints||[]).join(', ') }))
})

onMounted(async () => { await loadSpecies(); loading.value = false })

async function loadSpecies() {
  try {
    const res = await api.species()
    speciesList.value = res.species || []
  } catch(e) { ElMessage.error('加载物种失败: ' + e.message) }
}

async function selectSpecies(sp) {
  selectedSpecies.value = sp
  actionEditor.value = null
  previews.value = {}
  motionPreview.value = null
  editMode.value = null
  try {
    speciesDetail.value = await api.speciesDetail(sp.id)
    presetDetail.value = speciesDetail.value
  } catch(e) { ElMessage.error(e.message) }
}

// -- 动作管理 --

async function openAction(sp, actionId) {
  selectedSpecies.value = sp
  actionEditor.value = null
  try {
    speciesDetail.value = await api.speciesDetail(sp.id)
    presetDetail.value = speciesDetail.value
    const act = await api.actionDetail(sp.id, actionId)
    actionEditor.value = act
    actionJson.value = JSON.stringify(act, null, 2)
    motionPreview.value = null
  } catch(e) { ElMessage.error(e.message) }
}

function startCreateAction() {
  actionEditor.value = { schema:'assetslab_motion3d_v1', motion_id:'', title:'', description:'', species:selectedSpecies.value.id, frame_count:8, params:{}, root3d:{dy:{phase:true}}, offsets3d:{}, ik3d:{} }
  actionJson.value = JSON.stringify(actionEditor.value, null, 2)
  motionPreview.value = null
}

async function saveAction() {
  saving.value = true
  try {
    const data = JSON.parse(actionJson.value)
    if (!data.motion_id) { ElMessage.warning('motion_id 不能为空'); saving.value=false; return }
    data.species = selectedSpecies.value.id
    if (actionEditor.value?.motion_id && actionEditor.value.motion_id !== data.motion_id) {
      await api.createAction(selectedSpecies.value.id, data)
      await api.deleteAction(selectedSpecies.value.id, actionEditor.value.motion_id)
    } else if (actionEditor.value?.motion_id) {
      await api.updateAction(selectedSpecies.value.id, data.motion_id, data)
    } else {
      await api.createAction(selectedSpecies.value.id, data)
    }
    ElMessage.success('动作已保存')
    actionEditor.value = null
    speciesDetail.value = await api.speciesDetail(selectedSpecies.value.id)
    presetDetail.value = speciesDetail.value
    await loadSpecies()
  } catch(e) { ElMessage.error('保存失败: ' + e.message) }
  saving.value = false
}

async function confirmDeleteAction(actionId) {
  try {
    await ElMessageBox.confirm(`确定删除动作「${actionId}」吗？`, '确认', { type:'warning' })
    await api.deleteAction(selectedSpecies.value.id, actionId)
    ElMessage.success('已删除')
    speciesDetail.value = await api.speciesDetail(selectedSpecies.value.id)
    presetDetail.value = speciesDetail.value
    await loadSpecies()
  } catch(e) { if (e !== 'cancel') ElMessage.error(e.message || e) }
}

// -- 渲染 --

async function renderAllViews() {
  if (!selectedSpecies.value) return
  previewLoading.value = true
  try {
    // 用第一个可用预设渲染（数据驱动，不硬编码预设 id）
    const pl = await api.presets()
    const pid = (pl.skeletons || [])[0]?.id
    if (!pid) { ElMessage.warning('暂无预设，先创建预设'); return }
    for (const view of ['front','side','back']) {
      const r = await api.renderSkeleton(pid, { view })
      previews.value[view] = r.data_url
    }
  } catch(e) { ElMessage.error(e.message) }
  previewLoading.value = false
}

async function renderAction() {
  if (!actionEditor.value?.motion_id) { ElMessage.warning('请先填写 motion_id'); return }
  motionRenderLoading.value = true
  try {
    // 3D 动作：3D 相机渲染
    const r = await api.renderMotion3d(actionEditor.value.motion_id, camQS() + '&gif=1')
    motionPreview.value = r.gif || r.data_url
  } catch(e) { ElMessage.error(e.message) }
  motionRenderLoading.value = false
}

// -- 物种 CRUD --

function startCreate() {
  isCreating.value = true
  editMode.value = 'create'
  editForm.value = { species_id:'', title:'', description:'', jointsStr:'{}', bonesStr:'{}', chainsStr:'{}', paramChainsStr:'{}' }
}

function startEdit(sp) {
  isCreating.value = false
  editMode.value = 'edit'
  api.speciesDetail(sp.id).then(d => {
    editForm.value = {
      species_id: d.species_id || sp.id,
      title: d.title || '', description: d.description || '',
      jointsStr: JSON.stringify(d.joints || {}, null, 2),
      bonesStr: JSON.stringify(d.bones || {}, null, 2),
      chainsStr: JSON.stringify(d.chains || {}, null, 2),
      paramChainsStr: JSON.stringify(d.param_chains || {}, null, 2),
    }
  }).catch(e => ElMessage.error(e.message))
}

async function saveSpecies() {
  saving.value = true
  try {
    const data = {
      species_id: editForm.value.species_id.trim(),
      title: editForm.value.title.trim(),
      description: editForm.value.description.trim(),
      joints: JSON.parse(editForm.value.jointsStr),
      bones: JSON.parse(editForm.value.bonesStr),
      chains: JSON.parse(editForm.value.chainsStr),
      param_chains: JSON.parse(editForm.value.paramChainsStr),
      schema: 'assetslab_species_v1',
    }
    if (!data.species_id) { ElMessage.warning('物种ID不能为空'); saving.value=false; return }
    if (isCreating.value) await api.createSpecies(data)
    else await api.updateSpecies(data.species_id, data)
    ElMessage.success('已保存')
    editMode.value = null
    selectedSpecies.value = null
    speciesDetail.value = null
    presetDetail.value = null
    await loadSpecies()
  } catch(e) { ElMessage.error('保存失败: ' + e.message) }
  saving.value = false
}

async function confirmDelete(sp) {
  try {
    await ElMessageBox.confirm(`确定删除物种「${sp.title}」吗？此操作不可恢复。`, '确认删除', { type:'warning', confirmButtonText:'删除', cancelButtonText:'取消' })
    await api.deleteSpecies(sp.id)
    ElMessage.success('已删除')
    if (selectedSpecies.value?.id === sp.id) { selectedSpecies.value=null; speciesDetail.value=null; presetDetail.value=null }
    await loadSpecies()
  } catch(e) { if (e !== 'cancel') ElMessage.error(e.message || e) }
}
</script>

<style scoped>
.page { max-width: 1280px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 1.4rem; }
.page-desc { color: #909399; font-size: .85rem; margin: 0; }
.layout { display: flex; gap: 20px; min-height: 70vh; }

.sidebar { width: 320px; flex-shrink: 0; background: #fff; border: 1px solid #e4e7ed; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.sidebar-header { padding: 12px 16px; font-weight: 600; font-size: .9rem; border-bottom: 1px solid #ebeef5; display: flex; justify-content: space-between; align-items: center; }
.panel-loading { padding: 20px; }
.sidebar-list { flex: 1; overflow-y: auto; max-height: calc(100vh - 220px); }
.list-item { padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f0f2f5; transition: background .15s; }
.list-item:hover { background: #f5f7fa; }
.list-item.active { background: #ecf5ff; border-left: 3px solid #409eff; }
.item-main { display: flex; align-items: center; gap: 8px; }
.item-name { font-weight: 600; font-size: .9rem; }
.item-id { color: #909399; font-size: .72rem; font-family: monospace; }
.item-meta { display: flex; gap: 6px; margin-top: 6px; }
.meta-chip { font-size: .7rem; color: #909399; background: #f5f7fa; border: 1px solid #ebeef5; padding: 1px 6px; border-radius: 4px; }
.item-actions { display: flex; justify-content: flex-end; margin-top: 4px; opacity: 0; transition: opacity .15s; }
.list-item:hover .item-actions { opacity: 1; }
.empty-list { padding: 40px 20px; text-align: center; color: #c0c4cc; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.empty-icon { font-size: 2rem; }

.content { flex: 1; background: #fff; border: 1px solid #e4e7ed; border-radius: 10px; padding: 20px 24px; overflow-y: auto; max-height: calc(100vh - 160px); box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.content.empty { display: flex; align-items: center; justify-content: center; }
.content-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.crumb { display: flex; align-items: center; gap: 6px; font-size: .85rem; }
.crumb-root { color: #909399; } .crumb-sep { color: #c0c4cc; } .crumb-now { font-weight: 600; color: #303133; }
.content-actions { display: flex; gap: 8px; }

.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: #f8fafc; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 16px; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 700; color: #409eff; }
.stat-label { font-size: .75rem; color: #909399; margin-top: 2px; }

.section { margin-top: 4px; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 0 0 12px; }
.section-head h4 { margin: 0; font-size: .95rem; color: #606266; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.mono { font-family: monospace; font-size: .78rem; }
.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; }
.joint-tag { max-width: 100%; }
.tag-group { color: #409eff; font-weight: 600; }
.chain-list { display: flex; flex-direction: column; gap: 8px; }
.chain-row { display: flex; align-items: center; gap: 12px; padding: 6px 12px; background: #fafbfc; border: 1px solid #ebeef5; border-radius: 6px; }
.chain-path { font-family: monospace; font-size: .78rem; color: #606266; }
.param-tag { margin-right: 4px; }
.cell-main { display: flex; align-items: center; gap: 8px; }
.cell-title { font-weight: 600; } .cell-id { color: #909399; font-size: .72rem; }

.preview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.preview-cell { text-align: center; }
.preview-title { font-size: .8rem; color: #909399; margin-bottom: 6px; font-weight: 600; }
.preview-cell img { width: 100%; border: 1px solid #111827; border-radius: 8px; background: #111827; }
.preview-empty { text-align: center; color: #c0c4cc; padding: 40px; border: 2px dashed #e4e7ed; border-radius: 8px; }
.empty-inline { color: #c0c4cc; padding: 20px; text-align: center; }
.preview-controls { display: flex; gap: 8px; align-items: center; }
.motion-preview { display: flex; justify-content: center; }
.motion-preview img { max-width: 100%; border: 1px solid #111827; border-radius: 8px; background: #111827; }

.empty-state { text-align: center; color: #909399; }
.empty-state .empty-icon { font-size: 3rem; margin-bottom: 12px; }
.empty-state h3 { margin: 0 0 8px; color: #303133; }
.empty-state p { margin: 0 0 16px; font-size: .85rem; }
</style>
