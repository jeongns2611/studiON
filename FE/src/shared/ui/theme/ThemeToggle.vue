<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Moon, Sun } from 'lucide-vue-next'
import { Button } from '@/shared/ui/button'

type ThemeMode = 'light' | 'dark'

const THEME_STORAGE_KEY = 'theme'
const theme = ref<ThemeMode>('light')

const isDark = computed(() => theme.value === 'dark')

function applyTheme(nextTheme: ThemeMode) {
  theme.value = nextTheme

  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', nextTheme === 'dark')
  }

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
  }
}

function resolveInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }

  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)

  if (savedTheme === 'light' || savedTheme === 'dark') {
    return savedTheme
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function toggleTheme() {
  applyTheme(isDark.value ? 'light' : 'dark')
}

onMounted(() => {
  applyTheme(resolveInitialTheme())
})
</script>

<template>
  <Button
    type="button"
    variant="outline"
    size="icon"
    :aria-label="isDark ? '라이트 모드로 전환' : '다크 모드로 전환'"
    @click="toggleTheme"
  >
    <Sun v-if="isDark" class="h-4 w-4" />
    <Moon v-else class="h-4 w-4" />
  </Button>
</template>
