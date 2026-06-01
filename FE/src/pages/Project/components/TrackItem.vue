<script setup lang="ts">
import {ref, computed, inject, type Ref, nextTick} from 'vue';
import type { TrackUIState, ClipUIState } from '../types';
import { Pencil, VolumeX, Volume2 } from 'lucide-vue-next';
import { useTrackStore } from '../store/useTrackStore'; //트랙스토얼를 임포트해서 타임라인 길이를 맞춘다.
import { useAlertStore } from '@/shared/stores/useAlertStore';
import WaveformWebGL from './WaveformWebGL.vue'; //파형 컴포넌트 불러오기
import {UploadIcon, ScissorsIcon, ClipboardIcon, TrashIcon, CopyIcon, CopyPlusIcon, Lock, Unlock, Loader2, GripVertical, Sparkles} from 'lucide-vue-next';
import type { TrackMeasureCommentGroup } from '../types/comment.types'
import TrackCommentLayer from './TrackCommentLayer.vue'
import FileSizeWarningModal from './FileSizeWarningModal.vue'

// 트랙리스트로부터 트랙 1개의 데이터를 전달받음
const props = defineProps<{
  track: TrackUIState
  isMaster?: boolean //마스터 트랙인지 확인하는 용도
  hoveredMeasure?: number | null
  hoveredTrackId?: string | null
  commentedGroups?: TrackMeasureCommentGroup[]
}>()

//스토어 사용
const trackStore = useTrackStore();
const alertStore = useAlertStore();

const aiAnalysisItems = inject<Ref<any[]>>('aiAnalysisItems')
const activeAiAnalysisId = inject<Ref<string | number | null>>('activeAiAnalysisId')
const aiAnalyzing = inject<Ref<boolean>>('aiAnalyzing')

const isAiLocked = (clip: ClipUIState) => {
  if (aiAnalyzing?.value) return true;
  if (!aiAnalysisItems?.value || aiAnalysisItems.value.length === 0) return false;

  const clipStartMs = clip.start * trackStore.secondsPerBar * 1000;
  const clipEndMs = (clip.start + clip.duration) * trackStore.secondsPerBar * 1000;

  return aiAnalysisItems.value.some(conflict => {
    if (String(conflict.targetTrackId) !== String(props.track.trackId)) return false;
    return clipStartMs < conflict.endMs && clipEndMs > conflict.startMs;
  });
}

const getConflictLeft = (conflict: any) => {
  const startBarFloat = conflict.startMs / (trackStore.secondsPerBar * 1000)
  return startBarFloat * trackStore.pixelPerBar
}

const getConflictWidth = (conflict: any) => {
  const startBarFloat = conflict.startMs / (trackStore.secondsPerBar * 1000)
  const endBarFloat = Math.max(conflict.endMs / (trackStore.secondsPerBar * 1000), startBarFloat + 0.25)
  return Math.max((endBarFloat - startBarFloat) * trackStore.pixelPerBar, 8)
}

// 뷰포트 내에 존재하는 클립만 필터링하여 렌더링하는 가로 가상 스크롤 적용 (정렬 포함)
const visibleClips = computed(() => {
  const left = trackStore.viewportLeft;
  const right = trackStore.viewportRight;
  const buffer = 1000; // 좌우 1000px 여유 공간
  
  return [...props.track.clips]
    .filter(clip => {
      const clipLeft = clip.start * trackStore.pixelPerBar;
      const clipRight = clipLeft + (clip.duration * trackStore.pixelPerBar);
      return clipRight >= (left - buffer) && clipLeft <= (right + buffer);
    })
    // 클립이 겹칠 경우 나중에 생성된 클립(clipId가 큼)이 뒤에(아래에) 깔리도록 내림차순 정렬
    .sort((a, b) => b.clipId - a.clipId);
});



// ==========================================
// 클립 드래그 앤 드롭 로직
// ==========================================
const activeClip = ref<ClipUIState | null>(null); //현재 드래그 중인 클립 상태
const startMouseX = ref(0); //클립 드래그를 시작했을때 마우스 x 좌표
const startClipBar = ref(0); //클립 드래그를 시작했을때 클립의 시작 바 위치

//세로 이동을 위한 변수
const startMouseY = ref(0); //클립을 잡기 직전 마우스 y 좌표
const dragoffsetY = ref(0); //클립을 잡고 움직이기 시작한 지점으로부터 현재 마우스가 얼마나 아래/위에 있는지를 픽셀로 저장한 값

//오토스크롤 위한 추가 변수들
const startScrollLeft = ref(0); //드래그 시작 시점의 스크롤 위치
const startScrollTop = ref(0); //드래그 시작 시점의 세로 스크롤 위치
let scrollContainer: HTMLElement | null = null; //스크롤되는 부모 요소
let currentClientX = 0; //현재 마우스 X 좌표 (루프에서 감시용)
let currentClientY = 0; //현재 마우스 Y 좌표 (수직 오토스크롤 감시용)
let autoScrollRafId: number | null = null; // 오토스크롤 애니메이션 ID

//클립 위치 계산 함수(마우스 이동 + 스크롤 이동 동시 반영)
function updateClipPosition() {
  if(!activeClip.value || !scrollContainer) return;

  const currentScrollLeft = (scrollContainer as HTMLElement).scrollLeft; //현재 스크롤량 가져오기
  const currentScrollTop = (scrollContainer as HTMLElement).scrollTop; //현재 세로 스크롤량 가져오기

  const deltaX = ((currentClientX - startMouseX.value) + (currentScrollLeft - startScrollLeft.value)) / trackStore.workspaceZoom; //이동거리 계산
  dragoffsetY.value = ((currentClientY - startMouseY.value) + (currentScrollTop - startScrollTop.value)) / trackStore.workspaceZoom; //세로 이동값 계산

  const deltaBar = deltaX / trackStore.pixelPerBar; //이동 거리를 마디 단위로 변환
  let newStart = startClipBar.value + deltaBar; //새로운 시작점 계산

  //0마디 이전으로 뚫고 나가지 못하게 막기
  newStart = Math.max(0, newStart);
  //클립 이동시 자동처럼 붙는 기능
  const snapResolution = trackStore.subDivision; //스냅 해상도
  newStart = Math.round(newStart * snapResolution) / snapResolution; 
  
  activeClip.value.start = newStart; 
  
  //드래그가 끝나도 화면이 잘리지 않도록 필요하면 트랙을 늘리는 로직
  const clipEnd = newStart + activeClip.value.duration; 
  const currentTotalBars = trackStore.projectInfo.totalBarCount; 
  
  if(clipEnd > currentTotalBars * 0.9) { 
    trackStore.projectInfo.totalBarCount += 50; 
  }
}
  
  //마우스를 누르고 있을때 백 그라운드에서 돌아가는 오토 스크롤 엔진
 //마우스를 누르고 있을때 백 그라운드에서 돌아가는 오토 스크롤 엔진
function autoScrollLoop() {
  if((!activeClip.value && !resizeState.value.isResizing) || !scrollContainer) return; //조건이 맞지 않으면 함수 종료
  
  const EDGE_THRESHOLD = 80; //가장자리에서 80px안쪽으로 들어오면 자동 스크롤 시작
  const SCROLL_SPEED = 15; //한 프레임당 15px씩 밀어내기
  let scrolled = false; 

  //1. 오른화면 끝 도달
  if(currentClientX > window.innerWidth - EDGE_THRESHOLD){
    (scrollContainer as HTMLElement).scrollLeft += SCROLL_SPEED; 
    scrolled = true;
  }

  //2. 왼화면 끝 도달 (왼쪽 컨트롤 패널 224px 고려)
  if(currentClientX < 224 * trackStore.workspaceZoom + EDGE_THRESHOLD){
    (scrollContainer as HTMLElement).scrollLeft -= SCROLL_SPEED; 
    scrolled = true;
  }

  //3. 아래화면 끝 도달 (마스터 트랙 부근 도달 시 스크롤 되도록 200px 여유)
  if(currentClientY > window.innerHeight - 200){
    (scrollContainer as HTMLElement).scrollTop += SCROLL_SPEED;
    scrolled = true;
  }

  //4. 위화면 끝 도달 (상단 헤더 높이 등을 고려해 여유공간 120px)
  if(currentClientY < 120 + EDGE_THRESHOLD){
    (scrollContainer as HTMLElement).scrollTop -= SCROLL_SPEED;
    scrolled = true;
  }

  // 스크롤이 발생했다면, 마우스가 가만히 있어도 클립 위치를 갱신해야 함
  if (scrolled) {
    if (activeClip.value) {
      updateClipPosition(); 
    } else if (resizeState.value.isResizing) {
      updateResizePosition();
    }
  }

  // 드래그 중이면 끊임없이 다음 프레임 예약
  autoScrollRafId = requestAnimationFrame(autoScrollLoop);
}

// ==========================================
// 3. 마우스 조작 이벤트 핸들러
// ==========================================

// 클립 드래그(마우스 다운) 시작
const onClipPointerDown = (e: PointerEvent, clip: ClipUIState) => {
  if (clip.isLocked || isAiLocked(clip)) return;
  if(props.isMaster) return; // 마스터 트랙에선 아무것도 못하게 막기
  if(e.button !== 0) return; // 좌클릭만 허용하기
  // 누군가(다른 사람) 이미 잠근 클립이면 아예 건드리지도 못하게 튕겨냄
  if(clip.isLocked) {
      alertStore.showAlert("다른 사용자가 편집 중인 클립입니다.", "warning"); // 시각적 피드백
      return; 
  }
  e.stopPropagation(); //이벤트를 부모로 전달 안하기 (트랙의 빈 공간 클릭 방지)
  e.preventDefault(); //이벤트를 브라우저로 전달 안하기 (새 탭으로 열기 방지)클립을 잡을 때 트랙 전체가 드래그 되는 현상 차단
  // 백엔드에 클립 잠금(Lock) 요청 — 다른 사용자가 동시에 편집 못 하게
  trackStore.lockClip(clip.clipId, props.track.trackId);

  activeClip.value = clip; //현재 드래그하는 클립 상태로 저장
  startMouseX.value = e.clientX; //드래그 시작점의 x좌표 기록
  startMouseY.value = e.clientY; //드래그 시작점의 y좌표 기록
  
  startClipBar.value = clip.start; //드래그 시작점의 바 위치 기록
  dragoffsetY.value = 0; //차이 초기화
  clip.isDragging = true; // 시각적으로 피드백을 주기 위한 상태 변경

  // 가장 가까운 스크롤 영역('.overflow-auto')을 찾아 오토 스크롤 셋팅
  scrollContainer = document.querySelector('.custom-scrollbar') as HTMLElement;
  startScrollLeft.value = scrollContainer ? scrollContainer.scrollLeft : 0;
  startScrollTop.value = scrollContainer ? scrollContainer.scrollTop : 0;
  currentClientX = e.clientX; // 좌표 초기화
  currentClientY = e.clientY;

  // 오토 스크롤 엔진 가동
  if (autoScrollRafId) cancelAnimationFrame(autoScrollRafId);
  autoScrollRafId = requestAnimationFrame(autoScrollLoop);

  //마우스가 브라우저를 벗어나도 이벤트를 놓지지 않도록 잡음
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
};

  //2.클립을 잡고 움직일때
  const onClipPointerMove = (e: PointerEvent) => {
    if(!activeClip.value || !activeClip.value.isDragging) return;

    //1. 엔진이 알 수 있게 마우스 좌표 최신화
    currentClientX = e.clientX;
    currentClientY = e.clientY;


    //2. 업데이트 클립으로 위치 갱신
    updateClipPosition();
  };

  //3.클립을 놓았을때 (Pointer Up)
  const onClipPointerUp = (e: PointerEvent) => {
    if(!activeClip.value) return;
    const currentClipId = activeClip.value.clipId;
    //오토 스크롤 엔진 종료
    if(autoScrollRafId) {
      cancelAnimationFrame(autoScrollRafId);
      autoScrollRafId = null;
    }
    //트랙간 이동 -> 마우스 커서 위치에 있는 모든 DOM요소를 뚫고 지나가서 실제 위에 있는 요소 찾기
    const elementsUnderMouse = document.elementsFromPoint(e.clientX, e.clientY);
    //검사된 요소 중 'data-track-id'속성을 가진 트랙 박스를 찾는다 (트랙이라고 선언된 녀석 찾기)
    const targetTrackEl = elementsUnderMouse.find((el) => el.hasAttribute('data-track-id'));

    let finalTrackId = props.track.trackId; //기본은 현재 트랙 
    //만약 해당 요소를 찾았다면,
    if(targetTrackEl) {
      const targetTrackId = Number(targetTrackEl.getAttribute('data-track-id'));
      if (targetTrackId) {
      finalTrackId = targetTrackId; // 놓은 곳의 트랙 ID 타겟팅
    }
  }

    //겹침 방지로직(밀어내기 대신 원래 자리로 롤백)
    const finalTrack = trackStore.trackList.find(t => t.trackId === finalTrackId);
    let isOverlapping = false;
    const epsilon = 0.001; //소수점 오차로 인한 무한루프 방지

    if (finalTrack) {
     const activeStart = activeClip.value.start;
    const activeEnd = activeStart + activeClip.value.duration;

    // 타겟 트랙의 모든 클립을 순회하며 겹치는지 단 한 번만 검사합니다.
    for (const otherClip of finalTrack.clips) {
      // 자기 자신은 비교 대상에서 제외
      if (otherClip.clipId === activeClip.value.clipId) continue;

      const existingStart = otherClip.start;
      const existingEnd = otherClip.start + otherClip.duration;

      // 겹침 판별 공식: (A의 시작 < B의 끝) && (A의 끝 > B의 시작)
      if (activeStart < existingEnd - epsilon && activeEnd > existingStart + epsilon) {
        isOverlapping = true;
        break; // 하나라도 겹치면 즉시 검사 종료
      }
    }
  }

  // 결과 처리: 겹쳤다면 원상복구, 아니면 이동 확정
  if (isOverlapping) {
   // console.log("클립이 다른 클립과 겹쳐서 원래 자리로 돌아갑니다.");
    
    // 1. 위치 롤백 (드래그 시작 지점으로)
    activeClip.value.start = startClipBar.value; 
    
    // 2. 트랙 롤백 (트랙 이동도 무효화)
    finalTrackId = props.track.trackId; 

    // 오디오 동기화를 위해 제자리 통신(기존 위치)을 쏴주거나, 프론트에서만 조용히 돌려놓습니다.
    trackStore.resyncClip(activeClip.value.clipId, startClipBar.value);

  } else {
    // 겹치지 않았다면 트랙 이동 및 서버 확정 진행
    if (finalTrackId !== props.track.trackId) {
      trackStore.moveClipToTrack(activeClip.value.clipId, props.track.trackId, finalTrackId);
    }
    
    // 서버 통신 시 부동소수점 오차로 인한 백엔드 충돌 방지
    const safeStart = Number(activeClip.value.start.toFixed(3));
    activeClip.value.start = safeStart; // 로컬 상태도 안전한 값으로 보정
    
    // 서버에 통신을 보내서 이동 확정
    trackStore.confirmMoveClip(activeClip.value.clipId, finalTrackId, safeStart, props.track.trackId, startClipBar.value);
    // 이동한 당사자의 오디오도 새 위치에 맞춰 재동기화 (브로드캐스트는 위치 동일 시 건너뜀)
    trackStore.resyncClip(activeClip.value.clipId, safeStart);
  }

  // Move/롤백 통신 이후에 Unlock을 보내야 백엔드가 정상적으로 처리함
  trackStore.unlockClip(currentClipId, props.track.trackId);

  // console.log(`\n========================================`);
  // console.log(`[UI 드래그 종료] 클립 ID: ${activeClip.value.clipId}`);
  // console.log(`[UI 드래그 종료] 드롭된 마디 위치: ${activeClip.value.start}m`);
  // console.log(`========================================`);

  activeClip.value.isDragging = false; // 드래그 끝
  activeClip.value = null; // 클립 해제
  dragoffsetY.value = 0; // 세로 이동값 초기화

  try {
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  } catch (err) {
   // console.warn("releasePointerCapture 오류 발생", err);
  }

  // 드래그가 끝나면 이벤트 리스너 해제
  (e.currentTarget as HTMLElement).onpointerup = null;
  (e.currentTarget as HTMLElement).onpointermove = null;
};

  // ==========================================
// 클립 리사이즈(Trim) 로직
// ==========================================
const resizeState = ref({
  clip: null as ClipUIState | null,
  side: '' as 'left' | 'right',
  startX: 0,
  origStart: 0,
  origDuration: 0,
  origAudioStartMs: 0,
  origAudioDurationMs: 0,
  isResizing: false
});

// 리사이즈 마우스 다운 (가장자리 6-dot 핸들)
const onResizePointerDown = (e: PointerEvent, clip: ClipUIState, side: 'left' | 'right') => {
  if (clip.isLocked || isAiLocked(clip)) return;
  if(props.isMaster) return; // 마스터 트랙에선 아무것도 못하게 막기
  if(e.button !== 0) return;
  if(clip.isLocked) return; //클립이 잠겨있으면 리사이즈 금지
  e.stopPropagation(); // 일반 클립 이동(드래그) 이벤트 방지
  e.preventDefault(); // 클립을 잡을 때 트랙 전체가 드래그 되는 현상 차단
  // 리사이즈 시작 시 클립 잠금
  trackStore.lockClip(clip.clipId, props.track.trackId);

  resizeState.value = {
    clip,
    side,
    startX: e.clientX,
    origStart: clip.start,
    origDuration: clip.duration,
    origAudioStartMs: clip.audioStartMs,
    origAudioDurationMs: clip.audioDurationMs,
    isResizing: true
  };

  // 가장 가까운 스크롤 영역('.overflow-auto')을 찾아 오토 스크롤 셋팅
  scrollContainer = document.querySelector('.custom-scrollbar') as HTMLElement;
  startScrollLeft.value = scrollContainer ? scrollContainer.scrollLeft : 0;
  currentClientX = e.clientX; // 좌표 초기화
  currentClientY = e.clientY;

  // 오토 스크롤 엔진 가동
  if (autoScrollRafId) cancelAnimationFrame(autoScrollRafId);
  autoScrollRafId = requestAnimationFrame(autoScrollLoop);

  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
};

// 리사이즈 클립 위치/길이 업데이트 함수 (마우스 이동 + 스크롤 이동 동시 반영)
function updateResizePosition() {
  if (!resizeState.value.isResizing || !resizeState.value.clip || !scrollContainer) return;

  const currentScrollLeft = (scrollContainer as HTMLElement).scrollLeft; //현재 스크롤량 가져오기
  const state = resizeState.value;
  const targetClip = state.clip as ClipUIState;
  
  // 마우스 이동 거리 + 화면 스크롤 이동 거리 합산 (크롬 zoom 특성상 scrollLeft도 시각적 픽셀을 반환하므로 같이 나눔)
  const deltaX = ((currentClientX - state.startX) + (currentScrollLeft - startScrollLeft.value)) / trackStore.workspaceZoom;
  let deltaBar = deltaX / trackStore.pixelPerBar;

  const minDuration = 0.5; // 최소 0.5마디 길이 보장
  const snapResolution = trackStore.subDivision; // 스냅 해상도

  // 음원의 전체 길이를 마디 단위로 계산 (이 길이를 넘어서 늘릴 수 없음)
  // 백엔드 데이터 누락이나 목업 클립인 경우, Infinity 대신 현재 가시적인 오디오 길이의 끝을 최대치로 사용하여 무한 드래그 버그 방지
  const totalAudioDurationMs = (targetClip.audio?.durationMs && targetClip.audio.durationMs > 0)
    ? targetClip.audio.durationMs
    : (targetClip.audioStartMs + targetClip.audioDurationMs);
  // 원본 오디오의 ms/bar 비율을 보존 (BPM 무관하게 일정)
  const msPerBar = state.origAudioDurationMs / state.origDuration;
  const maxAudioBars = totalAudioDurationMs / msPerBar;

  if (state.side === 'right') {
    // 오른쪽 리사이즈: 스냅된 새로운 끝점을 기반으로 duration 계산
    let rawNewEnd = state.origStart + state.origDuration + deltaBar;
    let snappedEnd = Math.round(rawNewEnd * snapResolution) / snapResolution;
    let newDuration = snappedEnd - state.origStart;
    
    // 겹침 방지: 오른쪽에 있는 가장 가까운 클립의 시작점을 넘어갈 수 없음
    // 백엔드의 엄격한 부동소수점 검증을 통과하기 위해 0.01 마디의 미세한 간격을 둡니다 (화면상 구분 불가)
    const nextClip = props.track.clips
      .filter(c => c.start >= state.origStart + state.origDuration - 0.001 && c.clipId !== targetClip.clipId)
      .sort((a, b) => a.start - b.start)[0];
    if (nextClip) {
      newDuration = Math.min(newDuration, nextClip.start - state.origStart - 0.01);
    }

    // 음원 최대 길이 제한: 현재 audioStartMs부터 남은 오디오 길이까지만 늘릴 수 있음
    const remainingAudioBars = (totalAudioDurationMs - state.origAudioStartMs) / msPerBar;
    newDuration = Math.min(newDuration, remainingAudioBars);
    newDuration = Math.max(minDuration, newDuration);
    targetClip.duration = newDuration;
    // 오디오 재생 범위도 같이 업데이트 (원본 비율 유지)
    targetClip.audioDurationMs = newDuration * msPerBar;
  } else if (state.side === 'left') {
    // 왼쪽 리사이즈: 스냅된 새로운 시작점을 기반으로 boundedDelta 계산
    let rawNewStart = state.origStart + deltaBar;
    let snappedStart = Math.round(rawNewStart * snapResolution) / snapResolution;
    let boundedDelta = snappedStart - state.origStart;

    const maxDelta = state.origDuration - minDuration;
    boundedDelta = Math.min(boundedDelta, maxDelta);
    
    // 겹침 방지: 왼쪽에 있는 가장 가까운 클립의 끝점을 넘어갈 수 없음
    const prevClip = props.track.clips
      .filter(c => c.start + c.duration <= state.origStart + 0.001 && c.clipId !== targetClip.clipId)
      .sort((a, b) => (b.start + b.duration) - (a.start + a.duration))[0];
    const minAllowedStart = prevClip ? prevClip.start + prevClip.duration + 0.01 : 0;
    
    // 시작점이 minAllowedStart 뚫고 나가지 않게
    if (state.origStart + boundedDelta < minAllowedStart) {
      boundedDelta = minAllowedStart - state.origStart;
    }

    // audioStartMs가 0 미만이 되지 않게 (왼쪽으로 확장 시 오디오 시작점 제한)
    const newAudioStartMs = state.origAudioStartMs + boundedDelta * msPerBar;
    if (newAudioStartMs < 0) boundedDelta = -state.origAudioStartMs / msPerBar;

    targetClip.start = state.origStart + boundedDelta;
    targetClip.duration = state.origDuration - boundedDelta;
    // 왼쪽 리사이즈 시 오디오 시작점 이동 (줄인 만큼 오디오 시작점을 뒤로)
    targetClip.audioStartMs = state.origAudioStartMs + boundedDelta * msPerBar;
    targetClip.audioDurationMs = targetClip.duration * msPerBar;
  }
}

// 리사이즈 마우스 이동 (UI 선반영으로 부드럽게)
const onResizePointerMove = (e: PointerEvent) => {
  if (!resizeState.value.isResizing || !resizeState.value.clip) return;
  
  currentClientX = e.clientX; // 엔진이 알 수 있게 마우스 좌표 최신화
  currentClientY = e.clientY;
  updateResizePosition();
};

// 리사이즈 종료 (스토어에 통신 요청)
const onResizePointerUp = (e: PointerEvent) => {
  if (!resizeState.value.isResizing || !resizeState.value.clip) return;

  // 오토 스크롤 엔진 종료
  if(autoScrollRafId) {
    cancelAnimationFrame(autoScrollRafId);
    autoScrollRafId = null;
  }

  const state = resizeState.value;
  const targetClip = state.clip as ClipUIState;
  
  // 백엔드 요청: 변경된 값 확정 (왼쪽을 얼마나 잘라냈는지 trimLeftBars 전달)
  const trimLeftBars = state.side === 'left' ? (targetClip.start - state.origStart) : 0;
  
  // 부동소수점 정밀도 문제로 인한 오차 방지 (백엔드 CLIP_OVERLAP 오작동 해결)
  // 소수점 3자리까지만 남기고 자름으로써 백엔드의 깐깐한 수치 비교를 무사통과시킴
  const safeStart = Number(targetClip.start.toFixed(3));
  const safeDuration = Number(targetClip.duration.toFixed(3));
  const safeTrimLeft = Number(trimLeftBars.toFixed(3));

  // 로컬 상태도 안전한 값으로 동기화 (이중 연산 방지 스킵 로직 작동을 위해 필수!)
  targetClip.start = safeStart;
  targetClip.duration = safeDuration;
  
  if (state.side === 'left') {
    targetClip.audioStartMs = state.origAudioStartMs + safeTrimLeft * (state.origAudioDurationMs / state.origDuration);
  }
  targetClip.audioDurationMs = safeDuration * (state.origAudioDurationMs / state.origDuration);

  trackStore.resizeClip(
      targetClip.clipId, 
      props.track.trackId, 
      safeStart, 
      safeDuration,
      safeTrimLeft,
      state.origStart,
      state.origDuration,
      state.origAudioStartMs
  );

  // 리사이즈 후 오디오 플레이어를 새 범위에 맞게 재동기화
  trackStore.resyncClip(targetClip.clipId, safeStart);

  // Resize 통신 이후에 Unlock을 보내야 백엔드가 정상적으로 처리함
  // nextTick으로 감싸서 통신이 먼저 처리되도록 보장
  nextTick(() => {
    trackStore.unlockClip(targetClip.clipId, props.track.trackId);
  });

  resizeState.value.isResizing = false;
  resizeState.value.clip = null;

  try {
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  } catch(err) {}
};

 // ==========================================
// 우클릭 컨텍스트 메뉴 상태 관리
// ==========================================
const menuState = ref({
  isOpen: false,
  x: 0,
  y: 0,
  type: 'track' as 'track' | 'clip',
  targetTrackId: -1,
  targetClip: null as ClipUIState | null,
  targetBar: 0 // 마우스 커서가 가리키고 있는 타임라인 마디 위치
});

// 1. 트랙(빈 공간) 우클릭
const onTrackRightClick = (e: MouseEvent, trackId: number) => {
  if(props.isMaster) return; // 마스터 트랙에선 아무것도 못하게 막기
  
  const target = e.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const absoluteX = (e.clientX - rect.left) / trackStore.workspaceZoom;
  
  // 스냅 해상도(subDivision)에 맞춰서 위치 보정
  let targetBar = absoluteX / trackStore.pixelPerBar;
  const snap = trackStore.subDivision;
  targetBar = Math.max(0, Math.round(targetBar * snap) / snap);

  menuState.value = {
    isOpen: true,
    x: e.clientX,
    y: e.clientY,
    type: 'track',
    targetTrackId: trackId,
    targetClip: null,
    targetBar: targetBar
  };
};

// 2. 클립 우클릭
const onClipRightClick = (e: MouseEvent, clip: ClipUIState, trackId: number) => {
  if (clip.isLocked || isAiLocked(clip)) return;
  menuState.value = {
    isOpen: true,
    x: e.clientX,
    y: e.clientY,
    type: 'clip',
    targetTrackId: trackId,
    targetClip: clip,
    targetBar: clip.start
  };
};

// 메뉴 닫기
const closeMenu = () => {
  menuState.value.isOpen = false;
};

// ==========================================
// 메뉴 실행 액션들
// ==========================================

// 복제
const handleDuplicate = () => {
  if (menuState.value.targetClip) {
    trackStore.duplicateClip(menuState.value.targetClip, menuState.value.targetTrackId);
  }
  closeMenu();
};

//복사
const handleCopy = () => {
  if (menuState.value.targetClip) trackStore.copyClip(menuState.value.targetClip, menuState.value.targetTrackId);
  closeMenu();
};

//자르기
const handleCut = () => {
  if (menuState.value.targetClip) trackStore.cutClip(menuState.value.targetClip, menuState.value.targetTrackId);
  closeMenu();
};

//붙여넣기
const handlePaste = () => {
  if (trackStore.clipboardClip) {
    trackStore.pasteClip(menuState.value.targetTrackId, menuState.value.targetBar);
  }
  closeMenu();
};

//삭제
const handleDelete = () => {
  if (menuState.value.type === 'clip' && menuState.value.targetClip) {
    trackStore.deleteClip(menuState.value.targetClip.clipId, menuState.value.targetTrackId);
  } else if (menuState.value.type === 'track') {
    trackStore.deleteTrack(menuState.value.targetTrackId);
  }
  closeMenu();
};

// 분할 (Split)
const handleSplit = () => {
  if (menuState.value.targetClip) {
    trackStore.splitClip(menuState.value.targetClip.clipId, menuState.value.targetTrackId);
  }
  closeMenu();
};

// 파일 입력을 위한 참조 변수
const fileInputRef = ref<HTMLInputElement | null>(null);
const isFileSizeWarningOpen = ref(false);

// 우클릭 메뉴에서 '오디오 불러오기' 클릭 시 파일 탐색기 열기
const triggerFileInput = () => {
  if (fileInputRef.value) {
    fileInputRef.value.click();
  }
  closeMenu();
};

// 파일 선택이 완료되었을 때 실행되는 함수
const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const file = target.files[0];

    // 50MB 제한 (50 * 1024 * 1024 바이트)
    if (file.size > 50 * 1024 * 1024) {
      isFileSizeWarningOpen.value = true;
      target.value = ''; // 초기화
      return;
    }

   // console.log(`[디버그 - 2번 케이스: 탐색기 파일 선택] 파일명: ${file.name}, MIME 타입(file.type): '${file.type}'`);
    // 우클릭했던 트랙 ID와 타임라인의 마디(Bar) 위치를 이용해 업로드 액션 실행
    trackStore.uploadAndAddAudioClip(file, menuState.value.targetTrackId, menuState.value.targetBar);
    
    // 같은 파일을 다시 올릴 수 있도록 input 초기화
    target.value = '';
  }
};


// ==========================================
// 파일 드래그 앤 드롭 (OS에서 트랙으로 오디오 불러오기)
// ==========================================
const isDragOver = ref(false); // 파일을 트랙 위로 드래그 중인지 여부

const onDragEnter = (e: DragEvent) => {
  if (props.isMaster) return; // 마스터 트랙은 드롭 불가
  e.preventDefault();
  e.stopPropagation(); // 정상 트랙 영역에서는 전역 드롭 이벤트가 발생하지 않도록 차단
  isDragOver.value = true;
};

const onDragOver = (e: DragEvent) => {
  if (props.isMaster) return;
  e.preventDefault(); // 브라우저가 파일을 열어버리는 기본 동작 방지
  e.stopPropagation(); // 전파 방지
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'copy'; // 복사(추가)된다는 마우스 커서 표시
  }
};

const onDragLeave = (e: DragEvent) => {
  if (props.isMaster) return;
  e.preventDefault();
  e.stopPropagation();
  
  // 자식 요소 위로 마우스가 지나갈 때 깜빡이는 현상 방지
  const currentTarget = e.currentTarget as HTMLElement;
  const relatedTarget = e.relatedTarget as Node;
  if (!currentTarget.contains(relatedTarget)) {
    isDragOver.value = false;
  }
};

const onDrop = (e: DragEvent) => {
  if (props.isMaster) return;
  e.preventDefault();
  e.stopPropagation(); // 트랙에 제대로 떨어뜨렸으므로, 최상위 컨테이너로 버블링되지 않게 막음
  isDragOver.value = false;

  // 1. 떨어뜨린 파일 가져오기
  const files = e.dataTransfer?.files;
  if (!files || files.length === 0) return;

  const file = files[0];
 // console.log(`[디버그 - 1번 케이스: 드래그 앤 드롭] 파일명: ${file.name}, MIME 타입(file.type): '${file.type}'`);

  // 2. 오디오 파일인지 검증 (mp3, wav 등)
  if (!file.type.startsWith('audio/')) {
   // console.warn(`[디버그 - 드래그 앤 드롭 차단됨] file.type이 'audio/'로 시작하지 않습니다. (현재: '${file.type}')`);
    alertStore.showAlert('오디오 파일(mp3, wav 등)만 추가할 수 있습니다.', 'warning');
    return;
  }

  // 3. 마우스를 떨어뜨린 X 좌표를 마디(Bar)로 변환
  const target = e.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const absoluteX = (e.clientX - rect.left) / trackStore.workspaceZoom;
  
  let targetBar = absoluteX / trackStore.pixelPerBar;
  
  // 스냅 해상도에 맞춰 위치 보정
  const snap = trackStore.subDivision;
  targetBar = Math.max(0, Math.round(targetBar * snap) / snap);

  // 4. 스토어의 업로드 액션
  trackStore.uploadAndAddAudioClip(file, props.track.trackId, targetBar);
};

// ==========================================
// 볼륨/패닝 드래그 및 직접 입력 로직
// ==========================================

// 볼륨 슬라이더 드래그 로직
const isDraggingVolume = ref(false);
const localVolume = ref(0);

const displayVolume = computed(() => {
  return isDraggingVolume.value ? localVolume.value : (props.track.volume || 0);
});

const handleVolumeInput = (e: Event) => {
  isDraggingVolume.value = true;
  const val = Number((e.target as HTMLInputElement).value);
  localVolume.value = parseFloat(trackStore.getVolumeFromPercent(val).toFixed(1));
  // 실시간 로컬 오디오 업데이트 (소켓 전송 안함)
  trackStore.setTrackVolume(props.track.trackId, localVolume.value, false);
};

const handleVolumeChange = (e: Event) => {
  isDraggingVolume.value = false;
  const val = Number((e.target as HTMLInputElement).value);
  const finalVolume = parseFloat(trackStore.getVolumeFromPercent(val).toFixed(1));
  // 변경 완료 시 소켓 전송
  trackStore.setTrackVolume(props.track.trackId, finalVolume, true);
};

// 패닝 슬라이더 드래그 로직
const isDraggingPan = ref(false);
const localPan = ref(0);

const displayPan = computed(() => {
  return isDraggingPan.value ? localPan.value : (props.track.pan || 0);
});

const handlePanInput = (e: Event) => {
  isDraggingPan.value = true;
  localPan.value = Number((e.target as HTMLInputElement).value);
  // 실시간 로컬 오디오 업데이트 (소켓 전송 안함)
  trackStore.setTrackPan(props.track.trackId, localPan.value, false);
};

const handlePanChange = (e: Event) => {
  isDraggingPan.value = false;
  const pan = Number((e.target as HTMLInputElement).value);
  // 변경 완료 시 소켓 전송
  trackStore.setTrackPan(props.track.trackId, pan, true);
};

const isEditingVolume = ref(false);
const volumeInputRef = ref<HTMLInputElement | null>(null);
const editVolumeValue = ref<number | string>(0); // 입력 중인 임시 값 저장용

const startEditVolume = async () => {
  isEditingVolume.value = true;
  editVolumeValue.value = Number((props.track.volume || 0).toFixed(1)); // 현재 볼륨값을 임시 변수에 복사
  await nextTick();
  volumeInputRef.value?.focus();
  volumeInputRef.value?.select();
};

const finishEditVolume = () => {
  if (!isEditingVolume.value) return; // 엔터+Blur 중복 실행 방지
  isEditingVolume.value = false;
  
  let val = parseFloat(String(editVolumeValue.value));
  if (isNaN(val)) val = props.track.volume || 0;
  
  // 범위를 -60 ~ +6 dB 사이로 강제 고정
  val = Math.max(-60, Math.min(6, val)); 
  trackStore.setTrackVolume(props.track.trackId, Number(val.toFixed(1)));
};

const isEditingPan = ref(false);
const panInputRef = ref<HTMLInputElement | null>(null);
const editPanValue = ref<number | string>(0); // 입력 중인 임시 값 저장용

const startEditPan = async () => {
  isEditingPan.value = true;
  editPanValue.value = props.track.pan || 0; // 현재 패닝값을 임시 변수에 복사
  await nextTick();
  panInputRef.value?.focus();
  panInputRef.value?.select();
};

const finishEditPan = () => {
  if (!isEditingPan.value) return; // 중복 실행 방지
  isEditingPan.value = false;
  
  let val = parseInt(String(editPanValue.value), 10);
  if (isNaN(val)) val = props.track.pan || 0;
  
  // 범위를 -100 ~ +100 사이로 강제 고정
  val = Math.max(-100, Math.min(100, val)); 
  trackStore.setTrackPan(props.track.trackId, val);
};

const isEditingName = ref(false);
const nameInputRef = ref<HTMLInputElement | null>(null);
const editNameValue = ref('');
const isDragDisabled = ref(false);
const isCommentExpanded = ref(false);

const handleMouseDown = (e: MouseEvent) => {
  const target = e.target as HTMLElement;
  // 볼륨/팬 슬라이더(input), 각종 버튼, 텍스트 에디터 등을 클릭했을 때는 트랙 전체 드래그 속성을 즉시 끕니다.
  if (target.closest('input, button, .interactive-control, [role="slider"]')) {
    isDragDisabled.value = true;
  } else {
    isDragDisabled.value = false;
  }
};

const handleDragStart = (e: DragEvent) => {
  emit('dragstart', e);
};

const startEditName = async () => {
  if (props.isMaster) return; // 마스터 트랙은 수정 금지
  isEditingName.value = true;
  editNameValue.value = props.track.name;
  
  await nextTick();
  nameInputRef.value?.focus();
  nameInputRef.value?.select(); // 이름 전체 블록 지정 (바로 수정 가능하게)
};

const finishEditName = () => {
  if (!isEditingName.value) return; // 중복 실행 방지
  isEditingName.value = false;
  
  const trimmedName = editNameValue.value.trim();
  // 빈 문자열이 아니고 기존 이름과 다를 때만 스토어 호출
  if (trimmedName && trimmedName !== props.track.name) {
    trackStore.renameTrack(props.track.trackId, trimmedName);
  }
};

// 부모(TrackList.vue)로 드래그 이벤트를 올려보내기 위한 정의
const emit = defineEmits<{
  dragstart: [event: DragEvent]
  dragend: [event: DragEvent]
  'hover-measure': [payload: {
    trackId: string | null
    measure: number | null
  }]
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

//
const onWorkAreaMouseMove = (e: MouseEvent) => {
  if(props.isMaster) return;

  const target = e.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const absoluteX = (e.clientX / trackStore.workspaceZoom) - rect.left / trackStore.workspaceZoom;

  //마우스 위치를 바탕으로 정확한 '마디(Measure)' 역산
  const rawLocation = (absoluteX / trackStore.pixelPerBar) + 1;
  const snappedLocation = Math.round((rawLocation - 1) * trackStore.subDivision) / trackStore.subDivision + 1;

  // 코멘트 레이어를 위해 현재 마우스 위치 발송
  emit('hover-measure', {
    trackId: String(props.track.trackId),
    measure: snappedLocation
  });
};

const onWorkAreaMouseLeave = () => {
  if (props.isMaster) return;
  emit('hover-measure', { trackId: null, measure: null });
};

const commentCursorSvg = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23FF3DCB' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/%3E%3C/svg%3E") 12 12, auto`;

</script>

<template>
  <!--flex: 하위 요소 나란히 배치 // group: 상태 공유기 ,트랙 전체 그룹에 마우스를 올렸을떄 컨트롤 패널 색상 변경-->
  <!--sticky left-0 z-20: 스크롤 시 가장 위에 고정, 컨트롤 패널의 왼쪽을 고정-->
  <!-- shrink-0 : 줄어들지 않게 고정-->
   <!--min-w-0으로 텍스트가 늘어나는 걸 막고 글자를 잘라줌(truncate)-->
   <!--relative: 기준점, 부모 슬라이더의 회색 배경 우측-->
   <!--absolute: 자식, 기준점 안에서 자유롭게 공중부양, 트랙의 시작점, 슬라이더의 회색 배경 좌측-->
   <!--inset-0, inset-y, : absolute를 쓸때 상하좌우를 채움-->
   <!--flex-1 : 남은 공간을 모두 차지-->
   <!--border-border 테두리를 보더에 지정된 색으로 칠해라-->
   <div 
    :aria-label="`트랙: ${track.name}`" 
    class="flex border-b border-border group w-max min-w-full" 
    :data-track-id="track.trackId" 
    :class="[
      track.clips.some(c => c.isDragging) ? 'relative z-50' :
      (props.hoveredTrackId === String(track.trackId)) ? 'relative z-40' : 'relative'
    ]"
    :style="{ zIndex: isCommentExpanded ? 100 : '' }"
  >
   <div 
      :aria-label="`${track.name} 컨트롤 패널`"
      class="sticky left-0 z-60 flex shrink-0 flex-col gap-1.5 [@media(max-height:500px)]:gap-0.5 border-r py-2 [@media(max-height:500px)]:py-1 px-3 transition-colors duration-200 group-hover:bg-[#282828]"
      :class="[
        track.isSelected ? 'bg-[#2a2a2b] border-r-[#FF8F1A]' : 'bg-[#1c1c1c] border-border',
        isMaster ? 'cursor-pointer' : 'cursor-grab active:cursor-grabbing'
      ]"
      :style="{ 
        width: '224px', 
        borderLeft: `4px solid ${track.color || '#FF3DCB'}`,
        willChange: 'transform'
      }"
      :draggable="!isMaster && !isDragDisabled"
      @mousedown.capture="handleMouseDown"
      @dragstart="handleDragStart"
      @dragend="emit('dragend', $event)"
      @pointerdown.stop="trackStore.selectTrack(track.trackId)"
    >
    <!--빈틈 막는거-->
    <div class="absolute top-0 -bottom-px left-0 -right-px -z-10 bg-inherit pointer-events-none"></div>
    <div class="sticky left-0 z-20 w-[224px] shrink-0 border-r border-border bg-card" style="will-change: transform;"></div>
      <div class="flex items-center justify-between gap-2">
        <div class="flex min-w-0 flex-1 items-center gap-1.5">
          <!-- 드래그 핸들 (시각적 힌트) -->
          <GripVertical v-if="!isMaster" class="h-3.5 w-3.5 shrink-0 text-white/30 pointer-events-none" />
          
          <div class="flex min-w-0 flex-1 items-center gap-1.5">
           <!-- 수정 모드: 인풋창 -->
            <input
              v-if="isEditingName"
              ref="nameInputRef"
              type="text"
              v-model="editNameValue"
              @blur="finishEditName"
              @keydown.enter="finishEditName"
              @keydown.esc="isEditingName = false"
              @keydown.delete.stop
              @mousedown.stop 
              @dragstart.prevent.stop
              class="w-full truncate bg-transparent text-sm font-bold tracking-wide text-white outline-none border-b border-primary/50"
            />
            <!-- 일반 모드: 텍스트 -->
            <span 
              v-else 
              class="truncate text-sm font-bold tracking-wide text-white interactive-control"
              @dblclick="!isMaster && startEditName()"
              @mousedown.stop
            >
              {{ track.name }}
            </span>
            
            <!-- 연필 아이콘 -->
            <button 
              v-if="!isMaster && !isEditingName" 
              aria-label="트랙 이름 수정" 
              class="shrink-0 text-muted-foreground transition hover:text-white"
              @click.stop="startEditName"
              @mousedown.stop
            >
              <Pencil class="h-3 w-3" />
            </button>
          </div>
        </div>

       <div class="flex shrink-0 items-center gap-1" @mousedown.stop>
          <!-- 뮤트 버튼 -->
          <button 
            v-if="!isMaster"
            aria-label="음소거 토글" 
            @click="trackStore.toggleTrackMute(track.trackId)"
            :class="track.isMuted ? 'bg-red-500/20 text-red-500 border-red-500/50' : 'border-white/30 bg-white/10 text-white hover:bg-white/20'"
            class="grid h-6 w-7 place-items-center rounded border transition"
          >
            <VolumeX v-if="track.isMuted" class="h-3.5 w-3.5" />
            <Volume2 v-else class="h-3.5 w-3.5" />
          </button>
          
          <!-- 솔로 버튼 -->
          <button 
            v-if="!isMaster"
            aria-label="솔로 토글" 
            @click="trackStore.toggleTrackSolo(track.trackId)"
            :class="track.isSoloed ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/50' : 'border-transparent bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-white'"
            class="grid h-6 w-7 place-items-center rounded border transition"
          >
            <span class="text-[10px] font-bold">S</span>
          </button>
        </div>
      </div>

      <!-- 볼륨 / 팬 컨트롤 영역 교체 -->
      <div class="mt-auto flex flex-col gap-2 [@media(max-height:500px)]:gap-0.5">
        
        <!-- 볼륨 조절 -->
<div aria-label="볼륨 조절" class="flex items-center gap-2 [@media(max-height:500px)]:gap-1" @mousedown.stop @dragstart.prevent.stop>
          <span aria-hidden="true" class="w-7 shrink-0 font-mono text-[9px] tracking-widest text-muted-foreground">VOL</span>
          
          <!-- 1. 볼륨 커스텀 슬라이더 (드래그 조작용) -->
          <div class="relative h-1.5 flex-1 rounded-full bg-black/60 flex items-center">
            <!-- 게이지 -->
            <div class="absolute left-0 h-full rounded-full bg-[#9ca3af] shadow-[0_0_8px_rgba(156,163,175,0.6)]" :style="{ width: `${trackStore.getVolumePercent(displayVolume)}%` }"></div>
            <!-- 핸들 -->
            <div class="absolute h-4 w-4 -translate-x-1/2 rounded-full border-2 border-[#9ca3af] bg-[#1c1c1c] pointer-events-none" :style="{ left: `${trackStore.getVolumePercent(displayVolume)}%` }"></div>
            <!-- 투명 인풋 (마우스 드래그 조작 담당) -->
            <input 
              type="range" min="0" max="100" step="0.1" 
              :value="trackStore.getVolumePercent(displayVolume)" 
              @input="handleVolumeInput"
              @change="handleVolumeChange"
              class="absolute inset-0 w-full opacity-0 cursor-pointer z-10"
            />
          </div>

          <!-- 2. 수치 입력 박스 (키보드 직접 입력용) -->
          <div 
            aria-label="현재 볼륨 수치" 
            class="flex w-10 shrink-0 items-center justify-center rounded-[4px] border border-white/20 bg-black/20 py-0.5 [@media(max-height:500px)]:py-0 cursor-text hover:border-primary/50 transition-colors"
            @click.stop="startEditVolume"
          >
            <input
              v-if="isEditingVolume"
              ref="volumeInputRef"
              type="number"
              v-model="editVolumeValue"
              @blur="finishEditVolume"
              @keydown.enter="finishEditVolume"
              @keydown.delete.stop
              class="w-full bg-transparent text-center font-mono text-[10px] tabular-nums text-white outline-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              style="-moz-appearance: textfield; appearance: textfield;"
              step="0.1"
            />
            <span v-else class="font-mono text-[10px] tabular-nums text-white pointer-events-none">
              {{ displayVolume <= -60 ? '-inf' : displayVolume.toFixed(1) }}
            </span>
          </div>
        </div>

        <!-- 패닝 조절 -->
        <div aria-label="패닝 조절" class="flex items-center gap-2 [@media(max-height:500px)]:gap-1" @mousedown.stop @dragstart.prevent.stop>
          <span aria-hidden="true" class="w-7 shrink-0 font-mono text-[9px] tracking-widest text-muted-foreground">PAN</span>
          
          <!-- 1. 팬 커스텀 슬라이더 (드래그 조작용) -->
          <div class="relative h-1.5 flex-1 rounded-full bg-black/60 flex items-center">
            <!-- 게이지 -->
            <div class="absolute h-full rounded-full bg-[#d4d4d4] shadow-[0_0_8px_rgba(255,255,255,0.4)]" :style="{ left: displayPan < 0 ? `${50 + displayPan / 2}%` : '50%', width: `${Math.abs(displayPan) / 2}%` }"></div>
            <!-- 핸들 -->
            <div class="absolute h-4 w-4 -translate-x-1/2 rounded-full border-2 border-gray-300 bg-[#1c1c1c] pointer-events-none" :style="{ left: `${50 + displayPan / 2}%` }"></div>
            <!-- 투명 인풋 (마우스 드래그 조작 담당) -->
            <input 
              type="range" min="-100" max="100" step="1" 
              :value="displayPan" 
              @input="handlePanInput"
              @change="handlePanChange"
              class="absolute inset-0 w-full opacity-0 cursor-pointer z-10"
            />
          </div>

          <!-- 2. 수치 입력 박스 (키보드 직접 입력용) -->
          <div 
            aria-label="현재 패닝 수치" 
            class="flex w-10 shrink-0 items-center justify-center rounded-[4px] border border-white/20 bg-black/20 py-0.5 [@media(max-height:500px)]:py-0 cursor-text hover:border-primary/50 transition-colors"
            @click.stop="startEditPan"
          >
            <input
              v-if="isEditingPan"
              ref="panInputRef"
              type="number"
              v-model="editPanValue"
              @blur="finishEditPan"
              @keydown.enter="finishEditPan"
              @keydown.delete.stop
              class="w-full bg-transparent text-center font-mono text-[10px] tabular-nums text-white outline-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              style="-moz-appearance: textfield; appearance: textfield;"
              step="1"
            />
            <span v-else class="font-mono text-[10px] tabular-nums text-white pointer-events-none">
              {{ displayPan === 0 ? 'C' : (displayPan > 0 ? `R${displayPan}` : `L${Math.abs(displayPan)}`) }}
            </span>
          </div>
        </div>
      </div>
    </div> 
    <!--타임라인 우측 작업 영역-->
    <div 
      aria-label="오디오 클립 작업 영역" 
      class="relative shrink-0 select-none bg-transparent py-1.5 touch-none"
      :class="[
        isDragOver ? 'bg-primary/20 ring-2 ring-inset ring-primary' : 'bg-transparent',
        trackStore.isCommentMode ? 'comment-mode-active' : ''
      ]"
      :style="{ width: `${trackStore.totalTimelineWidth}px` }"
      @wheel.ctrl.prevent="trackStore.updateZoom($event.deltaY)"
      @dragenter="onDragEnter"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
      @dragstart.prevent.stop
      @mousemove="onWorkAreaMouseMove"
      @mouseleave="onWorkAreaMouseLeave"
    >
      <div class="relative h-full border-y border-r border-white/5 bg-card shadow-inner">
      
      <!--트랙 빈 공간 우클릭 감지용 투명 레이어 가장 바닥에 깔림 z-0-->
      <div 
          class="absolute inset-0 z-0 cursor-context-menu"
          @contextmenu.prevent.stop="onTrackRightClick($event, track.trackId)"
          @pointerdown.stop="trackStore.selectTrack(track.trackId)"
        ></div>

      <!--마디 세로줄 렌더링 (CSS 배경 패턴으로 DOM 0개 — 성능 최적화)-->
        <div 
          aria-hidden="true" 
          class="pointer-events-none absolute inset-0 z-0 border-b border-white/5 bg-[#171717]"
        />

        <!-- AI Conflict Backgrounds -->
        <template v-if="!props.isMaster && aiAnalysisItems">
          <div
            v-for="conflict in aiAnalysisItems"
            :key="conflict.id"
            v-show="activeAiAnalysisId === conflict.id && (
              String(conflict.targetTrackId) === String(track.trackId) ||
              (conflict.involvedTrackIds && conflict.involvedTrackIds.some((id: any) => String(id) === String(track.trackId)))
            )"
            class="pointer-events-none absolute top-0 bottom-0 z-40 border-x border-red-500 bg-red-500/20"
            :style="{
              left: getConflictLeft(conflict) + 'px',
              width: getConflictWidth(conflict) + 'px'
            }"
          />
        </template>

        <div 
          aria-hidden="true" 
          class="pointer-events-none absolute inset-0 z-0"
          :style="{
            backgroundImage: [
              `linear-gradient(to right, #505567 1px, transparent 1px)`,
              `linear-gradient(to right, #393C45 1px, transparent 1px)`,
              trackStore.subDivision > 1
                ? `linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px)`
                : ''
            ].filter(Boolean).join(', '),
            backgroundSize: [
              `${trackStore.pixelPerBar * 4}px 100%`,
              `${trackStore.pixelPerBar}px 100%`,
              trackStore.subDivision > 1
                ? `${trackStore.pixelPerBar / trackStore.subDivision}px 100%`
                : ''
            ].filter(Boolean).join(', ')
          }"
        ></div>


        <!-- 파일 업로드 중 임시 고스트 클립 -->
        <div 
          v-if="trackStore.uploadingTrackId === track.trackId && trackStore.uploadingBar !== null"
          class="absolute inset-y-1 z-20 flex flex-col items-center justify-center rounded-md border-2 border-dashed border-gray-400 bg-gray-700/50 text-white"
          :style="{ 
            left: `${trackStore.uploadingBar * trackStore.pixelPerBar}px`,
            width: `${4 * trackStore.pixelPerBar}px`  // 기본 4마디 크기로 표시
          }"
        >
          <Loader2 class="h-6 w-6 animate-spin mb-1" />
          <span class="text-xs font-bold">업로드 중...</span>
        </div>

        <!-- [고스트 클립 1] 잘라내기(Cut) 된 클립의 잔상 표시 -->
        <div 
          v-if="trackStore.isCutAction && trackStore.clipboardTrackId === track.trackId && trackStore.clipboardClip"
          class="absolute inset-y-1 z-0 flex items-center justify-center rounded-md border-2 border-dashed border-primary/50 bg-primary/10 pointer-events-none"
          :style="{ 
            left: `${trackStore.clipboardClip.start * trackStore.pixelPerBar}px`,
            width: `${trackStore.clipboardClip.duration * trackStore.pixelPerBar}px`
          }"
        >
          <span class="text-[10px] font-semibold text-primary/60 px-2 truncate">잘라낸 클립 (붙여넣기 대기 중)</span>
        </div>

        <!-- [고스트 클립 2] 이동(Drag) 중인 클립의 원본 위치 잔상 표시 -->
        <div 
          v-if="activeClip && activeClip.isDragging && !isMaster"
          class="absolute inset-y-1 z-0 rounded-md border-2 border-dashed border-primary/50 bg-primary/10 pointer-events-none transition-opacity duration-200"
          :style="{ 
            left: `${startClipBar * trackStore.pixelPerBar}px`,
            width: `${activeClip.duration * trackStore.pixelPerBar}px`
          }"
        ></div>

        <!-- [고스트 클립 3] 크기 조절(Resize) 중인 클립의 원본 위치/크기 잔상 표시 -->
        <div 
          v-if="resizeState.isResizing && resizeState.clip && !isMaster"
          class="absolute inset-y-1 z-0 rounded-md border-2 border-dashed border-primary/50 bg-primary/10 pointer-events-none transition-opacity duration-200"
          :style="{ 
            left: `${resizeState.origStart * trackStore.pixelPerBar}px`,
            width: `${resizeState.origDuration * trackStore.pixelPerBar}px`
          }"
        ></div>

      <!-- 실제 클립 렌더링 및 클립 전용 우클릭 이벤트(z-10) -->
        <div 
          v-for="clip in visibleClips" 
          :key="clip.clipId"
          :aria-label="`오디오 클립: ${clip.audio?.originalName || track.name}`"
          class="clip-container absolute inset-y-1 z-10 rounded-md"
          :class="[
            isMaster ? 'pointer-events-none' : 'cursor-grab border-2 active:cursor-grabbing',
            clip.isDragging ? 'opacity-95 brightness-75 shadow-2xl !z-50' : '',
            clip.isSelected && !clip.isDragging && !isMaster ? 'brightness-75 shadow-lg ring-2 ring-white/70 ring-offset-2 ring-offset-[#1c1c1c] z-40' : '',
            (clip.isLocked || isAiLocked(clip)) && !isMaster ? 'grayscale opacity-75 pointer-events-none' : ''
          ]"
          :style="{ 
            left: `${clip.start * trackStore.pixelPerBar}px`,
            '--clip-left-px': `${clip.start * trackStore.pixelPerBar}px`,
            width: `${clip.duration * trackStore.pixelPerBar}px`,
            borderColor: isMaster ? 'transparent' : (clip.isSelected || clip.isDragging ? clip.color : `${clip.color}80`), 
            backgroundColor: isMaster ? 'transparent' : (clip.isSelected || clip.isDragging ? `${clip.color}66` : `${clip.color}33`), 
            boxShadow: isMaster ? 'none' : (clip.isDragging ? '0 8px 16px rgba(0,0,0,0.6)' : clip.isSelected ? '0 4px 12px rgba(0,0,0,0.5)' : 'none'),
            transform: clip.isDragging ? `translateY(${dragoffsetY}px)` : 'none'
          }"
          @pointerdown="!isMaster && onClipPointerDown($event, clip); !isMaster && trackStore.selectClip(clip, track.trackId);"
          @pointermove="!isMaster && onClipPointerMove($event)"
          @pointerup="!isMaster && onClipPointerUp($event)"
          @pointercancel="!isMaster && onClipPointerUp($event)"
          @contextmenu.prevent.stop="!isMaster && onClipRightClick($event, clip, track.trackId)"
        >
          <!-- 왼쪽 리사이즈 핸들 (마스터에선 숨김) - 반투명 배경 + 6-dot 그립 아이콘 -->
          <div 
            v-if="!isMaster && !clip.isLocked && !isAiLocked(clip)"
            class="group absolute left-0 top-0 bottom-0 w-3 z-20 cursor-w-resize flex items-center justify-center rounded-l-md transition-colors hover:bg-white/20"
            :style="{ backgroundColor: `${clip.color}40` }"
            @pointerdown.stop="onResizePointerDown($event, clip, 'left')"
            @pointermove.stop="onResizePointerMove"
            @pointerup.stop="onResizePointerUp"
            @pointercancel.stop="onResizePointerUp"
          >
            <GripVertical class="h-4 w-4 text-white/50 group-hover:text-white/80 transition-colors" />
          </div>

          <!-- 중앙 잠금 아이콘 (클립 락 & AI 락 공통) -->
          <div 
            v-if="(clip.isLocked || isAiLocked(clip)) && !isMaster"
            class="absolute inset-0 z-30 flex items-center justify-center pointer-events-none"
          >
            <div 
              class="flex items-center justify-center rounded-full bg-black/40 p-2 text-white shadow-md backdrop-blur-sm ring-1 ring-white/20"
              :title="clip.isLocked ? '다른 사용자가 편집 중입니다 (이동 및 수정 불가)' : 'AI 작업 대기 중입니다 (조작 불가)'"
            >
              <Lock class="h-5 w-5 opacity-90" />
            </div>
          </div>

          <div 
            v-if="!isMaster"
            aria-hidden="true"
            class="absolute inset-x-0 top-0 truncate px-2 py-0.5 text-[10px] font-semibold pointer-events-none"
            :style="{ color: clip.color }"
          >
            {{ clip.audio?.originalName || track.name }}
          </div>

         <WaveformWebGL
          v-if="!isMaster"
          :key="clip.clipId"
          :clip="clip" />

          <!-- 오른쪽 리사이즈 핸들 (마스터에선 숨김) - 반투명 배경 + 6-dot 그립 아이콘 -->
          <div 
            v-if="!isMaster && !clip.isLocked && !isAiLocked(clip)"
            class="group absolute right-0 top-0 bottom-0 w-3 z-20 cursor-e-resize flex items-center justify-center rounded-r-md transition-colors hover:bg-white/20"
            :style="{ backgroundColor: `${clip.color}40` }"
            @pointerdown.stop="onResizePointerDown($event, clip, 'right')"
            @pointermove.stop="onResizePointerMove"
            @pointerup.stop="onResizePointerUp"
            @pointercancel.stop="onResizePointerUp"
          >
            <GripVertical class="h-4 w-4 text-white/50 group-hover:text-white/80 transition-colors" />
          </div>
        </div>

    <TrackCommentLayer
      v-if="!isMaster"
  :track-id="String(track.trackId)"
  :track-name="track.name"
  :total-bar-count="trackStore.displayBarCount"
  :pixel-per-bar="trackStore.pixelPerBar"
  :sub-division="trackStore.subDivision"
  :timeline-width="trackStore.totalTimelineWidth"
  :hovered-measure="hoveredMeasure ?? null"
  :hovered-track-id="hoveredTrackId ?? null"
  :commented-groups="commentedGroups ?? []"
  @hover-measure="emit('hover-measure', $event)"
  @submit-inline-comment="emit('submit-inline-comment', $event)"
  @resolve-comment="emit('resolve-comment', $event)"
  @delete-comment="emit('delete-comment', $event)"
  @track-contextmenu="onTrackRightClick($event, track.trackId)"
  @track-pointerdown="trackStore.selectTrack(track.trackId)"
  @comment-expanded="isCommentExpanded = $event"
/>
      </div> 

      

      <!--재생바 (DOM 직접 조작으로 이동 — Vue 반응성 우회)-->
    <div 
        class="playhead-line pointer-events-none absolute top-0 -bottom-px z-10 w-px bg-primary"
        style="box-shadow: 0 0 8px hsl(var(--primary) / 0.8); will-change: transform; transform: translate3d(calc(var(--playhead-px, 0px) - 50%), 0, 0);"
      ></div>

    </div>
    </div>

    <!-- ========================================== -->
  <!-- 우클릭 컨텍스트 메뉴 UI (화면 최상단에 렌더링) -->
  <!-- ========================================== -->
  <Teleport to="body">
    <!-- 배경 클릭 시 메뉴 닫기용 투명 오버레이 -->
    <div 
      v-if="menuState.isOpen" 
      class="fixed inset-0 z-9998" 
      @mousedown="closeMenu" 
      @contextmenu.prevent.stop="closeMenu"
    ></div>

    <!-- 메뉴 본체 -->
    <div 
      v-if="menuState.isOpen"
      class="fixed z-9999 w-56 rounded-md border border-[#393C45] bg-[#1E1E21] py-1.5 shadow-2xl text-[13px] text-[#D4CED2]"
      :style="{ top: `${menuState.y}px`, left: `${menuState.x}px` }"
    >
      <!-- 트랙 우클릭 시에만 보여줄 메뉴 (클립 우클릭 시엔 비활성화/숨김) -->
      <template v-if="menuState.type === 'track'">
        <button @click="triggerFileInput" class="flex w-full items-center justify-between px-4 py-1.5 hover:bg-white/10">
          <span class="flex items-center gap-2"><UploadIcon class="h-4 w-4" /> 오디오 업로드</span>
          <span class="text-[10px] text-gray-500">Ctrl+I</span>
        </button>
        <div class="my-1 h-px w-full bg-[#393C45]"></div>
      </template>

      <!-- 숨겨진 파일 인풋 (실제 업로드 처리 담당) -->
      <input 
        type="file" 
        ref="fileInputRef" 
        accept="audio/mpeg, audio/wav" 
        class="hidden" 
        @change="handleFileUpload" 
      />

      <!-- 클립 우클릭 시 활성화되는 메뉴들 -->
      
      <button
        @click="handleSplit"
        class="flex w-full items-center justify-between px-4 py-1.5"
        :class="menuState.type === 'clip' ? 'hover:bg-white/10' : 'opacity-40 cursor-not-allowed'"
        :disabled="menuState.type !== 'clip'"
      >
        <span class="flex items-center gap-2"><ScissorsIcon class="h-4 w-4" /> 재생바에서 분할</span>
        <span class="text-[10px] text-gray-500">Ctrl+E</span>
      </button>

      <button
        @click="handleDuplicate"
        class="flex w-full items-center justify-between px-4 py-1.5"
        :class="menuState.type === 'clip' ? 'hover:bg-white/10' : 'opacity-40 cursor-not-allowed'"
        :disabled="menuState.type !== 'clip'"
      >
        <span class="flex items-center gap-2"><CopyPlusIcon class="h-4 w-4" /> 클립 복제</span>
        <span class="text-[10px] text-gray-500">Ctrl+D</span>
      </button>

      <div class="my-1 h-px w-full bg-[#393C45]"></div>

      <button 
        @click="handleCopy"
        class="flex w-full items-center justify-between px-4 py-1.5"
        :class="menuState.type === 'clip' ? 'hover:bg-white/10' : 'opacity-40 cursor-not-allowed'"
        :disabled="menuState.type !== 'clip'"
      >
        <span class="flex items-center gap-2"><CopyIcon class="h-4 w-4" /> 복사</span>
        <span class="text-[10px] text-gray-500">Ctrl+C</span>
      </button>

      <button 
        @click="handleCut"
        class="flex w-full items-center justify-between px-4 py-1.5"
        :class="menuState.type === 'clip' ? 'hover:bg-white/10' : 'opacity-40 cursor-not-allowed'"
        :disabled="menuState.type !== 'clip'"
      >
        <span class="flex items-center gap-2"><ScissorsIcon class="h-4 w-4" /> 잘라내기</span>
        <span class="text-[10px] text-gray-500">Ctrl+X</span>
      </button>

      <!-- 붙여넣기는 클립보드에 데이터가 있을 때만 활성화 -->
      <button 
        @click="handlePaste"
        class="flex w-full items-center justify-between px-4 py-1.5"
        :class="trackStore.clipboardClip ? 'hover:bg-white/10' : 'opacity-40 cursor-not-allowed'"
        :disabled="!trackStore.clipboardClip"
      >
        <span class="flex items-center gap-2"><ClipboardIcon class="h-4 w-4" /> 붙여넣기</span>
        <span class="text-[10px] text-gray-500">Ctrl+V</span>
      </button>

      <div class="my-1 h-px w-full bg-[#393C45]"></div>

      <button 
        @click="handleDelete"
        class="flex w-full items-center justify-between px-4 py-1.5 hover:bg-red-500/20 text-red-400"
      >
        <span class="flex items-center gap-2">
          <TrashIcon class="h-4 w-4" /> 
          {{ menuState.type === 'clip' ? '클립 삭제' : '트랙 삭제' }}
        </span>
        <span class="text-[10px] text-gray-500">DEL</span>
      </button>
    </div>
  </Teleport>

  <FileSizeWarningModal
    :open="isFileSizeWarningOpen"
    @close="isFileSizeWarningOpen = false"
  />
</template>
<style scoped>
</style>