<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { SmilePlus, ArrowUpCircle, X, Check, Trash2, CornerDownRight } from 'lucide-vue-next'
import { useAuthStore } from '@/pages/Onboarding/stores/auth.store'
import type { TrackMeasureCommentGroup, TimelineComment } from '../types/comment.types'
import { useTrackStore } from '../store/useTrackStore';

const trackStore = useTrackStore();
const authStore = useAuthStore()

const currentUserProfileImageUrl = computed(() => {
  if (!authStore.accessToken) return null
  try {
    const payload = JSON.parse(atob(authStore.accessToken.split('.')[1]))
    return payload.profileImgUrl || null
  } catch(e) {
    return null
  }
})

const currentUserId = computed(() => {
  if (!authStore.accessToken) return null
  try {
    const payload = JSON.parse(atob(authStore.accessToken.split('.')[1]))
    return Number(payload.sub) || payload.userId || payload.memberId || null
  } catch(e) {
    return null
  }
})

type Placement = 'top' | 'bottom'

const props = defineProps<{
  trackId: string
  trackName: string
  totalBarCount: number
  pixelPerBar: number
  subDivision: number
  timelineWidth: number
  hoveredMeasure: number | null
  hoveredTrackId: string | null
  commentedGroups: TrackMeasureCommentGroup[]
}>()

const emit = defineEmits<{
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
  'track-contextmenu': [event: MouseEvent]
  'track-pointerdown': [event: MouseEvent]
  'comment-expanded': [isExpanded: boolean]
}>()

const draftComment = ref('')
const expandedMeasure = ref<number | null>(null)
const expandedCellLeft = ref(0)
const expandedPlacement = ref<Placement>('bottom')
const rootRef = ref<HTMLElement | null>(null)
const expandedAnchorRef = ref<HTMLElement | null>(null)
const expandedBoxRef = ref<HTMLElement | null>(null)
const expandedBoxStyle = ref<Record<string, string>>({})
const expandedArrowStyle = ref<Record<string, string>>({})

const mentionDropdownActive = ref(false)
const mentionQuery = ref('')
const selectedMentionIndex = ref(0)
const inputRef1 = ref<HTMLInputElement | null>(null)
const inputRef2 = ref<HTMLInputElement | null>(null)

const projectMembers = computed(() => trackStore.projectMembers || [])

const filteredMembers = computed(() => {
  if (!mentionQuery.value) return projectMembers.value
  const q = mentionQuery.value.toLowerCase()
  return projectMembers.value.filter(m => m.nickname.toLowerCase().includes(q))
})

function handleInput(e: Event) {
  const target = e.target as HTMLInputElement
  const val = target.value
  const cursorP = target.selectionStart || 0
  
  const textBeforeCursor = val.slice(0, cursorP)
  const match = textBeforeCursor.match(/@(\S*)$/)
  
  if (match) {
    mentionDropdownActive.value = true
    mentionQuery.value = match[1]
    selectedMentionIndex.value = 0
  } else {
    mentionDropdownActive.value = false
  }
}

function insertMention(member: { nickname: string }) {
  if (!mentionDropdownActive.value) return
  
  const activeInput = inputRef1.value?.contains(document.activeElement) ? inputRef1.value : inputRef2.value
  const cursorP = activeInput?.selectionStart || 0
  
  const textBeforeCursor = draftComment.value.slice(0, cursorP)
  const textAfterCursor = draftComment.value.slice(cursorP)
  
  const match = textBeforeCursor.match(/@(\S*)$/)
  if (match) {
    const startIdx = textBeforeCursor.lastIndexOf('@')
    const beforeAt = draftComment.value.slice(0, startIdx)
    const newText = beforeAt + '@' + member.nickname + ' ' + textAfterCursor
    draftComment.value = newText
    mentionDropdownActive.value = false
    
    nextTick(() => {
      const newCursorP = startIdx + member.nickname.length + 2
      if (activeInput) {
        activeInput.focus()
        activeInput.setSelectionRange(newCursorP, newCursorP)
      }
    })
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (!mentionDropdownActive.value) return
  
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedMentionIndex.value = (selectedMentionIndex.value + 1) % filteredMembers.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedMentionIndex.value = (selectedMentionIndex.value - 1 + filteredMembers.value.length) % filteredMembers.value.length
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (filteredMembers.value.length > 0) {
      insertMention(filteredMembers.value[selectedMentionIndex.value])
    }
  } else if (e.key === 'Escape') {
    mentionDropdownActive.value = false
  }
}

// 한글(IME) 조합 중 엔터 키 입력 시 발생하는 중복 등록(더블 코멘트) 이슈를 막기 위해
// composition 진행 중(e.isComposing === true)일 때는 이벤트를 무시하는 키 핸들러를 새로 도입합니다.
function handleInputKeydown(e: KeyboardEvent, measure: number) {
  if (e.isComposing) return

  if (e.key === 'Enter') {
    e.preventDefault()
    // 멘션 드롭다운이 활성인 경우 엔터는 멘션 목록의 멤버를 선택하는 동작이 우선이어야 합니다.
    if (mentionDropdownActive.value) {
      handleKeydown(e)
    } else {
      submitComment(measure)
    }
  } else {
    handleKeydown(e)
  }
}

const COMMENT_BOX_HEIGHT = 280
const COMMENT_BOX_WIDTH = 360
const COMMENT_BOX_GAP = 18
const COMMENT_BOX_ARROW_SAFE_PADDING = 28
const COMMENT_ANCHOR_OFFSET_X = 13
const COMMENT_ANCHOR_OFFSET_Y = 13
const VIEWPORT_MARGIN = 24

// [성능 최적화] 마우스 위치에서 셀 위치를 동적으로 계산 (수만 개 div 제거)
const activeCellLocation = ref<number | null>(null)
const activeCellLeft = ref(0)

// 작성자별 고유 색상 생성기 (간단한 해시)
const userColors = ['#00D06C', '#FFD700', '#FF3DCB', '#00E5FF', '#FF5722', '#B400FF']
function getAuthorColor(authorName: string) {
  if (!authorName) return userColors[0]
  let hash = 0
  for (let i = 0; i < authorName.length; i++) {
    hash = authorName.charCodeAt(i) + ((hash << 5) - hash)
  }
  return userColors[Math.abs(hash) % userColors.length]
}

let hideTimeout: ReturnType<typeof setTimeout> | null = null
const isButtonHovered = ref(false)

const onButtonMouseLeave = () => {
  isButtonHovered.value = false
  if (props.hoveredTrackId !== props.trackId || props.hoveredMeasure === null) {
    activeCellLocation.value = null
  } else {
    updateCellLocation(props.hoveredMeasure)
  }
}

function updateCellLocation(newVal: number) {
  activeCellLocation.value = newVal
  const safeSubDivision = Math.max(1, props.subDivision)
  const totalSubs = Math.round((newVal - 1) * safeSubDivision)
  const bar = Math.floor(totalSubs / safeSubDivision) + 1
  const sub = totalSubs % safeSubDivision
  const subCellW = props.pixelPerBar / safeSubDivision
  activeCellLeft.value = (bar - 1) * props.pixelPerBar + sub * subCellW
}

watch(() => [props.hoveredMeasure, props.hoveredTrackId], ([newMeasure, newTrackId]) => {
  if (newMeasure === null || newTrackId !== props.trackId) {
    if (hideTimeout) return
    hideTimeout = setTimeout(() => {
      activeCellLocation.value = null
    }, 50)
    return
  }

  if (hideTimeout) {
    clearTimeout(hideTimeout)
    hideTimeout = null
  }

  // 버튼에 마우스가 올라가 있다면 위치를 고정 (마우스가 옆으로 살짝 새어도 도망가지 않음)
  if (isButtonHovered.value) return

  updateCellLocation(newMeasure as number)
}, { immediate: true })

function isSameLocation(a: number, b: number) {
  return Math.abs(a - b) < 0.0001
}

function hasComment(location: number) {
  return props.commentedGroups.some(
    group =>
      group.trackId === props.trackId &&
      isSameLocation(group.measure, location),
  )
}

function getCommentGroup(location: number) {
  return props.commentedGroups.find(
    group =>
      group.trackId === props.trackId &&
      isSameLocation(group.measure, location),
  ) ?? null
}

function getPreviewComment(location: number) {
  return getCommentGroup(location)?.comments?.[0] ?? null
}

function isExpanded(location: number) {
  return expandedMeasure.value !== null &&
    isSameLocation(expandedMeasure.value, location)
}

async function openCommentBox(measure: number, event?: MouseEvent) {
  isButtonHovered.value = false
  document.dispatchEvent(new CustomEvent('close-other-comments', { detail: props.trackId }))
  
  expandedMeasure.value = measure

  const safeSubDivision = Math.max(1, props.subDivision)
  const totalSubs = Math.round((measure - 1) * safeSubDivision)
  const bar = Math.floor(totalSubs / safeSubDivision) + 1
  const sub = totalSubs % safeSubDivision
  const subCellW = props.pixelPerBar / safeSubDivision
  expandedCellLeft.value = (bar - 1) * props.pixelPerBar + sub * subCellW

  nextTick(() => {
    draftComment.value = ''
    emit('comment-expanded', true)
  })

  await nextTick()
  updateExpandedBoxPosition()
}

function closeCommentBox() {
  expandedMeasure.value = null
  draftComment.value = ''
  activeCellLocation.value = null
  mentionDropdownActive.value = false
  emit('hover-measure', { trackId: null, measure: null })
  emit('comment-expanded', false)
}

function updateExpandedBoxPosition() {
  if (expandedMeasure.value === null || !expandedAnchorRef.value) {
    return
  }

  const anchorRect = expandedAnchorRef.value.getBoundingClientRect()
  const anchorX = anchorRect.left
  const anchorY = anchorRect.top
  const availableAbove = anchorY - VIEWPORT_MARGIN
  const availableBelow = window.innerHeight - anchorY - VIEWPORT_MARGIN

  if (availableBelow >= COMMENT_BOX_HEIGHT + COMMENT_BOX_GAP) {
    expandedPlacement.value = 'bottom'
  } else if (availableAbove >= COMMENT_BOX_HEIGHT + COMMENT_BOX_GAP) {
    expandedPlacement.value = 'top'
  } else {
    expandedPlacement.value = availableBelow >= availableAbove ? 'bottom' : 'top'
  }

  const boxLeft = Math.min(
    Math.max(anchorX - COMMENT_BOX_WIDTH / 2, VIEWPORT_MARGIN),
    window.innerWidth - VIEWPORT_MARGIN - COMMENT_BOX_WIDTH,
  )
  const boxTop = expandedPlacement.value === 'top'
    ? Math.max(VIEWPORT_MARGIN, anchorY - COMMENT_BOX_HEIGHT - COMMENT_BOX_GAP)
    : Math.min(window.innerHeight - VIEWPORT_MARGIN - COMMENT_BOX_HEIGHT, anchorY + COMMENT_BOX_GAP)
  const arrowLeft = Math.min(
    Math.max(anchorX - boxLeft, COMMENT_BOX_ARROW_SAFE_PADDING),
    COMMENT_BOX_WIDTH - COMMENT_BOX_ARROW_SAFE_PADDING,
  )

  expandedBoxStyle.value = {
    left: `${boxLeft}px`,
    top: `${boxTop}px`,
  }
  expandedArrowStyle.value = {
    left: `${arrowLeft}px`,
  }
}

function submitComment(measure: number) {
  const trimmed = draftComment.value.trim()

  if (!trimmed) return

  if (mentionDropdownActive.value) {
      return // 드롭다운에서 Enter키를 눌러 멘션이 적용된 경우 실제 전송 방지
  }

  const mentionedUserIds: number[] = []
  const matches = trimmed.match(/@([^\s]+)/g) || []
  const uniqueNicknames = [...new Set(matches.map(m => m.slice(1)))]
  
  uniqueNicknames.forEach(nick => {
    const found = projectMembers.value.find(m => m.nickname === nick)
    if (found && !mentionedUserIds.includes(found.userId)) {
      mentionedUserIds.push(found.userId)
    }
  })

  const group = getCommentGroup(measure)
  const parentCommentId = group && group.comments.length > 0 ? Number(group.comments[0].id) : null

  emit('submit-inline-comment', {
    trackId: props.trackId,
    trackName: props.trackName,
    measure,
    content: trimmed,
    parentCommentId,
    mentionedUserIds
  })

  draftComment.value = ''
  mentionDropdownActive.value = false
}

function requestDeleteComment(commentId: string | number) {
  const parsedCommentId = Number(commentId)

  if (!Number.isInteger(parsedCommentId)) {
   // console.error('[댓글 삭제 실패] 유효하지 않은 commentId:', commentId)
    return
  }

  emit('delete-comment', {
    commentId: parsedCommentId,
  })
}

function handleOutsideClick(event: MouseEvent) {
  if (!rootRef.value) return

  const target = event.target as Node

  if (rootRef.value.contains(target)) return
  if (expandedBoxRef.value?.contains(target)) return

  closeCommentBox()
}

function handleCloseOtherComments(e: Event) {
  const customEvent = e as CustomEvent
  if (customEvent.detail !== props.trackId) {
    closeCommentBox()
  }
}

function handleOpenTrackComment(e: Event) {
  const customEvent = e as CustomEvent<{ trackId: string, measure: number }>
  const detail = customEvent.detail

  if (!detail || detail.trackId !== props.trackId) {
    return
  }

  activeCellLocation.value = detail.measure
  updateCellLocation(detail.measure)
  openCommentBox(detail.measure)
}

function handleViewportChange() {
  updateExpandedBoxPosition()
}

onMounted(() => {
  document.addEventListener('mousedown', handleOutsideClick)
  document.addEventListener('close-other-comments', handleCloseOtherComments)
  document.addEventListener('open-track-comment', handleOpenTrackComment)
  window.addEventListener('resize', handleViewportChange)
  window.addEventListener('scroll', handleViewportChange, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
  document.removeEventListener('close-other-comments', handleCloseOtherComments)
  document.removeEventListener('open-track-comment', handleOpenTrackComment)
  window.removeEventListener('resize', handleViewportChange)
  window.removeEventListener('scroll', handleViewportChange, true)
})

// 댓글 마커 클러스터링
interface FlatCommentMarker {
  measure: number
  x: number
  group: TrackMeasureCommentGroup
}

interface CommentCluster {
  x: number
  items: FlatCommentMarker[]
}

const flatCommentMarkers = computed<FlatCommentMarker[]>(() => {
  return props.commentedGroups
    .filter(group => group.trackId === props.trackId)
    .map(group => ({
      measure: group.measure,
      x: (group.measure - 1) * props.pixelPerBar,
      group,
    }))
    .sort((a, b) => a.x - b.x)
})

const shouldClusterComments = computed(() =>
  props.pixelPerBar < 120,
)

const clusterMergeDistance = computed(() =>
  shouldClusterComments.value ? 40 : 0,
)

const clusteredCommentMarkers = computed<CommentCluster[]>(() => {
  const markers = flatCommentMarkers.value

  if (!markers.length) return []

  if (!shouldClusterComments.value) {
    return markers.map(marker => ({
      x: marker.x,
      items: [marker],
    }))
  }

  const clusters: CommentCluster[] = []

  for (const marker of markers) {
    const lastCluster = clusters[clusters.length - 1]

    if (!lastCluster) {
      clusters.push({
        x: marker.x,
        items: [marker],
      })
      continue
    }

    const lastClusterX = lastCluster.x

    if (marker.x - lastClusterX <= clusterMergeDistance.value) {
      lastCluster.items.push(marker)
      lastCluster.x =
        lastCluster.items.reduce((sum, item) => sum + item.x, 0) /
        lastCluster.items.length
    }
    else {
      clusters.push({
        x: marker.x,
        items: [marker],
      })
    }
  }

  return clusters
})

function openCommentCluster(cluster: CommentCluster, event: MouseEvent) {
  const firstItem = cluster.items[0]

  if (!firstItem) return

  activeCellLocation.value = firstItem.measure
  activeCellLeft.value = firstItem.x
  openCommentBox(firstItem.measure, event)
}
function parseMentions(content: string) {
  if (!content) return []
  const regex = /(@\S+)/g
  const parts = content.split(regex)
  return parts.map(part => ({
    text: part,
    isMention: part.startsWith('@')
  }))
}
</script>

<template>
  <div
    ref="rootRef"
    class="absolute left-0 top-0 h-full pointer-events-none"
    :style="{
      width: `${props.timelineWidth}px`,
      minWidth: `${props.timelineWidth}px`,
    }"
  >
<!-- 등록된 댓글 마커 / 클러스터 레이어 -->
    <div class="pointer-events-none absolute inset-0 z-40">
      <button
        v-for="cluster in clusteredCommentMarkers"
        :key="`${trackId}-cluster-${cluster.x}-${cluster.items.length}`"
        type="button"
        class="pointer-events-auto absolute top-1.5 z-40 translate-x-0.5 flex h-[22px] min-w-[22px] items-center justify-center rounded-[6px] border-2 px-1.5 shadow-md transition hover:border-primary before:absolute before:-inset-3 before:content-['']"
        :class="cluster.items[0].group.resolved ? 'border-green-500 bg-[#1c1c1c]' : 'border-white/60 bg-[#1c1c1c]'"
        :style="{ left: `${cluster.x}px` }"
        @mousedown.stop.prevent="openCommentCluster(cluster, $event)"
      >
        <template v-if="cluster.items.length === 1">
          <div class="flex h-[18px] w-[18px] overflow-hidden items-center justify-center rounded-full" :style="{ backgroundColor: cluster.items[0].group.comments[0]?.profileImageUrl ? 'transparent' : getAuthorColor(cluster.items[0].group.comments[0]?.author || '') }">
            <img v-if="cluster.items[0].group.comments[0]?.profileImageUrl" :src="cluster.items[0].group.comments[0]?.profileImageUrl || undefined" class="h-full w-full object-cover" />
            <span v-else class="text-[8px] font-bold text-white/90">{{ cluster.items[0].group.comments[0]?.author?.slice(0, 2) || '' }}</span>
          </div>
        </template>
        <template v-else>
          <div class="flex items-center gap-1">
            <div class="flex h-[18px] w-[18px] overflow-hidden items-center justify-center rounded-full" :style="{ backgroundColor: cluster.items[0].group.comments[0]?.profileImageUrl ? 'transparent' : getAuthorColor(cluster.items[0].group.comments[0]?.author || '') }">
              <img v-if="cluster.items[0].group.comments[0]?.profileImageUrl" :src="cluster.items[0].group.comments[0]?.profileImageUrl || undefined" class="h-full w-full object-cover" />
              <span v-else class="text-[8px] font-bold text-white/90">{{ cluster.items[0].group.comments[0]?.author?.slice(0, 2) || '' }}</span>
            </div>
            <span class="text-[10px] font-bold text-white">{{ cluster.items.length }}</span>
          </div>
        </template>
      </button>
    </div>

    <!-- [성능 최적화] 투명 오버레이 1개로 수만 개의 셀 div를 대체 -->
    <div
      class="absolute top-0 left-0 h-full"
      :class="trackStore.isCommentMode ? 'pointer-events-auto' : 'pointer-events-none z-auto'"
      :style="{ width: `${props.timelineWidth}px`, zIndex: (expandedMeasure !== null || activeCellLocation !== null) ? 120 : (trackStore.isCommentMode ? 20 : 'auto') }"
      :data-track-id="props.trackId"
      @pointerdown.stop="emit('track-pointerdown', $event)"
      @contextmenu.prevent.stop="emit('track-contextmenu', $event)"
    >
      <!-- hover된 마디 세로 강조선 -->
      <div
        v-if="trackStore.isCommentMode && activeCellLocation !== null"
        class="pointer-events-none absolute inset-y-0 w-px bg-primary"
        :style="{ left: `${activeCellLeft}px` }"
      />

      <div
        v-if="expandedMeasure !== null"
        ref="expandedAnchorRef"
        class="pointer-events-none absolute h-0 w-0"
        :style="{
          left: `${expandedCellLeft + COMMENT_ANCHOR_OFFSET_X}px`,
          top: `${COMMENT_ANCHOR_OFFSET_Y}px`,
        }"
      />

      <!-- 댓글 없는 경우: hover 시 댓글 추가 버튼 -->
      <button
        v-if="trackStore.isCommentMode && activeCellLocation !== null && !hasComment(activeCellLocation) && !isExpanded(activeCellLocation)"
        type="button"
        class="pointer-events-auto absolute top-1.5 z-40 grid h-7 w-7 translate-x-0.5 place-items-center rounded-full border-2 border-white/60 bg-[#282828] text-white shadow-md transition hover:border-primary hover:text-primary before:absolute before:-inset-4 before:content-['']"
        :style="{ left: `${activeCellLeft}px` }"
        @mousedown.stop.prevent="openCommentBox(activeCellLocation, $event)"
        @mouseenter="isButtonHovered = true"
        @mouseleave="onButtonMouseLeave"
      >
        <SmilePlus class="h-4 w-4 relative z-10" />
      </button>

      <!-- 댓글 있는 경우: hover 시 preview -->
      <button
        v-if="trackStore.isCommentMode && activeCellLocation !== null && hasComment(activeCellLocation) && !isExpanded(activeCellLocation)"
        type="button"
        class="pointer-events-auto absolute top-1.5 z-40 flex h-[26px] max-w-[300px] translate-x-0.5 items-center gap-2 overflow-hidden whitespace-nowrap rounded-[6px] border-2 border-white/60 bg-[#1c1c1c] px-2.5 shadow-xl transition hover:border-primary"
        :style="{ left: `${activeCellLeft}px` }"
        @mousedown.stop.prevent="openCommentBox(activeCellLocation, $event)"
        @mouseenter="isButtonHovered = true"
        @mouseleave="onButtonMouseLeave"
      >
        <div class="flex h-5 w-5 shrink-0 overflow-hidden items-center justify-center rounded-full" :style="{ backgroundColor: getPreviewComment(activeCellLocation)?.profileImageUrl ? 'transparent' : getAuthorColor(getPreviewComment(activeCellLocation)?.author || '') }">
          <img v-if="getPreviewComment(activeCellLocation)?.profileImageUrl" :src="getPreviewComment(activeCellLocation)?.profileImageUrl || undefined" class="h-full w-full object-cover" />
          <span v-else class="text-[9px] font-bold text-white/90">{{ getPreviewComment(activeCellLocation)?.author?.slice(0, 2) || '' }}</span>
        </div>
        <div class="shrink-0 text-[11px] font-medium text-white/60">
          {{ getPreviewComment(activeCellLocation)?.author }}
        </div>
        <p class="truncate text-[11px] text-white">
          {{ getPreviewComment(activeCellLocation)?.content }}
        </p>
      </button>

    </div>
  </div>

  <Teleport to="body">
    <!-- 확장 댓글 박스 -->
    <div
      v-if="expandedMeasure !== null"
      ref="expandedBoxRef"
      class="track-comment-box pointer-events-auto fixed z-[500] w-[360px] rounded-[6px] border border-white/20 bg-[#1c1c1c] shadow-2xl p-4"
      :style="expandedBoxStyle"
      @mousedown.stop
      @click.stop
    >
      <!-- 말풍선 꼬리 (Arrow) -->
      <div
        class="absolute h-3.5 w-3.5 -translate-x-1/2 rotate-45 border-white/20 bg-[#1c1c1c]"
        :style="expandedArrowStyle"
        :class="expandedPlacement === 'top' ? 'bottom-[-7.5px] border-b border-r' : 'top-[-7.5px] border-t border-l'"
      ></div>

      <!-- 공통 헤더: 트랙 이름 & 마디 수 -->
      <div class="mb-2.5 flex items-center justify-between border-b border-white/10 pb-2">
        <span class="text-[13px] font-semibold text-white/50">
          {{ trackStore.masterTrack.trackId === Number(props.trackId) ? trackStore.masterTrack.name : (trackStore.trackList.find(t => String(t.trackId) === props.trackId)?.name || `트랙 ${props.trackId}`) }} · {{ expandedMeasure }}마디
        </span>
        <button
          class="shrink-0 transition hover:scale-110"
          @click.stop="closeCommentBox"
          title="닫기"
        >
          <X class="h-4 w-4 text-white/40 hover:text-white" />
        </button>
      </div>

      <div v-if="!getCommentGroup(expandedMeasure)" class="relative z-10 flex items-center gap-2">
        <div class="flex h-6 w-6 shrink-0 overflow-hidden items-center justify-center rounded-full bg-[#FF3DCB]">
          <img v-if="currentUserProfileImageUrl" :src="currentUserProfileImageUrl || undefined" class="h-full w-full object-cover" />
          <span v-else class="text-[10px] font-bold text-white/90">나</span>
        </div>
        <div class="relative flex-1 flex items-center justify-between rounded-[6px] border border-white/15 bg-transparent px-2.5 py-1.5">
          <input
            ref="inputRef1"
            v-model="draftComment"
            type="text"
            placeholder="댓글 추가"
            class="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-white/40"
            @input="handleInput"
            @keydown="handleInputKeydown($event, expandedMeasure)"
          />
          <button
            class="shrink-0 transition hover:scale-110 disabled:opacity-50"
            :disabled="!draftComment.trim()"
            @click="submitComment(expandedMeasure)"
          >
            <ArrowUpCircle class="h-5 w-5 text-white/40 hover:text-white" />
          </button>

          <div v-if="mentionDropdownActive && filteredMembers.length > 0" class="absolute left-0 right-0 bottom-full mb-1 max-h-40 overflow-y-auto rounded-md border border-white/20 bg-[#2a2a2a] shadow-lg custom-scrollbar z-[130]">
            <button
              v-for="(member, index) in filteredMembers"
              :key="member.userId"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] transition-colors hover:bg-white/10"
              :class="{ 'bg-white/10': index === selectedMentionIndex }"
              @click.prevent="insertMention(member)"
              @mousedown.prevent
            >
              <div class="flex h-5 w-5 shrink-0 overflow-hidden items-center justify-center rounded-full" :style="{ backgroundColor: member.profileImageUrl ? 'transparent' : getAuthorColor(member.nickname) }">
                <img v-if="member.profileImageUrl" :src="member.profileImageUrl" class="h-full w-full object-cover" />
                <span v-else class="text-[9px] font-bold text-white/90">{{ member.nickname.slice(0, 2) }}</span>
              </div>
              <span class="text-white">{{ member.nickname }}</span>
            </button>
          </div>
        </div>
      </div>

      <div v-else class="relative z-10 flex flex-col">
        <div class="flex max-h-[300px] flex-col gap-3 overflow-y-auto custom-scrollbar">
          <div
            v-for="(comment, idx) in getCommentGroup(expandedMeasure)?.comments || []"
            :key="comment.id"
            class="group flex flex-col gap-1"
            :class="getCommentGroup(expandedMeasure)?.resolved ? 'opacity-50' : ''"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2" :class="{ 'ml-4': idx > 0 }">
                <CornerDownRight v-if="idx > 0" class="h-4 w-4 shrink-0 text-white/40" />
                <div class="flex h-6 w-6 shrink-0 overflow-hidden items-center justify-center rounded-full" :style="{ backgroundColor: comment.profileImageUrl ? 'transparent' : (comment.color || getAuthorColor(comment.author)) }">
                  <img v-if="comment.profileImageUrl" :src="comment.profileImageUrl || undefined" class="h-full w-full object-cover" />
                  <span v-else class="text-[10px] font-bold text-white/90">{{ comment.author.slice(0, 2) }}</span>
                </div>
                <span class="text-[13px] font-medium text-white/60">{{ comment.author }}</span>
              </div>
              <div class="flex items-center gap-1">
                <button
                  v-if="comment.authorId === currentUserId"
                  class="opacity-0 transition-opacity group-hover:opacity-100"
                  @click.stop="requestDeleteComment(comment.id)"
                  title="삭제"
                >
                  <Trash2 class="h-4 w-4 text-white/40 hover:text-red-400" />
                </button>
                <div v-else class="h-4 w-4" />
                <button
                  v-if="idx === 0"
                  class="transition-colors"
                  :class="getCommentGroup(expandedMeasure)?.resolved ? 'text-green-500' : 'text-white hover:text-green-400'"
                  @click.stop="emit('resolve-comment', { trackId, measure: expandedMeasure })"
                  title="해결됨 표시"
                >
                  <Check class="h-4 w-4" />
                </button>
              </div>
            </div>
            <div class="pl-[32px]" :class="{ 'ml-10': idx > 0 }">
              <p class="whitespace-pre-wrap text-[13px] leading-relaxed text-white">
                <template v-for="(part, i) in parseMentions(comment.mention ? comment.mention + ' \n' + comment.content : comment.content)" :key="i">
                  <span v-if="part.isMention" class="font-medium text-[#FF3DCB]">{{ part.text }}</span>
                  <span v-else>{{ part.text }}</span>
                </template>
              </p>
            </div>
          </div>
        </div>

        <div class="mt-3 flex items-center gap-2">
          <div class="flex h-6 w-6 shrink-0 overflow-hidden items-center justify-center rounded-full bg-[#FF3DCB]">
            <img v-if="currentUserProfileImageUrl" :src="currentUserProfileImageUrl || undefined" class="h-full w-full object-cover" />
            <span v-else class="text-[10px] font-bold text-white/90">나</span>
          </div>
          <div class="relative flex flex-1 items-center justify-between rounded-[6px] border border-white/15 bg-transparent px-2.5 py-1.5">
            <input
              ref="inputRef2"
              v-model="draftComment"
              type="text"
              placeholder="댓글 추가"
              class="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-white/40"
              @input="handleInput"
              @keydown="handleInputKeydown($event, expandedMeasure)"
            />
            <button
              class="shrink-0 transition hover:scale-110 disabled:opacity-50"
              :disabled="!draftComment.trim()"
              @click="submitComment(expandedMeasure)"
            >
              <ArrowUpCircle class="h-5 w-5 text-white/40 hover:text-white" />
            </button>

            <div v-if="mentionDropdownActive && filteredMembers.length > 0" class="absolute left-0 right-0 bottom-full mb-1 max-h-40 overflow-y-auto rounded-md border border-white/20 bg-[#2a2a2a] shadow-lg custom-scrollbar z-[130]">
              <button
                v-for="(member, index) in filteredMembers"
                :key="member.userId"
                class="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] transition-colors hover:bg-white/10"
                :class="{ 'bg-white/10': index === selectedMentionIndex }"
                @click.prevent="insertMention(member)"
                @mousedown.prevent
              >
                <div class="flex h-5 w-5 shrink-0 overflow-hidden items-center justify-center rounded-full" :style="{ backgroundColor: member.profileImageUrl ? 'transparent' : getAuthorColor(member.nickname) }">
                  <img v-if="member.profileImageUrl" :src="member.profileImageUrl" class="h-full w-full object-cover" />
                  <span v-else class="text-[9px] font-bold text-white/90">{{ member.nickname.slice(0, 2) }}</span>
                </div>
                <span class="text-white">{{ member.nickname }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
