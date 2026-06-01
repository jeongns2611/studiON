import { axiosInstance } from '@/shared/api/axiosInstance'

export interface AudioVersionSummary {
  versionId: number
  name: string
  memo: string
  durationMs: number
  sizeBytes: number
  createdAt: string
}

export interface AudioVersionListResponse {
  totalVersion: number
  versions: AudioVersionSummary[]
}

export interface AudioVersionCreateRequest {
  name: string
  memo: string
}

export interface AudioVersionUploadUrlRequest {
  originalName: string
  mimeType: 'MPEG' | 'WAV'
  sizeBytes: number
}

export interface AudioVersionUploadUrlResponse {
  objectKey: string
  storedName: string
  uploadUrl: string
}

export interface AudioVersionUploadedCreateRequest extends AudioVersionCreateRequest {
  objectKey: string
  originalName: string
  storedName: string
  mimeType: 'MPEG' | 'WAV'
  sizeBytes: number
  durationMs: number
}

export interface AudioVersionDownloadUrlResponse {
  downloadUrl: string
}

// 1. 버전 이력 조회
export const getAudioVersionList = async (projectId: number) => {
  const { data } = await axiosInstance.get(`/api/v1/projects/${projectId}/versions`)
  return data
}

// 2. 버전 생성 (비동기 처리됨)
export const createAudioVersion = async (projectId: number, payload: AudioVersionCreateRequest) => {
  const { data } = await axiosInstance.post(`/api/v1/projects/${projectId}/versions`, payload)
  return data
}

export const getAudioVersionUploadUrl = async (
  projectId: number,
  payload: AudioVersionUploadUrlRequest,
) => {
  const { data } = await axiosInstance.post(`/api/v1/projects/${projectId}/versions/upload-url`, payload)
  return data
}

export const createUploadedAudioVersion = async (
  projectId: number,
  payload: AudioVersionUploadedCreateRequest,
) => {
  const { data } = await axiosInstance.post(`/api/v1/projects/${projectId}/versions/uploaded`, payload)
  return data
}

// 3. 버전 다운로드 URL 획득
export const getAudioVersionDownloadUrl = async (projectId: number, versionId: number) => {
  const { data } = await axiosInstance.get(`/api/v1/projects/${projectId}/versions/${versionId}/download-url`)
  return data
}

// 4. 버전 삭제
export const deleteAudioVersion = async (projectId: number, versionId: number) => {
  const { data } = await axiosInstance.delete(`/api/v1/projects/${projectId}/versions/${versionId}`)
  return data
}
