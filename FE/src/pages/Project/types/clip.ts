//오디오 원본 데이터 규격(프로젝트상세조회API)
export interface AudioMetadata {
    audioMetadataId: number; //오디오id
    cdnUrl: string; //오디오의 CDN urL
    originalName: string; // 오디오 파일명
    durationMs: number; //오디오 길이(ms)
}

// REST API를 통해 들어오는 클립 원본 데이터 규격
export interface ClipDto {
    clipId: number; //클립id
    start: number; // 클립 시작점의 마디
    duration: number; // 클립의 길이
    audioStartMs: number; // 클립 시작점의 오디오 시간
    audioDurationMs: number; //클립 오디오의 지속 시간
    color: string; //클립의 색상
    audio: AudioMetadata; //오디오 정보
}

//화면 렌더링용 확장 타입
export interface ClipUIState extends ClipDto {
    //?가 있으면 받아올 수도 있고 말수도 있고
    isSelected?: boolean;
    isDragging?: boolean;
    isLocked?: boolean;
}

//EQ
export type EqTypeCode = 1 | 2 | 3
// 1 = BELL
// 2 = LOW_SHELF
// 3 = HIGH_SHELF

export type EqSourceTypeCode = 1 | 2 | 3 | 4
// 1 = USER_MANUAL
// 2 = SYSTEM
// 3 = AI_CONFIRM
// 4 = AI_APPLIED

export interface TrackEqBandState {
  id?: number
  bandOrder: number
  eqTypeCode: EqTypeCode
  frequencyHz: number
  q: number
  gainDeltaDb: number
  sourceTypeCode: EqSourceTypeCode

  jobId?: number | null
  suggestionActionId?: number | null
  appliedSuggestionId?: number | null
}

export interface TrackEqState {
  bands: TrackEqBandState[]
}

