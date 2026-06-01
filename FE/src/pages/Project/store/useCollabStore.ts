import { defineStore } from 'pinia';
import { ref } from 'vue';
import { socketService } from '@/core/services/socket.service';

export const useCollabStore = defineStore('collab', () => {
    // 상대방들의 커서 상태 저장소 (키: 유저ID)
    const remoteCursors = ref<Record<string, { x: number, y: number, color: string, nickname: string }>>({});

    // 1. 서버에서 남의 커서 움직임 데이터가 오면 스토어 업데이트
    // 백엔드 미구현으로 임시 비활성화 (400 에러 방지)
    /*
    socketService.subscribePersistent('CURSOR_MOVE', (data) => {
        remoteCursors.value[data.userId] = {
            x: data.x,
            y: data.y,
            color: data.color || '#FF8F1A',
            nickname: data.nickname
        };
    });
    */

    // 2. 내 마우스 움직임을 서버로 전송
    let lastSendTime = 0;
    const sendMyCursor = (x: number, y: number) => {
        const now = Date.now();
        // 백엔드 미구현으로 임시 비활성화
        /*
        // 무한 전송 방지: 50ms 마다 한 번씩만 서버로 전송 (초당 20프레임)
        if (now - lastSendTime > 50) {
            socketService.publish('CURSOR_MOVE_SEND', { x, y });
            lastSendTime = now;
        }
        */
    };

    return { remoteCursors, sendMyCursor };
});