<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workflowApi, urlFromPath, PHASE_LABEL, STATUS_LABEL } from '../api'
import BodyPanel from '../components/BodyPanel.vue'

const route = useRoute()
const router = useRouter()

const instances = ref([])
const bodyTemplates = ref([])
const def = ref(null)      // definition {actions:[...]}
const state = ref(null)    // instance status (includes body + per-action state)
const wfId = ref('')
const current = ref(0)
const paramValues = reactive({})
const log = ref([])
const busy = ref(false)

const actions = computed(() => def.value?.actions || [])
const currentAction = computed(() => actions.value[current.value] || { action_id: '', params: {} })
const currentState = computed(() => (state.value?.actions || {})[currentAction.value.action_id] || {})
const body = computed(() => state.value?.body || {})

function pushLog(text) { log.value = [text, ...log.value].slice(0, 60) }

async function loadInstances() {
  instances.value = (await workflowApi.list().catch(() => [])) || []
}
async function loadBodyTemplates() {
  const d = await workflowApi.bodyTemplates().catch(() => ({}))
  bodyTemplates.value = d.body_templates || []
}

async function openInstance(id) {
  if (!id) return
  wfId.value = id
  state.value = await workflowApi.status(id)
  const st = state.value
  def.value = await workflowApi.definition(st.definition_id || 'default')
  // Land on the recommended next action.
  const nr = await workflowApi.next(id).catch(() => ({ next: null }))
  const idx = nr.next ? actions.value.findIndex((a) => a.action_id === nr.next) : -1
  current.value = idx >= 0 ? idx : 0
  seedParams()
}

function seedParams() {
  Object.keys(paramValues).forEach((k) => delete paramValues[k])
  const st = currentState.value
  for (const [k, spec] of Object.entries(currentAction.value.params || {})) {
    const d = spec?.default ?? 1.0
    paramValues[k] = st.params?.[k] ?? d
  }
}

watch(current, seedParams)

function onInstanceChange(id) {
  router.replace({ path: '/wizard', query: { id } })
  openInstance(id)
}

// ---- step ops -----------------------------------------------------------
async function runStep() {
  busy.value = true
  try {
    const r = await workflowApi.run(wfId.value, currentAction.value.action_id, { params: { ...paramValues } })
    pushLog(`[run] ${currentAction.value.action_id} params=${JSON.stringify(paramValues)} → ${JSON.stringify(r)}`)
    await refresh()
  } catch (e) { ElMessage.error(`运行失败：${e.message}`) } finally { busy.value = false }
}

async function refresh() {
  state.value = await workflowApi.status(wfId.value)
  seedParams()
}

async function goNext() {
  const st = currentState.value
  if (st.status !== 'passed') { ElMessage.warning('当前步骤尚未运行通过，请先「运行」。'); return }
  const nr = await workflowApi.next(wfId.value).catch(() => ({ next: null }))
  const idx = nr.next ? actions.value.findIndex((a) => a.action_id === nr.next) : -1
  if (idx >= 0) { current.value = idx }
  else { ElMessage.success('✅ 全部步骤已完成。') }
}

// ---- outputs (previous vs current side by side) --------------------------
function outputImages(list) {
  return (list || []).map(urlFromPath).filter(Boolean)
}

onMounted(async () => {
  await Promise.all([loadInstances(), loadBodyTemplates()])
  const urlId = route.query.id
  if (urlId) await openInstance(urlId)
  else if (instances.value.length) await openInstance(instances.value[0].workflow_id)
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center gap-3">
      <span class="text-sm text-slate-400">流程实例</span>
      <el-select v-model="wfId" filterable placeholder="选择实例" style="width: 260px" @change="onInstanceChange">
        <el-option v-for="it in instances" :key="it.workflow_id" :label="`${it.workflow_id} · ${it.progress}`" :value="it.workflow_id" />
      </el-select>
      <el-button @click="loadInstances()">⟳ 刷新</el-button>
      <span v-if="state" class="text-xs text-slate-500">{{ state.definition_id }} · v{{ state.version }} · {{ state.updated_at }}</span>
    </div>

    <template v-if="def && wfId">
      <!-- step stepper -->
      <el-steps :active="current" finish-status="success" align-center class="py-2">
        <el-step v-for="(a, i) in actions" :key="a.action_id" :title="String(i + 1)" :description="STATUS_LABEL[(state?.actions?.[a.action_id] || {}).status] || ''">
          <template #title><span class="text-sm">{{ i + 1 }}</span></template>
        </el-step>
      </el-steps>

      <!-- body panel -->
      <BodyPanel :workflow-id="wfId" :body="body" :body-template="state.body_template" :body-templates="bodyTemplates" @saved="(b) => (state.body = b)" />

      <!-- current step -->
      <div class="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-4">
        <div class="flex flex-wrap items-center gap-3">
          <el-tag size="small" type="info">{{ current + 1 }} / {{ actions.length }}</el-tag>
          <h2 class="text-lg font-semibold m-0">{{ currentAction.title }}</h2>
          <el-tag size="small">{{ PHASE_LABEL[currentAction.phase] || currentAction.phase }}</el-tag>
          <el-tag size="small" :type="currentState.status === 'passed' ? 'success' : currentState.status === 'failed' ? 'danger' : 'info'">
            {{ STATUS_LABEL[currentState.status] || currentState.status }}
          </el-tag>
        </div>
        <p class="text-slate-400 text-sm m-0">{{ currentAction.description }}</p>

        <div v-if="Object.keys(currentAction.params || {}).length" class="space-y-2">
          <div class="text-sm font-medium text-cyan-300">参数</div>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
            <label v-for="(spec, k) in currentAction.params" :key="k" class="flex items-center justify-between gap-2 bg-slate-900 rounded-lg px-3 py-2">
              <span class="text-sm">{{ spec.label || k }}</span>
              <el-input-number v-model="paramValues[k]" :min="spec.min ?? 0" :max="spec.max ?? 3" :step="0.05" size="small" controls-position="right" />
            </label>
          </div>
        </div>

        <!-- outputs: previous vs current -->
        <div v-if="outputImages(currentState.outputs).length || outputImages(currentState.prev_outputs).length" class="flex flex-wrap gap-6">
          <div v-if="outputImages(currentState.prev_outputs).length">
            <div class="text-xs text-slate-400 mb-1">上一版</div>
            <img v-for="u in outputImages(currentState.prev_outputs)" :key="u" :src="`${u}?t=${encodeURIComponent(currentState.finished_at || Date.now())}`" class="max-h-56 rounded-lg border border-slate-700 image-render-pixel" />
          </div>
          <div>
            <div class="text-xs text-slate-400 mb-1">当前版</div>
            <img v-for="u in outputImages(currentState.outputs)" :key="u" :src="`${u}?t=${encodeURIComponent(currentState.finished_at || Date.now())}`" class="max-h-56 rounded-lg border border-slate-700 image-render-pixel" />
          </div>
        </div>
        <div v-else class="text-slate-500 text-sm">（尚无输出）</div>

        <div class="flex flex-wrap gap-2 pt-1">
          <el-button type="primary" :loading="busy" @click="runStep">▶ 运行（带参数）</el-button>
        </div>
        <div v-if="currentState.params && Object.keys(currentState.params).length" class="text-xs text-slate-500">
          上次参数：{{ Object.entries(currentState.params).map(([k, v]) => `${k}=${v}`).join(' · ') }}
        </div>
      </div>

      <!-- nav -->
      <div class="flex gap-3">
        <el-button :disabled="current <= 0" @click="current--">← 上一步</el-button>
        <el-button type="primary" @click="goNext">下一步 →</el-button>
      </div>
    </template>

    <div v-else-if="!wfId" class="text-slate-500 py-10 text-center">
      请在上方选择一个实例（新建实例请到「控制台」）。
    </div>

    <!-- log -->
    <div class="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
      <div class="text-sm font-medium text-cyan-300 mb-2">操作日志</div>
      <pre class="text-xs text-slate-400 whitespace-pre-wrap max-h-64 overflow-auto m-0">{{ log.join('\n') || '—' }}</pre>
    </div>
  </div>
</template>

<style scoped>
.image-render-pixel { image-rendering: pixelated; }
</style>
