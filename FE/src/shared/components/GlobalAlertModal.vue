<script setup lang="ts">
import { useAlertStore } from '@/shared/stores/useAlertStore'

const alertStore = useAlertStore()

function getIconData(type: string) {
  const greyTheme = { color: 'text-gray-400', bg: 'bg-gray-400/20', border: 'border-gray-400/30' }
  switch (type) {
    case 'success':
      return { icon: 'check_circle', ...greyTheme }
    case 'error':
      return { icon: 'error', ...greyTheme }
    case 'warning':
      return { icon: 'warning', ...greyTheme }
    case 'info':
    default:
      return { icon: 'info', ...greyTheme }
  }
}
</script>

<template>
  <div v-if="alertStore.isOpen" class="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" @click.self="alertStore.closeAlert">
    <div class="bg-[#1c1b1b] border border-white/10 rounded-2xl w-full max-w-sm shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col items-center text-center p-8">
      
      <!-- Icon -->
      <div 
        class="w-16 h-16 rounded-full flex items-center justify-center mb-5 border relative"
        :class="[getIconData(alertStore.alertType).bg, getIconData(alertStore.alertType).border]"
      >
        <span 
          class="material-symbols-outlined text-[32px]" 
          :class="getIconData(alertStore.alertType).color"
          style="font-variation-settings: 'FILL' 1;"
        >
          {{ getIconData(alertStore.alertType).icon }}
        </span>
      </div>

      <!-- Message -->
      <p class="text-[#e5e2e1] text-[16px] font-medium leading-relaxed mb-8 whitespace-pre-line break-keep">
        {{ alertStore.message }}
      </p>

      <!-- Button -->
      <button 
        @click="alertStore.closeAlert"
        class="w-full bg-[#3d3d3d] text-[#e5e2e1] font-bold text-[16px] py-3 rounded-xl hover:bg-[#4d4d4d] hover:shadow-[0_0_15px_rgba(255,255,255,0.1)] transition-all focus:outline-none focus:ring-2 focus:ring-white/20"
      >
        확인
      </button>
    </div>
  </div>
</template>
