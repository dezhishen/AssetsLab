<template>
  <div class="cam-controls">
    <!-- 预设视角快捷入口 -->
    <div class="cam-presets">
      <el-button v-for="p in presets" :key="p.label" size="small"
                 :type="activePreset === p.label ? 'primary' : ''"
                 @click="applyPreset(p)">{{ p.label }}</el-button>
    </div>
    <!-- 相机滑块 -->
    <div class="cam-grid" :class="{ compact }">
      <div class="cam-item" v-for="item in items" :key="item.key">
        <div class="cam-label">{{ item.label }} <span class="cam-key">{{ item.display }}</span></div>
        <el-slider :min="item.min" :max="item.max" :step="item.step"
                   :model-value="cam[item.key]" @update:model-value="set(item.key, $event)" size="small" />
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
    { key: 'yaw', label: '水平角 yaw', min: 0, max: 360, step: 1, display: `${cam.value.yaw}°` },
    { key: 'pitch', label: '俯仰 pitch', min: -60, max: 60, step: 1, display: `${cam.value.pitch}°` },
  ]
  if (props.compact) return base
  base.push(
    { key: 'dist', label: '距离 distance', min: 200, max: 1500, step: 20, display: cam.value.dist },
    { key: 'zoom', label: '缩放 zoom', min: 0.5, max: 2, step: 0.1, display: cam.value.zoom.toFixed(1) },
    { key: 'panX', label: '水平平移 panX', min: -300, max: 300, step: 10, display: cam.value.panX },
    { key: 'panY', label: '垂直平移 panY', min: -200, max: 200, step: 10, display: cam.value.panY },
  )
  return base
})
</script>

<style scoped>
.cam-presets { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.cam-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px 14px; }
.cam-grid.compact { grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
.cam-item { border: 1px solid #ebeef5; border-radius: 8px; padding: 6px 10px; background: #fafbfc; }
.cam-label { display: flex; justify-content: space-between; font-size: .78rem; color: #606266; margin-bottom: 2px; }
.cam-key { font-family: monospace; color: #409eff; font-weight: 600; }
</style>
