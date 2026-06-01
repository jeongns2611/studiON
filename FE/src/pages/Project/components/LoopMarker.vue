<script setup lang="ts">
import { ref } from 'vue';
import { useTrackStore } from '../store/useTrackStore';
import { useAutoScroll } from '../composables/useAutoScroll';

const trackStore = useTrackStore();
const { startAutoScroll, updatePointer, stopAutoScroll } = useAutoScroll();

const dragState = ref<{ 
  type: 'start' | 'end' | 'move' | null, 
  startX: number, 
  initialStartBar: number, 
  initialEndBar: number, 
  startScrollLeft: number 
}>({ 
  type: null, 
  startX: 0, 
  initialStartBar: 0, 
  initialEndBar: 0, 
  startScrollLeft: 0 
});

let currentClientX = 0;

const updateLoopPosition = () => {
  if (!dragState.value.type) return;
  
  const scrollContainer = document.querySelector('.custom-scrollbar') as HTMLElement;
  const currentScrollLeft = scrollContainer ? scrollContainer.scrollLeft : 0;
  
  // 마우스의 이동 거리 + 화면(스크롤)의 이동 거리 합산 (크롬 zoom 특성상 scrollLeft도 시각적 픽셀을 반환하므로 같이 나눔)
  const dx = ((currentClientX - dragState.value.startX) + (currentScrollLeft - dragState.value.startScrollLeft)) / trackStore.workspaceZoom;
  const dBar = dx / trackStore.pixelPerBar;
  
  // 현재 설정된 그리드(SubDivision) 단위 스냅
  const snapRes = 1 / (trackStore.subDivision || 4);
  
  if (dragState.value.type === 'start') {
    let newBar = dragState.value.initialStartBar + dBar;
    newBar = Math.round(newBar / snapRes) * snapRes;
    newBar = Math.max(0, Math.min(newBar, trackStore.loopEndBar - snapRes));
    trackStore.loopStartBar = newBar;
  } else if (dragState.value.type === 'end') {
    let newBar = dragState.value.initialEndBar + dBar;
    newBar = Math.round(newBar / snapRes) * snapRes;
    newBar = Math.max(trackStore.loopStartBar + snapRes, Math.min(newBar, trackStore.projectInfo.totalBarCount));
    trackStore.loopEndBar = newBar;
  } else if (dragState.value.type === 'move') {
    const duration = dragState.value.initialEndBar - dragState.value.initialStartBar;
    let newStart = dragState.value.initialStartBar + dBar;
    newStart = Math.round(newStart / snapRes) * snapRes;
    
    // 화면 밖으로 나가지 않도록 Clamp
    newStart = Math.max(0, Math.min(newStart, trackStore.projectInfo.totalBarCount - duration));
    
    trackStore.loopStartBar = newStart;
    trackStore.loopEndBar = newStart + duration;
  }
};

const onPointerDown = (e: PointerEvent, type: 'start' | 'end' | 'move') => {
  e.stopPropagation();
  if (e.button !== 0) return; // 좌클릭만 허용
  
  const scrollContainer = document.querySelector('.custom-scrollbar') as HTMLElement;
  const scrollLeft = scrollContainer ? scrollContainer.scrollLeft : 0;
  
  currentClientX = e.clientX;
  
  dragState.value = {
    type,
    startX: e.clientX,
    initialStartBar: trackStore.loopStartBar,
    initialEndBar: trackStore.loopEndBar,
    startScrollLeft: scrollLeft
  };
  
  // 오토스크롤 시작
  startAutoScroll(e.clientX, e.clientY, updateLoopPosition, { enableVertical: false });
  
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
};

const onPointerMove = (e: PointerEvent) => {
  if (!dragState.value.type) return;
  
  currentClientX = e.clientX;
  updatePointer(e.clientX, e.clientY); // 오토스크롤 엔진에 최신 위치 전달
  updateLoopPosition();
};

const onPointerUp = () => {
  dragState.value.type = null;
  stopAutoScroll();
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
  window.removeEventListener('pointercancel', onPointerUp);
};
</script>

<template>
  <div 
    v-if="trackStore.isLoopActive"
    class="absolute top-0 bottom-0 bg-pink-500/20 border-x-2 border-pink-500 z-30"
    :style="{
      left: `${trackStore.loopStartBar * trackStore.pixelPerBar}px`,
      width: `${(trackStore.loopEndBar - trackStore.loopStartBar) * trackStore.pixelPerBar}px`
    }"
  >
    <!-- 본체(가운데) 드래그 핸들 -->
    <div 
      class="absolute inset-0 cursor-grab active:cursor-grabbing hover:bg-pink-400/10 pointer-events-auto"
      @pointerdown.stop="(e) => onPointerDown(e, 'move')"
    ></div>
    
    <!-- 왼쪽 조절 핸들 -->
    <div 
      class="absolute top-0 bottom-0 -left-1.5 w-3 cursor-ew-resize hover:bg-pink-400/50 pointer-events-auto"
      @pointerdown.stop="(e) => onPointerDown(e, 'start')"
    ></div>
    
    <!-- 오른쪽 조절 핸들 -->
    <div 
      class="absolute top-0 bottom-0 -right-1.5 w-3 cursor-ew-resize hover:bg-pink-400/50 pointer-events-auto"
      @pointerdown.stop="(e) => onPointerDown(e, 'end')"
    ></div>
  </div>
</template>
