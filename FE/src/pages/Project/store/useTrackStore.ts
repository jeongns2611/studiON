//API로 받아온 데이터를 가공해서 보관하는 창고
//데이터 창고 피니아
import { defineStore } from 'pinia';
//화면이 바뀌아도 자동으로 다시그리게 함 반응형
import { ref, computed, watch, nextTick } from 'vue';
//트랙과 클립의 타입
import type { TrackUIState, ClipUIState, TrackEqState, TrackEqBandState, } from '../types';
//음원 처리를 위한 lib
import * as Tone from 'tone';
import { socketService } from '../../../core/services/socket.service';
import { projectApi } from '../api/project.api'
import type { TrackEqBandSummary } from '../api/project.api'
import { getMasterLimiter } from '../api/projectLimiter.api'
import type { MasterLimiterState } from '../api/projectLimiter.api'
import axios from 'axios'
import { useAlertStore } from '@/shared/stores/useAlertStore'

//페이지 어디든 사용가능하도록 useTrackStore로 export 고유 ID는 track
export const useTrackStore = defineStore('track', () => {
    const alertStore = useAlertStore();
    // ==========================================
    // 1. 상태(State) 선언
    // ==========================================

    //오디오 객체 보관함 만들기 순수 자바스크립트 객체 보관용이기 때문에 ref를 사용하지 않는다.
    //음원 파일의 데이터를 브라우저 메모리에 올려서 타이밍에 맞춰 스피커로 재생
    // [핵심] Tone.Channel은 내부 Solo→PanVol 노드 체인에서 모노 다운믹스가 발생하여 패닝이 불가능합니다.
    // 따라서 Tone.Volume(볼륨/뮤트 전담) + Tone.Panner(패닝 전담)로 완전히 분리합니다.
    // 신호 흐름: Player → Tone.Volume → Tone.Panner → masterPanner → Destination
    const trackVolumes = new Map<number, Tone.Volume>();   // 트랙별 볼륨/뮤트 노드
    const trackPanners = new Map<number, Tone.Panner>();   // 트랙별 패닝 노드
    const clipPlayers = new Map<number, Tone.Player>(); //클립별 오디오 플레이어
    const myLockedClips = new Set<number>(); // 내가 직접 잠근(편집 중인) 클립 ID 목록
    const pendingDuplicateOriginalClipIds = new Set<number>(); // 내가 복제한 클립의 원본 ID 목록 (백엔드 강제 락 해제용)
    const cutClipsMap = new Map<number, ClipUIState>(); // 다른 사용자가 잘라내기 한 클립 임시 보관소 (붙여넣기 수신용)

    type TrackEqNode = {
        bandOrder: number
        filter: Tone.Filter
    }

    const trackEqNodes = new Map<number, TrackEqNode[]>()
    const trackAnalyzers = new Map<number, Tone.FFT>()

    const MAX_EQ_BANDS = 5

    const createDefaultTrackEq = (): TrackEqState => ({
        bands: [],
    })

    function mapEqTypeToCode(eqType: TrackEqBandSummary['eqType']) {
        switch (eqType) {
            case 'LOW_SHELF':
                return 2
            case 'HIGH_SHELF':
                return 3
            case 'BELL':
            default:
                return 1
        }
    }

    function mapSourceTypeToCode(sourceType: TrackEqBandSummary['sourceType']) {
        switch (sourceType) {
            case 'SYSTEM':
                return 2
            case 'AI_CONFIRM':
                return 3
            case 'AI_APPLIED':
                return 4
            case 'USER_MANUAL':
            default:
                return 1
        }
    }

    function mapTrackEqBandSummaryToState(band: TrackEqBandSummary): TrackEqBandState {
        return {
            id: band.trackEqBandId,
            bandOrder: band.bandOrder,
            eqTypeCode: mapEqTypeToCode(band.eqType),
            frequencyHz: band.frequencyHz,
            q: band.q,
            gainDeltaDb: band.gainDeltaDb,
            sourceTypeCode: mapSourceTypeToCode(band.sourceType),
            jobId: band.jobId,
            suggestionActionId: band.suggestionActionId,
            appliedSuggestionId: band.appliedSuggestionId,
        }
    }

    // [최적화] 전역 AudioBuffer 캐시: URL 당 한 번만 fetch+decode 하여 재생기(Tone.Player)와 파형(WaveformWebGL) 모두 공유
    // 키: cdnUrl 문자열, 값: 디코딩 완료된 AudioBuffer
    const audioBufferCache = new Map<string, AudioBuffer>();
    // 진행 중인 디코딩 Promise를 보관하여 동시에 같은 URL을 여러 번 디코딩하는 것을 방지
    const audioBufferPending = new Map<string, Promise<AudioBuffer>>();

    // URL에 대한 AudioBuffer를 한 번만 디코딩하여 캐시에 저장하고 반환하는 함수
    const fetchAndCacheAudioBuffer = async (url: string): Promise<AudioBuffer> => {
        // 이미 캐시에 있으면 즉시 반환
        const cached = audioBufferCache.get(url);
        if (cached) return cached;

        // 다른 곳에서 이미 디코딩 중이면 같은 Promise를 공유 (중복 요청 방지)
        const pending = audioBufferPending.get(url);
        if (pending) return pending;

        // 최초 요청: fetch → decode → 캐시 저장
        const promise = (async () => {
            const response = await fetch(url);
            const arrayBuffer = await response.arrayBuffer();
            const audioCtx = Tone.getContext().rawContext as AudioContext;
            const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

            // [최적화] Web Audio API 버퍼 할당 병목(JIT Compile Freeze) 사전 제거
            // 거대한 AudioBuffer가 처음 할당될 때 브라우저가 멈추는 현상을 막기 위해
            // ?�디???�운로드 직후 백그?�운?�에????�?�??�생??강제?�여 캐싱???�도?�니??
            try {
                const warmupSource = audioCtx.createBufferSource();
                warmupSource.buffer = audioBuffer;
                const dummyGain = audioCtx.createGain();
                dummyGain.gain.value = 0; // 무음 처리
                warmupSource.connect(dummyGain);
                dummyGain.connect(audioCtx.destination);

                warmupSource.start(0, 0, 0.001);

                // 웜업 노드가 JIT 컴파일을 충분히 완료할 수 있도록 메모리 해제를 늦춥니다
                setTimeout(() => {
                    try {
                        warmupSource.disconnect();
                        dummyGain.disconnect();
                    } catch (e) { /* ignore */ }
                }, 5000);
            } catch (e) {
                // 무시
            }

            audioBufferCache.set(url, audioBuffer);
            audioBufferPending.delete(url);
            return audioBuffer;
        })();

        audioBufferPending.set(url, promise);
        return promise;
    };

    // 외부(WaveformWebGL 등)에서 캐시에 접근할 수 있도록 getter 함수 제공
    const getAudioBufferCache = () => audioBufferCache;

    // 재생바 자동 스크롤용 타임라인 컨테이너 DOM 참조 (ProjectPage에서 전달받음)
    let timelineContainer: HTMLElement | null = null;
    let cachedScrollLeft = 0;
    let cachedClientWidth = 0;

    const isAutoScrollActive = ref(true); // 수동 스크롤 시 자동 스크롤 일시 정지용
    const workspaceZoom = ref(0.9); // 타임라인 워크스페이스 배율 (기본 90%)

    const setTimelineContainer = (el: HTMLElement | null) => {
        if (timelineContainer) {
            timelineContainer.removeEventListener('scroll', handleScroll);
        }
        timelineContainer = el;
        if (el) {
            cachedScrollLeft = el.scrollLeft;
            cachedClientWidth = el.clientWidth;
            el.addEventListener('scroll', handleScroll, { passive: true });
        }
    };

    const handleScroll = () => {
        // [최적화] 재생 중이더라도 자동 스크롤이 비활성화(사용자 수동 조작) 상태면 스크롤을 동기화합니다.
        if (timelineContainer && (!isPlaying.value || !isAutoScrollActive.value)) {
            cachedScrollLeft = timelineContainer.scrollLeft;
        }
    };

    // [Tone.js 버그 픽스]
    // Tone.js의 Player.sync()는 Transport에 의해 중간 지점에서 재생이 시작(Seek)될 때,
    // playbackRate를 고려하지 않고 오프셋을 계산하는 버그가 있습니다.
    // 이를 해결하기 위해 _start 내부 메서드를 몽키패칭하여 오프셋과 남은 재생 시간을 보정합니다.
    const patchTonePlayerForSync = (player: any) => {
        if (player._isPatchedForSync) return;
        player._isPatchedForSync = true;
        const origStart = player._start.bind(player);

        player._start = function (startTime: number, passedOffset: number, passedDuration?: number) {
            const originalOffset = this.customOriginalOffset || 0;
            const startOffsetTransport = passedOffset - originalOffset;

            let correctedOffset = passedOffset;
            let correctedDuration = passedDuration;

            // playbackRate가 Tone.Param 객체일 수 있으므로 값을 안전하게 추출
            const actualRate = (this.playbackRate && typeof this.playbackRate === 'object' && 'value' in this.playbackRate)
                ? (this.playbackRate as any).value
                : this.playbackRate;

            // startOffsetTransport가 0보다 크다는 것은 처음부터가 아니라 중간부터(Seek) 시작된다는 의미
            if (startOffsetTransport > 0.001 && actualRate !== 1) {
                // Transport의 이동 시간만큼 오디오 버퍼도 진행되어야 하므로 playbackRate를 곱해줍니다.
                correctedOffset = originalOffset + (startOffsetTransport * actualRate);
                if (passedDuration !== undefined) {
                    const originalDuration = this.customSourceAudioSec || passedDuration;
                    correctedDuration = originalDuration - (startOffsetTransport * actualRate);
                }
            }

            origStart(startTime, correctedOffset, correctedDuration !== undefined ? Math.max(0, correctedDuration) : undefined);
        };
    };

    //[1-1] 백엔드 연동 데이터
    const trackList = ref<TrackUIState[]>([]); //트랙들을 담을 배열
    //<trackUIstate[]>로 UI용 트랙데이터만 들어올수 있음을 선언 ref이므로 추가 삭제시 화면이 반응함 

    const projectInfo = ref({ //프로젝트의 전반적인 정보를 담은 객체 
        projectId: 0,
        name: '프로젝트',
        tempo: 120.0,
        rootNote: 'C',
        mode: 'major',
        timeSigNumerator: 4,
        timeSigDenominator: 4,
        totalBarCount: 32
    });

    const projectMembers = ref<{ userId: number; nickname: string; profileImageUrl: string | null; }[]>([]);
    const currentTotalSizeBytes = ref<number>(0);
    const maxTotalSizeBytes = ref<number>(50 * 1024 * 1024);
    const masterLimiterState = ref<MasterLimiterState | null>(null);

    //[1-2] 타임라인 UI 전용 상태 (프론트에서 화면 그릴 때만 쓰는 변수들)
    const isPlaying = ref(false); //재생중인지 아닌지
    const manualLatencyOffset = ref(0.15); // 사용자 수동 레이턴시 보정값 (초 단위, 예: 0.1 = 100ms 추가 지연)

    //프로젝트 BPM 설정 및 Tone.js 동기화
    const bpm = ref(120);
    Tone.getTransport().bpm.value = 120; // Transport 내부 시계는 항상 고정 (playbackRate로 속도 조절)
    // 메인 스레드 블로킹 시 이벤트 스킵 방지를 위한 스케줄링 여유시간 상향 조정
    Tone.getContext().lookAhead = 0.2;
    // transport는 백 그라운드의 오디오 시계 역할을 함. 여기 tempo를 조정하면 전체 앱의 빠르기가 바뀜.

    // 마스터 트랙의 믹서 채널 생성 (모노 다운믹스 절대 방지: 강제 스테레오)
    const masterPanner = new Tone.Panner(0).toDestination();
    const masterLimiterInput = new Tone.Gain(1);
    const masterLimiter = new Tone.Compressor({
        threshold: 0,
        ratio: 20,
        attack: 0.003,
        release: 0.25,
        knee: 0,
    });
    const masterLimiterOutput = new Tone.Gain(1);
    const masterVolume = new Tone.Volume(0).connect(masterLimiterInput);
    masterLimiterInput.connect(masterLimiter);
    masterLimiter.connect(masterLimiterOutput);
    masterLimiterOutput.connect(masterPanner);

    // 스테레오 보존을 위한 강력한 Web Audio API 옵션 적용
    masterVolume.channelCount = 2;
    masterVolume.channelCountMode = "explicit";
    masterLimiterInput.channelCount = 2;
    masterLimiterInput.channelCountMode = "explicit";
    masterLimiter.channelCount = 2;
    masterLimiter.channelCountMode = "explicit";
    masterLimiterOutput.channelCount = 2;
    masterLimiterOutput.channelCountMode = "explicit";
    masterPanner.channelCount = 2;
    masterPanner.channelCountMode = "explicit";

    const dbToLinear = (db: number) => Math.pow(10, db / 20);

    function applyMasterLimiterStateToAudio(limiterState: MasterLimiterState | null) {
        if (!limiterState || !limiterState.isEnabled) {
            masterLimiterInput.gain.value = 1;
            masterLimiter.threshold.value = 0;
            masterLimiter.attack.value = 0.003;
            masterLimiter.release.value = 0.25;
            masterLimiterOutput.gain.value = 1;
            return;
        }

        masterLimiterInput.gain.value = dbToLinear(limiterState.inputGainDb);
        masterLimiter.threshold.value = Math.max(-100, Math.min(0, limiterState.thresholdDb));
        masterLimiter.attack.value = Math.max(0, limiterState.attackMs / 1000);
        masterLimiter.release.value = Math.max(0.001, limiterState.releaseMs / 1000);
        masterLimiterOutput.gain.value = dbToLinear(
            limiterState.makeupGainDb + limiterState.ceilingDbfs,
        );
    }

    function setMasterLimiterState(limiterState: MasterLimiterState | null) {
        masterLimiterState.value = limiterState;
        applyMasterLimiterStateToAudio(limiterState);
    }

    //bpm이 변경될때마다 전체 클립을 재스케줄링 (Transport BPM은 고정, playbackRate만으로 속도 제어)
    watch(bpm, (newBpm) => {
        // Transport BPM은 변경하지 않음 — playbackRate와 이중 적용되어 재생 길이가 어긋나는 것을 방지

        // BPM이 바뀌면 secondsPerBar가 바뀌므로 모든 클립의 재생 스케줄을 새 기준으로 재등록
        // 재생 중이면 일시정지 → 재스케줄 → 자동 재개하여 타이밍 꼬임 방지
        const wasPlaying = isPlaying.value;
        if (wasPlaying) {
            Tone.getTransport().pause();
        }

        // 현재 재생 위치(마디)를 보존하여 재스케줄 후 같은 마디에서 재개
        // Tone.getTransport().seconds는 옛날 BPM 기준의 시간이고 secondsPerBar는 새 BPM 기준이므로,
        // 이를 나누면 위치가 왜곡됨. 대신 이미 정확한 마디를 가리키는 playheadPosition.value를 사용함.
        const currentBar = playheadPosition.value;

        resyncAllClips();

        // 메트로놈이 켜져 있으면 새 BPM 간격으로 재시작
        if (isMetronomeActive.value) {
            applyMetronomeState(true);
        }

        if (wasPlaying) {
            const newOffsetTime = currentBar * secondsPerBar.value;
            Tone.getTransport().start("+0.05", newOffsetTime);
        }
    })

    // ==========================================
    // BPM (Tempo) 변경
    // ==========================================
    const changeBpm = (newBpm: number) => {
        // 유효성 검사 (PlayController의 로직과 동일)
        if (isNaN(newBpm) || newBpm < 30 || newBpm > 300) return;

        // 로컬 값과 같으면 무시
        if (bpm.value === newBpm) return;

        // 로컬 즉시 적용 (Optimistic UI)
        // bpm.value가 변경되면 위의 watch(bpm)가 트리거되어 자동으로 클립이 재스케줄링됩니다.
        bpm.value = newBpm;
        projectInfo.value.tempo = newBpm;

        // 백엔드에 BPM 변경 요청 전송 → 브로드캐스트로 다른 사용자에게 전파
        socketService.publish('PROJECT_BPM', {
            projectId: projectInfo.value.projectId,
            tempo: newBpm
        });
    };

    // ==========================================
    // 키(Key) 변경
    // ==========================================
    // UI(문자열) -> 백엔드(Enum)
    const rootNoteToEnum: Record<string, string> = {
        "C": "C",
        "Db": "C_SHARP",
        "D": "D",
        "Eb": "E_FLAT",
        "E": "E",
        "F": "F",
        "F#": "F_SHARP",
        "G": "G",
        "Ab": "A_FLAT",
        "A": "A",
        "Bb": "B_FLAT",
        "B": "B"
    };

    // 백엔드(Enum) -> UI(문자열)
    const enumToRootNote: Record<string, string> = {
        "C": "C",
        "C_SHARP": "Db",
        "D": "D",
        "E_FLAT": "Eb",
        "E": "E",
        "F": "F",
        "F_SHARP": "F#",
        "G": "G",
        "A_FLAT": "Ab",
        "A": "A",
        "B_FLAT": "Bb",
        "B": "B"
    };

    // 반음 인덱스 매핑 (C=0 ~ B=11)
    const NOTE_TO_SEMITONE: Record<string, number> = {
        "C": 0, "Db": 1, "D": 2, "Eb": 3,
        "E": 4, "F": 5, "F#": 6, "G": 7,
        "Ab": 8, "A": 9, "Bb": 10, "B": 11
    };

    // 두 키 사이의 최단 반음 차이 계산 (예: C→D = +2, C→A = -3)
    const getSemitoneDiff = (fromNote: string, toNote: string): number => {
        const from = NOTE_TO_SEMITONE[fromNote] ?? 0;
        const to = NOTE_TO_SEMITONE[toNote] ?? 0;
        let diff = to - from;
        if (diff > 6) diff -= 12;
        if (diff < -6) diff += 12;
        return diff;
    };

    const changeKey = (rootNote: string, mode: string) => {
        const oldNote = projectInfo.value.rootNote;
        if (oldNote === rootNote && projectInfo.value.mode === mode) return;

        // 로컬 즉시 적용 (Optimistic UI)
        projectInfo.value.rootNote = rootNote;
        projectInfo.value.mode = mode;

        // 백엔드로 보낼 때는 Enum 규격에 맞춰서 변환
        const rootNoteEnum = rootNoteToEnum[rootNote] || rootNote;

        socketService.publish('PROJECT_KEY', {
            projectId: projectInfo.value.projectId,
            rootNote: rootNoteEnum,
            mode
        });
    };

    // ==========================================
    // 박자(Time Signature) 변경
    // ==========================================
    // 허용되는 박자 조합 (10가지)
    const ALLOWED_TIME_SIGNATURES: [number, number][] = [
        [2, 4], [3, 4], [4, 4], [5, 4], [6, 4], [7, 4],
        [3, 8], [6, 8], [9, 8], [12, 8]
    ];

    // 박자 변경 시 내부 적용 로직 (로컬 즉시 적용 + 원격 브로드캐스트 수신 공용)
    // DAW 표준: 클립의 마디 위치(숫자)는 그대로 유지, secondsPerBar만 바뀜
    const applyTimeSignatureChange = (newNumerator: number, newDenominator: number) => {
        const oldNumerator = projectInfo.value.timeSigNumerator;
        const oldDenominator = projectInfo.value.timeSigDenominator;

        // 이미 같은 값이면 무시 (브로드캐스트 자기 수신 차단)
        if (oldNumerator === newNumerator && oldDenominator === newDenominator) return;

        // 재생 중이면 일시정지
        const wasPlaying = isPlaying.value;
        if (wasPlaying) {
            Tone.getTransport().pause();
        }

        // projectInfo 갱신 → secondsPerBar computed 자동 재계산
        projectInfo.value.timeSigNumerator = newNumerator;
        projectInfo.value.timeSigDenominator = newDenominator;

        // 클립의 마디 위치(start, duration)는 그대로 유지
        // secondsPerBar가 바뀌었으므로 오디오 스케줄만 재등록
        resyncAllClips();

        // 메트로놈 재시작 (박자 패턴이 바뀌었으므로)
        if (isMetronomeActive.value) {
            applyMetronomeState(true);
        }

        // 재생 중이었으면 현재 재생바 위치에서 재개
        if (wasPlaying) {
            const newOffsetTime = playheadPosition.value * secondsPerBar.value;
            Tone.getTransport().start("+0.05", newOffsetTime);
        }
    };

    // 사용자 액션: 박자 변경 요청 (UI → 소켓 발행)
    const changeTimeSignature = (numerator: number, denominator: number) => {
        // 허용 조합 검증
        const isAllowed = ALLOWED_TIME_SIGNATURES.some(
            ([n, d]) => n === numerator && d === denominator
        );
        if (!isAllowed) return;

        // 로컬 즉시 적용 (Optimistic UI)
        applyTimeSignatureChange(numerator, denominator);

        // 백엔드에 박자 변경 요청 전송 → 브로드캐스트로 다른 사용자에게 전파
        socketService.publish('PROJECT_TIME_SIGNATURE', {
            projectId: projectInfo.value.projectId,
            timeSigNumerator: numerator,
            timeSigDenominator: denominator
        });
    };


    type SelectedTarget =
        | { type: 'TRACK'; trackId: number }
        | { type: 'MASTER' }
        | null
    const selectedTarget = ref<SelectedTarget>(null)
    // 현재 선택된 클립과 해당 트랙 ID
    const selectedClip = ref<ClipUIState | null>(null);
    const selectedTrackId = ref<number | null>(null);


    function selectMasterTrack() {
        if (selectedClip.value) {
            selectedClip.value.isSelected = false
            selectedClip.value = null
        }

        selectedTrackId.value = null
        selectedTarget.value = {
            type: 'MASTER',
        }

        trackList.value.forEach(t => {
            t.isSelected = false
        })

        masterTrack.value.isSelected = true
    }

    // 클립 선택 함수
    const selectClip = (clip: ClipUIState, trackId: number) => {
        if (selectedClip.value) {
            selectedClip.value.isSelected = false
        }

        clip.isSelected = true
        selectedClip.value = clip
        selectedTrackId.value = trackId
        selectedTarget.value = {
            type: 'TRACK',
            trackId,
        }

        trackList.value.forEach(t => {
            t.isSelected = false
        })

        masterTrack.value.isSelected = false
    }

    // 트랙 선택 함수 (클립 선택은 해제됨)
    const selectTrack = (trackId: number) => {
        if (trackId === 999999) {
            selectMasterTrack()
            return
        }

        if (selectedClip.value) {
            selectedClip.value.isSelected = false
            selectedClip.value = null
        }

        selectedTrackId.value = trackId
        selectedTarget.value = {
            type: 'TRACK',
            trackId,
        }

        trackList.value.forEach(t => {
            t.isSelected = t.trackId === trackId
        })

        masterTrack.value.isSelected = false
    }

    //  빈 공간 클릭 시 선택 해제 함수
    const deselectAll = () => {
        if (selectedClip.value) selectedClip.value.isSelected = false

        selectedClip.value = null
        selectedTrackId.value = null
        selectedTarget.value = null

        trackList.value.forEach(t => {
            t.isSelected = false
        })

        masterTrack.value.isSelected = false
    }
    //1마디당 걸리는 시간 계산 (박자의 분모를 반영하여 6/8박자 등에서도 정확한 마디 길이 보장)
    const secondsPerBar = computed(() => (projectInfo.value.timeSigNumerator * (4 / (projectInfo.value.timeSigDenominator || 4)) * 60) / bpm.value);

    // ==========================================
    // 구간 반복 (Loop)
    // ==========================================
    const isLoopActive = ref(false);
    const loopStartBar = ref(0);
    const loopEndBar = ref(4);

    watch([isLoopActive, loopStartBar, loopEndBar, bpm], () => {
        if (isLoopActive.value) {
            Tone.getTransport().setLoopPoints(
                loopStartBar.value * secondsPerBar.value,
                loopEndBar.value * secondsPerBar.value
            );
            Tone.getTransport().loop = true;
        } else {
            Tone.getTransport().loop = false;
        }
    });

    // ==========================================
    // 메트로놈 (Metronome / Click Track)
    // ==========================================
    const isMetronomeActive = ref(false);
    let clickSynth: Tone.Synth | null = null;
    let metronomeEventId: number | null = null;

    const applyMetronomeState = (active: boolean) => {
        // 기존 메트로놈 비활성화 시 스케줄링 해제 (다중 스케줄 방지)
        if (metronomeEventId !== null) {
            Tone.getTransport().clear(metronomeEventId);
            metronomeEventId = null;
        }

        if (active) {
            // Synth가 없으면 생성 — toDestination()으로 마스터 볼륨 무관하게 항상 출력
            if (!clickSynth) {
                clickSynth = new Tone.Synth({
                    oscillator: { type: "square" },
                    envelope: { attack: 0.001, decay: 0.05, sustain: 0, release: 0.01 }
                }).toDestination();
            }

            const denom = projectInfo.value.timeSigDenominator || 4;
            const numerator = projectInfo.value.timeSigNumerator || 4;
            // Transport BPM이 고정이므로, 메트로놈 간격을 초 단위로 직접 계산합니다.
            const beatIntervalSec = (denom === 8) ? (60 / bpm.value / 2) : (60 / bpm.value);

            metronomeEventId = Tone.getTransport().scheduleRepeat((time) => {
                // time은 AudioContext의 하드웨어 시간이고, Transport 내부 시간은 별도로 계산해야 합니다.
                // 하드웨어 예약 시간(time)과 현재 시간(Tone.now())의 차이(Lookahead)를 Transport.seconds에 더해 정확한 예약 시점(초)을 구합니다.
                const transportTimeSec = Tone.getTransport().seconds + Math.max(0, time - Tone.now());

                // 현재 재생 위치가 몇 번째 박자인지 계산 (반올림 처리로 스케줄링 오차 보정)
                const absoluteBeat = Math.round(transportTimeSec / beatIntervalSec);
                const currentBeat = absoluteBeat % numerator;

                // 첫 박자는 '삑(C6)', 나머지는 '띡(C5)' 소리
                const note = currentBeat === 0 ? "C6" : "C5";
                clickSynth!.triggerAttackRelease(note, "64n", time, 0.5);
            }, beatIntervalSec, 0);
        }
    };

    watch(isMetronomeActive, applyMetronomeState);

    let animationFrameId = 0; //requestAnimationFrame 실행 ID (취소를 위해 필요)
    const playheadPosition = ref(0); //현재 재생 위치(마디 단위)
    const zoomlevel = ref(1) //가로 확대/축소 배율 (기본 1배)

    // ==========================================
    // 가로 가상 스크롤 (수평 뷰포트) 상태
    // ==========================================
    const viewportLeft = ref(0);
    const viewportRight = ref(2000); // 초기 렌더링을 위해 기본값 제공

    //복사/잘라내기 한 클립 데이터를 보관할 클립보드
    const clipboardClip = ref<ClipUIState | null>(null);
    const clipboardTrackId = ref<number | null>(null);
    const isCutAction = ref(false);
    const uploadingTrackId = ref<number | null>(null);
    const uploadingBar = ref<number | null>(null); //현재 보관된 데이터가 '잘라내기'로 들어왔는지 여부

    // 스토어 내부에 변수와 토글 함수 선언
    const isCommentMode = ref(false);
    const toggleCommentMode = () => {
        isCommentMode.value = !isCommentMode.value;
    };

    interface HistoryCommand {
        undo: () => void;
        redo: () => void;
    }
    const undoStack = ref<HistoryCommand[]>([]);
    const redoStack = ref<HistoryCommand[]>([]);
    const MAX_HISTORY = 30;

    const pushCommand = (cmd: HistoryCommand) => {
        undoStack.value.push(cmd);
        if (undoStack.value.length > MAX_HISTORY) {
            undoStack.value.shift();
        }
        redoStack.value = [];
    };

    // ==========================================
    // 2. 계산된 상태(Getters) - 타임라인 픽셀 계산기
    // ==========================================

    //1마디당 픽셀 너비 (기본 120px * 줌 배율)
    //화면에서 클립 길이나 재생바 위치를 px로 바꿀때 사용
    const pixelPerBar = computed(() => 120 * zoomlevel.value);

    // 화면 너비(최대 4000px 기준)를 채우기 위해 필요한 최소 마디 수 계산
    const displayBarCount = computed(() => {
        const minRequiredBars = Math.ceil(4000 / pixelPerBar.value);
        return Math.max(projectInfo.value.totalBarCount, minRequiredBars);
    });

    //전체 타임라인의 가로 픽셀 길이(화면에 표시할 마디 수 * 1마디 픽셀)
    const totalTimelineWidth = computed(() => displayBarCount.value * pixelPerBar.value);

    //스크롤 축소 할때 숫자를 표시할 마디 간격 계산 (1,4,8)
    const barNumberStep = computed(() => {
        if (zoomlevel.value <= 0.15) return 32; // 매우 많이 축소할때 1, 33, 65 ... (100마디 보기 대응)
        if (zoomlevel.value <= 0.3) return 16;  // 더 축소할때 1, 17, 33 ...
        if (zoomlevel.value <= 0.5) return 8;   // 많이 축소할때 1, 9, 17 ...
        if (zoomlevel.value < 1.0) return 4; //약간 축소할때 1, 5, 9 ...
        return 1; //기본 1칸씩
    })

    // 스크롤 확대 시 1마디를 몇 칸으로 쪼갤 것인가 (박자에 따라 동적 계산)
    // 예: 4/4 → 4,8,16  |  3/4 → 3,6,12  |  6/8 → 6,12,24
    const subDivision = computed(() => {
        const numerator = projectInfo.value.timeSigNumerator || 4;
        if (zoomlevel.value >= 2.5) return numerator * 4; // 아주 많이 확대: 16분음표급 세밀 분할
        if (zoomlevel.value >= 1.5) return numerator * 2; // 많이 확대: 8분음표급 분할
        if (zoomlevel.value >= 1.0) return numerator;     // 기본: 비트(박자 분자) 단위 분할
        return 1; // 축소 시 분할 없음
    })

    // 타임라인 자동 확장 헬퍼 함수
    const checkAndExpandTimeline = (endBar: number) => {
        const currentTotalBars = projectInfo.value.totalBarCount;
        // 클립의 끝부분이 전체 타임라인의 90% 지점을 넘어가거나 아예 뚫고 나갔을 때
        if (endBar > currentTotalBars * 0.9) {
            // 기본 50마디를 늘려주되, 만약 클립이 너무 길어서 50마디로도 부족하면 그 클립 길이에 맞춰서 넉넉하게 늘려줍니다.
            const extendAmount = Math.max(50, Math.ceil(endBar - currentTotalBars) + 10);
            projectInfo.value.totalBarCount += extendAmount;
            // console.log(`타임라인이 자동으로 ${projectInfo.value.totalBarCount}마디로 확장되었습니다.`);
        }
    };

    function clampNumber(value: number, min: number, max: number) {
        return Math.max(min, Math.min(max, value))
    }

    function clampFrequency(frequencyHz: number) {
        return Math.round(clampNumber(frequencyHz, 20, 20000))
    }

    function clampGain(gainDeltaDb: number) {
        return Math.round(clampNumber(gainDeltaDb, -12, 12) * 10) / 10
    }

    function clampQ(q: number) {
        return Math.round(clampNumber(q, 0.1, 10) * 100) / 100
    }

    function getTrackEq(track: TrackUIState): TrackEqState {
        return {
            bands: track.eq?.bands ?? [],
        }
    }

    function createToneFilterFromBand(band: TrackEqBandState) {
        const type =
            band.eqTypeCode === 2
                ? 'lowshelf'
                : band.eqTypeCode === 3
                    ? 'highshelf'
                    : 'peaking'

        const filter = new Tone.Filter({
            type,
            frequency: band.frequencyHz,
            Q: band.q,
            gain: band.gainDeltaDb,
        })

        filter.channelCount = 2
        filter.channelCountMode = 'explicit'

        return filter
    }

    function disposeTrackEqNodes(trackId: number) {
        const nodes = trackEqNodes.get(trackId)

        if (!nodes) return

        nodes.forEach(node => {
            node.filter.dispose()
        })

        trackEqNodes.delete(trackId)
    }

    function disposeTrackAnalyzer(trackId: number) {
        const analyzer = trackAnalyzers.get(trackId)

        if (!analyzer) return

        analyzer.dispose()
        trackAnalyzers.delete(trackId)
    }

    function createTrackEqNodes(track: TrackUIState, customBands?: TrackEqBandState[]): TrackEqNode[] {
        disposeTrackEqNodes(track.trackId)

        const bands = customBands ?? getTrackEq(track).bands;

        const nodes = bands.map(band => ({
            bandOrder: band.bandOrder,
            filter: createToneFilterFromBand(band),
        }))

        trackEqNodes.set(track.trackId, nodes)

        return nodes
    }

    function getTrackInputNode(trackId: number) {
        const eqNodes = trackEqNodes.get(trackId) ?? []
        const analyzer = trackAnalyzers.get(trackId)
        const volume = trackVolumes.get(trackId)

        if (!volume) return null

        if (eqNodes.length > 0) {
            return eqNodes[0].filter
        }

        if (analyzer) {
            return analyzer
        }

        return volume
    }

    function connectPlayerToTrack(
        player: Tone.Player,
        trackId: number,
    ) {
        const inputNode = getTrackInputNode(trackId)

        if (!inputNode) return

        player.disconnect()
        player.connect(inputNode)
    }

    function reconnectTrackPlayers(trackId: number) {
        const track = trackList.value.find(track => track.trackId === trackId)
        if (!track) return

        const inputNode = getTrackInputNode(trackId)
        if (!inputNode) return

        track.clips.forEach(clip => {
            const player = clipPlayers.get(clip.clipId)
            if (!player) return

            player.disconnect()
            player.connect(inputNode)
        })
    }

    function rebuildTrackEqChain(trackId: number, customBands?: TrackEqBandState[]) {
        const track = trackList.value.find(track => track.trackId === trackId)
        const volume = trackVolumes.get(trackId)

        if (!track || !volume) return

        disposeTrackEqNodes(trackId)
        disposeTrackAnalyzer(trackId)
        const eqNodes = createTrackEqNodes(track, customBands)
        const analyzer = new Tone.FFT(2048)

        trackAnalyzers.set(trackId, analyzer)

        if (eqNodes.length > 0) {
            for (let i = 0; i < eqNodes.length - 1; i += 1) {
                eqNodes[i].filter.connect(eqNodes[i + 1].filter)
            }

            eqNodes[eqNodes.length - 1].filter.connect(analyzer)
            analyzer.connect(volume)
        }
        else {
            analyzer.connect(volume)
        }

        reconnectTrackPlayers(trackId)
    }

    function disposeClipAudio(clipId: number) {
        const player = clipPlayers.get(clipId)

        if (player) {
            player.unsync().stop().dispose()
            clipPlayers.delete(clipId)
        }
    }

    function disposeTrackAudioChain(trackId: number) {
        disposeTrackEqNodes(trackId)
        disposeTrackAnalyzer(trackId)
    }

    // ==========================================
    // 🌐 웹소켓 수신 (Subscribe) 처리부
    // ==========================================
    // 백엔드 명세에 맞추어 이벤트 명(`CLIP_PASTE_SUCCESS` 등)을 수정하여 사용


    // --------------------- 트랙 관련 (소켓) ---------------------    
    socketService.subscribePersistent('TRACK_ADD', (data) => {
        // 이미 그려져있으면 무시 (Optimistic UI 중복 방지)
        if (trackList.value.some(t => t.trackId === data.trackId)) return;

        const newTrack: TrackUIState = {
            trackId: data.trackId,
            name: data.name,
            type: data.type.toLowerCase(),
            preTrackId: data.preTrackId,
            postTrackId: data.postTrackId,
            isMuted: data.isMuted,
            isSoloed: data.isSoloed,
            volume: data.volume,
            pan: data.pan,
            clips: [],
            height: 100,
            isSelected: false,
            eq: createDefaultTrackEq(),
        };
        trackList.value.push(newTrack);

        const panner = new Tone.Panner(newTrack.pan / 100).connect(masterVolume);
        const vol = new Tone.Volume(newTrack.volume).connect(panner);
        panner.channelCount = 2; panner.channelCountMode = "explicit";
        vol.channelCount = 2; vol.channelCountMode = "explicit";

        trackVolumes.set(newTrack.trackId, vol);
        trackPanners.set(newTrack.trackId, panner);

        rebuildTrackEqChain(newTrack.trackId);

        if (pendingTrackAddCount.value > 0) {
            pendingTrackAddCount.value--;
            const createdTrackId = data.trackId;
            pushCommand({
                undo: () => {
                    // 트랙 추가 취소: 생성된 트랙을 다시 지움
                    socketService.publish('TRACK_DELETE', {
                        projectId: projectInfo.value.projectId,
                        trackId: createdTrackId
                    });
                },
                redo: () => {
                    useAlertStore().showAlert("취소된 트랙은 '새 트랙 추가' 버튼으로 다시 만들어 주세요.", "info");
                }
            });
        }
    });

    socketService.subscribePersistent('TRACK_DELETE', (data) => {
        const index = trackList.value.findIndex(t => t.trackId === data.trackId);
        if (index !== -1) {
            // 🚨 보완: 트랙을 지우기 전에, 트랙 안에 있던 모든 클립의 오디오 메모리를 완전 해제!
            trackList.value[index].clips.forEach(clip => {
                disposeClipAudio(clip.clipId);
            });

            disposeTrackAudioChain(data.trackId);

            trackList.value.splice(index, 1);
            trackVolumes.get(data.trackId)?.dispose(); trackVolumes.delete(data.trackId);
            trackPanners.get(data.trackId)?.dispose(); trackPanners.delete(data.trackId);
        }
        if (selectedTrackId.value === data.trackId) deselectAll();
    });

    socketService.subscribePersistent('TRACK_REORDER', (data) => {
        const { trackId, preTrackId, postTrackId } = data;
        const trackIndex = trackList.value.findIndex(t => t.trackId === trackId);
        if (trackIndex === -1) return;

        const [track] = trackList.value.splice(trackIndex, 1);

        let newIndex = 0;
        if (preTrackId) {
            const preIndex = trackList.value.findIndex(t => t.trackId === preTrackId);
            if (preIndex !== -1) newIndex = preIndex + 1;
        } else if (postTrackId) {
            const postIndex = trackList.value.findIndex(t => t.trackId === postTrackId);
            if (postIndex !== -1) newIndex = postIndex;
        }

        trackList.value.splice(newIndex, 0, track);
    });

    socketService.subscribePersistent('TRACK_RENAME', (data) => {
        const track = trackList.value.find(t => t.trackId === data.trackId);
        if (track) track.name = data.name;
    });

    socketService.subscribePersistent('TRACK_MUTE_CHANGE', (data) => {
        const track = trackList.value.find(t => t.trackId === data.trackId);
        if (track) { track.isMuted = data.isMuted; syncEffectiveMuteStates(); }
    });

    socketService.subscribePersistent('TRACK_SOLO_CHANGE', (data) => {
        const track = trackList.value.find(t => t.trackId === data.trackId);
        if (track) { track.isSoloed = data.isSoloed; syncEffectiveMuteStates(); }
    });

    socketService.subscribePersistent('TRACK_VOLUME_CHANGE', (data) => {
        const track = trackList.value.find(t => t.trackId === data.trackId);
        if (track) {
            track.volume = data.volume;
            const vol = trackVolumes.get(data.trackId);
            if (vol) vol.volume.value = data.volume;
        }
    });

    socketService.subscribePersistent('TRACK_PAN_CHANGE', (data) => {
        const track = trackList.value.find(t => t.trackId === data.trackId);
        if (track) {
            track.pan = data.pan;
            const panner = trackPanners.get(data.trackId);
            if (panner) panner.pan.value = data.pan / 100;
        }
    });

    // --------------------- 에러 수신 (소켓) ---------------------
    socketService.subscribePersistent('ERROR', (data: any) => {
        if (data && data.message) {
            alertStore.showAlert(data.message, "error");
        } else {
            alertStore.showAlert("처리 중 오류가 발생했습니다.", "error");
        }
    });

    // --------------------- 박자 변경 수신 (소켓) ---------------------
    socketService.subscribePersistent('MODIFIED_PROJECT_TIME_SIGNATURE', (data: any) => {
        const newNum = data.timeSigNumerator;
        const newDenom = data.timeSigDenominator;

        // 이미 같은 값이면 (내가 보낸 요청의 브로드캐스트 응답) 스킵
        if (projectInfo.value.timeSigNumerator === newNum &&
            projectInfo.value.timeSigDenominator === newDenom) return;

        // 다른 사용자가 변경한 박자를 로컬에 적용
        applyTimeSignatureChange(newNum, newDenom);
    });

    // --------------------- BPM 변경 수신 (소켓) ---------------------
    socketService.subscribePersistent('MODIFIED_PROJECT_BPM', (data: any) => {
        const newBpm = data.tempo;

        // 이미 같은 값이면 (내가 보낸 요청의 브로드캐스트 응답) 스킵
        if (bpm.value === newBpm) return;

        // 다른 사용자가 변경한 BPM을 로컬에 적용
        // 변경 시 watch(bpm)이 트리거되어 자동 재스케줄링됨
        bpm.value = newBpm;
        projectInfo.value.tempo = newBpm;
    });

    // --------------------- 키(Key) 변경 수신 (소켓) ---------------------
    socketService.subscribePersistent('MODIFIED_PROJECT_KEY', (data: any) => {
        // 서버에서 온 Enum 문자열을 다시 프론트엔드 표기법으로 변환
        const newNote = enumToRootNote[data.rootNote] || data.rootNote;
        const newMode = data.mode;

        // 이미 같은 값이면 (내가 보낸 요청의 브로드캐스트 응답) 스킵
        if (projectInfo.value.rootNote === newNote && projectInfo.value.mode === newMode) return;

        // 다른 사용자가 변경한 키를 로컬에 적용
        projectInfo.value.rootNote = newNote;
        projectInfo.value.mode = newMode;
    });

    // --------------------- 클립 관련 (소켓) ---------------------
    socketService.subscribePersistent('CLIP_LOCK', (data) => {
        // 내가 직접 잠근 클립이면 내 화면에서는 잠금 표시를 하지 않는다 (자기 자신 차단 방지)
        if (myLockedClips.has(data.clipId)) return;

        const track = trackList.value.find(t => t.clips.some(c => c.clipId === data.clipId));
        if (track) {
            const clip = track.clips.find(c => c.clipId === data.clipId);
            if (clip) {
                clip.isLocked = data.isLocked; // 다른 사람이 잠근 경우에만 자물쇠 찰칵!
            }
        }
    });

    //1.신규 클립 업로드 완료 수신
    // 1. 신규 클립 업로드 완료 수신
    socketService.subscribePersistent('CLIP_CREATE', async (data) => {
        // 업로드 중이던 클립이 백엔드에서 생성되어 돌아왔다면 고스트 클립 해제
        let isInitiator = false;
        if (uploadingTrackId.value === data.trackId) {
            isInitiator = true;
            uploadingTrackId.value = null;
            uploadingBar.value = null;
        }

        const track = trackList.value.find(t => t.trackId === data.trackId);
        if (!track) return;

        // 1. 화면에 우선 빈 클립 블록(소리 없는 껍데기) 렌더링
        const newClip: ClipUIState = {
            clipId: data.clipId,
            start: data.startBar,
            duration: data.duration,
            audioStartMs: data.audioStartMs,
            audioDurationMs: data.audioDurationMs,
            color: data.color,
            audio: {
                audioMetadataId: data.audioMetadataId,
                originalName: "오디오 로딩 중...",
                cdnUrl: "",
                durationMs: data.audioDurationMs,
            },
            isSelected: false,
            isDragging: false,
            isLocked: false
        };
        track.clips.push(newClip);
        checkAndExpandTimeline(newClip.start + newClip.duration);
        // 2. 백그라운드에서 오디오 상세 정보(URL) 조회 API 비동기 호출
        try {
            const audioInfo = await projectApi.getAudioDetail(projectInfo.value.projectId, data.audioMetadataId);

            // [최적화] 업로더 본인이 미리 캐싱해둔 로컬 blobUrl의 AudioBuffer를 CDN URL 키로 이전
            // → loadClipPlayer와 WaveformWebGL 모두 추가 네트워크 요청 없이 즉시 사용 가능
            if (data._localBlobUrl && audioBufferCache.has(data._localBlobUrl)) {
                const localBuffer = audioBufferCache.get(data._localBlobUrl)!;
                audioBufferCache.set(audioInfo.audioUrl, localBuffer);
                // 더 이상 필요 없는 blobUrl 키 제거 및 메모리 해제
                audioBufferCache.delete(data._localBlobUrl);
                URL.revokeObjectURL(data._localBlobUrl);
                // console.log(`[CLIP_CREATE 최적화] 로컬 AudioBuffer → CDN URL 키로 이전 완료 (네트워크 다운로드 생략)`);
            }

            // 3. Vue 반응성 확보: 배열 안의 실제 반응형 객체를 다시 찾아서 audio를 통째로 교체
            const reactiveClip = track.clips.find(c => c.clipId === data.clipId);
            if (reactiveClip) {
                reactiveClip.audio = {
                    audioMetadataId: data.audioMetadataId,
                    cdnUrl: audioInfo.audioUrl,
                    originalName: audioInfo.originalName,
                    durationMs: data.audioDurationMs,
                };

                // [원복] 오디오 Culling 시 디코딩 부하로 인한 끊김이 발생하여 미리 로딩
                loadClipPlayer(reactiveClip, data.trackId);
                // console.log(`[CLIP_CREATE] 백그라운드 오디오 로딩 예약 완료 (ID: ${reactiveClip.clipId})`);

                // 겹침 방지 (업로드한 당사자만 서버에 반영)
                resolveClipOverlap(reactiveClip, track, isInitiator);

                if (isInitiator) {
                    const newClipId = data.clipId;
                    const targetTrackId = data.trackId;
                    pushCommand({
                        undo: () => {
                            // 오디오 업로드 취소: 방금 생성된 클립 삭제
                            lockClip(newClipId, targetTrackId);
                            setTimeout(() => {
                                socketService.publish('CLIP_DELETE', {
                                    projectId: projectInfo.value.projectId,
                                    clipId: newClipId
                                });
                                setTimeout(() => unlockClip(newClipId, targetTrackId), 100);
                            }, 100);
                        },
                        redo: () => {
                            // 오디오 업로드 리두는 지원하지 않음 (파일 재업로드 필요하므로)
                            useAlertStore().showAlert("업로드 취소한 클립은 다시 복구할 수 없습니다.", "warning");
                        }
                    });
                }
            }
        } catch (error) {
            // console.error(`[CLIP_CREATE] 오디오 상세 정보(URL) 조회 실패:`, error);
            const failedClip = track.clips.find(c => c.clipId === data.clipId);
            if (failedClip && failedClip.audio) {
                failedClip.audio = { ...failedClip.audio, originalName: "오디오 로딩 실패" };
            }
        }
    });

    socketService.subscribePersistent('CLIP_MOVE', (data) => {
        let targetClip: ClipUIState | null = null;
        let sourceTrack: TrackUIState | null = null;

        for (const track of trackList.value) {
            const clip = track.clips.find(c => c.clipId === data.clipId);
            if (clip) {
                targetClip = clip;
                sourceTrack = track;
                break;
            }
        }

        if (!targetClip || !sourceTrack) return;

        if (
            targetClip.start === data.after.startBar &&
            sourceTrack.trackId === data.after.trackId
        ) {
            return;
        }

        if (sourceTrack.trackId !== data.after.trackId) {
            const targetTrack = trackList.value.find(t => t.trackId === data.after.trackId);
            if (!targetTrack) return;

            const clipIndex = sourceTrack.clips.findIndex(c => c.clipId === data.clipId);
            if (clipIndex !== -1) {
                sourceTrack.clips.splice(clipIndex, 1);
            }

            targetTrack.clips.push(targetClip);

            const player = clipPlayers.get(data.clipId);

            if (player) {
                connectPlayerToTrack(
                    player,
                    data.after.trackId,
                );
            }
        }

        targetClip.start = data.after.startBar;
        resyncClip(targetClip.clipId, targetClip.start);
    });

    socketService.subscribePersistent('CLIP_RESIZE', (data) => {
        for (const t of trackList.value) {
            const clip = t.clips.find(c => c.clipId === data.clipId);
            if (clip) {
                const beforeStart = data.before.startBar;
                const beforeDuration = data.before.length;
                const afterStart = data.after.startBar;
                const afterDuration = data.after.length;

                // console.log(`[CLIP_RESIZE 수신] clipId: ${data.clipId}`);
                // console.log(`  - before: start=${beforeStart}, duration=${beforeDuration}`);
                // console.log(`  - after: start=${afterStart}, duration=${afterDuration}`);
                // console.log(`  - 현재 로컬 상태: start=${clip.start}, duration=${clip.duration}`);

                // 내가 보낸 리사이즈 요청이라 이미 로컬 상태가 갱신되어 있다면 이중 적용(파형 밀림 현상) 방지
                if (Math.abs(clip.start - afterStart) < 0.0001 && Math.abs(clip.duration - afterDuration) < 0.0001) {
                    // console.log(`  => (스킵) 이미 로컬 상태가 최신입니다 (내가 보낸 요청).`);
                    break;
                }

                // 백엔드와 동일한 공식으로 프론트에서 계산하여 동기화
                const msPerBar = clip.audioDurationMs / clip.duration;
                const newAudioStartMs = Math.round(clip.audioStartMs + (afterStart - beforeStart) * msPerBar);
                const newAudioDurationMs = Math.round(afterDuration * msPerBar);

                // console.log(`  => (적용) 오디오 갱신: audioStartMs ${clip.audioStartMs} -> ${newAudioStartMs}, audioDurationMs ${clip.audioDurationMs} -> ${newAudioDurationMs}`);

                clip.start = afterStart;
                clip.duration = afterDuration;
                clip.audioStartMs = newAudioStartMs;
                clip.audioDurationMs = newAudioDurationMs;

                resyncClip(clip.clipId, clip.start);
                break; // 찾았으니 탈출
            }
        }
    });

    // 겹침 방지 및 자동 뒤로 밀어내기 유틸리티 함수
    const resolveClipOverlap = (clip: ClipUIState, track: TrackUIState, isInitiator: boolean) => {
        let hasOverlap = true;
        let safetyCounter = 0;
        const epsilon = 0.001;

        let resolvedStart = clip.start;
        const duration = clip.duration;

        while (hasOverlap && safetyCounter < 100) {
            hasOverlap = false;
            safetyCounter++;
            for (const existingClip of track.clips) {
                if (existingClip.clipId === clip.clipId) continue; // 자기 자신 건너뛰기

                const existingStart = existingClip.start;
                const existingEnd = existingClip.start + existingClip.duration;
                const desiredEnd = resolvedStart + duration;

                if (resolvedStart < existingEnd - epsilon && desiredEnd > existingStart + epsilon) {
                    hasOverlap = true;
                    resolvedStart = existingEnd; // 겹치면 해당 클립의 맨 뒤로 밀어냄
                    break; // 처음부터 다시 겹침 여부 검사
                }
            }
        }

        if (resolvedStart !== clip.start) {
            clip.start = resolvedStart;
            // 내가 복제/생성을 지시한 당사자라면 백엔드에도 위치 이동을 동기화합니다.
            if (isInitiator) {
                // console.log(`[Overlap Resolution] 클립 겹침 감지됨. 서버로 이동 요청 전송 (새 위치: ${resolvedStart})`);
                confirmMoveClip(clip.clipId, track.trackId, resolvedStart);
            }
        }
    };

    socketService.subscribePersistent('CLIP_DELETE', (data) => {
        for (const t of trackList.value) {
            const index = t.clips.findIndex(c => c.clipId === data.clipId);
            if (index !== -1) {
                t.clips.splice(index, 1);
                break; // 찾았으니 탈출
            }
        }
        disposeClipAudio(data.clipId);
    });

    socketService.subscribePersistent('CLIP_CUT', (data) => {
        // 잘라내기도 화면상 삭제 로직은 동일
        for (const t of trackList.value) {
            const index = t.clips.findIndex(c => c.clipId === data.clipId);
            if (index !== -1) {
                // 잘라낸 원본 클립을 지우기 전에 임시 보관소에 깊은 복사로 저장 (다른 유저가 붙여넣을 때 원본 데이터를 참조하기 위함)
                cutClipsMap.set(data.clipId, JSON.parse(JSON.stringify(t.clips[index])));
                t.clips.splice(index, 1);
                break;
            }
        }
        disposeClipAudio(data.clipId);
    });

    // 2. 클립 붙여넣기 수신 (가장 중요: sourceClipId를 통한 복제)
    socketService.subscribePersistent('CLIP_PASTE', (data) => {
        // 백엔드에서 '어떤 클립을 복사했는지(sourceClipId)'를 알려줌!
        let originalClip: ClipUIState | null = null;
        for (const t of trackList.value) {
            const found = t.clips.find(c => c.clipId === data.sourceClipId);
            if (found) { originalClip = found; break; }
        }
        // 잘라내기(Cut)의 경우 화면에서 이미 삭제되었으므로 내 로컬 클립보드에서 찾습니다.
        if (!originalClip && clipboardClip.value && clipboardClip.value.clipId === data.sourceClipId) {
            originalClip = clipboardClip.value;
        }
        // 내가 자른게 아니고 다른 사람이 자른 클립이라면, 임시 보관소(cutClipsMap)에서 찾습니다.
        if (!originalClip && cutClipsMap.has(data.sourceClipId)) {
            originalClip = cutClipsMap.get(data.sourceClipId) || null;
        }

        if (!originalClip) {
            // console.error(`[에러] 붙여넣기 할 원본 클립(ID: ${data.sourceClipId})을 화면에서 찾을 수 없습니다!`);
            return;
        }

        const targetTrack = trackList.value.find(t => t.trackId === data.targetTrackId);
        if (!targetTrack) return;

        // 원본 클립을 완벽하게 복제(Deep Copy)한 뒤, 백엔드가 지정해준 위치와 ID만 변경
        const pastedClip: ClipUIState = {
            ...JSON.parse(JSON.stringify(originalClip)),
            clipId: data.clipId,
            start: data.targetStartBar,
            audio: originalClip.audio ? { ...originalClip.audio } : undefined,
            isSelected: false,
            isDragging: false,
            isLocked: false
        };
        targetTrack.clips.push(pastedClip);
        checkAndExpandTimeline(pastedClip.start + pastedClip.duration);
        // [원복] 오디오 플레이어 미리 로드 (끊김 방지)
        loadClipPlayer(pastedClip, data.targetTrackId);

        let isInitiator = false;
        if (pendingPasteCount.value > 0) {
            pendingPasteCount.value--;
            isInitiator = true;
        }
        resolveClipOverlap(pastedClip, targetTrack, isInitiator);

        // 화면 렌더링이 무사히 끝난 후 잘라내기 클립보드 비우기
        if (isCutAction.value) {
            clipboardClip.value = null;
            isCutAction.value = false;
        }

        if (isInitiator) {
            const newClipId = data.clipId;
            const targetTrackId = data.targetTrackId;
            pushCommand({
                undo: () => {
                    // 붙여넣기 취소: 방금 붙여넣은 클립 삭제
                    lockClip(newClipId, targetTrackId);
                    setTimeout(() => {
                        socketService.publish('CLIP_DELETE', {
                            projectId: projectInfo.value.projectId,
                            clipId: newClipId
                        });
                        setTimeout(() => unlockClip(newClipId, targetTrackId), 100);
                    }, 100);
                },
                redo: () => {
                    // 붙여넣기 리두: 원래 붙여넣기 로직 재실행 (편의상 알림 제공)
                    useAlertStore().showAlert("되돌린 클립은 클립보드에서 다시 붙여넣기(Ctrl+V) 해주세요.", "info");
                }
            });
        }
    });

    // 내가 복제/붙여넣기 요청한 건인지 확인하기 위한 로컬 상태
    const pendingPasteCount = ref(0);

    // 3. 클립 복제 수신
    socketService.subscribePersistent('CLIP_DUPLICATE', (data) => {
        let originalClip: ClipUIState | null = null;
        for (const t of trackList.value) {
            const found = t.clips.find(c => c.clipId === data.clipId);
            if (found) { originalClip = found; break; }
        }
        if (!originalClip) return;
        const targetTrack = trackList.value.find(t => t.trackId === data.targetTrackId);
        if (!targetTrack) return;
        const duplicatedClip: ClipUIState = {
            ...JSON.parse(JSON.stringify(originalClip)),
            clipId: data.newClipId,
            start: data.targetStartBar,
            audio: originalClip.audio ? { ...originalClip.audio } : undefined,
            isSelected: false,
            isDragging: false,
            isLocked: false
        };
        targetTrack.clips.push(duplicatedClip);
        checkAndExpandTimeline(duplicatedClip.start + duplicatedClip.duration);
        // [원복] 오디오 플레이어 미리 로드 (끊김 방지)
        loadClipPlayer(duplicatedClip, data.targetTrackId);

        // 내가 복제 요청을 보낸 클립이라면 백엔드가 새 클립에 강제로 건 락을 해제
        const isInitiator = pendingDuplicateOriginalClipIds.has(data.clipId);
        if (isInitiator) {
            pendingDuplicateOriginalClipIds.delete(data.clipId);
            // 소켓 통신을 통해 새 클립(newClipId)의 잠금을 즉시 해제 요청
            socketService.publish('CLIP_LOCK', {
                projectId: projectInfo.value.projectId,
                clipId: data.newClipId,
                isLocked: false
            });

            const newClipId = data.newClipId;
            const targetTrackId = data.targetTrackId;
            pushCommand({
                undo: () => {
                    // 복제 취소: 방금 복제된 클립 삭제
                    lockClip(newClipId, targetTrackId);
                    setTimeout(() => {
                        socketService.publish('CLIP_DELETE', {
                            projectId: projectInfo.value.projectId,
                            clipId: newClipId
                        });
                        setTimeout(() => unlockClip(newClipId, targetTrackId), 100);
                    }, 100);
                },
                redo: () => {
                    // 복제 리두는 지원하지 않음
                    useAlertStore().showAlert("되돌린 클립은 다시 복제(Alt+Drag) 해주세요.", "info");
                }
            });
        }

        // 겹침 방지: 생성된 클립이 기존 클립과 겹치면 끝나는 위치 바로 뒤로 밀어냅니다.
        resolveClipOverlap(duplicatedClip, targetTrack, isInitiator);
    });
    // 4. 클립 분할 수신
    socketService.subscribePersistent('CLIP_SPLIT', async (data) => {
        let targetTrack: TrackUIState | null = null;
        let originalClip: ClipUIState | null = null;

        for (const t of trackList.value) {
            const found = t.clips.find(c => c.clipId === data.clipId);
            if (found) { originalClip = found; targetTrack = t; break; }
        }

        const isInitiator = pendingSplitOriginalClipIds.has(data.clipId);

        // 분할 응답이 왔으므로 대기 목록에서 제거
        pendingSplitOriginalClipIds.delete(data.clipId);

        if (!originalClip || !targetTrack) return;

        // 원본 클립의 분할 전 상태 백업 (언두용)
        const origDuration = originalClip.duration;
        const origAudioDurationMs = originalClip.audioDurationMs;

        // 재생 중이었다면 멈추고 안전하게 쪼개기 진행
        const wasPlaying = isPlaying.value;
        let pausedAtSeconds = 0;
        if (wasPlaying) {
            pausedAtSeconds = Tone.getTransport().seconds;
            Tone.getTransport().pause();
            isPlaying.value = false;
            if (animationFrameId) cancelAnimationFrame(animationFrameId);
            if (scrollRAFId) cancelAnimationFrame(scrollRAFId);
        }

        const splitOffsetBars = data.splitBar - originalClip.start;
        const splitOffsetMs = splitOffsetBars * (originalClip.audioDurationMs / originalClip.duration);
        // 백엔드 명세에 맞춰서 오른쪽 새 클립 생성
        // 주의: JSON.parse(stringify) 과정에서 audio 객체의 참조 무결성이 깨지거나 값이 유실될 수 있으므로 명시적 얕은 복사본을 할당합니다.
        const rightClip: ClipUIState = {
            ...JSON.parse(JSON.stringify(originalClip)),
            clipId: data.newClipId,
            start: data.splitBar,
            duration: data.newClipDuration,
            audioStartMs: originalClip.audioStartMs + splitOffsetMs,
            audioDurationMs: Math.max(0, originalClip.audioDurationMs - splitOffsetMs),
            audio: originalClip.audio ? { ...originalClip.audio } : undefined,
            isLocked: false,     // 분할로 새로 생긴 클립은 잠금 해제 상태로 초기화
            isDragging: false,
            isSelected: false
        };
        // 왼쪽 원본 클립 길이 수정
        originalClip.duration = data.originalDuration;
        originalClip.audioDurationMs = splitOffsetMs;
        targetTrack.clips.push(rightClip);
        // 왼쪽 클립 오디오 재설정 (resyncClip 내부 로직이 동작)
        resyncClip(originalClip.clipId, originalClip.start);

        // [원복] 오디오 플레이어 미리 로드
        loadClipPlayer(rightClip, targetTrack.trackId);

        // 분할 작업 완료 후 재생 재개
        if (wasPlaying) {
            Tone.getTransport().start("+0.05", pausedAtSeconds);
            isPlaying.value = true;
            updatePlayheadLoop();
            scrollAnimationLoop();
        }

        // 내가 요청한 분할인 경우에만 언두 스택에 등록
        if (isInitiator) {
            const origClipId = originalClip.clipId;
            const newClipId = data.newClipId;
            const trackId = targetTrack.trackId;

            pushCommand({
                undo: () => {
                    // 새로 생긴 조각(오른쪽) 삭제
                    lockClip(newClipId, trackId);
                    setTimeout(() => {
                        socketService.publish('CLIP_DELETE', {
                            projectId: projectInfo.value.projectId,
                            clipId: newClipId
                        });
                        setTimeout(() => unlockClip(newClipId, trackId), 100);
                    }, 100);

                    // 원본 클립(왼쪽) 길이 원복 (리사이즈)
                    lockClip(origClipId, trackId);
                    const clipToRestore = targetTrack?.clips.find(c => c.clipId === origClipId);
                    if (clipToRestore) {
                        clipToRestore.duration = origDuration;
                        clipToRestore.audioDurationMs = origAudioDurationMs;
                        resyncClip(origClipId, clipToRestore.start);
                        setTimeout(() => {
                            socketService.publish('CLIP_RESIZE', {
                                projectId: projectInfo.value.projectId,
                                clipId: origClipId,
                                startBar: clipToRestore.start,
                                length: origDuration
                            });
                            setTimeout(() => unlockClip(origClipId, trackId), 100);
                        }, 100);
                    }
                },
                redo: () => {
                    // 다시 분할 실행 (단, 새 ID가 부여될 것이므로 완벽한 리두는 아님. 현재는 편의상 호출)
                    lockClip(origClipId, trackId);
                    setTimeout(() => {
                        socketService.publish('CLIP_SPLIT', {
                            projectId: projectInfo.value.projectId,
                            clipId: origClipId,
                            splitBar: data.splitBar
                        });
                        setTimeout(() => unlockClip(origClipId, trackId), 100);
                    }, 100);
                }
            });
        }
    });
    // 5. 클립 복사 및 잘라내기 응답 
    socketService.subscribePersistent('CLIP_COPY', (data) => {
        // console.log(`[통신] 백엔드 클립보드에 복사 완료 (clipId: ${data.clipId})`);
    });

    // ==========================================
    // 3. 액션(Action) 선언 (웹소켓 발신 및 UI 렌더링)
    // ==========================================

    // 실제 오디오 파일 업로드 & 클립 추가 Action
    const uploadAndAddAudioClip = async (file: File, trackId: number, startBar: number) => {
        // console.log(`========== [Upload & Add Clip Start (Pessimistic UI)] ==========`);
        uploadingTrackId.value = trackId;
        uploadingBar.value = startBar;

        // 1. 로컬 파일을 AudioBuffer로 디코딩 (길이 측정 + 캐시 사전 적재를 한 번에 처리)
        //    → 기존에는 Tone.Player로 임시 로드 후 dispose했지만, 이제는 AudioBuffer를 캐시에 보관하여
        //      CLIP_CREATE 수신 시 네트워크 왕복 없이 즉시 재생/파형 표시가 가능합니다.
        const localBlobUrl = URL.createObjectURL(file);
        let durationMs: number;
        try {
            const localBuffer = await fetchAndCacheAudioBuffer(localBlobUrl);
            durationMs = Math.round(localBuffer.duration * 1000);
        } catch (e) {
            // console.error(`[Upload] 로컬 파일 디코딩 실패:`, e);
            URL.revokeObjectURL(localBlobUrl);
            uploadingTrackId.value = null;
            uploadingBar.value = null;
            return;
        }
        // ⚠️ revokeObjectURL은 하지 않습니다. 캐시에 blobUrl 키로 보관되어 있으므로
        //    CLIP_CREATE에서 CDN URL이 도착하면 그때 blobUrl 캐시를 CDN URL 키로 이전합니다.

        // 2. 파일 타입에 따른 MIME 타입 및 포맷팅 설정
        const mimeType = file.type.includes('wav') ? 'WAV' : 'MPEG';

        try {
            // 3. 백엔드 API를 통해 S3 Presigned URL(티켓) 발급
            const uploadTicket = await projectApi.getAudioUploadUrl(projectInfo.value.projectId, {
                originalName: file.name,
                mimeType: mimeType,
                sizeBytes: file.size
            });
            // 4. 발급받은 Presigned URL을 사용하여 S3로 직접 파일 전송 (PUT)
            await axios.put(uploadTicket.uploadUrl, file, {
                headers: {
                    'Content-Type': file.type
                }
            });

            // console.log(`[Upload] S3 파일 업로드 완료 (objectKey: ${uploadTicket.objectKey})`);
            // 5. 웹소켓으로 클립 생성(CLIP_CREATE) 브로드캐스트 요청 (현재 합의된 백엔드 스펙)
            socketService.publish('CLIP_CREATE', {
                projectId: projectInfo.value.projectId,
                trackId: trackId,
                startBar: startBar,
                color: "#" + Math.floor(Math.random() * 16777215).toString(16),
                objectKey: uploadTicket.objectKey,
                originalName: file.name,
                storedName: uploadTicket.storedName,
                mimeType: mimeType,
                sizeBytes: file.size,
                durationMs: durationMs,
                // [최적화] 업로더 본인의 CLIP_CREATE 수신부에서 CDN URL 대신 사용할 로컬 blob URL
                _localBlobUrl: localBlobUrl
            });

            // console.log(`[Upload] 백엔드로 CLIP_CREATE 발신 완료. 렌더링은 브로드캐스트 수신 후 진행됩니다.`);
            // 프론트엔드 로직 종료 (렌더링은 수신부에서 일괄 처리)
        } catch (error) {
            // console.error(`[Upload Error] 업로드 또는 클립 생성 요청 실패:`, error);
            URL.revokeObjectURL(localBlobUrl);
            useAlertStore().showAlert("파일 업로드에 실패했습니다.", "error");
            uploadingTrackId.value = null;
            uploadingBar.value = null;
        }
    };
    // 1. 복사
    const copyClip = (clip: ClipUIState, trackId: number) => {
        // 프론트 클립보드 저장
        clipboardClip.value = JSON.parse(JSON.stringify(clip));
        clipboardTrackId.value = trackId;
        isCutAction.value = false;
        // 서버 클립보드 동기화
        socketService.publish('CLIP_COPY', {
            projectId: projectInfo.value.projectId,
            clipId: clip.clipId
        });
    };

    // 잘라내기
    const cutClip = (clip: ClipUIState, trackId: number) => {
        clipboardClip.value = { ...JSON.parse(JSON.stringify(clip)), clipId: clip.clipId };
        clipboardTrackId.value = trackId;
        isCutAction.value = true;
        // Lock → 액션 → Unlock (백엔드가 Lock 소유를 검증함)
        lockClip(clip.clipId, trackId);
        setTimeout(() => {
            socketService.publish('CLIP_CUT', {
                projectId: projectInfo.value.projectId,
                clipId: clip.clipId
            });
            setTimeout(() => unlockClip(clip.clipId, trackId), 100);
        }, 100);

        pushCommand({
            undo: () => {
                useAlertStore().showAlert("잘라낸 클립은 되돌릴 수 없습니다.", "warning");
            },
            redo: () => {
                // do nothing
            }
        });
    };


    // 3. 붙여넣기
    const pasteClip = async (targetTrackId: number, startBar: number) => {
        // 함수 시작하자마자 현재 클립보드 데이터를 일반 변수에 안전하게 빼두기
        const clipDataToPaste = clipboardClip.value;
        if (!clipDataToPaste) return;

        const targetTrack = trackList.value.find(t => t.trackId === targetTrackId);
        if (!targetTrack) return;

        // 1. 겹침 방지 계산 (기존과 동일하게 프론트에서 최적의 위치를 미리 찾아둠)
        let resolvedStart = startBar;
        const duration = clipDataToPaste.duration;
        let hasOverlap = true;
        const epsilon = 0.001;
        let safetyCounter = 0;

        const isSpaceClear = (targetStart: number, dur: number) => {
            if (targetStart < 0) return false;
            const targetEnd = targetStart + dur;
            for (const c of targetTrack.clips) {
                if (targetStart < c.start + c.duration - epsilon && targetEnd > c.start + epsilon) {
                    return false;
                }
            }
            return true;
        };

        while (hasOverlap && safetyCounter < 100) {
            hasOverlap = false;
            safetyCounter++;
            for (const clip of targetTrack.clips) {
                const existingStart = clip.start;
                const existingEnd = clip.start + clip.duration;
                const desiredEnd = resolvedStart + duration;

                if (resolvedStart < existingEnd - epsilon && desiredEnd > existingStart + epsilon) {
                    hasOverlap = true;
                    const dropCenter = resolvedStart + (duration / 2);
                    const existingCenter = existingStart + (clip.duration / 2);
                    let placedFront = false;

                    if (dropCenter <= existingCenter) {
                        const proposedStart = existingStart - duration;
                        if (isSpaceClear(proposedStart, duration)) {
                            resolvedStart = proposedStart;
                            placedFront = true;
                        }
                    }
                    if (!placedFront) {
                        resolvedStart = existingEnd;
                    }
                    break;
                }
            }
        }

        // console.log(`[통신] 백엔드에 붙여넣기(CLIP_PASTE) 요청 전송`);
        pendingPasteCount.value++;
        socketService.publish('CLIP_PASTE', {
            projectId: projectInfo.value.projectId,
            targetTrackId: targetTrackId,
            targetStartBar: resolvedStart
        });

        // 3. 붙여넣기 완료 시 잔상 제거 (초기화)
        if (isCutAction.value) {
            isCutAction.value = false;
            clipboardClip.value = null;
            clipboardTrackId.value = null;
        }
    };

    // 삭제
    const deleteClip = (clipId: number, trackId: number) => {
        // console.log(`[통신] 백엔드에 클립 삭제(CLIP_DELETE) 요청 전송`);
        // Lock → 액션 → Unlock (백엔드가 Lock 소유를 검증함)
        lockClip(clipId, trackId);
        setTimeout(() => {
            socketService.publish('CLIP_DELETE', {
                projectId: projectInfo.value.projectId,
                clipId: clipId
            });
            setTimeout(() => unlockClip(clipId, trackId), 100);
        }, 100);

        pushCommand({
            undo: () => {
                useAlertStore().showAlert("삭제한 클립은 되돌릴 수 없습니다.", "warning");
            },
            redo: () => {
                // do nothing
            }
        });
    };

    // 4. 클립 복제 (Duplicate)
    const duplicateClip = (clip: ClipUIState, trackId: number) => {
        // console.log(`[통신] 백엔드에 클립 복제(CLIP_DUPLICATE) 요청 전송`);
        // Lock → 액션 → Unlock (백엔드가 Lock 소유를 검증함)
        lockClip(clip.clipId, trackId);
        pendingDuplicateOriginalClipIds.add(clip.clipId);
        socketService.publish('CLIP_DUPLICATE', {
            projectId: projectInfo.value.projectId,
            clipId: clip.clipId
        });
        unlockClip(clip.clipId, trackId);
    };
    // 서버 응답 대기 중인 클립 ID 목록 (네트워크 지연 시 연속 분할 방지용)
    const pendingSplitOriginalClipIds = new Set<number>();

    let lastSplitTime = 0;

    // 5. 클립 분할 (Split)
    const splitClip = async (clipId: number, trackId: number) => {
        const now = Date.now();
        if (now - lastSplitTime < 500) {
            // console.warn("분할 요청이 너무 빠릅니다. (연속 입력 방지)");
            return;
        }

        if (pendingSplitOriginalClipIds.has(clipId)) {
            // console.warn("이전 분할 요청이 처리 중입니다. (네트워크 대기)");
            return;
        }

        lastSplitTime = now;
        const track = trackList.value.find(t => t.trackId === trackId);
        if (!track) return;

        const clipIndex = track.clips.findIndex(c => c.clipId === clipId);
        const originalClip = track.clips[clipIndex];
        if (!originalClip) return;

        const currentBar = playheadPosition.value;

        const EPSILON = 0.0001; // 부동소수점 오차 방어
        if (currentBar <= originalClip.start + EPSILON || currentBar >= originalClip.start + originalClip.duration - EPSILON) {
            useAlertStore().showAlert("재생바(Playhead)가 클립 위에 있어야 분할할 수 있습니다.", "warning");
            return;
        }

        // console.log(`[통신] 클립 분할(CLIP_SPLIT) 요청 전송`);
        // Lock → 액션 → Unlock (백엔드가 Lock 소유를 검증함)
        lockClip(clipId, trackId);
        pendingSplitOriginalClipIds.add(clipId);
        socketService.publish('CLIP_SPLIT', {
            projectId: projectInfo.value.projectId,
            clipId: clipId,
            splitBar: currentBar
        });
        unlockClip(clipId, trackId);
    };

    // 6. 클립 길이 조절 (Resize / Trim)
    const resizeClip = (clipId: number, trackId: number, newStart: number, newDuration: number, trimLeftBars: number, origStart?: number, origDuration?: number, origAudioStartMs?: number) => {
        // console.log(`[통신] 클립 리사이즈(CLIP_RESIZE) 요청 전송`);
        socketService.publish('CLIP_RESIZE', {
            projectId: projectInfo.value.projectId,
            clipId: clipId,
            startBar: newStart,
            length: newDuration
        });

        if (origStart !== undefined && origDuration !== undefined && origAudioStartMs !== undefined) {
            // 리사이즈 시점의 클립에서 원본 오디오 비율(ms/bar)을 캡처
            // BPM이 나중에 바뀌어도 이 비율은 항상 원본 오디오의 물리적 비율을 유지
            const clip = trackList.value.flatMap(t => t.clips).find(c => c.clipId === clipId);
            const capturedMsPerBar = clip ? clip.audioDurationMs / clip.duration : origDuration > 0 ? (origDuration * 2000 / origDuration) : 2000;

            pushCommand({
                undo: () => {
                    const track = trackList.value.find(t => t.trackId === trackId);
                    const clip = track?.clips.find(c => c.clipId === clipId);
                    if (clip) {
                        lockClip(clipId, trackId);
                        clip.start = origStart;
                        clip.duration = origDuration;
                        clip.audioStartMs = origAudioStartMs;
                        clip.audioDurationMs = origDuration * capturedMsPerBar;
                        resyncClip(clipId, origStart);
                        setTimeout(() => {
                            socketService.publish('CLIP_RESIZE', {
                                projectId: projectInfo.value.projectId,
                                clipId: clipId,
                                startBar: origStart,
                                length: origDuration
                            });
                            setTimeout(() => unlockClip(clipId, trackId), 100);
                        }, 100);
                    }
                },
                redo: () => {
                    const track = trackList.value.find(t => t.trackId === trackId);
                    const clip = track?.clips.find(c => c.clipId === clipId);
                    if (clip) {
                        lockClip(clipId, trackId);
                        clip.start = newStart;
                        clip.duration = newDuration;
                        clip.audioStartMs = origAudioStartMs + trimLeftBars * capturedMsPerBar;
                        clip.audioDurationMs = newDuration * capturedMsPerBar;
                        resyncClip(clipId, newStart);
                        setTimeout(() => {
                            socketService.publish('CLIP_RESIZE', {
                                projectId: projectInfo.value.projectId,
                                clipId: clipId,
                                startBar: newStart,
                                length: newDuration
                            });
                            setTimeout(() => unlockClip(clipId, trackId), 100);
                        }, 100);
                    }
                }
            });
        }
    };

    // ==========================================
    // 트랙 관련 액션
    // ==========================================
    //마스터 트랙 (수정 불가, 고정 렌더링)
    const masterTrack = ref<TrackUIState>({
        trackId: 999999,
        name: "마스터 트랙",
        type: "AUDIO",
        preTrackId: null,
        postTrackId: null,
        volume: 0,
        pan: 0,
        isMuted: false,
        isSoloed: false,
        clips: [],
        height: 100,
        isSelected: false,
        eq: createDefaultTrackEq(),
    });

    // 일반 트랙에 변화가 생길 때마다 마스터 트랙에 실시간 병합!
    // [최적화] JSON.parse(JSON.stringify())를 제거하고 필요한 속성만 얕은 복사합니다.
    // 기존 방식은 300개 트랙의 클립을 모두 직렬화→역직렬화하면서 메인 스레드를 수십ms 블로킹했습니다.
    watch(() => trackList.value, (newTrackList) => {
        const mergedClips: ClipUIState[] = [];

        newTrackList.forEach(track => {
            track.clips.forEach(clip => {
                mergedClips.push({
                    clipId: clip.clipId + 9000000,
                    start: clip.start,
                    duration: clip.duration,
                    audioStartMs: clip.audioStartMs,
                    audioDurationMs: clip.audioDurationMs,
                    color: '#4b4b4b',
                    audio: clip.audio ? { ...clip.audio } : undefined as any,
                    isSelected: false,
                    isDragging: false,
                    isLocked: false,
                });
            });
        });

        masterTrack.value.clips = mergedClips;
    }, { deep: true, immediate: true });

    // 트랙 추가 요청 로컬 상태
    const pendingTrackAddCount = ref(0);

    //새로운 트랙 추가 액션
    const addTrack = () => {
        const newTrackName = `트랙 ${trackList.value.length + 1}`;
        //  console.log(`[통신] 트랙 추가(TRACK_ADD) 요청 전송`);

        pendingTrackAddCount.value++;
        socketService.publish('TRACK_ADD', {
            projectId: projectInfo.value.projectId,
            name: newTrackName,
            type: "audio"
        });
    };

    // ==========================================
    // 오디오 출력 상태 동기화 (Solo / Mute 통합 관리)
    // ==========================================
    const syncEffectiveMuteStates = () => {
        const isAnySoloed = trackList.value.some(t => t.isSoloed);

        trackList.value.forEach(t => {
            const vol = trackVolumes.get(t.trackId);
            if (vol) {
                if (isAnySoloed) {
                    // ?�로 모드???? ?�재 ?�랙???�로가 ?�니거나, ?��? ?�로?�라??명시?�으�??�소거된 ?�태�??�리�??�니??
                    vol.mute = !t.isSoloed || t.isMuted;
                } else {
                    // 솔로 모드가 아닐 때: 트랙의 음소거 상태를 그대로 따릅니다.
                    vol.mute = t.isMuted;
                }
            }
        });
    };

    // 트랙 음소거(Mute) 토글
    const toggleTrackMute = (trackId: number) => {
        if (trackId === 999999) return;
        const track = trackList.value.find(t => t.trackId === trackId);
        if (!track) return;

        track.isMuted = !track.isMuted;
        syncEffectiveMuteStates();

        socketService.publish('TRACK_MUTE_CHANGE', {
            projectId: projectInfo.value.projectId,
            trackId: trackId,
            isMuted: track.isMuted
        });
    };

    // 트랙 솔로(Solo) 토글
    const toggleTrackSolo = (trackId: number) => {
        if (trackId === 999999) return;
        const targetTrack = trackList.value.find(t => t.trackId === trackId);
        if (!targetTrack) return;

        const isTurningOn = !targetTrack.isSoloed;

        if (isTurningOn) {
            trackList.value.forEach(t => {
                if (t.trackId !== trackId && t.isSoloed) {
                    t.isSoloed = false;
                    // solo 상태 변경은 syncEffectiveMuteStates에서 mute로 일괄 처리
                    socketService.publish('TRACK_SOLO_CHANGE', {
                        projectId: projectInfo.value.projectId,
                        trackId: t.trackId,
                        isSoloed: false
                    });
                }
            });
        }

        targetTrack.isSoloed = isTurningOn;

        syncEffectiveMuteStates();

        socketService.publish('TRACK_SOLO_CHANGE', {
            projectId: projectInfo.value.projectId,
            trackId: trackId,
            isSoloed: targetTrack.isSoloed
        });
    };

    // 트랙 볼륨 조절 (-60dB ~ 6dB)
    const setTrackVolume = (trackId: number, volume: number, emitSocket: boolean = true) => {
        if (trackId === 999999) {
            masterTrack.value.volume = volume;
            masterVolume.volume.value = volume;
            return;
        }

        const track = trackList.value.find(t => t.trackId === trackId);
        if (!track) return;

        track.volume = volume;
        const vol = trackVolumes.get(trackId);
        if (vol) vol.volume.value = volume;

        if (emitSocket) {
            socketService.publish('TRACK_VOLUME_CHANGE', {
                projectId: projectInfo.value.projectId,
                trackId: trackId,
                volume: volume
            });
        }
    };

    // 볼륨 UI 0dB 매핑 (80% 지점에 위치)
    const getVolumePercent = (vol: number) => {
        if (vol <= 0) {
            return ((vol + 60) / 60) * 80;
        } else {
            return 80 + (vol / 6) * 20;
        }
    };

    const getVolumeFromPercent = (percent: number) => {
        if (percent <= 80) {
            return (percent / 80) * 60 - 60;
        } else {
            return ((percent - 80) / 20) * 6;
        }
    };

    // 트랙 패닝 조절 (-100 ~ 100)
    const setTrackPan = (trackId: number, pan: number, emitSocket: boolean = true) => {
        // console.log(`[패닝 디버그] setTrackPan 호출! trackId=${trackId}, pan=${pan}`);
        if (trackId === 999999) {
            masterTrack.value.pan = pan;
            masterPanner.pan.value = pan / 100;
            // console.log(`[패닝 디버그] 마스터 패너 적용 완료: masterPanner.pan.value=${masterPanner.pan.value}`);
            return;
        }

        const track = trackList.value.find(t => t.trackId === trackId);
        if (!track) {
            //  console.error(`[패닝 디버그] 트랙을 찾을 수 없음! trackId=${trackId}`);
            return;
        }

        track.pan = pan;
        const panner = trackPanners.get(trackId);
        if (panner) {
            panner.pan.value = pan / 100;
            //  console.log(`[패닝 디버그] 트랙 ${trackId} 패너 적용 완료: panner.pan.value=${panner.pan.value}`);
        } else {
            // console.error(`[패닝 디버그] 트랙 ${trackId}의 panner를 trackPanners Map에서 찾을 수 없음!`);
            // console.log(`[패닝 디버그] 현재 trackPanners 키 목록:`, [...trackPanners.keys()]);
            // console.log(`[패닝 디버그] 현재 trackVolumes 키 목록:`, [...trackVolumes.keys()]);
        }

        if (emitSocket) {
            socketService.publish('TRACK_PAN_CHANGE', {
                projectId: projectInfo.value.projectId,
                trackId: trackId,
                pan: pan
            });
        }
    };

    //트랙 삭제 기능
    const deleteTrack = (trackId: number) => {
        if (trackId === 999999) return;
        // console.log(`[통신] 백엔드에 트랙 삭제(TRACK_DELETE) 요청 전송`);

        socketService.publish('TRACK_DELETE', {
            projectId: projectInfo.value.projectId,
            trackId: trackId
        });

        pushCommand({
            undo: () => {
                useAlertStore().showAlert("트랙 삭제는 되돌릴 수 없습니다.", "warning");
            },
            redo: () => { }
        });
    };

    // 트랙 이름 변경 로직
    const renameTrack = (trackId: number, newName: string) => {
        if (trackId === 999999) return;
        const track = trackList.value.find(t => t.trackId === trackId);
        if (!track || track.name === newName) return;

        track.name = newName; // UI 즉각 반영

        //  console.log(`[통신] 백엔드에 트랙 이름 변경(TRACK_RENAME) 요청 전송`);
        socketService.publish('TRACK_RENAME', {
            projectId: projectInfo.value.projectId,
            trackId: trackId,
            name: newName
        });
    };

    // 트랙 순서 변경 로직
    const reorderTrack = (draggedTrackId: number, targetIndex: number) => {
        if (draggedTrackId === 999999) return;

        const draggedIndex = trackList.value.findIndex(t => t.trackId === draggedTrackId);
        if (draggedIndex === -1 || draggedIndex === targetIndex) return;

        const [track] = trackList.value.splice(draggedIndex, 1);
        trackList.value.splice(targetIndex, 0, track);

        const preTrackId = targetIndex > 0 ? trackList.value[targetIndex - 1].trackId : null;
        const postTrackId = targetIndex < trackList.value.length - 1 ? trackList.value[targetIndex + 1].trackId : null;

        //  console.log(`[통신] 백엔드에 트랙 순서 변경(TRACK_REORDER) 요청 전송`);
        socketService.publish('TRACK_REORDER', {
            projectId: projectInfo.value.projectId,
            trackId: draggedTrackId,
            preTrackId: preTrackId,
            postTrackId: postTrackId
        });
    };

    // ==========================================
    // 3. 액션(Action) 선언(데이터 패칭 및 가공)
    // ==========================================

    // 드래그 앤 드롭 종료 시 서버 확정 통신
    const confirmMoveClip = (clipId: number, targetTrackId: number, targetStartBar: number, origTrackId?: number, origStartBar?: number) => {
        // console.log(`[통신] 백엔드에 클립 이동(CLIP_MOVE) 요청 전송`);

        socketService.publish('CLIP_MOVE', {
            projectId: projectInfo.value.projectId,
            clipId: clipId,
            targetTrackId: targetTrackId,
            targetStartBar: targetStartBar
        });

        if (origTrackId !== undefined && origStartBar !== undefined) {
            pushCommand({
                undo: () => {
                    const targetTrack = trackList.value.find(t => t.trackId === targetTrackId);
                    if (!targetTrack) return;
                    const clip = targetTrack.clips.find(c => c.clipId === clipId);
                    if (clip) {
                        lockClip(clipId, origTrackId);
                        moveClipToTrack(clipId, targetTrackId, origTrackId);
                        clip.start = origStartBar;
                        resyncClip(clipId, origStartBar);
                        setTimeout(() => {
                            socketService.publish('CLIP_MOVE', {
                                projectId: projectInfo.value.projectId,
                                clipId: clipId,
                                targetTrackId: origTrackId,
                                targetStartBar: origStartBar
                            });
                            setTimeout(() => unlockClip(clipId, origTrackId), 100);
                        }, 100);
                    }
                },
                redo: () => {
                    const origTrack = trackList.value.find(t => t.trackId === origTrackId);
                    if (!origTrack) return;
                    const clip = origTrack.clips.find(c => c.clipId === clipId);
                    if (clip) {
                        lockClip(clipId, targetTrackId);
                        moveClipToTrack(clipId, origTrackId, targetTrackId);
                        clip.start = targetStartBar;
                        resyncClip(clipId, targetStartBar);
                        setTimeout(() => {
                            socketService.publish('CLIP_MOVE', {
                                projectId: projectInfo.value.projectId,
                                clipId: clipId,
                                targetTrackId: targetTrackId,
                                targetStartBar: targetStartBar
                            });
                            setTimeout(() => unlockClip(clipId, targetTrackId), 100);
                        }, 100);
                    }
                }
            });
        }
    };

    //클립을 다른 트랙으로 이동시키는 함수 (프론트 렌더링 지움, 순수 통신 트리거로 활용 가능)
    const moveClipToTrack = (clipId: number, fromTrackId: number, toTrackId: number) => {
        if (fromTrackId === toTrackId) return;
        // 이제 화면 즉시 반영 로직은 없고, 필요하다면 백엔드 publish를 위임합니다.
        // 드래그 이벤트는 confirmMoveClip에서 처리되므로 비워둡니다.
    };
    // 디버그용 변수 (로그 폭탄 방지용)
    let debugLoopCount = 0;

    let lastTransportSeconds = 0;
    let playbackStartTransportSec = 0;

    //재생 상태 토글 함수
    const togglePlay = () => {
        try {
            if (!isPlaying.value) {
                const offsetTime = playheadPosition.value * secondsPerBar.value;
                playbackStartTransportSec = offsetTime;

                if (!isNaN(offsetTime) && isFinite(offsetTime)) {
                    Tone.getTransport().start("+0.05", offsetTime);
                } else {
                    Tone.getTransport().start("+0.05");
                }

                isAutoScrollActive.value = true;
                isPlaying.value = true;
                updatePlayheadLoop();
                scrollAnimationLoop();
            } else {
                Tone.getTransport().pause();

                // Tone.js 버그 보완: 클립 시작 지점에서 정확히 일시정지 시, 
                // 스케줄링 예약(+0.05) 및 lookAhead로 인해 이미 Web Audio API에 
                // 예약된 오디오 노드가 멈추지 않는 현상(고스트 재생)을 강제로 정지시킵니다.
                clipPlayers.forEach(player => {
                    if (player.state === "started") {
                        player.stop();
                    }
                });

                isAutoScrollActive.value = true;
                isPlaying.value = false;
                if (animationFrameId) cancelAnimationFrame(animationFrameId);
                if (scrollRAFId) cancelAnimationFrame(scrollRAFId);
                // 일시정지 시 시각적 위치를 유지하기 위해 강제 보정을 하지 않습니다.
                // playheadPosition.value는 이미 updatePlayheadLoop에 의해 시각적 지연(latency)이 반영된 상태입니다.
            }
        } catch (e) {
            // console.error("재생 에러:", e);
        }
    };

    // 단일 클립 오디오 플레이어 로딩 함수 (동적 Culling 대신 미리 로드하여 렉 방지)
    // [최적화 & EQ병합] 캐시된 AudioBuffer를 직접 주입하여 중복 네트워크 다운로드+디코딩을 완전 제거하고, EQ 노드 체인 연결
    const loadClipPlayer = async (clip: ClipUIState, trackId: number) => {
        if (!clip.audio?.cdnUrl) return;

        if (!clipPlayers.has(clip.clipId)) {
            try {
                // 1. 최적화: 캐시에서 AudioBuffer를 가져오거나, 없으면 한 번만 fetch+decode
                const audioBuffer = await fetchAndCacheAudioBuffer(clip.audio.cdnUrl);

                // await 후 다른 곳에서 이미 등록했을 수 있으므로 중복 체크
                if (clipPlayers.has(clip.clipId)) return;

                // 2. 최적화: 버퍼를 주입하여 Player 생성 (네트워크 다운로드 및 디코딩 X)
                const newPlayer = new Tone.Player(audioBuffer);
                newPlayer.fadeIn = 0;
                newPlayer.fadeOut = 0;

                // 3. EQ 체인 연결
                connectPlayerToTrack(newPlayer, trackId);

                // Tone.js sync 재생 오프셋 버그 패치 적용
                patchTonePlayerForSync(newPlayer);

                clipPlayers.set(clip.clipId, newPlayer);

                const exactStartTimeSec = clip.start * secondsPerBar.value;
                const audioOffsetSec = clip.audioStartMs / 1000;
                const visualDurationSec = clip.duration * secondsPerBar.value;
                const sourceAudioSec = clip.audioDurationMs / 1000;

                // 패치에서 사용할 원본 오프셋과 길이를 저장
                (newPlayer as any).customOriginalOffset = audioOffsetSec;
                (newPlayer as any).customSourceAudioSec = sourceAudioSec;

                newPlayer.playbackRate = visualDurationSec > 0 ? sourceAudioSec / visualDurationSec : 1;
                // Tone.js는 내부적으로 duration/playbackRate로 실제 재생 길이를 계산하므로
                // sourceAudioSec를 넘기면 정확히 visualDurationSec 만큼 재생 후 정지
                newPlayer.sync().start(exactStartTimeSec, audioOffsetSec, sourceAudioSec);
                // Transport의 상태 관리를 위해 시각적 끝지점에 명시적으로 stop을 등록 (클립 밖으로 재생헤드 이동 시 고스트 재생 방지)
                newPlayer.sync().stop(exactStartTimeSec + visualDurationSec);
            } catch (e) {
                // console.error("[Audio Load Error]:", e);
                disposeClipAudio(clip.clipId); // EQ 기능의 완전 해제 함수 사용
            }
        }
    };

    // [성능 최적화] 재생바 UI 업데이트 루프
    // Vue 반응성(ref) 대신 DOM을 직접 조작하여 초당 1,300회 이상의 Vue re-render를 원천 차단
    let lastReactiveUpdate = 0; // PlayController 디스플레이용 마지막 갱신 시각
    const REACTIVE_UPDATE_INTERVAL = 250; // PlayController(마디/박자 표시)는 250ms마다만 갱신 (4fps)

    // 사용자가 타임라인 스크러빙(드래그)으로 재생바를 옮길 때, 정지 상태라면 즉시 DOM 위치 동기화
    watch(playheadPosition, (newBar) => {
        if (!isPlaying.value) {
            const px = newBar * pixelPerBar.value;
            document.documentElement.style.setProperty('--playhead-px', `${px}px`);

            // updatePlayheadLoop나 stopPlay에서 인라인 transform을 덮어씌웠기 때문에
            // 여기서도 직접 .playhead-line의 transform을 갱신해 주어야 합니다.
            const playheadEls = document.querySelectorAll('.playhead-line') as NodeListOf<HTMLElement>;
            for (let i = 0; i < playheadEls.length; i++) {
                playheadEls[i].style.transform = `translate3d(calc(${px}px - 50%), 0, 0)`;
            }

            // 정지 상태 스크러빙 시 진행 오버레이 갱신
            const clipEls = document.querySelectorAll('.clip-container') as NodeListOf<HTMLElement>;
            for (let i = 0; i < clipEls.length; i++) {
                const clipEl = clipEls[i];
                const clipLeft = parseFloat(clipEl.style.left) || 0;
                const clipWidth = parseFloat(clipEl.style.width) || 0;
                if (clipWidth <= 0) continue;
                const progressPx = Math.max(0, Math.min(px - clipLeft, clipWidth));
                clipEl.style.setProperty('--progress-px', `${progressPx}px`);
            }
        }
    });

    let lastFrameTime = performance.now();
    let loopFrameCount = 0;
    // [최적화] 스크롤 목표값을 별도 변수에 기록하고, 스크롤 쓰기는 독립 루프에서 처리
    let pendingScrollLeft = -1;
    let scrollRAFId = 0;

    // 스크롤 쓰기 전용 독립 루프 (재생바 렌더링 루프와 완전 분리)
    // scrollLeft = value 호출이 브라우저 Layout Reflow를 강제 트리거하여
    // 재생바 애니메이션을 30~40ms씩 멈추게 만드는 것을 방지합니다.
    const scrollAnimationLoop = () => {
        if (!isPlaying.value) return;
        if (pendingScrollLeft >= 0 && timelineContainer) {
            timelineContainer.scrollLeft = pendingScrollLeft;
            pendingScrollLeft = -1;
        }
        scrollRAFId = requestAnimationFrame(scrollAnimationLoop);
    };

    // Long Task 수집 배열
    const longTasks: any[] = [];
    if (typeof window !== 'undefined' && window.PerformanceObserver) {
        try {
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    longTasks.push(entry);
                    if (longTasks.length > 50) longTasks.shift(); // 메모리 누수 방지
                }
            });
            observer.observe({ entryTypes: ['longtask'] });
        } catch (e) {
            //  console.error("Long Task Observer 초기화 실패", e);
        }
    }

    const updatePlayheadLoop = () => {
        if (!isPlaying.value) return;

        loopFrameCount++;
        const loopStart = performance.now();
        const timeSinceLastFrame = loopStart - lastFrameTime;
        lastFrameTime = loopStart;

        // 프레임 드랍 감지 (30ms 이상 지연되면 멈칫거림으로 간주)
        if (timeSinceLastFrame > 30 && loopFrameCount > 10) {
            // console.warn(`🚨 [프레임 드랍 감지] 루프 지연 시간: ${timeSinceLastFrame.toFixed(2)}ms`);

            // Long Task API를 통해 직전에 메인 스레드를 막은 원인을 분석
            if (longTasks.length > 0) {
                const lastTask = longTasks[longTasks.length - 1];
                //                 console.warn(`🔍 [원인 분석] 최근 Long Task 발견: 
                // - 소요 시간: ${lastTask.duration.toFixed(2)}ms
                // - 원인(name): ${lastTask.name}
                // - 발생 시점: ${lastTask.startTime.toFixed(2)}
                // - 기여 요인:`, lastTask.attribution ? lastTask.attribution.map((a: any) => a.name + ' (' + a.containerType + ')').join(', ') : '없음');
            }
        }

        const currentSeconds = Tone.getTransport().seconds;

        // Seek 감지 (타임라인 클릭 등으로 Transport 시간이 크게 점프했을 때)
        if (Math.abs(currentSeconds - lastTransportSeconds) > 0.5) {
            playbackStartTransportSec = currentSeconds;
        }
        lastTransportSeconds = currentSeconds;

        let hardwareLatency = 0;
        if (Tone.context && Tone.context.rawContext) {
            const raw = Tone.context.rawContext as any;
            hardwareLatency = (raw.outputLatency || 0) + (raw.baseLatency || 0);
        }

        // 브라우저 API가 지연 시간을 0 또는 비정상적으로 작게 반환하는 경우(Windows Chrome 등)를 대비해
        // 최소 60ms(0.06초)의 기본 물리적 출력 지연(Fallback)을 보정합니다.
        if (hardwareLatency < 0.03) {
            hardwareLatency = 0.06;
        }

        // 사용자가 설정한 수동 보정값 합산
        hardwareLatency += manualLatencyOffset.value;

        // 레이턴시 보정: 출력 지연 시간만큼 재생바를 뒤로 늦춥니다.
        // 처음 ?�작 ?�치보다 ?�생바�? ?�로 ?�프?�는 것을 방�??�기 ?�해 ?�한값을 ?�정?�니??
        const compensatedSeconds = Math.max(playbackStartTransportSec, currentSeconds - hardwareLatency);

        const currentPositionBar = compensatedSeconds / secondsPerBar.value;
        const px = currentPositionBar * pixelPerBar.value;

        // [최적화] 전역 CSS 변수(--playhead-px)를 :root에 설정하면 브라우저 전체의 Style Recalculation이 발생하여 프레임 드랍이 생깁니다.
        // 현재 가상 스크롤이 적용되어 DOM 노드가 극소수이므로, 직접 주입하는 것이 100배 빠릅니다.
        const playheadEls = document.getElementsByClassName('playhead-line') as HTMLCollectionOf<HTMLElement>;
        for (let i = 0; i < playheadEls.length; i++) {
            playheadEls[i].style.transform = `translate3d(calc(${px}px - 50%), 0, 0)`;
        }

        const clipEls = document.getElementsByClassName('clip-container') as HTMLCollectionOf<HTMLElement>;
        for (let i = 0; i < clipEls.length; i++) {
            clipEls[i].style.setProperty('--playhead-px', `${px}px`);
        }

        // 1-1. 스크롤 위치 계산만 수행 (DOM 쓰기는 scrollAnimationLoop에서 분리 처리)
        if (cachedClientWidth > 0 && isAutoScrollActive.value) {
            const relativeX = px - cachedScrollLeft;
            const threshold = cachedClientWidth * 0.7;
            if (relativeX > threshold) {
                const targetScrollLeft = px - threshold;
                const lerpFactor = 0.12;
                cachedScrollLeft = cachedScrollLeft + (targetScrollLeft - cachedScrollLeft) * lerpFactor;
                pendingScrollLeft = cachedScrollLeft;
            }
        }

        // 2. DOM 직접 업데이트 (Vue 반응성 렌더링 스톰 방지)
        const now = performance.now();
        if (now - lastReactiveUpdate > REACTIVE_UPDATE_INTERVAL) {
            playheadPosition.value = currentPositionBar; // 정지 등 다른 의존성을 위해 값은 갱신해둠
            lastReactiveUpdate = now;

            // DOM을 직접 찾아 텍스트만 교체 (Vue 컴포넌트 렌더 사이클 우회)
            const barTextEl = document.getElementById('playhead-bar-text');
            const beatTextEl = document.getElementById('playhead-beat-text');
            const displayEl = document.getElementById('playhead-position-display');

            if (barTextEl && beatTextEl && projectInfo.value) {
                const numerator = projectInfo.value.timeSigNumerator || 4;
                const bar = Math.floor(currentPositionBar) + 1;
                const beat = Math.floor((currentPositionBar % 1) * numerator) + 1;

                barTextEl.textContent = String(bar).padStart(2, '0');
                beatTextEl.textContent = String(beat);

                if (displayEl) {
                    const total = String(projectInfo.value.totalBarCount).padStart(2, '0');
                    displayEl.setAttribute('aria-label', `현재 재생 위치: ${barTextEl.textContent}마디 ${beat}박자, 전체 ${total}마디`);
                }
            }
        }

        // 현재 루프 실행에 걸린 시간 측정
        const totalLoopTime = performance.now() - loopStart;
        if (totalLoopTime > 15) {
            // console.error(`🐢 [루프 자체 병목] updatePlayheadLoop 실행에 ${totalLoopTime.toFixed(2)}ms 소요!`);
        }

        if (currentPositionBar >= projectInfo.value.totalBarCount) {
            // console.log("⏹️ [재생 종료] 끝까지 도달하여 정지합니다.");
            stopPlay();
            return;
        }

        animationFrameId = requestAnimationFrame(updatePlayheadLoop);
    }

    // 완전 정지 (처음으로 되돌림)
    const stopPlay = () => {
        Tone.getTransport().stop();
        isAutoScrollActive.value = true;
        isPlaying.value = false;
        playheadPosition.value = 0;
        cancelAnimationFrame(animationFrameId);
        if (scrollRAFId) cancelAnimationFrame(scrollRAFId);
        // DOM 직접 조작: 재생바를 처음 위치로 리셋
        const playheadEls = document.querySelectorAll('.playhead-line') as NodeListOf<HTMLElement>;
        for (let i = 0; i < playheadEls.length; i++) {
            playheadEls[i].style.transform = `translate3d(calc(0px - 50%), 0, 0)`;
        }
        // 재생바 오버레이도 모두 리셋
        const clipEls = document.querySelectorAll('.clip-container') as NodeListOf<HTMLElement>;
        for (let i = 0; i < clipEls.length; i++) {
            clipEls[i].style.setProperty('--progress-px', `0px`);
        }

        // 타임라인 스크롤 위치를 맨 처음(0)으로 부드럽게 복귀
        if (timelineContainer) {
            timelineContainer.scrollTo({ left: 0, behavior: 'smooth' });
        }
    };

    //마우스 휠 방향에 따라 줌 배율을 조절하는 함수
    const updateZoom = (deltaY: number) => {
        const zoomStep = 0.1; //한 번 휠을 굴릴 때 변하는 배율(10%)

        if (deltaY > 0) {
            zoomlevel.value = Math.max(0.1, zoomlevel.value - zoomStep);
        } else {
            zoomlevel.value = Math.min(3, zoomlevel.value + zoomStep);
        }
    }

    //오디오 파일 로딩 및 Transport 조절 함수
    const setupAudioEngine = async (tracks: TrackUIState[]) => {
        // console.log("========== [Audio Engine Setup Start] ==========");

        for (const track of tracks) {
            if (!trackVolumes.has(track.trackId)) {
                const panner = new Tone.Panner(track.pan / 100).connect(masterVolume);
                const vol = new Tone.Volume(track.volume).connect(panner);

                panner.channelCount = 2;
                panner.channelCountMode = "explicit";
                vol.channelCount = 2;
                vol.channelCountMode = "explicit";

                trackVolumes.set(track.trackId, vol);
                trackPanners.set(track.trackId, panner);
                // console.log(`[Setup] 트랙 ${track.trackId} ('${track.name}') 믹서 노드 생성 완료. vol:`, vol, "panner:", panner);
            }

            rebuildTrackEqChain(track.trackId);
        }

        for (const track of tracks) {
            const vol = trackVolumes.get(track.trackId);
            if (!vol) continue;

            for (const clip of track.clips) {
                if (!clip.audio?.cdnUrl) {
                    // console.warn(`[Setup ⚠️] 클립 ${clip.clipId}에 오디오 URL이 없어 로딩 건너뜀.`);
                    continue;
                }
                //  console.log(`[Setup] 클립 ${clip.clipId} 오디오 로딩 시도 중...`);
                try {
                    // [최적화] 캐시에서 AudioBuffer를 가져오거나 한 번만 fetch+decode
                    const audioBuffer = await fetchAndCacheAudioBuffer(clip.audio.cdnUrl);

                    // 버퍼를 사용해 Player 생성 (네트워크 다운로드 X)
                    const player = new Tone.Player(audioBuffer);
                    player.fadeIn = 0;
                    player.fadeOut = 0;

                    // EQ 노드를 체인으로 연결
                    connectPlayerToTrack(
                        player,
                        track.trackId,
                    );

                    patchTonePlayerForSync(player);

                    // console.log(`[Setup] 클립 ${clip.clipId} 오디오 로드 성공. (버퍼길이: ${player.buffer.duration.toFixed(2)}초)`);

                    const exactStartTimeSec = clip.start * secondsPerBar.value;
                    const audioOffsetSec = (clip.audioStartMs || 0) / 1000;
                    const visualDurationSec = clip.duration * secondsPerBar.value;
                    const sourceAudioSec = clip.audioDurationMs / 1000;

                    (player as any).customOriginalOffset = audioOffsetSec;
                    (player as any).customSourceAudioSec = sourceAudioSec;

                    player.playbackRate = visualDurationSec > 0 ? sourceAudioSec / visualDurationSec : 1;
                    player.sync().start(exactStartTimeSec, audioOffsetSec, sourceAudioSec);
                    player.sync().stop(exactStartTimeSec + visualDurationSec);
                    clipPlayers.set(clip.clipId, player);
                } catch (error) {
                    // console.error(`[Setup 🚨] 클립 ${clip.clipId} 로드 실패:`, error);
                    disposeClipAudio(clip.clipId);
                }
            }
        }
        
        // 초기 로딩 후 트랙의 mute, solo 상태를 Tone.Volume에 동기화
        syncEffectiveMuteStates();
        // console.log("========== [Audio Engine Setup End] ==========");
    }

    // 프로젝트 진입 시 기존 오디오 자원 완벽 초기화 (유령 오디오, 중복 스케줄링 누수 방지)
    const disposeAllAudio = () => {
        // console.log("========== [Audio Engine Cleanup Start] ==========");
        clipPlayers.forEach((player, clipId) => {
            player.unsync();
            player.dispose();
            // console.log(`[Dispose] 유령 클립 방지: 클립 ${clipId} 오디오 자원 해제 완료`);
        });
        clipPlayers.clear();

        // 트랙 볼륨/패너 노드도 함께 초기화하여 메모리 누수 완벽 차단
        trackVolumes.forEach(vol => vol.dispose());
        trackVolumes.clear();

        trackPanners.forEach(panner => panner.dispose());
        trackPanners.clear();

        // EQ/분석 노드 정리
        trackEqNodes.forEach(nodes => nodes.forEach(node => node.filter.dispose()));
        trackEqNodes.clear();
        trackAnalyzers.forEach(analyzer => analyzer.dispose());
        trackAnalyzers.clear();

        // console.log("========== [Audio Engine Cleanup End] ==========");
    };

    //클립 위치가 변경되었을 때 오디오 엔진 스케줄을 재설정 하는 함수
    const resyncClip = (clipId: number, newStartBar: number) => {
        // console.log(`  └─ [Resync] 클립 ID ${clipId} 재동기화 시작 (새 위치: ${newStartBar}마디)`);

        const player = clipPlayers.get(clipId);
        if (!player) {
            // console.error(`  └─ [Resync 🚨] 클립 ID ${clipId}의 오디오 플레이어를 찾을 수 없습니다! (유령 클립)`);
            return;
        }

        let targetClip: ClipUIState | null = null;
        for (const track of trackList.value) {
            const found = track.clips.find(c => c.clipId === clipId);
            if (found) {
                targetClip = found;
                break;
            }
        }

        if (!targetClip) {
            // console.error(`  └─ [Resync 🚨] 트랙 리스트에서 클립 데이터를 찾을 수 없습니다!`);
            return;
        }

        player.unsync();
        player.stop();

        const exactStartTimeSec = newStartBar * secondsPerBar.value;
        const audioOffsetSec = (targetClip.audioStartMs || 0) / 1000;
        const visualDurationSec = targetClip.duration * secondsPerBar.value;
        const sourceAudioSec = targetClip.audioDurationMs / 1000;

        (player as any).customOriginalOffset = audioOffsetSec;
        (player as any).customSourceAudioSec = sourceAudioSec;

        const rate = visualDurationSec > 0 ? sourceAudioSec / visualDurationSec : 1;
        player.playbackRate = rate;

        if (visualDurationSec > 0) {
            player.sync().start(exactStartTimeSec, audioOffsetSec, sourceAudioSec);
            player.sync().stop(exactStartTimeSec + visualDurationSec);
            //  console.log(`  └─ [Resync] 스케줄링 등록 완료! (상태: 정상)`);
        } else {
            //  console.error(`  └─ [Resync 🚨] 재생 길이(safeDurationSec)가 0 이하입니다! 스케줄링 실패.`);
        }
    };

    // ==========================================
    // BPM 변경 시 전체 클립 재스케줄링
    // ==========================================
    // BPM이 바뀌면 secondsPerBar가 바뀌므로, 이미 player.sync().start()로 등록된
    // 재생 길이(초)가 옛 BPM 기준이라 불일치가 발생합니다.
    // 이 함수는 모든 clipPlayer를 unsync→재계산→재등록하여 동기화합니다.
    const resyncAllClips = () => {
        for (const [clipId, player] of clipPlayers) {
            // 클립 데이터를 trackList에서 역추적
            let targetClip: ClipUIState | null = null;
            for (const track of trackList.value) {
                const found = track.clips.find(c => c.clipId === clipId);
                if (found) {
                    targetClip = found;
                    break;
                }
            }

            if (!targetClip) continue;

            // 기존 스케줄 해제
            player.unsync();
            player.stop();

            // BPM 변경 시 오디오 원본 재생 속도는 유지(1x)하고, 그리드 상의 차지하는 마디 수(duration)만 변환
            const sourceAudioSec = targetClip.audioDurationMs / 1000;
            targetClip.duration = sourceAudioSec / secondsPerBar.value;

            // 새 secondsPerBar 기준으로 시작점 재계산
            const exactStartTimeSec = targetClip.start * secondsPerBar.value;
            const audioOffsetSec = (targetClip.audioStartMs || 0) / 1000;
            const visualDurationSec = sourceAudioSec; // 재생 시간은 항상 원본 길이와 같음

            (player as any).customOriginalOffset = audioOffsetSec;
            (player as any).customSourceAudioSec = sourceAudioSec;

            // 항상 원본 오디오 속도(1x) 유지
            player.playbackRate = 1;

            console.log(`[resyncAll] clipId=${clipId}, rate=1, visualDur=${visualDurationSec.toFixed(2)}s, sourceDur=${sourceAudioSec.toFixed(2)}s, newBarDur=${targetClip.duration.toFixed(2)}`);

            if (visualDurationSec > 0) {
                player.sync().start(exactStartTimeSec, audioOffsetSec, sourceAudioSec);
                player.sync().stop(exactStartTimeSec + visualDurationSec);
            }
        }
    };

    const addTrackEqBand = (
        trackId: number,
        payload: {
            frequencyHz: number
            gainDeltaDb: number
        },
    ) => {
        const track = trackList.value.find(track => track.trackId === trackId)
        if (!track) return

        const currentBands = track.eq?.bands ?? []

        if (currentBands.length >= MAX_EQ_BANDS) {
            //  console.warn('EQ 밴드는 최대 5개까지만 추가할 수 있습니다.')
            return
        }

        const nextBandOrder =
            currentBands.length > 0
                ? Math.max(...currentBands.map(band => band.bandOrder)) + 1
                : 1

        const nextBand: TrackEqBandState = {
            bandOrder: nextBandOrder,
            eqTypeCode: 1,
            frequencyHz: clampFrequency(payload.frequencyHz),
            q: 1,
            gainDeltaDb: clampGain(payload.gainDeltaDb),
            sourceTypeCode: 2,
            jobId: null,
            suggestionActionId: null,
            appliedSuggestionId: null,
        }

        track.eq = {
            bands: [
                ...currentBands,
                nextBand,
            ],
        }

        rebuildTrackEqChain(trackId)
    }

    const updateTrackEqBand = (
        trackId: number,
        bandOrder: number,
        patch: Partial<TrackEqBandState>,
    ) => {
        const track = trackList.value.find(track => track.trackId === trackId)
        if (!track?.eq) return

        const nextBands = track.eq.bands.map((band): TrackEqBandState => {
            if (band.bandOrder !== bandOrder) return band

            return {
                ...band,
                ...patch,
                frequencyHz: patch.frequencyHz !== undefined
                    ? clampFrequency(patch.frequencyHz)
                    : band.frequencyHz,
                gainDeltaDb: patch.gainDeltaDb !== undefined
                    ? clampGain(patch.gainDeltaDb)
                    : band.gainDeltaDb,
                q: patch.q !== undefined
                    ? clampQ(patch.q)
                    : band.q,
            }
        })

        const updatedBand = nextBands.find(band => band.bandOrder === bandOrder)

        if (!updatedBand) return

        track.eq = {
            bands: nextBands,
        }

        const nodes = trackEqNodes.get(trackId)
        const targetNode = nodes?.find(node => node.bandOrder === bandOrder)

        if (targetNode) {
            targetNode.filter.frequency.rampTo(updatedBand.frequencyHz, 0.03)
            targetNode.filter.gain.rampTo(updatedBand.gainDeltaDb, 0.03)
            targetNode.filter.Q.value = updatedBand.q
        }
        else {
            rebuildTrackEqChain(trackId)
        }
    }

    const removeTrackEqBand = (
        trackId: number,
        bandOrder: number,
    ) => {
        const track = trackList.value.find(track => track.trackId === trackId)
        if (!track?.eq) return

        const nextBands = track.eq.bands
            .filter(band => band.bandOrder !== bandOrder)
            .map((band, index) => ({
                ...band,
                bandOrder: index + 1,
            }))

        track.eq = {
            bands: nextBands,
        }

        rebuildTrackEqChain(trackId)
    }

    const setTrackEqBands = (
        trackId: number,
        bands: TrackEqBandState[],
    ) => {
        const track = trackList.value.find(track => track.trackId === trackId)
        if (!track) return

        const nextBands = bands
            .slice(0, MAX_EQ_BANDS)
            .map((band, index): TrackEqBandState => ({
                ...band,
                bandOrder: index + 1,
                eqTypeCode:
                    band.eqTypeCode === 2 || band.eqTypeCode === 3
                        ? band.eqTypeCode
                        : 1,
                frequencyHz: clampFrequency(band.frequencyHz),
                q: clampQ(band.q),
                gainDeltaDb: clampGain(band.gainDeltaDb),
                sourceTypeCode: band.sourceTypeCode ?? 4,
                jobId: band.jobId ?? null,
                suggestionActionId: band.suggestionActionId ?? null,
                appliedSuggestionId: band.appliedSuggestionId ?? null,
            }))

        track.eq = {
            bands: nextBands,
        }

        rebuildTrackEqChain(trackId)
    }

    const getTrackSpectrum = (trackId: number): number[] => {
        const analyzer = trackAnalyzers.get(trackId)

        if (!analyzer) return []

        const values = analyzer.getValue()

        return Array.from(values).map(value => {
            if (typeof value !== 'number') return -100
            if (!Number.isFinite(value)) return -100
            return value
        })
    }

    // 비동기 함수를 선언 ref 반응형
    const isLoading = ref(true);
    const fetchProject = async (projectId: number) => {
        try {
            isLoading.value = true;
            // 새 프로젝트 방에 들어올 때 기존 오디오 엔진의 찌꺼기(유령 플레이어)를 모두 파기
            disposeAllAudio();

            // 기존 상태(트랙 목록, 프로젝트 정보 등)를 초기화하여
            // 새 프로젝트 렌더링 전에 이전 프로젝트의 잔여 트랙이 표시되는 버그(Race Condition)를 완벽히 차단합니다.
            trackList.value = [];
            projectInfo.value = {
                projectId: projectId,
                name: '프로젝트',
                tempo: 120.0,
                rootNote: 'C',
                mode: 'major',
                timeSigNumerator: 4,
                timeSigDenominator: 4,
                totalBarCount: 100
            };
            projectMembers.value = [];
            currentTotalSizeBytes.value = 0;
            maxTotalSizeBytes.value = 50 * 1024 * 1024;
            setMasterLimiterState(null);
            bpm.value = 120;

            // 백엔드 연결 시 실제 통신 로직으로 복구 필요 
            const data = await projectApi.getProjectDetail(projectId);

            // console.log('[fetchProject] data:', data)
            // console.log('[fetchProject] data.name:', data.name)

            if (data) {
                const MIN_TOTAL_BAR_COUNT = 100
                projectInfo.value = {
                    projectId: data.projectId,
                    name: data.name ?? '프로젝트',
                    tempo: data.tempo ?? 120,
                    rootNote: enumToRootNote[data.rootNote] || data.rootNote || 'C',
                    mode: data.mode ?? 'MAJOR',
                    timeSigNumerator: data.timeSigNumerator ?? 4,
                    timeSigDenominator: data.timeSigDenominator ?? 4,

                    // 핵심: 백엔드가 0을 내려줘도 화면 작업 영역은 최소 100마디 확보
                    totalBarCount: Math.max(data.totalBarCount ?? 0, MIN_TOTAL_BAR_COUNT),
                }
                projectMembers.value = data.members || [];
                currentTotalSizeBytes.value = data.currentTotalSizeBytes || 0;
                maxTotalSizeBytes.value = data.maxTotalSizeBytes || (50 * 1024 * 1024);
                bpm.value = data.tempo;

                const eqBandsByTrackId = new Map<number, TrackEqBandState[]>()

                try {
                    const trackEqs = await projectApi.getProjectTrackEqs(projectId)

                    await Promise.allSettled(
                        trackEqs.map(async (trackEq) => {
                            try {
                                const bands = await projectApi.getTrackEqBands(trackEq.trackEqId)

                                eqBandsByTrackId.set(
                                    Number(trackEq.trackId),
                                    [...bands]
                                        .sort((a, b) => a.bandOrder - b.bandOrder)
                                        .map(mapTrackEqBandSummaryToState),
                                )
                            } catch (bandError) {
                                console.warn(`[EQ] trackEqId=${trackEq.trackEqId} bands 로딩 실패, 빈 밴드로 진행`, bandError)
                            }
                        }),
                    )
                } catch (eqError) {
                    console.error('[EQ bands fetch failed]', eqError)
                }

                try {
                    const limiter = await getMasterLimiter(projectId)
                    setMasterLimiterState(limiter)
                } catch (limiterError) {
                    console.error('[Master limiter fetch failed]', limiterError)
                    setMasterLimiterState(null)
                }

                trackList.value = data.tracks.map((track): TrackUIState => ({
                    ...track,
                    eq: {
                        bands: eqBandsByTrackId.get(Number(track.trackId)) ?? [],
                    },
                    height: 100,
                    isSelected: false,
                    clips: track.clips.map((clip): ClipUIState => ({
                        ...clip,
                        isSelected: false,
                        isDragging: false,
                        isLocked: false,
                    }))
                }));

                let maxClipEnd = 0;
                trackList.value.forEach(track => {
                    track.clips.forEach(clip => {
                        const clipEnd = clip.start + clip.duration;
                        if (clipEnd > maxClipEnd) {
                            maxClipEnd = clipEnd;
                        }
                    });
                });

                checkAndExpandTimeline(maxClipEnd);

                // nextTick???�용??DOM ?�데?�트�?보장?????�디???�진???�정?�여 ?�더�?꼬임??방�?
                await nextTick();
                try {
                    setupAudioEngine(trackList.value);
                } catch (audioError) {
                    console.warn('[AudioEngine] setupAudioEngine failed, but track loaded.', audioError);
                }
            }
        } catch (error) {
            //  console.error("프로젝트 로딩 실패:", error);
        } finally {
            isLoading.value = false;
        }
    };

    // 1. 내가 클립을 잡았을 때 서버에 Lock 요청
    const lockClip = (clipId: number, trackId: number) => {
        myLockedClips.add(clipId); // 내가 잠근 목록에 등록 (브로드캐스트 자기차단용)
        socketService.publish('CLIP_LOCK', {
            projectId: projectInfo.value.projectId,
            clipId: clipId,
            isLocked: true // 잠가줘!
        });
    };

    // 2. 내가 클립에서 마우스를 뗐을 때 서버에 Unlock 요청
    const unlockClip = (clipId: number, trackId: number) => {
        myLockedClips.delete(clipId); // 내가 잠근 목록에서 제거
        socketService.publish('CLIP_LOCK', {
            projectId: projectInfo.value.projectId,
            clipId: clipId,
            isLocked: false // 풀어줘!
        });
    };

    const undo = () => {
        const cmd = undoStack.value.pop();
        if (cmd) {
            if (isPlaying.value) { togglePlay(); }
            cmd.undo();
            redoStack.value.push(cmd);
        }
    };

    const redo = () => {
        const cmd = redoStack.value.pop();
        if (cmd) {
            if (isPlaying.value) { togglePlay(); }
            cmd.redo();
            undoStack.value.push(cmd);
        }
    };

    // ==========================================
    // 오프라인 렌더링 (파형 시각화용)
    // ==========================================
    const renderAudioBufferWithEq = async (audioUrl: string, bands: TrackEqBandState[]): Promise<{ channels: Float32Array[], sampleRate: number } | null> => {
        try {
            // 원본 버퍼 가져오기 (캐시 활용)
            const originalBuffer = await fetchAndCacheAudioBuffer(audioUrl);
            
            // 밴드가 없으면 원본 데이터 그대로 반환
            if (!bands || bands.length === 0) {
                const numChannels = Math.min(2, originalBuffer.numberOfChannels);
                const channels = [];
                for (let i = 0; i < numChannels; i++) {
                    channels.push(originalBuffer.getChannelData(i));
                }
                return { channels, sampleRate: originalBuffer.sampleRate };
            }

            // 오프라인 렌더링 시작 (duration은 원본 버퍼 길이와 동일)
            const renderedBuffer = await Tone.Offline(({ transport }) => {
                const player = new Tone.Player(originalBuffer).start(0);
                
                let currentNode: any = player;
                bands.forEach(band => {
                    const type = band.eqTypeCode === 2 ? 'lowshelf' : band.eqTypeCode === 3 ? 'highshelf' : 'peaking';
                    const filter = new Tone.Filter({
                        type,
                        frequency: band.frequencyHz,
                        Q: band.q,
                        gain: band.gainDeltaDb,
                    });
                    
                    filter.channelCount = 2;
                    filter.channelCountMode = 'explicit';

                    currentNode.connect(filter);
                    currentNode = filter;
                });
                
                currentNode.toDestination();
            }, originalBuffer.duration);

            const numChannels = Math.min(2, renderedBuffer.numberOfChannels);
            const channels = [];
            for (let i = 0; i < numChannels; i++) {
                channels.push(renderedBuffer.getChannelData(i));
            }

            return { channels, sampleRate: renderedBuffer.sampleRate };
        } catch (e) {
            console.error('[EQ Waveform Render Error]', e);
            return null;
        }
    };

    // ==========================================
    // 3. 내보내기 (Return)
    // ==========================================
    return {
        undoStack,
        redoStack,
        pushCommand,
        undo,
        redo,
        // State
        trackList,
        projectInfo,
        isPlaying,
        playheadPosition,
        zoomlevel,
        bpm,
        secondsPerBar,
        isCommentMode,
        toggleCommentMode,

        // 구간 반복 및 메트로놈
        isLoopActive,
        loopStartBar,
        loopEndBar,
        isMetronomeActive,

        // Getters
        pixelPerBar,
        totalTimelineWidth,
        subDivision,
        displayBarCount,
        barNumberStep,
        manualLatencyOffset,

        // Actions
        fetchProject,
        isLoading,
        togglePlay,
        updateZoom,
        moveClipToTrack,
        stopPlay,
        updatePlayheadLoop,
        resyncClip,
        selectedClip,
        selectedTrackId,
        selectClip,
        selectedTarget,
        selectMasterTrack,
        deselectAll,

        // 클립보드
        viewportLeft,
        viewportRight,
        clipboardClip,
        clipboardTrackId,
        isCutAction,
        copyClip,
        cutClip,
        pasteClip,
        deleteClip,
        duplicateClip,
        splitClip,
        resizeClip,
        confirmMoveClip,
        masterTrack,
        addTrack,
        deleteTrack,

        //트랙 선택 기능
        selectTrack,

        //오디오 업로드 추가
        uploadingTrackId,
        uploadingBar,
        uploadAndAddAudioClip,

        //트랙 편집하기
        toggleTrackMute,
        toggleTrackSolo,
        setTrackVolume,
        setTrackPan,
        getVolumePercent,
        getVolumeFromPercent,
        renameTrack,
        reorderTrack,
        lockClip,
        unlockClip,
        setTimelineContainer,

        // 박자 변경
        changeTimeSignature,

        // BPM 변경
        changeBpm,

        // 키(Key) 변경
        changeKey,

        // [최적화] 파형 컴포넌트(WaveformWebGL)가 스토어 캐시에 접근하기 위한 인터페이스
        getAudioBufferCache,
        projectMembers,
        currentTotalSizeBytes,
        maxTotalSizeBytes,
        masterLimiterState,
        fetchAndCacheAudioBuffer,
        isAutoScrollActive,
        setMasterLimiterState,

        addTrackEqBand,
        updateTrackEqBand,
        removeTrackEqBand,
        setTrackEqBands,
        getTrackSpectrum,
        workspaceZoom,
        rebuildTrackEqChain,
        renderAudioBufferWithEq
    };
});


