import { createRouter, createWebHashHistory } from 'vue-router'
import ConsoleView from './views/ConsoleView.vue'
import WizardView from './views/WizardView.vue'
import ArtifactsView from './views/ArtifactsView.vue'

// Hash routing so the Python static server needs no history fallback.
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/console' },
    { path: '/console', name: 'console', component: ConsoleView },
    { path: '/wizard', name: 'wizard', component: WizardView },
    { path: '/artifacts', name: 'artifacts', component: ArtifactsView },
  ],
})
