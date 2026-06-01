<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import type { OnlineUser } from '../types/projectSocket.types'
import {
  Camera,
  Download,
  History,
  Pencil,
  Redo2,
  Save,
  Undo2,
  UserPlus,
  MessageSquare,
  CircleHelp,
} from 'lucide-vue-next'
import logoLight from '@/assets/logo_light.png'
import logoDark from '@/assets/logo_dark.png'
import { useCommentStore } from '../store/useCommentStore'
import { useTrackStore } from '../store/useTrackStore'

const commentStore = useCommentStore()
const trackStore = useTrackStore()

interface Props {
  projectName: string
  lastSavedAt?: string
  onlineUsers?: OnlineUser[]
  canUndo?: boolean
  canRedo?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  lastSavedAt: '13:24',
  onlineUsers: () => [],
  canUndo: true,
  canRedo: true,
})

const emit = defineEmits<{
  (e: 'rename', name: string): void
  (e: 'export'): void
  (e: 'save-version'): void
  (e: 'save'): void
  (e: 'undo'): void
  (e: 'redo'): void
  (e: 'open-invite'): void
  (e: 'open-comments'): void
  (e: 'open-history'): void
  (e: 'open-help'): void
}>()

const visibleOnlineUsers = computed(() => props.onlineUsers.slice(0, 3))
const hiddenOnlineUserCount = computed(() => Math.max(props.onlineUsers.length - 3, 0))

const isEditingProjectName = ref(false)
const editingProjectName = ref('')
const projectNameInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.projectName,
  (newName) => {
    if (!isEditingProjectName.value) {
      editingProjectName.value = newName || ''
    }
  },
  { immediate: true },
)

async function startProjectNameEdit() {
  isEditingProjectName.value = true
  editingProjectName.value = props.projectName || ''

  await nextTick()

  projectNameInputRef.value?.focus()
  projectNameInputRef.value?.select()
}

function submitProjectNameEdit() {
  const trimmedName = editingProjectName.value.trim()

  if (!trimmedName) {
    editingProjectName.value = props.projectName || ''
    isEditingProjectName.value = false
    return
  }

  if (trimmedName !== props.projectName) {
    emit('rename', trimmedName)
  }

  isEditingProjectName.value = false
}

function cancelProjectNameEdit() {
  editingProjectName.value = props.projectName || ''
  isEditingProjectName.value = false
}

// 프로젝트의 실제 총 재생 시간(Length) 계산
const projectLengthFormatted = computed(() => {
  let maxEndBar = 0
  trackStore.trackList.forEach(track => {
    track.clips.forEach(clip => {
      const endBar = clip.start + clip.duration
      if (endBar > maxEndBar) {
        maxEndBar = endBar
      }
    })
  })

  // trackStore의 secondsPerBar(마디당 초 단위 시간)를 사용하여 정확한 총 재생 시간(초)을 계산합니다.
  // 이 방식은 박자 분모(timeSigDenominator)와 BPM 등이 모두 반영된 정확한 값입니다.
  const totalSeconds = Math.floor(maxEndBar * trackStore.secondsPerBar)

  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) return '0:00'

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60

  return `${minutes}:${String(seconds).padStart(2, '0')}`
})

function formatAudioSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB'
  const mb = bytes / (1024 * 1024)
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

const isNearLimit = computed(() => {
  return trackStore.currentTotalSizeBytes > trackStore.maxTotalSizeBytes * 0.9
})
</script>

<template>
  <header class="relative flex h-[68px] w-full items-center justify-between border-b border-border bg-background px-4">
    <!-- 왼쪽 -->
    <div class="flex min-w-0 items-center gap-2 sm:gap-4">
      <RouterLink
        to="/dashboard"
        class="inline-flex items-center gap-4"
      >
        <div class="shrink-0">
          <img
            :src="logoLight"
            alt="StudiON"
            class="h-8 w-auto dark:hidden"
          >
          <img
            :src="logoDark"
            alt="StudiON"
            class="hidden h-8 w-auto dark:block"
          >
        </div>
      </RouterLink>

      <div class="hidden h-7 w-px bg-border md:block" />

      <div class="flex min-w-0 items-center gap-2">
        <template v-if="!isEditingProjectName">
          <span class="truncate text-sm font-semibold text-foreground">
            {{ projectName }}
          </span>

          <button
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md border border-transparent text-muted-foreground transition hover:border-border hover:bg-muted hover:text-foreground"
            @click="startProjectNameEdit"
          >
            <Pencil class="h-3.5 w-3.5" />
          </button>
        </template>

        <template v-else>
          <input
            ref="projectNameInputRef"
            v-model="editingProjectName"
            type="text"
            class="h-7 w-[160px] rounded-md border border-border bg-background px-2 text-sm font-semibold text-foreground outline-none transition focus:border-primary"
            @keydown.enter.prevent="submitProjectNameEdit"
            @keydown.esc.prevent="cancelProjectNameEdit"
            @blur="submitProjectNameEdit"
          >
        </template>
      </div>

      <!-- 새로 추가된 프로젝트 재생 시간 (대시보드와 동일한 Length) -->
      <div class="hidden lg:flex ml-2 items-center gap-1.5 rounded-lg bg-secondary/30 px-3 py-1.5 text-xs font-mono-tight text-foreground border border-border/50">
        <span class="text-[9px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">총 재생 시간 :</span>
        <span class="font-semibold text-primary/90 mt-0.5">{{ projectLengthFormatted }}</span>
      </div>

      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-lg border border-border p-2 xl:px-3 xl:py-2 text-xs font-medium text-foreground transition hover:bg-muted"
        data-guide="export"
        @click="emit('export')"
      >
        <Download class="h-4 w-4" />
        <span class="hidden xl:inline">음원 내보내기</span>
      </button>

      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-lg border border-border p-2 xl:px-3 xl:py-2 text-xs font-medium text-foreground transition hover:bg-muted"
        data-guide="version-save" 
        @click="emit('save-version')"
      >
        <Camera class="h-4 w-4" />
        <span class="hidden xl:inline">버전 저장</span>
      </button>
    </div>

    <!-- 가운데 -->
    <div class="flex items-center gap-1 sm:gap-2">
      <button
        type="button"
        class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!canUndo"
        @click="emit('undo')"
      >
        <Undo2 class="h-4 w-4" />
      </button>

      <button
        type="button"
        class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="!canRedo"
        @click="emit('redo')"
      >
        <Redo2 class="h-4 w-4" />
      </button>
      
      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-foreground transition hover:bg-muted"
        title="저장 (Ctrl + S)"
        @click="emit('save')"
      >
        <Save class="h-4 w-4" />
        <span></span>
        <span class="hidden xl:inline text-muted-foreground">{{ lastSavedAt }}</span>
      </button>
    </div>

    <!-- 오른쪽 -->
    <div class="flex items-center gap-2 lg:gap-3">
      
      <!-- 오디오 사용량 -->
      <div class="hidden lg:flex ml-2 mr-2 items-center gap-1.5 rounded-lg bg-secondary/30 px-3 py-1.5 text-xs font-mono-tight text-foreground border border-border/50" :title="`최대 ${formatAudioSize(trackStore.maxTotalSizeBytes)}까지 업로드 가능합니다.`">
        <span class="text-[9px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">내 사용량 :</span>
        <span class="font-semibold mt-0.5" :class="isNearLimit ? 'text-red-400 drop-shadow-[0_0_5px_rgba(248,113,113,0.5)]' : 'text-primary/90'">
          {{ formatAudioSize(trackStore.currentTotalSizeBytes) }} <span class="text-muted-foreground font-normal text-[10px]">/ {{ formatAudioSize(trackStore.maxTotalSizeBytes) }}</span>
        </span>
      </div>

      <!-- 접속자 프로필 -->
      <div class="hidden items-center -space-x-2 md:flex">
        <div
          v-for="user in visibleOnlineUsers"
          :key="user.userId"
          class="flex h-7 w-7 items-center justify-center overflow-hidden rounded-full border-2 border-background bg-muted text-[10px] font-semibold text-foreground"
          :title="user.nickname"
        >
          <img
            v-if="user.profileImageUrl"
            :src="user.profileImageUrl"
            :alt="user.nickname"
            class="h-full w-full object-cover"
          >
          <span v-else>
            {{ user.nickname.charAt(0) }}
          </span>
        </div>

        <div
          v-if="hiddenOnlineUserCount > 0"
          class="flex h-7 w-7 items-center justify-center rounded-full border-2 border-background bg-muted text-[10px] font-semibold text-muted-foreground"
        >
          +{{ hiddenOnlineUserCount }}
        </div>
      </div>

      <!-- 초대코드 생성 -->
      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-full border border-border p-2 xl:px-4 xl:py-2 text-xs font-medium text-foreground transition hover:bg-muted"
        @click="emit('open-invite')"
      >
        <UserPlus class="h-4 w-4" />
        <span class="hidden xl:inline">초대코드 생성</span>
      </button>

      <!-- 히스토리 (시계 아이콘) -->
      <button
        type="button"
        class="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border text-foreground transition hover:bg-muted"
        @click="emit('open-history')"
      >
        <History class="h-4 w-4" />
      </button>

      <!-- 코멘트 (말풍선 아이콘) -->
      <button
        type="button"
        class="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border text-foreground transition hover:bg-muted"
        @click="emit('open-comments')"
      >
        <MessageSquare class="h-4 w-4" />
        <span v-if="commentStore.hasNewComment" class="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
      </button>

      <!-- 도움말 -->
      <button
        type="button"
        class="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border text-foreground transition hover:bg-muted"
        @click="emit('open-help')"
      >
        <CircleHelp class="h-4 w-4" />
      </button>

    </div>
  </header>
</template>
