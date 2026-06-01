import { useAuthStore } from '@/pages/Onboarding/stores/auth.store'

type EventHandler = (data: any) => void;

class SocketService {


  private ws: WebSocket | null = null;
  private currentProjectId: number | null = null;
  private disconnectTimer: number | null = null;
  // 페이지 전환 시 초기화되는 임시 리스너 (컴포넌트용)
  private listeners: Map<string, EventHandler[]> = new Map();
  // 페이지 전환에도 절대 지워지지 않는 영구 보존 리스너 (Pinia 스토어용)
  private persistentListeners: Map<string, EventHandler[]> = new Map();

  connect(projectId: number) {
    if (this.disconnectTimer) {
      clearTimeout(this.disconnectTimer);
      this.disconnectTimer = null;
    }

    if (
  this.ws &&
  (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) &&
  this.currentProjectId === projectId
) {
  //console.log(`[Socket] 이미 프로젝트 ${projectId}에 연결 또는 연결 시도 중`)
  return
}

    this.currentProjectId = projectId;
    const authStore = useAuthStore();
    const token = authStore.accessToken;

    // 🌟 추가된 디버깅 및 방어 코드 🌟
    //console.log("[Socket] 현재 가져온 토큰:", token);

    if (!token) {
      //console.error("[Socket 🚨] 토큰이 없습니다! 소켓 연결을 중단합니다. (로그인 상태 확인 필요)");
      return; // 토큰이 없으면 아예 연결 시도를 하지 않고 함수 종료
    }

    // 🌟 1. baseUrl의 끝에 /ws를 빼고 순수 도메인까지만 잡습니다.
    let baseUrl = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8080';
    if (baseUrl.startsWith('http')) {
      baseUrl = baseUrl.replace('http', 'ws');
    }

    // 🌟 2. 백엔드 엔드포인트(/ws/projects/{projectId})에 정확히 맞춥니다.
    const wsUrl = `${baseUrl}/ws/projects/${projectId}?accessToken=${encodeURIComponent(token)}`
    this.ws = new WebSocket(wsUrl);

    // 연결 성공 시
    this.ws.onopen = () => {
      //console.log(`[Socket] 🟢 프로젝트 ${projectId} 순수 웹소켓 연결 성공!`);
      this.publish('PROJECT_JOIN', { projectId });
    };

    // 메시지 수신 시 (STOMP의 subscribe 역할 대체)
    this.ws.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data);

        // 백엔드가 { event: '...', payload: {...} } 형태로 보낼 경우를 대비
        const eventType = receivedData.event || receivedData.eventType;
        // payload 껍데기가 있으면 알맹이만 꺼내고, 없으면 전체를 payload로 씀
        const payload = receivedData.payload ? receivedData.payload : receivedData;

        //console.log(`[Socket 📥] 수신 [${eventType}]:`, payload);

        if (eventType) {
          // 1. 임시 리스너 실행
          if (this.listeners.has(eventType)) {
            const callbacks = this.listeners.get(eventType) || [];
            callbacks.forEach(cb => cb(payload));
          }
          // 2. 영구 리스너 실행
          if (this.persistentListeners.has(eventType)) {
            const persistentCallbacks = this.persistentListeners.get(eventType) || [];
            persistentCallbacks.forEach(cb => cb(payload));
          }
        }
      } catch (e) {
        //console.error(`[Socket 🚨] 메시지 파싱 에러:`, e);
      }
    };

    // 에러 발생 시
    this.ws.onerror = (error) => {
      //console.error('[Socket 🚨] 웹소켓 에러 발생:', error);
    };

    // 연결 종료 시
    this.ws.onclose = () => {
  //console.log('[Socket] 🔴 웹소켓 연결 해제됨')
  this.ws = null
  this.currentProjectId = null
}
  }

  // 컴포넌트에서 임시 이벤트 리스너를 등록하는 함수 (disconnect 시 지워짐)
  subscribe(eventType: string, callback: EventHandler) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType)?.push(callback);
  }

  // 스토어에서 영구 이벤트 리스너를 등록하는 함수 (절대 안 지워짐)
  subscribePersistent(eventType: string, callback: EventHandler) {
    if (!this.persistentListeners.has(eventType)) {
      this.persistentListeners.set(eventType, []);
    }
    this.persistentListeners.get(eventType)?.push(callback);
  }

  // 서버로 메시지 발신
  publish(eventType: string, payload: any) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.currentProjectId) {
      //console.warn(`[Socket ⚠️] 연결되지 않은 상태에서 전송 시도됨: ${eventType}`);

      return;
    }

    // 프론트엔드 상태 업데이트 지연(Race Condition)으로 인해 이전 프로젝트의 projectId가 전송되는 것을 방지합니다.
    let finalPayload = payload;
    if (payload && typeof payload === 'object' && 'projectId' in payload) {
      finalPayload = { ...payload, projectId: this.currentProjectId };
    }

    // 🌟 백엔드의 WsMessage 객체 구조({ event: "...", payload: {...} })에 정확히 맞춥니다!
    const message = {
      event: eventType,
      payload: finalPayload
    };

    this.ws.send(JSON.stringify(message));
    //console.log(`[Socket 📤] 발신 [${eventType}]:`, finalPayload);
  }

disconnect() {
  //console.log('[Socket] disconnect 호출됨')

  if (this.ws && this.ws.readyState === WebSocket.OPEN) {
    //console.log('[Socket] PROJECT_LEFT 전송 시도')
    this.publish('PROJECT_LEFT', {})

    if (this.disconnectTimer) {
      clearTimeout(this.disconnectTimer);
      this.disconnectTimer = null;
    }

    this.disconnectTimer = window.setTimeout(() => {
      this.ws?.close()
      this.ws = null
      this.listeners.clear()
      this.currentProjectId = null
      this.disconnectTimer = null
      //console.log('[Socket] 🔴 웹소켓 수동 연결 해제 완료')
    }, 100)

    return
  }

  //console.log('[Socket] OPEN 상태가 아니라 PROJECT_LEFT 전송 안 함', this.ws?.readyState)

  this.ws = null
  this.listeners.clear()
  this.currentProjectId = null
}
}

export const socketService = new SocketService();