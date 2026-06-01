from __future__ import annotations

import math
from typing import Any

import librosa
import numpy as np
from fastapi import HTTPException, status
from scipy.signal import butter, resample_poly, sosfiltfilt

from app.graph.nodes.analysis import DSP_TARGET_SR
from app.services.workflow_artifacts import get_workflow_artifact_store
from app.services.workflow_audio_paths import AudioPathResolutionError, resolve_clip_audio_path
from app.services.workflow_audio_rendering import load_clip_segment, ms_to_frames
from app.services.workflow_snapshots import TimelineSnapshotDocument

WAVEFORM_POINT_COUNT = 1200
SPECTRUM_BIN_COUNT = 96
LOUDNESS_WINDOW_MS = 200
TRUE_PEAK_OVERSAMPLE_FACTOR = 4
DEFAULT_SIBILANCE_BAND = (6000, 8500)
DEFAULT_HARSHNESS_BAND = (4500, 9000)
DEFAULT_BODY_BAND = (200, 2000)
DEFAULT_PRESENCE_BAND = (2000, 5000)


def build_preview_compare_payload(
    state: dict[str, Any],
    snapshot: TimelineSnapshotDocument,
    *,
    mode: str = "preview",
) -> dict[str, Any]:
    preview = _require_preview_ready(state)
    focus_region = _resolve_focus_region(state)
    actions = _resolve_compare_actions(state, mode=mode)
    excerpt_range = preview["preview_excerpt_range"]

    track_signals = _build_excerpt_track_signals(
        clip_index=snapshot.clip_index,
        excerpt_start_ms=int(excerpt_range["start_ms"]),
        excerpt_end_ms=int(excerpt_range["end_ms"]),
    )
    before_master = _sum_track_signals(track_signals)
    after_track_signals = {
        track_id: signal.copy() for track_id, signal in track_signals.items()
    }
    after_master = _apply_preview_actions(
        excerpt_start_ms=int(excerpt_range["start_ms"]),
        before_master=before_master,
        track_signals=after_track_signals,
        actions=actions,
    )

    before_mono = _to_mono(before_master)
    after_mono = _to_mono(after_master)
    diff_mono = after_mono - before_mono
    region_slice = _resolve_focus_region_slice(
        focus_region=focus_region,
        excerpt_start_ms=int(excerpt_range["start_ms"]),
        excerpt_end_ms=int(excerpt_range["end_ms"]),
        total_frames=before_mono.size,
    )
    before_region = before_mono[region_slice]
    after_region = after_mono[region_slice]

    metric_before_signal, metric_after_signal, metric_source = _resolve_metric_signals(
        focus_region=focus_region,
        action=actions[-1],
        track_signals=track_signals,
        after_track_signals=after_track_signals,
        before_mono=before_mono,
        after_mono=after_mono,
    )
    before_excerpt = _build_excerpt_summary(before_mono)
    after_excerpt = _build_excerpt_summary(after_mono)
    before_region_summary = _build_excerpt_summary(metric_before_signal[region_slice])
    after_region_summary = _build_excerpt_summary(metric_after_signal[region_slice])
    diff_excerpt = _build_diff_summary(diff_mono, before_mono, after_mono)
    issue_overlay = _build_issue_overlay(
        state=state,
        focus_region=focus_region,
        action=actions[-1],
        track_signals=track_signals,
        after_track_signals=after_track_signals,
        before_mono=before_mono,
        after_mono=after_mono,
        region_slice=region_slice,
    )
    prompt_feedback_hints = _build_prompt_feedback_hints(
        focus_region=focus_region,
        before_mono=before_mono,
        after_mono=after_mono,
        issue_overlay=issue_overlay,
        excerpt_start_ms=int(excerpt_range["start_ms"]),
        excerpt_end_ms=int(excerpt_range["end_ms"]),
    )

    return {
        "preview": preview,
        "mode": mode,
        "focus_region": focus_region,
        "action": actions[-1],
        "actions": actions,
        "before_excerpt": before_excerpt,
        "after_excerpt": after_excerpt,
        "before_region_summary": before_region_summary,
        "after_region_summary": after_region_summary,
        "region_metric_source": metric_source,
        "diff_excerpt": diff_excerpt,
        "issue_overlay": issue_overlay,
        "prompt_feedback_hints": prompt_feedback_hints,
    }


def _require_preview_ready(state: dict[str, Any]) -> dict[str, Any]:
    preview_id = state.get("preview_id")
    if not preview_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview render was not found.",
        )
    preview_excerpt_range = {
        "start_ms": state.get("preview_excerpt_start_ms"),
        "end_ms": state.get("preview_excerpt_end_ms"),
    }
    if state.get("preview_status") != "READY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview render is not ready.",
        )
    if preview_excerpt_range["start_ms"] is None or preview_excerpt_range["end_ms"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview excerpt range is not available.",
        )
    return {
        "id": preview_id,
        "status": state.get("preview_status"),
        "preview_target_region": _resolve_focus_region_id(state),
        "preview_band_specs": _resolve_preview_band_specs(state),
        "preview_excerpt_range": {
            "start_ms": int(preview_excerpt_range["start_ms"]),
            "end_ms": int(preview_excerpt_range["end_ms"]),
        },
        "requested_at": state.get("preview_requested_at"),
        "started_at": state.get("preview_started_at"),
        "completed_at": state.get("preview_completed_at"),
    }


def _resolve_focus_region(state: dict[str, Any]) -> dict[str, Any]:
    selected_region_id = _resolve_focus_region_id(state)
    for region in state.get("analysis_regions", []):
        if int(region["id"]) == int(selected_region_id):
            return dict(region)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Preview focus region was not found.",
    )


def _resolve_preview_action(state: dict[str, Any]) -> dict[str, Any]:
    plan_payload = state.get("plan_payload") or {}
    candidate = plan_payload.get("candidate") or {}
    action = candidate.get("action")
    if not isinstance(action, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview compare requires one materialized preview action.",
        )
    return {
        "action_id": str(candidate.get("candidateId") or f"{state['job_id']}-plan-candidate-1"),
        "action_type": action.get("actionType"),
        "target_scope": action.get("targetScope"),
        "target_track_id": action.get("targetTrackId"),
        "target_clip_id": action.get("targetClipId"),
        "start_ms": int(action.get("startMs") or 0),
        "end_ms": int(action.get("endMs") or 0),
        "band_low_hz": action.get("bandLowHz"),
        "band_high_hz": action.get("bandHighHz"),
        "gain_delta_db": action.get("gainDeltaDb"),
        "params": action.get("params") or {},
    }


def _resolve_compare_actions(state: dict[str, Any], *, mode: str) -> list[dict[str, Any]]:
    if mode == "preview":
        actions = _resolve_auto_fix_actions(state)
        try:
            actions.append(_resolve_preview_action(state))
        except HTTPException:
            pass
        if actions:
            return actions
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview compare requires at least one materialized preview action.",
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported preview compare mode '{mode}'.",
    )


def _resolve_preview_band_specs(state: dict[str, Any]) -> list[dict[str, Any]]:
    payload = state.get("suggestion_payload") or {}
    preview_band_specs: list[dict[str, Any]] = []
    for suggestion in payload.get("suggestions", []):
        for band in suggestion.get("previewBands", []):
            if isinstance(band, dict):
                preview_band_specs.append(dict(band))
    return preview_band_specs


def _resolve_auto_fix_actions(state: dict[str, Any]) -> list[dict[str, Any]]:
    artifact_id = state.get("auto_fix_recipe_artifact_id")
    if not artifact_id:
        return []
    artifact = get_workflow_artifact_store().get_artifact(str(artifact_id))
    if artifact is None:
        return []
    groups = artifact.payload.get("groups") or []
    actions: list[dict[str, Any]] = []
    for group in groups:
        for recipe in group.get("recipes", []):
            actions.append(_normalize_action_payload(recipe))
    return actions


def _normalize_action_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": str(action.get("actionId") or ""),
        "region_id": action.get("regionId"),
        "action_type": action.get("actionType"),
        "target_scope": action.get("targetScope"),
        "target_track_id": action.get("targetTrackId"),
        "target_clip_id": action.get("targetClipId"),
        "start_ms": int(action.get("startMs") or 0),
        "end_ms": int(action.get("endMs") or 0),
        "band_low_hz": action.get("bandLowHz"),
        "band_high_hz": action.get("bandHighHz"),
        "gain_delta_db": action.get("gainDeltaDb"),
        "params": action.get("params") or {},
    }


def _resolve_focus_region_id(state: dict[str, Any]) -> int:
    selected_region_id = state.get("selected_region_id")
    if selected_region_id is not None:
        return int(selected_region_id)
    artifact_id = state.get("auto_fix_recipe_artifact_id")
    if artifact_id:
        artifact = get_workflow_artifact_store().get_artifact(str(artifact_id))
        if artifact is not None:
            groups = artifact.payload.get("groups") or []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                region_ids = group.get("regionIds") or []
                if region_ids:
                    return int(region_ids[0])
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Preview focus region was not found.",
    )


def _build_excerpt_track_signals(
    *,
    clip_index: list[dict[str, object | None]],
    excerpt_start_ms: int,
    excerpt_end_ms: int,
) -> dict[int, np.ndarray]:
    excerpt_duration_ms = max(excerpt_end_ms - excerpt_start_ms, 1)
    excerpt_frames = ms_to_frames(excerpt_duration_ms, DSP_TARGET_SR)
    track_signals: dict[int, np.ndarray] = {}
    for clip in clip_index:
        clip_start_ms = int(clip.get("start_ms") or 0)
        clip_end_ms = int(clip.get("end_ms") or 0)
        overlap_start_ms = max(excerpt_start_ms, clip_start_ms)
        overlap_end_ms = min(excerpt_end_ms, clip_end_ms)
        if overlap_end_ms <= overlap_start_ms:
            continue
        try:
            resolved_audio_path = resolve_clip_audio_path(clip)
        except AudioPathResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.message,
            ) from exc
        if resolved_audio_path is None:
            continue
        clip_waveform = load_clip_segment(
            resolved_audio_path,
            audio_start_ms=int(clip.get("audio_start_ms") or 0),
            audio_duration_ms=int(
                clip.get("audio_duration_ms") or max(clip_end_ms - clip_start_ms, 1)
            ),
        )
        local_clip_start_ms = overlap_start_ms - clip_start_ms
        overlap_duration_ms = overlap_end_ms - overlap_start_ms
        source_start_frame = ms_to_frames(local_clip_start_ms, DSP_TARGET_SR)
        source_end_frame = min(
            source_start_frame + ms_to_frames(overlap_duration_ms, DSP_TARGET_SR),
            clip_waveform.shape[0],
        )
        if source_end_frame <= source_start_frame:
            continue
        timeline_start_frame = ms_to_frames(overlap_start_ms - excerpt_start_ms, DSP_TARGET_SR)
        timeline_end_frame = min(
            timeline_start_frame + (source_end_frame - source_start_frame),
            excerpt_frames,
        )
        if timeline_end_frame <= timeline_start_frame:
            continue
        track_id = int(clip.get("track_id") or 0)
        track_signal = track_signals.setdefault(
            track_id,
            np.zeros((excerpt_frames, 2), dtype=np.float32),
        )
        usable_frames = timeline_end_frame - timeline_start_frame
        track_signal[timeline_start_frame:timeline_end_frame] += clip_waveform[
            source_start_frame : source_start_frame + usable_frames
        ]
    return track_signals


def _sum_track_signals(track_signals: dict[int, np.ndarray]) -> np.ndarray:
    if not track_signals:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No excerpt audio could be resolved for preview compare.",
        )
    first_signal = next(iter(track_signals.values()))
    summed = np.zeros_like(first_signal)
    for signal in track_signals.values():
        summed += signal
    return summed


def _apply_preview_actions(
    *,
    excerpt_start_ms: int,
    before_master: np.ndarray,
    track_signals: dict[int, np.ndarray],
    actions: list[dict[str, Any]],
) -> np.ndarray:
    master_after = before_master.copy()
    for action in actions:
        master_after = _apply_preview_action(
            excerpt_start_ms=excerpt_start_ms,
            before_master=master_after,
            track_signals=track_signals,
            action=action,
        )
    return master_after


def _apply_preview_action(
    *,
    excerpt_start_ms: int,
    before_master: np.ndarray,
    track_signals: dict[int, np.ndarray],
    action: dict[str, Any],
) -> np.ndarray:
    action_start_ms = int(action.get("start_ms") or 0)
    action_end_ms = int(action.get("end_ms") or 0)
    excerpt_end_ms = excerpt_start_ms + _samples_to_ms(before_master.shape[0])
    if action_end_ms <= excerpt_start_ms or action_start_ms >= excerpt_end_ms:
        return before_master
    action_start_frame = ms_to_frames(
        max(action_start_ms - excerpt_start_ms, 0),
        DSP_TARGET_SR,
    )
    action_end_frame = ms_to_frames(
        max(action_end_ms - excerpt_start_ms, 0),
        DSP_TARGET_SR,
    )
    action_start_frame = min(action_start_frame, before_master.shape[0])
    action_end_frame = min(action_end_frame, before_master.shape[0])
    if action_end_frame <= action_start_frame:
        action_end_frame = min(action_start_frame + 1, before_master.shape[0])
    if str(action.get("target_scope")) == "MASTER":
        master_after = before_master.copy()
        master_after[action_start_frame:action_end_frame] = _process_action_signal(
            master_after[action_start_frame:action_end_frame],
            action=action,
        )
        return master_after

    target_track_id = action.get("target_track_id")
    if target_track_id is None or int(target_track_id) not in track_signals:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preview action target track was not found in excerpt.",
        )
    target_signal = track_signals[int(target_track_id)]
    target_signal[action_start_frame:action_end_frame] = _process_action_signal(
        target_signal[action_start_frame:action_end_frame],
        action=action,
    )
    return _sum_track_signals(track_signals)


def _resolve_focus_region_slice(
    *,
    focus_region: dict[str, Any],
    excerpt_start_ms: int,
    excerpt_end_ms: int,
    total_frames: int,
) -> slice:
    region_start_frame = ms_to_frames(
        max(int(focus_region.get("start_ms") or 0) - excerpt_start_ms, 0),
        DSP_TARGET_SR,
    )
    region_end_frame = ms_to_frames(
        max(int(focus_region.get("end_ms") or excerpt_end_ms) - excerpt_start_ms, 0),
        DSP_TARGET_SR,
    )
    region_end_frame = min(max(region_end_frame, region_start_frame + 1), total_frames)
    return slice(region_start_frame, region_end_frame)


def _process_action_signal(signal: np.ndarray, *, action: dict[str, Any]) -> np.ndarray:
    if signal.size == 0:
        return signal
    action_type = str(action.get("action_type") or "")
    gain_delta_db = action.get("gain_delta_db")
    if action_type == "GAIN_TRIM":
        processed = signal * _db_to_linear(float(gain_delta_db or 0.0))
        return _apply_post_action(processed, action.get("params") or {})
    if action_type == "TRUE_PEAK_LIMITER":
        params = action.get("params") or {}
        return _apply_limiter(signal, ceiling_dbfs=float(params.get("ceilingDbfs") or -1.0))
    if action_type in {"DYNAMIC_EQ", "EQ_CUT", "DE_ESSER"}:
        band_low_hz, band_high_hz = _resolve_action_band(action)
        processed = _apply_band_gain(
            signal,
            band_low_hz=band_low_hz,
            band_high_hz=band_high_hz,
            gain_delta_db=float(gain_delta_db or -2.0),
        )
        return _apply_post_action(processed, action.get("params") or {})
    return signal


def _apply_post_action(signal: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    if str(params.get("postAction")) == "TRUE_PEAK_LIMITER":
        return _apply_limiter(signal, ceiling_dbfs=float(params.get("ceilingDbfs") or -1.0))
    return signal


def _resolve_action_band(action: dict[str, Any]) -> tuple[int, int]:
    action_type = str(action.get("action_type") or "")
    band_low_hz = action.get("band_low_hz")
    band_high_hz = action.get("band_high_hz")
    if isinstance(band_low_hz, int) and isinstance(band_high_hz, int):
        return band_low_hz, band_high_hz
    if action_type == "DE_ESSER":
        return DEFAULT_SIBILANCE_BAND
    return (250, 4000)


def _apply_band_gain(
    signal: np.ndarray,
    *,
    band_low_hz: int,
    band_high_hz: int,
    gain_delta_db: float,
) -> np.ndarray:
    low_hz = max(20, min(band_low_hz, (DSP_TARGET_SR // 2) - 200))
    high_hz = max(low_hz + 50, min(band_high_hz, (DSP_TARGET_SR // 2) - 50))
    if high_hz <= low_hz:
        return signal
    sos = butter(
        4,
        [low_hz, high_hz],
        btype="bandpass",
        fs=DSP_TARGET_SR,
        output="sos",
    )
    processed = signal.copy()
    gain_linear = _db_to_linear(gain_delta_db)
    for channel_index in range(processed.shape[1]):
        channel = processed[:, channel_index]
        try:
            band_signal = sosfiltfilt(sos, channel)
        except ValueError:
            continue
        processed[:, channel_index] = channel + (band_signal * (gain_linear - 1.0))
    return processed


def _apply_limiter(signal: np.ndarray, *, ceiling_dbfs: float) -> np.ndarray:
    ceiling = _db_to_linear(ceiling_dbfs)
    return np.clip(signal.copy(), -ceiling, ceiling)


def _to_mono(signal: np.ndarray) -> np.ndarray:
    if signal.ndim == 1:
        return signal.astype(np.float32, copy=False)
    return signal.mean(axis=1).astype(np.float32, copy=False)


def _build_excerpt_summary(signal: np.ndarray) -> dict[str, Any]:
    return {
        "duration_ms": _samples_to_ms(signal.size),
        "waveform_points": _build_waveform_points(signal),
        "spectrum_bins": _build_spectrum_bins(signal),
        "peak_dbfs": round(_to_dbfs(float(np.max(np.abs(signal))) if signal.size else 0.0), 3),
        "rms_dbfs": round(_rms_dbfs(signal), 3),
        "crest_factor_db": round(_crest_factor_db(signal), 3),
        "true_peak_dbfs": round(_to_dbfs(_oversampled_true_peak(signal)), 3),
        "clipped_sample_count": int(np.sum(np.abs(signal) >= 0.999)),
        "loudness_curve": _build_loudness_curve(signal),
    }


def _build_diff_summary(
    diff_signal: np.ndarray,
    before_signal: np.ndarray,
    after_signal: np.ndarray,
) -> dict[str, Any]:
    mean_abs_delta = float(np.mean(np.abs(diff_signal))) if diff_signal.size else 0.0
    max_abs_delta = float(np.max(np.abs(diff_signal))) if diff_signal.size else 0.0
    return {
        "waveform_points": _build_waveform_points(diff_signal),
        "spectrum_bins": _build_spectrum_bins(diff_signal),
        "mean_abs_delta_db": round(_to_dbfs(mean_abs_delta), 3),
        "max_abs_delta_db": round(_to_dbfs(max_abs_delta), 3),
        "rms_delta_db": round(_rms_dbfs(after_signal) - _rms_dbfs(before_signal), 3),
    }


def _build_issue_overlay(
    *,
    state: dict[str, Any],
    focus_region: dict[str, Any],
    action: dict[str, Any],
    track_signals: dict[int, np.ndarray],
    after_track_signals: dict[int, np.ndarray],
    before_mono: np.ndarray,
    after_mono: np.ndarray,
    region_slice: slice,
) -> dict[str, Any]:
    issue_type = str(focus_region.get("issue_type") or "")
    if issue_type == "master_clipping":
        return _build_master_clipping_overlay(
            before_mono,
            after_mono,
            region_before=before_mono[region_slice],
            region_after=after_mono[region_slice],
        )
    if issue_type == "track_clipping":
        if str(action.get("target_scope")) == "MASTER":
            return _build_master_clipping_overlay(
                before_mono,
                after_mono,
                kind="track_clipping",
                region_before=before_mono[region_slice],
                region_after=after_mono[region_slice],
            )
        target_track = int(action.get("target_track_id") or focus_region.get("track_id") or 0)
        before_track = _to_mono(track_signals.get(target_track, np.zeros((0, 2), dtype=np.float32)))
        after_track = _to_mono(
            after_track_signals.get(target_track, np.zeros((0, 2), dtype=np.float32))
        )
        return _build_master_clipping_overlay(
            before_track,
            after_track,
            kind="track_clipping",
            region_before=before_track[region_slice],
            region_after=after_track[region_slice],
        )
    if issue_type == "sibilance":
        return _build_band_focus_overlay(
            before_mono,
            after_mono,
            band=DEFAULT_SIBILANCE_BAND,
            kind="sibilance",
            region_before=before_mono[region_slice],
            region_after=after_mono[region_slice],
        )
    if issue_type == "high_band_harshness":
        return _build_band_focus_overlay(
            before_mono,
            after_mono,
            band=DEFAULT_HARSHNESS_BAND,
            kind="high_band_harshness",
            region_before=before_mono[region_slice],
            region_after=after_mono[region_slice],
        )
    if issue_type == "band_overlap":
        return _build_overlap_overlay(
            state=state,
            focus_region=focus_region,
            action=action,
            track_signals=track_signals,
            after_track_signals=after_track_signals,
            region_slice=region_slice,
        )
    return {"kind": issue_type, "metrics": {}, "series": {}}


def _resolve_metric_signals(
    *,
    focus_region: dict[str, Any],
    action: dict[str, Any],
    track_signals: dict[int, np.ndarray],
    after_track_signals: dict[int, np.ndarray],
    before_mono: np.ndarray,
    after_mono: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str]:
    issue_type = str(focus_region.get("issue_type") or "")
    if issue_type == "master_clipping" or str(action.get("target_scope")) == "MASTER":
        return before_mono, after_mono, "master"

    target_track_id = int(action.get("target_track_id") or focus_region.get("track_id") or 0)
    if target_track_id:
        before_track = _to_mono(
            track_signals.get(target_track_id, np.zeros((0, 2), dtype=np.float32))
        )
        after_track = _to_mono(
            after_track_signals.get(target_track_id, np.zeros((0, 2), dtype=np.float32))
        )
        if before_track.size and after_track.size:
            return before_track, after_track, f"track:{target_track_id}"

    return before_mono, after_mono, "master"


def _build_master_clipping_overlay(
    before_signal: np.ndarray,
    after_signal: np.ndarray,
    *,
    kind: str = "master_clipping",
    region_before: np.ndarray | None = None,
    region_after: np.ndarray | None = None,
) -> dict[str, Any]:
    metrics_before = before_signal if region_before is None else region_before
    metrics_after = after_signal if region_after is None else region_after
    before_markers = _build_clip_markers(before_signal)
    after_markers = _build_clip_markers(after_signal)
    return {
        "kind": kind,
        "metrics": {
            "before_clipped_sample_count": int(np.sum(np.abs(metrics_before) >= 0.999)),
            "after_clipped_sample_count": int(np.sum(np.abs(metrics_after) >= 0.999)),
            "before_true_peak_dbfs": round(_to_dbfs(_oversampled_true_peak(metrics_before)), 3),
            "after_true_peak_dbfs": round(_to_dbfs(_oversampled_true_peak(metrics_after)), 3),
        },
        "series": {
            "before_clip_markers_ms": before_markers,
            "after_clip_markers_ms": after_markers,
        },
    }


def _build_band_focus_overlay(
    before_signal: np.ndarray,
    after_signal: np.ndarray,
    *,
    band: tuple[int, int],
    kind: str,
    region_before: np.ndarray | None = None,
    region_after: np.ndarray | None = None,
) -> dict[str, Any]:
    before_curve = _build_band_energy_curve(before_signal, *band)
    after_curve = _build_band_energy_curve(after_signal, *band)
    metric_before = before_signal if region_before is None else region_before
    metric_after = after_signal if region_after is None else region_after
    metric_before_curve = _build_band_energy_curve(metric_before, *band)
    metric_after_curve = _build_band_energy_curve(metric_after, *band)
    before_mean = (
        float(np.mean([item["value"] for item in metric_before_curve])) if metric_before_curve else 0.0
    )
    after_mean = (
        float(np.mean([item["value"] for item in metric_after_curve])) if metric_after_curve else 0.0
    )
    return {
        "kind": kind,
        "metrics": {
            "band_low_hz": band[0],
            "band_high_hz": band[1],
            "before_band_mean_db": round(before_mean, 3),
            "after_band_mean_db": round(after_mean, 3),
            "band_delta_db": round(after_mean - before_mean, 3),
        },
        "series": {
            "before_band_curve": before_curve,
            "after_band_curve": after_curve,
        },
    }


def _build_overlap_overlay(
    *,
    state: dict[str, Any],
    focus_region: dict[str, Any],
    action: dict[str, Any],
    track_signals: dict[int, np.ndarray],
    after_track_signals: dict[int, np.ndarray],
    region_slice: slice,
) -> dict[str, Any]:
    preserve_clip_id = state.get("preserve_clip_id")
    preserve_track_id = _resolve_clip_track_id(state.get("clip_index", []), preserve_clip_id)
    target_track_id = int(action.get("target_track_id") or focus_region.get("track_id") or 0)
    if preserve_track_id is None:
        preserve_track_id = int(focus_region.get("secondary_track_id") or 0)
    before_target = _to_mono(track_signals.get(target_track_id, np.zeros((0, 2), dtype=np.float32)))
    after_target = _to_mono(
        after_track_signals.get(target_track_id, np.zeros((0, 2), dtype=np.float32))
    )
    preserve_signal = _to_mono(
        track_signals.get(int(preserve_track_id or 0), np.zeros((0, 2), dtype=np.float32))
    )
    metric_before_target = before_target[region_slice]
    metric_after_target = after_target[region_slice]
    metric_preserve_signal = preserve_signal[region_slice]
    before_body_overlap = _band_overlap_ratio(
        metric_before_target,
        metric_preserve_signal,
        *DEFAULT_BODY_BAND,
    )
    after_body_overlap = _band_overlap_ratio(
        metric_after_target,
        metric_preserve_signal,
        *DEFAULT_BODY_BAND,
    )
    before_presence_overlap = _band_overlap_ratio(
        metric_before_target,
        metric_preserve_signal,
        *DEFAULT_PRESENCE_BAND,
    )
    after_presence_overlap = _band_overlap_ratio(
        metric_after_target,
        metric_preserve_signal,
        *DEFAULT_PRESENCE_BAND,
    )
    return {
        "kind": "band_overlap",
        "metrics": {
            "target_track_id": target_track_id,
            "preserve_track_id": preserve_track_id,
            "before_body_overlap": round(before_body_overlap, 3),
            "after_body_overlap": round(after_body_overlap, 3),
            "before_presence_overlap": round(before_presence_overlap, 3),
            "after_presence_overlap": round(after_presence_overlap, 3),
        },
        "series": {
            "before_body_curve": _build_band_energy_curve(before_target, *DEFAULT_BODY_BAND),
            "after_body_curve": _build_band_energy_curve(after_target, *DEFAULT_BODY_BAND),
            "preserve_body_curve": _build_band_energy_curve(preserve_signal, *DEFAULT_BODY_BAND),
            "before_presence_curve": _build_band_energy_curve(before_target, *DEFAULT_PRESENCE_BAND),
            "after_presence_curve": _build_band_energy_curve(after_target, *DEFAULT_PRESENCE_BAND),
            "preserve_presence_curve": _build_band_energy_curve(
                preserve_signal,
                *DEFAULT_PRESENCE_BAND,
            ),
        },
    }


def _resolve_clip_track_id(
    clip_index: list[dict[str, object | None]],
    clip_id: Any,
) -> int | None:
    if clip_id is None:
        return None
    for clip in clip_index:
        if str(clip.get("clip_id")) == str(clip_id):
            return int(clip.get("track_id") or 0)
    return None


def _build_prompt_feedback_hints(
    *,
    focus_region: dict[str, Any],
    before_mono: np.ndarray,
    after_mono: np.ndarray,
    issue_overlay: dict[str, Any],
    excerpt_start_ms: int,
    excerpt_end_ms: int,
) -> list[dict[str, str]]:
    region_start_frame = ms_to_frames(
        max(int(focus_region.get("start_ms") or 0) - excerpt_start_ms, 0),
        DSP_TARGET_SR,
    )
    region_end_frame = ms_to_frames(
        max(int(focus_region.get("end_ms") or excerpt_end_ms) - excerpt_start_ms, 0),
        DSP_TARGET_SR,
    )
    region_end_frame = min(max(region_end_frame, region_start_frame + 1), before_mono.size)
    diff = np.abs(after_mono - before_mono)
    inside = diff[region_start_frame:region_end_frame]
    outside = np.concatenate([diff[:region_start_frame], diff[region_end_frame:]])
    inside_mean = float(np.mean(inside)) if inside.size else 0.0
    outside_mean = float(np.mean(outside)) if outside.size else 0.0
    leakage_ratio = outside_mean / max(inside_mean, 1e-6)
    rms_delta_db = _rms_dbfs(after_mono) - _rms_dbfs(before_mono)
    hints = [
        _build_hint(
            label="변화 범위 적합성",
            verdict="good" if leakage_ratio <= 0.35 else "warn",
            detail=(
                f"region 외부 변화 비율 {leakage_ratio:.2f}"
                if leakage_ratio > 0
                else "region 내부 중심으로 변화가 모였습니다."
            ),
            prompt_hint=(
                "문제 구간 밖 변화는 최소화하고 region 내부에서만 처리하라고 명시하라."
                if leakage_ratio > 0.35
                else "현재처럼 문제 구간 중심 처리를 유지하라고 명시하라."
            ),
        ),
        _build_hint(
            label="전체 레벨 부작용",
            verdict="warn" if abs(rms_delta_db) >= 1.5 else "good",
            detail=f"excerpt RMS 변화 {rms_delta_db:.2f}dB",
            prompt_hint=(
                "문제 해결과 별개로 전체 레벨 변화는 1dB 이내로 제한하라고 명시하라."
                if abs(rms_delta_db) >= 1.5
                else "전체 레벨 보존을 유지하라고 명시하라."
            ),
        ),
    ]
    issue_kind = issue_overlay.get("kind")
    issue_metrics = issue_overlay.get("metrics", {})
    if issue_kind in {"sibilance", "high_band_harshness"}:
        band_delta_db = float(issue_metrics.get("band_delta_db") or 0.0)
        hints.append(
            _build_hint(
                label="목표 대역 강도",
                verdict="warn" if abs(band_delta_db) < 0.8 else "good",
                detail=f"목표 대역 평균 변화 {band_delta_db:.2f}dB",
                prompt_hint=(
                    "목표 대역 감쇠량을 조금 더 분명하게 지시하라."
                    if abs(band_delta_db) < 0.8
                    else "현재 대역 제어 폭을 기준값으로 삼으라고 명시하라."
                ),
            )
        )
    elif issue_kind in {"master_clipping", "track_clipping"}:
        before_clipped = int(issue_metrics.get("before_clipped_sample_count") or 0)
        after_clipped = int(issue_metrics.get("after_clipped_sample_count") or 0)
        hints.append(
            _build_hint(
                label="클리핑 감소 효과",
                verdict="good" if after_clipped < before_clipped else "warn",
                detail=f"clipped samples {before_clipped} -> {after_clipped}",
                prompt_hint=(
                    "true peak 감소를 우선 목표로 두고 limiter 또는 trim 강도를 높이라고 명시하라."
                    if after_clipped >= before_clipped
                    else "현재처럼 true peak 보호 우선 원칙을 유지하라고 명시하라."
                ),
            )
        )
    elif issue_kind == "band_overlap":
        before_body = float(issue_metrics.get("before_body_overlap") or 0.0)
        after_body = float(issue_metrics.get("after_body_overlap") or 0.0)
        hints.append(
            _build_hint(
                label="대역 분리 효과",
                verdict="good" if after_body < before_body else "warn",
                detail=f"body overlap {before_body:.2f} -> {after_body:.2f}",
                prompt_hint=(
                    "preserve 대상과 겹치는 중역만 우선 줄이라고 명시하라."
                    if after_body >= before_body
                    else "preserve 대상과 충돌하는 body band를 우선 줄이라는 지시를 유지하라."
                ),
            )
        )
    return hints


def _build_hint(*, label: str, verdict: str, detail: str, prompt_hint: str) -> dict[str, str]:
    return {
        "label": label,
        "verdict": verdict,
        "detail": detail,
        "prompt_hint": prompt_hint,
    }


def _build_waveform_points(signal: np.ndarray) -> list[float]:
    if signal.size == 0:
        return [0.0] * WAVEFORM_POINT_COUNT
    chunk_size = max(int(math.ceil(signal.size / WAVEFORM_POINT_COUNT)), 1)
    values: list[float] = []
    for start in range(0, signal.size, chunk_size):
        chunk = signal[start : start + chunk_size]
        values.append(round(float(np.max(np.abs(chunk))) if chunk.size else 0.0, 5))
        if len(values) == WAVEFORM_POINT_COUNT:
            break
    if len(values) < WAVEFORM_POINT_COUNT:
        values.extend([0.0] * (WAVEFORM_POINT_COUNT - len(values)))
    return values


def _build_spectrum_bins(signal: np.ndarray) -> list[float]:
    if signal.size == 0:
        return [0.0] * SPECTRUM_BIN_COUNT
    n_fft = 2048 if signal.size >= 2048 else int(2 ** math.ceil(math.log2(max(signal.size, 2))))
    stft = librosa.stft(signal, n_fft=n_fft, hop_length=max(n_fft // 4, 1), center=False)
    magnitude = np.mean(np.abs(stft), axis=1)
    if magnitude.size == 0:
        return [0.0] * SPECTRUM_BIN_COUNT
    edges = np.linspace(0, magnitude.size, SPECTRUM_BIN_COUNT + 1, dtype=int)
    bins: list[float] = []
    for index in range(SPECTRUM_BIN_COUNT):
        start = edges[index]
        end = max(edges[index + 1], start + 1)
        value = float(np.mean(magnitude[start:end]))
        bins.append(round(_to_dbfs(value), 3))
    return bins


def _build_loudness_curve(signal: np.ndarray) -> list[dict[str, float]]:
    if signal.size == 0:
        return []
    window_frames = max(ms_to_frames(LOUDNESS_WINDOW_MS, DSP_TARGET_SR), 1)
    curve: list[dict[str, float]] = []
    for start_frame in range(0, signal.size, window_frames):
        end_frame = min(start_frame + window_frames, signal.size)
        window = signal[start_frame:end_frame]
        curve.append(
            {
                "x_ms": float(_samples_to_ms(start_frame)),
                "value": round(_rms_dbfs(window), 3),
            }
        )
    return curve


def _build_clip_markers(signal: np.ndarray) -> list[float]:
    indices = np.where(np.abs(signal) >= 0.999)[0]
    if indices.size == 0:
        return []
    step = max(int(math.ceil(indices.size / 48)), 1)
    return [float(_samples_to_ms(int(index))) for index in indices[::step]]


def _build_band_energy_curve(signal: np.ndarray, low_hz: int, high_hz: int) -> list[dict[str, float]]:
    if signal.size == 0:
        return []
    n_fft = 1024 if signal.size >= 1024 else int(2 ** math.ceil(math.log2(max(signal.size, 2))))
    hop_length = max(n_fft // 4, 1)
    stft = librosa.stft(signal, n_fft=n_fft, hop_length=hop_length, center=False)
    power = np.abs(stft) ** 2
    freqs = librosa.fft_frequencies(sr=DSP_TARGET_SR, n_fft=n_fft)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(mask):
        return []
    curve: list[dict[str, float]] = []
    for frame_index in range(power.shape[1]):
        value = float(np.mean(power[mask, frame_index]))
        curve.append(
            {
                "x_ms": float(_samples_to_ms(frame_index * hop_length)),
                "value": round(_to_dbfs(math.sqrt(max(value, 1e-12))), 3),
            }
        )
    return curve


def _band_overlap_ratio(
    first_signal: np.ndarray,
    second_signal: np.ndarray,
    low_hz: int,
    high_hz: int,
) -> float:
    if first_signal.size == 0 or second_signal.size == 0:
        return 0.0
    first_energy = _band_energy(first_signal, low_hz, high_hz)
    second_energy = _band_energy(second_signal, low_hz, high_hz)
    denominator = max(first_energy + second_energy, 1e-9)
    return float((2.0 * min(first_energy, second_energy)) / denominator)


def _band_energy(signal: np.ndarray, low_hz: int, high_hz: int) -> float:
    if signal.size == 0:
        return 0.0
    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(signal.size, 1.0 / DSP_TARGET_SR)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    return float(np.sum(power[mask]))


def _rms_dbfs(signal: np.ndarray) -> float:
    if signal.size == 0:
        return _to_dbfs(0.0)
    rms = float(np.sqrt(np.mean(np.square(signal))))
    return _to_dbfs(rms)


def _crest_factor_db(signal: np.ndarray) -> float:
    if signal.size == 0:
        return 0.0
    peak = float(np.max(np.abs(signal)))
    rms = float(np.sqrt(np.mean(np.square(signal))))
    return max(_to_dbfs(peak) - _to_dbfs(rms), 0.0)


def _oversampled_true_peak(signal: np.ndarray) -> float:
    if signal.size == 0:
        return 0.0
    if signal.size == 1:
        return float(np.max(np.abs(signal)))
    oversampled = resample_poly(signal, up=TRUE_PEAK_OVERSAMPLE_FACTOR, down=1)
    return float(np.max(np.abs(oversampled)))


def _to_dbfs(amplitude: float) -> float:
    return 20.0 * math.log10(max(amplitude, 1e-6))


def _db_to_linear(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _samples_to_ms(sample_index: int) -> int:
    return int(round((sample_index / DSP_TARGET_SR) * 1000))
