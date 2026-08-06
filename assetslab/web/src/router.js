import { createRouter, createWebHashHistory } from 'vue-router'
import SpeciesView from './views/SpeciesView.vue'
import PresetView from './views/PresetView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/species' },
    { path: '/species', name: 'species', component: SpeciesView },
    { path: '/presets', name: 'presets', component: PresetView },
  ],
})
