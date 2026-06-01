<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, inject } from 'vue'
import type { Ref } from 'vue'
import { Play, Square, Sparkles, Wand2, ChevronUp, ChevronDown } from 'lucide-vue-next'
import type { TrackUIState, TrackEqBandState } from '../types'
import type { AiAnalysisItem } from '../composables/useProjectAiWorkflow'
import EqGraph from './EqGraph.vue'
import { useTrackStore } from '../store/useTrackStore'

type AiUiMode = 'eq_ai' | 'master_trim' | 'marker_only' | null

const props = withDefaults(defineProps<{
  selectedTrack: TrackUIState | null
  aiAnalyzing: boolean
  aiAnalyzed: boolean
  aiBeforeBands: TrackEqBandState[]
  aiAfterBands: TrackEqBandState[]
  aiMarkers?: EqMarker[]
  activeAiUiMode?: AiUiMode
}>(), {
  aiMarkers: () => [],
  activeAiUiMode: null,
})

type EqMarker = {
  trackId: number | null
  centerHz?: number | null
  bandLowHz?: number | null
  bandHighHz?: number | null
}

const trackStore = useTrackStore()
const spectrumData = ref<number[]>([])
let spectrumRafId: number | null = null

const isCollapsed = ref(false)

const currentBands = computed(() => {
  return props.selectedTrack?.eq?.bands ?? []
})

const emit = defineEmits<{
  'apply-ai-eq': []
  'cancel-ai-eq': []
  'request-ai-eq-revision': [payload: {
    selectedTrackIds: number[]
    message: string
  }]
  'add-eq-band': [payload: {
    frequencyHz: number
    gainDeltaDb: number
    isAiEq?: boolean
  }]
  'update-eq-band': [payload: {
    bandOrder: number
    patch: Partial<TrackEqBandState>
    isAiEq?: boolean
  }]
  'remove-eq-band': [payload: {
    bandOrder: number
    isAiEq?: boolean
  }]
}>()

const beforeBands = computed(() => {
  return props.aiBeforeBands
})

const afterBands = computed(() => {
  return props.aiAfterBands.length > 0
    ? props.aiAfterBands
    : currentBands.value
})

const hasAiSuggestion = computed(() => {
  return props.aiAfterBands.length > 0 || props.aiMarkers.length > 0
})

const isMarkerOnlyMode = computed(() => {
  return props.activeAiUiMode === 'marker_only'
})

const hasAiEqBands = computed(() => {
  return props.aiAfterBands.length > 0
})

const shouldShowSingleEqGraph = computed(() => {
  return !props.aiAnalyzed || isMarkerOnlyMode.value
})

const shouldShowRevisionRequest = computed(() => {
  return props.activeAiUiMode === 'eq_ai' && !hasAiEqBands.value
})

const shouldShowCompareEqGraph = computed(() => {
  return props.activeAiUiMode === 'eq_ai' && hasAiEqBands.value
})

const selectedRevisionTrackIds = ref<number[]>([])
const revisionMessage = ref('')

const revisionCandidateTracks = computed(() => {
  const allowedTrackIds = new Set(activeAiAnalysis.value?.involvedTrackIds ?? [])

  if (allowedTrackIds.size === 0) {
    return []
  }

  return trackStore.trackList.filter(track =>
    allowedTrackIds.has(Number(track.trackId)),
  )
})

const hasRevisionCandidates = computed(() => {
  return revisionCandidateTracks.value.length > 0
})

function toggleRevisionTrack(trackId: number) {
  if (selectedRevisionTrackIds.value.includes(trackId)) {
    selectedRevisionTrackIds.value = selectedRevisionTrackIds.value.filter(id => id !== trackId)
    return
  }

  selectedRevisionTrackIds.value = [
    ...selectedRevisionTrackIds.value,
    trackId,
  ]
}

function requestAiRevision() {
  emit('request-ai-eq-revision', {
    selectedTrackIds: selectedRevisionTrackIds.value,
    message: revisionMessage.value.trim(),
  })
}

const freqLabels = ['20', '50', '100', '200', '500', '1K', '2K', '5K', '10K', '20K']
const dbLabels = ['+12', '+8', '+6', '+3', '0', '-3', '-6', '-9', '-12']

function hasMeaningfulSpectrum(values: number[]) {
  const validValues = values.filter(value => {
    return (
      typeof value === 'number' &&
      Number.isFinite(value) &&
      value < -1 &&
      value > -95
    )
  })

  return validValues.length >= 3
}

function updateSpectrum() {
  if (!props.selectedTrack) {
    spectrumData.value = []
    spectrumRafId = requestAnimationFrame(updateSpectrum)
    return
  }

  if (trackStore.isPlaying) {
    const nextSpectrum = trackStore.getTrackSpectrum(props.selectedTrack.trackId)

    if (nextSpectrum.length > 0 && hasMeaningfulSpectrum(nextSpectrum)) {
      spectrumData.value = nextSpectrum
    }
  }

  spectrumRafId = requestAnimationFrame(updateSpectrum)
}

onMounted(() => {
  spectrumRafId = requestAnimationFrame(updateSpectrum)
})

onUnmounted(() => {
  if (spectrumRafId !== null) {
    cancelAnimationFrame(spectrumRafId)
  }
})

watch(
  () => props.selectedTrack?.trackId,
  () => {
    spectrumData.value = []
  },
)

const isPreviewPlaying = ref<'before' | 'after' | null>(null)

const aiAnalysisItems = inject<Ref<AiAnalysisItem[]>>('aiAnalysisItems')
const activeAiAnalysisId = inject<Ref<string | number | null>>('activeAiAnalysisId')

const activeAiAnalysis = computed(() => {
  if (!aiAnalysisItems?.value || !activeAiAnalysisId?.value) return null
  return aiAnalysisItems.value.find(item => item.id === activeAiAnalysisId.value) || null
})

watch(
  () => activeAiAnalysis.value?.id,
  () => {
    selectedRevisionTrackIds.value = []
    revisionMessage.value = ''
  },
)

watch(
  revisionCandidateTracks,
  (tracks) => {
    const candidateTrackIds = new Set(tracks.map(track => Number(track.trackId)))

    selectedRevisionTrackIds.value = selectedRevisionTrackIds.value.filter(trackId =>
      candidateTrackIds.has(Number(trackId)),
    )
  },
)

let previousLoopState = { active: false, start: 0, end: 4 }

async function togglePreview(type: 'before' | 'after') {
  if (!props.selectedTrack) return

  if (isPreviewPlaying.value === type) {
    trackStore.stopPlay()
    return
  }

  trackStore.stopPlay()

  if (type === 'before') {
    trackStore.rebuildTrackEqChain(props.selectedTrack.trackId)
  } else {
    trackStore.rebuildTrackEqChain(props.selectedTrack.trackId, props.aiAfterBands)
  }

  if (isPreviewPlaying.value === null) {
    previousLoopState = {
      active: trackStore.isLoopActive,
      start: trackStore.loopStartBar,
      end: trackStore.loopEndBar
    }
  }

  isPreviewPlaying.value = type

  const analysis = activeAiAnalysis.value
  if (analysis) {
    trackStore.isLoopActive = true
    
    // 밀리초(ms) 데이터를 기반으로 정확한 마디 단위(소수점 포함) 계산
    const exactStartBar = analysis.startMs / (trackStore.secondsPerBar * 1000)
    
    // 루프가 너무 짧아 오디오가 튀는 현상을 막기 위해 최소 1박자(0.25마디) 길이는 보장
    const exactEndBar = Math.max(
      analysis.endMs / (trackStore.secondsPerBar * 1000),
      exactStartBar + 0.25
    )

    trackStore.loopStartBar = exactStartBar
    trackStore.loopEndBar = exactEndBar
    trackStore.playheadPosition = exactStartBar
  }

  trackStore.togglePlay()
}

watch(
  () => trackStore.isPlaying,
  (playing) => {
    if (!playing && isPreviewPlaying.value !== null) {
      isPreviewPlaying.value = null
      if (props.selectedTrack) {
        trackStore.rebuildTrackEqChain(props.selectedTrack.trackId)
      }

      trackStore.isLoopActive = previousLoopState.active
      trackStore.loopStartBar = previousLoopState.start
      trackStore.loopEndBar = previousLoopState.end
    }
  }
)
</script>

<template>
  <section
    data-guide="ai-eq-panel"
    class="shrink-0 border-t border-white/10 bg-[#202020] shadow-[0_-18px_30px_rgba(0,0,0,0.45)] transition-all"
  >
    <!-- 상단 헤더 -->
    <div 
      class="flex h-12 cursor-pointer items-center gap-3 border-b border-white/10 px-5 hover:bg-white/5 transition"
      @click="isCollapsed = !isCollapsed"
    >
      <Sparkles
        class="h-4 w-4 text-[#FF8F1A]"
        :class="{ 'animate-pulse': aiAnalyzing }"
      />

      <span class="text-sm font-bold tracking-[0.18em] text-white">
        EQ
      </span>

      <span class="font-mono text-[11px] tracking-widest text-gray-400">
        {{ selectedTrack ? selectedTrack.name : '트랙을 선택하세요' }}
      </span>

      <div class="ml-auto text-gray-400 transition">
        <ChevronUp v-if="!isCollapsed" class="h-4 w-4" />
        <ChevronDown v-else class="h-4 w-4" />
      </div>
    </div>

    <!-- 패널 내용 -->
    <div v-show="!isCollapsed">

    <!-- 트랙 미선택: 빈 EQ 상태 -->
    <div
      v-if="!selectedTrack"
      class="flex h-[260px] items-center justify-center bg-[#242424]"
    >
      <div class="text-center">
        <div class="mb-2 text-sm font-semibold tracking-[0.18em] text-gray-400">
          NO TRACK SELECTED
        </div>
        <div class="text-xs text-gray-500">
          EQ를 조절할 트랙을 선택하세요.
        </div>
      </div>
    </div>

    <!-- 트랙 선택 + AI 분석 전: 단일 EQ -->
    <!-- 트랙 선택 + 일반 EQ / 하쉬니스 마커 표시 -->
    <div v-else-if="shouldShowSingleEqGraph" class="h-[260px]">
      <EqGraph
        :title="isMarkerOnlyMode ? '하쉬니스 감지' : '현재'"
        :freq-labels="freqLabels"
        :db-labels="dbLabels"
        :bands="currentBands"
        :spectrum-data="spectrumData"
        :ai-markers="isMarkerOnlyMode ? aiMarkers : []"
        :interactive="!!selectedTrack"
        @add-band="emit('add-eq-band', $event)"
        @update-band="emit('update-eq-band', $event)"
        @remove-band="emit('remove-eq-band', $event)"
      />
    </div>

    <!-- 트랙 선택 + AI 분석 후 -->
<div v-else>
  <div class="grid grid-cols-2 border-b border-white/10">
    <!-- 왼쪽: Before 헤더 -->
    <div class="flex h-11 items-center gap-3 border-r border-white/10 px-5">
      <span class="text-xs font-bold tracking-[0.28em] text-gray-400">
        이전
      </span>

      <button
        @click="togglePreview('before')"
        class="grid h-7 w-7 place-items-center rounded-full border text-white transition"
        :class="isPreviewPlaying === 'before' ? 'border-[#FF8F1A] text-[#FF8F1A] bg-[#FF8F1A]/10' : 'border-white/15 hover:border-[#FF8F1A] hover:text-[#FF8F1A]'"
      >
        <Square v-if="isPreviewPlaying === 'before'" class="h-3 w-3 fill-current" />
        <Play v-else class="h-3 w-3 fill-current" />
      </button>
    </div>

    <!-- 오른쪽: 요청 전/후 헤더 -->
    <div class="flex h-11 items-center gap-3 px-5">
      <span class="text-xs font-bold tracking-[0.28em] text-gray-400">
        {{
          isMarkerOnlyMode
            ? '하쉬니스 감지'
            : hasAiEqBands
              ? '이후'
              : 'AI 수정 요청'
        }}
      </span>

      <button
        @click="togglePreview('after')"
        class="grid h-7 w-7 place-items-center rounded-full border text-white transition"
        :class="isPreviewPlaying === 'after' ? 'border-[#FF8F1A] text-[#FF8F1A] bg-[#FF8F1A]/10' : 'border-white/15 hover:border-[#FF8F1A] hover:text-[#FF8F1A]'"
      >
        <Square v-if="isPreviewPlaying === 'after'" class="h-3 w-3 fill-current" />
        <Play v-else class="h-3 w-3 fill-current" />
      </button>

      <div class="ml-auto flex items-center gap-2">
        <button
          class="inline-flex items-center gap-1.5 rounded-full bg-[#FF8F1A] px-3 py-1.5 text-[11px] font-bold text-black transition hover:brightness-110 disabled:opacity-40"
          :disabled="aiAnalyzing || !hasAiEqBands"
          @click="emit('apply-ai-eq')"
        >
          <Wand2 class="h-3.5 w-3.5" />
          AI 적용
        </button>

        <button
          class="rounded-full border border-white/15 px-3 py-1.5 text-[11px] font-bold text-gray-300 transition hover:border-white/30 hover:text-white"
          @click="emit('cancel-ai-eq')"
        >
          취소
        </button>
      </div>
    </div>
  </div>

  <div class="grid h-[300px] grid-cols-2 bg-white/10 gap-px">
    <!-- 왼쪽: Before EQ -->
    <EqGraph
      title="Before"
      :freq-labels="freqLabels"
      :db-labels="dbLabels"
      :bands="beforeBands"
      :spectrum-data="spectrumData"
      :interactive="false"
    />

    <!-- 오른쪽: AI 요청 UI -->
    <div
      v-if="shouldShowRevisionRequest"
      class="flex h-full flex-col justify-center bg-[#242424] px-8"
    >
      <div>
        <div class="text-xl font-bold text-white">
          유지할 트랙 선택
        </div>

        <p class="mt-2 text-sm text-gray-400">
          충돌 트랙을 확인하고 유지할 트랙을 선택해주세요. 해당 트랙을 제외하고 AI가 수정 계획을 생성합니다.
        </p>

        <p
          v-if="!hasRevisionCandidates"
          class="mt-4 text-sm text-amber-300"
        >
          현재 문제 구간과 직접 관련된 트랙 정보가 없어 수정 요청을 보낼 수 없습니다.
        </p>

        <div
          v-else
          class="mt-5 flex flex-wrap gap-3"
        >
          <button
            v-for="track in revisionCandidateTracks"
            :key="track.trackId"
            type="button"
            class="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-bold transition"
            :class="selectedRevisionTrackIds.includes(track.trackId)
              ? 'border-[#FF8F1A] bg-[#FF8F1A] text-black'
              : 'border-white/25 text-gray-100 hover:border-[#FF8F1A] hover:text-[#FF8F1A]'"
            @click="toggleRevisionTrack(track.trackId)"
          >
            <span
              class="grid h-4 w-4 place-items-center rounded-full border"
              :class="selectedRevisionTrackIds.includes(track.trackId)
                ? 'border-black bg-black/20'
                : 'border-white/60'"
            >
              <span
                v-if="selectedRevisionTrackIds.includes(track.trackId)"
                class="h-2 w-2 rounded-full bg-black"
              />
            </span>

            {{ track.name }}
          </button>
        </div>
      </div>

      <div class="mt-10">
        <div class="text-xl font-bold text-white">
          수정 요청하기
        </div>

        <p class="mt-2 text-sm text-gray-400">
          선택하지 않은 트랙에 대해 AI에게 수정 방향을 요청하세요.
        </p>

        <div class="mt-4 flex gap-3">
          <input
            v-model="revisionMessage"
            type="text"
            class="h-11 flex-1 rounded-md border border-white/10 bg-black/30 px-4 text-sm text-white outline-none placeholder:text-gray-500 focus:border-[#FF8F1A]"
            placeholder="선택한 트랙은 그대로 두고, 나머지 트랙만 자연스럽게 줄여줘."
          />

          <button
            type="button"
            class="inline-flex h-11 items-center gap-2 rounded-md bg-[#FF8F1A] px-5 text-sm font-bold text-black transition hover:brightness-110 disabled:opacity-40"
            :disabled="aiAnalyzing || selectedRevisionTrackIds.length === 0 || !hasRevisionCandidates"
            @click="requestAiRevision"
          >
            <Wand2 class="h-4 w-4" />
            계획 생성
          </button>
        </div>
      </div>
    </div>

    <!-- 오른쪽: AI 수정안 After EQ -->
    <EqGraph
  v-else-if="shouldShowCompareEqGraph"
  title="After"
  :freq-labels="freqLabels"
  :db-labels="dbLabels"
  :bands="afterBands"
  :spectrum-data="spectrumData"
  :ai-markers="aiMarkers"
  :after="true"
  :loading="aiAnalyzing"
  :interactive="false"
/>
  </div>
</div>
    </div>
    <!-- 패널 내용 끝 -->
  </section>
</template>
