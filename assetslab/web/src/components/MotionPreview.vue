<template>
  <div class="motion-preview">
    <div class="mp-stage" :class="{ dragging }" @mousedown="onDragDown">
      <img v-if="current" :src="current" class="mp-img" alt="动作预览" />
      <div v-else class="preview-empty">
        <p>{{ loading ? '渲染中…' : '暂无预览帧，请先渲染动作' }}</p>
      </div>
      <span v-if="frames.length" class="mp-badge">{{ index + 1 }} / {{ frames.length }}</span>
      <span v-if="dragging" class="mp-orbit-hint">拖动旋转视角…</span>
    </div>
    <div class="mp-toolbar">
      <el-button size="small" :disabled="!frames.length" :icon="playing ? 'VideoPause' : 'VideoPlay'" @click="togglePlay">
        {{ playing ? '暂停' : '播放' }}
      </el-button>
      <el-button size="small" type="primary" :disabled="!frames.length" :loading="gifLoading" icon="Download" @click="exportGif">
        导出 GIF
      </el-button>
      <span class="mp-hint">拖拽画面旋转视角 · GIF 由后端按当前相机视角逐帧合成</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { api } from '../api.js'
import { ElMessage } from 'element-plus'
import { useOrbitDrag } from '../composables/useOrbitDrag.js'

const props = defineProps({
  /** 帧序列（PNG data URL 数组），由父级渲染后传入 */
  frames: { type: Array, default: () => [] },
  /** 播放速度（帧/秒） */
  fps: { type: Number, default: 6 },
  /** 相机参数 {yaw,pitch,dist,zoom,panX,panY}，拖拽旋转 + 导出 GIF 用 */
  cam: { type: Object, default: () => ({}) },
  /** 物种 ID（导出 GIF 需要） */
  speciesId: { type: String, default: '' },
  /** 动作 ID（导出 GIF 需要） */
  motionId: { type: String, default: '' },
  /** 渲染中状态（空帧时显示） */
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:cam'])

const index = ref(0)
const playing = ref(false)
const gifLoading = ref(false)
let timer = null

const current = computed(() => props.frames[index.value] ?? props.frames[0] ?? null)

watch(() => props.frames, () => { index.value = 0 }, { immediate: true })
watch(() => props.frames.length, (n) => { if (n === 0) stop() })

function togglePlay() {
  if (playing.value) return stop()
  if (!props.frames.length) return
  playing.value = true
  const ms = Math.max(50, Math.round(1000 / props.fps))
  timer = setInterval(() => { index.value = (index.value + 1) % props.frames.length }, ms)
}

function stop() {
  playing.value = false
  if (timer) { clearInterval(timer); timer = null }
}

// 轨道相机：拖拽预览图旋转视角（父级 watch cam 自动重渲染）
const { onMouseDown: onDragDown, isDragging } = useOrbitDrag({
  getCam: () => props.cam || {},
  setCam: (c) => emit('update:cam', c),
})
const dragging = isDragging

/** 导出 GIF：后端按当前相机视角逐帧合成，浏览器下载 */
async function exportGif() {
  if (!props.motionId || !props.speciesId) { ElMessage.warning('缺少动作信息，无法导出 GIF'); return }
  gifLoading.value = true
  try {
    const c = props.cam || {}
    const qs = `species=${encodeURIComponent(props.speciesId)}&yaw=${c.yaw ?? 0}&pitch=${c.pitch ?? 0}` +
               `&dist=${c.dist ?? 600}&zoom=${c.zoom ?? 1}&pan_x=${c.panX ?? 0}&pan_y=${c.panY ?? 0}&gif=1`
    const r = await api.renderMotion3d(props.motionId, qs)
    if (r.gif) {
      const a = document.createElement('a')
      a.href = r.gif
      a.download = `${props.motionId}.gif`
      document.body.appendChild(a)
      a.click()
      a.remove()
      ElMessage.success('GIF 已导出')
    } else {
      ElMessage.error('GIF 生成失败')
    }
  } catch (e) { ElMessage.error(e.message) }
  gifLoading.value = false
}

onBeforeUnmount(stop)
</script>

<style scoped>
.motion-preview { display: flex; flex-direction: column; gap: 10px; }
.mp-stage { position: relative; display: flex; justify-content: center; min-height: 200px;
  cursor: grab; user-select: none; }
.mp-stage.dragging { cursor: grabbing; }
.mp-img { max-width: 100%; border: 1px solid #111827; border-radius: 8px; background: #111827;
  pointer-events: none; }
.mp-badge { position: absolute; right: 8px; bottom: 8px; background: rgba(0,0,0,.65); color: #fff;
  font-size: .75rem; padding: 2px 8px; border-radius: 999px; }
.mp-orbit-hint { position: absolute; left: 50%; top: 12px; transform: translateX(-50%);
  background: rgba(0,0,0,.65); color: #fff; font-size: .75rem; padding: 3px 10px; border-radius: 999px; }
.mp-toolbar { display: flex; gap: 8px; align-items: center; }
.mp-hint { font-size: .75rem; color: #c0c4cc; }
.preview-empty { text-align: center; color: #c0c4cc; padding: 40px; border: 2px dashed #e4e7ed;
  border-radius: 8px; width: 100%; }
</style>
