import { axiosInstance } from '@/shared/api/axiosInstance'

export interface ApiResponse<T> {
  isSuccess: boolean
  code: string
  message: string
  data: T
}

export interface AiJobStartRequest {
  project_id: number
  issue_types: string[]
  validator_mode: string
  critic_mode: string
  project_snapshot: ProjectSnapshotRequest
}

export interface ProjectSnapshotRequest {
  duration_ms: number
  bpm: number
  numerator: number
  denominator: number
  tracks: ProjectTrackRequest[]
  clips: ProjectClipRequest[]

  // 나중에 AI가 현재 EQ/리미터 상태까지 참고하게 할 때 사용
  track_eqs?: ProjectTrackEqRequest[]
  master_limiter?: ProjectMasterLimiterRequest
}

export interface ProjectTrackRequest {
  track_id: number
  name: string
}

export interface ProjectClipRequest {
  clip_id: number
  track_id: number
  start_ms: number
  end_ms: number
  audio_metadata_id: number
  audio_start_ms: number
  audio_duration_ms: number

  // 문서상 optional. 현재는 백에서 audio_metadata_id로 URL을 찾는 구조면 없어도 됨
  audio_url?: string | null
}

export interface ProjectTrackEqRequest {
  track_id: number
  bands: ProjectTrackEqBandRequest[]
}

export interface ProjectTrackEqBandRequest {
  band_order: number
  eq_type: string
  frequency_hz: number
  q: number
  gain_delta_db: number
}

export interface ProjectMasterLimiterRequest {
  is_enabled: boolean
  threshold_db: number
  ceiling_dbfs: number
  attack_ms: number
  release_ms: number
  input_gain_db: number
  makeup_gain_db: number
}

export interface AiJobStartResponse {
  job: {
    job_id: number
    project_id: number
    dispatch_type: string
    status: string
    queue_name: string
  }
}

/**
 * 새 AI suggestion payload 계약
 */
export type AiIssueUiMode = 'eq_ai' | 'master_trim' | 'marker_only'

export type AiIssueType =
  | 'band_overlap'
  | 'track_clipping'
  | 'master_clipping'
  | 'sibilance'
  | 'high_band_harshness'

export interface AiSuggestionPayload {
  groupTitle: string
  groupSummary: string
  activeIssueId: string | null
  navigationOrder: string[]
  issues: AiSuggestionIssue[]
  suggestions: AiLegacySuggestion[]
}

export interface AiSuggestionIssue {
  issueId: string
  issueType: AiIssueType | string
  startMs: number
  endMs: number
  trackId: number | null
  bubbleTarget: 'track' | 'master'
  uiMode: AiIssueUiMode
  summary: string
  explanation: string | null
  previewBands: AiPreviewBand[]
  actions: AiSuggestionAction[]
  markers: AiIssueMarker[]
}

export interface AiSuggestionAction {
  type: string
  targetScope?: 'TRACK' | 'MASTER'
  targetTrackId?: number | null
  startMs?: number | null
  endMs?: number | null
  bandLowHz?: number | null
  bandHighHz?: number | null
  gainDeltaDb?: number | null
  recommendedReductionDb?: number | null
  currentTruePeakDbtp?: number | null
  targetCeilingDbtp?: number | null
  params?: Record<string, unknown>

  // 백엔드가 action id를 내려줄 가능성 대비
  id?: string | number | null
  suggestionActionId?: string | number | null

  [key: string]: unknown
}

export interface AiIssueMarker {
  trackId: number | null
  centerHz?: number | null
  bandLowHz?: number | null
  bandHighHz?: number | null
}

export interface AiPreviewBand {
  jobId?: number | null
  targetTrackId: number
  bandOrder: number
  eqTypeCode: number
  frequencyHz: number
  q: number
  gainDeltaDb: number
  statusCode?: string | number | null
  previewExpiresAt?: string | null
}

export interface AiLegacySuggestion {
  rank?: number
  summary?: string
  explanation?: string | null
  previewBands?: AiPreviewBand[]
}

export interface AiWorkflowStatusResponse {
  job: {
    id: number
    project_id: number
    status: string
    phase: string
    current_node: string | null
    progress: number
    timeline_snapshot_id: string | null
    requested_by: number | null
    started_at: string | null
    completed_at: string | null
    error_code: string | null
    error_message: string | null
  }
  projections: {
    analysis_regions?: AiAnalysisRegion[]

    // 새 UI 계약
    suggestion_payload?: AiSuggestionPayload

    // 혹시 camelCase로 내려올 경우 대비
    suggestionPayload?: AiSuggestionPayload

    [key: string]: unknown
  }
}

/**
 * 기존 analysis_regions fallback 타입
 */
export interface AiAnalysisRegion {
  id: string
  job_id: number
  issue_type: string | null
  start_ms: number | null
  end_ms: number | null
  measure_start: number | null
  measure_end: number | null
  severity: string
  analysis_summary: string | null
  track_id: number | null
  secondary_track_id: number | null
  band_low_hz: number | null
  band_high_hz: number | null

  center_hz?: number | null
  band_confidence?: number | null
  estimated_gain_reduction_db?: number | null
  current_true_peak_dbtp?: number | null
  target_ceiling_dbtp?: number | null

  involved_track_ids: number[]
  affected_clip_ids: number[]
  contributing_track_ids?: number[]
  track_contribution_scores?: Record<string, number>
  contributor_band_hints?: Record<string, string[]>
}

export async function startAiWorkflow(payload: AiJobStartRequest) {
  const response = await axiosInstance.post<ApiResponse<AiJobStartResponse>>(
    '/api/v1/ai/workflow/jobs/start',
    payload,
    {
      timeout: 30000,
    },
  )

  return response.data.data
}

export async function getAiWorkflowStatus(jobId: number) {
  const response = await axiosInstance.get<ApiResponse<AiWorkflowStatusResponse>>(
    `/api/v1/ai/workflow/jobs/${jobId}`,
    {
      timeout: 30000,
    },
  )

  return response.data.data
}

export interface AiWorkflowJobResponse {
  job_id: number
  project_id: number
  dispatch_type: string
  status: string
  queue_name: string
}

export interface AiUserFeedbackRequest {
  project_id?: number

  // 신규 feedback 필드
  issue_id?: string | null
  action_type?: string | null
  action_payload?: Record<string, unknown> | null

  // 기존 resume 흐름 호환
  selected_region_id?: number | null
  preserve_clip_id?: number | null
  user_feedback_message?: string | null
  user_decision?: 'CONFIRM' | 'CANCEL' | 'RESUME'
}

export async function sendAiWorkflowFeedback(
  jobId: number,
  request: AiUserFeedbackRequest,
): Promise<AiWorkflowJobResponse> {
  const response = await axiosInstance.post<ApiResponse<AiWorkflowJobResponse>>(
    `/api/v1/ai/workflow/jobs/${jobId}/feedback`,
    request,
    {
      timeout: 30000,
    },
  )

  return response.data.data
}