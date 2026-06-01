from __future__ import annotations

import base64
import io
import json
import wave
from copy import deepcopy
from typing import Any

import numpy as np
from fastapi import HTTPException, status

from app.graph.state import build_workflow_initial_state
from app.persistence.projections import build_workflow_projections
from app.services.workflow_artifacts import WorkflowArtifactDocument, get_workflow_artifact_store
from app.services.workflow_jobs import get_workflow_job_store
from app.services.workflow_preview_compare import (
    _apply_preview_actions,
    _build_excerpt_track_signals,
    _require_preview_ready,
    _resolve_compare_actions,
    _sum_track_signals,
    build_preview_compare_payload,
)
from app.services.workflow_snapshots import TimelineSnapshotDocument, get_workflow_snapshot_store


def build_workflow_inspection_report(job_id: int) -> dict[str, Any]:
    store = get_workflow_job_store()
    snapshot_store = get_workflow_snapshot_store()
    artifact_store = get_workflow_artifact_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow job was not found.",
        )
    if not job.timeline_snapshot_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow job does not have a timeline snapshot.",
        )
    snapshot = snapshot_store.get_snapshot(job.timeline_snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow timeline snapshot was not found.",
        )

    state = _build_restored_job_state(job)
    projections = build_workflow_projections(state).model_dump(mode="json")
    planner_artifact = _load_artifact(artifact_store, state.get("planner_artifact_id"))
    critic_artifact = _load_artifact(artifact_store, state.get("critic_artifact_id"))
    execution_plan_artifact = _find_latest_artifact(
        artifact_store,
        state.get("mongo_artifact_ids", []),
        artifact_type="execution_plan",
    )

    preview_compare: dict[str, Any] | None = None
    preview_audio: dict[str, Any] | None = None
    preview_error: dict[str, Any] | None = None
    try:
        preview_compare = build_preview_compare_payload(state, snapshot, mode="preview")
        preview_audio = _build_preview_audio_payload(state, snapshot)
    except HTTPException as exc:
        preview_error = {
            "status_code": exc.status_code,
            "detail": exc.detail,
        }

    return {
        "job": {
            "id": job.id,
            "project_id": job.project_id,
            "status": job.status,
            "phase": job.phase,
            "current_node": job.current_node,
            "progress": job.progress,
            "timeline_snapshot_id": job.timeline_snapshot_id,
            "requested_by": job.requested_by,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_code": job.error_code,
            "error_message": job.error_message,
        },
        "snapshot": _build_snapshot_report(snapshot),
        "analysis": {
            "detected_issues": list(state.get("detected_issues", [])),
            "ranked_candidate_ids": [int(region_id) for region_id in state.get("ranked_candidate_ids", [])],
            "selected_region_id": state.get("selected_region_id"),
            "preserve_clip_id": state.get("preserve_clip_id"),
            "suggestion_payload": deepcopy(state.get("suggestion_payload") or {}),
            "regions": [_build_region_report(region, state) for region in state.get("analysis_regions", [])],
        },
        "planner": {
            "status": state.get("plan_status"),
            "revise_count": state.get("revise_count", 0),
            "raw_text": _resolve_planner_raw_text(state, planner_artifact),
            "plan_payload": deepcopy(state.get("plan_payload") or {}),
            "artifact": planner_artifact.model_dump(mode="json") if planner_artifact else None,
        },
        "critic": {
            "result": state.get("critic_result"),
            "revision_notes": list(state.get("plan_revision_notes", [])),
            "raw_text": _resolve_critic_raw_text(state, critic_artifact),
            "artifact": critic_artifact.model_dump(mode="json") if critic_artifact else None,
        },
        "execution_plan": (
            execution_plan_artifact.model_dump(mode="json") if execution_plan_artifact else None
        ),
        "preview": {
            "render": projections.get("preview_render"),
            "compare": preview_compare,
            "audio": preview_audio,
            "error": preview_error,
        },
        "projections": projections,
    }


def _build_snapshot_report(snapshot: TimelineSnapshotDocument) -> dict[str, Any]:
    track_names = {
        int(track.get("track_id")): track.get("name")
        for track in snapshot.snapshot.get("tracks", [])
        if isinstance(track, dict) and track.get("track_id") is not None
    }
    clips_by_track: dict[int, list[dict[str, Any]]] = {}
    for clip in snapshot.clip_index:
        track_id = int(clip.get("track_id") or 0)
        clips_by_track.setdefault(track_id, []).append(
            {
                "clip_id": clip.get("clip_id"),
                "track_id": track_id,
                "start_ms": clip.get("start_ms"),
                "end_ms": clip.get("end_ms"),
                "audio_start_ms": clip.get("audio_start_ms"),
                "audio_duration_ms": clip.get("audio_duration_ms"),
            }
        )
    tracks = []
    for track_id in snapshot.track_ids:
        tracks.append(
            {
                "track_id": int(track_id),
                "name": track_names.get(int(track_id)) or f"Track {track_id}",
                "clips": clips_by_track.get(int(track_id), []),
                "eq_bands": deepcopy(snapshot.track_eq_map.get(str(track_id), [])),
            }
        )
    return {
        "duration_ms": snapshot.duration_ms,
        "bpm": snapshot.bpm,
        "numerator": snapshot.numerator,
        "denominator": snapshot.denominator,
        "bar_mapping": deepcopy(snapshot.bar_mapping),
        "tracks": tracks,
    }


def _build_region_report(region: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    region_id = int(region["id"])
    exact_metrics = {
        "score": region.get("score"),
        "ranking_score": (state.get("ranking_scores") or {}).get(region_id),
        "band_confidence": region.get("band_confidence"),
        "current_true_peak_dbtp": region.get("current_true_peak_dbtp"),
        "target_ceiling_dbtp": region.get("target_ceiling_dbtp"),
        "recommended_reduction_db": region.get("recommended_reduction_db"),
        "track_body_contributions": deepcopy(region.get("track_body_contributions") or {}),
        "track_contribution_scores": deepcopy(region.get("track_contribution_scores") or {}),
        "contributor_band_hints": deepcopy(region.get("contributor_band_hints") or {}),
    }
    exact_metrics = {key: value for key, value in exact_metrics.items() if value not in (None, {}, [])}
    involved_track_ids = [int(track_id) for track_id in region.get("involved_track_ids", [])]
    contributing_track_ids = [int(track_id) for track_id in region.get("contributing_track_ids", [])]
    return {
        "id": region_id,
        "issue_type": region.get("issue_type"),
        "summary": region.get("summary"),
        "severity": region.get("severity", "MEDIUM"),
        "requires_user_action": bool(region.get("requires_user_action", True)),
        "start_ms": region.get("start_ms"),
        "end_ms": region.get("end_ms"),
        "measure_start": region.get("measure_start"),
        "measure_end": region.get("measure_end"),
        "track_id": region.get("track_id"),
        "secondary_track_id": region.get("secondary_track_id"),
        "involved_track_ids": involved_track_ids,
        "contributing_track_ids": contributing_track_ids,
        "affected_clip_ids": [int(clip_id) for clip_id in region.get("affected_clip_ids", [])],
        "band_low_hz": region.get("band_low_hz"),
        "band_high_hz": region.get("band_high_hz"),
        "center_hz": region.get("center_hz"),
        "exact_metrics": exact_metrics,
        "raw_region": deepcopy(region),
    }


def _resolve_planner_raw_text(
    state: dict[str, Any],
    planner_artifact: WorkflowArtifactDocument | None,
) -> str:
    raw_text = state.get("planner_raw_text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text
    artifact_raw = (planner_artifact.payload if planner_artifact else {}).get("rawText")
    if isinstance(artifact_raw, str) and artifact_raw.strip():
        return artifact_raw
    return json.dumps(state.get("plan_payload") or {}, ensure_ascii=False, indent=2)


def _resolve_critic_raw_text(
    state: dict[str, Any],
    critic_artifact: WorkflowArtifactDocument | None,
) -> str:
    raw_text = state.get("critic_raw_text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text
    artifact_raw = (critic_artifact.payload if critic_artifact else {}).get("rawText")
    if isinstance(artifact_raw, str) and artifact_raw.strip():
        return artifact_raw
    return json.dumps(
        {
            "result": state.get("critic_result"),
            "notes": state.get("plan_revision_notes", []),
        },
        ensure_ascii=False,
        indent=2,
    )


def _load_artifact(
    artifact_store: Any,
    artifact_id: str | None,
) -> WorkflowArtifactDocument | None:
    if not artifact_id:
        return None
    return artifact_store.get_artifact(str(artifact_id))


def _find_latest_artifact(
    artifact_store: Any,
    artifact_ids: list[str],
    *,
    artifact_type: str,
) -> WorkflowArtifactDocument | None:
    for artifact_id in reversed([str(value) for value in artifact_ids]):
        artifact = artifact_store.get_artifact(artifact_id)
        if artifact is not None and artifact.artifact_type == artifact_type:
            return artifact
    return None


def _build_preview_audio_payload(
    state: dict[str, Any],
    snapshot: TimelineSnapshotDocument,
) -> dict[str, Any]:
    preview = _require_preview_ready(state)
    excerpt_start_ms = int(preview["preview_excerpt_range"]["start_ms"])
    excerpt_end_ms = int(preview["preview_excerpt_range"]["end_ms"])
    track_signals = _build_excerpt_track_signals(
        clip_index=snapshot.clip_index,
        excerpt_start_ms=excerpt_start_ms,
        excerpt_end_ms=excerpt_end_ms,
    )
    before_master = _sum_track_signals(track_signals)
    after_track_signals = {
        track_id: signal.copy()
        for track_id, signal in track_signals.items()
    }
    after_master = _apply_preview_actions(
        excerpt_start_ms=excerpt_start_ms,
        before_master=before_master,
        track_signals=after_track_signals,
        actions=_resolve_compare_actions(state, mode="preview"),
    )
    return {
        "excerpt_start_ms": excerpt_start_ms,
        "excerpt_end_ms": excerpt_end_ms,
        "before_excerpt_wav_uri": _encode_wav_data_uri(before_master),
        "after_excerpt_wav_uri": _encode_wav_data_uri(after_master),
    }


def _encode_wav_data_uri(signal: np.ndarray) -> str:
    waveform = np.asarray(signal, dtype=np.float32)
    if waveform.ndim == 1:
        waveform = waveform[:, np.newaxis]
    waveform = np.clip(waveform, -1.0, 1.0)
    pcm = (waveform * 32767.0).astype("<i2")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(waveform.shape[1])
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm.tobytes())
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


def _build_restored_job_state(job: Any) -> dict[str, Any]:
    state = build_workflow_initial_state(job_id=job.id, project_id=job.project_id)
    state.update(job.state_snapshot)
    state.update(
        {
            "job_id": job.id,
            "project_id": job.project_id,
            "phase": job.phase,
            "current_node": job.current_node,
            "progress": job.progress,
            "durable_status": job.status,
            "timeline_snapshot_id": job.timeline_snapshot_id,
            "requested_by": job.requested_by,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "failure_code": job.error_code,
            "failure_message": job.error_message,
        }
    )
    return state
