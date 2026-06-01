<!--스토어에서 트랙 목록을 가져와서 세로로 나열하는 역할을 수행한다.-->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {useTrackStore} from '../store/useTrackStore'
import TrackItem from './TrackItem.vue'
import type { TrackMeasureCommentGroup } from '../types/comment.types'

//1.스토어에서 트랙 데이터를 꺼내옴
const trackStore = useTrackStore();

// ==========================================
// 가상 스크롤링 (Virtual Scrolling) 로직
// ==========================================
const scrollTop = ref(0);
const containerHeight = ref(1000); // 임시 기본값
const trackHeight = 100; // 트랙의 대략적인 높이 (픽셀)

let scrollContainer: Element | null = null;
let lastScrollTop = 0;
let scrollRafId: number | null = null;

const handleScroll = () => {
  // rAF 스로틀링: 프레임당 최대 1회만 처리하여 스크롤 렉 방지
  if (scrollRafId) return;
  scrollRafId = requestAnimationFrame(() => {
    scrollRafId = null;
    if (!scrollContainer) return;
    const newScrollTop = scrollContainer.scrollTop;
    // 세로 스크롤이 변하지 않았으면(가로 스크롤만 한 경우) 가상 스크롤 재계산 생략
    if (newScrollTop === lastScrollTop) return;
    lastScrollTop = newScrollTop;
    scrollTop.value = newScrollTop;
  });
};

onMounted(() => {
  scrollContainer = document.querySelector('.custom-scrollbar');
  if (scrollContainer) {
    containerHeight.value = scrollContainer.clientHeight;
    scrollContainer.addEventListener('scroll', handleScroll, { passive: true });
    // 초기 렌더링 시 스크롤 위치 동기화
    handleScroll();
  }
});

onUnmounted(() => {
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll);
  }
  if (scrollRafId) {
    cancelAnimationFrame(scrollRafId);
    scrollRafId = null;
  }
});

const visibleTracksInfo = computed(() => {
  const total = trackStore.trackList.length;
  if (total === 0) return { list: [], paddingTop: 0, paddingBottom: 0 };
  
  const startIdx = Math.floor(scrollTop.value / trackHeight);
  // 부드러운 스크롤을 위해 위아래로 3개씩 버퍼 렌더링
  const buffer = 3; 
  const safeStart = Math.max(0, startIdx - buffer);
  const endIdx = Math.ceil((scrollTop.value + containerHeight.value) / trackHeight);
  const safeEnd = Math.min(total, endIdx + buffer);

  return {
    // 렌더링할 트랙 목록과 원본 인덱스
    list: trackStore.trackList.slice(safeStart, safeEnd).map((track, i) => ({ 
      track, 
      originalIndex: safeStart + i 
    })),
    // 렌더링 생략된 상하단 공간을 패딩으로 채워 스크롤바 크기 유지
    paddingTop: safeStart * trackHeight,
    paddingBottom: (total - safeEnd) * trackHeight
  };
});

// 드래그 앤 드롭 상태 관리
const draggedTrackId = ref<number | null>(null);
const dragOverIndex = ref<number | null>(null);

const onDragStart = (e: DragEvent, trackId: number) => {
  draggedTrackId.value = trackId;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move';
    setTimeout(() => {
      const target = e.target as HTMLElement;
      if (target) target.classList.add('opacity-50');
    }, 0);
  }
};

const onDragEnter = (e: DragEvent, originalIndex: number) => {
  e.preventDefault();
  dragOverIndex.value = originalIndex;
};

const onDragOver = (e: DragEvent) => {
  e.preventDefault();
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'move';
  }
};

const onDrop = (e: DragEvent, originalIndex: number) => {
  e.preventDefault();
  if (draggedTrackId.value !== null && draggedTrackId.value !== trackStore.trackList[originalIndex].trackId) {
    trackStore.reorderTrack(draggedTrackId.value, originalIndex);
  }
  
  draggedTrackId.value = null;
  dragOverIndex.value = null;
};

const onDragEnd = (e: DragEvent) => {
  draggedTrackId.value = null;
  dragOverIndex.value = null;
  const target = e.target as HTMLElement;
  if (target) target.classList.remove('opacity-50');
};

const props = defineProps<{
  hoveredMeasure: number | null
  hoveredTrackId: string | null
  commentedGroups: TrackMeasureCommentGroup[]
}>()

const emit = defineEmits<{
  'hover-measure': [payload: { trackId: string | null; measure: number | null }]
  'submit-inline-comment': [payload: {
    trackId: string
    trackName: string
    measure: number
    content: string
    parentCommentId?: number | null
    mentionedUserIds: number[]
  }]
  'resolve-comment': [payload: {
    trackId: string
    measure: number
  }]
  'delete-comment': [payload: {
    commentId: number
  }]
}>()

</script>

<template>
  <section aria-label="트랙 리스트 영역" class="flex flex-col bg-background relative">
    
    <!--일반 트랙 목록 렌더링 (가상 스크롤 적용)-->
    <div 
      v-if="trackStore.trackList.length > 0" 
      aria-label="트랙 목록" 
      class="flex flex-col relative"
      :style="{ paddingTop: `${visibleTracksInfo.paddingTop}px`, paddingBottom: `${visibleTracksInfo.paddingBottom}px` }"
    >
      <slot name="overlays"></slot>
      <!-- 드래그 앤 드롭 이벤트 연결 -->
      <div
        v-for="item in visibleTracksInfo.list"
        :key="item.track.trackId"
        @dragenter="onDragEnter($event, item.originalIndex)"
        @dragover="onDragOver"
        @drop="onDrop($event, item.originalIndex)"
        class="transition-transform duration-200"
        :class="{
          'border-t-2 border-t-primary': dragOverIndex === item.originalIndex && draggedTrackId !== item.track.trackId
        }"
      >
        <TrackItem
          :track="item.track"
          :is-master="false"
          :hovered-measure="props.hoveredMeasure"
          :hovered-track-id="props.hoveredTrackId"
          :commented-groups="props.commentedGroups"
          @hover-measure="emit('hover-measure', $event)"
          @submit-inline-comment="emit('submit-inline-comment', $event)"
          @resolve-comment="emit('resolve-comment', $event)"
          @delete-comment="emit('delete-comment', $event)"
          @dragstart="onDragStart($event, item.track.trackId)"
          @dragend="onDragEnd"
        />
      </div>

    </div>
    
    <div 
      v-else 
      aria-label="빈 트랙 안내"
      class="flex h-32 items-center justify-center border-b border-border bg-muted/20 text-sm text-muted-foreground"
    >
      프로젝트에 생성된 트랙이 없습니다. + 버튼을 눌러 트랙을 추가하세요.
    </div>

    <!--트랙 추가 버튼-->
    <div class="flex border-b border-border group w-max min-w-full h-[100px]">
      <div class="sticky left-0 z-60 flex w-[224px] shrink-0 items-center justify-center border-r border-border bg-[#1c1c1c]" style="will-change: transform;">
        <button 
          @click="trackStore.addTrack" 
          class="flex items-center gap-2 rounded-md border border-white/20 px-6 py-2.5 text-sm font-semibold text-gray-300 hover:text-white hover:bg-white/10 hover:border-white/40 transition-all duration-200"
        >
          + 트랙 추가
        </button>
      </div>
      <!-- 빈 타임라인 배경 -->
      <div class="relative flex-1 bg-transparent pointer-events-none"></div>
    </div>

  </section>
</template>

<style scoped>

</style>