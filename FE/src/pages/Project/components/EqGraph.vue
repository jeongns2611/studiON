<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { TrackEqBandState } from '../types'

const props = withDefaults(defineProps<{
  title?: string
  freqLabels?: string[]
  dbLabels?: string[]
  bands: TrackEqBandState[]
  spectrumData: number[]
  interactive?: boolean
  after?: boolean
  loading?: boolean
  aiMarkers?: EqMarker[]
}>(), {
  title: '',
  freqLabels: () => ['20', '50', '100', '200', '500', '1K', '2K', '5K', '10K', '20K'],
  dbLabels: () => ['+12', '+9', '+6', '+3', '0', '-3', '-6', '-9', '-12'],
  interactive: false,
  after: false,
  loading: false,
})

type EqMarker = {
  trackId: number | null
  centerHz?: number | null
  bandLowHz?: number | null
  bandHighHz?: number | null
}

const emit = defineEmits<{
  'add-band': [payload: { frequencyHz: number; gainDeltaDb: number }]
  'update-band': [payload: { bandOrder: number; patch: Partial<TrackEqBandState> }]
  'remove-band': [payload: { bandOrder: number }]
}>()

const svgRef = ref<SVGSVGElement | null>(null)
const activeBandOrder = ref<number | null>(null)
const draggingBandOrder = ref<number | null>(null)
const hoverFreqHz = ref<number | null>(null)
const hoverGainDb = ref<number | null>(null)

const VIEWBOX_WIDTH = 1600
const VIEWBOX_HEIGHT = 420

const PADDING = {
  top: 20,
  right: 60,
  bottom: 44,
  left: 18,
}

const MIN_FREQ = 20
const MAX_FREQ = 20000
const MIN_DB = -12
const MAX_DB = 12

const SPECTRUM_MIN_DB = -96
const SPECTRUM_MAX_DB = -18

const plotWidth = VIEWBOX_WIDTH - PADDING.left - PADDING.right
const plotHeight = VIEWBOX_HEIGHT - PADDING.top - PADDING.bottom

const majorFreqs = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
const minorFreqs = [
  30, 40, 60, 70, 80, 90,
  150, 300, 400, 600, 700, 800, 900,
  1500, 3000, 4000, 6000, 7000, 8000, 9000,
  15000,
]
const dbTicks = [12, 9, 6, 3, 0, -3, -6, -9, -12]

const orderedBands = computed(() =>
  [...props.bands].sort((a, b) => a.bandOrder - b.bandOrder),
)

const activeBand = computed(() => {
  if (activeBandOrder.value == null) return null
  return orderedBands.value.find(band => band.bandOrder === activeBandOrder.value) ?? null
})

const validAiMarkers = computed(() => {
  return (props.aiMarkers ?? []).filter(marker => {
    return (
      marker.centerHz != null ||
      (marker.bandLowHz != null && marker.bandHighHz != null)
    )
  })
})

watch(
  () => props.bands,
  (bands) => {
    if (
      activeBandOrder.value != null &&
      !bands.some(band => band.bandOrder === activeBandOrder.value)
    ) {
      activeBandOrder.value = null
    }
  },
  { deep: true },
)

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function round(value: number, precision = 1) {
  const factor = 10 ** precision
  return Math.round(value * factor) / factor
}

function log10(value: number) {
  return Math.log(value) / Math.LN10
}

function freqToX(freqHz: number) {
  const clamped = clamp(freqHz, MIN_FREQ, MAX_FREQ)
  const min = log10(MIN_FREQ)
  const max = log10(MAX_FREQ)
  const ratio = (log10(clamped) - min) / (max - min)
  return PADDING.left + ratio * plotWidth
}

function xToFreq(x: number) {
  const ratio = clamp((x - PADDING.left) / plotWidth, 0, 1)
  const min = log10(MIN_FREQ)
  const max = log10(MAX_FREQ)
  return 10 ** (min + (max - min) * ratio)
}

function gainToY(gainDb: number) {
  const clamped = clamp(gainDb, MIN_DB, MAX_DB)
  const ratio = (MAX_DB - clamped) / (MAX_DB - MIN_DB)
  return PADDING.top + ratio * plotHeight
}

function yToGain(y: number) {
  const ratio = clamp((y - PADDING.top) / plotHeight, 0, 1)
  return MAX_DB - ratio * (MAX_DB - MIN_DB)
}

function spectrumDbToY(value: number) {
  const clamped = clamp(value, SPECTRUM_MIN_DB, SPECTRUM_MAX_DB)

  const normalized =
    (clamped - SPECTRUM_MIN_DB) / (SPECTRUM_MAX_DB - SPECTRUM_MIN_DB)

  return PADDING.top + (1 - normalized) * plotHeight
}

function formatFreq(freq: number) {
  if (freq >= 1000) {
    const kHz = freq / 1000
    return kHz >= 10 ? `${Math.round(kHz)} kHz` : `${round(kHz, 2)} kHz`
  }
  return `${Math.round(freq)} Hz`
}

function formatGain(gain: number) {
  const rounded = round(gain, 1)
  return `${rounded > 0 ? '+' : ''}${rounded} dB`
}

function formatQ(q: number) {
  return round(q, 2).toFixed(2)
}

function labelForFreq(freq: number) {
  if (freq >= 1000) {
    if (freq % 1000 === 0) return `${freq / 1000}K`
    return `${round(freq / 1000, 1)}K`
  }
  return `${freq}`
}

function getLocalPoint(clientX: number, clientY: number) {
  if (!svgRef.value) return null

  const rect = svgRef.value.getBoundingClientRect()
  const x = ((clientX - rect.left) / rect.width) * VIEWBOX_WIDTH
  const y = ((clientY - rect.top) / rect.height) * VIEWBOX_HEIGHT

  return { x, y }
}

function isInsidePlot(x: number, y: number) {
  return (
    x >= PADDING.left &&
    x <= VIEWBOX_WIDTH - PADDING.right &&
    y >= PADDING.top &&
    y <= VIEWBOX_HEIGHT - PADDING.bottom
  )
}

function updateHoverState(clientX: number, clientY: number) {
  const point = getLocalPoint(clientX, clientY)
  if (!point || !isInsidePlot(point.x, point.y)) {
    hoverFreqHz.value = null
    hoverGainDb.value = null
    return
  }

  hoverFreqHz.value = xToFreq(point.x)
  hoverGainDb.value = yToGain(point.y)
}

function handlePointerMoveOnSvg(event: PointerEvent) {
  updateHoverState(event.clientX, event.clientY)
}

function handlePointerLeave() {
  hoverFreqHz.value = null
  hoverGainDb.value = null
}

function handleBackgroundPointerDown(event: PointerEvent) {
  if (!props.interactive) return

  const point = getLocalPoint(event.clientX, event.clientY)
  if (!point || !isInsidePlot(point.x, point.y)) return

  const frequencyHz = Math.round(xToFreq(point.x))
  const gainDeltaDb = round(yToGain(point.y), 1)

  emit('add-band', {
    frequencyHz,
    gainDeltaDb,
  })
}

function startBandDrag(event: PointerEvent, bandOrder: number) {
  if (!props.interactive) return

  event.preventDefault()
  event.stopPropagation()

  activeBandOrder.value = bandOrder
  draggingBandOrder.value = bandOrder

  window.addEventListener('pointermove', handleBandDrag)
  window.addEventListener('pointerup', stopBandDrag)

  updateHoverState(event.clientX, event.clientY)
}

function handleBandDoubleClick(event: MouseEvent, bandOrder: number) {
  if (!props.interactive) return

  event.preventDefault()
  event.stopPropagation()

  emit('remove-band', { bandOrder })

  if (activeBandOrder.value === bandOrder) {
    activeBandOrder.value = null
  }
}

function handleBandDrag(event: PointerEvent) {
  if (draggingBandOrder.value == null) return

  const point = getLocalPoint(event.clientX, event.clientY)
  if (!point) return

  const clampedX = clamp(point.x, PADDING.left, VIEWBOX_WIDTH - PADDING.right)
  const clampedY = clamp(point.y, PADDING.top, VIEWBOX_HEIGHT - PADDING.bottom)

  const frequencyHz = Math.round(xToFreq(clampedX))
  const gainDeltaDb = round(yToGain(clampedY), 1)

  emit('update-band', {
    bandOrder: draggingBandOrder.value,
    patch: {
      frequencyHz,
      gainDeltaDb,
    },
  })

  updateHoverState(event.clientX, event.clientY)
}

function stopBandDrag() {
  draggingBandOrder.value = null
  window.removeEventListener('pointermove', handleBandDrag)
  window.removeEventListener('pointerup', stopBandDrag)
}

onBeforeUnmount(() => {
  stopBandDrag()
})

function bellResponse(freqHz: number, band: TrackEqBandState) {
  const distance = Math.log2(freqHz / band.frequencyHz)
  const width = clamp(1.15 / Math.max(band.q, 0.1), 0.12, 2.4)
  return band.gainDeltaDb * Math.exp(-(distance * distance) / (2 * width * width))
}

function lowShelfResponse(freqHz: number, band: TrackEqBandState) {
  const distance = Math.log2(freqHz / band.frequencyHz)
  const steepness = clamp(band.q * 2.4, 0.8, 10)
  const shelf = 1 / (1 + Math.exp(distance * steepness))
  return band.gainDeltaDb * shelf
}

function highShelfResponse(freqHz: number, band: TrackEqBandState) {
  const distance = Math.log2(freqHz / band.frequencyHz)
  const steepness = clamp(band.q * 2.4, 0.8, 10)
  const shelf = 1 / (1 + Math.exp(-distance * steepness))
  return band.gainDeltaDb * shelf
}

function getBandResponse(freqHz: number, band: TrackEqBandState) {
  switch (band.eqTypeCode) {
    case 2:
      return lowShelfResponse(freqHz, band)
    case 3:
      return highShelfResponse(freqHz, band)
    default:
      return bellResponse(freqHz, band)
  }
}

function getTotalResponse(freqHz: number) {
  return orderedBands.value.reduce((sum, band) => {
    return sum + getBandResponse(freqHz, band)
  }, 0)
}

const eqCurvePath = computed(() => {
  const sampleCount = 420
  let path = ''

  for (let i = 0; i <= sampleCount; i++) {
    const ratio = i / sampleCount
    const freqHz = 10 ** (log10(MIN_FREQ) + ratio * (log10(MAX_FREQ) - log10(MIN_FREQ)))
    const x = freqToX(freqHz)
    const y = gainToY(getTotalResponse(freqHz))

    path += `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)} `
  }

  return path.trim()
})

const spectrumPoints = computed(() => {
  const values = props.spectrumData ?? []

  if (!values.length) return []

  // 실제 FFT 값은 보통 음수 dB 값이다.
  // 0, 양수, -Infinity, NaN, 전부 무효값으로 처리한다.
  const validValues = values.filter(value => {
    return (
      typeof value === 'number' &&
      Number.isFinite(value) &&
      value < -1 &&
      value > SPECTRUM_MIN_DB
    )
  })

  // 유효한 값이 거의 없으면 무음/초기 상태로 보고 아예 그리지 않는다.
  if (validValues.length < 3) {
    return []
  }

  const nyquist = 22050
  const result: Array<{ x: number; y: number }> = []

  for (let i = 0; i < values.length; i += 1) {
    const freqHz = (i / Math.max(1, values.length - 1)) * nyquist

    if (freqHz < MIN_FREQ || freqHz > MAX_FREQ) continue

    const rawValue = values[i]

    // 유효하지 않은 bin은 바닥값으로 처리
    const value =
      typeof rawValue === 'number' &&
      Number.isFinite(rawValue) &&
      rawValue < -1 &&
      rawValue > SPECTRUM_MIN_DB
        ? rawValue
        : SPECTRUM_MIN_DB

    result.push({
      x: freqToX(freqHz),
      y: spectrumDbToY(value),
    })
  }

  return result
})

const spectrumAreaPath = computed(() => {
  const points = spectrumPoints.value
  if (points.length < 2) return ''

  const bottomY = PADDING.top + plotHeight
  let path = `M ${points[0].x.toFixed(2)} ${bottomY.toFixed(2)} `

  for (let i = 0; i < points.length; i++) {
    path += `L ${points[i].x.toFixed(2)} ${points[i].y.toFixed(2)} `
  }

  path += `L ${points[points.length - 1].x.toFixed(2)} ${bottomY.toFixed(2)} Z`
  return path.trim()
})

const spectrumLinePath = computed(() => {
  const points = spectrumPoints.value
  if (points.length < 2) return ''

  let path = ''
  for (let i = 0; i < points.length; i++) {
    path += `${i === 0 ? 'M' : 'L'} ${points[i].x.toFixed(2)} ${points[i].y.toFixed(2)} `
  }
  return path.trim()
})

const infoText = computed(() => {
  if (activeBand.value) {
    return {
      freq: formatFreq(activeBand.value.frequencyHz),
      gain: formatGain(activeBand.value.gainDeltaDb),
      q: formatQ(activeBand.value.q),
    }
  }

  if (hoverFreqHz.value != null && hoverGainDb.value != null) {
    return {
      freq: formatFreq(hoverFreqHz.value),
      gain: formatGain(hoverGainDb.value),
      q: '--',
    }
  }

  return {
    freq: '--',
    gain: '--',
    q: '--',
  }
})

const zeroDbY = computed(() => gainToY(0))
</script>

<template>
  <div class="relative h-full w-full overflow-hidden bg-[#1b1b1b]">
    <!-- 상단 상태 표시 -->
    <div class="pointer-events-none absolute left-4 top-3 z-20 flex items-center gap-5">
      <div v-if="title" class="text-[11px] font-semibold tracking-[0.2em] text-gray-300 uppercase">
        {{ title }}
      </div>

      <div class="flex items-center gap-4 text-[11px] text-gray-400">
        <span>Freq <span class="ml-1 font-mono text-[#f7d34a]">{{ infoText.freq }}</span></span>
        <span>Gain <span class="ml-1 font-mono text-[#f7d34a]">{{ infoText.gain }}</span></span>
        <span>Q <span class="ml-1 font-mono text-[#f7d34a]">{{ infoText.q }}</span></span>
      </div>
    </div>

    <!-- 로딩 오버레이 -->
    <div
      v-if="loading"
      class="absolute inset-0 z-30 grid place-items-center bg-black/35 backdrop-blur-[1px]"
    >
      <div class="rounded-full border border-white/10 bg-[#222]/90 px-4 py-2 text-xs tracking-[0.18em] text-gray-300">
        ANALYZING...
      </div>
    </div>

    <svg
      ref="svgRef"
      class="h-full w-full"
      :viewBox="`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`"
      preserveAspectRatio="none"
      @pointermove="handlePointerMoveOnSvg"
      @pointerleave="handlePointerLeave"
    >
      <!-- 배경 -->
      <rect
        :x="PADDING.left"
        :y="PADDING.top"
        :width="plotWidth"
        :height="plotHeight"
        rx="8"
        fill="#161616"
      />

      <!-- 세로 그리드 (minor) -->
      <g opacity="0.55">
        <line
          v-for="freq in minorFreqs"
          :key="`minor-${freq}`"
          :x1="freqToX(freq)"
          :x2="freqToX(freq)"
          :y1="PADDING.top"
          :y2="PADDING.top + plotHeight"
          stroke="#3b3b3b"
          stroke-width="1"
        />
      </g>

      <!-- 세로 그리드 (major) -->
      <g opacity="0.9">
        <line
          v-for="freq in majorFreqs"
          :key="`major-${freq}`"
          :x1="freqToX(freq)"
          :x2="freqToX(freq)"
          :y1="PADDING.top"
          :y2="PADDING.top + plotHeight"
          stroke="#4a4a4a"
          stroke-width="1.4"
        />
      </g>

      <!-- 가로 그리드 -->
      <g>
        <line
          v-for="db in dbTicks"
          :key="`db-${db}`"
          :x1="PADDING.left"
          :x2="PADDING.left + plotWidth"
          :y1="gainToY(db)"
          :y2="gainToY(db)"
          :stroke="db === 0 ? '#806d20' : '#343434'"
          :stroke-width="db === 0 ? 2 : 1"
        />
      </g>

      <!-- 클릭 추가용 히트 영역 -->
      <rect
        :x="PADDING.left"
        :y="PADDING.top"
        :width="plotWidth"
        :height="plotHeight"
        fill="transparent"
        @pointerdown="handleBackgroundPointerDown"
      />

      <!-- 스펙트럼 회색 면 -->
      <path
        v-if="spectrumAreaPath"
        :d="spectrumAreaPath"
        fill="rgba(185, 185, 185, 0.28)"
        stroke="none"
        pointer-events="none"
      />

      <!-- 스펙트럼 윤곽선 -->
      <path
        v-if="spectrumLinePath"
        :d="spectrumLinePath"
        fill="none"
        stroke="rgba(180, 180, 180, 0.55)"
        stroke-width="1.25"
        vector-effect="non-scaling-stroke"
        pointer-events="none"
      />

      <!-- EQ 0dB 라인 강조 -->
      <line
        :x1="PADDING.left"
        :x2="PADDING.left + plotWidth"
        :y1="zeroDbY"
        :y2="zeroDbY"
        stroke="#af8a1d"
        stroke-width="2.2"
        pointer-events="none"
      />

      <!-- EQ 커브 -->
      <path
        :d="eqCurvePath"
        fill="none"
        stroke="#f7d34a"
        stroke-width="5"
        stroke-linecap="round"
        stroke-linejoin="round"
        vector-effect="non-scaling-stroke"
        pointer-events="none"
      />

      <!-- AI 하쉬니스 마커 -->
<g pointer-events="none">
  <g
    v-for="marker in validAiMarkers"
    :key="`${marker.trackId}-${marker.centerHz}-${marker.bandLowHz}-${marker.bandHighHz}`"
  >
    <rect
      v-if="marker.bandLowHz != null && marker.bandHighHz != null"
      :x="freqToX(marker.bandLowHz)"
      :y="PADDING.top"
      :width="Math.max(2, freqToX(marker.bandHighHz) - freqToX(marker.bandLowHz))"
      :height="plotHeight"
      fill="rgba(255, 143, 26, 0.12)"
      stroke="rgba(255, 143, 26, 0.35)"
      stroke-width="1"
    />

    <line
      v-if="marker.centerHz != null"
      :x1="freqToX(marker.centerHz)"
      :x2="freqToX(marker.centerHz)"
      :y1="PADDING.top"
      :y2="PADDING.top + plotHeight"
      stroke="rgba(255, 143, 26, 0.95)"
      stroke-width="2"
      stroke-dasharray="8 6"
      vector-effect="non-scaling-stroke"
    />

    <text
      v-if="marker.centerHz != null"
      :x="freqToX(marker.centerHz)"
      :y="PADDING.top + 22"
      text-anchor="middle"
      font-size="15"
      font-weight="700"
      fill="#FF8F1A"
    >
      HARSH
    </text>
  </g>
</g>

      <!-- 밴드 포인트 -->
      <g v-for="band in orderedBands" :key="band.bandOrder">
        <g
          class="cursor-pointer"
          @pointerdown.stop.prevent="startBandDrag($event, band.bandOrder)"
          @dblclick.stop.prevent="handleBandDoubleClick($event, band.bandOrder)"
        >
          <circle
            :cx="freqToX(band.frequencyHz)"
            :cy="gainToY(band.gainDeltaDb)"
            r="13"
            :fill="activeBandOrder === band.bandOrder ? '#ffbf33' : '#f2c63d'"
            stroke="#1c1c1c"
            stroke-width="3"
          />
          <text
            :x="freqToX(band.frequencyHz)"
            :y="gainToY(band.gainDeltaDb) + 4"
            text-anchor="middle"
            font-size="11"
            font-weight="700"
            fill="#222"
          >
            {{ band.bandOrder }}
          </text>
        </g>
      </g>

      <!-- 하단 주파수 라벨 -->
      <g>
        <text
          v-for="freq in majorFreqs"
          :key="`freq-label-${freq}`"
          :x="freqToX(freq)"
          :y="VIEWBOX_HEIGHT - 12"
          text-anchor="middle"
          font-size="18"
          fill="#7986a0"
        >
          {{ labelForFreq(freq) }}
        </text>
      </g>

      <!-- 우측 dB 라벨 -->
      <g>
        <text
          v-for="db in dbTicks"
          :key="`db-label-${db}`"
          :x="VIEWBOX_WIDTH - 10"
          :y="gainToY(db) + 5"
          text-anchor="end"
          font-size="18"
          fill="#8a95aa"
        >
          {{ db > 0 ? `+${db}` : `${db}` }}
        </text>
      </g>
    </svg>

    <!-- 인터랙션 안내 -->
    <div
      v-if="interactive"
      class="pointer-events-none absolute bottom-3 left-4 text-[11px] text-gray-500"
    >
      클릭해서 밴드 추가 · 드래그해서 주파수/게인 조절
    </div>
  </div>
</template>