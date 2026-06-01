<script setup lang="ts">
interface Props {
  sizeClass?: string
  trackClass?: string
  thicknessClass?: string
}

withDefaults(defineProps<Props>(), {
  sizeClass: 'h-3 w-3',
  trackClass: 'border-white/20',
  thicknessClass: 'border-[2px]',
})
</script>

<template>
  <span
    aria-hidden="true"
    class="spinner-gradient relative inline-block animate-spin rounded-full border-transparent"
    :class="[sizeClass, trackClass, thicknessClass]"
  />
</template>

<style scoped>
.spinner-gradient {
  background:
    linear-gradient(rgba(255, 61, 203, 0.18), rgba(255, 61, 203, 0.18)) padding-box,
    conic-gradient(
      from 180deg,
      rgba(255, 61, 203, 0.92) 0deg,
      rgba(255, 110, 222, 1) 90deg,
      rgba(255, 214, 246, 1) 160deg,
      rgba(255, 61, 203, 1) 240deg,
      rgba(255, 145, 231, 1) 320deg,
      rgba(255, 61, 203, 0.92) 360deg
    ) border-box;
  box-shadow:
    0 0 12px rgba(255, 61, 203, 0.42),
    0 0 24px rgba(255, 61, 203, 0.22);
}
</style>
