<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { workflowApi } from '../api'

const props = defineProps({
  workflowId: { type: String, required: true },
  body: { type: Object, default: () => ({}) },
  bodyTemplate: { type: String, default: '' },
  bodyTemplates: { type: Array, default: () => [] },
})
const emit = defineEmits(['saved'])

const open = ref(false)
const local = reactive({})
watch(() => props.body, (v) => Object.assign(local, v || {}), { immediate: true, deep: true })

const BODY_KEYS = ['arm_length', 'leg_length', 'torso_length', 'shoulder_width', 'head_scale', 'neck_length', 'height']
const BODY_LABEL = { arm_length: '臂长', leg_length: '腿长', torso_length: '躯干长', shoulder_width: '肩宽', head_scale: '头大小', neck_length: '脖子长', height: '身高' }
const BODY_MIN = { arm_length: 0.6, leg_length: 0.6, torso_length: 0.6, shoulder_width: 0.6, head_scale: 0.6, neck_length: 0.6, height: 0.8 }
const BODY_MAX = { arm_length: 1.6, leg_length: 1.6, torso_length: 1.6, shoulder_width: 1.6, head_scale: 1.6, neck_length: 1.6, height: 1.4 }

const presetTitle = computed(() => {
  const t = props.bodyTemplates.find((x) => x.id === props.bodyTemplate)
  return t ? t.title : (props.bodyTemplate || '')
})
const summary = computed(() => {
  const parts = BODY_KEYS.filter((k) => Math.abs((local[k] ?? 1) - 1) > 0.001).map((k) => `${BODY_LABEL[k]} ${local[k]}`)
  return (presetTitle.value ? `${presetTitle.value} · ` : '') + (parts.join(' · ') || '标准体型')
})

const saving = ref(false)
let timer = null
watch(local, () => {
  if (!props.workflowId) return
  clearTimeout(timer)
  timer = setTimeout(save, 500)
}, { deep: true })

async function save() {
  saving.value = true
  try {
    const r = await workflowApi.setBody(props.workflowId, { ...local })
    emit('saved', r.body || { ...local })
  } catch (e) {
    // keep local edits; surface quietly
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-collapse v-model="open" class="rounded-lg border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60">
    <el-collapse-item name="body">
      <template #title>
        <div class="flex items-center gap-3 text-sm">
          <span class="font-medium text-cyan-600 dark:text-cyan-300">角色体型</span>
          <span class="text-slate-500 text-xs truncate max-w-md dark:text-slate-400">{{ summary }}</span>
          <span v-if="saving" class="text-slate-500 text-xs">保存中…</span>
        </div>
      </template>
      <p class="text-xs text-slate-500 mb-3">骨骼比例（臂长/腿长/躯干长/肩宽/头大小/身高）属于「角色」而非「动作」；三视图共享，修改后自动保存到该实例。</p>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <label v-for="k in BODY_KEYS" :key="k" class="flex items-center justify-between gap-2 bg-slate-100 rounded-lg px-3 py-2 dark:bg-slate-900">
          <span class="text-sm">{{ BODY_LABEL[k] }}</span>
          <el-input-number v-model="local[k]" :min="BODY_MIN[k]" :max="BODY_MAX[k]" :step="0.05" size="small" controls-position="right" />
        </label>
      </div>
    </el-collapse-item>
  </el-collapse>
</template>
