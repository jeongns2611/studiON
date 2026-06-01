<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const handleClose = () => {
  emit('close')
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-[100] grid place-items-center bg-black/40 px-4 backdrop-blur-md animate-fade-in"
    @click.self="handleClose"
  >
    <div class="relative w-full max-w-sm rounded-2xl border border-white/10 bg-card p-7 shadow-2xl transition-all">      <div class="mb-6 flex flex-col items-center gap-3 text-center">
        <div class="grid h-12 w-12 place-items-center rounded-full bg-destructive/10 text-destructive shadow-neon-sm">
          <AlertCircle class="h-6 w-6" />
        </div>
        <h2 class="font-display text-xl font-extrabold tracking-tight text-foreground mt-2">
          업로드 용량 초과
        </h2>
        <p class="text-sm font-medium text-muted-foreground leading-relaxed mt-2">
          선택하신 파일의 크기가 너무 큽니다.<br/>
          <span class="text-foreground font-bold">50MB 이하</span>의 파일만 업로드할 수 있습니다.
        </p>
      </div>

      <div class="flex justify-center mt-2">
        <button
          type="button"
          class="inline-flex min-w-[120px] items-center justify-center rounded-full bg-primary px-6 py-2.5 text-base font-bold text-primary-foreground transition hover:shadow-neon"
          @click="emit('close')"
        >
          확인
        </button>
      </div>
    </div>
  </div>
</template>
