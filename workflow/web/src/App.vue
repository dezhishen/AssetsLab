<script setup>
import { ref, onMounted, computed } from 'vue'
import { mode, setMode, initTheme } from './theme'

// Version info is written into dist/version.json by the CI build (commit,
// branch, build time). Served as a plain static file by the Python server.
const version = ref(null)
onMounted(async () => {
  initTheme()
  try {
    const r = await fetch('version.json')
    if (r.ok) version.value = await r.json()
  } catch (e) { /* version.json absent in dev */ }
})

const modeLabel = computed(() => ({ light: '日间', dark: '夜间', system: '跟随系统' })[mode.value])
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-20 dark:border-slate-800 dark:bg-slate-900/60">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
        <span class="font-semibold text-lg">AssetsLab 工作流</span>
        <nav class="flex gap-2">
          <router-link to="/console" class="px-3 py-1.5 rounded-lg text-sm hover:bg-slate-100 dark:hover:bg-slate-800" active-class="bg-slate-200 text-cyan-600 dark:bg-slate-800 dark:text-cyan-300">控制台</router-link>
          <router-link to="/wizard" class="px-3 py-1.5 rounded-lg text-sm hover:bg-slate-100 dark:hover:bg-slate-800" active-class="bg-slate-200 text-cyan-600 dark:bg-slate-800 dark:text-cyan-300">流程向导</router-link>
        </nav>
        <el-dropdown trigger="click" @command="setMode" class="ml-auto">
          <button class="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
            <el-icon v-if="mode === 'light'"><Sunny /></el-icon>
            <el-icon v-else-if="mode === 'dark'"><Moon /></el-icon>
            <el-icon v-else><Monitor /></el-icon>
            <span>{{ modeLabel }}</span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="light"><el-icon><Sunny /></el-icon>日间</el-dropdown-item>
              <el-dropdown-item command="dark"><el-icon><Moon /></el-icon>夜间</el-dropdown-item>
              <el-dropdown-item command="system"><el-icon><Monitor /></el-icon>跟随系统</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
      <router-view />
    </main>
    <footer class="border-t border-slate-200 py-3 dark:border-slate-800">
      <div class="max-w-7xl mx-auto px-4 flex items-center justify-between text-xs text-slate-600">
        <span>AssetsLab Workflow</span>
        <span v-if="version">v{{ version.package_version }} · {{ version.commit?.slice(0, 7) }} · {{ version.branch }} · {{ version.build_time }}</span>
      </div>
    </footer>
  </div>
</template>

