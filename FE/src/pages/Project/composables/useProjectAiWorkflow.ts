import { computed, ref } from 'vue'
import { useAlertStore } from '@/shared/stores/useAlertStore'
import { useTrackStore } from '../store/useTrackStore'
import type { EqTypeCode, TrackEqBandState } from '../types'
import {
  startAiWorkflow,
  getAiWorkflowStatus,
  sendAiWorkflowFeedback,
  type AiAnalysisRegion,
  type AiIssueMarker,
  type AiIssueUiMode,
  type AiSuggestionAction,
  type AiSuggestionIssue,
  type AiSuggestionPayload,
  type ProjectSnapshotRequest,
} from '../api/projectAi.api'
import {
  getMasterLimiter,
  saveMasterLimiterDraft,
  lockMasterLimiter,
} from '../api/projectLimiter.api'
import { trackEvent } from '@/shared/utils/analytics'

const TIMELINE_TRACK_HEADER_WIDTH = 266

type AiIssueKind = 'BAND_OVERLAP' | 'CLIPPING' | 'HARSHNESS'
type AiIssueTargetType = 'TIMELINE' | 'MASTER_TRACK' | 'TRACK'

export type AiAnalysisItem = {
  id: string | number
  issueType: string
  kind: AiIssueKind
  uiMode: AiIssueUiMode

  jobId: number | null
  regionId: number | null
  startMs: number
  endMs: number

  targetType: AiIssueTargetType
  targetTrackId: number | null
  involvedTrackIds: number[]
  affectedClipIds: number[]

  startPercent: number
  endPercent: number
  startPx: number
  endPx: number

  barStart: number
  barEnd: number

  title: string
  summary: string
  explanation: string | null
  bullets: string[]

  bandLowHz: number | null
  bandHighHz: number | null

  recommendedGainReductionDb: number | null

  previewBands: TrackEqBandState[]
  actions: AiSuggestionAction[]
  markers: AiIssueMarker[]
}

export function useProjectAiWorkflow(projectId: number) {
const trackStore = useTrackStore()

  const aiAnalyzing = ref(false)

  const aiAnalysisItems = ref<AiAnalysisItem[]>([])
  const activeAiAnalysisId = ref<string | number | null>(null)
  const aiSuccessMessage = ref<string | null>(null)



  const activeAiAnalysis = computed(() => {
    return aiAnalysisItems.value.find(item => item.id === activeAiAnalysisId.value) ?? null
  })

  // 기존 ProjectPage / Overlay 호환용
  const aiConflict = computed(() => activeAiAnalysis.value)

  const aiBeforeBands = ref<TrackEqBandState[]>([])
  const aiAfterBands = ref<TrackEqBandState[]>([])
  const currentAiJobId = ref<number | null>(null)
  const selectedAiRegionId = ref<number | null>(null)

  const appliedClippingIssueIds = ref<Set<string | number>>(new Set())
  const appliedClippingInfoMap = ref<
  Map<string | number, {
    reductionDb: number
    inputGainDb: number
    ceilingDbfs: number
  }>
>(new Map())

const appliedAiEqIssueIds = ref<Set<string | number>>(new Set())

const selectedEqTrack = computed(() => {
  if (trackStore.selectedTarget?.type === 'MASTER') {
    return trackStore.masterTrack
  }

  const selectedTrackId = trackStore.selectedTrackId

  if (!selectedTrackId) return null

  return trackStore.trackList.find(track =>
    track.trackId === selectedTrackId
  ) ?? null
})



  function sleep(ms: number) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

const AI_WORKFLOW_POLL_INTERVAL_MS = 2000
const AI_WORKFLOW_POLL_TIMEOUT_MS = 10 * 60 * 1000
const AI_WORKFLOW_POLL_MAX_TRY = Math.ceil(
  AI_WORKFLOW_POLL_TIMEOUT_MS / AI_WORKFLOW_POLL_INTERVAL_MS,
)

  async function pollAiWorkflow(jobId: number) {
  const maxTry = AI_WORKFLOW_POLL_MAX_TRY

  for (let i = 0; i < maxTry; i += 1) {
    const result = await getAiWorkflowStatus(jobId)
    const regions = result.projections.analysis_regions ?? []
    const suggestionPayload = getSuggestionPayload(result.projections)

    const status = result.job.status?.toLowerCase()
    const phase = result.job.phase?.toLowerCase()
    const hasSuggestionIssues = Boolean(suggestionPayload?.issues?.length)

    if (status === 'failed') {
      throw new Error(result.job.error_message ?? 'AI 분석에 실패했습니다.')
    }

    if (
      status === 'completed' ||
      status === 'waiting_user' ||
      status === 'waiting_user_plan_input' ||
      phase === 'completed' ||
      phase === 'waiting_user' ||
      phase === 'waiting_for_user_plan_input' ||
      result.job.progress >= 100 ||
      regions.length > 0 ||
      hasSuggestionIssues
    ) {
      return result
    }

    await sleep(AI_WORKFLOW_POLL_INTERVAL_MS)
  }

  throw new Error('AI 분석 결과를 가져오지 못했습니다. (timeout: 응답 대기 시간 초과)')
}

async function pollAiFeedbackResult(jobId: number) {
  const maxTry = AI_WORKFLOW_POLL_MAX_TRY

  for (let i = 0; i < maxTry; i += 1) {
    const result = await getAiWorkflowStatus(jobId)

    const status = result.job.status?.toLowerCase()
    const phase = result.job.phase?.toLowerCase()
    const hasSuggestion = hasAiEqSuggestion(result)

    if (status === 'failed') {
      throw new Error('AI 수정안 생성에 실패했습니다.')
    }

    if (hasSuggestion) {
      return result
    }

    // 수정안 없이 completed면 더 기다려도 의미 없을 가능성이 높음
    if (
      status === 'completed' ||
      phase === 'completed' ||
      result.job.progress >= 100
    ) {
      return result
    }

    await sleep(AI_WORKFLOW_POLL_INTERVAL_MS)
  }

  throw new Error('AI 수정안을 가져오지 못했습니다. 잠시 후 다시 시도해주세요.')
}

  function getAudioMetadataId(clip: any): number | null {
    return (
      clip.audioMetadataId ??
      clip.audio_metadata_id ??
      clip.audio?.audioMetadataId ??
      clip.audio?.audio_metadata_id ??
      null
    )
  }

function getAudioDurationMs(clip: any, fallbackDurationMs: number): number {
  return (
    clip.audioDurationMs ??
      clip.audio_duration_ms ??
      clip.audio?.durationMs ??
      clip.audio?.duration_ms ??
      clip.audio?.audioDurationMs ??
    fallbackDurationMs
  )
}

function toNumericId(value: unknown): number | null {
  const numericValue = Number(value)

  return Number.isNaN(numericValue) ? null : numericValue
}

function normalizeTrackIds(trackIds: number[] | null | undefined): number[] {
  return (trackIds ?? [])
    .map(trackId => Number(trackId))
    .filter(trackId => !Number.isNaN(trackId))
}

function normalizeClipIds(clipIds: number[] | null | undefined): number[] {
  return (clipIds ?? [])
    .map(clipId => Number(clipId))
    .filter(clipId => !Number.isNaN(clipId))
}

  function getMsPerBar() {
    const info = trackStore.projectInfo

    const bpm = info.tempo || 120
    const numerator = info.timeSigNumerator || 4
    const denominator = info.timeSigDenominator || 4

    return (60000 / bpm) * numerator * (4 / denominator)
  }

  function buildProjectSnapshotFromStore(): ProjectSnapshotRequest {
    const info = trackStore.projectInfo

    const bpm = info.tempo || 120
    const numerator = info.timeSigNumerator || 4
    const denominator = info.timeSigDenominator || 4

    const msPerBar = (60000 / bpm) * numerator * (4 / denominator)

    const tracks = trackStore.trackList.map(track => ({
      track_id: Number(track.trackId),
      name: track.name ?? '',
    }))

    const clips = trackStore.trackList.flatMap(track =>
      track.clips
        .map(clip => {
          const anyClip = clip as any
          const audioMetadataId = getAudioMetadataId(anyClip)

          if (!audioMetadataId) {
            return null
          }

          const startMs = Math.round(clip.start * msPerBar)
          const endMs = Math.round((clip.start + clip.duration) * msPerBar)
          const clipDurationMs = Math.max(endMs - startMs, 1)

          return {
            clip_id: Number(clip.clipId),
            track_id: Number(track.trackId),
            start_ms: startMs,
            end_ms: Math.max(endMs, startMs + 1),
            audio_metadata_id: Number(audioMetadataId),
            audio_start_ms: Math.round(anyClip.audioStartMs ?? anyClip.audio_start_ms ?? 0),
            audio_duration_ms: Math.round(getAudioDurationMs(anyClip, clipDurationMs)),
          }
        })
        .filter((clip): clip is ProjectSnapshotRequest['clips'][number] => clip !== null),
    )

    const baseDurationMs = Math.round(info.totalBarCount * msPerBar)
    const durationMs = Math.max(
      baseDurationMs,
      ...clips.map(clip => clip.end_ms),
    )

    return {
      duration_ms: durationMs,
      bpm,
      numerator,
      denominator,
      tracks,
      clips,
    }
  }

  function getClippingTrimValues(source: any) {
  const recommendedReductionDb =
    source.estimated_gain_reduction_db ??
    source.estimatedGainReductionDb ??
    source.recommended_reduction_db ??
    source.recommendedReductionDb ??
    null

  const currentTruePeakDbtp =
    source.current_true_peak_dbtp ??
    source.currentTruePeakDbtp ??
    null

  const targetCeilingDbtp =
    source.target_ceiling_dbtp ??
    source.targetCeilingDbtp ??
    null

  return {
    recommendedReductionDb:
      recommendedReductionDb == null ? null : Number(recommendedReductionDb),
    currentTruePeakDbtp:
      currentTruePeakDbtp == null ? null : Number(currentTruePeakDbtp),
    targetCeilingDbtp:
      targetCeilingDbtp == null ? null : Number(targetCeilingDbtp),
  }
}

function mapRegionToAnalysisItem(
  region: AiAnalysisRegion,
  durationMs: number,
): AiAnalysisItem {
  const startMs = region.start_ms ?? 0
  const endMs = region.end_ms ?? startMs + 1

  const msPerBar = getMsPerBar()

  const barStart =
    region.measure_start ??
    Math.floor(startMs / msPerBar) + 1

  const barEnd =
    region.measure_end ??
    Math.ceil(endMs / msPerBar)

  const startBarFloat = startMs / msPerBar
  const endBarFloat = Math.max(endMs / msPerBar, startBarFloat + 0.25)

  const startPx = TIMELINE_TRACK_HEADER_WIDTH + startBarFloat * trackStore.pixelPerBar
  const endPx = TIMELINE_TRACK_HEADER_WIDTH + endBarFloat * trackStore.pixelPerBar

  const startPercent = Math.max(0, Math.min(100, (startMs / durationMs) * 100))
  const endPercent = Math.max(
    startPercent + 0.5,
    Math.min(100, (endMs / durationMs) * 100),
  )

  const kind = mapIssueTypeToKind(region.issue_type)
  const involvedTrackIds = normalizeTrackIds(region.involved_track_ids)
  const affectedClipIds = normalizeClipIds(region.affected_clip_ids)
  const involvedTrackNamesText = formatTrackNames(involvedTrackIds)
  const clippingTrackName = getTrackDisplayName(region.track_id)

  let targetType: AiIssueTargetType = 'TIMELINE'
  let targetTrackId: number | null = null

  if (kind === 'BAND_OVERLAP') {
    targetType = 'TIMELINE'
    targetTrackId =
      involvedTrackIds[0] ??
      region.track_id ??
      region.secondary_track_id ??
      null
  }

  if (kind === 'CLIPPING') {
    targetType = 'MASTER_TRACK'
    targetTrackId = null
  }

  if (kind === 'HARSHNESS') {
    targetType = 'TRACK'
    targetTrackId =
      region.track_id ??
      involvedTrackIds[0] ??
      null
  }

  const titlePrefix =
    kind === 'BAND_OVERLAP'
      ? '대역 중복'
      : kind === 'CLIPPING'
        ? '클리핑'
        : '하쉬니스'

  const regionId =
    region.id ??
    (region as any).region_id ??
    `${kind}-${startMs}-${endMs}`
  const numericRegionId = toNumericId(regionId)

  const uiMode: AiIssueUiMode =
    kind === 'CLIPPING'
      ? 'master_trim'
      : kind === 'HARSHNESS'
        ? 'marker_only'
        : 'eq_ai'

  const bullets =
    kind === 'CLIPPING'
      ? [
          clippingTrackName
            ? `클리핑 감지 트랙: ${clippingTrackName}`
            : '클리핑 감지 트랙 정보를 확인 중입니다.',
          region.estimated_gain_reduction_db != null
            ? `권장 감소량: ${region.estimated_gain_reduction_db.toFixed(2)}dB`
            : '권장 감소량 정보를 확인 중입니다.',
          region.current_true_peak_dbtp != null
            ? `현재 트루 피크: ${region.current_true_peak_dbtp.toFixed(2)} dBTP`
            : '현재 트루 피크 정보를 확인 중입니다.',
          region.target_ceiling_dbtp != null
            ? `목표 상한: ${region.target_ceiling_dbtp.toFixed(1)} dBTP`
            : '목표 상한 정보를 확인 중입니다.',
        ]
      : [
          region.band_low_hz && region.band_high_hz
            ? `${region.band_low_hz}Hz~${region.band_high_hz}Hz 대역에서 문제가 감지됐어요.`
            : '주파수 대역 정보가 없습니다.',
          ...(kind === 'HARSHNESS'
            ? []
            : [
                involvedTrackNamesText
                  ? `관련 트랙: ${involvedTrackNamesText}`
                  : '관련 트랙 정보를 확인 중입니다.',
              ]),
        ]

  const clippingTrimValues = getClippingTrimValues(region)

  const clippingAction =
    kind === 'CLIPPING' &&
    clippingTrimValues.recommendedReductionDb != null
      ? ({
          type: 'apply_master_gain_trim',
          targetScope: 'MASTER',
          targetTrackId: null,
          startMs,
          endMs,
          recommendedReductionDb: clippingTrimValues.recommendedReductionDb,
          currentTruePeakDbtp: clippingTrimValues.currentTruePeakDbtp,
          targetCeilingDbtp: clippingTrimValues.targetCeilingDbtp ?? -1,
        } as AiSuggestionAction)
      : null

  const regionMarkers =
    kind === 'HARSHNESS'
      ? [{
          trackId: targetTrackId,
          centerHz: region.center_hz ?? null,
          bandLowHz: region.band_low_hz ?? null,
          bandHighHz: region.band_high_hz ?? null,
        }]
      : []

  return {
    id: regionId,
    issueType: region.issue_type ?? '',
    kind,
    uiMode,

    jobId: Number(region.job_id ?? currentAiJobId.value ?? null),
    regionId: numericRegionId,
    startMs,
    endMs,

    targetType,
    targetTrackId,
    involvedTrackIds,
    affectedClipIds,

    startPercent,
    endPercent,
    startPx,
    endPx,

    barStart,
    barEnd,

    title: `${titlePrefix} · ${barStart}마디에서 ${barEnd}마디 사이`,
    summary: region.analysis_summary ?? 'AI가 문제가 발생한 구간을 감지했어요.',
    explanation: null,
    bullets,

    bandLowHz: region.band_low_hz,
    bandHighHz: region.band_high_hz,

    recommendedGainReductionDb:
      clippingAction?.recommendedReductionDb ?? null,

    previewBands: [],
    actions: clippingAction ? [clippingAction] : [],
    markers: regionMarkers,
  }
}

function getSuggestionPayload(projections: any): AiSuggestionPayload | null {
  return (
    projections?.suggestion_payload ??
    projections?.suggestionPayload ??
    projections?.suggestion_group?.suggestion_payload ??
    projections?.suggestionGroup?.suggestionPayload ??
    projections?.suggestionGroups?.[0]?.suggestion_payload ??
    projections?.suggestionGroups?.[0]?.suggestionPayload ??
    null
  )
}

function mapPreviewBandsToEqBands(previewBands: any[] = []): TrackEqBandState[] {
  return previewBands
    .map((band, index): TrackEqBandState | null => {
      const frequencyHz = Number(band.frequency_hz ?? band.frequencyHz)
      const gainDeltaDb = Number(band.gain_delta_db ?? band.gainDeltaDb)
      const q = Number(band.q ?? 1)
      const rawEqTypeCode = Number(band.eq_type_code ?? band.eqTypeCode ?? 1)
      const eqTypeCode: EqTypeCode =
        rawEqTypeCode === 2 || rawEqTypeCode === 3 ? rawEqTypeCode : 1

      if (!Number.isFinite(frequencyHz) || !Number.isFinite(gainDeltaDb)) {
        return null
      }

      return {
        bandOrder: Number(band.band_order ?? band.bandOrder ?? index + 1),
        frequencyHz,
        gainDeltaDb,
        q: Number.isFinite(q) ? q : 1,
        eqTypeCode,
        sourceTypeCode: 3,
        jobId: band.job_id ?? band.jobId ?? null,
        suggestionActionId: band.suggestion_action_id ?? band.suggestionActionId ?? null,
        appliedSuggestionId: band.applied_suggestion_id ?? band.appliedSuggestionId ?? null,
      }
    })
    .filter((band): band is TrackEqBandState => band !== null)
}

function mapSuggestionIssueToAnalysisItem(
  issue: AiSuggestionIssue,
  durationMs: number,
  region: AiAnalysisRegion | null,
): AiAnalysisItem {
  const startMs = issue.startMs ?? 0
  const endMs = issue.endMs ?? startMs + 1
  const msPerBar = getMsPerBar()

  const barStart = Math.floor(startMs / msPerBar) + 1
  const barEnd = Math.max(barStart, Math.ceil(endMs / msPerBar))

  const startBarFloat = startMs / msPerBar
  const endBarFloat = Math.max(endMs / msPerBar, startBarFloat + 0.25)

  const startPx = TIMELINE_TRACK_HEADER_WIDTH + startBarFloat * trackStore.pixelPerBar
  const endPx = TIMELINE_TRACK_HEADER_WIDTH + endBarFloat * trackStore.pixelPerBar

  const startPercent = Math.max(0, Math.min(100, (startMs / durationMs) * 100))
  const endPercent = Math.max(
    startPercent + 0.5,
    Math.min(100, (endMs / durationMs) * 100),
  )

  const kind = mapIssueTypeToKind(issue.issueType)
  const involvedTrackIds = normalizeTrackIds(region?.involved_track_ids)
  const affectedClipIds = normalizeClipIds(region?.affected_clip_ids)

  const existingTrimAction = issue.actions?.find(action =>
    action.type === 'apply_master_gain_trim'
  )

  const issueTrimValues = getClippingTrimValues(issue)

  const trimAction =
    existingTrimAction ??
    (
      kind === 'CLIPPING' &&
      issueTrimValues.recommendedReductionDb != null
        ? ({
            type: 'apply_master_gain_trim',
            targetScope: 'MASTER',
            targetTrackId: null,
            startMs,
            endMs,
            recommendedReductionDb: issueTrimValues.recommendedReductionDb,
            currentTruePeakDbtp: issueTrimValues.currentTruePeakDbtp,
            targetCeilingDbtp: issueTrimValues.targetCeilingDbtp ?? -1,
          } as AiSuggestionAction)
        : null
    )

  const firstMarker = issue.markers?.[0] ?? null
  const markerBandLowHz = firstMarker?.bandLowHz ?? null
  const markerBandHighHz = firstMarker?.bandHighHz ?? null
  const markerCenterHz = firstMarker?.centerHz ?? null

  const targetType: AiIssueTargetType =
    issue.uiMode === 'master_trim'
      ? 'MASTER_TRACK'
      : issue.trackId
        ? 'TRACK'
        : 'TIMELINE'

  const targetTrackId =
    targetType === 'MASTER_TRACK'
      ? null
      : issue.trackId ?? involvedTrackIds[0] ?? null
  const numericRegionId = toNumericId(issue.issueId)

  const bullets =
    kind === 'HARSHNESS'
      ? [
          markerCenterHz != null
            ? `중심 주파수: ${markerCenterHz}Hz`
            : '중심 주파수 정보가 없습니다.',
          markerBandLowHz != null && markerBandHighHz != null
            ? `감지 대역: ${markerBandLowHz}Hz~${markerBandHighHz}Hz`
            : '감지 대역 정보가 없습니다.',
        ]
      : kind === 'CLIPPING'
        ? [
            trimAction?.recommendedReductionDb != null
              ? `권장 감소량: ${trimAction.recommendedReductionDb}dB`
              : '권장 감소량 정보를 확인 중입니다.',
            trimAction?.currentTruePeakDbtp != null
              ? `현재 트루 피크: ${trimAction.currentTruePeakDbtp} dBTP`
              : '현재 트루 피크 정보를 확인 중입니다.',
            trimAction?.targetCeilingDbtp != null
              ? `목표 상한: ${trimAction.targetCeilingDbtp} dBTP`
              : '목표 상한 정보를 확인 중입니다.',
          ]
        : []

  return {
    id: issue.issueId,
    issueType: issue.issueType,
    kind,
    uiMode: issue.uiMode,

    jobId: currentAiJobId.value,
    regionId: numericRegionId,
    startMs,
    endMs,

    targetType,
    targetTrackId,
    involvedTrackIds,
    affectedClipIds,

    startPercent,
    endPercent,
    startPx,
    endPx,

    barStart,
    barEnd,

    title:
      kind === 'CLIPPING'
        ? `클리핑 · ${barStart}마디에서 ${barEnd}마디 사이`
        : kind === 'HARSHNESS'
          ? `하쉬니스 · ${barStart}마디에서 ${barEnd}마디 사이`
          : `AI 분석 · ${barStart}마디에서 ${barEnd}마디 사이`,

    summary: issue.summary ?? 'AI가 문제가 발생한 구간을 감지했어요.',
    explanation: issue.explanation ?? null,
    bullets,

    bandLowHz: markerBandLowHz,
    bandHighHz: markerBandHighHz,

    recommendedGainReductionDb:
      trimAction?.recommendedReductionDb ?? null,

    previewBands: mapPreviewBandsToEqBands(issue.previewBands),
    actions: trimAction
      ? [
          ...(issue.actions ?? []).filter(action =>
            action.type !== 'apply_master_gain_trim'
          ),
          trimAction,
        ]
      : issue.actions ?? [],

    markers: issue.markers ?? [],
  }
}

function mapSuggestionPayloadToAnalysisItems(
  payload: AiSuggestionPayload,
  durationMs: number,
  regions: AiAnalysisRegion[],
): AiAnalysisItem[] {
  const regionMap = new Map(
    regions.map(region => [String(region.id), region]),
  )
  const issueMap = new Map(
    payload.issues.map(issue => [issue.issueId, issue]),
  )

  const orderedIssues =
    payload.navigationOrder?.length
      ? payload.navigationOrder
          .map(issueId => issueMap.get(issueId))
          .filter((issue): issue is AiSuggestionIssue => Boolean(issue))
      : payload.issues

  return orderedIssues.map(issue =>
    mapSuggestionIssueToAnalysisItem(
      issue,
      durationMs,
      regionMap.get(String(issue.issueId)) ?? null,
    ),
  )
}

function syncAiPreviewBandsFromActiveItem() {
  const item = activeAiAnalysis.value

  aiAfterBands.value = item?.previewBands ?? []
}

  function mapIssueTypeToKind(issueType: string | null): AiIssueKind {
  const normalized = issueType?.toLowerCase() ?? ''

  if (
    normalized.includes('clipping') ||
    normalized.includes('clip')
  ) {
    return 'CLIPPING'
  }

  if (
    normalized.includes('harshness') ||
    normalized.includes('harsh') ||
    normalized.includes('high_band') ||
    normalized.includes('sibilance') ||
    normalized.includes('sibilant')
  ) {
    return 'HARSHNESS'
  }

  if (
    normalized.includes('band_overlap') ||
    normalized.includes('overlap') ||
    normalized.includes('masking')
  ) {
    return 'BAND_OVERLAP'
  }

  return 'BAND_OVERLAP'
}

function getFeedbackStatusResult(response: any) {
  return response?.data?.data ?? response?.data ?? response
}

function getPreviewBandSpecs(statusResult: any) {
  const projections = statusResult?.projections ?? {}

  return (
    projections.preview_render?.preview_band_specs ??
    projections.previewRender?.previewBandSpecs ??
    projections.preview?.preview_band_specs ??
    projections.preview?.previewBandSpecs ??
    []
  )
}

function getPreviewActionTrackId(statusResult: any) {
  const projections = statusResult?.projections ?? {}

  return (
    projections.preview_render?.preview_action_track ??
    projections.previewRender?.previewActionTrack ??
    projections.preview?.preview_action_track ??
    projections.preview?.previewActionTrack ??
    null
  )
}

function mapPreviewBandSpecsToEqBands(previewBandSpecs: any[]): TrackEqBandState[] {
  return previewBandSpecs
    .map((band, index): TrackEqBandState | null => {
      const frequencyHz = Number(band.frequencyHz ?? band.frequency_hz)
      const gainDeltaDb = Number(band.gainDeltaDb ?? band.gain_delta_db)
      const q = Number(band.q ?? 1)
      const rawEqTypeCode = Number(band.eqTypeCode ?? band.eq_type_code ?? 1)
      const eqTypeCode: EqTypeCode =
        rawEqTypeCode === 2 || rawEqTypeCode === 3 ? rawEqTypeCode : 1

      if (!Number.isFinite(frequencyHz) || !Number.isFinite(gainDeltaDb)) {
        return null
      }

      return {
        bandOrder: Number(band.bandOrder ?? band.band_order ?? index + 1),
        eqTypeCode,
        frequencyHz,
        q: Number.isFinite(q) ? q : 1,
        gainDeltaDb,
        sourceTypeCode: 3,
        jobId: band.jobId ?? band.job_id ?? null,
        suggestionActionId: band.suggestionActionId ?? band.suggestion_action_id ?? null,
        appliedSuggestionId: band.appliedSuggestionId ?? band.applied_suggestion_id ?? null,
      } satisfies TrackEqBandState
    })
    .filter((band): band is TrackEqBandState => band !== null)
}

function applyPreviewBandsToActiveIssue(previewBands: TrackEqBandState[]) {
  const item = activeAiAnalysis.value
  if (!item) return

  aiAnalysisItems.value = aiAnalysisItems.value.map(analysisItem => {
    if (analysisItem.id !== item.id) return analysisItem

    return {
      ...analysisItem,
      previewBands,
    }
  })

  aiAfterBands.value = previewBands
}

function mapAiSuggestionToEqBands(statusResult: any): TrackEqBandState[] {
  const previewBandSpecs = getPreviewBandSpecs(statusResult)

  if (!Array.isArray(previewBandSpecs) || previewBandSpecs.length === 0) {
    return []
  }

  return mapPreviewBandSpecsToEqBands(previewBandSpecs)
}

function hasAiEqSuggestion(statusResult: any) {
  return mapAiSuggestionToEqBands(statusResult).length > 0
}

  async function runAiAnalysis() {
  if (aiAnalyzing.value) return

  try {
    aiAnalyzing.value = true
    aiAnalysisItems.value = []
    activeAiAnalysisId.value = null
    aiAfterBands.value = []
    currentAiJobId.value = null
    selectedAiRegionId.value = null
    appliedClippingIssueIds.value = new Set()
    appliedClippingInfoMap.value = new Map()
    appliedAiEqIssueIds.value = new Set()

    const selectedTrack = selectedEqTrack.value

    aiBeforeBands.value = selectedTrack?.eq?.bands
      ? selectedTrack.eq.bands.map(band => ({ ...band }))
      : []

    const snapshot = buildProjectSnapshotFromStore()

    if (snapshot.tracks.length === 0) {
        useAlertStore().showAlert('분석할 트랙이 없습니다.', 'warning')
      return
    }

    if (snapshot.clips.length === 0) {
        useAlertStore().showAlert('AI 분석을 하려면 먼저 저장된 오디오 클립이 필요합니다.', 'warning')
      return
    }

    let startResult: any = null
    let statusResult: any = null

    startResult = await startAiWorkflow({
      project_id: projectId,
      issue_types: [
        'band_overlap',
        'track_clipping',
        'master_clipping',
        'sibilance',
        'high_band_harshness',
      ],
      validator_mode: 'PASS',
      critic_mode: 'PASS',
      project_snapshot: snapshot,
    })

    currentAiJobId.value = startResult.job.job_id
    statusResult = await pollAiWorkflow(startResult.job.job_id)

    const suggestionPayload = getSuggestionPayload(statusResult.projections)
    const regions = statusResult.projections.analysis_regions ?? []

    const regionItems = regions.map((region: AiAnalysisRegion) =>
  mapRegionToAnalysisItem(region, snapshot.duration_ms),
)

const suggestionItems = suggestionPayload
  ? mapSuggestionPayloadToAnalysisItems(
      suggestionPayload,
      snapshot.duration_ms,
      regions,
    )
  : []

const suggestionNonClippingItems = suggestionItems.filter(item =>
  item.kind !== 'CLIPPING'
)

const actionableSuggestionClippingItems = suggestionItems.filter(item =>
  isActionableClippingItem(item)
)

const actionableRegionClippingItems = regionItems.filter((item: AiAnalysisItem) =>
  isActionableClippingItem(item)
)

// analysis_regions 에서 온 비클리핑 항목(BAND_OVERLAP, HARSHNESS 등)도 항상 포함
const regionNonClippingItems = regionItems.filter((item: AiAnalysisItem) =>
  item.kind !== 'CLIPPING'
)

let mergedItems =
  suggestionItems.length > 0
    ? [
        ...suggestionNonClippingItems,
        ...actionableSuggestionClippingItems,
        ...actionableRegionClippingItems,
        ...regionNonClippingItems,
      ]
    : regionItems

// [최적화 & 전시 지원] 대역 중복(BAND_OVERLAP) 이슈가 다수 발생 시 수동 처리 시간 단축을 위해
// 첫 번째 감지된 대역 중복 이슈만 남기고 나머지는 제외(필터링) 처리합니다.
const firstBandOverlapIndex = mergedItems.findIndex((item: AiAnalysisItem) => item.kind === 'BAND_OVERLAP')
if (firstBandOverlapIndex !== -1) {
  mergedItems = mergedItems.filter((item: AiAnalysisItem, index: number) => {
    if (item.kind === 'BAND_OVERLAP') {
      return index === firstBandOverlapIndex
    }
    return true
  })
}

if (mergedItems.length > 0) {
  aiAnalysisItems.value = mergedItems
} else {
  useAlertStore().showAlert('AI가 감지한 문제 구간이 없습니다.', 'info')
  return
}

// AI 분석 완료 시 기본적으로 첫 번째 팝업이 열려 있는 상태를 방지하기 위해 null로 초기화합니다.
activeAiAnalysisId.value = null

syncSelectedRegionIdFromActiveItem()
applyActiveAiAnalysisSelection()
syncAiPreviewBandsFromActiveItem()

trackEvent('ai_analysis_completed', {
      project_id: projectId,
      issue_count: aiAnalysisItems.value.length,
    })
  } catch (error) {
   // console.error(error)

   trackEvent('ai_analysis_failed', {
    project_id: projectId,
    reason: 'server_error',
  })

    // 에러 메시지를 안전하게 추출
    const errorMessage = error instanceof Error ? error.message : String(error ?? '')

    if (errorMessage.includes('timeout')) {
        useAlertStore().showAlert('AI 서버 응답이 지연되고 있습니다. 네트워크 상태를 확인하고 잠시 후 다시 시도해주세요.', 'warning')
      return
    }

    // 500 에러 등 서버 측 오류
    if (errorMessage.includes('서버') || errorMessage.includes('500')) {
      useAlertStore().showAlert('AI 분석 서버에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요.', 'error')
      return
    }

      useAlertStore().showAlert(errorMessage || 'AI 분석 중 오류가 발생했습니다.', 'error')
  } finally {
    aiAnalyzing.value = false
  }
}

function handleApplyAiEq() {
  const item = activeAiAnalysis.value

  if (!item) {
      useAlertStore().showAlert('적용할 AI 분석 결과가 없습니다.', 'warning')
    return
  }

  if (item.kind !== 'BAND_OVERLAP') {
      useAlertStore().showAlert('EQ 적용은 대역 중복 이슈에서만 사용할 수 있습니다.', 'warning')
    return
  }

  if (appliedAiEqIssueIds.value.has(item.id)) {
      useAlertStore().showAlert('이미 적용된 AI EQ입니다.', 'warning')
    return
  }

  const previewBands = item.previewBands.length > 0
    ? item.previewBands
    : aiAfterBands.value

  if (previewBands.length === 0) {
      useAlertStore().showAlert('적용할 AI EQ가 없습니다.', 'warning')
    return
  }

  const targetTrackId =
    item.targetTrackId ??
    selectedEqTrack.value?.trackId ??
    trackStore.selectedTrackId

  if (!targetTrackId) {
      useAlertStore().showAlert('AI EQ를 적용할 트랙을 찾지 못했습니다.', 'warning')
    return
  }

  const committedBands = previewBands.map((band, index): TrackEqBandState => ({
    ...band,
    bandOrder: index + 1,
    sourceTypeCode: 4,
    jobId: band.jobId ?? item.jobId ?? currentAiJobId.value,
    suggestionActionId: band.suggestionActionId ?? null,
    appliedSuggestionId: band.appliedSuggestionId ?? null,
  }))

  trackStore.setTrackEqBands(targetTrackId, committedBands)
  aiAfterBands.value = committedBands.map(band => ({ ...band }))

  appliedAiEqIssueIds.value = new Set([
    ...appliedAiEqIssueIds.value,
    item.id,
  ])

  // 자동 삭제 및 모달 팝업
  aiSuccessMessage.value = 'AI EQ 설정이 성공적으로 적용되었습니다.'
  aiAnalysisItems.value = aiAnalysisItems.value.filter(i => i.id !== item.id)
  if (activeAiAnalysisId.value === item.id) activeAiAnalysisId.value = null

  setTimeout(() => {
    aiSuccessMessage.value = null
  }, 2500)

  const appliedTrack = trackStore.trackList.find(track =>
    Number(track.trackId) === Number(targetTrackId)
  )

  aiBeforeBands.value = appliedTrack?.eq?.bands
    ? appliedTrack.eq.bands.map(band => ({ ...band }))
    : []

  useAlertStore().showAlert('AI EQ가 현재 트랙에 추가되었습니다.', 'success')
}

function handleCancelAiEq() {
  // 패널을 닫기 위해 현재 선택된 활성 상태만 해제합니다.
  // 주의: 전체 분석 결과(aiAnalysisItems)나 job_id는 유지해야 합니다.
  activeAiAnalysisId.value = null
  selectedAiRegionId.value = null
  aiBeforeBands.value = []
  aiAfterBands.value = []
}

function isActionableClippingItem(item: AiAnalysisItem) {
  if (item.kind !== 'CLIPPING') return false

  return (
    item.recommendedGainReductionDb != null ||
    item.actions.some(action =>
      action.type === 'apply_master_gain_trim' &&
      action.recommendedReductionDb != null
    )
  )
}

function getActiveClippingTrimAction(item: AiAnalysisItem): AiSuggestionAction | null {
  if (!item || item.kind !== 'CLIPPING') return null

  const action = item.actions.find(action =>
    action.type === 'apply_master_gain_trim'
  )

  if (action) return action

  if (item.recommendedGainReductionDb == null) return null

  return {
    type: 'apply_master_gain_trim',
    targetScope: 'MASTER',
    targetTrackId: null,
    recommendedReductionDb: item.recommendedGainReductionDb,
    targetCeilingDbtp: -1,
  }
}

async function handleApplyClippingIssue(item: AiAnalysisItem) {
  if (aiAnalyzing.value) return

  if (!item || item.kind !== 'CLIPPING') return

  if (appliedClippingIssueIds.value.has(item.id)) {
      useAlertStore().showAlert('이미 적용된 클리핑 이슈입니다.', 'warning')
    return
  }

  const action = getActiveClippingTrimAction(item)

  if (!action || action.recommendedReductionDb == null) {
      useAlertStore().showAlert('클리핑 적용값이 없습니다.', 'warning')
    return
  }

  const clippingAction = action
  const recommendedReductionDb = Number(clippingAction.recommendedReductionDb)

  let locked = false

  try {
    aiAnalyzing.value = true

    await lockMasterLimiter(projectId, true)
    locked = true

    const currentLimiter = await getMasterLimiter(projectId)

    const savedLimiter = await saveMasterLimiterDraft(projectId, {
  isEnabled: true,
  thresholdDb: currentLimiter.thresholdDb,
  ceilingDbfs: clippingAction.targetCeilingDbtp ?? currentLimiter.ceilingDbfs,
  attackMs: currentLimiter.attackMs,
  releaseMs: currentLimiter.releaseMs,
  // 백엔드의 inputGainDb 허용 범위는 [-12.0, 12.0]dB 입니다.
  // 계산된 게인 값이 이 범위를 이탈하여 유효성 에러가 발생하는 것을 방지하고자 최대/최솟값 한계 조정을 수행합니다.
  inputGainDb: Math.max(-12.0, Math.min(12.0, currentLimiter.inputGainDb - Math.abs(recommendedReductionDb))),
  makeupGainDb: currentLimiter.makeupGainDb,
  jobId: currentAiJobId.value,
  suggestionActionId: null,
  appliedSuggestionId: null,
  sourceType: 'AI_SUGGESTION',
})
    trackStore.setMasterLimiterState(savedLimiter)

    appliedClippingIssueIds.value = new Set([
      ...appliedClippingIssueIds.value,
      item.id,
    ])

    appliedClippingInfoMap.value = new Map([
      ...appliedClippingInfoMap.value,
      [
        item.id,
        {
          reductionDb: Math.abs(recommendedReductionDb),
          inputGainDb: savedLimiter.inputGainDb,
          ceilingDbfs: savedLimiter.ceilingDbfs,
        },
      ],
    ])

    // 자동 삭제 및 모달 팝업
    aiSuccessMessage.value = '마스터 리미터에 클리핑 감소안이 반영되었습니다.'
    aiAnalysisItems.value = aiAnalysisItems.value.filter(i => i.id !== item.id)
    if (activeAiAnalysisId.value === item.id) activeAiAnalysisId.value = null

    setTimeout(() => {
      aiSuccessMessage.value = null
    }, 2500)

   // goNextAiAnalysis()
  } catch (error: any) {
    console.error('[AI clipping apply failed]', {
      status: error?.response?.status,
      data: error?.response?.data,
      error,
    })

      useAlertStore().showAlert(error?.response?.data?.message ?? '클리핑 적용 중 오류가 발생했습니다.', 'error')
  } finally {
    if (locked) {
      try {
        await lockMasterLimiter(projectId, false)
      } catch (unlockError) {
        console.error('[AI clipping unlock failed]', unlockError)
      }
    }

    aiAnalyzing.value = false
  }
}

function handleDismissClippingIssue(item: AiAnalysisItem) {
  aiAnalysisItems.value = aiAnalysisItems.value.filter(i => i.id !== item.id)
  
  if (activeAiAnalysisId.value === item.id) {
    activeAiAnalysisId.value = null
  }
}

function getValidRevisionTrackIds(
  item: AiAnalysisItem,
  selectedTrackIds: number[],
) {
  if (item.involvedTrackIds.length === 0) return []

  const allowedTrackIds = new Set(item.involvedTrackIds.map(trackId => Number(trackId)))

  return selectedTrackIds.filter(trackId => allowedTrackIds.has(Number(trackId)))
}

function findPreserveClipIdFromSelectedRegion(
  item: AiAnalysisItem,
  selectedTrackIds: number[],
) {
  const validTrackIds = getValidRevisionTrackIds(item, selectedTrackIds)

  if (validTrackIds.length === 0 || item.affectedClipIds.length === 0) {
    return null
  }

  const affectedClipIds = new Set(item.affectedClipIds.map(clipId => Number(clipId)))

  for (const selectedTrackId of validTrackIds) {
    const targetTrack = trackStore.trackList.find(track =>
      Number(track.trackId) === Number(selectedTrackId),
    )

    if (!targetTrack) continue

    const candidateClips = targetTrack.clips
      .filter(clip => affectedClipIds.has(Number(clip.clipId)))
      .sort((left, right) => {
        const startDiff = Number(left.start) - Number(right.start)

        if (startDiff !== 0) return startDiff

        return Number(left.clipId) - Number(right.clipId)
      })

    const preserveClip = candidateClips[0]

    if (!preserveClip) continue

    const clipId = Number(preserveClip.clipId)

    if (!Number.isNaN(clipId)) {
      return clipId
    }
  }

  return null
}

function hasValidRevisionMetadata(item: AiAnalysisItem) {
  return (
    item.regionId != null &&
    item.involvedTrackIds.length > 0 &&
    item.affectedClipIds.length > 0
  )
}

function findPreserveClipIdFromSelectedTrack(selectedTrackIds: number[]) {
  const item = activeAiAnalysis.value

  if (!item) return null

  return findPreserveClipIdFromSelectedRegion(item, selectedTrackIds)
}
async function handleRequestAiEqRevision(payload: {
  selectedTrackIds: number[]
  message: string
}) {
  if (aiAnalyzing.value) return

  const item = activeAiAnalysis.value
  if (!item) return

  const jobId = item.jobId ?? currentAiJobId.value

  if (!jobId) {
      useAlertStore().showAlert('AI 분석 작업 정보가 없습니다. 먼저 AI 분석을 실행해주세요.', 'warning')
    return
  }

  if (!hasValidRevisionMetadata(item)) {
      useAlertStore().showAlert('현재 AI 이슈는 수정 요청 대상을 결정할 수 없어 다시 분석이 필요합니다.', 'warning')
    return
  }

  const validSelectedTrackIds = getValidRevisionTrackIds(item, payload.selectedTrackIds)

  if (validSelectedTrackIds.length === 0) {
      useAlertStore().showAlert('현재 문제 구간과 직접 관련된 트랙만 선택해 수정 요청을 보낼 수 있습니다.', 'warning')
    return
  }

  const preserveClipId = findPreserveClipIdFromSelectedTrack(validSelectedTrackIds)

  if (preserveClipId == null) {
      useAlertStore().showAlert('선택한 트랙에서 AI 분석 구간과 겹치는 클립을 찾지 못했습니다.', 'warning')
    return
  }

  const selectedTrackNamesText = formatTrackNames(validSelectedTrackIds)

  const selectedTrackText =
    selectedTrackNamesText
      ? `선택한 트랙: ${selectedTrackNamesText}. `
      : ''

  try {
    aiAnalyzing.value = true

    await sendAiWorkflowFeedback(jobId, {
      project_id: projectId,
      issue_id: String(item.id),
      action_type: 'preserve_clip',
      action_payload: {
        selected_track_ids: validSelectedTrackIds,
        preserve_clip_id: preserveClipId,
      },
      selected_region_id: item.regionId ?? selectedAiRegionId.value,
      preserve_clip_id: preserveClipId,
      user_feedback_message: `${selectedTrackText}${payload.message}`.trim(),
      user_decision: 'RESUME',
    })

    const statusResult = await pollAiFeedbackResult(jobId)

    const nextBands = mapAiSuggestionToEqBands(statusResult)

    if (nextBands.length === 0) {
        useAlertStore().showAlert('AI 수정안이 아직 생성되지 않았습니다. 잠시 후 다시 시도해주세요.', 'warning')
      return
    }

    const previewActionTrackId = getPreviewActionTrackId(statusResult)

    if (previewActionTrackId != null) {
      trackStore.selectTrack?.(Number(previewActionTrackId))
    }

    applyPreviewBandsToActiveIssue(nextBands)
  } catch (error) {
    console.error('[AI 수정 요청 실패]', error)
      useAlertStore().showAlert(error instanceof Error ? error.message : 'AI 수정 요청 중 오류가 발생했습니다.', 'error')
  } finally {
    aiAnalyzing.value = false
  }
}
function syncSelectedRegionIdFromActiveItem() {
  const item = activeAiAnalysis.value

  if (!item) {
    selectedAiRegionId.value = null
    return
  }

  selectedAiRegionId.value = item.regionId
}

function applyActiveAiAnalysisSelection() {
  const item = activeAiAnalysis.value

  if (!item) return

  if (item.kind === 'CLIPPING') {
    trackStore.selectMasterTrack?.()
    return
  }

  if (item.targetTrackId) {
    trackStore.selectTrack?.(item.targetTrackId)
  }
}

function resetAiEqSuggestionOnNavigation() {
  aiAfterBands.value = []
}

function setActiveAiAnalysis(id: string | number) {
  activeAiAnalysisId.value = id
  syncSelectedRegionIdFromActiveItem()
  resetAiEqSuggestionOnNavigation()
  applyActiveAiAnalysisSelection()
  syncAiPreviewBandsFromActiveItem()
}

function getClippingAppliedInfo(item: AiAnalysisItem) {
  if (!item || item.kind !== 'CLIPPING') return null
  return appliedClippingInfoMap.value.get(item.id) ?? null
}

function checkIsClippingApplied(item: AiAnalysisItem) {
  if (!item || item.kind !== 'CLIPPING') return false
  return appliedClippingIssueIds.value.has(item.id)
}

const activeAiMarkers = computed(() => {
  return activeAiAnalysis.value?.markers ?? []
})

const activeAiUiMode = computed(() => {
  return activeAiAnalysis.value?.uiMode ?? null
})

const isActiveAiMarkerOnly = computed(() => {
  return activeAiAnalysis.value?.uiMode === 'marker_only'
})

function getTrackDisplayName(trackId: number | null | undefined) {
  if (trackId == null) return null

  const numericTrackId = Number(trackId)

  if (Number.isNaN(numericTrackId)) return null

  if (trackStore.masterTrack?.trackId === numericTrackId) {
    return trackStore.masterTrack.name
  }

  const track = trackStore.trackList.find(track =>
    Number(track.trackId) === numericTrackId
  )

  if (track?.name) {
    return track.name
  }

  return `트랙 ${numericTrackId}`
}

function getTrackDisplayNames(trackIds: Array<number | null | undefined>) {
  return trackIds
    .map(trackId => getTrackDisplayName(trackId))
    .filter((name): name is string => Boolean(name))
}

function formatTrackNames(trackIds: Array<number | null | undefined>) {
  const names = getTrackDisplayNames(trackIds)

  return names.length > 0
    ? names.join(', ')
    : null
}

  const shouldShowAiEqRevisionPanel = computed(() => {
    const item = activeAiAnalysis.value

    if (!item) return false

    return item.uiMode === 'eq_ai' || item.markers.length > 0
  })

  // 일괄 적용 가능한 이슈(미적용 클리핑 또는 하쉬니스)가 있는지 확인
  const hasActionableAiIssues = computed(() => {
    return aiAnalysisItems.value.some(item => 
      (isActionableClippingItem(item) && !checkIsClippingApplied(item)) ||
      item.kind === 'HARSHNESS'
    )
  })

  // 일괄 적용 실행: 클리핑은 최대 감소값을 찾아 마스터 리미터에 한 번만 적용, 하쉬니스는 자동 제거(dismiss)
  async function handleApplyAll() {
    if (aiAnalyzing.value) return

    const clippingItems = aiAnalysisItems.value.filter(item => 
      isActionableClippingItem(item) && !checkIsClippingApplied(item)
    )

    let maxReductionDb = 0
    let targetCeilingDbtp: number | null = null

    // 모든 클리핑 이슈 중 최대 감소값 찾기
    for (const item of clippingItems) {
      const action = getActiveClippingTrimAction(item)
      if (action && action.recommendedReductionDb != null) {
        const reduction = Math.abs(Number(action.recommendedReductionDb))
        if (reduction > maxReductionDb) {
          maxReductionDb = reduction
        }
        if (action.targetCeilingDbtp != null && action.targetCeilingDbtp !== -1) {
          targetCeilingDbtp = action.targetCeilingDbtp
        }
      }
    }

    if (clippingItems.length > 0 && maxReductionDb > 0) {
      let locked = false
      try {
        aiAnalyzing.value = true
        await lockMasterLimiter(projectId, true)
        locked = true

        const currentLimiter = await getMasterLimiter(projectId)

        const savedLimiter = await saveMasterLimiterDraft(projectId, {
          isEnabled: true,
          thresholdDb: currentLimiter.thresholdDb,
          ceilingDbfs: targetCeilingDbtp ?? currentLimiter.ceilingDbfs,
          attackMs: currentLimiter.attackMs,
          releaseMs: currentLimiter.releaseMs,
          inputGainDb: Math.max(-12.0, Math.min(12.0, currentLimiter.inputGainDb - maxReductionDb)),
          makeupGainDb: currentLimiter.makeupGainDb,
          jobId: currentAiJobId.value,
          suggestionActionId: null,
          appliedSuggestionId: null,
          sourceType: 'AI_SUGGESTION',
        })
        trackStore.setMasterLimiterState(savedLimiter)

        const newIssueIds = new Set(appliedClippingIssueIds.value)
        const newInfoMap = new Map(appliedClippingInfoMap.value)

        for (const item of clippingItems) {
          newIssueIds.add(item.id)
          newInfoMap.set(item.id, {
            reductionDb: maxReductionDb,
            inputGainDb: savedLimiter.inputGainDb,
            ceilingDbfs: savedLimiter.ceilingDbfs,
          })
        }

        appliedClippingIssueIds.value = newIssueIds
        appliedClippingInfoMap.value = newInfoMap

        const appliedIds = new Set(clippingItems.map(i => i.id))
        aiAnalysisItems.value = aiAnalysisItems.value.filter(i => !appliedIds.has(i.id))
        
        if (activeAiAnalysisId.value && appliedIds.has(activeAiAnalysisId.value)) {
          activeAiAnalysisId.value = null
        }
      } catch (error: any) {
        console.error('[AI bulk clipping apply failed]', error)
        useAlertStore().showAlert(error?.response?.data?.message ?? '일괄 클리핑 적용 중 오류가 발생했습니다.', 'error')
      } finally {
        if (locked) {
          try {
            await lockMasterLimiter(projectId, false)
          } catch (unlockError) {
            console.error('[AI clipping unlock failed]', unlockError)
          }
        }
        aiAnalyzing.value = false
      }
    }

    // 하쉬니스 이슈는 마커만 표시하는 유형이므로 일괄 제거(dismiss)
    const harshnessItems = aiAnalysisItems.value.filter(item => item.kind === 'HARSHNESS')
    for (const item of harshnessItems) {
      handleDismissClippingIssue(item)
    }

    if (clippingItems.length > 0 || harshnessItems.length > 0) {
      aiSuccessMessage.value = '선택 가능한 모든 AI 이슈가 일괄 적용 및 정리되었습니다.'
      setTimeout(() => {
        if (aiSuccessMessage.value === '선택 가능한 모든 AI 이슈가 일괄 적용 및 정리되었습니다.') {
          aiSuccessMessage.value = null
        }
      }, 2500)
    }
  }

  return {
    activeAiMarkers,
    aiAnalyzing,
    aiConflict,
    aiBeforeBands,
    aiAfterBands,
    selectedEqTrack,
    runAiAnalysis,
    handleApplyAiEq,
    handleCancelAiEq,
    handleRequestAiEqRevision,
    handleApplyClippingIssue,
    handleDismissClippingIssue,
    hasActionableAiIssues,
    handleApplyAll,
    setActiveAiAnalysis,
    aiAnalysisItems,
    activeAiAnalysisId,
    activeAiAnalysis,
    shouldShowAiEqRevisionPanel,
    checkIsClippingApplied,
    getClippingAppliedInfo,
    activeAiUiMode,
    isActiveAiMarkerOnly,
    aiSuccessMessage,
  }
}
