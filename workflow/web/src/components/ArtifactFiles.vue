<script setup>
// Shared renderer for a list of exported artifact files (image thumbnails +
// view/download links). Used by the Artifacts page and the Wizard's artifact
// panel. Files point at /dist/<workflow_id>/... served by the Python server.
defineProps({ files: { type: Array, default: () => [] } })

const isImage = (p) => /(\.png|\.gif|\.jpe?g|\.webp)$/i.test(p)

function fmtSize(n) {
  if (n == null || n === '') return ''
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(2)} MB`
}
</script>

<template>
  <div v-if="!files.length" class="text-xs text-slate-500 py-4 text-center">
    （该实例暂无导出制品，运行「导出 Godot 制品」步骤后生成）
  </div>
  <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
    <div v-for="f in files" :key="f.path" class="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 p-2 flex flex-col gap-1.5">
      <a :href="f.url" target="_blank" rel="noopener" class="block">
        <img v-if="isImage(f.path)" :src="f.url" loading="lazy"
             class="w-full h-24 object-contain image-render-pixel rounded border border-slate-200 dark:border-slate-700" />
        <div v-else class="h-24 flex items-center justify-center text-xs text-slate-500 bg-slate-100 dark:bg-slate-900 rounded font-mono break-all p-1 overflow-hidden">
          {{ f.name }}
        </div>
      </a>
      <div class="text-xs truncate" :title="f.path">{{ f.name }}</div>
      <div class="text-[10px] text-slate-500 flex items-center justify-between gap-1">
        <span class="truncate">{{ fmtSize(f.size) }}</span>
        <span class="flex gap-1.5 shrink-0">
          <a :href="f.url" target="_blank" rel="noopener" class="text-cyan-600 hover:underline dark:text-cyan-300" title="新标签查看">查看</a>
          <a :href="`${f.url}?download=1`" download class="text-cyan-600 hover:underline dark:text-cyan-300" title="下载">下载</a>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-render-pixel { image-rendering: pixelated; }
</style>
