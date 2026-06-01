<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronRight, Compass, X } from 'lucide-vue-next'

interface GuideStep {
  selector: string
  title: string
  description: string
}

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

const props = defineProps<{
  steps: GuideStep[]
  open: boolean
}>()

const emit = defineEmits<{
  close: [doNotShowAgain: boolean]
}>()

const PADDING = 10
const TOOLTIP_WIDTH = 420
const TOOLTIP_HEIGHT = 220

const currentIndex = ref(0)
const targetRect = ref<Rect | null>(null)

let measureTimer: number | null = null

const currentStep = computed(() => props.steps[currentIndex.value])
const isLastStep = computed(() => currentIndex.value === props.steps.length - 1)

const doNotShowAgain = ref(false)

const tooltipStyle = computed(() => {
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  if (!targetRect.value) {
    return {
      top: `${viewportHeight / 2 - TOOLTIP_HEIGHT / 2}px`,
      left: `${viewportWidth / 2 - TOOLTIP_WIDTH / 2}px`,
    }
  }

  const rect = targetRect.value

  const below = rect.top + rect.height + 12
  const above = rect.top - TOOLTIP_HEIGHT - 12

  const top =
    below + TOOLTIP_HEIGHT < viewportHeight
      ? below
      : Math.max(12, above)

  const left = Math.min(
    Math.max(12, rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2),
    viewportWidth - TOOLTIP_WIDTH - 12,
  )

  return {
    top: `${top}px`,
    left: `${left}px`,
  }
})

function measureTarget() {
  if (!props.open) return

  const step = currentStep.value
  if (!step) {
    targetRect.value = null
    return
  }

  const element = document.querySelector(step.selector) as HTMLElement | null

  if (!element) {
    targetRect.value = null
    return
  }

  element.scrollIntoView({
    block: 'center',
    behavior: 'smooth',
  })

  const rect = element.getBoundingClientRect()

  targetRect.value = {
    top: rect.top - PADDING,
    left: rect.left - PADDING,
    width: rect.width + PADDING * 2,
    height: rect.height + PADDING * 2,
  }
}

async function startMeasure() {
  await nextTick()

  measureTarget()

  if (measureTimer) {
    window.clearTimeout(measureTimer)
  }

  measureTimer = window.setTimeout(() => {
    measureTarget()
  }, 80)

  window.addEventListener('resize', measureTarget)
  window.addEventListener('scroll', measureTarget, true)
}

function stopMeasure() {
  if (measureTimer) {
    window.clearTimeout(measureTimer)
    measureTimer = null
  }

  window.removeEventListener('resize', measureTarget)
  window.removeEventListener('scroll', measureTarget, true)
}

function closeGuide() {
  emit('close', doNotShowAgain.value)
}

function goNext() {
  if (isLastStep.value) {
    closeGuide()
    return
  }

  currentIndex.value += 1
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
        currentIndex.value = 0
        doNotShowAgain.value = false
        await startMeasure()
    } else {
      currentIndex.value = 0
      targetRect.value = null
      stopMeasure()
    }
  },
)

watch(currentIndex, async () => {
  if (!props.open) return
  await startMeasure()
})

onBeforeUnmount(() => {
  stopMeasure()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && currentStep"
      class="fixed inset-0 z-[9999]"
      role="dialog"
      aria-modal="true"
    >
      <!-- SVG mask overlay -->
      <svg class="absolute inset-0 h-full w-full">
        <defs>
          <mask id="project-guide-mask">
            <rect width="100%" height="100%" fill="white" />

            <rect
              v-if="targetRect"
              :x="targetRect.left"
              :y="targetRect.top"
              :width="targetRect.width"
              :height="targetRect.height"
              rx="12"
              ry="12"
              fill="black"
            />
          </mask>
        </defs>

        <rect
          width="100%"
          height="100%"
          fill="rgba(10, 10, 10, 0.82)"
          mask="url(#project-guide-mask)"
        />
      </svg>

      <!-- Highlight ring -->
      <div
        v-if="targetRect"
        class="pointer-events-none absolute rounded-xl ring-2 ring-[#FF3DCB] shadow-[0_0_30px_-2px_rgba(255,61,203,0.9)] transition-all duration-300"
        :style="{
          top: `${targetRect.top}px`,
          left: `${targetRect.left}px`,
          width: `${targetRect.width}px`,
          height: `${targetRect.height}px`,
        }"
      />

      <!-- Tooltip -->
      <div
        class="absolute w-[420px] rounded-2xl border border-[#FF3DCB]/40 bg-gradient-to-br from-zinc-950/95 to-zinc-900/95 p-6 text-white shadow-[0_15px_50px_-10px_rgba(255,61,203,0.6)] backdrop-blur-xl transition-all duration-300"
        :style="tooltipStyle"
      >
        <div class="mb-4 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="grid h-8 w-8 place-items-center rounded-full bg-[#FF3DCB]/20 text-[#FF3DCB] ring-1 ring-[#FF3DCB]/50">
              <Compass class="h-4 w-4" />
            </span>

            <span class="font-mono text-xs font-bold uppercase tracking-[0.2em] text-[#FF3DCB]/80">
              STEP {{ currentIndex + 1 }} OF {{ steps.length }}
            </span>
          </div>

          <button
            type="button"
            aria-label="가이드 닫기"
            class="grid h-7 w-7 place-items-center rounded-md text-zinc-400 transition hover:bg-white/10 hover:text-white"
            @click="closeGuide"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <h3 class="mb-2 text-lg font-bold tracking-tight text-white">
          {{ currentStep.title }}
        </h3>

        <p class="mb-6 text-[15px] leading-relaxed text-zinc-300">
          {{ currentStep.description }}
        </p>

        <label class="mb-4 flex cursor-pointer items-center gap-2 text-xs text-zinc-400">
            <input
                v-model="doNotShowAgain"
                type="checkbox"
                class="h-3.5 w-3.5 rounded border-zinc-600 bg-zinc-900 accent-[#FF3DCB]"
            />
            <span>다시 보지 않기</span>
            </label>

        <div class="flex items-center justify-between gap-2">
          <button
            type="button"
            class="font-mono text-[10px] uppercase tracking-widest text-zinc-400 transition hover:text-white"
            @click="closeGuide"
          >
            건너뛰기
          </button>

          <div class="flex items-center gap-1">
            <span
              v-for="(_, index) in steps"
              :key="index"
              class="h-1.5 rounded-full transition-all"
              :class="
                index === currentIndex
                  ? 'w-6 bg-[#FF3DCB]'
                  : 'w-1.5 bg-zinc-700'
              "
            />
          </div>

          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-full border border-[#FF3DCB]/50 bg-[#FF3DCB]/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#FF3DCB] transition hover:bg-[#FF3DCB]/20"
            @click="goNext"
          >
            {{ isLastStep ? '시작하기' : '다음' }}
            <ChevronRight
              v-if="!isLastStep"
              class="h-3 w-3"
            />
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>