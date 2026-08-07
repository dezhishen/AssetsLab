import { ref, onBeforeUnmount } from 'vue'

/**
 * 轨道相机拖拽旋转（3D 视角直观调整）。
 *
 * 用法：预览图（或任意元素）上按住左键拖动 → 水平拖动旋转 yaw、垂直拖动调整 pitch。
 * 视角变化通过 setCam 回调交给父级（通常配合 watch cam → debounce 重渲染）。
 *
 * @param {Object} opts
 * @param {() => Object} opts.getCam   读取当前相机 {yaw, pitch, ...}
 * @param {(cam: Object) => void} opts.setCam  更新相机
 * @param {(e: MouseEvent) => void} [opts.onDragStart]
 * @param {(e: MouseEvent) => void} [opts.onDragEnd]
 * @returns {{ onMouseDown: (e: MouseEvent) => void, isDragging: import('vue').Ref<boolean> }}
 */
export function useOrbitDrag({ getCam, setCam, onDragStart, onDragEnd }) {
  const dragging = ref(false)
  let sx = 0, sy = 0, syaw = 0, spitch = 0

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

  function onMouseMove(e) {
    if (!dragging.value) return
    const dx = e.clientX - sx
    const dy = e.clientY - sy
    const yaw = (((syaw + dx * 0.5) % 360) + 360) % 360
    const pitch = clamp(spitch + dy * 0.5, -60, 60)
    setCam({ ...getCam(), yaw, pitch })
  }

  function end(e) {
    if (!dragging.value) return
    dragging.value = false
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', end)
    document.body.style.cursor = ''
    if (onDragEnd) onDragEnd(e)
  }

  function onMouseDown(e) {
    if (e.button !== 0) return
    dragging.value = true
    sx = e.clientX; sy = e.clientY
    syaw = getCam().yaw ?? 0
    spitch = getCam().pitch ?? 0
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', end)
    document.body.style.cursor = 'grabbing'
    e.preventDefault()
    if (onDragStart) onDragStart(e)
  }

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', end)
  })

  return { onMouseDown, isDragging: dragging }
}
