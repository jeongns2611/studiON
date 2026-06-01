//프로젝트 도메인 관련한 백엔드 통신을 모아둠.
import type {
  AcceptInviteCodeResponse,
  CreateInviteCodeResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  FetchProjectsResponse,
  Mode,
  ProjectId,
  RootNote,
} from '../types/project.types'
import type { FetchCommentsParams, FetchCommentsResponse, CommentDto } from '../types/comment.types';
import { axiosInstance } from '@/shared/api/axiosInstance';
import type { TrackDto } from '@/pages/Project/types';
import type { SaveProjectSnapshotResponse } from '../types/project.types';

// ==========================================
// [인터페이스] 백엔드 응답 규격 (명세서 기반)
// ==========================================

//프로젝트 상세보기 응답
export interface ProjectDetailResponse {
  code: number;
  message: string;
  isSuccess: boolean;
  data: {
    projectId: number;
    name: string;
    rootNote: string;
    mode: string;
    tempo: number;
    timeSigNumerator: number;
    timeSigDenominator: number;
    totalBarCount: number;
    totalPlayTimeMs: number;
    masterTrack: {
      masterTrackId: number;
      isSoloed: boolean;
      isMuted: boolean;
      volume: number;
      pan: number;
    };
    tracks: TrackDto[];
    members: {
      userId: number;
      nickname: string;
      profileImageUrl: string | null;
    }[];
    currentTotalSizeBytes: number;
    maxTotalSizeBytes: number;
  }
}

// --- [타입 선언부] ---
export interface AudioDetailResponse {
  code: string;
  message: string;
  isSuccess: boolean;
  data: {
    audioMetadataId: number;
    originalName: string;
    mimeType: string;
    sizeBytes: number;
    durationMs: number;
    audioUrl: string; // ✨ 백엔드에서 반환해주는 실제 오디오 URL
  }
}


// ==============================
// 프로젝트 생성 기본값
// ==============================


const DEFAULT_PROJECT_NAME = '새 프로젝트';
const DEFAULT_ROOT_NOTE: RootNote = 'C';
const DEFAULT_MODE: Mode = 'Major';
const DEFAULT_TEMPO = 120.0;
const DEFAULT_TIME_SIG_NUMERATOR = 4;
const DEFAULT_TIME_SIG_DENOMINATOR = 4;

// 기존 프로젝트명과 겹치지 않는 기본 프로젝트명을 만든다.
// 예: 새 프로젝트, 새 프로젝트1, 새 프로젝트2
export function getNextDefaultProjectName(existingProjectNames: string[]): string {
  const nameSet = new Set(existingProjectNames)

  if (!nameSet.has(DEFAULT_PROJECT_NAME)) {
    return DEFAULT_PROJECT_NAME
  }

  let suffix = 1

  while (nameSet.has(`${DEFAULT_PROJECT_NAME}${suffix}`)) {
    suffix += 1
  }

  return `${DEFAULT_PROJECT_NAME}${suffix}`
}

// 프로젝트 생성 API에 보낼 기본 payload를 만든다.
export function buildCreateProjectPayload(
  existingProjectNames: string[] = [],
): CreateProjectRequest {
  return {
    name: getNextDefaultProjectName(existingProjectNames),
    rootNote: DEFAULT_ROOT_NOTE,
    projectMode: DEFAULT_MODE,
    tempo: DEFAULT_TEMPO,
    timeSigNumerator: DEFAULT_TIME_SIG_NUMERATOR,
    timeSigDenominator: DEFAULT_TIME_SIG_DENOMINATOR,
  }
}

// ==========================================
// [추가] 오디오 파일 업로드 관련 API 인터페이스
// ==========================================
export interface GetUploadUrlRequest {
  originalName: string;
  mimeType: 'MPEG' | 'WAV';
  sizeBytes: number;
}

export interface GetUploadUrlResponse {
  code: string;
  message: string;
  isSuccess: boolean;
  data: {
    objectKey: string;
    storedName: string;
    uploadUrl: string; // S3 Presigned URL
  }
}

export interface SaveAudioMetadataRequest {
  objectKey: string;
  originalName: string;
  storedName: string;
  mimeType: 'MPEG' | 'WAV';
  sizeBytes: number;
  durationMs: number;
}

export interface SaveAudioMetadataResponse {
  code: string;
  message: string;
  isSuccess: boolean;
  data: {
    audioMetadataId: number;
    originalName: string;
    mimeType: string;
    sizeBytes: number;
    durationMs: number;
  }
}

type EqType = 'BELL' | 'LOW_SHELF' | 'HIGH_SHELF'
type EqSourceType = 'USER_MANUAL' | 'SYSTEM' | 'AI_CONFIRM' | 'AI_APPLIED'

export interface TrackEqSummary {
  trackEqId: number
  trackId: number
  projectId: number
}

export interface TrackEqBandSummary {
  trackEqBandId: number
  trackEqId: number
  bandOrder: number
  eqType: EqType
  frequencyHz: number
  q: number
  gainDeltaDb: number
  jobId: number | null
  suggestionActionId: number | null
  appliedSuggestionId: number | null
  sourceType: EqSourceType
}

interface TrackEqsResponse {
  isSuccess: boolean
  code: string
  message: string
  data: {
    trackEqs: TrackEqSummary[]
  }
}

interface TrackEqBandsResponse {
  isSuccess: boolean
  code: string
  message: string
  data: {
    trackEqBandSummaries: TrackEqBandSummary[]
  }
}

interface SaveTrackEqBandsRequest {
  bands: {
    bandOrder: number
    eqType: EqType
    frequencyHz: number
    q: number
    gainDeltaDb: number
    sourceType: EqSourceType
    jobId: number | null
    suggestionActionId: number | null
    appliedSuggestionId: number | null
  }[]
}


// ==========================================
// [API 객체] 프로젝트 관련 통신 모음집
// ==========================================
export const projectApi = {
  // ------------------------------------------
  // 1. 프로젝트 초기 데이터
  // ------------------------------------------
  /**
   * 프로젝트 상세 조회 (초기 로딩)
   * GET /api/v1/projects/{projectId}
   */
  getProjectDetail: async (projectId: number) => {
    //shared에서 정의한 axios사용 -> 인증로직 자동첨부됨
    const response = await axiosInstance.get<ProjectDetailResponse>(`/api/v1/projects/${projectId}`);

    //인터셉터 덕분에 response.data에 data객체가 바로 들어있음
    return response.data.data;
  },

  // [추가] 오디오 단건 상세 조회 (오디오 URL 획득용)
  getAudioDetail: async (projectId: number, audioMetadataId: number) => {
    const response = await axiosInstance.get<AudioDetailResponse>(`/api/v1/projects/${projectId}/audios/${audioMetadataId}`);
    return response.data.data;
  },

  // S3 업로드 URL 발급
  getAudioUploadUrl: async (projectId: number, payload: GetUploadUrlRequest) => {
    const response = await axiosInstance.post<GetUploadUrlResponse>(`/api/v1/projects/${projectId}/audios/upload-url`, payload);
    return response.data.data;
  },

  // 메타데이터 저장
  saveAudioMetadata: async (projectId: number, payload: SaveAudioMetadataRequest) => {
    const response = await axiosInstance.post<SaveAudioMetadataResponse>(`/api/v1/projects/${projectId}/audios`, payload);
    return response.data.data;
  },

  //프로젝트 코멘트 목록 조회
  getComments: async (projectId: number, params?: FetchCommentsParams) => {
    const response = await axiosInstance.get<any>(
      `/api/v1/projects/${projectId}/comments`,
      { params }
    );
    const comments = response.data.data.comments || [];
    // 백엔드 응답 필드명(user)을 프론트엔드 컴포넌트(author)에 맞게 맵핑
    return comments.map((c: any) => ({
      ...c,
      author: c.user || c.author,
      replies: c.replies?.map((r: any) => ({ ...r, author: r.user || r.author })) || []
    })) as CommentDto[];
  },

  getProjectTrackEqs: async (projectId: number) => {
    const response = await axiosInstance.get<TrackEqsResponse>(`/api/v1/eq/projects/${projectId}/track-eqs`)

    return response.data.data.trackEqs
  },

  getTrackEqBands: async (trackEqId: number) => {
    const response = await axiosInstance.get<TrackEqBandsResponse>(`/api/v1/eq/track-eqs/${trackEqId}/bands`)

    return response.data.data.trackEqBandSummaries
  },

  saveTrackEqBands: async (
    trackEqId: number,
    payload: SaveTrackEqBandsRequest,
  ) => {
    const response = await axiosInstance.post<{
      isSuccess: boolean
      code: string
      message: string
      data: null
    }>(
      `/api/v1/eq/track-eqs/${trackEqId}/bands`,
      payload,
    )

    return response.data
  },

  // 프로젝트 수동 저장
  saveProjectSnapshot: async (projectId: number) => {
    const response = await axiosInstance.post<SaveProjectSnapshotResponse>(
      `/api/v1/projects/${projectId}/snapshot`
    );
    return response.data.data;
  }

}

// 프로젝트 목록 조회

export async function fetchProjects(): Promise<FetchProjectsResponse> {
  const { data } = await axiosInstance.get('/api/v1/projects')
  return data
}

/**
 * 프로젝트 생성
 */
export async function createProject(
  payload: CreateProjectRequest = buildCreateProjectPayload(),
): Promise<CreateProjectResponse> {

  const response = await axiosInstance.post<CreateProjectResponse>(
    '/api/v1/projects',
    payload,
  )

  return response.data
}

// 프로젝트 초대코드 생성
// POST /api/v1/projects/{projectId}/invitations
export async function createProjectInviteCode(
  projectId: ProjectId,
): Promise<CreateInviteCodeResponse> {
  const response = await axiosInstance.post<CreateInviteCodeResponse>(
    `/api/v1/projects/${projectId}/invitations`,
  )

  return response.data
}

// 프로젝트 초대코드 입력
// POST /api/v1/invitations/{inviteCode}/accept
export async function acceptProjectInviteCode(
  inviteCode: string,
): Promise<AcceptInviteCodeResponse> {
  const response = await axiosInstance.post<AcceptInviteCodeResponse>(
    `/api/v1/invitations/${inviteCode}/accept`,
  )

  return response.data
}

