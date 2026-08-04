<script setup>
import { ref, onMounted } from 'vue'
import { workflowApi } from '../api'
import ArtifactFiles from '../components/ArtifactFiles.vue'

const items = ref([])
const loading = ref(false)
const open = ref({})

function fmtSize(n) {
  if (n == null || n === '') return ''
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(2)} MB`
}

async function load() {
  loading.value = true
  try {
    const d = await workflowApi.artifacts().catch(() => ({ artifacts: [] }))
    items.value = d.artifacts || []
    if (items.value.length && !Object.keys(open.value).length) {
      open.value = { [items.value[0].workflow_id]: true }
    }
  } finally { loading.value = false }
}
function totalSize(files) { return files.reduce((s, f) => s + (f.size || 0), 0) }
onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-lg font-semibold m-0">导出制品 <span class="text-xs text-slate-500 font-normal">dist/&lt;实例&gt;/ · 共 {{ items.length }} 个实例</span></h2>
        <el-button :loading="loading" @click="load">⟳ 刷新</el-button>
      </div>
    </div>

    <div v-if="!items.length && !loading" class="rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60 p-8 text-center text-slate-500">
      暂无导出制品。在流程向导运行「导出 Godot 制品」步骤后，制品会出现在这里，可查看与下载。
    </div>

    <el-collapse v-model="open" v-for="g in items" :key="g.workflow_id"
                 class="rounded-lg border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60">
      <el-collapse-item :name="g.workflow_id">
        <template #title>
          <div class="flex items-center gap-3 text-sm">
            <span class="font-medium">{{ g.workflow_id }}</span>
            <span class="text-xs text-slate-500">{{ g.files.length }} 个文件 · {{ fmtSize(totalSize(g.files)) }}</span>
          </div>
        </template>
        <ArtifactFiles :files="g.files" />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>
