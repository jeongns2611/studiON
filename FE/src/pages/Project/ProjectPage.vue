<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted, nextTick, watch, provide } from 'vue'
import { useRoute } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import type { TrackMeasureCommentGroup, TimelineComment } from './types/comment.types'
import {useTrackStore} from './store/useTrackStore' //트랙 상태 저장소
import ProjectHeader from './components/ProjectHeader.vue'
import TrackList from './components/TrackList.vue' //트랙 리스트 컴포넌트
import InviteCodeModal from './components/InviteCodeModal.vue'
import ProjectSidePanel from './components/ProjectSidePanel.vue'
import TimelineRuler from './components/TimelineRuler.vue' //타임라인 눈금자
import PlayController from './components/PlayController.vue' //재생 컨트롤러
import * as Tone from 'tone' //오디오 엔진
import AiConflictOverlay from './components/AiConflictOverlay.vue'
import TrackItem from './components/TrackItem.vue'//트랙 아이템 마스터 트랙 렌더링용 
import RemoteCursors from './components/RemoteCursors.vue' //커서 컴포넌트
import { useCollabStore } from './store/useCollabStore';//공동 작업 스토어 
import {socketService} from '../../core/services/socket.service'; //웹 소켓 서비스
import {useAuthStore} from '@/pages/Onboarding/stores/auth.store';
import ProjectEqPanel from './components/ProjectEqPanel.vue'
import type { TrackEqBandState } from './types'
import { AlertTriangle } from 'lucide-vue-next';
import { projectApi } from './api/project.api';
import { useProjectSave } from './composables/useProjectSave';
import { useCommentStore } from './store/useCommentStore'
import ExportModal from './components/ExportModal.vue';
import VersionSaveModal from './components/VersionSaveModal.vue';
import { useProjectAiWorkflow } from './composables/useProjectAiWorkflow'
import { useProjectCollaboration } from './composables/useProjectCollaboration'
import ProjectGuideOverlay from '@/pages/Project/components/ProjectGuideOverlay.vue'
import DefaultTrackDropGuide from '@/pages/Project/components/DefaultTrackDropGuide.vue'
import { trackEvent } from '@/shared/utils/analytics'
import { useAlertStore } from '@/shared/stores/useAlertStore'

type SidePanelType = 'comments' | 'history' | 'ai' | 'help' | null
type CommentToastVariant = 'comment' | 'mention'

interface CommentToast {
  id: number
  variant: CommentToastVariant
  title: string
  meta: string
  content: string
  trackId: number
  location: number
  author: string
  profileImageUrl?: string | null
}

const route = useRoute()
const alertStore = useAlertStore()
const projectId = route.params.projectId as string
const trackStore = useTrackStore() // 트랙 리스트 정보 사용 준비
const collabStore = useCollabStore(); //공동 작업 스토어 사용
const authStore = useAuthStore(); // Auth 스토어 사용 준비
const commentStore = useCommentStore(); // 코멘트 전역 상태 사용
const commentToasts = ref<CommentToast[]>([])
const commentToastTimers = new Map<number, ReturnType<typeof setTimeout>>()
const COMMENT_TOAST_DURATION_MS = 10000
const MENTION_TOAST_DURATION_MS = 10000

const shouldShowDefaultTrackGuide = computed(() => {
  const tracks = trackStore.trackList

  const hasOnlyDefaultTrack = tracks.length === 1
  if (!hasOnlyDefaultTrack) return false

  const defaultTrack = tracks[0]
  const hasNoClips = !defaultTrack.clips || defaultTrack.clips.length === 0

  return hasNoClips
})

function handleDefaultTrackBrowse() {
  const defaultTrack = trackStore.trackList[0]

  if (!defaultTrack) return

  trackStore.selectedTrackId = defaultTrack.trackId
  toolbarFileInputRef.value?.click()
}

// 현재 내 정보 (토큰에서 추출)
const currentUserId = computed(() => {
  if (!authStore.accessToken) return null
  try {
    const payload = JSON.parse(atob(authStore.accessToken.split('.')[1]))
    return Number(payload.sub) || payload.userId || payload.memberId || null
  } catch(e) {
    return null
  }
})

function trimCommentPreview(content: string, maxLength = 88) {
  const normalized = content.replace(/\s+/g, ' ').trim()

  if (normalized.length <= maxLength) {
    return normalized
  }

  return `${normalized.slice(0, maxLength - 1)}...`
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function formatCommentLocation(location: number) {
  if (Number.isInteger(location)) {
    return String(location)
  }

  return location.toFixed(2).replace(/\.?0+$/, '')
}

function removeCommentToast(toastId: number) {
  const timer = commentToastTimers.get(toastId)
  if (timer) {
    clearTimeout(timer)
    commentToastTimers.delete(toastId)
  }

  commentToasts.value = commentToasts.value.filter(toast => toast.id !== toastId)
}

function pushCommentToast(toast: CommentToast, durationMs: number) {
  if (commentToasts.value.length >= 3) {
    const oldestToast = commentToasts.value[commentToasts.value.length - 1]
    if (oldestToast) {
      removeCommentToast(oldestToast.id)
    }
  }

  commentToasts.value = [toast, ...commentToasts.value]

  const timer = window.setTimeout(() => {
    removeCommentToast(toast.id)
  }, durationMs)

  commentToastTimers.set(toast.id, timer)
}

function openTimelineCommentThread(toastId: number, trackId: number, location: number) {
  const container = timelineContainerRef.value
  if (!container) return

  removeCommentToast(toastId)

  const targetEl = container.querySelector(
    `[data-track-id="${trackId}"]`,
  ) as HTMLElement | null

  if (!targetEl) return

  const contentTop = getElementContentTop(container, targetEl)
  const targetLeft = Math.max(
    0,
    (location - 1) * trackStore.pixelPerBar - Math.max(container.clientWidth * 0.28, 160),
  )

  container.scrollTo({
    top: Math.max(0, contentTop - 80),
    left: targetLeft,
    behavior: 'smooth',
  })

  window.setTimeout(() => {
    document.dispatchEvent(new CustomEvent('open-track-comment', {
      detail: {
        trackId: String(trackId),
        measure: location,
      },
    }))
  }, 260)
}

function isCurrentUserMentionedInContent(content: string) {
  const userId = currentUserId.value

  if (!userId || !content) {
    return false
  }

  const currentMember = trackStore.projectMembers.find(member => member.userId === userId)

  if (!currentMember?.nickname) {
    return false
  }

  const escapedNickname = escapeRegExp(currentMember.nickname)
  const mentionPattern = new RegExp(`(^|\\s)@${escapedNickname}(?=\\s|$|[.,!?)]|:)`)

  return mentionPattern.test(content)
}

function isCurrentUserMentionedInComment(data: {
  content: string
  mentionedUsers: {
    userId: number
  }[]
}) {
  const userId = currentUserId.value

  if (!userId) {
    return false
  }

  const isMentionedByPayload = data.mentionedUsers.some(user => user.userId === userId)

  if (isMentionedByPayload) {
    return true
  }

  return isCurrentUserMentionedInContent(data.content)
}

function notifyIncomingComment(data: {
  trackId: number
  commentId: number
  parentCommentId: number | null
  content: string
  location: number
  author: {
    userId: number
    nickname: string
    profileImgUrl: string | null
  }
  mentionedUsers: {
    userId: number
  }[]
}) {
  if (data.author.userId === currentUserId.value) {
    return
  }

  const isMentioned = isCurrentUserMentionedInComment(data)
  const trackName = findTrackName(String(data.trackId))
  const locationLabel = formatCommentLocation(data.location)

  pushCommentToast(
    {
      id: data.commentId,
      variant: isMentioned ? 'mention' : 'comment',
      title: isMentioned
        ? `${data.author.nickname}님이 회원님을 언급했습니다`
        : `${data.author.nickname}님이 새 코멘트를 남겼습니다`,
      meta: `${trackName} · ${locationLabel}마디`,
      content: trimCommentPreview(data.content),
      trackId: data.trackId,
      location: data.location,
      author: data.author.nickname,
      profileImageUrl: data.author.profileImgUrl,
    },
    isMentioned ? MENTION_TOAST_DURATION_MS : COMMENT_TOAST_DURATION_MS,
  )
}

const {
  onlineUsers,
  projectName,
  syncProjectNameFromStore,
  registerProjectSocketHandlers,
  connectProjectSocket,
  disconnectProjectSocket,
  handleRename,
} = useProjectCollaboration(Number(projectId))

const { lastSavedTime, handleSave } = useProjectSave(Number(projectId));
const TIMELINE_TRACK_HEADER_WIDTH = 266

//휠 이벤트를 적용할 컨테이너
const timelineContainerRef = ref<HTMLElement | null>(null)
const masterTrackWrapperRef = ref<HTMLElement | null>(null)
const toolbarFileInputRef = ref<HTMLInputElement | null>(null)

// 재생바 자동 스크롤: 스토어의 RAF 루프에서 직접 컨테이너를 조작하도록 컨테이너 참조를 전달
watch(timelineContainerRef, (el) => {
  trackStore.setTimelineContainer(el);
}, { immediate: true });


//휠할때 마우스가 가르키는 위치에서 휠되게 
const handleWheel = (e: WheelEvent) => {
  // 사용자가 수동으로 휠을 조작했으므로 자동 스크롤 일시 정지
  trackStore.isAutoScrollActive = false;

  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    
    const container = timelineContainerRef.value;
    if (!container) return;

    // 1. 마우스의 현재 컨테이너 내 상대적 픽셀 위치 구하기
    const rect = container.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;

    // 2. 줌 전의 스크롤 위치와 마디당 픽셀 확인
    const oldScrollLeft = container.scrollLeft;
    const oldPixelPerBar = trackStore.pixelPerBar;

    // 3. 현재 마우스가 가리키고 있는 '음악적 위치(마디)' 계산
    // 예: (스크롤 500px + 마우스 200px) / 마디당 120px = 5.83마디 지점
    const mouseBarPos = (oldScrollLeft + mouseX) / oldPixelPerBar;

    // 4. 줌 레벨 변경 (스토어 업데이트)
    trackStore.updateZoom(e.deltaY);

    // 5. 변경된 줌 배율이 적용된 후의 마디당 픽셀 확인
    const newPixelPerBar = trackStore.pixelPerBar;

    // 6. 새로운 스크롤 위치 계산
    // (마우스가 가리키던 마디 지점 * 새로운 픽셀 단위) - 마우스의 화면상 픽셀 위치
    const newScrollLeft = (mouseBarPos * newPixelPerBar) - mouseX;

    // 7. 계산된 스크롤 위치를 적용하여 마우스 위치 고정
    container.scrollLeft = newScrollLeft;
  }
};

let initialPinchDistance = 0;

useEventListener(timelineContainerRef, 'touchstart', (e: TouchEvent) => {
  if (e.touches.length === 2) {
    trackStore.isAutoScrollActive = false;
    initialPinchDistance = Math.hypot(
      e.touches[0].clientX - e.touches[1].clientX,
      e.touches[0].clientY - e.touches[1].clientY
    );
  }
}, { passive: false });

useEventListener(timelineContainerRef, 'touchmove', (e: TouchEvent) => {
  if (e.touches.length === 2) {
    e.preventDefault();
    trackStore.isAutoScrollActive = false;
    
    const currentDistance = Math.hypot(
      e.touches[0].clientX - e.touches[1].clientX,
      e.touches[0].clientY - e.touches[1].clientY
    );
    
    const diff = initialPinchDistance - currentDistance;
    
    if (Math.abs(diff) > 5) {
      const container = timelineContainerRef.value;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const centerX = ((e.touches[0].clientX + e.touches[1].clientX) / 2) - rect.left;

      const oldScrollLeft = container.scrollLeft;
      const oldPixelPerBar = trackStore.pixelPerBar;
      const centerBarPos = (oldScrollLeft + centerX) / oldPixelPerBar;

      trackStore.updateZoom(diff * 3);
      
      const newPixelPerBar = trackStore.pixelPerBar;
      const newScrollLeft = (centerBarPos * newPixelPerBar) - centerX;
      container.scrollLeft = newScrollLeft;
      
      initialPinchDistance = currentDistance;
    }
  }
}, { passive: false });

let scrollRafId: number | null = null;
const handleHorizontalScroll = (e: Event) => {
  if (scrollRafId) return;
  scrollRafId = requestAnimationFrame(() => {
    scrollRafId = null;
    const target = e.target as HTMLElement;
    if (target) {
      trackStore.viewportLeft = target.scrollLeft;
      trackStore.viewportRight = target.scrollLeft + target.clientWidth;
    }
  });
};

//스페이스바 단축키 핸들러
const handleKeyDown = async (e: KeyboardEvent) => { // async 추가
  // 입력창(input, textarea)에 포커스가 있을 때는 단축키를 무시해야 합니다. (이름/볼륨 수정 중 스페이스바 띄어쓰기 보호)
  if ((e.target instanceof HTMLInputElement && e.target.type !== 'range') || e.target instanceof HTMLTextAreaElement) return;

  // 대소문자 상관없이 순수하게 C키만 눌렀을 때 코멘트 모드 전환
  if(e.code === 'KeyC' && !e.ctrlKey && !e.metaKey) {
    trackStore.toggleCommentMode();
    return;
  }

  // 스페이스바 처리
  if(e.code === 'Space' || e.key === ' '){
    e.preventDefault(); // 여기서 브라우저 기본 스크롤 동작을 완벽히 차단.
    await Tone.start(); 
    trackStore.togglePlay();
    return; // 실행 후 바로 종료
  }

// 삭제 (Delete / Backspace)
  if (e.code === 'Delete' || e.code === 'Backspace') {
    e.preventDefault();
    if (trackStore.selectedClip && trackStore.selectedTrackId) {
      trackStore.deleteClip(trackStore.selectedClip.clipId, trackStore.selectedTrackId);
      trackStore.deselectAll(); // 지운 후 선택 해제
    } else if (trackStore.selectedTrackId && !trackStore.selectedClip) {
      // 클립 없이 트랙만 선택된 경우 트랙 자체를 삭제
      trackStore.deleteTrack(trackStore.selectedTrackId);
    }
    return;
  }
  // Shift + T: 트랙 추가 단축키
  if (e.shiftKey && e.code === 'KeyT') {
    e.preventDefault();
    trackStore.addTrack();
    return;
  }

  // Ctrl 키(또는 Mac의 Cmd 키)와 함께 누른 경우
  if (e.ctrlKey || e.metaKey) {
    if (e.code === 'KeyZ') {
      e.preventDefault();
      if (e.shiftKey) {
        trackStore.redo();
      } else {
        trackStore.undo();
      }
      return;
    }
    if (e.code === 'KeyY') {
      e.preventDefault();
      trackStore.redo();
      return;
    }

    switch (e.code) {
      case 'KeyS': // 저장
        e.preventDefault();
        handleSave();
        break;

      case 'KeyC': // 복사
        e.preventDefault();
        if (trackStore.selectedClip && trackStore.selectedTrackId) {
          trackStore.copyClip(trackStore.selectedClip, trackStore.selectedTrackId);
        }
        break;
        
      case 'KeyD': // 복제
        e.preventDefault();
        if (trackStore.selectedClip && trackStore.selectedTrackId) {
          trackStore.duplicateClip(trackStore.selectedClip, trackStore.selectedTrackId);
        }
        break;
        
      case 'KeyX': // 잘라내기
        e.preventDefault();
        if (trackStore.selectedClip && trackStore.selectedTrackId) {
          trackStore.cutClip(trackStore.selectedClip, trackStore.selectedTrackId);
          trackStore.deselectAll();
        }
        break;
        
      case 'KeyV': // 붙여넣기
        e.preventDefault();
        if (trackStore.clipboardClip) {
          // 복사했던 트랙 또는 1번 트랙
          const targetTrackId = trackStore.clipboardTrackId || trackStore.trackList[0]?.trackId;
          
          if (targetTrackId) {
            // 위치는 무조건 현재 재생바(playhead) 위치로 통일
            const targetBar = trackStore.playheadPosition;
            
            // 계산된 최종 위치(targetBar)에 붙여넣기 실행!
            trackStore.pasteClip(targetTrackId, targetBar);
          }
        }
        break;
        
      case 'KeyE': //  분할(Split)
        e.preventDefault();
        const currentBar = trackStore.playheadPosition;

        if (trackStore.selectedClip && trackStore.selectedTrackId) {
          // 1. 선택된 클립이 명확히 있으면 그 클립만 안전하게 분할
          trackStore.splitClip(trackStore.selectedClip.clipId, trackStore.selectedTrackId);
        } else if (trackStore.selectedTrackId) {
          // 2. 선택된 클립이 없다면, 선택된 트랙이 있는지 확인하고 해당 트랙의 클립만 분할
          const track = trackStore.trackList.find((t: any) => t.trackId === trackStore.selectedTrackId);
          if (track) {
            const clipUnderPlayhead = track.clips.find((c: any) => 
              currentBar > c.start && currentBar < c.start + c.duration
            );
            if (clipUnderPlayhead) {
              trackStore.splitClip(clipUnderPlayhead.clipId, track.trackId);
            } else {
              alertStore.showAlert("선택한 트랙의 재생바 위치에 자를 수 있는 오디오 클립이 없습니다.", "warning");
            }
          }
        } else {
          // 3. 아무것도 선택되지 않은 경우 분할 취소
          alertStore.showAlert("분할할 클립이나 트랙을 선택해 주세요.", "warning");
        }
        break;
      }
    }

  // Shift 키와 함께 누른 경우
  if (e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
    switch (e.code) {
      case 'KeyT': // 트랙 추가
        e.preventDefault();
        trackStore.addTrack();
        break;
    }
  }
};
//사용자가 기존에 사용하던 테마 임시 저장
let previousTheme = '';

//  현재 마우스 좌표를 기억하는 변수
let currentMouseX = 0;
let currentMouseY = 0;

const updateMousePos = (e: MouseEvent) => {
  currentMouseX = e.clientX;
  currentMouseY = e.clientY;

  // 내 마우스 좌표를 서버로 계속 쏘기
 // collabStore.sendMyCursor(e.clientX, e.clientY);
};

// 프로젝트 시작 시 트랙 정보 불러오기
onMounted(async () => {
  //페이지 진입 시 무조건 다크 모드로 강제 전환
  const rootElement = document.documentElement;
  // 사용자가 원래 쓰고 있던 테마가 라이트 모드(클래스에 'dark'가 없음)인지 확인
  if (!rootElement.classList.contains('dark')) {
      previousTheme = 'light';
      rootElement.classList.add('dark'); // 강제로 다크 모드 켜기
  } else {
      previousTheme = 'dark';
  }
  

  //id가 존재할 때만 트랙 정보 불러오기
  if(projectId){
    const numericProjectId = Number(projectId)
    await trackStore.fetchProject(Number(projectId))
    await nextTick() // fetchProject 직후 상태가 DOM에 반영될 시간을 확보
    commentStore.fetchComments(numericProjectId)

    trackEvent('project_opened', {
    project_id: numericProjectId,
  })

    syncProjectNameFromStore()
    registerProjectSocketHandlers()

    socketService.subscribe('COMMENT_ADDED', applyCommentAdded)
    socketService.subscribe('COMMENT_DELETED', applyCommentDeleted)
    socketService.subscribe('COMMENT_STATUS_CHANGED', applyCommentStatusChanged)
    socketService.subscribe('ERROR', handleSocketError)
  
    connectProjectSocket()
  }
  
  //키보드 이벤트 리스너 등록 (캡처링 단계에서 가로채서 버튼 클릭 등 방지)
  window.addEventListener('keydown', handleKeyDown, { capture: true });
  //  마우스 이동 감지
  window.addEventListener('mousemove', updateMousePos);

//브라우저 기본 줌을 막기 위해 수동으로 이벤트 리스너 등록
if(timelineContainerRef.value) {
  timelineContainerRef.value.addEventListener('wheel', handleWheel, {passive: false}) 
  }

  //사용자가 화면을 클릭 혹은 키를누르는 순간 오디오 제한 해제
  window.addEventListener('pointerdown', unlockAudioEngine, {capture: true});
  window.addEventListener('keydown', unlockAudioEngine, {capture: true});

await nextTick()

const hasSeenGuide =
  localStorage.getItem(PROJECT_GUIDE_STORAGE_KEY) === 'true'

if (FORCE_SHOW_PROJECT_GUIDE || !hasSeenGuide) {
  isProjectGuideOpen.value = true
}

})

onUnmounted(()=>{
  //키보드 이벤트 제거
  window.removeEventListener('keydown', handleKeyDown, { capture: true });
  // 마우스 감지해제
  window.removeEventListener('mousemove', updateMousePos);
  //오디오 제한 해제 리스너 제거
  window.removeEventListener('pointerdown', unlockAudioEngine, {capture: true});
  window.removeEventListener('keydown', unlockAudioEngine, {capture: true});
  // 웹소켓 연결 해제
  disconnectProjectSocket()
  // 프로젝트 페이지를 벗어날 때 오디오 재생 즉시 중지
  trackStore.stopPlay();
  // 프로젝트를 나갈 때 코멘트 모드 상태 초기화
  trackStore.isCommentMode = false;
  commentToastTimers.forEach(timer => clearTimeout(timer))
  commentToastTimers.clear()
})


const isInviteModalOpen = ref(false)
const activeSidePanel = ref<SidePanelType>(null)

function parseTrackId(trackId: string) {
  const parsed = Number(trackId)

  if (!Number.isNaN(parsed)) {
    return parsed
  }

  const matched = trackId.match(/\d+/)
  return matched ? Number(matched[0]) : 0
}

const hoveredMeasure = ref<number | null>(null)
const hoveredTrackId = ref<string | null>(null)

function applyCommentAdded(data: {
  projectId: number
  trackId: number
  commentId: number
  parentCommentId: number | null
  content: string
  location: number
  isResolved: boolean
  author: {
    userId: number
    nickname: string
    profileImgUrl: string | null
  }
  mentionedUsers: {
    userId: number
    nickname: string
    profileImgUrl: string | null
  }[]
  createdAt: string
}) {
  if (data.isResolved) return

  const trackId = String(data.trackId)

  const target = commentGroups.value.find(group =>
    group.trackId === trackId && group.measure === data.location,
  )

  const newComment: TimelineComment = {
    id: String(data.commentId),
    authorId: data.author.userId,
    author: data.author.nickname,
    content: data.content,
    color: '#d93ce6',
    profileImageUrl: data.author.profileImgUrl,
  }

  if (target) {
    target.comments.push(newComment)
    target.resolved = data.isResolved
  }
  else {
    commentGroups.value.push({
      trackId,
      trackName: findTrackName(trackId),
      measure: data.location,
      resolved: data.isResolved,
      comments: [newComment],
    })
  }

  // 코멘트 스토어 동기화
  if (projectId) {
    commentStore.fetchComments(Number(projectId));
  }
  
  // 내가 작성한 코멘트가 아니라면 알림 점 표시
  if (data.author.userId !== currentUserId.value) {
    commentStore.setHasNewComment(true)
  }

  notifyIncomingComment(data)
}

function findTrackName(trackId: string) {
  const numericTrackId = Number(trackId)

  if (trackStore.masterTrack.trackId === numericTrackId) {
    return trackStore.masterTrack.name
  }

  return trackStore.trackList.find((track: any) =>
    track.trackId === numericTrackId
  )?.name ?? `트랙 ${trackId}`
}

function applyCommentDeleted(data: {
  projectId: number
  trackId: number
  commentId: number
  parentCommentId: number | null
}) {
  const trackId = String(data.trackId)
  const commentId = String(data.commentId)

  commentGroups.value = commentGroups.value
    .map(group => {
      if (group.trackId !== trackId) return group

      return {
        ...group,
        comments: group.comments.filter(comment => comment.id !== commentId),
      }
    })
    .filter(group => group.comments.length > 0)

  if (projectId) {
    commentStore.fetchComments(Number(projectId));
  }
}

function applyCommentStatusChanged(data: {
  projectId: number
  trackId: number
  commentId: number
  parentCommentId: number | null
  isResolved: boolean
  updatedAt: string
}) {
  const commentId = String(data.commentId)

  if (data.isResolved) {
    commentGroups.value = commentGroups.value.filter(group =>
      !group.comments.some(comment => comment.id === commentId),
    )
  } else {
    const trackId = String(data.trackId)
    const targetGroup = commentGroups.value.find(group =>
      group.trackId === trackId &&
      group.comments.some(comment => comment.id === commentId),
    )

    if (!targetGroup) return
    targetGroup.resolved = false
  }

  if (projectId) {
    commentStore.fetchComments(Number(projectId));
  }
}

function handleSocketError(error: {
  code: number
  message: string
}) {
 // console.error('[댓글 웹소켓 에러]', error)
}

function handleResolveComment(payload: {
  trackId: string
  measure: number
}) {
  const targetGroup = commentGroups.value.find(group =>
    group.trackId === payload.trackId && group.measure === payload.measure,
  )

  const firstComment = targetGroup?.comments[0]

  if (!firstComment) return

  socketService.publish('COMMENT_STATUS_CHANGE', {
    commentId: Number(firstComment.id),
  })
}

function handleDeleteComment(payload: {
  commentId: number
}) {
  socketService.publish('COMMENT_DELETE', {
    commentId: payload.commentId,
  })
}

const commentGroups = ref<TrackMeasureCommentGroup[]>([])

watch(
  () => commentStore.comments,
  (newComments) => {
    const newGroups = new Map<string, TrackMeasureCommentGroup>()

    newComments.forEach((rootComment) => {
      if (rootComment.isResolved) return

      const trackIdStr = String(rootComment.trackId)
      // 마스터 트랙은 인라인 코멘트를 지원하지 않으므로 무시
      if (trackStore.masterTrack && trackIdStr === String(trackStore.masterTrack.trackId)) return;

      const key = `${trackIdStr}-${rootComment.location}`
      
      const newComment: TimelineComment = {
        id: String(rootComment.commentId),
        authorId: rootComment.author?.userId,
        author: rootComment.author?.nickname || 'Unknown',
        content: rootComment.content,
        color: '#d93ce6',
        profileImageUrl: rootComment.author?.profileImgUrl,
      }
      
      const replyComments: TimelineComment[] = (rootComment.replies || []).map(reply => ({
        id: String(reply.commentId),
        authorId: reply.author?.userId,
        author: reply.author?.nickname || 'Unknown',
        content: reply.content,
        color: '#d93ce6',
        profileImageUrl: reply.author?.profileImgUrl,
      }))
      
      if (newGroups.has(key)) {
        const group = newGroups.get(key)!
        group.comments.push(newComment, ...replyComments)
        if (rootComment.isResolved === false) {
          group.resolved = false
        }
      } else {
        newGroups.set(key, {
          trackId: trackIdStr,
          trackName: findTrackName(trackIdStr),
          measure: rootComment.location,
          resolved: rootComment.isResolved,
          comments: [newComment, ...replyComments],
        })
      }
    })

    commentGroups.value = Array.from(newGroups.values())
  },
  { immediate: true, deep: true }
)

const isExportModalOpen = ref(false)

function handleExport() {
  isExportModalOpen.value = true
}

const isVersionSaveModalOpen = ref(false)

function handleSaveVersion() {
  isVersionSaveModalOpen.value = true
}

function handleUndo() {
  trackStore.undo()
}

function handleRedo() {
  trackStore.redo()
}

function handleOpenInvite() {
  isInviteModalOpen.value = true
}

function handleCloseInvite() {
  isInviteModalOpen.value = false
}

function handleOpenHistory() {
  activeSidePanel.value = activeSidePanel.value === 'history' ? null : 'history'
}

function handleOpenComments() {
  commentStore.setHasNewComment(false)
  activeSidePanel.value = activeSidePanel.value === 'comments' ? null : 'comments'
}

function handleOpenHelp() {
  activeSidePanel.value = activeSidePanel.value === 'help' ? null : 'help'
}

function startAiTutorial() {
  activeSidePanel.value = null
  isProjectGuideOpen.value = true
}

function handleCloseSidePanel() {
  activeSidePanel.value = null
}

function handleHoverMeasure(payload: { trackId: string | null, measure: number | null }) {
 // console.log('호버 이벤트 수신:', payload)

  hoveredTrackId.value = payload.trackId
  hoveredMeasure.value = payload.measure
}

function handleSubmitInlineComment(payload: {
  trackId: string
  trackName: string
  measure: number
  content: string
  parentCommentId?: number | null
  mentionedUserIds: number[]
}) {
  const trimmed = payload.content.trim()

  if (!trimmed) return

  const trackId = parseTrackId(payload.trackId)

  // console.log('[댓글 등록 직전]', {
  //   originalTrackId: payload.trackId,
  //   parsedTrackId: trackId,
  //   trackName: payload.trackName,
  //   measure: payload.measure,
  // })

  socketService.publish('COMMENT_ADD', {
    trackId,
    parentCommentId: payload.parentCommentId || null,
    content: trimmed,
    location: payload.measure,
    mentionedUserIds: payload.mentionedUserIds || [],
  })

  trackEvent('comment_created', {
    project_id: Number(projectId),
    track_id: trackId,
    comment_length: trimmed.length,
  })
}

function handlePanelResolveComment(commentId: number) {
  socketService.publish('COMMENT_STATUS_CHANGE', {
    commentId,
  })
}

function handlePanelAddReply(parentCommentId: number, content: string, mentionedUserIds: number[]) {
  const parent = commentStore.comments.find(c => c.commentId === parentCommentId);
  if (!parent) return;

  socketService.publish('COMMENT_ADD', {
    trackId: parent.trackId,
    parentCommentId,
    content: content.trim(),
    location: parent.location,
    mentionedUserIds: mentionedUserIds || [],
  })
}

const {
  aiAnalyzing,
  activeAiAnalysisId,
  aiAnalysisItems,
  shouldShowAiEqRevisionPanel,
  aiBeforeBands,
  aiAfterBands,
  activeAiMarkers,
  activeAiUiMode,
  selectedEqTrack,
  runAiAnalysis,
  handleApplyAiEq,
  handleCancelAiEq,
  handleRequestAiEqRevision,
  handleApplyClippingIssue,
  handleDismissClippingIssue,
  hasActionableAiIssues,
  handleApplyAll,
  setActiveAiAnalysis,
  checkIsClippingApplied,
  getClippingAppliedInfo,
  aiSuccessMessage,
} = useProjectAiWorkflow(Number(projectId))

provide('aiAnalysisItems', aiAnalysisItems)
provide('activeAiAnalysisId', activeAiAnalysisId)
provide('aiAnalyzing', aiAnalyzing)

function handleAddEqBand(payload: {
  frequencyHz: number
  gainDeltaDb: number
  isAiEq?: boolean
}) {
  if (!trackStore.selectedTrackId) return

  trackStore.addTrackEqBand(
    trackStore.selectedTrackId,
    payload,
  )
}

function handleUpdateEqBand(payload: {
  bandOrder: number
  patch: Partial<TrackEqBandState>
  isAiEq?: boolean
}) {
  if (!trackStore.selectedTrackId) return

  trackStore.updateTrackEqBand(
    trackStore.selectedTrackId,
    payload.bandOrder,
    payload.patch,
  )
}

function handleRemoveEqBand(payload: {
  bandOrder: number
  isAiEq?: boolean
}) {
  if (!trackStore.selectedTrackId) return

  trackStore.removeTrackEqBand(
    trackStore.selectedTrackId,
    payload.bandOrder,
  )
}

//브라우저 오디오 제한 강제 해제
const unlockAudioEngine = async () => {
  if(Tone.getContext().state !== 'running') {
    await Tone.start();
   // console.log('브라우저 오디오 제한 해제 완료')
  }

  //한번 풀렸으면 더 이상 이벤트 감지 필요 없으므로 리스너 삭제
  window.removeEventListener('pointerdown', unlockAudioEngine);
  window.removeEventListener('keydown', unlockAudioEngine);
}

// 툴바 액션 핸들러
function handleActionCopy() {
  if (trackStore.selectedClip && trackStore.selectedTrackId) {
    trackStore.copyClip(trackStore.selectedClip, trackStore.selectedTrackId);
  }
}

function handleActionCut() {
  if (trackStore.selectedClip && trackStore.selectedTrackId) {
    trackStore.cutClip(trackStore.selectedClip, trackStore.selectedTrackId);
    trackStore.deselectAll();
  }
}

function handleActionUpload() {
  if (trackStore.selectedTrackId && toolbarFileInputRef.value) {
    toolbarFileInputRef.value.click();
  }
}

async function handleToolbarFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const selectedTrackId = trackStore.selectedTrackId
  if (!selectedTrackId) {
    alertStore.showAlert("오디오를 업로드할 트랙을 먼저 선택해 주세요.", "warning");
    target.value = '';
    return;
  }

  try {
    await trackStore.uploadAndAddAudioClip(
      file,
      selectedTrackId,
      trackStore.playheadPosition,
    )

    trackEvent('audio_uploaded', {
      project_id: Number(projectId),
      track_id: selectedTrackId,
      file_type: file.type,
      file_size_mb: Number((file.size / 1024 / 1024).toFixed(1)),
    })
  }
  finally {
    target.value = ''
  }
}

function handleActionPaste() {
  if (trackStore.clipboardClip) {
    const targetTrackId = trackStore.clipboardTrackId || trackStore.trackList[0]?.trackId;
    const targetBar = trackStore.playheadPosition;

    if (targetTrackId) {
      trackStore.pasteClip(targetTrackId, targetBar);
    }
  }
}

function handleActionDuplicate() {
  if (trackStore.selectedClip && trackStore.selectedTrackId) {
    trackStore.duplicateClip(trackStore.selectedClip, trackStore.selectedTrackId);
  }
}

function handleActionSplit() {
  const currentBar = trackStore.playheadPosition;

  if (trackStore.selectedClip && trackStore.selectedTrackId) {
    trackStore.splitClip(trackStore.selectedClip.clipId, trackStore.selectedTrackId);
  } else if (trackStore.selectedTrackId) {
    const track = trackStore.trackList.find((t: any) => t.trackId === trackStore.selectedTrackId);
    if (track) {
      const clipUnderPlayhead = track.clips.find((c: any) => 
        currentBar > c.start && currentBar < c.start + c.duration
      );
      if (clipUnderPlayhead) {
        trackStore.splitClip(clipUnderPlayhead.clipId, track.trackId);
      } else {
        alertStore.showAlert("선택한 트랙의 재생바 위치에 자를 수 있는 오디오 클립이 없습니다.", "warning");
      }
    }
  } else {
    alertStore.showAlert("분할할 클립이나 트랙을 선택해 주세요.", "warning");
  }
}

function handleActionDelete() {
  if (trackStore.selectedClip && trackStore.selectedTrackId) {
    trackStore.deleteClip(trackStore.selectedClip.clipId, trackStore.selectedTrackId);
    trackStore.deselectAll();
  } else if (trackStore.selectedTrackId) {
    trackStore.deleteTrack(trackStore.selectedTrackId);
  }
}

function handleActionAddTrack() {
  trackStore.addTrack();
}

// 전역 파일 드래그 앤 드롭 에러 방지 처리
const isInvalidDropModalOpen = ref(false);

const onGlobalDragOver = (e: DragEvent) => {
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'copy'; // 드롭 이벤트를 발생시키기 위해 copy로 설정
  }
};

const onGlobalDrop = (e: DragEvent) => {
  // 브라우저의 기본 파일 열기 동작 차단
  
  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    // 트랙 내부의 이벤트 리스너(stopPropagation)를 거치지 않고 여기까지 올라온 이벤트는
    // 빈 공간이나 헤더 등에 드롭한 잘못된 위치의 드롭임.
    isInvalidDropModalOpen.value = true;
  }
};

// 스크롤바 클릭 시 트랙 선택 취소(deselect) 방지 로직
function handleBackgroundPointerDown(e: PointerEvent) {
  const target = e.currentTarget as HTMLElement;
  
  if (e.target === target) {
    const rect = target.getBoundingClientRect();
    // 스크롤바 영역(컨텐츠 너비/높이를 넘어선 부분) 클릭인지 판별
    const isScrollbarClick = 
      e.clientX >= rect.left + target.clientWidth ||
      e.clientY >= rect.top + target.clientHeight;
      
    if (isScrollbarClick) {
      // 스크롤바 조작 시 자동 스크롤 일시 정지
      trackStore.isAutoScrollActive = false;
      return; // 스크롤바를 누른 경우 선택 해제 무시
    }
  }
  
  trackStore.deselectAll();
}

type AiBubblePosition = {
  mode: 'absolute'
  top: number
}

function getElementContentTop(container: HTMLElement, targetEl: HTMLElement) {
  const containerRect = container.getBoundingClientRect()
  const targetRect = targetEl.getBoundingClientRect()

  return targetRect.top - containerRect.top + container.scrollTop
}

function getAiBubblePosition(conflict: any): AiBubblePosition {
  const container = timelineContainerRef.value

  if (!container || !conflict) {
    return {
      mode: 'absolute',
      top: 12,
    }
  }

  if (conflict.kind === 'CLIPPING') {
    return {
      mode: 'absolute',
      top: 12,
    }
  }

  if (conflict.kind === 'BAND_OVERLAP') {
    return {
      mode: 'absolute',
      top: 12,
    }
  }

  if (conflict.kind === 'HARSHNESS' && conflict.targetTrackId) {
    const targetEl = container.querySelector(
      `[data-track-id="${conflict.targetTrackId}"]`,
    ) as HTMLElement | null

    if (!targetEl) {
      return {
        mode: 'absolute',
        top: 12,
      }
    }

    const contentTop = getElementContentTop(container, targetEl)

    return {
      mode: 'absolute',
      top: Math.max(12, contentTop - 34 - 20),
    }
  }

  return {
    mode: 'absolute',
    top: 12,
  }
}

function scrollToAiConflict(conflict: any) {
  const container = timelineContainerRef.value
  if (!container || !conflict) return

  // 스크롤은 하쉬니스만 한다.
  if (conflict.kind !== 'HARSHNESS') return
  if (!conflict.targetTrackId) return

  const targetEl = container.querySelector(
    `[data-track-id="${conflict.targetTrackId}"]`,
  ) as HTMLElement | null

  if (!targetEl) {
   // console.warn('[AI scroll] target track element not found', conflict.targetTrackId)
    return
  }

  const contentTop = getElementContentTop(container, targetEl)

  container.scrollTo({
    top: Math.max(0, contentTop - 80),
    behavior: 'smooth',
  })
}


const PROJECT_GUIDE_STORAGE_KEY = 'studion-project-guide-seen'

const FORCE_SHOW_PROJECT_GUIDE =
  import.meta.env.VITE_FORCE_PROJECT_GUIDE === 'true'

const isProjectGuideOpen = ref(false)

const projectGuideSteps = [
  {
    selector: '[data-guide="timeline"]',
    title: '작업 영역 (타임라인)',
    description: '타임라인 빈 공간에 오디오 파일(.mp3, .wav)을 드래그 앤 드롭하여 새 트랙을 추가해 보세요.',
  },
  {
    selector: '[data-guide="play-controls"]',
    title: '재생 및 제어',
    description: '스페이스바를 누르거나 재생 버튼을 클릭해 음악을 들어보세요.',
  },
  {
    selector: '[data-guide="version-save"]',
    title: '버전 저장',
    description: '현재 작업 상태를 버전으로 저장하세요. 버전기록된 음원을 항상 다운 받을 수 있습니다.',
  },
  {
    selector: '[data-guide="comment"]',
    title: '코멘트 모드',
    description: '단축키 \'C\'를 누르거나 이 버튼을 눌러 코멘트 모드를 켜세요. 특정 트랙과 마디에 피드백을 남길 수 있습니다.',
  },
  {
    selector: '[data-guide="ai-analysis"]',
    title: 'AI 오디오 분석 시작',
    description: 'AI가 오디오를 분석하여 주파수 마스킹(소리 겹침), 위상 캔슬링(소리 상쇄), 볼륨 불균형 등 믹싱 문제점들을 탐지합니다. 플레이 컨트롤러의 별 버튼을 눌러 스캔을 시작해 보세요.',
  },
  {
    selector: '[data-guide="ai-eq-panel"]',
    title: 'AI 스마트 EQ 조절',
    description: '탐지된 문제를 클릭하면 EQ 패널이 열립니다. AI가 제안하는 Before/After 곡선을 비교하고 \'유지할 트랙\'을 선택해 자연스러운 수정을 요청할 수 있습니다. 마음에 들면 \'AI 적용\'으로 반영하세요.',
  },
  {
    selector: '[data-guide="export"]',
    title: '음원 추출',
    description: '작업이 모두 끝났다면 프로젝트를 오디오 파일로 내보내기(Export) 해보세요!',
  },
]

function closeProjectGuide(doNotShowAgain: boolean) {
  if (doNotShowAgain) {
    localStorage.setItem(PROJECT_GUIDE_STORAGE_KEY, 'true')
  }

  isProjectGuideOpen.value = false
}


</script>

<template>
  <!-- 로딩 오버레이 -->
  <div v-if="trackStore.isLoading" class="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm transition-all duration-300">
    <p class="text-zinc-300 font-medium animate-pulse">프로젝트를 불러오는 중입니다...</p>
  </div>

  <!-- 세로 모드 안내 오버레이 -->
  <div class="portrait-overlay fixed inset-0 z-[10000] hidden flex-col items-center justify-center bg-black/90 backdrop-blur-md px-4 text-center">
    <div class="rounded-full bg-white/10 p-4 mb-4">
      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-white rotate-90 animate-pulse"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><line x1="12" x2="12.01" y1="18" y2="18"/></svg>
    </div>
    <h2 class="text-xl font-bold text-white mb-2">가로 모드로 변경해 주세요</h2>
    <p class="text-gray-400 text-sm leading-relaxed max-w-xs">
      원활한 음악 작업과 타임라인 스크롤을 위해<br>스마트폰/태블릿을 가로로 돌려주세요.
    </p>
  </div>

  <!--트랙과 트랙목록 내용물을 위에서 아래로 쌓음, h-screen -> 화면 전체 높이, overflow-hidden -> 넘치는 부분 숨김, bg-background -> 배경색, text-foreground -> 글자색 -->
  
  <div 
    class="flex h-screen flex-col overflow-hidden bg-background text-foreground"
    @dragover.prevent="onGlobalDragOver"
    @drop.prevent="onGlobalDrop"
  >
    <ExportModal 
      :is-open="isExportModalOpen"
      :project-name="projectName"
      @close="isExportModalOpen = false"
    />
    <ProjectHeader
  :project-name="projectName"
  :online-users="onlineUsers"
  :last-saved-at="lastSavedTime"
  :can-undo="trackStore.undoStack.length > 0"
  :can-redo="trackStore.redoStack.length > 0"
  @rename="handleRename"
  @export="handleExport"
  @save-version="handleSaveVersion"
  @save="handleSave"
  @undo="handleUndo"
  @redo="handleRedo"
  @open-invite="handleOpenInvite"
  @open-comments="handleOpenComments"
  @open-history="handleOpenHistory"
  @open-help="handleOpenHelp"
/>
    <!-- 재생 컨트롤러 컴포넌트 추가 -->
    <PlayController
      :ai-analyzing="aiAnalyzing"
      :project-id="Number(projectId)"
      :has-actionable-ai-issues="hasActionableAiIssues"
      @run-ai-analysis="runAiAnalysis"
      @apply-all-ai-issues="handleApplyAll"
      @action-upload="handleActionUpload"
      @action-copy="handleActionCopy"
      @action-cut="handleActionCut"
      @action-paste="handleActionPaste"
      @action-duplicate="handleActionDuplicate"
      @action-split="handleActionSplit"
      @action-delete="handleActionDelete"
      @action-add-track="handleActionAddTrack"
    />
    <!-- flex-1 -> 남은 공간 차지, flex-col -> 위에서 아래로 쌓음, overflow-hidden -> 넘치는 부분 숨김, bg-muted/10 -> 배경색+투명도 -->
    <!-- 툴바 공통 파일 업로드용 인풋 -->
    <input 
      type="file" 
      ref="toolbarFileInputRef" 
      accept="audio/mpeg, audio/wav" 
      class="hidden" 
      @change="handleToolbarFileUpload" 
    />

    <main class="relative flex flex-1 flex-col overflow-hidden bg-[#131313]">

      <div 
        class="relative flex-1 flex flex-col min-h-0 overflow-hidden"
        :style="{ zoom: trackStore.workspaceZoom }"
      >
        <div 
          ref="timelineContainerRef" 
          class="flex-1 overflow-x-scroll overflow-y-auto relative flex flex-col custom-scrollbar bg-[#131313]"
          :class="trackStore.isCommentMode ? 'comment-mode-active' : ''"
          data-guide="timeline"
          @pointerdown.stop="handleBackgroundPointerDown"
          @scroll="handleHorizontalScroll"
        >
        <!-- 눈금자 -->
        <div class="sticky top-0 z-50 w-max min-w-full bg-[#1c1c1c] border-b border-white/5">
          <TimelineRuler />
        </div>
     

     
        <!--  [세로 스크롤] -->
        <div class="w-max min-w-full pb-4 relative">
  <TrackList
    :hovered-measure="hoveredMeasure"
    :hovered-track-id="hoveredTrackId"
    :commented-groups="commentGroups"
    @hover-measure="handleHoverMeasure"
    @submit-inline-comment="handleSubmitInlineComment"
    @resolve-comment="handleResolveComment"
    @delete-comment="handleDeleteComment"
  >
    <template #overlays>
      <AiConflictOverlay
        v-for="conflict in aiAnalysisItems"
        :key="conflict.id"
        :conflict="conflict"
        :bubble-position="getAiBubblePosition(conflict)"
        :is-clipping-applied="checkIsClippingApplied(conflict)"
        :clipping-applied-info="getClippingAppliedInfo(conflict)"
        @open="setActiveAiAnalysis(conflict.id)"
        @apply-clipping="handleApplyClippingIssue(conflict)"
        @dismiss-clipping="handleDismissClippingIssue(conflict)"
      />
    </template>
  </TrackList>
</div>
  <DefaultTrackDropGuide
    v-if="shouldShowDefaultTrackGuide"
    @browse="handleDefaultTrackBrowse"
  />

  <div
  ref="masterTrackWrapperRef"
  class="mt-auto shrink-0 sticky bottom-0 z-70 w-max min-w-full shadow-[0_-16px_24px_rgba(0,0,0,0.5)] bg-[#1c1c1c]"
>
        <!-- 마스터 트랙 -->
          <TrackItem
            :track="trackStore.masterTrack"
            :is-master="true"
            :hovered-measure="hoveredMeasure"
            :hovered-track-id="hoveredTrackId"
            :commented-groups="commentGroups"
            @hover-measure="handleHoverMeasure"
            @submit-inline-comment="handleSubmitInlineComment"
            @resolve-comment="handleResolveComment"
            @delete-comment="handleDeleteComment"
          />
        </div>
      </div>
      </div>
      <ProjectEqPanel
        :style="{ zoom: trackStore.workspaceZoom }"
        :selected-track="selectedEqTrack"
        :ai-analyzing="aiAnalyzing"
        :ai-analyzed="shouldShowAiEqRevisionPanel"
        :ai-before-bands="aiBeforeBands"
        :ai-after-bands="aiAfterBands"
        :ai-markers="activeAiMarkers"
        :active-ai-ui-mode="activeAiUiMode"
        @apply-ai-eq="handleApplyAiEq"
        @cancel-ai-eq="handleCancelAiEq"
        @request-ai-eq-revision="handleRequestAiEqRevision"
        @add-eq-band="handleAddEqBand"
        @update-eq-band="handleUpdateEqBand"
        @remove-eq-band="handleRemoveEqBand"
      />
    
    <ProjectSidePanel
      class="z-50"
      :open="activeSidePanel !== null"
      :type="activeSidePanel"
      @close="handleCloseSidePanel"
      @resolve-comment="handlePanelResolveComment"
      @add-reply="handlePanelAddReply"
      @start-tutorial="startAiTutorial"
    />

    <div class="pointer-events-none fixed left-1/2 top-4 z-[400] flex w-full max-w-[480px] -translate-x-1/2 flex-col gap-2 px-4">
      <TransitionGroup name="comment-toast">
        <div
          v-for="toast in commentToasts"
          :key="toast.id"
          class="pointer-events-auto relative overflow-hidden rounded-[18px] border shadow-2xl backdrop-blur-md"
          :class="toast.variant === 'mention'
            ? 'border-[#FF3DCB]/50 bg-[#1b171c]/95 shadow-[0_0_0_1px_rgba(255,61,203,0.08),0_14px_40px_rgba(255,61,203,0.20)]'
            : 'border-white/18 bg-[#181818]/92 shadow-[0_18px_50px_rgba(0,0,0,0.32)]'"
          @click="openTimelineCommentThread(toast.id, toast.trackId, toast.location)"
        >
          <button
            type="button"
            class="absolute z-10 shrink-0 rounded-full p-1 text-white/35 transition hover:bg-white/8 hover:text-white/75"
            :class="toast.variant === 'mention' ? 'right-3 top-2 text-white/45' : 'right-3 top-1.5'"
            @click.stop="removeCommentToast(toast.id)"
          >
            <span class="text-[12px] font-semibold leading-none">x</span>
          </button>
          <div class="relative z-[1] flex items-center gap-2 px-3.5 py-3">
            <div
              class="flex h-[34px] w-[34px] shrink-0 items-center justify-center overflow-hidden rounded-full text-[10px] font-semibold"
              :class="toast.variant === 'mention'
                ? 'ring-1 ring-[#FF3DCB]/35 bg-[#FF3DCB]/12 text-[#FF72D7]'
                : 'bg-white/8 text-white/80'"
            >
              <img
                v-if="toast.profileImageUrl"
                :src="toast.profileImageUrl"
                class="h-full w-full object-cover"
              />
              <span v-else>{{ toast.author.slice(0, 2) }}</span>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-start gap-2 pr-6">
                <div class="flex min-w-0 items-center gap-2">
                  <p
                    class="truncate text-[13px] font-extrabold tracking-[-0.03em]"
                    :class="toast.variant === 'mention' ? 'text-[#FFF4FD]' : 'text-white'"
                  >
                    {{ toast.title }}
                  </p>
                  <span
                    class="shrink-0 rounded-full border px-1.5 py-0.5 text-[8px] font-bold tracking-[0.04em]"
                    :class="toast.variant === 'mention'
                      ? 'border-[#FF3DCB]/40 bg-[#3b2338]/88 text-[#FFB1E8]'
                      : 'border-white/16 bg-[#2a2a2a]/90 text-white/64'"
                  >
                    {{ toast.variant === 'mention' ? 'MENTION' : 'COMMENT' }}
                  </span>
                </div>
              </div>
              <div class="mt-1 flex items-end justify-between gap-2">
                <p
                  class="min-w-0 truncate text-[11px] font-semibold leading-tight text-white"
                >
                  {{ toast.content }}
                </p>
                <p class="shrink-0 text-right text-[9px] font-semibold text-white/42">
                  {{ toast.meta }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
    </main>

    <!-- 협업자 커서 렌더링 -->
    <RemoteCursors />
    <InviteCodeModal
      :open="isInviteModalOpen"
  :project-id="projectId"
  :project-name="projectName"
  @close="isInviteModalOpen = false"
    />
    
    <VersionSaveModal
      :open="isVersionSaveModalOpen"
      :project-id="Number(projectId)"
      @close="isVersionSaveModalOpen = false"
    />

    <!-- 잘못된 파일 드롭 안내 모달 -->
    <div v-if="isInvalidDropModalOpen" class="fixed inset-0 z-[9999] grid place-items-center bg-black/40 px-4 backdrop-blur-md animate-fade-in" @click.self="isInvalidDropModalOpen = false">
      <div class="relative w-full max-w-sm rounded-2xl border border-white/10 bg-card p-7 shadow-2xl transition-all flex flex-col items-center gap-4 text-center">
        <div class="rounded-full bg-red-500/20 p-3">
          <AlertTriangle class="h-6 w-6 text-red-400" />
        </div>
        <div class="text-center">
          <h3 class="text-base font-semibold text-white">잘못된 드롭 위치</h3>
          <p class="mt-2 text-sm text-gray-400">오디오 파일은 타임라인의 <span class="text-primary font-bold">트랙 작업 영역</span> 위에 드래그 앤 드롭해 주세요.</p>
        </div>
        <button @click="isInvalidDropModalOpen = false" class="mt-4 w-full rounded-md bg-primary py-2 text-sm font-semibold text-black hover:bg-primary/80 transition-colors">
          확인
        </button>
      </div>
    </div>

    <!-- AI 성공 메시지 모달 -->
    <div v-if="aiSuccessMessage" class="fixed inset-0 z-[9999] grid place-items-center bg-black/40 px-4 backdrop-blur-md animate-fade-in" @click.self="aiSuccessMessage = null">
      <div class="relative w-full max-w-sm rounded-2xl border border-white/10 bg-card p-7 shadow-2xl transition-all flex flex-col items-center gap-4 text-center">
        <div class="rounded-full bg-emerald-500/20 p-3">
          <svg class="h-6 w-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div class="text-center">
          <h3 class="text-base font-semibold text-white">AI 분석 적용 완료</h3>
          <p class="mt-2 text-sm text-gray-400">{{ aiSuccessMessage }}</p>
        </div>
      </div>
    </div>
  </div>

  <ProjectGuideOverlay
  :steps="projectGuideSteps"
  :open="isProjectGuideOpen"
  @close="closeProjectGuide"
/>
</template>

<style scoped>
/* 1. 가로/세로 스크롤바 공간 할당 */
.custom-scrollbar::-webkit-scrollbar {
  width: 12px !important;  /* 세로 스크롤바 두께 */
  height: 12px !important; /* 가로 스크롤바 두께 */
}

/* 모바일 등 좁은 화면/가로 모드에서는 터치하기 쉽게 스크롤바를 더 두껍게 만듦 */
@media (max-height: 500px), (max-width: 768px) {
  .custom-scrollbar::-webkit-scrollbar {
    width: 20px !important;
    height: 20px !important;
  }
}

/* 2. 스크롤바 배경(트랙) */
.custom-scrollbar::-webkit-scrollbar-track {
  background: #131313;
  border-radius: 8px;
}

/* 3. 스크롤바 손잡이(썸) - 회색으로 변경 */
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #52525b;
  border-radius: 8px;
  border: 3px solid #131313; /* 배경색으로 테두리를 깎아서 얇게 만듦 */
}

/* 모바일 화면에서는 테두리를 줄여서 손잡이를 실질적으로 더 두껍게(터치 영역 확대) */
@media (max-height: 500px), (max-width: 768px) {
  .custom-scrollbar::-webkit-scrollbar-thumb {
    border: 2px solid #131313; 
  }
}

/* 4. 마우스 올렸을 때 살짝 밝아짐 */
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #71717a;
}

/* 파이어폭스(Firefox) 대응 - 파이어폭스는 두께 픽셀 조절이 안되어서 얇게 렌더링 */
.custom-scrollbar {
  scrollbar-width: thin;
  scrollbar-color: #52525b #131313;
}

.comment-toast-enter-active,
.comment-toast-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.comment-toast-enter-from,
.comment-toast-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.98);
}

.comment-toast-move {
  transition: transform 0.22s ease;
}

@media (orientation: portrait) and (max-width: 768px) {
  .portrait-overlay {
    display: flex !important;
  }
}
</style>
