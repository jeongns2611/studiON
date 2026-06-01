export interface TimelineComment {
  id: string
  authorId?: number
  author: string
  mention?: string
  content: string
  color: string
  profileImageUrl?: string | null
}

export interface TrackMeasureCommentGroup {
  trackId: string
  trackName: string
  measure: number
  resolved?: boolean
  comments: TimelineComment[]
}

export interface CommentUser {
  userId: number
  nickname: string
  profileImgUrl: string | null
}

export interface AddCommentPayload {
  trackId: number
  parentCommentId: number | null
  content: string
  location: number
  mentionedUserIds: number[]
}

export interface CommentAddedResponse {
  projectId: number
  trackId: number
  commentId: number
  parentCommentId: number | null
  content: string
  location: number
  isResolved: boolean
  author: CommentUser
  mentionedUsers: CommentUser[]
  createdAt: string
}

export interface DeleteCommentPayload {
  commentId: number
}

export interface CommentDeletedResponse {
  projectId: number
  trackId: number
  commentId: number
  parentCommentId: number | null
}

export interface ChangeCommentStatusPayload {
  commentId: number
}

export interface CommentStatusChangedResponse {
  projectId: number
  trackId: number
  commentId: number
  parentCommentId: number | null
  isResolved: boolean
  updatedAt: string
}

export interface SocketErrorResponse {
  code: number
  message: string
}

// GET API 호출 시 사용할 쿼리 파라미터 인터페이스
export interface FetchCommentsParams {
  isResolved?: boolean;
  trackId?: number;
  mentionedMe?: boolean;
}

// 백엔드 CommentDto 대응
export interface CommentDto {
  commentId: number;
  trackId: number;
  parentCommentId: number | null;
  content: string;
  location: number;
  isResolved: boolean;
  author: CommentUser; // 기존에 존재하는 CommentUser 재사용
  mentionedUsers: CommentUser[];
  createdAt: string;
  replies: CommentDto[]; // 대댓글 리스트 (계층 구조)
}


// 전체 응답 구조
export interface FetchCommentsResponse {
  code: string;
  message: string;
  isSuccess: boolean;
  data: {
    comments: CommentDto[];
  };
}