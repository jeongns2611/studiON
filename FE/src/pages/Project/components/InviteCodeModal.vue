<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Copy, KeyRound, RefreshCw, X } from 'lucide-vue-next'
import { createProjectInviteCode } from '@/pages/Project/api/project.api'
import { trackEvent } from '@/shared/utils/analytics'

interface Props {
  open: boolean
  projectId: string | number
  projectName?: string
}

interface InviteResponse {
  data?: {
    inviteCode?: string | null
  } | null
  inviteCode?: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const inviteCode = ref('')
const isLoading = ref(false)
const isCopied = ref(false)
const errorMessage = ref('')

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) {
      resetState()
      return
    }

    await generateInviteCode()
  },
  { immediate: true },
)

function resetState() {
  inviteCode.value = ''
  isLoading.value = false
  isCopied.value = false
  errorMessage.value = ''
}

function extractInviteCode(response: InviteResponse): string {
  return response?.data?.inviteCode ?? response?.inviteCode ?? ''
}

async function generateInviteCode() {
  isLoading.value = true
  errorMessage.value = ''
  isCopied.value = false

  try {
    const projectId = Number(props.projectId)

    if (Number.isNaN(projectId)) {
      throw new Error('프로젝트 정보를 확인할 수 없습니다.')
    }

    const response = await createProjectInviteCode(projectId)
    const nextInviteCode = extractInviteCode(response)

    if (!nextInviteCode) {
      throw new Error('초대코드를 생성할 수 없습니다.')
    }

    inviteCode.value = nextInviteCode

    trackEvent('invite_code_created', {
      project_id: projectId,
    })
  }
  catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : '초대코드 생성에 실패했습니다.'
  }
  finally {
    isLoading.value = false
  }
}

async function handleCopy() {
  if (!inviteCode.value || isLoading.value)
    return

  try {
    await navigator.clipboard.writeText(inviteCode.value)
    isCopied.value = true

    window.setTimeout(() => {
      isCopied.value = false
    }, 1500)
  }
  catch {
    errorMessage.value = '초대코드 복사에 실패했습니다.'
  }
}

function handleClose() {
  emit('close')
}

function handleComplete() {
  emit('close')
}

const displayedCode = computed(() => {
  if (isLoading.value)
    return '생성 중...'

  if (errorMessage.value)
    return 'ERROR'

  return inviteCode.value || '------'
})
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-[9999] grid place-items-center bg-black/40 px-4 backdrop-blur-md animate-fade-in"
    @click.self="handleClose"
  >
    <div
      class="relative w-full max-w-md rounded-2xl border border-white/10 bg-card p-7 shadow-2xl transition-all"
    >
      <button
        type="button"
        aria-label="닫기"
        class="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full border border-border text-muted-foreground transition hover:border-primary hover:text-primary"
        @click="handleClose"
      >
        <X class="h-3.5 w-3.5" />
      </button>

      <div class="mb-6 flex items-center gap-3">
        <div class="grid h-10 w-10 place-items-center rounded-lg bg-secondary text-primary shadow-neon-sm">
          <KeyRound class="h-4 w-4" />
        </div>

        <div>
          <h2 class="font-display text-2xl font-extrabold tracking-tight text-foreground">
            코드생성
          </h2>
        </div>
      </div>

      <div class="mb-5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span class="text-base font-medium text-muted-foreground">
          초대코드
        </span>

        <span class="text-2xl font-extrabold text-foreground">
          초대 코드는 5분 동안 유효합니다.
        </span>
      </div>

      <div class="mb-6 rounded-xl border border-primary/40 bg-secondary/40 p-2">
        <div class="flex items-center gap-2">
          <div class="min-w-0 flex-1 px-4 py-3">
            <div
              class="truncate font-mono text-xl font-extrabold tracking-[0.3em]"
              :class="errorMessage ? 'text-destructive' : 'text-primary text-neon'"
            >
              {{ displayedCode }}
            </div>

            <p
              v-if="errorMessage"
              class="mt-2 text-sm text-destructive"
            >
              {{ errorMessage }}
            </p>
          </div>

          <button
            type="button"
            aria-label="재생성"
            class="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-border text-muted-foreground transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="isLoading"
            @click="generateInviteCode"
          >
            <RefreshCw
              class="h-4 w-4"
              :class="isLoading ? 'animate-spin' : ''"
            />
          </button>

          <button
            type="button"
            aria-label="복사"
            class="grid h-10 w-10 shrink-0 place-items-center rounded-lg border transition disabled:cursor-not-allowed disabled:opacity-40"
            :class="isCopied
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border text-muted-foreground hover:border-primary hover:text-primary'"
            :disabled="isLoading || !inviteCode"
            @click="handleCopy"
          >
            <Check
              v-if="isCopied"
              class="h-4 w-4"
            />
            <Copy
              v-else
              class="h-4 w-4"
            />
          </button>
        </div>
      </div>

      <div class="flex justify-center">
        <button
          type="button"
          class="inline-flex min-w-[152px] items-center justify-center rounded-full bg-primary px-8 py-3 text-lg font-extrabold text-primary-foreground transition hover:shadow-neon disabled:cursor-not-allowed disabled:opacity-40"
          @click="handleComplete"
        >
          완료
        </button>
      </div>
    </div>
  </div>
</template>