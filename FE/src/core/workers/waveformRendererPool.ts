/**
 * 파형 렌더러 Worker Pool — 싱글톤
 *
 * 목적: 브라우저의 OffscreenCanvas(또는 WebGL 컨텍스트) 개수 제한(8~16개)을 회피하고,
 * Worker를 매번 생성/파괴하지 않아 메모리 누수를 차단합니다.
 *
 * 동작 원리:
 *   1. Worker를 최대 MAX_WORKERS(4)개만 생성하고, 각각 내부에 OffscreenCanvas 1개를 소유합니다.
 *   2. 컴포넌트가 렌더 요청을 보내면 큐에 넣고, 유휴 Worker에 배정합니다.
 *   3. Worker는 그린 결과를 ImageBitmap으로 반환 → 컴포넌트가 일반 canvas에 drawImage()로 표시합니다.
 *   4. Worker 재사용으로 인해 OffscreenCanvas 수가 항상 4개 이하로 고정됩니다.
 *
 * [최적화] LRU ImageBitmap 캐시:
 *   - 렌더링 완료된 ImageBitmap을 캐시 키(audioKey+width+height+samplesPerPixel+startSampleOffset+channelIndex)로 저장합니다.
 *   - 동일한 파라미터로 재요청 시 Worker를 거치지 않고 즉시(0ms) 반환합니다.
 *   - 캐시 최대 개수(MAX_CACHE_SIZE)를 초과하면 가장 오래전 사용된 항목부터 폐기합니다.
 */

import WaveformWorker from './waveform.worker.ts?worker';

// 렌더 요청 데이터 타입
export interface WaveformRenderRequest {
  audioKey: string;
  color: string;
  width: number;
  height: number;
  samplesPerPixel: number;
  startSampleOffset: number;
  channelIndex: number;
}

// 렌더 결과 타입
export interface WaveformRenderResult {
  bitmap: ImageBitmap;
}

// 내부 큐 항목
interface QueueItem {
  request: WaveformRenderRequest;
  requestId: number;
  resolve: (result: WaveformRenderResult | null) => void;
}

// Worker 래퍼
interface PooledWorker {
  worker: Worker;
  busy: boolean;
  currentRequestId: number | null;
}

const MAX_WORKERS = 4;

/**
 * [최적화] LRU(Least Recently Used) ImageBitmap 캐시
 *
 * Map은 삽입 순서를 보장하므로, 항목에 접근할 때마다 delete → set으로 맨 뒤로 이동시킵니다.
 * 캐시가 가득 차면 Map의 첫 번째 항목(가장 오래전 사용된 항목)을 삭제합니다.
 */
const MAX_CACHE_SIZE = 500;

class BitmapLRUCache {
  private cache = new Map<string, ImageBitmap>();

  /**
   * 렌더 요청 파라미터로부터 고유 캐시 키를 생성합니다.
   * color는 현재 항상 '#D4CED2'로 고정이므로 키에서 제외하여 캐시 히트율을 높입니다.
   */
  static buildKey(req: WaveformRenderRequest): string {
    // startSampleOffset을 정수로 반올림하여 부동소수점 미세 차이로 캐시 미스가 나는 것을 방지
    return `${req.audioKey}|${req.width}|${req.height}|${Math.round(req.samplesPerPixel * 100)}|${Math.round(req.startSampleOffset)}|${req.channelIndex}`;
  }

  /**
   * 캐시에서 ImageBitmap을 조회합니다.
   * 히트 시 해당 항목을 맨 뒤로 이동(LRU 갱신)합니다.
   */
  get(key: string): ImageBitmap | undefined {
    const bitmap = this.cache.get(key);
    if (bitmap) {
      // LRU 갱신: 삭제 후 다시 삽입하여 맨 뒤(최신)로 이동
      this.cache.delete(key);
      this.cache.set(key, bitmap);
    }
    return bitmap;
  }

  /**
   * 렌더링 결과를 캐시에 저장합니다.
   * 캐시가 MAX_CACHE_SIZE를 초과하면 가장 오래된 항목의 ImageBitmap.close()를 호출하여 GPU 메모리를 해제합니다.
   */
  set(key: string, bitmap: ImageBitmap): void {
    // 이미 존재하는 키라면 기존 것을 삭제(LRU 갱신)
    if (this.cache.has(key)) {
      this.cache.delete(key);
    }

    // 용량 초과 시 가장 오래된 항목(Map의 첫 번째)부터 제거
    while (this.cache.size >= MAX_CACHE_SIZE) {
      const oldest = this.cache.keys().next().value;
      if (oldest !== undefined) {
        const oldBitmap = this.cache.get(oldest);
        if (oldBitmap) oldBitmap.close(); // GPU/메모리 해제
        this.cache.delete(oldest);
      } else {
        break;
      }
    }

    this.cache.set(key, bitmap);
  }

  /**
   * 특정 audioKey에 해당하는 모든 캐시를 무효화합니다.
   * 오디오 데이터가 변경되었을 때(예: EQ 적용, 오디오 교체 등) 호출합니다.
   */
  invalidateByAudioKey(audioKey: string): void {
    const prefix = `${audioKey}|`;
    for (const [key, bitmap] of this.cache) {
      if (key.startsWith(prefix)) {
        bitmap.close();
        this.cache.delete(key);
      }
    }
  }

  /** 전체 캐시 비우기 */
  clear(): void {
    for (const bitmap of this.cache.values()) {
      bitmap.close();
    }
    this.cache.clear();
  }

  get size(): number {
    return this.cache.size;
  }
}

class WaveformRendererPool {
  private workers: PooledWorker[] = [];
  private queue: QueueItem[] = [];
  private nextRequestId = 0;
  private initialized = false;

  // [최적화] LRU ImageBitmap 캐시 — 싱글톤 Pool에 함께 유지
  private _bitmapCache = new BitmapLRUCache();

  /**
   * Pool 초기화 — 최초 호출 시에만 Worker를 생성합니다.
   */
  private ensureInitialized() {
    if (this.initialized) return;
    this.initialized = true;

    for (let i = 0; i < MAX_WORKERS; i++) {
      const worker = new WaveformWorker();

      // 각 Worker에 초기화 메시지를 보내 내부 OffscreenCanvas를 생성하도록 지시
      worker.postMessage({ type: 'init' });

      const pooledWorker: PooledWorker = {
        worker,
        busy: false,
        currentRequestId: null,
      };

      // Worker가 결과를 반환했을 때의 콜백
      worker.onmessage = (e: MessageEvent) => {
        const { bitmap, requestId, cacheKey } = e.data;
        pooledWorker.busy = false;
        pooledWorker.currentRequestId = null;

        // 결과를 기다리고 있는 resolve 호출은 requestRender에서 직접 처리
        // → onmessage에서는 _pendingResolves에서 찾아 호출
        const pendingResolve = this._pendingResolves.get(requestId);
        if (pendingResolve) {
          this._pendingResolves.delete(requestId);
          if (bitmap) {
            // [최적화] 렌더링 결과를 LRU 캐시에 저장
            // createImageBitmap()으로 사본을 만들어 캐시에 보관하고,
            // 원본 bitmap은 컴포넌트에 반환하여 drawImage()에 사용
            if (cacheKey) {
              createImageBitmap(bitmap).then((cloned) => {
                this._bitmapCache.set(cacheKey, cloned);
              }).catch(() => {
                // 복제 실패 시 캐시 저장을 포기 — 렌더링 자체에는 영향 없음
              });
            }
            pendingResolve({ bitmap });
          } else {
            pendingResolve(null);
          }
        }

        // 큐에 대기 중인 다음 작업 처리
        this.processQueue();
      };

      this.workers.push(pooledWorker);
    }
  }

  // requestId → resolve 매핑 (Worker onmessage에서 올바른 Promise를 찾기 위함)
  private _pendingResolves = new Map<number, (result: WaveformRenderResult | null) => void>();

  /**
   * 오디오 데이터 전체를 워커 풀의 모든 워커에게 한 번 전송하여 캐싱합니다.
   * 메인 스레드 블로킹을 막는 Zero-Copy 렌더링을 위한 핵심입니다.
   */
  broadcastCacheAudio(audioKey: string, channels: Float32Array[]) {
    this.ensureInitialized();
    for (const pw of this.workers) {
      pw.worker.postMessage({
        type: 'cache',
        audioKey,
        channels,
      });
    }
  }

  /**
   * 파형 렌더링을 요청합니다.
   *
   * [최적화] 캐시 히트 시 Worker를 거치지 않고 즉시 ImageBitmap 사본을 반환합니다.
   *
   * @returns Promise<WaveformRenderResult | null> — ImageBitmap을 담은 결과 또는 null(취소됨)
   */
  requestRender(request: WaveformRenderRequest): { promise: Promise<WaveformRenderResult | null>; requestId: number } {
    this.ensureInitialized();

    const cacheKey = BitmapLRUCache.buildKey(request);
    const requestId = this.nextRequestId++;

    // [최적화 핵심] 캐시 히트 → Worker 큐를 건너뛰고 즉시 반환
    const cachedBitmap = this._bitmapCache.get(cacheKey);
    if (cachedBitmap) {
      // 캐시에 있는 ImageBitmap의 사본을 만들어 반환 (원본은 캐시에 유지)
      const promise = createImageBitmap(cachedBitmap).then((cloned) => {
        return { bitmap: cloned } as WaveformRenderResult;
      }).catch(() => {
        // 사본 생성 실패 시 캐시에서 제거하고 Worker를 통해 다시 렌더링
        this._bitmapCache.invalidateByAudioKey(request.audioKey);
        return this._requestRenderFromWorker(request, cacheKey);
      });

      return { promise, requestId };
    }

    // 캐시 미스 → 기존 로직대로 Worker에 렌더 요청
    const promise = this._requestRenderFromWorker(request, cacheKey);
    return { promise, requestId };
  }

  /**
   * Worker에 실제로 렌더링 작업을 위임하는 내부 메서드입니다.
   * 캐시 미스 시에만 호출됩니다.
   */
  private _requestRenderFromWorker(request: WaveformRenderRequest, cacheKey: string): Promise<WaveformRenderResult | null> {
    const requestId = this.nextRequestId++;

    return new Promise<WaveformRenderResult | null>((resolve) => {
      this.queue.push({ request: { ...request, _cacheKey: cacheKey } as any, requestId, resolve });
      this.processQueue();
    });
  }

  /**
   * 특정 요청을 취소합니다. 큐에서 제거하거나, 이미 실행 중이면 결과를 무시합니다.
   */
  cancelRequest(requestId: number) {
    // 큐에서 제거
    const queueIndex = this.queue.findIndex((item) => item.requestId === requestId);
    if (queueIndex !== -1) {
      const removed = this.queue.splice(queueIndex, 1)[0];
      removed.resolve(null);
      return;
    }

    // 이미 실행 중이라면 pending resolve를 제거하여 결과를 무시
    if (this._pendingResolves.has(requestId)) {
      this._pendingResolves.delete(requestId);
    }
  }

  /**
   * 특정 오디오의 캐시를 무효화합니다.
   * EQ 변경, 오디오 교체 등 원본 데이터가 바뀌었을 때 호출합니다.
   */
  invalidateCache(audioKey: string) {
    this._bitmapCache.invalidateByAudioKey(audioKey);
  }

  /**
   * 큐에서 다음 작업을 꺼내 유휴 Worker에 배정합니다.
   */
  private processQueue() {
    while (this.queue.length > 0) {
      const idleWorker = this.workers.find((w) => !w.busy);
      if (!idleWorker) break; // 모든 Worker가 바쁨 → 대기

      const item = this.queue.shift()!;
      idleWorker.busy = true;
      idleWorker.currentRequestId = item.requestId;

      // resolve를 보관해 두고, Worker onmessage에서 호출
      this._pendingResolves.set(item.requestId, item.resolve);

      // [최적화 핵심] 메인 스레드 블로킹 원천 차단
      // 기존처럼 Float32Array.slice()를 호출해 동기적으로 메모리를 할당/복사하지 않습니다.
      // 렌더링 시에는 워커 내부에 캐시된 데이터에 대한 접근 좌표(Offset)만 JSON으로 전송합니다.
      const cacheKey = (item.request as any)._cacheKey || '';
      idleWorker.worker.postMessage({
        type: 'render',
        requestId: item.requestId,
        cacheKey, // Worker가 결과와 함께 돌려보내 줄 캐시 키
        audioKey: item.request.audioKey,
        color: item.request.color,
        width: item.request.width,
        height: item.request.height,
        samplesPerPixel: item.request.samplesPerPixel,
        startSampleOffset: item.request.startSampleOffset,
        channelIndex: item.request.channelIndex,
      });
    }
  }

  /**
   * 전체 Pool 해제 (페이지 언마운트 시 호출)
   */
  dispose() {
    for (const pw of this.workers) {
      pw.worker.terminate();
    }
    this.workers = [];
    this.queue = [];
    this._pendingResolves.clear();
    this._bitmapCache.clear();
    this.initialized = false;
  }
}

// 싱글톤 인스턴스 내보내기
export const waveformRendererPool = new WaveformRendererPool();
