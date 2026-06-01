import { defineStore } from 'pinia'
import { ref } from 'vue'
import { projectApi } from '../api/project.api'
import type { CommentDto } from '../types/comment.types'

export const useCommentStore = defineStore('commentStore', () => {
  const comments = ref<CommentDto[]>([])
  const isLoading = ref(false)
  
  // 패널 필터 상태
  const isResolvedFilter = ref(false)
  const isMentionedFilter = ref(false)
  const selectedTrackId = ref<number | undefined>(undefined)
  
  // 알림 (빨간 점) 상태
  const hasNewComment = ref(false)
  
  const setHasNewComment = (val: boolean) => {
    hasNewComment.value = val
  }

  const fetchComments = async (projectId: number) => {
    try {
      isLoading.value = true
      const response = await projectApi.getComments(projectId, {
        // 백엔드의 isResolved 필터 로직 우회: 프론트엔드에서 모든 데이터를 받아 직접 필터링합니다.
      })
      comments.value = response
    } catch (error) {
     // console.error('코멘트 목록 조회 실패:', error)
    } finally {
      isLoading.value = false
    }
  }

  return {
    comments,
    isLoading,
    isResolvedFilter,
    isMentionedFilter,
    selectedTrackId,
    hasNewComment,
    setHasNewComment,
    fetchComments,
  }
})
