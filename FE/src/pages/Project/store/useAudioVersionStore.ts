import axios from 'axios'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  createUploadedAudioVersion,
  deleteAudioVersion,
  getAudioVersionDownloadUrl,
  getAudioVersionList,
  getAudioVersionUploadUrl,
  type AudioVersionCreateRequest,
  type AudioVersionSummary,
} from '../api/audioVersion.api'

export const useAudioVersionStore = defineStore('audioVersion', () => {
  const versions = ref<AudioVersionSummary[]>([])
  const isLoading = ref(false)

  const fetchVersions = async (projectId: number) => {
    try {
      isLoading.value = true
      const res = await getAudioVersionList(projectId)
      if (res && res.data) {
        versions.value = res.data.versions || []
      }
    } catch (error) {
      console.error('버전 목록을 불러오는 중 오류 발생:', error)
    } finally {
      isLoading.value = false
    }
  }

  const saveVersion = async (
    projectId: number,
    payload: AudioVersionCreateRequest,
    blob: Blob,
    durationMs: number,
  ) => {
    try {
      const originalName = `${payload.name}.wav`
      const uploadUrlResponse = await getAudioVersionUploadUrl(projectId, {
        originalName,
        mimeType: 'WAV',
        sizeBytes: blob.size,
      })

      await axios.put(uploadUrlResponse.data.uploadUrl, blob, {
        headers: {
          'Content-Type': 'audio/wav',
        },
      })

      const res = await createUploadedAudioVersion(projectId, {
        ...payload,
        objectKey: uploadUrlResponse.data.objectKey,
        originalName,
        storedName: uploadUrlResponse.data.storedName,
        mimeType: 'WAV',
        sizeBytes: blob.size,
        durationMs,
      })

      return res.isSuccess !== false
    } catch (error) {
      console.error('버전 저장 중 오류 발생:', error)
      return false
    }
  }

  const removeVersion = async (projectId: number, versionId: number) => {
    try {
      await deleteAudioVersion(projectId, versionId)
      await fetchVersions(projectId)
      return true
    } catch (error) {
      console.error('버전 삭제 중 오류 발생:', error)
      return false
    }
  }

  const downloadVersion = async (projectId: number, versionId: number, fileName: string) => {
    try {
      const res = await getAudioVersionDownloadUrl(projectId, versionId)
      if (res && res.data && res.data.downloadUrl) {
        const url = res.data.downloadUrl
        const link = document.createElement('a')
        link.href = url
        link.download = fileName.endsWith('.wav') ? fileName : `${fileName}.wav`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        return true
      }
    } catch (error) {
      console.error('다운로드 URL 발급 중 오류 발생:', error)
    }
    return false
  }

  return {
    versions,
    isLoading,
    fetchVersions,
    saveVersion,
    removeVersion,
    downloadVersion,
  }
})
