<script setup lang="ts">
import {ref, onMounted, onUnmounted} from 'vue';
import { useTrackStore } from '../store/useTrackStore';
import * as Tone from 'tone';
import LoopMarker from './LoopMarker.vue';

// 트랙 스토어에서 타임라인 상태와 픽셀 계산 사용
const trackStore = useTrackStore();

//1.타임라인 넒이 영역을 가져오기 위한 Ref
const timelineCanvasRef = ref<HTMLElement | null>(null);

//드래그 중인지 상태를 추적
const isScrubbing = ref(false);

//드래그 최적화를 위한 렌더링 프레임 변수
let rafId : number | null = null;

// 2. 마우스의 X 좌표를 '마디(Bar)' 단위로 변환해 스토어에 업데이트하는 함수
const updatePlayhead = (clientX: number) => {
  if(!timelineCanvasRef.value) return;

  //요소의 현재 화면상 위치와 크기를 가져옴
  const rect = timelineCanvasRef.value.getBoundingClientRect();

  //마우스의 절대 좌표에서 도화지의 왼쪽 시작점을 빼서 '도화지 내부의 X 픽셀을 구함'
  const xPositionPx = (clientX - rect.left) / trackStore.workspaceZoom;

  //픽셀을 다시 마디로 전환(예 120px 위치 / 1 마디당 120px = 1마디)
  let newPositionBar = xPositionPx / trackStore.pixelPerBar;

  //재생바가 0마디 이전으로 가거나, 전체 마디 수를 뚤고 나가 않도록 가둔다. (clamp)
  newPositionBar = Math.max(0, Math.min(newPositionBar, trackStore.projectInfo.totalBarCount));

  //반응형으로 인해 재생바 UI가 즉시 이동 (스토어 업데이트)
  trackStore.playheadPosition = newPositionBar;

  //오디오 엔진 시간 동기화
try {
    // 스토어에 이미 계산된 안전한 computed 값을 사용하여 NaN(에러) 방지
    const exactTime = newPositionBar * trackStore.secondsPerBar;
    if (!isNaN(exactTime) && isFinite(exactTime)) {
      Tone.getTransport().seconds = exactTime;
    }
  } catch (e) {
   // console.warn("오디오 엔진 시간 동기화 중 에러 방어:", e);
  }

}


//마우스 조작 이벤트 헨들러

//눈금을 더블클릭 했을때 해당 위치로 이동하도록 하는 함수
const onClick = (e: MouseEvent) => {
  e.stopPropagation(); // 부모의 클릭 해제(deselect) 이벤트와 충돌 차단
  updatePlayhead(e.clientX);
};

//마우스 왼쪽 버튼을 누르는 순간 단 한번 발생
const onPointerDown = (e: PointerEvent) => {
  //마우스 좌클릭(버튼 번호 0)일때만 작동하도록 방어
  //마우스 우클릭이나 휠을 방어
  if(e.button !== 0) return;

  e.stopPropagation(); // 부모의 클릭 해제(deselect) 이벤트와 충돌 차단
  
  //드래그모드 시작임
  isScrubbing.value = true;

  //브라우저 밖으로 마우스가 나가도 이벤트를 놓지지 않도록 요소를 묶어둔다.
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);

  //클릭한 즉시 그 자리로 재생바가 이동된다.
  updatePlayhead(e.clientX);
};

//드래그 중 (마우스를 누른 채로 이동하는 동안 계속해서 발생)
const onPointerMove = (e: PointerEvent) => {
  //드래그 중(마우스 버튼을 누른 상태)이 아닐 때, 혹은 브라우저 밖으로 나갔다면 중지
  if(!isScrubbing.value || e.buttons === 0) {
    isScrubbing.value = false;
    return;
  }

  //화면그리기 요청 통제
  //모니터가 그릴 준비가 된 타이밍(60fps)에 맞춰서 한 번만 계산
  if(rafId){
    cancelAnimationFrame(rafId);
  }

  rafId = requestAnimationFrame(()=>{
    updatePlayhead(e.clientX);
    rafId = null; // 실행 후에는 변수를 비워준다.
  });
};

//드래그 종료 시점
const onPointerUp = (e:PointerEvent) => {
  if(!isScrubbing.value) return;
  isScrubbing.value = false;

  //찌꺼기 렌더링 요청 취소
  if(rafId){
    cancelAnimationFrame(rafId);
    rafId = null;
  }

  try{
    //마우스 캡처 해제
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }catch(error){
   // console.error(error);
  }
};

// ==========================================
// 스크롤 로직 추가
// ==========================================
const handleWheel = (e: WheelEvent) => {
  // 컨트롤이나 메타 키를 누른 상태에서 휠을 굴릴 때만 줌으로 동작
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault(); // 브라우저 기본 줌 방지
    
    // 가장 가까운 스크롤 컨테이너(ProjectTimeline.vue에 있는 최상단 div)를 찾습니다.
   const container = document.querySelector('.custom-scrollbar') as HTMLElement;
    if (!container) return;

    // 1. 마우스의 컨테이너 내 상대적 X 픽셀 위치
    const rect = container.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left) / trackStore.workspaceZoom;

    // 2. 줌하기 전의 스크롤 위치와 마디당 픽셀 가져오기
    const oldScrollLeft = container.scrollLeft;
    const oldPixelPerBar = trackStore.pixelPerBar;

    // 3. 현재 마우스가 위치한 음악적 타임라인 위치(마디) 계산
    const mouseBarPos = (oldScrollLeft + mouseX) / oldPixelPerBar;

    // 4. 스토어의 줌 배율 업데이트
    trackStore.updateZoom(e.deltaY);

 // 새로운 배율 적용 후 스크롤 위치 보정
    const newPixelPerBar = trackStore.pixelPerBar;
    container.scrollLeft = (mouseBarPos * newPixelPerBar) - mouseX;
  }
};


onMounted(() => {
  // 윈도우 전체에 휠 이벤트를 감지하여 줌 기능 구현
  window.addEventListener('wheel', handleWheel, {passive: false});
});

onUnmounted(() => {
  // 컴포넌트 파괴 시 이벤트 리스너 제거 (메모리 누수 방지)
  window.removeEventListener('wheel', handleWheel,);
});

</script>

<template>
  <div 
    aria-label="타임라인 눈금자 및 재생 바 영역"
    class="sticky top-0 z-40 flex h-7 border-b border-border bg-card select-none w-max min-w-full"
    style="will-change: transform;"
  >
    <div 
      aria-label="트랙 헤더 정렬 공간"
      class="sticky left-0 z-50 w-[224px] shrink-0 border-r border-border bg-card"
      style="will-change: transform;"
    ></div>

    <div 
      aria-label="시간 축 탐색 영역"
      class="relative shrink-0 cursor-pointer touch-none"
      :style="{ width: `${trackStore.totalTimelineWidth}px` }"
      @click.stop="onClick"
      @pointerdown.stop
    >
      
      <div
        ref="timelineCanvasRef"
        class="relative h-full w-full"
      >
        <div 
          v-for="bar in trackStore.displayBarCount" 
          :key="bar"
          class="absolute top-0 h-full border-l border-white/5"
          :style="{ left: `${(bar - 1) * trackStore.pixelPerBar}px` }"
        >
          <span 
            v-if="(bar - 1) % trackStore.barNumberStep === 0" 
            class="absolute left-1.5 bottom-0 font-mono text-[10px] uppercase tracking-widest text-muted-foreground"
          >
            {{ bar }}
          </span>

      <template v-if="trackStore.subDivision > 1">
            <div
              v-for="sub in trackStore.subDivision - 1"
              :key="sub"
              class="absolute bottom-0 border-l border-white/5"
              :style="{ 
                left: `${(sub * trackStore.pixelPerBar) / trackStore.subDivision}px`,
                height: sub % (trackStore.subDivision / trackStore.projectInfo.timeSigNumerator) === 0 ? '40%' : '20%'
              }"
            ></div>
          </template>
        </div>

        <!-- 구간 반복(Loop) 마커 (분리된 컴포넌트 사용) -->
        <LoopMarker />

        <div 
          aria-label="현재 재생 위치 표시 바"
          class="playhead-line absolute top-0 bottom-0 z-40 w-3.5 cursor-pointer pointer-events-auto"
          style="transform: translate3d(calc(var(--playhead-px, 0px) - 50%), 0, 0);"
          @pointerdown.stop="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
        >
          <div class="absolute top-0 bottom-[10px] left-1/2 -translate-x-1/2 w-1px bg-white/20 pointer-events-none"></div>

          <div
            class="absolute bottom-0 left-0 w-full h-2.5 bg-primary pointer-events-none"
            style="
              clip-path: polygon(0% 0%, 100% 0%, 50% 100%); 
              filter: drop-shadow(0 0 6px hsl(var(--primary) / 0.8));
            "
          ></div>
          
        </div>

      </div>
    </div>
  </div>
</template>