<script setup lang="ts">
import { ref, computed } from 'vue';
import { useTrackStore } from '../store/useTrackStore';
import { Play, Pause, Square, Sparkles, ChevronDown, Copy, Scissors, ClipboardPaste, CopyPlus, Split, Trash2, ListPlus, MessageSquarePlus, Upload, Repeat } from 'lucide-vue-next';
import * as Tone from 'tone';
import { trackEvent } from '@/shared/utils/analytics'
import SpinnerGradient from '@/shared/ui/spinner/SpinnerGradient.vue'

const trackStore = useTrackStore();

// 1. 마디(Bar)와 박자(Beat) 변환 로직 (반응성 제거 - DOM 직접 업데이트)
const playheadBar = ref('01');
const playheadBeat = ref('1');
const totalBars = computed(() => String(trackStore.displayBarCount).padStart(2, '0'));

// 2. 키(Key) 관련 상태 및 배열
const isKeyPickerOpen = ref(false);

const NATURAL_NOTES = ["C", "D", "E", "F", "G", "A", "B"];
const SHARP_FLAT_ROW = ["Db", "Eb", null, "F#", "Ab", "Bb"];

const displayKey = computed(() => {
  const note = trackStore.projectInfo.rootNote || 'C';
  const mode = (trackStore.projectInfo.mode || 'MAJOR').toLowerCase() === 'minor' ? 'min' : 'Maj';
  return `${note} ${mode}`;
});

const handleKeyChange = (newNote: string, newMode: string) => {
  trackStore.changeKey(newNote, newMode);
  isKeyPickerOpen.value = false;
};

// 3. 재생 제어 함수
const handlePlay = async() => {
  await Tone.start();
  if(!trackStore.isPlaying) trackStore.togglePlay();
};
const handlePause = async() => {
  if(trackStore.isPlaying) trackStore.togglePlay();
};
const handleStop = () => {
  trackStore.stopPlay();
};

// 4. ai 분석 버튼 상태 전달
const props = defineProps<{
  aiAnalyzing: boolean
  projectId: number | string
  hasActionableAiIssues?: boolean
}>()

const emit = defineEmits<{
  (e: 'run-ai-analysis'): void
  (e: 'apply-all-ai-issues'): void
  (e: 'action-copy'): void
  (e: 'action-cut'): void
  (e: 'action-paste'): void
  (e: 'action-duplicate'): void
  (e: 'action-split'): void
  (e: 'action-delete'): void
  (e: 'action-add-track'): void
  (e: 'action-upload'): void
}>()

function handleRunAiAnalysisClick() {
  trackEvent('ai_analysis_clicked', {
    project_id: Number(props.projectId),
  })

  emit('run-ai-analysis')
}

const hasSelectedTrack = computed(() => trackStore.selectedTrackId !== null);
const hasSelectedClip = computed(() => trackStore.selectedClip !== null);
const hasClipboard = computed(() => trackStore.clipboardClip !== null);
const hasAnySelection = computed(() => trackStore.selectedTrackId !== null || trackStore.selectedClip !== null);

// 5. BPM 편집 관련 상태
const isBpmEditing = ref(false);
const bpmInputValue = ref('');
const bpmInputRef = ref<HTMLInputElement | null>(null);

const startBpmEdit = () => {
  isBpmEditing.value = true;
  bpmInputValue.value = String(trackStore.bpm);
  // DOM 갱신 후 input에 포커스
  setTimeout(() => bpmInputRef.value?.select(), 0);
};

const confirmBpmEdit = () => {
  const newBpm = Number(bpmInputValue.value);
  if (!isNaN(newBpm) && newBpm >= 30 && newBpm <= 300) {
    trackStore.changeBpm(newBpm);
  }
  isBpmEditing.value = false;
};

const cancelBpmEdit = () => {
  isBpmEditing.value = false;
};

// 6. 박자(Time Signature) 편집 관련 상태
const isTimeSigPickerOpen = ref(false);

// 허용되는 박자 조합 (10가지)
const TIME_SIG_OPTIONS: { numerator: number; denominator: number; label: string }[] = [
  { numerator: 2, denominator: 4, label: '2/4' },
  { numerator: 3, denominator: 4, label: '3/4' },
  { numerator: 4, denominator: 4, label: '4/4' },
  { numerator: 5, denominator: 4, label: '5/4' },
  { numerator: 6, denominator: 4, label: '6/4' },
  { numerator: 7, denominator: 4, label: '7/4' },
  { numerator: 3, denominator: 8, label: '3/8' },
  { numerator: 6, denominator: 8, label: '6/8' },
  { numerator: 9, denominator: 8, label: '9/8' },
  { numerator: 12, denominator: 8, label: '12/8' },
];

const handleTimeSigChange = (numerator: number, denominator: number) => {
  trackStore.changeTimeSignature(numerator, denominator);
  isTimeSigPickerOpen.value = false;
};

const isCurrentTimeSig = (numerator: number, denominator: number) => {
  return trackStore.projectInfo.timeSigNumerator === numerator
    && trackStore.projectInfo.timeSigDenominator === denominator;
};
</script>

<template>
  <!--조작 담당의 네비게이션 역할-->
  <!--select none은 마우스로 선택할 수 없게 함-->
  <nav 
    aria-label="트랜스포트 컨트롤 및 프로젝트 정보 바"
    class="relative h-12 w-full border-b border-border bg-[#151515] select-none overflow-x-auto [&::-webkit-scrollbar]:hidden"
  >
    <div class="flex h-full items-center justify-between w-full min-w-[1000px] px-4 md:px-6 gap-4">

  <!--:arial-label 재생바가 움직일때마다 읽는 정보가 실시간으로 변경 font mono는 숫자 바뀔떄 UI 흔들림을 방지-->
      <!-- 1. 좌측 영역: Playhead + Tools -->
      <div class="flex items-center gap-6">
        <!-- Playhead -->
        <div class="flex items-center">
          <div 
            id="playhead-position-display"
            :aria-label="`현재 재생 위치: ${playheadBar}마디 ${playheadBeat}박자, 전체 ${totalBars}마디`"
            class="flex h-8 items-center gap-2 rounded border border-white/5 bg-white/5 px-3 font-mono text-sm"
          >
            <span class="hidden xl:inline text-[10px] uppercase tracking-wider text-muted-foreground" aria-hidden="true">마디</span>
            <span class="tabular-nums text-primary drop-shadow-[0_0_6px_hsl(var(--primary)/0.6)]">
              <span id="playhead-bar-text">{{ playheadBar }}</span><span class="text-muted-foreground">.</span><span id="playhead-beat-text">{{ playheadBeat }}</span>
            </span>
            <span class="text-muted-foreground" aria-hidden="true">/</span>
            <span class="tabular-nums text-muted-foreground">{{ totalBars }}</span>
          </div>
        </div>

        <!-- 단축키 도구 모음 -->
        <div class="flex items-center gap-1 shrink-0" role="group" aria-label="클립 및 트랙 도구">
      <!-- 트랙 이벤트: 트랙이 선택되어야 활성화 -->
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="오디오 업로드" 
        :disabled="!hasSelectedTrack"
        @click="emit('action-upload')"
      >
        <Upload class="h-4 w-4" />
      </button>

      <!-- 클립 이벤트: 클립이 선택되어야 활성화 -->
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="복사 (Ctrl/Cmd + C)" 
        :disabled="!hasSelectedClip"
        @click="emit('action-copy')"
      >
        <Copy class="h-4 w-4" />
      </button>
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="잘라내기 (Ctrl/Cmd + X)" 
        :disabled="!hasSelectedClip"
        @click="emit('action-cut')"
      >
        <Scissors class="h-4 w-4" />
      </button>
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="붙여넣기 (Ctrl/Cmd + V)" 
        :disabled="!hasClipboard"
        @click="emit('action-paste')"
      >
        <ClipboardPaste class="h-4 w-4" />
      </button>
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="분할 (Ctrl/Cmd + E)" 
        :disabled="!hasSelectedClip"
        @click="emit('action-split')"
      >
        <Split class="h-4 w-4" />
      </button>
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="복제 (Ctrl/Cmd + D)" 
        :disabled="!hasSelectedClip"
        @click="emit('action-duplicate')"
      >
        <CopyPlus class="h-4 w-4" />
      </button>

      <!-- 공통: 코멘트는 항상 활성화 -->
      <button 
        :class="[
          'inline-flex h-8 w-8 items-center justify-center rounded transition',
          trackStore.isCommentMode 
            ? 'bg-primary/20 text-primary border border-primary/50 shadow-[0_0_8px_hsl(var(--primary)/0.4)]' 
            : 'text-muted-foreground hover:bg-white/10 hover:text-white'
        ]"
        title="코멘트 모드 (C)" 
        data-guide="comment"
        @click="trackStore.toggleCommentMode()"
      >
        <MessageSquarePlus class="h-4 w-4" />
      </button>

      <!-- 공통: 삭제는 트랙이나 클립 중 하나라도 선택되면 활성화 -->
      <button 
        class="inline-flex h-8 w-8 items-center justify-center rounded transition text-muted-foreground hover:bg-white/10 hover:text-red-400 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed" 
        title="삭제 (Del/Backspace)" 
        :disabled="!hasAnySelection"
        @click="emit('action-delete')"
      >
        <Trash2 class="h-4 w-4" />
        </button>
      </div>
    </div>

    <!-- 2. 중앙 영역: 재생 컨트롤 -->
    <div class="flex items-center justify-center gap-1.5 shrink-0" role="group" aria-label="재생 컨트롤" data-guide="play-controls">
      <button 
        :aria-label="trackStore.isPlaying ? '일시정지' : '재생 시작'"
        :class="[
          'grid h-8 w-10 place-items-center rounded border transition',
          trackStore.isPlaying 
            ? 'border-primary bg-primary/20 text-primary shadow-[0_0_8px_hsl(var(--primary)/0.6)]' 
            : 'border-white/10 bg-white/5 text-white hover:bg-white/10 active:scale-95'
        ]"
        @click="trackStore.isPlaying ? handlePause() : handlePlay()"
      >
        <Pause v-if="trackStore.isPlaying" class="h-3.5 w-3.5 fill-current" aria-hidden="true" />
        <Play v-else class="h-3.5 w-3.5 fill-current" aria-hidden="true" />
      </button>

      <button 
        aria-label="정지 및 재생바 초기화" 
        class="grid h-8 w-10 place-items-center rounded border border-white/10 bg-white/5 text-white transition hover:bg-white/10 active:scale-95" 
        @click="handleStop"
      >
        <Square class="h-3.5 w-3.5 fill-current" aria-hidden="true" />
      </button>

      <!-- 메트로놈 토글 버튼 (M 단축키) -->
      <button 
        aria-label="메트로놈 토글"
        :class="[
          'grid h-8 w-10 place-items-center rounded border transition',
          trackStore.isMetronomeActive 
            ? 'border-primary bg-primary/20 text-primary shadow-[0_0_8px_hsl(var(--primary)/0.6)]' 
            : 'border-white/10 bg-white/5 text-white hover:bg-white/10 active:scale-95'
        ]"
        @click="trackStore.isMetronomeActive = !trackStore.isMetronomeActive"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">
          <!-- 메트로놈 외형 (사다리꼴) -->
          <path d="M6 20h12L15 4H9Z"/>
          <!-- 똑딱거리는 시침 막대기 (하단 중앙에서 좌측 상단으로 뻗음) -->
          <path d="M12 20 8 6"/>
          <!-- 시침에 달린 무게추 -->
          <circle cx="9.4" cy="11.5" r="1.5"/>
        </svg>
      </button>

      <!-- 구간 반복(Loop) 토글 버튼 (L 단축키) -->
      <button 
        aria-label="구간 반복 토글"
        :class="[
          'grid h-8 w-10 place-items-center rounded border transition',
          trackStore.isLoopActive 
            ? 'border-pink-500 bg-pink-500/20 text-pink-400 shadow-[0_0_8px_rgba(236,72,153,0.6)]' 
            : 'border-white/10 bg-white/5 text-white hover:bg-white/10 active:scale-95'
        ]"
        @click="trackStore.isLoopActive = !trackStore.isLoopActive"
      >
        <Repeat class="h-4 w-4" aria-hidden="true" />
      </button>
    </div>

    <!-- 3. 우측 영역: AI 분석 및 곡 정보 -->
    <div class="flex items-center gap-2 shrink-0">
  <!-- 일괄적용하기 버튼 -->
  <button
    v-if="props.hasActionableAiIssues"
    type="button"
    aria-label="AI 이슈 일괄 적용"
    class="group relative inline-flex h-10 items-center justify-center overflow-hidden rounded-full p-px transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
    @click="emit('apply-all-ai-issues')"
  >
    <!-- gradient border -->
    <span
      class="absolute inset-0 rounded-full bg-[linear-gradient(135deg,#8B5CF6,#3B82F6,#06B6D4,#22C55E,#F59E0B,#EC4899)] opacity-80 transition duration-300 group-hover:opacity-100"
    />

    <!-- inner button (white background) -->
    <span
      class="relative z-10 inline-flex h-full items-center gap-1.5 rounded-full bg-white px-4 text-[11px] font-semibold tracking-wider text-gray-800 transition duration-300 group-hover:bg-gray-50"
    >
      <Sparkles class="h-3.5 w-3.5 text-violet-500" aria-hidden="true" />
      일괄적용하기
    </span>
  </button>

  <button
    type="button"
    aria-label="AI 믹스 분석 실행"
    :disabled="props.aiAnalyzing"
    data-guide="ai-analysis"
    class="group relative inline-flex h-10 items-center justify-center overflow-hidden rounded-full p-px transition-all duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-50"
    @click="handleRunAiAnalysisClick"
  >
    <!-- gradient border -->
    <span
      class="absolute inset-0 rounded-full bg-[linear-gradient(135deg,#8B5CF6,#3B82F6,#06B6D4,#22C55E,#F59E0B,#EC4899)] opacity-80 transition duration-300 group-hover:opacity-100 group-hover:blur-[0.5px]"
    />

    <!-- hover glow -->
    <span
      class="absolute -inset-3 rounded-full bg-[radial-gradient(circle,#8B5CF655,transparent_62%)] opacity-0 blur-xl transition duration-300 group-hover:opacity-100"
    />

    <!-- inner button -->
    <span
      class="relative z-10 inline-flex h-full items-center gap-2 rounded-full bg-[#171717]/95 p-2 xl:px-4 text-[11px] font-semibold tracking-[0.18em] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)] transition duration-300 group-hover:bg-[#202020]/95"
    >
      <span
        class="grid h-5 w-5 place-items-center rounded-full bg-[conic-gradient(from_180deg,#8B5CF6,#38BDF8,#22C55E,#F59E0B,#EC4899,#8B5CF6)]"
      >
        <span class="absolute h-4 w-4 rounded-full bg-[#171717]" />

        <SpinnerGradient
          v-if="props.aiAnalyzing"
          class="relative z-10"
          size-class="h-3 w-3"
        />
        <Sparkles
          v-else
          class="relative z-10 h-3 w-3 text-white"
          aria-hidden="true"
        />
      </span>

      <span
        v-if="false"
        class="bg-[linear-gradient(90deg,#DDD6FE,#93C5FD,#67E8F9,#F9A8D4)] bg-clip-text text-transparent"
      >
        {{ props.aiAnalyzing ? '분석 중' : 'AI 분석' }}
      </span>
      <span class="hidden xl:inline bg-[linear-gradient(90deg,#DDD6FE,#93C5FD,#67E8F9,#F9A8D4)] bg-clip-text text-transparent">
        {{ props.aiAnalyzing ? '분석 중' : 'AI 분석' }}
      </span>
    </span>
  </button>


      <!-- BPM 표시/편집 영역 -->
      <div 
        :aria-label="`현재 템포: ${trackStore.bpm} BPM. 클릭하여 변경`"
        class="flex h-8 items-center gap-2 rounded border px-2.5 cursor-pointer transition-colors"
        :class="isBpmEditing 
          ? 'border-primary bg-primary/10' 
          : 'border-white/5 bg-white/5 hover:border-white/20 hover:bg-white/10'"
        @click="!isBpmEditing && startBpmEdit()"
      >
        <span class="hidden xl:inline font-mono text-[9px] uppercase tracking-widest text-muted-foreground" aria-hidden="true">BPM</span>
        <!-- 편집 모드 -->
        <input
          v-if="isBpmEditing"
          ref="bpmInputRef"
          v-model="bpmInputValue"
          type="number"
          min="30"
          max="300"
          step="1"
          class="w-14 bg-transparent font-display text-xs tracking-wider text-white tabular-nums outline-none border-none appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden"
          @keydown.enter="confirmBpmEdit"
          @keydown.escape="cancelBpmEdit"
          @blur="confirmBpmEdit"
        />
        <!-- 표시 모드 -->
        <span v-else class="font-display text-xs tracking-wider text-white tabular-nums">
          {{ trackStore.bpm.toFixed(0) }}
        </span>
      </div>

      <!-- 박자(Time Signature) 피커 -->
      <div class="relative">
        <button 
          :aria-label="`현재 박자: ${trackStore.projectInfo.timeSigNumerator}/${trackStore.projectInfo.timeSigDenominator}. 클릭하여 변경`"
          :aria-expanded="isTimeSigPickerOpen"
          :class="[
            'flex h-8 items-center gap-2 rounded border px-2.5 transition-colors',
            isTimeSigPickerOpen
              ? 'border-primary bg-primary/10'
              : 'border-white/5 bg-white/5 hover:border-white/20 hover:bg-white/10 cursor-pointer'
          ]"
          @click="isTimeSigPickerOpen = !isTimeSigPickerOpen"
        >
          <span class="hidden xl:inline font-mono text-[9px] uppercase tracking-widest text-muted-foreground" aria-hidden="true">박자</span>
          <div class="flex items-center gap-1 font-display text-xs tracking-wider text-white tabular-nums">
            <span>{{ trackStore.projectInfo.timeSigNumerator }}</span>
            <span class="text-muted-foreground">/</span>
            <span>{{ trackStore.projectInfo.timeSigDenominator }}</span>
          </div>
          <ChevronDown class="h-3 w-3 text-muted-foreground transition-transform" :class="isTimeSigPickerOpen ? 'rotate-180' : ''" aria-hidden="true" />
        </button>

        <!-- 박자 선택 팝업 -->
        <div 
          v-if="isTimeSigPickerOpen" 
          role="dialog"
          aria-label="박자 선택창"
          class="absolute right-0 top-full mt-2 z-50 min-w-[200px] rounded-md border border-border bg-[#1c1c1c] p-4 shadow-xl shadow-black/50"
        >
          <!-- 바깥 클릭 시 닫기 -->
          <div class="fixed inset-0 z-[-1]" @click="isTimeSigPickerOpen = false"></div>

          <!-- /4 박자 그룹 -->
          <div class="mb-3">
            <span class="mb-1.5 block font-mono text-[9px] uppercase tracking-widest text-muted-foreground">4분음표 기준</span>
            <div class="grid grid-cols-3 gap-1.5" role="group" aria-label="4분음표 기준 박자 선택">
              <button
                v-for="opt in TIME_SIG_OPTIONS.filter(o => o.denominator === 4)"
                :key="opt.label"
                :aria-label="`박자 ${opt.label} 적용`"
                :aria-pressed="isCurrentTimeSig(opt.numerator, opt.denominator)"
                :class="[
                  'flex h-9 items-center justify-center rounded-md border font-display text-sm tracking-wider transition-colors',
                  isCurrentTimeSig(opt.numerator, opt.denominator)
                    ? 'border-primary bg-primary/10 text-primary shadow-[0_0_10px_hsl(var(--primary)/0.4)]'
                    : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
                ]"
                @click="handleTimeSigChange(opt.numerator, opt.denominator)"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>

          <!-- /8 박자 그룹 -->
          <div>
            <span class="mb-1.5 block font-mono text-[9px] uppercase tracking-widest text-muted-foreground">8분음표 기준</span>
            <div class="grid grid-cols-3 gap-1.5" role="group" aria-label="8분음표 기준 박자 선택">
              <button
                v-for="opt in TIME_SIG_OPTIONS.filter(o => o.denominator === 8)"
                :key="opt.label"
                :aria-label="`박자 ${opt.label} 적용`"
                :aria-pressed="isCurrentTimeSig(opt.numerator, opt.denominator)"
                :class="[
                  'flex h-9 items-center justify-center rounded-md border font-display text-sm tracking-wider transition-colors',
                  isCurrentTimeSig(opt.numerator, opt.denominator)
                    ? 'border-primary bg-primary/10 text-primary shadow-[0_0_10px_hsl(var(--primary)/0.4)]'
                    : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
                ]"
                @click="handleTimeSigChange(opt.numerator, opt.denominator)"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="relative">
        
        <button 
          :aria-label="`현재 키: ${displayKey}. 클릭하여 변경`"
          :aria-expanded="isKeyPickerOpen"
          :class="[
            'flex h-8 items-center gap-2 rounded border px-2.5 transition-colors',
            isKeyPickerOpen
              ? 'border-primary bg-primary/10'
              : 'border-white/5 bg-white/5 hover:border-white/20 hover:bg-white/10 cursor-pointer'
          ]"
          @click="isKeyPickerOpen = !isKeyPickerOpen"
        >
          <span class="hidden xl:inline font-mono text-[9px] uppercase tracking-widest text-muted-foreground" aria-hidden="true">키</span>
          <span class="font-display text-xs tracking-wider text-white">{{ displayKey }}</span>
          <ChevronDown class="h-3 w-3 text-muted-foreground transition-transform" :class="isKeyPickerOpen ? 'rotate-180' : ''" aria-hidden="true" />
        </button>
        <!--현재키를 변경하는 버튼이 true일 때만 div 팝업창을 화면에 출력한다 v-if-->
        <!--role="dialog" -> 키 및 스케일 선택창 역할 부여 aria-expanded="isKeyPickerOpen" 버튼과 연동하여 확장 여부 알려줌-->
        <div 
          v-if="isKeyPickerOpen" 
          role="dialog"
          aria-label="키 및 스케일 선택창"
          class="absolute right-0 top-full mt-2 z-50 min-w-[280px] rounded-md border border-border bg-[#1c1c1c] p-5 shadow-xl shadow-black/50"
        >
        <!--화면 전체를 덮는 막 fixed inset-0 z-[-1] -> -> 팝업창이 클릭되어 열려있을 때 키보드나 마우스로 팝업창 밖을 클릭하면 팝업창이 닫히게 하는 기능-->
          <div class="fixed inset-0 z-[-1]" @click="isKeyPickerOpen = false"></div>

          <div class="mb-4 flex gap-2" role="group" aria-label="음계 모드 선택">
            <button
              v-for="mode in ['MAJOR', 'MINOR']" 
              :key="mode"
              :aria-label="mode === 'MAJOR' ? '장조(Major) 적용' : '단조(Minor) 적용'"
              :aria-pressed="trackStore.projectInfo.mode === mode"
              :class="[
                'flex h-10 flex-1 items-center justify-center rounded-md border font-display text-sm tracking-wider transition-colors',
                trackStore.projectInfo.mode === mode
                  ? 'border-primary bg-primary/10 text-primary shadow-[0_0_12px_hsl(var(--primary)/0.4)]'
                  : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
              ]"
              @click="handleKeyChange(trackStore.projectInfo.rootNote, mode)"
            >
              {{ mode === 'MAJOR' ? 'Major' : 'Minor' }}
            </button>
          </div>

          <div class="mb-1.5 grid grid-cols-7 gap-1.5" role="group" aria-label="반음계 선택">
            <!--Sharp_flat_row 검은 건반 배열-->
            <!--null은 빈칸 피아노 건반 모양-->
            <template v-for="(note, i) in SHARP_FLAT_ROW" :key="i">
              <div v-if="note === null" aria-hidden="true" class="translate-x-[calc(50%+0.1875rem)]"></div>
              <button
                v-else
                :aria-label="`으뜸음 ${note} 적용`"
                :aria-pressed="trackStore.projectInfo.rootNote === note"
                :class="[
                  'translate-x-[calc(50%+0.1875rem)] flex h-8 items-center justify-center rounded-md border font-display text-sm transition-colors',
                  trackStore.projectInfo.rootNote === note
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
                ]"
                @click="handleKeyChange(note, trackStore.projectInfo.mode)"
              >
                {{ note.charAt(0) }}<sup class="text-[10px]" aria-hidden="true">{{ note.charAt(1) }}</sup>
              </button>
            </template>
          </div>

          <div class="grid grid-cols-7 gap-1.5" role="group" aria-label="자연음계 선택">
           <!--반복문사용, 배열 안에 있는 요소를 하나씩 꺼내서 반복적으로 버튼을 만든다. 반복할 요소는 NATURAL_NOTES-->
           <!-- 현재 스토어의 mode 값과 버튼의 mode 값이 일치하면 불이 켜진다. -> v-for에 바인딩된 렝이 현재 스토어의 값과 같다면 해당하는 버튼이 불이 켜진다. v-bind:aria-pressed-->
            <button
              v-for="note in NATURAL_NOTES" 
              :key="note"
              :aria-label="`으뜸음 ${note} 적용`"
              :aria-pressed="trackStore.projectInfo.rootNote === note"
              :class="[
                'flex h-10 items-center justify-center rounded-md border font-display text-sm transition-colors',
                trackStore.projectInfo.rootNote === note
                  ? 'border-primary bg-primary/10 text-primary shadow-[0_0_10px_hsl(var(--primary)/0.4)]'
                  : 'border-border bg-secondary/40 text-foreground hover:border-primary/60'
              ]"
              @click="handleKeyChange(note, trackStore.projectInfo.mode)"
            >
              {{ note }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
  </nav>
</template>

<style scoped>
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
</style>
