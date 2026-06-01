<script setup lang="ts">
const emit = defineEmits<{
  browse: []
}>()

function handleBrowseClick() {
  emit('browse')
}
</script>

<template>
  <div
    class="pointer-events-none absolute left-[288px] right-0 top-[38px] z-[60] h-[94px] px-20"
  >
    <div
      class="flex h-full items-center justify-center rounded-md border border-dashed border-orange-400/45 bg-orange-400/[0.025]"
    >
      <div
        class="pointer-events-none flex h-[58px] min-w-[420px] items-center justify-center gap-3 rounded-lg border border-dashed border-orange-300/35 bg-[#1b1b1b]/80 px-6 text-sm text-zinc-300 shadow-[0_8px_24px_rgba(0,0,0,0.24)] backdrop-blur-sm"
      >
        <span class="font-medium text-zinc-200">
          파일을 드래그 앤 드롭하거나
        </span>

        <button
          type="button"
          class="pointer-events-auto rounded-md border border-orange-400/60 bg-orange-400/10 px-3 py-1.5 text-xs font-semibold text-orange-300 transition hover:bg-orange-400/20 hover:text-orange-200"
          @click.stop="handleBrowseClick"
        >
          파일 직접 찾기
        </button>

        <span class="text-zinc-500">
          로 오디오를 등록해 주세요
        </span>
      </div>
    </div>
  </div>
</template>