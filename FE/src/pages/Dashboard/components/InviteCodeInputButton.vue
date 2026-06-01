<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Check, KeyRound, X } from 'lucide-vue-next'
import { Button } from '@/shared/ui/button'
import { acceptProjectInviteCode } from '@/pages/Project/api/project.api'
import type { AcceptInviteCodeResponse, ProjectId } from '@/pages/Project/types/project.types'
import { trackEvent } from '@/shared/utils/analytics'

const router = useRouter()
const isInputMode = ref(false)
const inviteCode = ref('')
const errorMessage = ref('')
const isLoading = ref(false)
const inviteInputRef = ref<HTMLInputElement | null>(null)

function resetState() {
  isInputMode.value = false
  inviteCode.value = ''
  errorMessage.value = ''
  isLoading.value = false
}

async function openInputMode() {
  isInputMode.value = true
  inviteCode.value = ''
  errorMessage.value = ''
  await nextTick()
  inviteInputRef.value?.focus()
}

function extractProjectId(response: AcceptInviteCodeResponse): ProjectId | null {
  return response.data?.projectId ?? null
}

async function confirmInviteCode() {
  const trimmedInviteCode = inviteCode.value.trim()

  errorMessage.value = ''

  if (!trimmedInviteCode) {
    errorMessage.value = '초대코드를 입력해주세요.'
    return
  }

  trackEvent('invite_code_submitted')

  isLoading.value = true

  try {
    const response = await acceptProjectInviteCode(trimmedInviteCode)
    const projectId = extractProjectId(response)

    if (!projectId) {
      throw new Error('참여할 프로젝트 정보를 찾을 수 없습니다.')
    }

    trackEvent('invite_code_joined', {
      project_id: projectId,
    })

    resetState()
    await router.push(`/project/${projectId}`)
  }
  catch (error) {

    trackEvent('invite_code_failed', {
      reason: 'invalid_or_expired',
    })
    errorMessage.value = error instanceof Error
      ? error.message
      : '초대코드 확인 중 오류가 발생했습니다.'
  }
  finally {
    isLoading.value = false
  }
}

function cancelInputMode() {
  resetState()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    void confirmInviteCode()
    return
  }

  if (event.key === 'Escape') {
    cancelInputMode()
  }
}
</script>

<template>
  <div class="relative flex flex-col items-end">
    <div
      class="flex items-center overflow-hidden rounded-full border transition-all duration-300 ease-out"
      :class="isInputMode
        ? [
          'h-10 w-[280px] px-4 md:w-[340px] bg-[#1c1b1b]',
          errorMessage
            ? 'border-red-400 animate-shake'
            : 'border-[#FF3DCB]/40',
        ]
        : 'w-auto bg-[#131313] border-white/10 hover:border-[#FF3DCB]/40 hover:bg-[#1c1b1b]'"
    >
      <button
        v-if="!isInputMode"
        type="button"
        class="inline-flex h-10 items-center gap-1.5 px-4 text-[10px] font-medium uppercase tracking-[0.2em] text-[#e5bcc5] hover:text-[#FF3DCB] transition-colors md:text-xs"
        @click="openInputMode"
      >
        <KeyRound class="h-3.5 w-3.5" />
        <span class="hidden sm:inline">초대코드 입력</span>
      </button>

      <div
        v-else
        class="flex w-full items-center gap-2 animate-fade-in"
      >
        <KeyRound
          class="h-3.5 w-3.5 shrink-0"
          :class="errorMessage ? 'text-red-400' : 'text-[#FF3DCB]'"
        />

        <input
          ref="inviteInputRef"
          v-model="inviteCode"
          type="text"
          placeholder="STU-XXXX"
          :disabled="isLoading"
          maxlength="20"
          spellcheck="false"
          class="w-full min-w-0 bg-transparent text-xs uppercase tracking-[0.2em] text-[#e5e2e1] placeholder:text-[#e5bcc5]/50 focus:outline-none disabled:opacity-50"
          @keydown="handleKeydown"
          @input="errorMessage = ''"
        >

        <Button
          type="button"
          :disabled="isLoading"
          class="rounded-full border border-white/20 bg-[#2a2a2a] px-2.5 py-0.5 text-[9px] uppercase tracking-[0.2em] text-[#e5bcc5] transition hover:border-[#FF3DCB]/60 hover:text-[#FF3DCB] disabled:opacity-40"
          @click="confirmInviteCode"
        >
          <template v-if="isLoading">
            ...
          </template>
          <template v-else>
            <Check class="h-3 w-3" />
          </template>
        </Button>

        <Button
          type="button"
          variant="ghost"
          :disabled="isLoading"
          class="grid h-5 w-5 place-items-center rounded-full p-0 text-[#e5bcc5] transition hover:text-[#FF3DCB]"
          @click="cancelInputMode"
        >
          <X class="h-3 w-3" />
        </Button>
      </div>
    </div>

    <p
      v-if="errorMessage"
      class="absolute -bottom-6 right-0 text-[11px] tracking-wide text-red-400 animate-fade-in"
    >
      {{ errorMessage }}
    </p>
  </div>
</template>