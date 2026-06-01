from __future__ import annotations

import logging

from copy import deepcopy

from app.graph.state import RAW_DSP_STATE_DEFAULTS, WorkflowState, utc_now

logger = logging.getLogger(__name__)


def append_transition(state: WorkflowState, name: str) -> list[str]:
    return [*state.get("transition_log", []), name]


def workflow_update(
    state: WorkflowState,
    *,
    node: str,
    phase: str,
    progress: int,
    runtime_status: str | None = None,
    durable_status: str | None = None,
    extra: dict | None = None,
) -> WorkflowState:
    payload: WorkflowState = {
        "current_node": node,
        "phase": phase,
        "progress": progress,
        "heartbeat_at": utc_now(),
        "transition_log": append_transition(state, node),
    }
    if runtime_status is not None:
        payload["runtime_status"] = runtime_status
    if durable_status is not None:
        payload["durable_status"] = durable_status
    if extra:
        payload.update(extra)
    _log_workflow_update(state, payload)
    return payload


def artifact_id(state: WorkflowState, label: str) -> str:
    return f"{state['job_id']}:{label}:{len(state.get('transition_log', [])) + 1}"


def decide_validation_result(state: WorkflowState, *, mode_key: str) -> str:
    mode = state.get(mode_key, "PASS")
    revise_count = state.get("revise_count", 0)
    max_revise_count = state.get("max_revise_count", 5)
    if mode == "REJECT":
        return "REJECT"
    if mode == "REVISE_ONCE" and revise_count < max_revise_count:
        return "REVISE"
    return "PASS"


def build_action(
    state: WorkflowState,
    *,
    index: int,
    action_type: str,
    track_id: int | None,
    start_ms: int,
    end_ms: int,
    band_low_hz: int | None = None,
    band_high_hz: int | None = None,
    gain_delta_db: float | None = None,
    params: dict | None = None,
    target_scope: str = "TRACK",
) -> dict:
    action = {
        "actionType": action_type,
        "targetTrackId": track_id,
        "targetClipId": None,
        "startMs": start_ms,
        "endMs": end_ms,
        "bandLowHz": band_low_hz,
        "bandHighHz": band_high_hz,
        "gainDeltaDb": gain_delta_db,
        "params": params or {},
        "targetScope": target_scope,
        "actionId": f"{state['job_id']}-action-{index}",
        "jobId": int(state["job_id"]),
    }
    static_eq_band = _resolve_static_eq_band_fields(
        band_low_hz=band_low_hz,
        band_high_hz=band_high_hz,
        params=params or {},
        target_scope=target_scope,
    )
    if static_eq_band is not None:
        action.update(static_eq_band)
        action["sourceType"] = "AI_CONFIRM"
    return action


def _resolve_static_eq_band_fields(
    *,
    band_low_hz: int | None,
    band_high_hz: int | None,
    params: dict,
    target_scope: str,
) -> dict[str, object] | None:
    if target_scope != "TRACK":
        return None
    if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int):
        return None
    if band_low_hz <= 0 or band_high_hz <= band_low_hz:
        return None

    frequency_hz = int(round((band_low_hz * band_high_hz) ** 0.5))
    q_value = params.get("q") if isinstance(params, dict) else None
    if isinstance(q_value, int | float) and float(q_value) > 0:
        q = round(float(q_value), 3)
    else:
        q = round(float(frequency_hz) / float(band_high_hz - band_low_hz), 3)
    if q <= 0:
        return None
    return {
        "frequencyHz": frequency_hz,
        "q": q,
        "eqType": "BELL",
    }


def clear_raw_dsp_state() -> dict[str, object]:
    payload = {key: deepcopy(value) for key, value in RAW_DSP_STATE_DEFAULTS.items()}
    payload["clip_feature_artifact_id"] = None
    return payload


def resolve_clip_track_id(state: WorkflowState, clip_id: int | None) -> int | None:
    if clip_id is None:
        return None
    for clip in state.get("clip_index", []):
        if int(clip.get("clip_id") or 0) == int(clip_id):
            return int(clip["track_id"])
    return None


def resolve_preserve_clip_id_for_track(
    state: WorkflowState,
    region: dict[str, object],
    preserve_track_id: int,
) -> int | None:
    for clip_id in region.get("affected_clip_ids", []) or []:
        resolved_track_id = resolve_clip_track_id(state, int(clip_id))
        if resolved_track_id is not None and int(resolved_track_id) == int(preserve_track_id):
            return int(clip_id)

    region_start_ms = region.get("start_ms")
    region_end_ms = region.get("end_ms")
    for clip in state.get("clip_index", []):
        clip_track_id = clip.get("track_id")
        if clip_track_id is None or int(clip_track_id) != int(preserve_track_id):
            continue
        clip_start_ms = clip.get("start_ms")
        clip_end_ms = clip.get("end_ms")
        if not all(
            isinstance(value, int)
            for value in (region_start_ms, region_end_ms, clip_start_ms, clip_end_ms)
        ):
            continue
        if int(clip_end_ms) <= int(region_start_ms) or int(clip_start_ms) >= int(region_end_ms):
            continue
        return int(clip.get("clip_id") or 0)
    return None


def build_selection_context(
    state: WorkflowState,
    region: dict[str, object],
    preserve_clip_id: int,
) -> dict[str, object]:
    preserve_track_id = resolve_clip_track_id(state, preserve_clip_id)
    selected_track_id = _resolve_selected_track_id(state) or preserve_track_id
    involved_track_ids = [int(track_id) for track_id in region.get("involved_track_ids", [])]
    track_ids_for_labels = list(dict.fromkeys([
        *involved_track_ids,
        *(
            track_id
            for track_id in (selected_track_id, preserve_track_id)
            if isinstance(track_id, int)
        ),
    ]))
    non_preserve_track_ids = [
        track_id
        for track_id in involved_track_ids
        if preserve_track_id is None or track_id != preserve_track_id
    ]
    track_name_map = {
        track_id: _track_name(state, track_id)
        for track_id in track_ids_for_labels
    }
    return {
        "selectedTrackId": selected_track_id,
        "preserveTrackId": preserve_track_id,
        "selectedTrackIsProtected": (
            selected_track_id is not None and selected_track_id == preserve_track_id
        ),
        "selectedClipId": preserve_clip_id,
        "preserveClipId": preserve_clip_id,
        "primaryTrackId": region.get("track_id"),
        "secondaryTrackId": region.get("secondary_track_id"),
        "bandOverlapSubtype": region.get("band_overlap_subtype"),
        "bandFocusLabel": region.get("band_focus_label"),
        "trackBodyContributions": deepcopy(region.get("track_body_contributions") or {}),
        "trackNameMap": track_name_map,
        "nonPreserveOverlappingTrackIds": non_preserve_track_ids,
    }


def _resolve_selected_track_id(state: WorkflowState) -> int | None:
    action_payload = state.get("action_payload")
    if not isinstance(action_payload, dict):
        return None
    selected_track_ids = action_payload.get("selected_track_ids")
    if not isinstance(selected_track_ids, list):
        return None
    for track_id in selected_track_ids:
        if isinstance(track_id, bool):
            continue
        if isinstance(track_id, int):
            return track_id
        if isinstance(track_id, str):
            stripped = track_id.strip()
            if stripped:
                try:
                    return int(stripped)
                except ValueError:
                    continue
    return None


def _track_name(state: WorkflowState, track_id: int) -> str | None:
    track_name_map = state.get("track_name_map") or {}
    track_name = track_name_map.get(int(track_id))
    if isinstance(track_name, str) and track_name.strip():
        return track_name.strip()
    return None


def _log_workflow_update(previous: WorkflowState, current: WorkflowState) -> None:
    log_level = _decide_log_level(current)
    summary = (
        "workflow node update | "
        f"job_id={current.get('job_id', previous.get('job_id'))} "
        f"node={current.get('current_node')} "
        f"phase={current.get('phase')} "
        f"progress={current.get('progress')} "
        f"runtime_status={current.get('runtime_status', previous.get('runtime_status'))} "
        f"durable_status={current.get('durable_status', previous.get('durable_status'))}"
    )
    logger.log(log_level, summary)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "workflow node debug | "
            f"job_id={current.get('job_id', previous.get('job_id'))} "
            f"transition_count={len(current.get('transition_log', []))} "
            f"track_count={len(current.get('track_ids', previous.get('track_ids', [])))} "
            "sampled_clip_count="
            f"{len(current.get('sampled_clip_ids', previous.get('sampled_clip_ids', [])))} "
            "analysis_region_count="
            f"{len(current.get('analysis_regions', previous.get('analysis_regions', [])))} "
            "detected_issue_count="
            f"{len(current.get('detected_issues', previous.get('detected_issues', [])))} "
            "ranked_candidate_count="
            f"{len(current.get('ranked_candidate_ids', previous.get('ranked_candidate_ids', [])))} "
            "latest_artifact_id="
            f"{current.get('latest_artifact_id', previous.get('latest_artifact_id'))} "
            f"failure_code={current.get('failure_code', previous.get('failure_code'))}"
        )


def _decide_log_level(current: WorkflowState) -> int:
    runtime_status = current.get("runtime_status")
    phase = current.get("phase", "")
    if runtime_status == "failed" or current.get("current_node") == "fail_workflow":
        return logging.ERROR
    if runtime_status == "waiting_for_user" or phase.startswith("waiting_for_user"):
        return logging.WARNING
    if runtime_status == "completed" or phase == "completed":
        return logging.INFO
    return logging.INFO
