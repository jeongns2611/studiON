<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Check, X } from 'lucide-vue-next'
import { completeOnboarding, fetchPositions } from '../api/onboarding.api'
import { useAuthStore } from '../stores/auth.store'
import type { Position } from '../types/onboarding.types'

const MAX_SELECTIONS = 3

const router = useRouter()
const authStore = useAuthStore()

const positions = ref<Position[]>([])
const selectedPositionCodes = ref<number[]>([])

const activeGroupCode = ref<number | null>(null)
const activePositionCode = ref<number | null>(null)

const done = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')

const canSubmit = computed(() => {
  return selectedPositionCodes.value.length > 0 && !isLoading.value
})

const groupedPositions = computed(() => {
  const groupMap = new Map<number, {
    code: number
    name: string
    order: number
    positions: Position[]
  }>()

  positions.value.forEach((position) => {
    if (!groupMap.has(position.groupCode)) {
      groupMap.set(position.groupCode, {
        code: position.groupCode,
        name: position.groupName,
        order: position.groupOrder,
        positions: [],
      })
    }

    groupMap.get(position.groupCode)?.positions.push(position)
  })

  return Array.from(groupMap.values())
    .map(group => ({
      ...group,
      positions: group.positions.sort((a, b) => a.order - b.order),
    }))
    .sort((a, b) => a.order - b.order)
})

const activeGroup = computed(() => {
  if (activeGroupCode.value === null)
    return null

  return groupedPositions.value.find(group => group.code === activeGroupCode.value) ?? null
})

const activeGroupPositions = computed(() => {
  return activeGroup.value?.positions ?? []
})

const selectedPositions = computed(() => {
  return selectedPositionCodes.value
    .map(code => positions.value.find(position => position.code === code))
    .filter((position): position is Position => Boolean(position))
})

onMounted(async () => {
  try {
    const response = await fetchPositions()

    if (!response.isSuccess) {
      throw new Error(response.message)
    }

    positions.value = response.data

    // 초기 진입 시 기본으로 첫 번째 그룹을 활성화하지 않음
    // const firstGroup = groupedPositions.value[0]
    // if (firstGroup) {
    //   activeGroupCode.value = firstGroup.code
    // }
  } catch (error) {
   // console.error(error)
    errorMessage.value = '포지션 목록을 불러오지 못했습니다.'
  }
})

function addSelection(positionCode: number) {
  if (selectedPositionCodes.value.includes(positionCode))
    return

  if (selectedPositionCodes.value.length >= MAX_SELECTIONS) {
    errorMessage.value = `포지션은 최대 ${MAX_SELECTIONS}개까지 선택할 수 있습니다.`
    return
  }

  errorMessage.value = ''
  selectedPositionCodes.value.push(positionCode)
}

function handleGroupClick(group: {
  code: number
  name: string
  order: number
  positions: Position[]
}) {
  activeGroupCode.value = group.code
  activePositionCode.value = null

  const hasSubOptions = group.positions.length > 1

  if (!hasSubOptions) {
    const onlyPosition = group.positions[0]
    if (onlyPosition) {
      activePositionCode.value = onlyPosition.code
      addSelection(onlyPosition.code)
    }
  }
}

function handlePositionClick(position: Position) {
  activePositionCode.value = position.code
  addSelection(position.code)
}

function removeSelection(positionCode: number) {
  selectedPositionCodes.value = selectedPositionCodes.value.filter(code => code !== positionCode)
  activeGroupCode.value = null
  activePositionCode.value = null
}

function isGroupPicked(group: {
  positions: Position[]
}) {
  return group.positions.some(position => selectedPositionCodes.value.includes(position.code))
}

async function handleSubmit() {
  if (!canSubmit.value)
    return

  try {
    isLoading.value = true
    errorMessage.value = ''

    const response = await completeOnboarding({
      positionCodes: selectedPositionCodes.value,
    })

    if (!response.isSuccess) {
      throw new Error(response.message)
    }

    authStore.setAccessToken(response.data.accessToken)

    done.value = true
  } catch (error) {
   // console.error(error)
    errorMessage.value = '온보딩 처리 중 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
}

function handleEnterDashboard() {
  router.push('/dashboard')
}

</script>

<template>
  <div class="animate-fade-in">
    <div
      v-if="!done"
      class="rounded-3xl border border-white/5 bg-[#1c1b1b]/60 p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl md:p-12"
    >
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-[11px] font-semibold uppercase tracking-[0.35em] text-[#FF3DCB]">
            환영합니다!
          </p>

          <h1 class="mt-4 font-display text-4xl font-bold leading-[1.05] tracking-tight text-white md:text-5xl">
            스튜디온에<br>
            초대합니다.
          </h1>

          <p class="mt-5 text-sm leading-relaxed text-muted-foreground">
            선호 포지션을 입력해주세요.<br>
            협업 매칭에 사용됩니다.
          </p>
        </div>
      </div>

      <div class="mt-10">
  <span class="text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
    포지션
  </span>

  <p
    v-if="positions.length === 0 && !errorMessage"
    class="mt-4 text-sm text-muted-foreground"
  >
    포지션 목록을 불러오는 중입니다.
  </p>

  <div class="mt-4 flex flex-wrap gap-2.5">
    <button
      v-for="group in groupedPositions"
      :key="group.code"
      type="button"
      :disabled="selectedPositionCodes.length >= MAX_SELECTIONS && !isGroupPicked(group)"
      class="rounded-full px-5 py-2 text-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
      :class="activeGroupCode === group.code || isGroupPicked(group)
        ? 'bg-[#FF3DCB] text-[#65002e] font-bold shadow-[0_0_15px_rgba(255,61,203,0.4)]'
        : 'bg-[#2a2a2a] text-[#e5bcc5] border border-transparent hover:bg-[#333] hover:border-[#FF3DCB]/50 disabled:hover:bg-[#2a2a2a] disabled:hover:border-transparent'"
      @click="handleGroupClick(group)"
    >
      {{ group.name }}
    </button>
  </div>
</div>

<div
  v-if="activeGroup && activeGroupPositions.length > 1"
  class="mt-10 animate-fade-in"
>
  <span class="text-[11px] uppercase tracking-[0.35em] text-muted-foreground/80">
    {{ activeGroup.name }}
  </span>

  <div class="mt-4 space-y-2.5">
    <button
      v-for="position in activeGroupPositions"
      :key="position.code"
      type="button"
      :disabled="selectedPositionCodes.length >= MAX_SELECTIONS && !selectedPositionCodes.includes(position.code)"
      class="block w-full rounded-full px-6 py-3 text-left text-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
      :class="activePositionCode === position.code || selectedPositionCodes.includes(position.code)
        ? 'bg-[#FF3DCB] text-[#65002e] font-bold shadow-[0_0_15px_rgba(255,61,203,0.4)]'
        : 'bg-[#2a2a2a] text-[#e5bcc5] border border-transparent hover:bg-[#333] hover:border-[#FF3DCB]/50 disabled:hover:bg-[#2a2a2a] disabled:hover:border-transparent'"
      @click="handlePositionClick(position)"
    >
      {{ position.name }}
    </button>
  </div>
</div>

      <p
        v-if="errorMessage"
        class="mt-6 text-sm text-red-500"
      >
        {{ errorMessage }}
      </p>

      <div class="mt-12 border-t border-white/10 pt-6">
        <div class="flex flex-wrap gap-2.5">
          <span
            v-if="selectedPositions.length === 0"
            class="text-xs text-muted-foreground/60"
          >
            포지션을 선택해주세요
          </span>

          <span
            v-for="selection in selectedPositions"
            v-else
            :key="selection.code"
            class="inline-flex items-center gap-2 rounded-full border border-white/10 bg-[#2a2a2a] px-4 py-1.5 text-sm text-[#e5bcc5]"
          >
            {{ selection.name }}

            <button
              type="button"
              class="text-zinc-400 transition hover:text-[#FF3DCB]"
              :aria-label="`${selection.name} 제거`"
              @click="removeSelection(selection.code)"
            >
              <X class="h-3.5 w-3.5" />
            </button>
          </span>
        </div>

        <div class="mt-5 flex items-end justify-between gap-4">
          <p class="text-xs tracking-wide text-zinc-400">
            포지션은 <span class="text-white">{{ MAX_SELECTIONS }}개</span>까지 입력 가능합니다.
          </p>

          <button
            type="button"
            :disabled="!canSubmit"
            class="rounded-full bg-[#FF3DCB] px-7 py-2.5 text-[15px] font-bold text-[#65002e] shadow-[0_0_20px_rgba(255,61,203,0.4)] transition hover:bg-[#ff4a8d] hover:shadow-[0_0_25px_rgba(255,61,203,0.6)] disabled:cursor-not-allowed disabled:bg-[#2a2a2a] disabled:text-zinc-500 disabled:shadow-none"
            @click="handleSubmit"
          >
            {{ isLoading ? '처리 중...' : '완료하기' }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-else
      class="rounded-3xl border border-white/5 bg-[#1c1b1b]/60 p-10 text-center shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl animate-fade-in"
    >
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#FF3DCB]/15 text-[#FF3DCB]">
        <Check class="h-6 w-6" />
      </div>

      <h2 class="mt-6 font-display text-3xl leading-tight text-white">
        환영합니다!
      </h2>

      <p class="mt-3 text-sm text-zinc-400">
        프로필이 준비됐어요. 첫 세션을 시작해보세요.
      </p>

      <div class="mt-8 flex justify-center gap-3">
        <button
          type="button"
          class="rounded-full bg-[#FF3DCB] px-6 py-2.5 text-xs font-bold uppercase tracking-[0.3em] text-[#65002e] shadow-[0_0_20px_rgba(255,61,203,0.4)] transition hover:bg-[#ff4a8d]"
          @click="handleEnterDashboard"
        >
          Enter Dashboard
        </button>

      </div>
    </div>
  </div>
</template>
