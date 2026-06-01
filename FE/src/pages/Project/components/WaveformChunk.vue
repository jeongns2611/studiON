<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue';
import { useTrackStore } from '../store/useTrackStore';
import type { ClipUIState } from '../types';
import { waveformRendererPool } from '../../../core/workers/waveformRendererPool';

const props = defineProps<{
  clip: ClipUIState;
  chunkLeft: number;
  chunkWidth: number;
  audioData: { channels: Float32Array[]; sampleRate: number };
  audioKey: string;
}>();

const trackStore = useTrackStore();
const canvasRef = ref<HTMLCanvasElement | null>(null);

// 리사이즈 시 모양 찌그러짐을 방지하기 위한 렌더링 상태 캐싱
const renderedWidth = ref(props.chunkWidth);
const renderedLeft = ref(props.chunkLeft);
const renderedAudioStartMs = ref(props.clip.audioStartMs);

const msPerPixel = computed(() => {
  if (props.clip.duration <= 0 || trackStore.pixelPerBar <= 0) return 1;
  return props.clip.audioDurationMs / (props.clip.duration * trackStore.pixelPerBar);
});

// 클립의 시작점이 변할 때(왼쪽 리사이즈), 캔버스를 반대 방향으로 이동시켜 잘라내기(Crop) 효과 생성
const visualTransformX = computed(() => {
  const diffMs = props.clip.audioStartMs - renderedAudioStartMs.value;
  if (diffMs === 0) return 0;
  return -(diffMs / msPerPixel.value);
});


// 현재 진행 중인 렌더 요청 ID들 (채널별, 이전 요청을 취소하기 위함)
let currentRequestIds: number[] = [];
let renderTimeout: ReturnType<typeof setTimeout> | null = null;

const requestRenderDebounced = () => {
  if (renderTimeout) clearTimeout(renderTimeout);
  // 리사이즈 중 메인 스레드 부하를 줄이기 위해 150ms 디바운스 적용
  renderTimeout = setTimeout(() => {
    renderWaveform();
  }, 150);
};

const renderWaveform = async () => {
  if (!canvasRef.value) return;
  if (props.chunkWidth <= 0) return;

  const currentMsPerPixel = msPerPixel.value;
  const secondsPerPixel = currentMsPerPixel / 1000;
  const samplesPerPixel = secondsPerPixel * props.audioData.sampleRate;

  // 1. 전체 오디오에서의 시작점(오프셋) 계산
  const baseOffsetSec = props.clip.audioStartMs / 1000;
  // 2. 이 청크가 담당하는 추가적인 시작점(픽셀 기반) 계산
  const chunkOffsetSec = props.chunkLeft * secondsPerPixel;
  
  const startSampleOffset = (baseOffsetSec + chunkOffsetSec) * props.audioData.sampleRate;

  const numChannels = props.audioData.channels.length;
  if (numChannels === 0) return;

  const totalSamples = props.audioData.channels[0].length;
  if (startSampleOffset >= totalSamples) {
    return; // 이 청크는 그릴 데이터가 없음
  }

  // 이전 요청이 진행 중이면 취소
  if (currentRequestIds.length > 0) {
    currentRequestIds.forEach(id => waveformRendererPool.cancelRequest(id));
    currentRequestIds = [];
  }

  // Worker Pool에 채널별로 렌더 요청 (Zero-Copy)
  const channelHeight = Math.floor(100 / numChannels);
  
  const requests = props.audioData.channels.map((_, index) => {
    return waveformRendererPool.requestRender({
      audioKey: props.audioKey,
      color: '#D4CED2',
      width: props.chunkWidth,
      height: channelHeight,
      samplesPerPixel,
      startSampleOffset,
      channelIndex: index,
    });
  });

  currentRequestIds = requests.map(r => r.requestId);

  const results = await Promise.all(requests.map(r => r.promise));

  // 요청이 취소되었거나 컴포넌트가 언마운트된 경우
  if (!canvasRef.value) return;

  // 최신 요청과 ID가 일치하는지 확인
  const isMatch = currentRequestIds.every((id, idx) => id === requests[idx].requestId);
  if (!isMatch) {
    results.forEach(res => {
      if (res && res.bitmap) res.bitmap.close();
    });
    return;
  }

  currentRequestIds = [];

  // 일반 canvas에 ImageBitmap 그리기
  const canvas = canvasRef.value;
  canvas.width = props.chunkWidth;
  canvas.height = 100;
  
  // 성공적으로 그렸을 때만 시각적 크기/위치를 업데이트하여 찌그러짐 방지
  renderedWidth.value = props.chunkWidth;
  renderedLeft.value = props.chunkLeft;
  renderedAudioStartMs.value = props.clip.audioStartMs;

  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    results.forEach((res, index) => {
      if (res && res.bitmap) {
        ctx.drawImage(res.bitmap, 0, index * channelHeight);
        res.bitmap.close(); // ImageBitmap 메모리 해제
      }
    });
  }
};

const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible') {
    requestRenderDebounced();
  }
};

// 줌이나 데이터가 변경될 때 다시 그리기 (리사이즈 시 렉 방지를 위한 디바운스)
watch(
  () => [trackStore.pixelPerBar, props.clip.duration, props.chunkWidth, props.audioKey],
  () => {
    requestRenderDebounced();
  }
);

onMounted(async () => {
  await nextTick();
  if (!canvasRef.value) return;

  // IO 폭주 방지: IntersectionObserver 삭제
  // Worker Pool이 렌더링 부하를 제어하므로 마운트 시 즉시 비동기 렌더 요청
  requestRenderDebounced();
  
  document.addEventListener('visibilitychange', handleVisibilityChange);
});

onUnmounted(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  // 진행 중인 렌더 요청 취소
  if (currentRequestIds.length > 0) {
    currentRequestIds.forEach(id => waveformRendererPool.cancelRequest(id));
    currentRequestIds = [];
  }
});
</script>

<template>
  <canvas 
    ref="canvasRef"
    class="absolute top-0 h-full max-w-none origin-left"
    :style="{ 
      left: `${renderedLeft}px`, 
      width: `${renderedWidth}px`,
      transform: `translateX(${visualTransformX}px)`
    }"
  ></canvas>
</template>

<style scoped>
@keyframes smoothAppear {
  0% { opacity: 0; }
  100% { opacity: 0.6; }
}
canvas {
  animation: smoothAppear 0.15s ease-out forwards;
}
</style>
