export type ProjectSocketEvent =
  | 'PROJECT_JOIN'
  | 'PROJECT_LEFT'
  | 'PROJECT_RENAME'
  | 'PROJECT_ONLINE_USERS'
  | 'USER_JOINED_PROJECT'
  | 'USER_LEFT_PROJECT'
  | 'PROJECT_RENAMED'
  | 'TRACK_ADD'
  | 'TRACK_DELETE'
  | 'TRACK_RENAME'
  | 'TRACK_MUTE_CHANGE'
  | 'TRACK_SOLO_CHANGE'
  | 'TRACK_VOLUME_CHANGE'
  | 'TRACK_PAN_CHANGE'
  | 'CLIP_LOCK'
  | 'CLIP_CREATE'
  | 'CLIP_MOVE'
  | 'CLIP_RESIZE'
  | 'CLIP_DELETE'
  | 'CLIP_CUT'
  | 'CLIP_PASTE'
  | 'CLIP_DUPLICATE'
  | 'CLIP_SPLIT'
  | 'ERROR'

export interface WsMessage<T = unknown> {
  event: ProjectSocketEvent | string
  payload: T
}

export interface OnlineUser {
  userId: number
  nickname: string
  profileImageUrl: string | null
}

export interface ProjectOnlineUsersPayload {
  projectId: number
  users: OnlineUser[]
}

export interface UserJoinedProjectPayload {
  projectId: number
  user: OnlineUser
}

export interface UserLeftProjectPayload {
  userId: number
}

export interface ProjectRenamedPayload {
  name: string
}