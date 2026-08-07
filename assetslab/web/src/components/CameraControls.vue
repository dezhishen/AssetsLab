<template>
  <div class="cam-controls" :class="{ compact }">
    <!-- 预设视角快捷入口 -->
    <div class="cam-presets">
      <el-button v-for="p in presets" :key="p.label" size="small"
                 :type="activePreset === p.label ? 'primary' : ''"
                 @click="applyPreset(p)">{{ p.label }}</el-button>
    </div>
    <!-- 相机数值（input-number，紧凑单行；不用滑块） -->
    <div class="cam-fields">
      <div class="cam-field" v-for="item in items" :key="item.key" :title="item.label">
        <span class="cam-key">{{ item.short }}</span>
        <el-input-number :min="item.min" :max="item.max" :step="item.step"
                         :model-value="cam[item.key]" @update:model-value="set(item.key, $event)"
                         size="small" controls-position="right" class="cam-input" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

/**
 * 3D 相机控制（可复用）：预设视角快捷入口 + 角度/距离/缩放/平移滑块。
 * v-model 绑定相机状态 { yaw, pitch, dist, zoom, panX, panY }。
 * compact 模式只保留预设入口 + yaw/pitch 微调（用于动作预览区）。
 */
const props = defineProps({
  modelValue: { type: Object, required: true },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const cam = computed(() => props.modelValue)
const set = (key, val) => emit('update:modelValue', { ...props.modelValue, [key]: val })

const presets = [
  { label: '正面', yaw: 0, pitch: 0 },
  { label: '侧面', yaw: 90, pitch: 0 },
  { label: '背面', yaw: 180, pitch: 0 },
  { label: '斜侧 45°', yaw: 45, pitch: 10 },
  { label: '俯视 30°', yaw: 30, pitch: 30 },
  { label: '微仰', yaw: 30, pitch: -15 },
]
const applyPreset = (p) => emit('update:modelValue', { ...props.modelValue, yaw: p.yaw, pitch: p.pitch })

const activePreset = computed(() => {
  const p = presets.find(x => x.yaw === cam.value.yaw && x.pitch === cam.value.pitch)
  return p ? p.label : ''
})

const items = computed(() => {
  const base = [
    { key: 'yaw', label: '水平角 yaw', short: 'yaw', min: 0, max: 360, step: 1 },
    { key: 'pitch', label: '俯仰 pitch', short: 'pitch', min: -60, max: 60, step: 1 },
  ]
  if (props.compact) return base
  base.push(
    { key: 'dist', label: '距离 distance', short: 'dist', min: 200, max: 1500, step: 20 },
    { key: 'zoom', label: '缩放 zoom', short: 'zoom', min: 0.5, max: 2, step: 0.1 },
    { key: 'panX', label: '水平平移 panX', short: 'panX', min: -300, max: 300, step: 10 },
    { key: 'panY', label: '垂直平移 panY', short: 'panY', min: -200, max: 200, step: 10 },
  )
  return base
})
</script>

<style scoped>
.cam-controls { display: flex; flex-direction: column; gap: 6px; }
.cam-presets { display: flex; flex-wrap: wrap; gap: 6px; }
.cam-fields { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.cam-field { display: inline-flex; align-items: center; gap: 4px; }
.cam-key { font-family: monospace; color: #909399; font-size: .7rem; width: 44px; flex-shrink: 0; }
.cam-input { width: 96px; }
.cam-controls.compact .cam-field { gap: 4px; }
.cam-controls.compact .cam-input { width: 84px; }
</style>
