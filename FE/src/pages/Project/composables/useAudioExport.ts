import * as Tone from 'tone'
import { useTrackStore } from '../store/useTrackStore'
import type { MasterLimiterState } from '../api/projectLimiter.api'

export function calculateMasterRenderDurationSec(
  tracks: ReturnType<typeof useTrackStore>['trackList'],
  secondsPerBar: number,
) {
  let maxDurationBar = 0
  tracks.forEach((track) => {
    track.clips.forEach((clip) => {
      const end = clip.start + clip.duration
      if (end > maxDurationBar) maxDurationBar = end
    })
  })

  if (maxDurationBar === 0) {
    return 0
  }

  return maxDurationBar * secondsPerBar + 1.0
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

function dbToLinear(db: number) {
  return Math.pow(10, db / 20)
}

function applyOfflineMasterLimiter(
  destination: Tone.ToneAudioNode,
  limiterState: MasterLimiterState | null,
) {
  if (!limiterState || !limiterState.isEnabled) {
    return destination
  }

  const inputGain = new Tone.Gain(dbToLinear(limiterState.inputGainDb))
  const limiter = new Tone.Compressor({
    threshold: Math.max(-100, Math.min(0, limiterState.thresholdDb)),
    ratio: 20,
    attack: Math.max(0, limiterState.attackMs / 1000),
    release: Math.max(0.001, limiterState.releaseMs / 1000),
    knee: 0,
  })
  const outputGain = new Tone.Gain(
    dbToLinear(limiterState.makeupGainDb + limiterState.ceilingDbfs),
  )

  inputGain.connect(limiter)
  limiter.connect(outputGain)
  outputGain.connect(destination)

  return inputGain
}

function encodeWAV24Bit(
  audioBuffer: AudioBuffer,
  sampleRate: number,
  numChannels: number,
): Blob {
  const left = audioBuffer.getChannelData(0)
  const right = numChannels > 1 ? audioBuffer.getChannelData(1) : left

  const numSamples = left.length
  const bitDepth = 24
  const bytesPerSample = bitDepth / 8
  const blockAlign = numChannels * bytesPerSample
  const byteRate = sampleRate * blockAlign
  const dataSize = numSamples * blockAlign

  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(view, 8, 'WAVE')

  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitDepth, true)

  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < numSamples; i++) {
    for (let channel = 0; channel < numChannels; channel++) {
      const sample = channel === 0 ? left[i] : right[i]
      const clamped = Math.max(-1, Math.min(1, sample))

      let val = clamped < 0 ? clamped * 0x800000 : clamped * 0x7fffff
      val = Math.round(val)

      view.setUint8(offset, val & 0xff)
      view.setUint8(offset + 1, (val >> 8) & 0xff)
      view.setUint8(offset + 2, (val >> 16) & 0xff)
      offset += bytesPerSample
    }
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

export function useAudioExport() {
  const trackStore = useTrackStore()

  const exportMasterAudio = async (isMono: boolean = false): Promise<Blob> => {
    const tracks = trackStore.trackList
    const renderDurationSec = calculateMasterRenderDurationSec(
      tracks,
      trackStore.secondsPerBar,
    )

    if (renderDurationSec === 0) {
      throw new Error('내보낼 오디오 클립이 없습니다.')
    }

    const secondsPerBar = trackStore.secondsPerBar
    const sampleRate = 48000
    const channels = isMono ? 1 : 2
    const isAnyTrackSoloed = tracks.some((track) => track.isSoloed)

    const renderedBuffer = await Tone.Offline(async ({ transport }) => {
      const masterVolume = new Tone.Volume(0)
      const masterBusInput = applyOfflineMasterLimiter(
        Tone.getDestination(),
        trackStore.masterLimiterState,
      )
      masterVolume.connect(masterBusInput)

      for (const track of tracks) {
        if (track.isMuted) continue
        if (isAnyTrackSoloed && !track.isSoloed) continue

        const panner = new Tone.Panner(track.pan / 100).connect(masterVolume)
        const vol = new Tone.Volume(track.volume).connect(panner)

        panner.channelCount = 2
        panner.channelCountMode = 'explicit'
        vol.channelCount = 2
        vol.channelCountMode = 'explicit'

        let currentInput: Tone.ToneAudioNode = vol

        const eqState = track.eq
        if (eqState && eqState.bands && eqState.bands.length > 0) {
          const eqNodes = eqState.bands.map((band) => {
            const type: BiquadFilterType =
              band.eqTypeCode === 2
                ? 'lowshelf'
                : band.eqTypeCode === 3
                  ? 'highshelf'
                  : 'peaking'

            return new Tone.Filter({
              type,
              frequency: band.frequencyHz,
              Q: band.q,
              gain: band.gainDeltaDb,
            })
          })

          for (let i = 0; i < eqNodes.length - 1; i++) {
            eqNodes[i].connect(eqNodes[i + 1])
          }
          eqNodes[eqNodes.length - 1].connect(vol)
          currentInput = eqNodes[0]
        }

        for (const clip of track.clips) {
          if (!clip.audio?.cdnUrl) continue

          const audioBuffer = await trackStore.fetchAndCacheAudioBuffer(clip.audio.cdnUrl)
          const player = new Tone.Player(audioBuffer)
          player.connect(currentInput)

          const exactStartTimeSec = clip.start * secondsPerBar
          const audioOffsetSec = (clip.audioStartMs || 0) / 1000
          const visualDurationSec = clip.duration * secondsPerBar
          const sourceAudioSec = clip.audioDurationMs / 1000

          player.playbackRate = visualDurationSec > 0 ? sourceAudioSec / visualDurationSec : 1
          player.sync().start(exactStartTimeSec, audioOffsetSec, sourceAudioSec)
        }
      }

      transport.start()
    }, renderDurationSec, channels, sampleRate)

    return encodeWAV24Bit(renderedBuffer.get() as AudioBuffer, sampleRate, channels)
  }

  return {
    exportMasterAudio,
  }
}
