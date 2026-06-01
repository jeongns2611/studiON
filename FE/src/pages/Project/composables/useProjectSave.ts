import { ref } from 'vue'
import { projectApi } from '../api/project.api'
import { useTrackStore } from '../store/useTrackStore'
import { useAlertStore } from '@/shared/stores/useAlertStore'
import type { TrackEqBandState } from '../types'

type EqType = 'BELL' | 'LOW_SHELF' | 'HIGH_SHELF'
type SourceType = 'USER_MANUAL' | 'SYSTEM' | 'AI_CONFIRM' | 'AI_APPLIED'

function formatTime(isoString: string) {
  const date = new Date(isoString)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${hours}:${minutes}`
}

function mapEqTypeCodeToEqType(eqTypeCode?: number | null): EqType {
  switch (eqTypeCode) {
    case 2:
      return 'LOW_SHELF'
    case 3:
      return 'HIGH_SHELF'
    case 1:
    default:
      return 'BELL'
  }
}

function mapSourceTypeCodeToSourceType(sourceTypeCode?: number | null): SourceType {
  switch (sourceTypeCode) {
    case 2:
      return 'SYSTEM'
    case 3:
      return 'AI_CONFIRM'
    case 4:
      return 'AI_APPLIED'
    case 1:
    default:
      return 'USER_MANUAL'
  }
}

function normalizeEqBandsForSave(bands: TrackEqBandState[]) {
  return bands
    .filter(band => {
      return (
        Number.isFinite(Number(band.frequencyHz)) &&
        Number(band.frequencyHz) > 0 &&
        Number.isFinite(Number(band.q)) &&
        Number(band.q) > 0 &&
        Number.isFinite(Number(band.gainDeltaDb))
      )
    })
    .map((band, index) => {
      const bandWithMeta = band as TrackEqBandState & {
        sourceTypeCode?: number | null
        jobId?: number | null
        suggestionActionId?: number | null
        appliedSuggestionId?: number | null
      }

      return {
        bandOrder: index + 1,
        eqType: mapEqTypeCodeToEqType(band.eqTypeCode),
        frequencyHz: Number(band.frequencyHz),
        q: Number(band.q),
        gainDeltaDb: Number(band.gainDeltaDb),
        sourceType: 'USER_MANUAL' as const,
        jobId: null,
        suggestionActionId: null,
        appliedSuggestionId: null,
      }
    })
}

export function useProjectSave(projectId: number) {
  const lastSavedTime = ref<string>('--:--')
  const trackStore = useTrackStore()

  async function saveEqBandsBeforeSnapshot() {
    const trackEqs = await projectApi.getProjectTrackEqs(projectId)

    const trackEqIdByTrackId = new Map<number, number>()

    trackEqs.forEach(trackEq => {
      trackEqIdByTrackId.set(Number(trackEq.trackId), Number(trackEq.trackEqId))
    })

    for (const track of trackStore.trackList) {
      const trackEqId = trackEqIdByTrackId.get(Number(track.trackId))

      if (!trackEqId) continue

      const bands = normalizeEqBandsForSave(track.eq?.bands ?? [])

      if (bands.length === 0) continue

      await projectApi.saveTrackEqBands(trackEqId, {
        bands,
      })
    }
  }

  async function handleSave() {
    try {
      await saveEqBandsBeforeSnapshot()

      const response = await projectApi.saveProjectSnapshot(projectId)
      lastSavedTime.value = formatTime(response.saveAt)
    } catch (error) {
      console.error('저장 실패:', error)
      useAlertStore().showAlert('프로젝트 저장에 실패했습니다.', 'error')
    }
  }

  return { lastSavedTime, handleSave }
}