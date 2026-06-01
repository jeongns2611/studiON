// 프론트의 모든 api 요청을 배달.
import axios from 'axios'
import { useAuthStore } from '@/pages/Onboarding/stores/auth.store'

const PUBLIC_AUTH_PATHS = [
  '/api/v1/auth/positions',
  '/api/v1/auth/onboarding',
  '/api/v1/auth/exchange',
  '/api/v1/auth/reissue',
  '/api/v1/auth/logout',
]

function isPublicAuthRequest(url?: string) {
  if (!url) {
    return false
  }

  return PUBLIC_AUTH_PATHS.some((path) => url.includes(path))
}

// 1. 기본 설정이 적용된 axios instance 생성
export const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  timeout: 10000,
  withCredentials: true,
})

// 2. 요청 가로채기(Request Interceptor)
// 모든 요청이 나가기 전에 메모리에 저장된 accessToken을 Authorization 헤더에 추가
axiosInstance.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    const token = authStore.accessToken

    if (token && !isPublicAuthRequest(config.url)) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// 3. 응답 가로채기(Response Interceptor)
// 백엔드 공통 응답에서 isSuccess가 false면 에러로 처리
axiosInstance.interceptors.response.use(
  (response) => {
    if (response.data && response.data.isSuccess === false) {
      const error = new Error(
        response.data.errorMessage ||
        response.data.message ||
        '요청에 실패했습니다.',
      )

      ;(error as any).code = response.data.errorCode || response.data.code

      throw error
    }

    return response
  },
  async (error) => {
    const originalRequest = error.config

    if (
      error.response?.status === 401 &&
      !originalRequest._isRetry &&
      !isPublicAuthRequest(originalRequest.url)
    ) {
      originalRequest._isRetry = true
      
      const authStore = useAuthStore()
      const success = await authStore.silentRefresh()
      
      if (success && authStore.accessToken) {
        originalRequest.headers = originalRequest.headers ?? {}
        originalRequest.headers.Authorization = `Bearer ${authStore.accessToken}`
        return axiosInstance(originalRequest)
      } else {
        // Refresh failed, clear token
        authStore.clearAccessToken()
      }
    }

    if (error.response) {
      error.message =
        error.response.data?.errorMessage ||
        error.response.data?.message ||
        error.message
    }

    return Promise.reject(error)
  },
)
