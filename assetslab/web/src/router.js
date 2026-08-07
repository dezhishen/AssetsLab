import { createRouter, createWebHashHistory } from 'vue-router'
import SpeciesView from './views/SpeciesView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/species' },
    { path: '/species', name: 'species', component: SpeciesView },
  ],
})
