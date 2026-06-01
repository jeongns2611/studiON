/**
 * 파형 렌더링 Worker (Pool 방식 호환)
 *
 * 동작 원리:
 *   1. 'init' 메시지를 받으면 내부에 OffscreenCanvas를 생성합니다. (Worker 1개당 1개)
 *   2. 'render' 메시지를 받으면 파형을 그린 뒤, transferToImageBitmap()으로 결과를 생성합니다.
 *   3. ImageBitmap과 requestId를 메인 스레드로 반환합니다.
 *
 * 이 방식의 장점:
 *   - OffscreenCanvas는 Worker 내부에서만 존재 → 브라우저의 컨텍스트 개수 제한에 걸리지 않음
 *   - Worker를 재사용하므로 매번 생성/파괴에 따른 메모리 누수 없음
 *   - 매 프레임 clearRect() 후 다시 그리므로 GPU 메모리 누적 없음
 */

interface InitMessage {
  type: 'init';
}

interface CacheMessage {
  type: 'cache';
  audioKey: string;
  channels: Float32Array[];
}

interface RenderMessage {
  type: 'render';
  requestId: number;
  cacheKey: string; // 메인 스레드의 LRU 캐시에서 사용할 키
  audioKey: string;
  color: string;
  width: number;
  height: number;
  samplesPerPixel: number;
  startSampleOffset: number;
  channelIndex: number;
}

type WorkerMessage = InitMessage | CacheMessage | RenderMessage;

let offscreenCanvas: OffscreenCanvas | null = null;
let ctx: OffscreenCanvasRenderingContext2D | null = null;
const audioCache = new Map<string, Float32Array[]>();

self.onmessage = (e: MessageEvent<WorkerMessage>) => {
  const msg = e.data;

  // 초기화: Worker 내부에 OffscreenCanvas를 한 번만 생성
  if (msg.type === 'init') {
    // 초기 크기는 임의값 — render 시 동적으로 조정됨
    offscreenCanvas = new OffscreenCanvas(1, 1);
    ctx = offscreenCanvas.getContext('2d');
    return;
  }

  // 데이터 캐싱
  if (msg.type === 'cache') {
    audioCache.set(msg.audioKey, msg.channels);
    return;
  }

  // 렌더 요청
  if (msg.type === 'render') {
    const { requestId, cacheKey, audioKey, color, width, height, samplesPerPixel, startSampleOffset, channelIndex } = msg;

    const channels = audioCache.get(audioKey);
    const channelData = channels ? channels[channelIndex] : undefined;
    if (!channelData) {
      // 캐시된 데이터가 없으면 렌더링 중단
      (self as unknown as Worker).postMessage({ requestId, bitmap: null });
      return;
    }

    if (!offscreenCanvas || !ctx) {
      // 혹시 init이 아직 안 왔으면 즉석 생성 (방어)
      offscreenCanvas = new OffscreenCanvas(width, height);
      ctx = offscreenCanvas.getContext('2d');
    }

    if (!ctx || width <= 0 || height <= 0) {
      (self as unknown as Worker).postMessage({ requestId, bitmap: null });
      return;
    }

    // 캔버스 크기를 요청에 맞게 조정 (기존 내용은 자동으로 초기화됨)
    offscreenCanvas.width = width;
    offscreenCanvas.height = height;

    // 1. 도화지 초기화
    ctx.clearRect(0, 0, width, height);

    // 2. 펜 설정 (색상과 두께 지정)
    ctx.strokeStyle = color || '#D4CED2';
    ctx.lineWidth = 1;

    // 3. 선 그리기 시작
    ctx.beginPath();

    // 가운데 기준점
    const centerY = height / 2;

    // 오디오 데이터를 순회하며 픽셀 단위로 최소/최대 높이
    for (let x = 0; x < width; x += 1) {
      const start = Math.floor(startSampleOffset + x * samplesPerPixel);
      const end = Math.floor(startSampleOffset + (x + 1) * samplesPerPixel);
      // 계산된 위치가 실제 오디오 데이터 길이보다 길어지면 렌더링을 중단
      if (start >= channelData.length) break;

      const actualEnd = Math.min(end, channelData.length);
      // 가장 낮은 음수 값과 가장 높은 양수를 구해서 수직선의 양끝을 이음
      let min = 1.0;
      let max = -1.0;

      // [최적화] 픽셀당 너무 많은 샘플이 들어갈 경우, 최대 100개만 샘플링하여 워커 CPU 과부하 및 렉(Stutter) 방지
      const step = Math.max(1, Math.floor((actualEnd - start) / 100));
      for (let i = start; i < actualEnd; i += step) {
        const value = channelData[i];
        if (value < min) min = value;
        if (value > max) max = value;
      }

      // 소리가 완전히 없는 무음 구간이더라도 캔버스에서 선이 끊어져 보이지 않게 보정
      const minHeightClip = 2.0 / height;
      if (max - min < minHeightClip) {
        max = minHeightClip / 2;
        min = -minHeightClip / 2;
      }

      // 브라우저 2D 캔버스는 맨위가 0이고 아래로 갈수록 숫자가 커진다.
      const yTop = centerY - (max * centerY);
      const yBottom = centerY - (min * centerY);

      // X좌표에 맞춰 위에서 아래로 세로선을 쭉 그음
      ctx.moveTo(x, yTop);
      ctx.lineTo(x, yBottom);
    }

    // 4. 화면에 출력!
    ctx.stroke();

    // 5. ImageBitmap으로 변환하여 메인 스레드로 반환
    const bitmap = offscreenCanvas.transferToImageBitmap();
    (self as unknown as Worker).postMessage({ requestId, bitmap, cacheKey }, [bitmap]);
    return;
  }
};