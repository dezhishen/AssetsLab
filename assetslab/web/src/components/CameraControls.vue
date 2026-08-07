<template>
  <div class="cam-controls" :class="{ compact }">
    <!-- 常驻：快捷视角按钮（轨道相机：一个点 → 看模型） -->
    <div class="cam-presets">
      <el-button v-for="p in presets" :key="p.label" size="small" text
                 :type="activePreset === p.label ? 'primary' : ''"
                 @click="applyPreset(p)">{{ p.label }}</el-button>
    </div>
    <!-- 常驻：相机设置按钮 → 弹出细调面板 -->
    <el-popover placement="bottom-end" :width="300" trigger="click" popper-class="cam-popover"
                :visible="panelOpen" @update:visible="panelOpen = $event">
      <template #reference>
        <el-button size="small" icon="Setting" :type="panelOpen ? 'primary' : ''">相机</el-button>
      </template>
      <div class="cam-panel">
        <div class="cam-panel-head">
          <span class="cam-panel-title">相机设置</span>
          <el-button size="small" text type="primary" @click="reset" icon="RefreshLeft">重置</el-button>
        </div>
        <div class="cam-row" v-for="item in items" :key="item.key">
          <span class="cam-label">{{ item.label }}</span>
          <el-slider class="cam-slider" :min="item.min" :max="item.max" :step="item.step"
                     :model-value="cam[item.key]" @update:model-value="set(item.key, $event)" />
          <span class="cam-val">{{ fmt(item, cam[item.key]) }}</span>
        </div>
        <div class="cam-tip">💡 直接拖拽预览图即可旋转视角</div>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

/**
 * 3D 相机控制（轨道相机：绕模型中心旋转，从一个空间点看模型）。
 * - 常驻：快捷视角按钮（正面/侧面/背面/45°/俯视/微仰）
 * - 面板：yaw/pitch/dist/zoom/pan 细调 + 重置（隐藏收纳，不常驻）
 * - 配合预览图拖拽旋转（见 useOrbitDrag）
 * v-model 绑定相机状态 { yaw, pitch, dist, zoom, panX, panY }。
 */
const props = defineProps({
  modelValue: { type: Object, required: true },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const panelOpen = ref(false)
const cam = computed(() => props.modelValue)
const set = (key, val) => emit('update:modelValue', { ...props.modelValue, [key]: val })

const DEFAULT_CAM = { yaw: 30, pitch: 12, dist: 600, zoom: 1, panX: 0, panY: 0 }
function reset() { emit('update:modelValue', { ...DEFAULT_CAM }) }

const presets = [
  { label: '正面', yaw: 0, pitch: 0 },
  { label: '侧面', yaw: 90, pitch: 0 },
  { label: '背面', yaw: 180, pitch: 0 },
  { label: '斜侧', yaw: 45, pitch: 10 },
  { label: '俯视', yaw: 30, pitch: 30 },
  { label: '微仰', yaw: 30, pitch: -15 },
]
const applyPreset = (p) => emit('update:modelValue', { ...props.modelValue, yaw: p.yaw, pitch: p.pitch })

const activePreset = computed(() => {
  const p = presets.find(x => x.yaw === cam.value.yaw && x.pitch === cam.value.pitch)
  return p ? p.label : ''
})

const items = computed(() => {
  const base = [
    { key: 'yaw', label: '水平角', unit: '°', min: 0, max: 360, step: 1 },
    { key: 'pitch', label: '俯仰角', unit: '°', min: -60, max: 60, step: 1 },
    { key: 'dist', label: '距离', unit: '', min: 200, max: 1500, step: 20 },
  ]
  if (props.compact) return base
  base.push(
    { key: 'zoom', label: '缩放', unit: '×', min: 0.5, max: 2, step: 0.05 },
    { key: 'panX', label: '平移 X', unit: '', min: -300, max: 300, step: 10 },
    { key: 'panY', label: '平移 Y', unit: '', min: -200, max: 200, step: 10 },
  )
  return base
})

const fmt = (item, v) => (typeof v === 'number' ? Math.round(v * 100) / 100 : v) + item.unit
</script>

<style scoped>
.cam-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cam-presets { display: flex; flex-wrap: wrap; gap: 2px; }
.cam-panel { display: flex; flex-direction: column; gap: 6px; }
.cam-panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.cam-panel-title { font-weight: 600; color: #303133; font-size: .9rem; }
.cam-row { display: flex; align-items: center; gap: 8px; }
.cam-label { width: 52px; flex-shrink: 0; color: #606266; font-size: .8rem; }
.cam-slider { flex: 1; }
.cam-val { width: 56px; text-align: right; font-family: monospace; color: #606266; font-size: .75rem; }
.cam-tip { font-size: .75rem; color: #909399; margin-top: 4px; }
</style>
