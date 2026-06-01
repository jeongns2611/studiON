<script setup lang="ts">
import {ref, onMounted} from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/pages/Onboarding/stores/auth.store'
import GlobalAlertModal from '@/shared/components/GlobalAlertModal.vue'

const authStore = useAuthStore()
const route = useRoute()


//인증초기화 완료 여부 추적
const isAuthInitialized = ref(false);


onMounted(async () => {
  const skipSilentRefreshPaths = [
    '/onboarding',
    '/onboarding/profile-setup',
    '/auth/callback',
  ]

  if (!skipSilentRefreshPaths.includes(route.path)) {
    // 인증 초기화가 필요한 경로인 경우에만 silentRefresh 수행
    await authStore.silentRefresh()
  }
  
  // 복구가 끝나면 하위 페이지 렌더링 허용
  isAuthInitialized.value = true
})

</script>

<template>
  <RouterView v-if="isAuthInitialized" />
  <GlobalAlertModal />
</template>
