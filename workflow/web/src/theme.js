/* Theme switcher: light / dark / system.
   Applies Tailwind's `dark` class on <html> (darkMode: 'class') and keeps the
   choice in localStorage. Element Plus switches its own theme via html.dark
   (element-plus dark css-vars imported in main.js). */

import { ref, watch } from 'vue'

const STORAGE_KEY = 'assetslab-theme'
const mode = ref(localStorage.getItem(STORAGE_KEY) || 'system')

let media = null

function isDark() {
  return mode.value === 'dark' || (mode.value === 'system' && !!media && media.matches)
}

function apply() {
  document.documentElement.classList.toggle('dark', isDark())
  // Color-scheme so native scrollbars / form controls follow the theme.
  document.documentElement.style.colorScheme = isDark() ? 'dark' : 'light'
}

function setMode(m) {
  mode.value = m
  localStorage.setItem(STORAGE_KEY, m)
  apply()
}

function initTheme() {
  if (typeof window === 'undefined') return
  media = window.matchMedia('(prefers-color-scheme: dark)')
  apply()
  // Follow OS changes while in "system" mode.
  media.addEventListener('change', () => { if (mode.value === 'system') apply() })
}

watch(mode, () => {
  // Also react when mode ref changes from anywhere (e.g. initial load).
  if (document.documentElement) apply()
})

export { mode, setMode, initTheme }
