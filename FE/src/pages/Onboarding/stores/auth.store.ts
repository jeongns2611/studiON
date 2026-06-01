import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { reissueAccessToken, requestLogout } from '../api/onboarding.api'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)

  const isLoggedIn = computed(() => accessToken.value !== null)

  function setAccessToken(token: string) {
    accessToken.value = token
  }

  function clearAccessToken() {
    accessToken.value = null
  }

  let silentRefreshPromise: Promise<boolean> | null = null

  async function silentRefresh() {
    if (silentRefreshPromise) {
      return silentRefreshPromise
    }

    silentRefreshPromise = (async () => {
      try {
        const response = await reissueAccessToken()
        if (response && response.data && response.data.accessToken) {
          setAccessToken(response.data.accessToken)
          return true
        }
        return false
      } catch (error) {
        clearAccessToken()
        return false
      } finally {
        silentRefreshPromise = null
      }
    })()

    return silentRefreshPromise
  }

  async function logout() {
    clearAccessToken()

    try {
      await requestLogout()
    } catch {
      // 서버 요청 실패와 무관하게 클라이언트는 로그아웃 상태를 유지한다.
    }
  }

  return {
    accessToken,
    isLoggedIn,
    setAccessToken,
    clearAccessToken,
    silentRefresh,
    logout,
  }
})
