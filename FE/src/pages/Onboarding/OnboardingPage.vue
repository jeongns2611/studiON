<script setup lang="ts">
import logoDark from '@/assets/logo_dark.png'
import { redirectToGoogleLogin } from './api/onboarding.api'
import { ref } from 'vue'

const isTermsModalOpen = ref(false)
const isPrivacyModalOpen = ref(false)

function handleLoginClick() {
  redirectToGoogleLogin()
}
</script>

<template>
  <main class="onboarding-page min-h-screen flex flex-col overflow-x-hidden font-body-md text-body-md bg-[#131313] text-[#e5e2e1] selection:bg-[#FF3DCB]/30">
    <!-- Minimal Header for Landing Page -->
    <header class="fixed top-0 left-0 w-full z-50 bg-[#131313]/70 backdrop-blur-xl border-b border-white/10 px-4 md:px-10 h-[64px] flex items-center justify-between">
      <div class="flex items-center gap-3">
        <img
          :src="logoDark"
          alt="StudiON"
          class="h-10 w-auto"
        >
      </div>
      <div class="flex gap-4 items-center">
        <button
          @click="handleLoginClick"
          class="px-5 py-2 bg-white text-black text-sm font-bold rounded-full hover:bg-gray-200 transition-colors"
        >
          로그인
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <section class="flex-1 w-full pt-[64px] relative bg-[#131313]">
      <div class="relative min-h-[870px] w-full flex flex-col items-center justify-start pt-6 md:pt-8 px-4 md:px-10 overflow-hidden pb-32">
        <div class="relative z-10 max-w-4xl mx-auto flex flex-col items-center text-center space-y-8">
          <!-- Main Headlines -->
          <h1 class="font-display-lg text-[#e5e2e1] drop-shadow-2xl text-4xl sm:text-5xl md:text-[64px] leading-tight">
            브라우저에서 만나는<br/>
            <span class="text-transparent bg-clip-text bg-gradient-to-r from-[#FF3DCB] to-[#e3b5ff]">무한한 음악의 세계</span>
          </h1>

          <h2 class="font-headline-md text-gray-400 max-w-2xl">
            실시간으로 연결되는 우리만의 스튜디오
          </h2>
        </div>

        <!-- CTA Container -->
        <div class="relative z-10 flex flex-col items-center mt-12 mb-12">
          <button class="gsi-material-button" @click="handleLoginClick">
            <div class="gsi-material-button-state"></div>
            <div class="gsi-material-button-content-wrapper">
              <div class="gsi-material-button-icon">
                <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" xmlns:xlink="http://www.w3.org/1999/xlink" style="display: block;">
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"></path>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"></path>
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
                  <path fill="none" d="M0 0h48v48H0z"></path>
                </svg>
              </div>
              <span class="gsi-material-button-contents">Google 계정으로 로그인</span>
              <span style="display: none;">Google 계정으로 로그인</span>
            </div>
          </button>
          <div class="mt-8 font-body-md text-gray-300 text-center flex flex-col gap-2.5 bg-[#1c1b1b]/60 border border-white/10 p-6 rounded-2xl backdrop-blur-md max-w-lg shadow-2xl">
            <div class="flex items-center justify-center gap-2 mb-2">
              <span class="material-symbols-outlined text-[20px] text-[#00dce6]" style="font-variation-settings: 'FILL' 1;">info</span>
              <span class="text-white font-bold text-[15px]">베타 서비스 이용 안내</span>
            </div>
            <p class="text-[14px] leading-relaxed tracking-wide">계정 당 총 <strong class="text-[#00dce6]">100MB</strong>, 1회 최대 <strong class="text-[#00dce6]">50MB</strong>의 오디오를 업로드할 수 있습니다.</p>
            <p class="text-[14px] leading-relaxed tracking-wide">프로젝트당 최대 <strong class="text-[#00dce6]">6명</strong>까지 동시 참여가 가능합니다.</p>
            <p class="text-[13px] leading-relaxed text-gray-500 mt-1">현재 베타 버전은 오디오 트랙 생성 위주로 지원되며, 더 많은 기능이 곧 추가될 예정입니다.</p>
          </div>
        </div>

        <!-- Video Showcase -->
        <div class="relative z-10 w-full max-w-4xl mx-auto mb-16 md:mb-24">
          <div class="relative rounded-[2rem] overflow-hidden border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] bg-black">
            <div class="absolute inset-0 bg-gradient-to-t from-[#131313] via-transparent to-transparent opacity-50 z-10 pointer-events-none"></div>
            <video autoplay class="w-full aspect-video object-cover opacity-90" loop muted playsinline>
              <source src="/back1.mp4" type="video/mp4"/>
            </video>
          </div>
        </div>

        <!-- Features Bento Grid -->
        <div class="w-full max-w-[1200px] mx-auto pt-8 pb-12 md:pt-16 md:pb-16 relative z-10">
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            <!-- Feature 1 -->
            <div class="group relative bg-[#1c1b1b]/60 backdrop-blur-xl border border-white/5 rounded-[1.5rem] p-8 overflow-hidden hover:bg-[#2a2a2a]/80 hover:border-[#FF3DCB]/30 transition-all duration-500 ease-out flex flex-col items-start min-h-[320px]">
              <div class="absolute -inset-1 bg-gradient-to-br from-[#FF3DCB]/10 to-transparent opacity-0 group-hover:opacity-100 blur-2xl transition-opacity duration-500 rounded-[1.5rem] pointer-events-none"></div>
              <div class="relative z-10 w-14 h-14 rounded-2xl bg-[#131313] border border-white/10 flex items-center justify-center mb-8 shadow-[0_0_15px_rgba(0,0,0,0.5)] group-hover:border-[#FF3DCB]/50 group-hover:shadow-[0_0_20px_rgba(255,61,203,0.2)] transition-all duration-300">
                <span class="material-symbols-outlined text-[28px] text-[#FF3DCB]" style="font-variation-settings: 'FILL' 1;">groups</span>
              </div>
              <div class="relative z-10 flex-1">
                <h3 class="font-headline-md text-[20px] text-[#e5e2e1] mb-3">실시간 동시 편집</h3>
                <p class="font-body-md text-[15px] text-gray-400 leading-relaxed">
                  팀원들과 함께 동일한 프로젝트에 접속하여 딜레이 없는 실시간 공동 작업을 경험하세요. 커서 위치부터 파라미터 변경까지
                  즉각적으로 동기화됩니다.
                </p>
              </div>
            </div>

            <!-- Feature 2 -->
            <div class="group relative bg-[#1c1b1b]/60 backdrop-blur-xl border border-white/5 rounded-[1.5rem] p-8 overflow-hidden hover:bg-[#2a2a2a]/80 hover:border-[#00dce6]/30 transition-all duration-500 ease-out flex flex-col items-start min-h-[320px]">
              <div class="absolute -inset-1 bg-gradient-to-br from-[#00dce6]/10 to-transparent opacity-0 group-hover:opacity-100 blur-2xl transition-opacity duration-500 rounded-[1.5rem] pointer-events-none"></div>
              <div class="relative z-10 w-14 h-14 rounded-2xl bg-[#131313] border border-white/10 flex items-center justify-center mb-8 shadow-[0_0_15px_rgba(0,0,0,0.5)] group-hover:border-[#00dce6]/50 group-hover:shadow-[0_0_20px_rgba(0,220,230,0.2)] transition-all duration-300">
                <span class="material-symbols-outlined text-[28px] text-[#00dce6]" style="font-variation-settings: 'FILL' 1;">cloud_sync</span>
              </div>
              <div class="relative z-10 flex-1">
                <h3 class="font-headline-md text-[20px] text-[#e5e2e1] mb-3">별도 설치 없는 웹 기반 DAW</h3>
                <p class="font-body-md text-[15px] text-gray-400 leading-relaxed">
                  무거운 설치 파일이나 복잡한 설정은 그만. 
                  인터넷이 연결된 브라우저만 있다면 어디서나 스튜디오 환경이 펼쳐집니다.
                </p>
              </div>
            </div>

            <!-- Feature 3 -->
            <div class="group relative bg-[#1c1b1b]/60 backdrop-blur-xl border border-white/5 rounded-[1.5rem] p-8 overflow-hidden hover:bg-[#2a2a2a]/80 hover:border-[#e3b5ff]/30 transition-all duration-500 ease-out flex flex-col items-start min-h-[320px]">
              <div class="absolute -inset-1 bg-gradient-to-br from-[#e3b5ff]/10 to-transparent opacity-0 group-hover:opacity-100 blur-2xl transition-opacity duration-500 rounded-[1.5rem] pointer-events-none"></div>
              <div class="relative z-10 w-14 h-14 rounded-2xl bg-[#131313] border border-white/10 flex items-center justify-center mb-8 shadow-[0_0_15px_rgba(0,0,0,0.5)] group-hover:border-[#e3b5ff]/50 group-hover:shadow-[0_0_20px_rgba(227,181,255,0.2)] transition-all duration-300">
                <span class="material-symbols-outlined text-[28px] text-[#e3b5ff]" style="font-variation-settings: 'FILL' 1;">tune</span>
              </div>
              <div class="relative z-10 flex-1">
                <h3 class="font-headline-md text-[20px] text-[#e5e2e1] mb-3"> AI 분석을 통한 오디오 믹싱</h3>
                <p class="font-body-md text-[15px] text-gray-400 leading-relaxed">
                  AI가 주파수 충돌 구간을 자동으로 분석하여 작곡에만 집중할 수 있도록 도와드립니다.
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- How It Works Section -->
        <div class="w-full max-w-[1200px] mx-auto pt-16 pb-16 relative z-10 border-t border-white/5">
          <div class="text-center mb-16">
            <h2 class="font-display-lg text-3xl sm:text-4xl md:text-5xl text-white mb-4">How It Works</h2>
            <p class="font-body-lg text-gray-400">단 3단계면 충분합니다. 웹 브라우저에서 바로 시작하세요.</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div class="relative flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-[#1c1b1b] border border-white/10 flex items-center justify-center text-2xl font-bold text-[#FF3DCB] mb-6 shadow-[0_0_15px_rgba(255,61,203,0.2)]">1</div>
              <h3 class="text-xl font-bold text-white mb-3">트랙 추가</h3>
              <p class="text-gray-400 leading-relaxed text-[15px]">오디오 파일(.mp3, .wav)을 빈 타임라인에 드래그 앤 드롭하여 간편하게 새 트랙을 추가해 보세요.</p>
            </div>
            <!-- 연결선 (Desktop) -->
            <div class="hidden md:block absolute top-8 left-[16.66%] w-[33.33%] h-px bg-gradient-to-r from-transparent via-[#FF3DCB]/30 to-transparent"></div>
            
            <div class="relative flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-[#1c1b1b] border border-white/10 flex items-center justify-center text-2xl font-bold text-[#00dce6] mb-6 shadow-[0_0_15px_rgba(0,220,230,0.2)]">2</div>
              <h3 class="text-xl font-bold text-white mb-3">AI 분석 & 협업</h3>
              <p class="text-gray-400 leading-relaxed text-[15px]">AI의 도움으로 믹싱 오류를 잡고, 초대된 팀원들과 코멘트를 주고받으며 실시간으로 프로젝트를 발전시키세요.</p>
            </div>
            <!-- 연결선 (Desktop) -->
            <div class="hidden md:block absolute top-8 left-[50%] w-[33.33%] h-px bg-gradient-to-r from-transparent via-[#00dce6]/30 to-transparent"></div>

            <div class="relative flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-[#1c1b1b] border border-white/10 flex items-center justify-center text-2xl font-bold text-[#e3b5ff] mb-6 shadow-[0_0_15px_rgba(227,181,255,0.2)]">3</div>
              <h3 class="text-xl font-bold text-white mb-3">고품질 추출</h3>
              <p class="text-gray-400 leading-relaxed text-[15px]">작업이 완료된 프로젝트는 언제든지 클릭 한 번으로 무손실 고음질 오디오 파일로 내보낼 수 있습니다.</p>
            </div>
          </div>
        </div>



        <!-- FAQ Section -->
        <div class="w-full max-w-[800px] mx-auto pt-16 pb-24 relative z-10 border-t border-white/5">
          <div class="text-center mb-12">
            <h2 class="font-display-lg text-3xl sm:text-4xl md:text-5xl text-white mb-4">FAQ</h2>
            <p class="font-body-lg text-gray-400">자주 묻는 질문들을 모아봤습니다.</p>
          </div>
          <div class="flex flex-col gap-4">
            <details class="group bg-[#1c1b1b]/40 border border-white/10 rounded-xl overflow-hidden [&_summary::-webkit-details-marker]:hidden">
              <summary class="flex items-center justify-between cursor-pointer p-6 text-white font-bold text-lg hover:bg-white/5 transition-colors">
                <span>정말 무료로 사용할 수 있나요?</span>
                <span class="transition group-open:rotate-180 text-gray-400">
                  <svg fill="none" height="24" shape-rendering="geometricPrecision" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" viewBox="0 0 24 24" width="24"><path d="M6 9l6 6 6-6"></path></svg>
                </span>
              </summary>
              <div class="px-6 pb-6 text-gray-400 text-[15px] leading-relaxed">
                네, 현재 베타 서비스 기간 동안 실시간 동시 편집, AI 믹싱 분석 등 모든 핵심 기능을 100% 무료로 이용하실 수 있습니다. (계정당 최대 100MB 업로드 지원)
              </div>
            </details>
            <details class="group bg-[#1c1b1b]/40 border border-white/10 rounded-xl overflow-hidden [&_summary::-webkit-details-marker]:hidden">
              <summary class="flex items-center justify-between cursor-pointer p-6 text-white font-bold text-lg hover:bg-white/5 transition-colors">
                <span>어떤 오디오 포맷을 지원하나요?</span>
                <span class="transition group-open:rotate-180 text-gray-400">
                  <svg fill="none" height="24" shape-rendering="geometricPrecision" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" viewBox="0 0 24 24" width="24"><path d="M6 9l6 6 6-6"></path></svg>
                </span>
              </summary>
              <div class="px-6 pb-6 text-gray-400 text-[15px] leading-relaxed">
                현재 가장 널리 쓰이는 MP3 파일과 무손실 WAV 파일을 업로드하고 다운로드(Export)할 수 있습니다. 1회 업로드 용량은 최대 50MB로 제한됩니다.
              </div>
            </details>
            <details class="group bg-[#1c1b1b]/40 border border-white/10 rounded-xl overflow-hidden [&_summary::-webkit-details-marker]:hidden">
              <summary class="flex items-center justify-between cursor-pointer p-6 text-white font-bold text-lg hover:bg-white/5 transition-colors">
                <span>AI 분석은 정확히 어떤 역할을 하나요?</span>
                <span class="transition group-open:rotate-180 text-gray-400">
                  <svg fill="none" height="24" shape-rendering="geometricPrecision" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" viewBox="0 0 24 24" width="24"><path d="M6 9l6 6 6-6"></path></svg>
                </span>
              </summary>
              <div class="px-6 pb-6 text-gray-400 text-[15px] leading-relaxed">
                인간의 귀로는 구분하기 힘든 주파수 마스킹(소리 겹침 현상), 위상 캔슬링(소리 상쇄 현상) 등의 믹싱 오류를 AI가 빠르게 스캔합니다. 나아가 스마트 EQ를 통해 보컬이나 특정 악기를 선명하게 살리는 자동 보정(Revision) 기능을 제공합니다.
              </div>
            </details>
          </div>
        </div>

        <!-- Bottom CTA Section -->
        <div class="w-full relative z-10 py-24 bg-gradient-to-b from-[#131313] to-[#FF3DCB]/10 border-t border-white/5 text-center px-4">
          <h2 class="font-display-lg text-3xl sm:text-4xl md:text-6xl text-white mb-6">당신만의 스튜디오를<br/>지금 열어보세요.</h2>
          <p class="font-body-lg text-gray-300 mb-10 max-w-2xl mx-auto">더 이상 무거운 프로그램을 설치하지 마세요. 구글 계정만 있다면 10초 만에 브라우저에서 음악 작업을 시작할 수 있습니다.</p>
          <div class="flex justify-center">
            <button class="gsi-material-button scale-110 shadow-2xl" @click="handleLoginClick">
              <div class="gsi-material-button-state"></div>
              <div class="gsi-material-button-content-wrapper">
                <div class="gsi-material-button-icon">
                  <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" xmlns:xlink="http://www.w3.org/1999/xlink" style="display: block;">
                    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"></path>
                    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"></path>
                    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path>
                    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
                    <path fill="none" d="M0 0h48v48H0z"></path>
                  </svg>
                </div>
                <span class="gsi-material-button-contents">Google 계정으로 시작하기</span>
                <span style="display: none;">Google 계정으로 시작하기</span>
              </div>
            </button>
          </div>
        </div>

        <!-- Footer -->
        <footer class="w-full relative z-10 py-10 border-t border-white/10 bg-[#0a0a0a] text-center md:text-left">
          <div class="max-w-[1200px] mx-auto px-4 md:px-10 flex flex-col md:flex-row justify-between items-center gap-6">
            <div class="flex items-center gap-2">
              <img :src="logoDark" alt="StudiON" class="h-6 w-auto opacity-70">
              <span class="text-gray-500 text-sm">© 2026 StudiON. All rights reserved.</span>
            </div>
            <div class="flex gap-6 text-sm text-gray-500">
              <button @click="isTermsModalOpen = true" class="hover:text-white transition-colors">이용약관</button>
              <button @click="isPrivacyModalOpen = true" class="hover:text-white transition-colors">개인정보처리방침</button>
              <a href="https://docs.google.com/forms/d/e/1FAIpQLSd8j0DchO_6TY9FC7Ya_LCfH-mxJQUTAqcV4Gu-UXptyRPsuA/viewform?usp=publish-editor" target="_blank" rel="noopener noreferrer" class="hover:text-white transition-colors">문의하기</a>
            </div>
          </div>
        </footer>

      </div>
    </section>

    <!-- Terms Modal -->
    <div v-if="isTermsModalOpen" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" @click.self="isTermsModalOpen = false">
      <div class="bg-[#1c1b1b] border border-white/10 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        <div class="flex items-center justify-between p-6 border-b border-white/10">
          <h2 class="text-xl font-bold text-white">이용약관</h2>
          <button @click="isTermsModalOpen = false" class="text-gray-400 hover:text-white transition-colors">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6 overflow-y-auto custom-scrollbar text-gray-300 text-[15px] leading-relaxed space-y-4">
          <p><strong>제 1 조 (목적)</strong><br>본 약관은 StudiON(이하 "회사")이 제공하는 웹 기반 오디오 편집 서비스(이하 "서비스")의 이용과 관련하여 회사와 회원 간의 권리, 의무 및 책임사항 등을 규정함을 목적으로 합니다.</p>
          <p><strong>제 2 조 (약관의 효력 및 변경)</strong><br>1. 본 약관은 서비스를 이용하고자 하는 모든 회원에 대하여 그 효력을 발생합니다.<br>2. 회사는 약관의 규제에 관한 법률 등 관련 법령을 위배하지 않는 범위에서 본 약관을 개정할 수 있습니다.</p>
          <p><strong>제 3 조 (서비스의 제공 및 변경)</strong><br>1. 서비스는 현재 베타 버전으로 제공되며, 일부 기능이 제한되거나 예고 없이 변경될 수 있습니다.<br>2. 회사는 서비스의 안정적인 제공을 위해 최선을 다하며, 정기 점검 등으로 서비스가 일시 중단될 수 있습니다.</p>
          <p><strong>제 4 조 (사용자의 의무)</strong><br>1. 회원은 서비스 이용 시 타인의 저작권을 침해하는 오디오 데이터를 업로드해서는 안 됩니다.<br>2. 불법적이거나 타인에게 불쾌감을 주는 콘텐츠의 업로드 및 공유는 엄격히 금지됩니다.</p>
        </div>
        <div class="p-6 border-t border-white/10 flex justify-end">
          <button @click="isTermsModalOpen = false" class="px-5 py-2 bg-white text-black font-bold rounded-lg hover:bg-gray-200 transition">확인</button>
        </div>
      </div>
    </div>

    <!-- Privacy Policy Modal -->
    <div v-if="isPrivacyModalOpen" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" @click.self="isPrivacyModalOpen = false">
      <div class="bg-[#1c1b1b] border border-white/10 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        <div class="flex items-center justify-between p-6 border-b border-white/10">
          <h2 class="text-xl font-bold text-white">개인정보처리방침</h2>
          <button @click="isPrivacyModalOpen = false" class="text-gray-400 hover:text-white transition-colors">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6 overflow-y-auto custom-scrollbar text-gray-300 text-[15px] leading-relaxed space-y-4">
          <p><strong>1. 수집하는 개인정보 항목</strong><br>회사는 회원가입, 고객상담, 각종 서비스의 제공을 위해 아래와 같은 최소한의 개인정보를 수집하고 있습니다.<br>- 필수항목: 이메일 주소, 이름(또는 닉네임), 프로필 이미지 (소셜 로그인 시 제공받는 정보)</p>
          <p><strong>2. 개인정보의 수집 및 이용 목적</strong><br>회사는 수집한 개인정보를 다음의 목적을 위해 활용합니다.<br>- 서비스 제공에 관한 계약 이행 및 콘텐츠 제공<br>- 회원 관리, 본인 확인, 불량 회원의 부정 이용 방지</p>
          <p><strong>3. 개인정보의 보유 및 이용기간</strong><br>원칙적으로, 개인정보 수집 및 이용 목적이 달성된 후에는 해당 정보를 지체 없이 파기합니다. 단, 관계법령의 규정에 의하여 보존할 필요가 있는 경우 회사는 법령에서 정한 일정한 기간 동안 회원정보를 보관합니다.</p>
          <p><strong>4. 업로드된 오디오 데이터</strong><br>사용자가 업로드한 오디오 데이터는 서비스 제공(실시간 동기화, AI 분석 등)의 목적으로만 활용되며, 사용자의 명시적인 동의 없이 외부로 유출되거나 상업적인 용도로 사용되지 않습니다.</p>
        </div>
        <div class="p-6 border-t border-white/10 flex justify-end">
          <button @click="isPrivacyModalOpen = false" class="px-5 py-2 bg-white text-black font-bold rounded-lg hover:bg-gray-200 transition">확인</button>
        </div>
      </div>
    </div>

  </main>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:ital,wght@0,100..900;1,100..900&family=JetBrains+Mono:ital,wght@0,100..800;1,100..800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap');

.onboarding-page {
  font-family: 'Hanken Grotesk', sans-serif;
}
.font-display-lg {
  font-family: 'Hanken Grotesk', sans-serif;
  font-size: 48px;
  line-height: 1.1;
  letter-spacing: -0.02em;
  font-weight: 800;
}
.font-headline-md {
  font-family: 'Hanken Grotesk', sans-serif;
  font-size: 24px;
  line-height: 1.3;
  font-weight: 700;
}
.font-body-lg {
  font-family: 'Hanken Grotesk', sans-serif;
  font-size: 18px;
  line-height: 1.6;
  font-weight: 400;
}
.font-body-md {
  font-family: 'Hanken Grotesk', sans-serif;
  font-size: 16px;
  line-height: 1.6;
  font-weight: 400;
}
.font-label-sm {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.0;
  letter-spacing: 0.05em;
  font-weight: 500;
}

@media (max-width: 768px) {
  .font-display-lg {
    font-size: 32px;
    line-height: 1.2;
  }
}

/* Google Sign-In Button Material Design Styles */
.gsi-material-button {
  -moz-user-select: none;
  -webkit-user-select: none;
  -ms-user-select: none;
  -webkit-appearance: none;
  background-color: WHITE;
  background-image: none;
  border: 1px solid #747775;
  -webkit-border-radius: 4px;
  border-radius: 4px;
  -webkit-box-sizing: border-box;
  box-sizing: border-box;
  color: #1f1f1f;
  cursor: pointer;
  font-family: 'Roboto', arial, sans-serif;
  font-size: 14px;
  height: 40px;
  letter-spacing: 0.25px;
  outline: none;
  overflow: hidden;
  padding: 0 12px;
  position: relative;
  text-align: center;
  -webkit-transition: background-color .218s, border-color .218s, box-shadow .218s;
  transition: background-color .218s, border-color .218s, box-shadow .218s;
  vertical-align: middle;
  white-space: nowrap;
  width: auto;
  max-width: 400px;
  min-width: min-content;
}

.gsi-material-button .gsi-material-button-icon {
  height: 20px;
  margin-right: 12px;
  min-width: 20px;
  width: 20px;
}

.gsi-material-button .gsi-material-button-content-wrapper {
  -webkit-align-items: center;
  align-items: center;
  display: flex;
  -webkit-flex-direction: row;
  flex-direction: row;
  -webkit-flex-wrap: nowrap;
  flex-wrap: nowrap;
  height: 100%;
  justify-content: space-between;
  position: relative;
  width: 100%;
}

.gsi-material-button .gsi-material-button-contents {
  -webkit-flex-grow: 1;
  flex-grow: 1;
  font-family: 'Roboto', arial, sans-serif;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
}

.gsi-material-button .gsi-material-button-state {
  -webkit-transition: opacity .218s;
  transition: opacity .218s;
  bottom: 0;
  left: 0;
  opacity: 0;
  position: absolute;
  right: 0;
  top: 0;
}

.gsi-material-button:disabled {
  cursor: default;
  background-color: #ffffff61;
  border-color: #1f1f1f1f;
}

.gsi-material-button:disabled .gsi-material-button-contents {
  opacity: 38%;
}

.gsi-material-button:disabled .gsi-material-button-icon {
  opacity: 38%;
}

.gsi-material-button:not(:disabled):active .gsi-material-button-state, 
.gsi-material-button:not(:disabled):focus .gsi-material-button-state {
  background-color: #303030;
  opacity: 12%;
}

.gsi-material-button:not(:disabled):hover {
  -webkit-box-shadow: 0 1px 2px 0 rgba(60, 64, 67, .30), 0 1px 3px 1px rgba(60, 64, 67, .15);
  box-shadow: 0 1px 2px 0 rgba(60, 64, 67, .30), 0 1px 3px 1px rgba(60, 64, 67, .15);
}

.gsi-material-button:not(:disabled):hover .gsi-material-button-state {
  background-color: #303030;
  opacity: 8%;
}
</style>