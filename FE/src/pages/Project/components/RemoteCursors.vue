<script setup lang="ts">
import { useCollabStore } from '../store/useCollabStore';

const collabStore = useCollabStore();
</script>

<template>
  <!-- 화면 전체를 덮는 투명 레이어. 클릭 통과(pointer-events-none) 필수! -->
  <div class="fixed inset-0 z-9999 pointer-events-none overflow-hidden">
    
    <!-- 스토어에 있는 남의 커서 개수만큼 반복해서 그리기 -->
    <div 
      v-for="(cursor, userId) in collabStore.remoteCursors" 
      :key="userId"
      class="absolute top-0 left-0 transition-transform duration-100 ease-linear"
      :style="{ transform: `translate(${cursor.x}px, ${cursor.y}px)` }"
    >
      <!-- 피그마 스타일 마우스 아이콘 -->
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/equiv">
        <path d="M5.65376 2.15376C5.40574 1.90574 5 2.08146 5 2.43236V21.5676C5 21.9185 5.40574 22.0943 5.65376 21.8462L11.8462 15.6538C11.9399 15.5599 12.0671 15.5074 12.2 15.5074H21.5676C21.9185 15.5074 22.0943 15.0943 21.8462 14.8462L5.65376 2.15376Z" 
              :fill="cursor.color" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
      </svg>
      
      <!-- 닉네임 이름표 -->
      <div 
        class="absolute left-4 top-4 rounded-br-lg rounded-bl-lg rounded-tr-lg px-2 py-1 text-[10px] font-bold text-white shadow-md whitespace-nowrap"
        :style="{ backgroundColor: cursor.color }"
      >
        {{ cursor.nickname }}
      </div>
    </div>

  </div>
</template>