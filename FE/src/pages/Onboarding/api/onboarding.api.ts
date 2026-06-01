import { axiosInstance } from '@/shared/api/axiosInstance'
import type {
  ApiResponse,
  FetchPositionsResponse,
  OnboardingRequest,
  OnboardingResponse,
  TokenExchangeResponse,
} from '../types/onboarding.types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'

export function redirectToGoogleLogin() {
  window.location.href = `${API_BASE_URL}/oauth2/authorization/google`
}

export async function exchangeLoginCode(code: string): Promise<TokenExchangeResponse> {
  const { data } = await axiosInstance.post<TokenExchangeResponse>(
    `/api/v1/auth/exchange?code=${code}`,
  )

  return data
}

export async function fetchPositions(): Promise<FetchPositionsResponse> {
  const { data } = await axiosInstance.get<FetchPositionsResponse>(
    '/api/v1/auth/positions',
  )

  return data
}

export async function completeOnboarding(
  payload: OnboardingRequest,
): Promise<OnboardingResponse> {
  const { data } = await axiosInstance.post<OnboardingResponse>(
    '/api/v1/auth/onboarding',
    payload,
    {
      withCredentials: true,
    },
  )

  return data
}

export async function reissueAccessToken(): Promise<TokenExchangeResponse> {
  const { data } = await axiosInstance.post<TokenExchangeResponse>(
    '/api/v1/auth/reissue',
    undefined,
    {
      withCredentials: true,
    },
  )

  return data
}

export async function requestLogout(): Promise<ApiResponse<null>> {
  const { data } = await axiosInstance.post<ApiResponse<null>>(
    '/api/v1/auth/logout',
    undefined,
    {
      withCredentials: true,
    },
  )

  return data
}
