//프로젝트 지침, 서버 켜기, 리액트 코드 읽기등
//Vite 환경 설정을 도와주는 도구를 가져오고 코드 자동완성을 띄워줌
import { defineConfig } from 'vite'
//vite에게 뷰언어 번역 능력 부여
import vue from '@vitejs/plugin-vue'
//tailwind css 번역 능력 부여
import tailwindcss from '@tailwindcss/vite'
//npm다운 말고 노드제이에스 원래 부품을 가져오기
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
//지침을 내보낸다.
export default defineConfig({
  //바이트에 장착하는 플러그인
  plugins: [vue(), tailwindcss()],
  define: {
    global: 'globalThis',
  },
  resolve: {
    //dirname 설정파일이 있는 FE폴더, @는 src폴더를 가리킴
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  // TODO: 백엔드에 CORS 설정 추가되면 지워도 됨
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  
  // 빌드 시 청크 용량 경고 해결 및 최적화 설정
  build: {
    chunkSizeWarningLimit: 1000, // 경고 기준을 500KB -> 1000KB로 상향 (Tone.js 등 무거운 라이브러리 감안)
    rollupOptions: {
      output: {
        // 용량이 큰 라이브러리들을 별도의 js 파일로 쪼개어(Code Splitting) 브라우저 캐싱 최적화
        manualChunks(id) {
          if (id.includes('node_modules/tone')) {
            return 'tone';
          }
          if (id.includes('node_modules/vue') || id.includes('node_modules/pinia') || id.includes('node_modules/vue-router')) {
            return 'vue-vendor';
          }
          if (id.includes('node_modules/lucide-vue-next') || id.includes('node_modules/wavesurfer.js')) {
            return 'ui-vendor';
          }
        }
      }
    }
  }


})


