<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { exchangeLoginCode } from '@/pages/Onboarding/api/onboarding.api'
import { useAuthStore } from '@/pages/Onboarding/stores/auth.store'

const router = useRouter()
const authStore = useAuthStore()

const isLoading = ref(true)
const errorMessage = ref('')

onMounted(async () => {
  const loginCode = new URLSearchParams(window.location.search).get('code')
   
   // ★ 백엔드 요청 전에 무조건 예전 토큰 비우기 ★
  authStore.clearAccessToken() 
  
  if (!loginCode) {
    errorMessage.value = '로그인 코드가 없습니다.'
    isLoading.value = false
    return
  }

  try {
    const response = await exchangeLoginCode(loginCode)

    if (!response.isSuccess) {
      throw new Error(response.message)
    }

    authStore.setAccessToken(response.data.accessToken)

    router.replace('/dashboard')
  } catch (error) {
    //console.error(error)
    errorMessage.value = '로그인 처리 중 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-background text-foreground">
    <p v-if="isLoading">
      로그인 처리 중...
    </p>

    <div v-else class="text-center">
      <p>{{ errorMessage }}</p>
      <button
        type="button"
        class="mt-4 border px-4 py-2"
        @click="router.replace('/')"
      >
        로그인 페이지로 돌아가기
      </button>
    </div>
  </main>
</template>