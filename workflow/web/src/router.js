import { createRouter, createWebHashHistory } from 'vue-router'
import ConsoleView from './views/ConsoleView.vue'
import WizardView from './views/WizardView.vue'

// Hash routing so the Python static server needs no history fallback.
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/console' },
    { path: '/console', name: 'console', component: ConsoleView },
    { path: '/wizard', name: 'wizard', component: WizardView },
  ],
})
