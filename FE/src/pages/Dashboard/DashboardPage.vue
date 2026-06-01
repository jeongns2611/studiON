<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { AudioLines, Disc3, Mic, Play } from 'lucide-vue-next'
import DashboardHeader from './components/DashboardHeader.vue'
import ProjectGuideOverlay from '@/pages/Project/components/ProjectGuideOverlay.vue'
import { fetchProjects } from '@/pages/Project/api/project.api'
import { buildCreateProjectPayload, createProject, projectApi } from '@/pages/Project/api/project.api'
import type { ProjectListItem, CreateProjectResponse, ProjectId } from '@/pages/Project/types/project.types'
import { trackEvent } from '@/shared/utils/analytics'

const router = useRouter()
const projects = ref<ProjectListItem[]>([])
const isLoading = ref(false)
const errorMessage = ref('')
const isCreating = ref(false)
const showFeedbackModal = ref(false)
const neverShowAgain = ref(false)
const searchQuery = ref('')
const currentTotalSizeBytes = ref(0)
const maxTotalSizeBytes = ref(50 * 1024 * 1024)

// Guide Overlay State
const isGuideOpen = ref(false)

const dashboardGuideSteps = [
  {
    selector: '[data-guide="invite-code"]',
    title: '초대 코드 입력',
    description: '팀원에게 전달받은 6자리 초대 코드를 입력하여 기존 프로젝트에 참여할 수 있습니다.',
  },
  {
    selector: '[data-guide="create-project"]',
    title: '새 프로젝트 생성',
    description: '새로운 빈 캔버스를 열고 당신만의 음악 작업을 시작해 보세요. 생성된 프로젝트에서 팀원들을 초대할 수 있습니다.',
  },
  {
    selector: '[data-guide="usage-bar"]',
    title: '내 사용량 확인',
    description: '현재 계정에서 사용 중인 총 오디오 용량을 확인합니다. 최대 50MB(임시)까지 업로드할 수 있습니다.',
  },
  {
    selector: '[data-guide="search-project"]',
    title: '프로젝트 검색',
    description: '프로젝트 이름으로 검색하여 원하는 작업물을 빠르게 찾아볼 수 있습니다.',
  },
  {
    selector: '[data-guide="feedback-button"]',
    title: '피드백 남기기',
    description: '베타 서비스 이용 중 불편한 점이나 제안할 내용이 있다면 언제든 설문조사에 참여해 주세요!',
  },
]

// Slider State
const currentSlide = ref(0)
const slideInterval = ref<number | undefined>(undefined)

const slides: { id: number; image?: string; title: string; desc: string; bg?: string }[] = [
  { id: 2, image: '/Open.png', title: 'StudiON 전격 오픈!', desc: 'AI 기반의 충돌 분석과 실시간 협업을 경험해 보세요!' },
  { id: 1, image: '/banner.png', title: '피드백 참여하기', desc: 'StudiON에서 피드백을 남기고 커피쿠폰 받자!' },
]

function nextSlide() {
  currentSlide.value = (currentSlide.value + 1) % slides.length
}

function prevSlide() {
  currentSlide.value = (currentSlide.value - 1 + slides.length) % slides.length
}

function setSlide(index: number) {
  currentSlide.value = index
}

function handleSlideClick(id: number) {
  if (id === 1) {
    showFeedbackModal.value = true
  } else if (id === 2) {
    window.location.reload()
  } else if (id === 3) {
    window.open('https://www.ssafy.com/ksp/servlet/swp.content.controller.SwpContentServlet?p_process=select-content-view&p_menu_cd=M0307&p_content_cd=C0307', '_blank')
  }
}

const filteredProjects = computed(() => {
  if (!searchQuery.value) return projects.value
  const query = searchQuery.value.toLowerCase()
  return projects.value.filter(project => 
    project.projectName.toLowerCase().includes(query)
  )
})

const existingProjectNames = computed(() =>
  projects.value.map(project => project.projectName),
)

function getProjectIcon(index: number) {
  const icons = [Disc3, AudioLines, Mic]
  return icons[index % icons.length]
}

function hideFeedbackModal(neverShowAgain: boolean) {
  if (neverShowAgain) {
    localStorage.setItem('hideFeedbackModal', 'true')
  }
  showFeedbackModal.value = false
}

function formatPlayTime(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '0:00'
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function formatAudioSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB'
  const mb = bytes / (1024 * 1024)
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

function formatEditedText(lastUpdateAt: string): string {
  const updatedAt = new Date(lastUpdateAt)
  if (Number.isNaN(updatedAt.getTime())) return '최근 수정'
  const diffMs = Date.now() - updatedAt.getTime()
  const diffMinutes = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMinutes < 60) return `${Math.max(diffMinutes, 1)}분 전 수정`
  if (diffHours < 24) return `${diffHours}시간 전 수정`
  return `${diffDays}일 전 수정`
}

function extractProjectId(response: CreateProjectResponse): ProjectId | null {
  return response.data.project.projectId ?? null
}

function extractProjectName(response: CreateProjectResponse): string {
  return response.data?.project?.name ?? '새 프로젝트'
}

async function handleCreateProjectClick() {
  isCreating.value = true
  errorMessage.value = ''

  try {
    const payload = buildCreateProjectPayload(existingProjectNames.value)
    const response = await createProject(payload)
    const projectId = extractProjectId(response)
    const projectName = extractProjectName(response)

    if (!projectId) {
      throw new Error('생성된 프로젝트 ID를 확인할 수 없습니다.')
    }

    trackEvent('project_created', { project_id: projectId })
    await projectApi.saveProjectSnapshot(projectId)

    await router.push({
      path: `/project/${projectId}`,
      query: { name: projectName },
    })
  }
  catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : '프로젝트 생성 중 오류가 발생했습니다.'
  }
  finally {
    isCreating.value = false
  }
}

async function loadProjects() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await fetchProjects()
    projects.value = response.data?.projects ?? []
    currentTotalSizeBytes.value = response.data?.currentTotalSizeBytes ?? 0
    maxTotalSizeBytes.value = response.data?.maxTotalSizeBytes ?? (50 * 1024 * 1024)
  }
  catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : '프로젝트 목록을 불러오는 중 오류가 발생했습니다.'
  }
  finally {
    isLoading.value = false
  }
}



// ...
onMounted(() => {
  void loadProjects()
  if (localStorage.getItem('hideFeedbackModal') !== 'true') {
    showFeedbackModal.value = true
  }
  slideInterval.value = window.setInterval(nextSlide, 5000)
})

onUnmounted(() => {
  if (slideInterval.value) {
    clearInterval(slideInterval.value)
  }
})
</script>

<template>
  <main class="min-h-[125vh] bg-[#131313] text-[#e5e2e1] flex flex-col font-body-md text-body-md" style="zoom: 0.8;">
    <DashboardHeader :existing-project-names="existingProjectNames" @openFeedback="showFeedbackModal = true" @start-guide="isGuideOpen = true" />

    <div class="flex-1 flex flex-col p-4 sm:p-6 md:p-10 mx-auto w-full sm:w-[95%] lg:w-[80%] max-w-[1600px] gap-6 md:gap-8">
      
      <!-- Top Banner: Carousel -->
      <div class="w-full h-[200px] md:h-[360px] lg:h-[440px] rounded-3xl overflow-hidden relative shadow-[0_0_30px_rgba(255,61,203,0.05)] border border-white/5 bg-[#131313] group">
        <!-- Slides Container -->
        <div 
          class="flex transition-transform duration-700 ease-[cubic-bezier(0.25,1,0.5,1)] h-full w-full"
          :style="`transform: translateX(-${currentSlide * 100}%)`"
        >
          <div v-for="slide in slides" :key="slide.id" @click="handleSlideClick(slide.id)" class="w-full h-full shrink-0 relative flex-none cursor-pointer">
            <img v-if="slide.image" :src="slide.image" :alt="slide.title" class="w-full h-full object-fill opacity-80 transition-opacity hover:opacity-100" />
            <div v-else :class="slide.bg" class="w-full h-full flex items-center justify-center">
              <span class="material-symbols-outlined text-6xl text-white/50" style="font-variation-settings: 'FILL' 1;">music_note</span>
            </div>
            <div class="absolute inset-0 bg-gradient-to-t from-[#131313] via-[#131313]/30 to-transparent"></div>
            <div class="absolute bottom-0 left-0 w-full p-8 md:px-12">
              <h3 class="text-2xl md:text-3xl font-bold text-[#e5e2e1] mb-2 drop-shadow-md">{{ slide.title }}</h3>
              <p class="text-[#e5bcc5] text-[15px] md:text-[16px] leading-relaxed drop-shadow-md">{{ slide.desc }}</p>
            </div>
          </div>
        </div>
        
        <!-- Dots -->
        <div class="absolute bottom-6 left-0 w-full flex justify-center gap-2 z-10">
          <button 
            v-for="(_, idx) in slides" 
            :key="idx"
            @click.stop="setSlide(idx)"
            class="w-2 h-2 rounded-full transition-all duration-300"
            :class="currentSlide === idx ? 'w-6 bg-[#FF3DCB]' : 'bg-white/30 hover:bg-white/50'"
          ></button>
        </div>

        <!-- Left/Right Controls -->
        <button 
          @click.stop="prevSlide" 
          class="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/40 hover:bg-[#FF3DCB] flex items-center justify-center text-white transition-all z-20 group opacity-0 group-hover:opacity-100 focus:opacity-100"
        >
          <span class="material-symbols-outlined group-hover:text-[#65002e]">chevron_left</span>
        </button>
        <button 
          @click.stop="nextSlide" 
          class="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/40 hover:bg-[#FF3DCB] flex items-center justify-center text-white transition-all z-20 group opacity-0 group-hover:opacity-100 focus:opacity-100"
        >
          <span class="material-symbols-outlined group-hover:text-[#65002e]">chevron_right</span>
        </button>
      </div>

      <!-- Main: Projects -->
      <section class="flex flex-col gap-6 md:gap-8 mt-4">
        <!-- Header & Actions -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 pb-6 border-b border-white/10">
          <div>
            <h1 class="font-headline-md text-[28px] md:text-[32px] font-bold text-[#e5e2e1] flex items-center gap-3">
              내 프로젝트
              <span class="text-[18px] font-normal text-[#e5bcc5]/80 bg-[#2a2a2a] px-3 py-0.5 rounded-full">{{ projects.length }}</span>
            </h1>
            <p class="font-body-lg text-[16px] text-[#e5bcc5] mt-2 opacity-80">최근 작업 중인 트랙들을 확인하고 관리하세요.</p>
            
            <!-- 오디오 사용량 프로그레스 바 -->
            <div data-guide="usage-bar" class="mt-4 flex items-center gap-4 max-w-md w-full bg-[#1c1b1b] p-3.5 rounded-2xl border border-white/10 shadow-lg">
              <span class="text-[14px] text-white uppercase tracking-wider shrink-0 font-bold flex items-center gap-2">
                내 사용량
              </span>
              <div class="flex-1 h-3 bg-[#2a2a2a] rounded-full overflow-hidden relative shadow-inner">
                <div class="absolute inset-y-0 left-0 bg-gradient-to-r from-[#FF3DCB] to-[#00dce6] transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(255,61,203,0.5)]" :style="{ width: `${Math.min(100, (currentTotalSizeBytes / maxTotalSizeBytes) * 100)}%` }"></div>
              </div>
              <span class="text-[14px] font-bold shrink-0 font-mono" :class="currentTotalSizeBytes > maxTotalSizeBytes * 0.9 ? 'text-red-400' : 'text-[#00dce6]'">
                {{ formatAudioSize(currentTotalSizeBytes) }} <span class="text-white/50 text-[12px] font-normal">/ {{ formatAudioSize(maxTotalSizeBytes) }}</span>
              </span>
            </div>
          </div>

          <div class="flex flex-col sm:flex-row justify-end items-center gap-4 w-full md:w-auto">
            <div data-guide="search-project" class="relative w-full sm:w-64">
              <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#e5bcc5]" style="font-variation-settings: 'FILL' 0;">search</span>
              <input v-model="searchQuery" class="w-full bg-[#1c1b1b] border border-white/10 rounded-full focus:border-[#FF3DCB] text-[#e5e2e1] text-[14px] pl-10 pr-4 py-2.5 outline-none transition-colors placeholder:text-[#e5bcc5]/50" placeholder="프로젝트 검색..." type="text" />
            </div>
            <button
              data-guide="create-project"
              @click="handleCreateProjectClick"
              :disabled="isCreating"
              class="bg-[#FF3DCB] text-[#65002e] text-[15px] font-bold px-6 py-2.5 rounded-full hover:shadow-[0_0_15px_rgba(255,61,203,0.4)] hover:bg-[#ff4a8d] transition-all flex items-center justify-center gap-2 w-full sm:w-auto whitespace-nowrap disabled:opacity-50">
              <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">add</span>
              {{ isCreating ? '생성 중...' : '새 프로젝트 생성' }}
            </button>
          </div>
        </div>

      <!-- Status Messages -->
      <div v-if="isLoading" class="text-center py-20 text-[#e5bcc5]">
        프로젝트 불러오는 중...
      </div>
      <div v-else-if="errorMessage" class="text-center py-20 text-red-400">
        {{ errorMessage }}
      </div>
      
      <!-- Empty State -->
      <div v-else-if="projects.length === 0" class="gap-6 flex flex-col items-center">
        <div class="col-span-full flex flex-col items-center justify-center py-24 px-6 text-center animate-in fade-in duration-700">
          <div class="relative mb-8 w-32 h-32 shrink-0">
            <div class="absolute inset-0 bg-[#FF3DCB]/20 blur-3xl rounded-full"></div>
            <div class="relative w-full h-full bg-[#2a2a2a]/50 backdrop-blur-xl border border-white/10 rounded-full flex items-center justify-center hover:shadow-[0_0_15px_rgba(255,61,203,0.4)] aspect-square">
              <span class="material-symbols-outlined text-6xl text-[#FF3DCB]" style="font-variation-settings: 'FILL' 0;">library_music</span>
              <div class="absolute -bottom-1 -right-1 bg-[#FF3DCB] text-[#65002e] rounded-full w-9 h-9 flex items-center justify-center border-4 border-[#131313]">
                <span class="material-symbols-outlined text-xl" style="font-variation-settings: 'FILL' 1;">add</span>
              </div>
            </div>
          </div>
          <h2 class="font-headline-md text-2xl md:text-3xl text-[#e5e2e1] mb-3">아직 생성된 프로젝트가 없습니다.</h2>
          <p class="font-body-lg text-[#e5bcc5] max-w-md mb-10">StudiON에서 당신의 첫 번째 음악 작업을 시작해보세요.</p>
          <button
            @click="handleCreateProjectClick"
            :disabled="isCreating"
            class="bg-[#FF3DCB] text-[#65002e] font-body-md text-[16px] font-bold px-10 py-4 rounded-[0.125rem] hover:shadow-[0_0_15px_rgba(255,61,203,0.4)] hover:bg-[#ff4a8d] transition-all flex items-center justify-center gap-2">
            <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">add</span>
            {{ isCreating ? '생성 중...' : '새 프로젝트 생성' }}
          </button>
        </div>
      </div>

      <!-- Project Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <RouterLink
          v-for="(project, idx) in filteredProjects"
          :key="project.projectId"
          :to="{
            path: `/project/${project.projectId}`,
            query: { name: project.projectName },
          }"
          class="block group cursor-pointer"
        >
          <article class="bg-[#2a2a2a]/70 backdrop-blur-[12px] border border-white/10 rounded-xl overflow-hidden hover:border-[#FF3DCB]/50 transition-colors flex flex-col h-full relative">
            <div class="relative h-40 bg-[#262022] w-full flex items-center justify-center overflow-hidden">
              <component
                :is="getProjectIcon(idx)"
                class="w-16 h-16 text-[#FF3DCB] group-hover:scale-110 transition-transform duration-300 z-10"
              />
            </div>
            
            <div class="p-5 flex-1 flex flex-col justify-between gap-4">
              <div class="flex justify-between items-start gap-4">
                <div class="flex-1 min-w-0">
                  <h2 class="font-headline-md text-[18px] font-bold text-[#e5e2e1] truncate">{{ project.projectName }}</h2>
                  <p class="font-body-md text-[12px] text-[#e5bcc5] mt-1">{{ formatEditedText(project.lastUpdateAt) }}</p>
                </div>
                <!-- Profiles -->
                <div class="flex -space-x-2 shrink-0">
                  <img
                    v-for="member in project.members.slice(0, 3)"
                    :key="member.userId"
                    :src="member.profileImgUrl"
                    class="h-7 w-7 rounded-full border-2 border-[#2a2a2a] object-cover"
                  >
                </div>
              </div>
              
              <div class="bg-[#201f1f]/50 rounded-lg p-3.5 font-mono text-[14px] text-[#e5bcc5] flex flex-col gap-2.5">
                <div class="flex justify-between items-center">
                  <span class="uppercase tracking-widest text-[11px]">Length:</span>
                  <span class="text-[#00dce6] font-medium">{{ formatPlayTime(project.totalPlayTime) }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="uppercase tracking-widest text-[11px]">Size:</span>
                  <span class="text-[#00dce6] font-medium">{{ formatAudioSize(project.totalAudioSize) }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="uppercase tracking-widest text-[11px]">Bars:</span>
                  <span class="text-[#00dce6] font-medium">{{ project.totalBarCount }}</span>
                </div>
              </div>
            </div>
          </article>
        </RouterLink>

        <!-- Add New Project Card -->
        <article
          @click="handleCreateProjectClick"
          class="bg-[#1c1b1b]/50 border border-white/5 border-dashed rounded-xl overflow-hidden hover:border-[#FF3DCB]/50 hover:bg-[#1c1b1b]/80 transition-all cursor-pointer flex flex-col items-center justify-center h-full min-h-[320px] group"
        >
          <div class="w-16 h-16 rounded-full bg-[#201f1f] flex items-center justify-center group-hover:scale-110 transition-transform group-hover:shadow-[0_0_15px_rgba(255,61,203,0.4)] mb-4">
            <span class="material-symbols-outlined text-[#FF3DCB] text-3xl" style="font-variation-settings: 'FILL' 0;">add</span>
          </div>
          <h3 class="font-headline-md text-[18px] font-bold text-[#e5e2e1]">새 프로젝트</h3>
          <p class="font-body-md text-[12px] text-[#e5bcc5] mt-2 text-center px-4">빈 캔버스에서 새로운 음악을 시작하세요.</p>
        </article>
      </div>
      </section>
    </div>

    <!-- Feedback Modal -->
    <div v-if="showFeedbackModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div class="bg-[#1c1b1b] border border-white/10 rounded-2xl w-full max-w-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden relative">
        <!-- 상단 배너 이미지 -->
        <div class="w-full aspect-video overflow-hidden bg-[#262022] flex items-center justify-center border-b border-white/10">
          <img src="/dash.png" alt="Dashboard Feedback Preview" class="w-full h-full object-cover object-[center_90%] opacity-90" />
        </div>
        <div class="p-8 pt-6 flex flex-col items-center text-center">
          <div class="w-16 h-16 rounded-full bg-gradient-to-tr from-[#FF3DCB] to-[#e3b5ff] flex items-center justify-center mb-5 shadow-[0_0_20px_rgba(255,61,203,0.3)] -mt-14 border-4 border-[#1c1b1b] relative z-10">
            <span class="material-symbols-outlined text-[32px] text-[#65002e]" style="font-variation-settings: 'FILL' 1;">campaign</span>
          </div>
          <h3 class="text-2xl font-bold text-[#e5e2e1] mb-2">피드백 남기기</h3>
          <p class="text-[#e5bcc5] text-[15px] mb-8 leading-relaxed">
            StudiON을 사용해 보시고 소중한 의견을 들려주세요. 여러분의 피드백이 더 나은 서비스를 만듭니다.
          </p>
          <a
            href="https://docs.google.com/forms/d/e/1FAIpQLSd8j0DchO_6TY9FC7Ya_LCfH-mxJQUTAqcV4Gu-UXptyRPsuA/viewform?usp=publish-editor"
            target="_blank"
            rel="noopener noreferrer"
            @click="hideFeedbackModal(true)"
            class="w-full bg-gradient-to-r from-[#FF3DCB] to-[#e3b5ff] text-[#65002e] font-bold text-[16px] py-3.5 rounded-xl hover:shadow-[0_0_20px_rgba(255,61,203,0.4)] transition-all mb-4 block"
          >
            설문조사 참여하기
          </a>
          <div class="flex items-center justify-between w-full mt-2">
            <label class="flex items-center gap-2 cursor-pointer text-[#e5bcc5] hover:text-[#e5e2e1] transition-colors text-[14px]">
              <input type="checkbox" v-model="neverShowAgain" class="w-4 h-4 rounded bg-[#131313] border-white/20 text-[#FF3DCB] focus:ring-[#FF3DCB] focus:ring-offset-0" />
              <span>다시 보지 않기</span>
            </label>
            <button @click="hideFeedbackModal(neverShowAgain)" class="text-[#e5bcc5] hover:text-[#e5e2e1] text-[14px] transition-colors font-medium">
              닫기
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Guide Overlay -->
    <ProjectGuideOverlay
      :steps="dashboardGuideSteps"
      :open="isGuideOpen"
      @close="isGuideOpen = false"
    />
  </main>
</template>