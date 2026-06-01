<script lang="ts">
const audioCache = new Map<string, { channels: Float32Array[], sampleRate: number }>();
</script>

<script setup lang="ts">
import { computed, onMounted, shallowRef, watch, ref } from 'vue';
import { useTrackStore } from '../store/useTrackStore';
import type { ClipUIState } from '../types';
import WaveformChunk from './WaveformChunk.vue';
import { waveformRendererPool } from '../../../core/workers/waveformRendererPool';
import { Loader2 } from 'lucide-vue-next';

const props = defineProps<{ 
  clip: ClipUIState;
}>();

const trackStore = useTrackStore();

const audioData = shallowRef<{ channels: Float32Array[], sampleRate: number } | null>(null);
const audioKey = ref(props.clip.audio?.cdnUrl || 'unknown');

// 브라우저 렌더링 한계치를 피하기 위한 최대 캔버스 너비 (안전하게 8000픽셀로 설정)
// [최적화] 기존 8000에서 2000으로 대폭 축소.
// ImageBitmap을 GPU로 업로드할 때 발생하는 메인 스레드 멈춤(Stutter) 현상을 최소화합니다.
const MAX_CANVAS_WIDTH = 2000;

// 전체 길이를 바탕으로 청크 조각들을 계산
const chunks = computed(() => {
  if (!audioData.value) return [];
  
  const totalWidth = Math.floor(props.clip.duration * trackStore.pixelPerBar);
  if (totalWidth <= 0) return [];
  
  const numChunks = Math.ceil(totalWidth / MAX_CANVAS_WIDTH);
  
  return Array.from({ length: numChunks }, (_, i) => {
    const isLast = i === numChunks - 1;
    const chunkWidth = isLast ? (totalWidth % MAX_CANVAS_WIDTH || MAX_CANVAS_WIDTH) : MAX_CANVAS_WIDTH;
    return {
      id: `${props.clip.clipId}-${i}`, // 고유 식별자
      left: i * MAX_CANVAS_WIDTH,
      width: chunkWidth
    };
  });
});

// [최적화] 스토어의 전역 AudioBuffer 캐시를 활용하여 중복 fetch+decode 완전 제거
// 재생기(Tone.Player)와 파형 렌더링이 동일한 디코딩 결과를 공유합니다.
const loadAudioData = async () => {
  if (!props.clip.audio?.cdnUrl) return;
  const audioUrl = props.clip.audio.cdnUrl;
  
  // 파형 전용 로컬 캐시 확인 (channelData 추출 결과 재사용)
  let cached = audioCache.get(audioUrl);
  
  if (!cached) {
    try {
      // 스토어의 전역 캐시에서 AudioBuffer를 가져옴 (이미 디코딩되어 있으면 즉시 반환)
      const audioBuffer = await trackStore.fetchAndCacheAudioBuffer(audioUrl);
      
      const numChannels = Math.min(2, audioBuffer.numberOfChannels); // 최대 2채널만 처리
      const channels = [];
      for (let i = 0; i < numChannels; i++) {
        channels.push(audioBuffer.getChannelData(i));
      }
      
      cached = {
        channels,
        sampleRate: audioBuffer.sampleRate
      };
      audioCache.set(audioUrl, cached);
    } catch (error) {
     // console.error("[Waveform] 오디오 데이터 로드 실패:", error);
      return;
    }
  }

  // [최적화] 메인 스레드 렌더링 병목을 없애기 위해 오디오 로드 시점에 전체 워커 풀에 배열을 단 1회 브로드캐스트 캐싱합니다.
  waveformRendererPool.broadcastCacheAudio(audioUrl, cached!.channels);
  
  audioKey.value = audioUrl;
  audioData.value = cached;
};

onMounted(() => {
 // console.log('[Waveform 🔍] onMounted - clipId:', props.clip.clipId, 'cdnUrl:', props.clip.audio?.cdnUrl || '(비어있음)');
  loadAudioData();
});

// cdnUrl이 비동기로 나중에 채워지는 경우(다른 사용자의 CLIP_CREATE 수신 시)
// URL이 빈 문자열 → 실제 URL로 변경될 때 파형 데이터를 다시 로딩
watch(() => props.clip.audio?.cdnUrl, (newUrl, oldUrl) => {
  if (newUrl && newUrl !== oldUrl && !audioData.value) {
    loadAudioData();
  }
});

</script>

<template>
  <div class="pointer-events-none absolute inset-0 h-full w-full">
    <!-- 파형 렌더링 영역 (mix-blend-screen 적용, 좌측은 밝게, 우측은 어둡게 마스킹) -->
    <div v-if="audioData" 
         class="absolute inset-0 h-full w-full mix-blend-screen"
         style="mask-image: linear-gradient(to right, rgba(0,0,0,1) calc(var(--playhead-px, 0px) - var(--clip-left-px, 0px)), rgba(0,0,0,0.4) calc(var(--playhead-px, 0px) - var(--clip-left-px, 0px))); -webkit-mask-image: linear-gradient(to right, rgba(0,0,0,1) calc(var(--playhead-px, 0px) - var(--clip-left-px, 0px)), rgba(0,0,0,0.4) calc(var(--playhead-px, 0px) - var(--clip-left-px, 0px)));"
    >
    <WaveformChunk
      v-for="chunk in chunks"
      :key="chunk.id"
      :clip="clip"
      :audio-data="audioData"
      :audio-key="audioKey"
      :chunk-left="chunk.left"
      :chunk-width="chunk.width"
    />
    </div>
    
    <!-- 로딩 스피너 영역 (독립적인 스타일, 높은 z-index) -->
    <div v-else class="absolute inset-0 flex items-center justify-center z-50 bg-black/60 rounded text-white font-bold text-xs gap-2">
      <Loader2 class="h-6 w-6 animate-spin text-white drop-shadow-lg" />
      <span>로딩중...</span>
    </div>
  </div>
</template>