<script setup lang="ts">
import { ref, watch, computed, onBeforeUnmount, inject, type Ref, type StyleValue } from 'vue'
import { ChevronUp, ChevronDown, Sparkles, Minus } from 'lucide-vue-next'
import { useTrackStore } from '../store/useTrackStore'

const trackStore = useTrackStore()

const props = defineProps<{
  conflict: {
    id?: string | number
    kind: 'BAND_OVERLAP' | 'CLIPPING' | 'HARSHNESS'
    startPercent: number
    endPercent: number
    startPx: number
    endPx: number
    startMs: number
    endMs: number
    barStart: number
    barEnd: number
    title: string
    summary: string
    bullets: string[]
    recommendedGainReductionDb: number | null
    targetTrackId?: string | number | null
  }
  bubblePosition: {
    mode: 'absolute'
    top: number
  }

  isClippingApplied?: boolean
  clippingAppliedInfo?: {
    reductionDb: number
    inputGainDb: number
    ceilingDbfs: number
  } | null
}>()

const emit = defineEmits<{
  open: []
  applyClipping: []
  dismissClipping: []
}>()

// 상위에서 주입된 활성 AI 분석 ID와 설명창 상태 동기화
const activeAiAnalysisId = inject<Ref<string | number | null>>('activeAiAnalysisId', ref(null))
const open = ref(false)

watch(
  () => activeAiAnalysisId.value,
  (newId) => {
    if (newId === props.conflict.id) {
      open.value = true
    } else {
      open.value = false
    }
  },
  { immediate: true }
)

const buttonRef = ref<HTMLElement | null>(null)
const popupStyle = ref<{ top: string; left: string; transform?: string }>({ top: '0px', left: '0px' })
let rafId: number | null = null

// 드래그 상태 관리
const isDragged = ref(false)
const isDragging = ref(false)
const dragOffset = { x: 0, y: 0 }

const updatePopupPosition = () => {
  if (!open.value || !buttonRef.value) return
  if (isDragged.value) return // 사용자가 드래그한 경우 위치 추적 중단
  
  const rect = buttonRef.value.getBoundingClientRect()
  
  // 기본적으로 버튼 바로 아래(top + height + margin)에 배치
  let top = rect.bottom + 10
  let left = rect.left + rect.width / 2 // 중앙 정렬 기준점
  let transform = 'translateX(-50%)'

  // 왼쪽 화면 밖으로 나가지 않도록 조정 (트랙 헤더 224px 고려)
  if (left < 256 + 180) { // 180은 팝업 넓이(360px)의 절반
    left = rect.left
    transform = 'translateX(-16px)'
  }

  popupStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    transform
  }
  
  if (!isDragged.value) {
    rafId = requestAnimationFrame(updatePopupPosition)
  }
}

const onDrag = (e: PointerEvent) => {
  if (!isDragging.value) return
  e.preventDefault()
  
  let newTop = e.clientY - dragOffset.y
  let newLeft = e.clientX - dragOffset.x

  // 화면 밖으로 나가지 않도록 (특히 위쪽으로 가서 헤더를 못 잡게 되는 상황 방지)
  if (newTop < 0) newTop = 0 // 상단 이탈 방지
  if (newTop > window.innerHeight - 40) newTop = window.innerHeight - 40 // 하단 이탈 방지
  
  // 좌우 이탈 방지 (팝업 가로 크기 460px 기준, 최소 50px은 화면에 남도록)
  if (newLeft < -410) newLeft = -410
  if (newLeft > window.innerWidth - 50) newLeft = window.innerWidth - 50

  popupStyle.value = {
    top: `${newTop}px`,
    left: `${newLeft}px`,
    transform: 'none' // 드래그 시 중앙 정렬 해제
  }
}

const endDrag = () => {
  isDragging.value = false
  window.removeEventListener('pointermove', onDrag)
  window.removeEventListener('pointerup', endDrag)
}

const startDrag = (e: PointerEvent) => {
  if (!open.value) return
  isDragged.value = true
  isDragging.value = true

  // 기존 팝업 위치 파싱
  const currentTop = parseFloat(popupStyle.value.top) || 0
  const currentLeft = parseFloat(popupStyle.value.left) || 0
  
  // 만약 transform(translateX(-50%))가 적용된 상태라면, 실제 좌상단 X좌표를 계산하여 보정해야 함
  let adjustedLeft = currentLeft
  if (popupStyle.value.transform === 'translateX(-50%)') {
    adjustedLeft -= 230 // 팝업 넓이(460px)의 절반
  } else if (popupStyle.value.transform === 'translateX(-16px)') {
    adjustedLeft -= 16
  }

  dragOffset.x = e.clientX - adjustedLeft
  dragOffset.y = e.clientY - currentTop

  // 즉시 보정된 위치 적용 (포인터가 튀지 않도록)
  popupStyle.value = {
    top: `${currentTop}px`,
    left: `${adjustedLeft}px`,
    transform: 'none'
  }

  window.addEventListener('pointermove', onDrag)
  window.addEventListener('pointerup', endDrag)
}

watch(open, (newVal) => {
  if (newVal) {
    isDragged.value = false // 다시 열릴 때 초기 위치로 리셋
    isDragging.value = false
    updatePopupPosition()
  } else {
    if (rafId) cancelAnimationFrame(rafId)
    endDrag() // 안전을 위해 드래그 종료
  }
})

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId)
})

const close = () => {
  // 닫을 때 전역 활성 AI 분석 ID도 해제하여 일관성 유지
  if (activeAiAnalysisId && activeAiAnalysisId.value === props.conflict.id) {
    activeAiAnalysisId.value = null
  } else {
    open.value = false
  }
}

const isMinimized = ref(false)
const toggleMinimize = () => {
  isMinimized.value = !isMinimized.value
}

const toggleOpen = () => {
  if (open.value) {
    close()
  } else {
    emit('open')
    if (activeAiAnalysisId) {
      activeAiAnalysisId.value = props.conflict.id ?? null
    }
  }
}

const issueLabel = () => {
  if (props.conflict.kind === 'BAND_OVERLAP') return '대역 중복'
  if (props.conflict.kind === 'CLIPPING') return '클리핑'
  return '하쉬니스'
}


const TIMELINE_TRACK_HEADER_WIDTH = 224

const dynamicStartPx = computed(() => {
  // 실제 에러 발생 시작점(밀리초) 기준으로 정확히 버튼을 위치시킴
  const startBarFloat = props.conflict.startMs / (trackStore.secondsPerBar * 1000)
  return TIMELINE_TRACK_HEADER_WIDTH + (startBarFloat * trackStore.pixelPerBar)
})

const trackIndex = computed(() => {
  if (!props.conflict.targetTrackId) return 0
  const index = trackStore.trackList.findIndex(t => String(t.trackId) === String(props.conflict.targetTrackId))
  return index >= 0 ? index : 0
})

const formatBarBeat = (ms: number) => {
  // 백엔드/AI에서 넘어온 정확한 밀리초(ms) 데이터를 기반으로 마디(Bar)와 박자(Beat)를 계산합니다.
  const startBarFloat = ms / (trackStore.secondsPerBar * 1000)
  const numerator = trackStore.projectInfo.timeSigNumerator || 4
  const bar = Math.floor(startBarFloat) + 1
  const beat = Math.floor((startBarFloat - Math.floor(startBarFloat)) * numerator) + 1
  return `${String(bar).padStart(2, '0')}.${beat}`
}

const barLabel = computed(() => {
  const startStr = formatBarBeat(props.conflict.startMs)
  const endStr = formatBarBeat(props.conflict.endMs)
  return `${startStr} 마디 ~ ${endStr} 마디`
})

const bubbleWrapperStyle = computed<StyleValue>(() => {
  const topOffset = (trackIndex.value * 100) + 12
  return {
    position: 'absolute',
    top: `${topOffset}px`,
    left: '4px',
  }
})

const dynamicWidthPx = computed(() => {
  const startBarFloat = props.conflict.startMs / (trackStore.secondsPerBar * 1000)
  const endBarFloat = Math.max(props.conflict.endMs / (trackStore.secondsPerBar * 1000), startBarFloat + 0.25)
  return Math.max((endBarFloat - startBarFloat) * trackStore.pixelPerBar, 8)
})


</script>

<template>
  <div
    class="pointer-events-none absolute top-0 bottom-0 z-60"
    :style="{
      left: `${dynamicStartPx}px`,
      width: `${dynamicWidthPx}px`,
    }"
  >
    <div
      class="pointer-events-auto"
  :style="bubbleWrapperStyle"
  @pointerdown.stop
>
      <button
        ref="buttonRef"
        type="button"
        class="relative z-1000 grid h-8 w-8 place-items-center rounded-full bg-[conic-gradient(from_180deg,#8B5CF6,#38BDF8,#22C55E,#F59E0B,#EC4899,#8B5CF6)] shadow-lg hover:scale-105 transition-transform"
        @click="toggleOpen"
      >
        <span class="absolute h-7 w-7 rounded-full bg-[#171717]" />
        <Sparkles class="relative z-10 h-4 w-4 text-white" aria-hidden="true" />
      </button>

      <Teleport to="body">
        <div
          v-if="open"
          class="fixed z-9999 w-[460px] rounded-lg p-px shadow-2xl backdrop-blur-md"
          :style="popupStyle"
        >
          <div class="absolute inset-0 rounded-lg bg-[linear-gradient(135deg,#8B5CF6,#3B82F6,#06B6D4,#22C55E,#F59E0B,#EC4899)] opacity-80" />
        
        <div class="relative h-full w-full rounded-[7px] bg-[#171717]/95">
          <div
            class="flex items-center justify-between border-b border-white/10 px-4 py-3 rounded-t-[7px] select-none"
            :class="{ 'cursor-grab': !isDragging, 'cursor-grabbing': isDragging }"
            @pointerdown.stop="startDrag"
          >
            <div class="flex items-center gap-2 text-[11px] font-bold tracking-[0.18em] text-white">
              <span class="grid h-5 w-5 place-items-center rounded-full bg-[conic-gradient(from_180deg,#8B5CF6,#38BDF8,#22C55E,#F59E0B,#EC4899,#8B5CF6)]">
                <span class="absolute h-4 w-4 rounded-full bg-[#171717]" />
                <Sparkles class="relative z-10 h-3 w-3 text-white" aria-hidden="true" />
              </span>
              <span class="bg-[linear-gradient(90deg,#DDD6FE,#93C5FD,#67E8F9,#F9A8D4)] bg-clip-text text-transparent uppercase mt-0.5">
                AI ANALYSIS
              </span>
              <span class="ml-1 rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-white/90">
                {{ barLabel }}
              </span>
            </div>

            <div class="flex items-center gap-2">
              <span class="rounded-full border border-white/10 px-2 py-0.5 text-[10px] font-bold text-white/70">
                {{ issueLabel() }}
              </span>

              <button
                type="button"
                class="ml-2 text-sm text-white/50 hover:text-white transition"
                @click.stop="toggleMinimize"
                @pointerdown.stop
                title="최소화"
              >
                <Minus class="w-4 h-4" />
              </button>

              <button
                type="button"
                class="ml-1 text-sm text-white/50 hover:text-white transition"
                @click.stop="close"
                @pointerdown.stop
                title="닫기"
              >
                ×
              </button>
            </div>
          </div>

          <div v-show="!isMinimized" class="space-y-3 px-4 py-4">

          <p class="text-base text-white/60 break-keep">
            {{ props.conflict.summary }}
          </p>

          <ul class="space-y-2 pt-1 text-base leading-relaxed text-white/80 break-keep">
            <li
              v-for="(bullet, index) in props.conflict.bullets"
              :key="index"
              class="flex gap-2"
            >
              <span class="text-fuchsia-300 shrink-0">›</span>
              <span>{{ bullet }}</span>
            </li>
          </ul>

          <div
            v-if="props.conflict.kind === 'CLIPPING'"
            class="space-y-3 border-t border-white/10 pt-3"
          >
            <p class="text-sm leading-relaxed text-white/60 break-keep">
              마스터 트랙에서 클리핑이 감지됐어요.<br />
              AI는 약 {{ Math.abs(props.conflict.recommendedGainReductionDb ?? 0).toFixed(2) }}dB 감소를 제안합니다.
            </p>

            <div class="flex gap-2">
              <button
                type="button"
                :disabled="props.conflict.recommendedGainReductionDb == null"
                class="w-full rounded-md bg-[#FF8F1A] px-3 py-1.5 text-sm font-bold text-black hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 transition"
                @click="emit('applyClipping')"
              >
                적용하기
              </button>

              <button
                type="button"
                class="w-full rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-sm font-bold text-white/70 hover:bg-white/10 hover:text-white transition"
                @click="emit('dismissClipping')"
              >
                건너뛰기
              </button>
            </div>
          </div>

<!-- 클리핑이 아닌 다른 모든 이슈 처리 (테스트 등) -->
<div
  v-else
  class="space-y-3 pt-1"
>
  <div class="flex gap-2">
    <button
      type="button"
      class="w-full rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-sm font-bold text-white/70 hover:bg-white/10 hover:text-white transition"
      @click="emit('dismissClipping')"
    >
      무시하기
    </button>
  </div>
</div>

        </div>
      </div>
    </div>
    </Teleport>
  </div>
</div>
</template>