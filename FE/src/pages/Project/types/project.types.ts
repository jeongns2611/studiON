export type ProjectId = number
export type MasterTrackId = number
export type UserId = number

export type RootNote =
  | 'C'
  | 'C#'
  | 'D'
  | 'Eb'
  | 'E'
  | 'F'
  | 'F#'
  | 'G'
  | 'Ab'
  | 'A'
  | 'Bb'
  | 'B'

export type Mode = 'Major' | 'Minor'

export interface CreateProjectRequest {
  name: string
  rootNote: RootNote
  projectMode: Mode
  tempo: number
  timeSigNumerator: number
  timeSigDenominator: number
}

export interface CreateProjectResponse {
  code: number
  message: string
  isSuccess: boolean
  data: {
    project: {
      projectId: number
      name: string
      rootNote: RootNote
      mode: Mode
      tempo: number
      timeSigNumerator: number
      timeSigDenominator: number
      totalBarCount: number
      totalPlayTimeMs: number
    }
    masterTrack: {
      masterTrackId: number
      isSoloed: boolean
      isMuted: boolean
      volume: number
      pan: number
    }
    defaultTrack: {
      trackId: number
      name: string
      type: string
      preTrackId: number | null
      postTrackId: number | null
      isMuted: boolean
      isSoloed: boolean
      volume: number
      pan: number
    }
  }
}

export interface ProjectSummary {
  projectId: ProjectId
  name: string
  rootNote: RootNote
  mode: Mode
  tempo: number
  timeSigNumerator: number
  timeSigDenominator: number
  totalBarCount: number
  totalPlayTimeMs: number
}

export interface MasterTrackSummary {
  masterTrackId: MasterTrackId
  isSoloed: boolean
  isMuted: boolean
  volume: number
  pan: number
}

export interface CreateProjectData {
  project: ProjectSummary
  masterTrack: MasterTrackSummary
}

export interface ProjectListMember {
  userId: UserId
  profileImgUrl: string
}

export interface ProjectListItem {
  projectId: ProjectId
  projectName: string
  totalBarCount: number
  totalPlayTime: number
  totalAudioSize: number
  lastUpdateAt: string
  members: ProjectListMember[]
}

export interface FetchProjectsData {
  projects: ProjectListItem[]
  currentTotalSizeBytes: number
  maxTotalSizeBytes: number
}

export interface FetchProjectsResponse {
  code: number
  message: string
  isSuccess: boolean
  data: FetchProjectsData
}

export interface ApiResponse<T> {
  code: number
  message: string
  isSuccess: boolean
  data: T
}

// 초대코드 생성 응답 data
export interface CreateProjectInviteCodeData {
  projectId: number
  inviteCode: string
  expiresAt: string
}

// 초대코드 생성 응답 전체
export type CreateInviteCodeResponse = ApiResponse<CreateProjectInviteCodeData>

// 초대코드 입력 성공 응답 data
export interface AcceptInviteCodeData {
  projectId: number
}

// 초대코드 입력 응답 전체
export type AcceptInviteCodeResponse = ApiResponse<AcceptInviteCodeData | null>

// 프로젝트 저장 응답
export interface SaveProjectSnapshotResponse {
  code: string;
  message: string;
  isSuccess: boolean;
  data: {
    projectId: number;
    trigger: string;       // 예: "MANUAL"
    saveAt: string;        // 예: "2026-05-12T15:30:00"
  };
}