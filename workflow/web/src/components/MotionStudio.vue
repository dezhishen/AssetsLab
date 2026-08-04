<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workflowApi } from '../api'

const motions = ref([])
const motionId = ref('')
const view = ref('front')
const stage = ref('arms')
const ik = ref(false)
const blendId = ref('')
const blendT = ref(0.5)
const result = ref('')
const status = ref('')
const loading = ref(false)

const MV_PARAM_KEYS = ['stride', 'pelvis_bob', 'arm_swing']
const MV_LABEL = { stride: '步幅', pelvis_bob: '骨盆起伏', arm_swing: '摆臂' }
const params = reactive({})
const body = reactive({
  arm_length: 1, leg_length: 1, torso_length: 1, shoulder_width: 1, head_scale: 1, height: 1,
})
const BODY_LABEL = { arm_length: '臂长', leg_length: '腿长', torso_length: '躯干长', shoulder_width: '肩宽', head_scale: '头大小', height: '身高' }

const currentMotion = computed(() => motions.value.find((m) => m.id === motionId.value) || motions.value[0])

async function load() {
  const d = await workflowApi.motions().catch(() => ({}))
  motions.value = d.motions || []
  if (motions.value.length) {
    motionId.value = motions.value[0].id
    blendSelectOptions()
    seedParams()
    render()
  }
}

function seedParams() {
  Object.keys(params).forEach((k) => delete params[k])
  const m = currentMotion.value
  const keys = m?.params && Object.keys(m.params).length ? Object.keys(m.params) : MV_PARAM_KEYS
  for (const k of keys) params[k] = m.params?.[k]?.default ?? 1.0
}

function blendSelectOptions() {
  blendId.value = ''
}

watch(view, (v) => { if (v === 'back' && ['pelvis', 'arms'].includes(stage.value)) stage.value = 'legs' })

async function render() {
  if (!motionId.value) return
  loading.value = true
  try {
    const r = await workflowApi.renderMotion(motionId.value, {
      view: view.value, stage: stage.value, ik: ik.value,
      ...{ ...params }, ...{ ...body },
      blend: blendId.value || undefined, blend_t: blendT.value,
    })
    if (r.gif) {
      result.value = r.gif
      status.value = `${view.value}/${stage.value}${stage.value === 'skeleton' ? '（静态参考）' : ''}${blendId.value && blendT.value > 0 ? ` · 混合 ${blendId.value} ${blendT.value}` : ''}${ik.value ? ' · IK' : ''}`
    } else {
      result.value = ''
      status.value = `渲染错误：${r.error || JSON.stringify(r)}`
    }
  } catch (e) {
    result.value = ''
    status.value = `请求失败：${e.message}`
  } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center gap-3">
      <el-select v-model="motionId" style="width: 160px" @change="seedParams">
        <el-option v-for="m in motions" :key="m.id" :label="`${m.id} — ${m.title}`" :value="m.id" />
      </el-select>
      <el-select v-model="view" style="width: 110px">
        <el-option label="front" value="front" /><el-option label="side" value="side" /><el-option label="back" value="back" />
      </el-select>
      <el-select v-model="stage" style="width: 130px" title="完整动作 = 全部层合成的动画；静态骨架 = 参考图">
        <el-option label="完整动作" value="arms" /><el-option label="静态骨架" value="skeleton" />
        <el-option label="腿循环" value="legs" /><el-option label="骨盆" value="pelvis" />
      </el-select>
      <el-checkbox v-model="ik">IK 落地锁定</el-checkbox>
      <el-button type="primary" :loading="loading" @click="render">⟳ 渲染循环</el-button>
      <span class="text-xs text-slate-400">{{ status }}</span>
    </div>

    <div class="text-xs text-slate-500">动作参数（怎么动）</div>
    <div class="flex flex-wrap gap-3">
      <label v-for="(v, k) in params" :key="k" class="flex items-center gap-2">
        <span class="text-sm">{{ MV_LABEL[k] || k }}</span>
        <el-input-number v-model="params[k]" :step="0.05" size="small" controls-position="right" @change="render" />
      </label>
    </div>

    <details class="group">
      <summary class="text-xs text-slate-500 cursor-pointer select-none">角色体型（骨骼比例 · 与动作正交，三视图共享）</summary>
      <div class="flex flex-wrap gap-3 mt-2">
        <label v-for="(v, k) in body" :key="k" class="flex items-center gap-2">
          <span class="text-sm">{{ BODY_LABEL[k] }}</span>
          <el-input-number v-model="body[k]" :min="0.6" :max="1.6" :step="0.05" size="small" controls-position="right" @change="render" />
        </label>
      </div>
    </details>

    <div class="flex flex-wrap items-center gap-3">
      <el-select v-model="blendId" style="width: 130px" @change="render">
        <el-option label="无混合" value="" />
        <el-option v-for="m in motions" :key="m.id" :label="m.id" :value="m.id" />
      </el-select>
      <el-slider v-model="blendT" :min="0" :max="1" :step="0.05" style="width: 160px" @change="render" />
    </div>

    <div v-if="result" class="mt-2">
      <img :src="result" class="max-w-full max-h-64 rounded-lg border border-slate-700 image-render-pixel" />
    </div>
  </div>
</template>

<style scoped>
.image-render-pixel { image-rendering: pixelated; }
</style>
