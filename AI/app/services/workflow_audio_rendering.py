from __future__ import annotations

import librosa
import numpy as np


RENDER_TARGET_SR = 44100
RENDER_PEAK_LIMIT = 0.98


class AudioRenderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_clip_segment(
    audio_path: str,
    *,
    audio_start_ms: int,
    audio_duration_ms: int,
) -> np.ndarray:
    waveform, sample_rate = librosa.load(
        audio_path,
        sr=None,
        mono=False,
    )
    waveform = ensure_stereo(waveform)
    if sample_rate != RENDER_TARGET_SR:
        waveform = librosa.resample(
            waveform,
            orig_sr=sample_rate,
            target_sr=RENDER_TARGET_SR,
            axis=-1,
        )

    if audio_duration_ms <= 0:
        return waveform.T.astype(np.float32, copy=False)

    start_frame = ms_to_frames(audio_start_ms, RENDER_TARGET_SR)
    end_frame = min(
        start_frame + ms_to_frames(audio_duration_ms, RENDER_TARGET_SR),
        waveform.shape[-1],
    )
    if end_frame <= start_frame:
        return np.zeros((0, 2), dtype=np.float32)
    return waveform[:, start_frame:end_frame].T.astype(np.float32, copy=False)


def ensure_stereo(waveform: np.ndarray) -> np.ndarray:
    if waveform.ndim == 1:
        return np.stack([waveform, waveform], axis=0)
    if waveform.shape[0] == 1:
        return np.repeat(waveform, 2, axis=0)
    if waveform.shape[0] >= 2:
        return waveform[:2]
    raise AudioRenderError(
        "INVALID_AUDIO_WAVEFORM",
        "지원하지 않는 오디오 채널 형식입니다.",
    )


def ms_to_frames(value_ms: int, sample_rate: int = RENDER_TARGET_SR) -> int:
    return max(int(round((value_ms / 1000.0) * sample_rate)), 0)
