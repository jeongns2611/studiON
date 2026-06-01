<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { CommentDto } from '../types/comment.types'
import { Check, ArrowUpCircle, CornerDownRight } from 'lucide-vue-next'

const props = defineProps<{
  comment: CommentDto
  trackName: string
}>()

const emit = defineEmits<{
  (e: 'resolve', commentId: number): void
  (e: 'add-reply', parentCommentId: number, content: string, mentionedUserIds: number[]): void
}>()

import { useTrackStore } from '../store/useTrackStore'

const trackStore = useTrackStore()
const projectMembers = computed(() => trackStore.projectMembers || [])

const replyContent = ref('')

const mentionDropdownActive = ref(false)
const mentionQuery = ref('')
const selectedMentionIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

const filteredMembers = computed(() => {
  if (!mentionQuery.value) return projectMembers.value
  const q = mentionQuery.value.toLowerCase()
  return projectMembers.value.filter(m => m.nickname.toLowerCase().includes(q))
})

const userColors = ['#00D06C', '#FFD700', '#FF3DCB', '#00E5FF', '#FF5722', '#B400FF']
function getAuthorColor(authorName: string) {
  if (!authorName) return userColors[0]
  let hash = 0
  for (let i = 0; i < authorName.length; i++) {
    hash = authorName.charCodeAt(i) + ((hash << 5) - hash)
  }
  return userColors[Math.abs(hash) % userColors.length]
}

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
  
  const activeInput = inputRef.value
  const cursorP = activeInput?.selectionStart || 0
  
  const textBeforeCursor = replyContent.value.slice(0, cursorP)
  const textAfterCursor = replyContent.value.slice(cursorP)
  
  const match = textBeforeCursor.match(/@(\S*)$/)
  if (match) {
    const startIdx = textBeforeCursor.lastIndexOf('@')
    const beforeAt = replyContent.value.slice(0, startIdx)
    const newText = beforeAt + '@' + member.nickname + ' ' + textAfterCursor
    replyContent.value = newText
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

// 한글(IME) 조합(composition) 도중에 엔터 키를 입력할 때 대댓글이 이중 등록되는 버그를
// 해결하기 위해 isComposing 상태를 검사하여 중복 엔터 이벤트를 필터링하는 핸들러입니다.
function handleInputKeydown(e: KeyboardEvent) {
  if (e.isComposing) return

  if (e.key === 'Enter') {
    e.preventDefault()
    if (mentionDropdownActive.value) {
      handleKeydown(e)
    } else {
      handleSubmitReply()
    }
  } else {
    handleKeydown(e)
  }
}

const handleSubmitReply = () => {
  const trimmed = replyContent.value.trim()
  if (!trimmed) return
  if (mentionDropdownActive.value) return

  const mentionedUserIds: number[] = []
  const matches = trimmed.match(/@([^\s]+)/g) || []
  const uniqueNicknames = [...new Set(matches.map(m => m.slice(1)))]
  
  uniqueNicknames.forEach(nick => {
    const found = projectMembers.value.find(m => m.nickname === nick)
    if (found && !mentionedUserIds.includes(found.userId)) {
      mentionedUserIds.push(found.userId)
    }
  })

  emit('add-reply', props.comment.commentId, trimmed, mentionedUserIds)
  replyContent.value = ''
  mentionDropdownActive.value = false
}

const highlightMentions = (text: string) => {
  if (!text) return ''
  // @어쩌고 형식의 텍스트를 핑크색으로 하이라이트
  return text.replace(/(@[^\s]+)/g, '<span class="text-pink-500">$1</span>')
}
</script>

<template>
  <div class="mb-4 rounded-xl border border-white/10 bg-[#262626] p-4 text-sm text-gray-200">
    <!-- Header -->
    <div v-if="comment.author" class="mb-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <img v-if="comment.author.profileImgUrl" :src="comment.author.profileImgUrl" class="h-6 w-6 rounded-full object-cover" />
        <div v-else class="h-6 w-6 rounded-full bg-yellow-500"></div>
        <span class="font-medium text-white">{{ comment.author.nickname }}</span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs text-gray-400">{{ trackName }} &middot; {{ comment.location }}마디</span>
        <button 
          @click="emit('resolve', comment.commentId)"
          class="flex h-6 w-6 items-center justify-center rounded border border-white/20 bg-transparent text-gray-400 transition hover:bg-white/10 hover:text-white"
        >
          <Check class="h-4 w-4" />
        </button>
      </div>
    </div>

    <!-- Body -->
    <div class="mb-5 text-sm leading-relaxed" v-html="highlightMentions(comment.content)"></div>

    <!-- Replies -->
    <div class="mb-3 text-xs text-gray-400">댓글</div>
    <div v-if="comment.replies && comment.replies.length > 0" class="mb-4 flex flex-col gap-4">
      <div v-for="reply in comment.replies" :key="reply.commentId" class="flex flex-col gap-1">
        <div v-if="reply.author" class="flex items-center gap-2">
          <CornerDownRight class="h-3.5 w-3.5 shrink-0 text-gray-500" />
          <img v-if="reply.author.profileImgUrl" :src="reply.author.profileImgUrl" class="h-5 w-5 rounded-full object-cover" />
          <div v-else class="h-5 w-5 rounded-full bg-blue-500"></div>
          <span class="font-medium text-white text-xs">{{ reply.author.nickname }}</span>
        </div>
        <div class="text-sm pl-11 leading-relaxed" v-html="highlightMentions(reply.content)"></div>
      </div>
    </div>

    <!-- Input -->
    <div class="relative flex items-center gap-2">
      <!-- 현재 사용자 아바타 플레이스홀더 (이미지에서는 초록색 원) -->
      <div class="h-5 w-5 shrink-0 rounded-full bg-green-500"></div>
      <div class="relative flex-1">
        <input
          ref="inputRef"
          v-model="replyContent"
          @input="handleInput"
          @keydown="handleInputKeydown"
          type="text"
          placeholder="댓글 추가"
          class="w-full rounded-md border border-white/10 bg-[#1c1c1c] py-1.5 pl-3 pr-8 text-xs text-white placeholder-gray-500 focus:border-white/30 focus:outline-none"
        />
        <button 
          @click="handleSubmitReply"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 transition hover:text-white"
        >
          <ArrowUpCircle class="h-4 w-4" />
        </button>

        <!-- 멘션 자동완성 드롭다운 -->
        <div v-if="mentionDropdownActive && filteredMembers.length > 0" class="absolute left-0 right-0 bottom-full mb-1 max-h-40 overflow-y-auto rounded-md border border-white/20 bg-[#2a2a2a] shadow-lg custom-scrollbar z-[100]">
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
</template>
