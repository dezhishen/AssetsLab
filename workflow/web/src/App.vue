<script setup>
import { ref, onMounted } from 'vue'

// Version info is written into dist/version.json by the CI build (commit,
// branch, build time). Served as a plain static file by the Python server.
const version = ref(null)
onMounted(async () => {
  try {
    const r = await fetch('version.json')
    if (r.ok) version.value = await r.json()
  } catch (e) { /* version.json absent in dev */ }
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-20">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
        <span class="font-semibold text-lg">AssetsLab 工作流</span>
        <nav class="flex gap-2">
          <router-link to="/console" class="px-3 py-1.5 rounded-lg text-sm hover:bg-slate-800" active-class="bg-slate-800 text-cyan-300">控制台</router-link>
          <router-link to="/wizard" class="px-3 py-1.5 rounded-lg text-sm hover:bg-slate-800" active-class="bg-slate-800 text-cyan-300">流程向导</router-link>
        </nav>
        <span class="ml-auto text-xs text-slate-500">CLI 与 Web 共享同一 run/workflows state</span>
      </div>
    </header>
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
      <router-view />
    </main>
    <footer class="border-t border-slate-800 py-3">
      <div class="max-w-7xl mx-auto px-4 flex items-center justify-between text-xs text-slate-600">
        <span>AssetsLab Workflow</span>
        <span v-if="version">v{{ version.package_version }} · {{ version.commit?.slice(0, 7) }} · {{ version.branch }} · {{ version.build_time }}</span>
      </div>
    </footer>
  </div>
</template>

