<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

interface Props {
  bars?: number
  speed?: number
  className?: string
  color?: string
}

const props = withDefaults(defineProps<Props>(), {
  bars: 180,
  speed: 1,
  className: '',
  color: 'hsl(0 0% 96%)',
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
let rafId: number | null = null
let resizeObserver: ResizeObserver | null = null

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas)
    return

  const dpr = window.devicePixelRatio || 1
  canvas.width = canvas.clientWidth * dpr
  canvas.height = canvas.clientHeight * dpr
}

function stopAnimation() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

function startAnimation() {
  const canvas = canvasRef.value
  if (!canvas)
    return

  const ctx = canvas.getContext('2d')
  if (!ctx)
    return

  const draw = (time: number) => {
    const w = canvas.width
    const h = canvas.height
    const dpr = window.devicePixelRatio || 1

    ctx.clearRect(0, 0, w, h)

    const t = (time / 1000) * props.speed
    const cy = h / 2

    const gap = Math.max(1 * dpr, (w / props.bars) * 0.25)
    const barW = Math.max(1 * dpr, w / props.bars - gap)

    ctx.fillStyle = props.color
    ctx.shadowColor = props.color
    ctx.shadowBlur = 4
    ctx.globalAlpha = 0.95

    for (let i = 0; i < props.bars; i += 1) {
      const phase = i / props.bars

      const swell
        = 0.55 * Math.sin(phase * Math.PI * 3 + t * 0.7)
          + 0.30 * Math.sin(phase * Math.PI * 6 + t * 1.1)
          + 0.20 * Math.sin(phase * Math.PI * 11 + t * 1.6)

      const detail
        = 0.6 * Math.sin(t * 6 + i * 0.9)
          + 0.4 * Math.sin(t * 9 + i * 2.3)

      const env = Math.abs(swell) * 0.75 + 0.15
      const tex = Math.abs(detail) * 0.55 + 0.45
      const edge = Math.pow(Math.sin(phase * Math.PI), 0.6)

      const amp = Math.min(1, env * tex) * edge
      const barH = Math.max(2 * dpr, amp * h * 0.95)

      const x = i * (barW + gap)
      ctx.fillRect(x, cy - barH / 2, barW, barH)
    }

    ctx.globalAlpha = 1
    ctx.shadowBlur = 0

    rafId = requestAnimationFrame(draw)
  }

  rafId = requestAnimationFrame(draw)
}

onMounted(() => {
  resizeCanvas()

  if (canvasRef.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeCanvas()
    })
    resizeObserver.observe(canvasRef.value)
  }

  startAnimation()
})

onBeforeUnmount(() => {
  stopAnimation()
  resizeObserver?.disconnect()
})

watch(
  () => [props.bars, props.speed, props.color],
  () => {
    stopAnimation()
    resizeCanvas()
    startAnimation()
  },
)
</script>

<template>
  <canvas
    ref="canvasRef"
    :class="className"
    aria-hidden="true"
  />
</template>