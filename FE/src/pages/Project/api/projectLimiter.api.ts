import { axiosInstance } from '@/shared/api/axiosInstance'

export interface ApiResponse<T> {
  isSuccess: boolean
  code: string
  message: string
  data: T
}

export type LimiterSourceType = 'MANUAL' | 'AI_SUGGESTION' | 'AI_APPLIED'

export interface MasterLimiterState {
  projectId: number
  masterLimiterId: number
  updatedAt: string
  source?: 'COMMITTED' | 'DRAFT'

  isEnabled: boolean
  thresholdDb: number
  ceilingDbfs: number
  attackMs: number
  releaseMs: number
  inputGainDb: number
  makeupGainDb: number

  jobId: number | null
  suggestionActionId: number | null
  appliedSuggestionId: number | null
  sourceType: LimiterSourceType | null
}

export interface SaveMasterLimiterDraftRequest {
  isEnabled: boolean
  thresholdDb: number
  ceilingDbfs: number
  attackMs: number
  releaseMs: number
  inputGainDb: number
  makeupGainDb: number

  jobId?: number | null
  suggestionActionId?: number | null
  appliedSuggestionId?: number | null
  sourceType: LimiterSourceType
}

export async function getMasterLimiter(projectId: number) {
  const response = await axiosInstance.get<ApiResponse<MasterLimiterState>>(
    `/api/v1/limiter/projects/${projectId}`,
    {
      timeout: 30000,
    },
  )

  return response.data.data
}

export async function saveMasterLimiterDraft(
  projectId: number,
  payload: SaveMasterLimiterDraftRequest,
) {
  const response = await axiosInstance.post<ApiResponse<MasterLimiterState>>(
    `/api/v1/limiter/projects/${projectId}/draft`,
    payload,
    {
      timeout: 30000,
    },
  )

  return response.data.data
}

export interface LockMasterLimiterResponse {
  masterLimiterId: number
  isLocked: boolean
  userId: number
}

export async function lockMasterLimiter(
  projectId: number,
  isLocked: boolean,
) {
  const response = await axiosInstance.post<ApiResponse<LockMasterLimiterResponse>>(
    `/api/v1/limiter/projects/${projectId}/lock`,
    { isLocked },
    {
      timeout: 30000,
    },
  )

  return response.data.data
}