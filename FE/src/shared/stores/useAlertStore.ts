import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AlertType = 'info' | 'success' | 'warning' | 'error'

export const useAlertStore = defineStore('alert', () => {
  const isOpen = ref(false)
  const message = ref('')
  const alertType = ref<AlertType>('info')

  function showAlert(msg: string, type: AlertType = 'info') {
    message.value = msg
    alertType.value = type
    isOpen.value = true
  }

  function closeAlert() {
    isOpen.value = false
    // 애니메이션이 끝난 후 메시지 초기화
    setTimeout(() => {
      message.value = ''
    }, 300)
  }

  return {
    isOpen,
    message,
    alertType,
    showAlert,
    closeAlert,
  }
})
