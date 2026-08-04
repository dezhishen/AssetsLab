<script setup>
import { ref, reactive, computed, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElCheckbox, ElMessage, ElMessageBox } from 'element-plus'
import { workflowApi, PHASE_LABEL, STATUS_LABEL } from '../api'
import MotionStudio from '../components/MotionStudio.vue'

const router = useRouter()
const instances = ref([])
const definitions = ref([])
const templates = ref([])
const bodyTemplates = ref([])
const newDef = ref('default')
const newTpl = ref('')
const newBodyTpl = ref('')
const newId = ref('')
const newBodyTplDesc = ref('')
const detail = ref(null)
const detailDef = ref(null)
const log = ref([])

const groups = computed(() => {
  const map = {}
  for (const a of detailDef.value?.actions || []) {
    ;(map[a.phase] ||= []).push(a)
  }
  return map
})

const pmOpen = ref(false)
const pmWorkflow = ref('')
const pmAction = ref(null)
const pmParams = reactive({})
const instSearch = ref('')

// Instances as a searchable list, newest updated first.
const filteredInstances = computed(() => {
  const q = instSearch.value.trim().toLowerCase()
  return instances.value
    .filter((it) => !q
      || (it.workflow_id || '').toLowerCase().includes(q)
      || (it.definition_id || '').toLowerCase().includes(q))
    .slice()
    .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
})

function pushLog(text) { log.value = [text, ...log.value].slice(0, 60) }

function progressPct(p) {
  const [a, b] = String(p || '0/0').split('/')
  return b > 0 ? Math.round((a / b) * 100) : 0
}

async function loadAll() {
  instances.value = (await workflowApi.list().catch(() => [])) || []
  const [d, t, b] = await Promise.all([
    workflowApi.definitions().catch(() => ({ definitions: [] })),
    workflowApi.templates().catch(() => ({ templates: [] })),
    workflowApi.bodyTemplates().catch(() => ({ body_templates: [] })),
  ])
  definitions.value = d.definitions || []
  templates.value = t.templates || []
  bodyTemplates.value = b.body_templates || []
  if (!definitions.value.includes(newDef.value) && definitions.value.length) newDef.value = definitions.value[0]
}

async function createInstance() {
  try {
    const r = await workflowApi.create({
      definition: newDef.value, id: newId.value || undefined,
      template: newTpl.value || undefined, body_template: newBodyTpl.value || undefined,
    })
    pushLog(`新建实例 → ${JSON.stringify(r)}`)
    newId.value = ''
    await loadAll()
    if (r.workflow_id) await openDetail(r.workflow_id)
  } catch (e) { ElMessage.error(e.message) }
}

function updateBodyTplDesc() {
  const t = bodyTemplates.value.find((x) => x.id === newBodyTpl.value)
  newBodyTplDesc.value = t ? t.description : '创建时套用的角色体型预设；留空 = 标准体型。'
}

async function openDetail(id) {
  detail.value = await workflowApi.status(id)
  detailDef.value = await workflowApi.definition(detail.value.definition_id || 'default')
}
function gotoWizard(id) { router.push({ path: '/wizard', query: { id } }) }

const removeArtifacts = ref(false)

async function removeInstance(id) {
  try {
    await ElMessageBox.confirm(
      h('div', { class: 'space-y-2' }, [
        h('p', { class: 'm-0 text-sm' }, `确定删除实例「${id}」吗？`),
        h('p', { class: 'm-0 text-xs text-slate-500' }, '其导出制品默认保留，可在「制品」页单独删除。'),
        h(ElCheckbox,
          { modelValue: removeArtifacts.value, 'onUpdate:modelValue': (v) => { removeArtifacts.value = v } },
          () => `同时删除导出制品（dist/${id}/）`),
      ]),
      '删除实例',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' },
    )
  } catch (e) { return } // cancelled
  try {
    const r = await workflowApi.deleteInstance(id, { remove_artifacts: removeArtifacts.value })
    pushLog(`删除实例 → ${JSON.stringify(r)}`)
    if (detail.value?.workflow_id === id) detail.value = null
    removeArtifacts.value = false
    await loadAll()
  } catch (e) { ElMessage.error(e.message) }
}

function stFor(aid) { return (detail.value?.actions || {})[aid] || {} }

function openParams(workflowId, action) {
  pmWorkflow.value = workflowId
  pmAction.value = action
  Object.keys(pmParams).forEach((k) => delete pmParams[k])
  const st = stFor(action.action_id)
  for (const [k, spec] of Object.entries(action.params || {})) {
    pmParams[k] = st.params?.[k] ?? spec?.default ?? 1.0
  }
  pmOpen.value = true
}
async function runWithParams() {
  try {
    await workflowApi.run(pmWorkflow.value, pmAction.value.action_id, { params: { ...pmParams } })
    pushLog(`[run] ${pmWorkflow.value}/${pmAction.value.action_id} params=${JSON.stringify(pmParams)}`)
    pmOpen.value = false
    await openDetail(pmWorkflow.value)
  } catch (e) { ElMessage.error(e.message) }
}
async function act(id, aid) {
  try {
    await workflowApi.run(id, aid)
    pushLog(`[run] ${id}/${aid}`)
    await openDetail(id)
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(async () => { await loadAll(); updateBodyTplDesc() })
</script>

<template>
  <div class="space-y-6">
    <!-- create instance -->
    <div class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-4">
      <div class="flex flex-wrap items-center gap-3">
        <el-button @click="loadAll">⟳ 刷新</el-button>
        <el-select v-model="newDef" style="width: 130px">
          <el-option v-for="d in definitions" :key="d" :label="d" :value="d" />
        </el-select>
        <el-select v-model="newTpl" placeholder="参数模板" style="width: 170px" clearable>
          <el-option v-for="t in templates" :key="t.id" :label="`${t.title}（${t.id}）`" :value="t.id" />
        </el-select>
        <el-select v-model="newBodyTpl" placeholder="体型模板" style="width: 170px" clearable @change="updateBodyTplDesc">
          <el-option v-for="t in bodyTemplates" :key="t.id" :label="`${t.title}（${t.id}）`" :value="t.id" />
        </el-select>
        <el-input v-model="newId" placeholder="实例 id（留空用默认）" style="width: 190px" clearable />
        <el-button type="primary" @click="createInstance">＋ 新建实例</el-button>
      </div>
      <div class="text-xs text-slate-500 mt-2">{{ newBodyTplDesc }}</div>
    </div>

    <!-- motion studio -->
    <div class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-4">
      <h2 class="text-lg font-semibold m-0 mb-1">动作预览台 <span class="text-xs text-slate-500 font-normal">数据驱动动作预设 · pose library</span></h2>
      <MotionStudio />
    </div>

    <!-- instances -->
    <div class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-4">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
        <h2 class="text-lg font-semibold m-0">工作流实例 <span class="text-xs text-slate-500 font-normal">共 {{ instances.length }} 个 · 按更新时间倒序</span></h2>
        <el-input v-model="instSearch" placeholder="搜索实例 id / 定义…" clearable style="width: 240px">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
      <div v-if="!instances.length" class="text-slate-500 py-6 text-center">暂无实例，点击上方「新建实例」开始。</div>
      <div v-else-if="!filteredInstances.length" class="text-slate-500 py-6 text-center">没有匹配「{{ instSearch }}」的实例。</div>
      <div v-else class="divide-y divide-slate-200 dark:divide-slate-700">
        <div v-for="it in filteredInstances" :key="it.workflow_id" class="flex items-center gap-3 py-3 cursor-pointer rounded px-2 -mx-2 hover:bg-slate-100 dark:hover:bg-slate-800/60" @click="gotoWizard(it.workflow_id)">
          <div class="flex-1 min-w-0">
            <div class="font-medium">{{ it.workflow_id }}</div>
            <div class="text-xs text-slate-500">{{ it.definition_id }} · v{{ it.version }} · {{ it.updated_at }}</div>
          </div>
          <div class="w-32 shrink-0">
            <el-progress :percentage="progressPct(it.progress)" :show-text="false" />
          </div>
          <span class="text-xs text-slate-500 whitespace-nowrap dark:text-slate-400 w-10 text-right shrink-0">{{ it.progress }}</span>
          <el-button size="small" @click.stop="openDetail(it.workflow_id)">详情</el-button>
          <el-button size="small" type="danger" plain @click.stop="removeInstance(it.workflow_id)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- detail -->
    <div v-if="detail" class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-4">
      <div class="flex items-center gap-3 flex-wrap mb-3">
        <el-button size="small" @click="detail = null">← 返回列表</el-button>
        <h2 class="text-lg font-semibold m-0">{{ detail.workflow_id }} <span class="text-sm font-normal text-slate-500 dark:text-slate-400">· {{ detail.title }}</span></h2>
        <el-button size="small" type="primary" @click="gotoWizard(detail.workflow_id)">进入向导</el-button>
      </div>
      <div v-if="detail.body" class="text-xs text-slate-500 mb-3">
        体型：{{ JSON.stringify(detail.body) }}
      </div>
      <div v-for="(list, phase) in groups" :key="phase" class="mb-4">
        <div class="text-sm font-medium text-cyan-600 dark:text-cyan-300 mb-2">{{ PHASE_LABEL[phase] || phase }}</div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div v-for="a in list" :key="a.action_id" class="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-950 p-3">
            <div class="flex items-center gap-2">
              <span class="font-medium text-sm">{{ a.title }}</span>
              <span class="text-xs text-slate-500 font-mono">{{ a.action_id }}</span>
              <el-tag size="small" :type="stFor(a.action_id).status === 'passed' ? 'success' : stFor(a.action_id).status === 'failed' ? 'danger' : 'info'">
                {{ STATUS_LABEL[stFor(a.action_id).status] || stFor(a.action_id).status }}
              </el-tag>
            </div>
            <div class="text-xs text-slate-500 mt-1">{{ a.description }}</div>
            <div v-if="stFor(a.action_id).outputs?.length" class="mt-2">
              <img v-for="u in stFor(a.action_id).outputs.map((p) => p.split('/run/')[1] ? '/run/' + p.split('/run/')[1] : null).filter(Boolean)" :key="u" :src="u" class="max-h-40 rounded border border-slate-200 dark:border-slate-700 image-render-pixel" />
            </div>
            <div class="flex gap-2 mt-3">
              <el-button v-if="Object.keys(a.params || {}).length" size="small" type="primary" @click="openParams(detail.workflow_id, a)">▶ 运行（带参数）</el-button>
              <el-button v-else size="small" type="primary" @click="act(detail.workflow_id, a.action_id)">▶ 运行</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- log -->
    <div class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-4">
      <div class="text-sm font-medium text-cyan-600 dark:text-cyan-300 mb-2">最近操作日志</div>
      <pre class="text-xs text-slate-600 whitespace-pre-wrap max-h-72 overflow-auto m-0 dark:text-slate-400">{{ log.join('\n') || '—' }}</pre>
    </div>

    <!-- run-with-params dialog -->
    <el-dialog v-model="pmOpen" :title="`运行：${pmAction?.title || ''}`" width="480px">
      <div class="grid grid-cols-2 gap-3">
        <label v-for="(spec, k) in pmAction?.params || {}" :key="k" class="flex items-center justify-between gap-2">
          <span class="text-sm">{{ spec.label || k }}</span>
          <el-select v-if="spec.choices" v-model="pmParams[k]" size="small" style="width: 150px">
            <el-option v-for="c in spec.choices" :key="c" :label="c" :value="c" />
          </el-select>
          <el-input-number v-else-if="typeof spec.default === 'number' || spec.min !== undefined || spec.max !== undefined" v-model="pmParams[k]" :min="spec.min ?? 0" :max="spec.max ?? 3" :step="0.05" size="small" controls-position="right" />
          <el-input v-else v-model="pmParams[k]" size="small" style="width: 150px" />
        </label>
      </div>
      <template #footer>
        <el-button @click="pmOpen = false">取消</el-button>
        <el-button type="primary" @click="runWithParams">运行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.image-render-pixel { image-rendering: pixelated; }
</style>
