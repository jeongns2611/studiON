import { onUnmounted, ref, watch, type WatchStopHandle } from 'vue'
import { useTrackStore } from '../store/useTrackStore'
import { socketService } from '@/core/services/socket.service'
import { useAuthStore } from '@/pages/Onboarding/stores/auth.store'

interface OnlineUser {
  userId: number
  nickname: string
  profileImageUrl: string | null
}

export function useProjectCollaboration(projectId: number) {
  const trackStore = useTrackStore()
  const authStore = useAuthStore()

  const onlineUsers = ref<OnlineUser[]>([])
  const projectName = ref('프로젝트')

  let tokenWatcher: WatchStopHandle | null = null
  let isProjectSocketSubscribed = false

  function syncProjectNameFromStore() {
    projectName.value = trackStore.projectInfo.name || '프로젝트'
  }

  function registerProjectSocketHandlers() {
    if (isProjectSocketSubscribed) return
    isProjectSocketSubscribed = true

    socketService.subscribe('PROJECT_ONLINE_USERS', (payload) => {
      onlineUsers.value = payload.users
    })

    socketService.subscribe('USER_JOINED_PROJECT', (payload) => {
      onlineUsers.value = [
        ...onlineUsers.value.filter(user => user.userId !== payload.user.userId),
        payload.user,
      ]
    })

    socketService.subscribe('USER_LEFT_PROJECT', (payload) => {
     // console.log('[ProjectPage] USER_LEFT_PROJECT 수신:', payload)

      onlineUsers.value = onlineUsers.value.filter(
        user => user.userId !== payload.userId,
      )
    })

    socketService.subscribe('PROJECT_RENAMED', (payload) => {
      projectName.value = payload.name
      trackStore.projectInfo.name = payload.name
    })
  }

  function connectProjectSocket() {
    if (authStore.accessToken) {
      socketService.connect(projectId)
      return
    }

    tokenWatcher = watch(
      () => authStore.accessToken,
      (newToken) => {
        if (!newToken) return

        socketService.connect(projectId)

        tokenWatcher?.()
        tokenWatcher = null
      },
    )
  }

  function disconnectProjectSocket() {
    tokenWatcher?.()
    tokenWatcher = null

    socketService.disconnect()
  }

  function handleRename(nextName: string) {
    const trimmedName = nextName.trim()

    if (!trimmedName) return
    if (trimmedName === projectName.value) return

    socketService.publish('PROJECT_RENAME', {
      name: trimmedName,
    })
  }

  onUnmounted(() => {
    disconnectProjectSocket()
  })

  return {
    onlineUsers,
    projectName,
    syncProjectNameFromStore,
    registerProjectSocketHandlers,
    connectProjectSocket,
    disconnectProjectSocket,
    handleRename,
  }
}