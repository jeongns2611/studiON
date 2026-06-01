from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, NotRequired
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from typing_extensions import TypedDict

RAW_DSP_STATE_DEFAULTS = {
    "track_frames": {},
    "mix_frames": [],
    "track_power_spectra": {},
    "mix_power_spectra": [],
    "frequency_bins_hz": [],
}

IssueType = Literal[
    "band_overlap",
    "track_clipping",
    "master_clipping",
    "sibilance",
    "high_band_harshness",
]
ValidatorOutcome = Literal["PASS", "REVISE", "REJECT"]
CriticOutcome = Literal["PASS", "REVISE", "REJECT"]
# worker dispatch 메시지가 이번 실행을 어떤 종류로 처리해야 하는지 나타내는 제어 값이다.
# start는 최초 실행이고, 나머지는 사용자 입력 이후 특정 대기 지점부터 재개하는 흐름이다.
WorkflowDispatchType = Literal[
    "start",
    "resume_plan_input",
]
RequestMode = Literal["single", "batch"]
WorkflowUserDecision = Literal[
    "CONFIRM",
    "CANCEL",
    "RESUME",
]
RuntimeStatus = Literal[
    "queued",
    "running",
    "waiting_for_user",
    "failed",
    "completed",
]
DurableJobStatus = Literal[
    "REQUESTED",
    "RUNNING",
    "WAITING_USER",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
]
class WorkflowState(TypedDict, total=False):
    job_id: int
    project_id: int
    dispatch_type: WorkflowDispatchType | None
    phase: str
    current_node: str
    progress: int
    heartbeat_at: str
    transition_log: list[str]
    runtime_status: RuntimeStatus
    durable_status: DurableJobStatus
    langgraph_thread_id: str
    timeline_snapshot_id: str | None
    # snapshot 원문 대신 region 투영 계산에 필요한 파생 메타만 state에 유지한다.
    project_duration_ms: int | None
    bpm: float | None
    numerator: int | None
    denominator: int | None
    bar_mapping: list[dict]
    clip_index: list[dict]
    track_eq_map: dict[int, list[dict]]
    track_ids: list[int]
    track_name_map: dict[int, str | None]
    sampled_clip_ids: list[int]
    track_representative_specs: list[dict]
    role_candidate_track_ids: list[int]
    inferred_roles: dict[int, str]
    track_role_scores: dict[int, float]
    track_role_confidences: dict[int, float]
    issue_types: list[IssueType]
    detected_issues: list[IssueType]
    analysis_region_ids: list[int]
    analysis_regions: list[dict]
    master_clipping_candidates: list[dict]
    master_clipping_contributors: list[dict]
    promoted_track_clipping_regions: list[dict]
    ranked_candidate_ids: list[int]
    ranking_scores: dict[int, float]
    request_mode: RequestMode | None
    selected_region_id: int | None
    preserve_clip_id: int | None
    selected_region_selections: list[dict]
    issue_id: str | None
    action_type: str | None
    action_payload: dict | None
    user_feedback_message: str | None
    user_decision: WorkflowUserDecision | None
    user_feedback_recorded_at: str | None
    clip_feature_artifact_id: str | None
    dsp_scan_summary: dict[str, object]
    track_frames: dict[int, list[dict[str, object]]]
    mix_frames: list[dict[str, object]]
    track_power_spectra: dict[int, list[list[float]]]
    mix_power_spectra: list[list[float]]
    frequency_bins_hz: list[float]
    vocal_detected: bool
    clipping_fix_applied: bool
    clipping_fix_log_id: str | None
    sibilance_fix_applied: bool
    sibilance_fix_log_id: str | None
    high_band_harshness_fix_applied: bool
    auto_fix_log_artifact_id: str | None
    auto_fix_recipe_artifact_id: str | None
    plan_payload: dict
    planner_raw_text: str | None
    planner_artifact_id: str | None
    plan_status: str | None
    plan_revision_notes: list[str]
    batch_candidate_plans: list[dict]
    batch_failed_regions: list[dict]
    batch_final_track_envelopes: list[dict]
    batch_failed_envelopes: list[dict]
    batch_validation_summary: dict
    critic_raw_text: str | None
    critic_artifact_id: str | None
    suggestion_payload: dict
    suggestion_group_id: str | None
    preview_id: str | None
    preview_status: str | None
    preview_render_no: int
    preview_excerpt_start_ms: int | None
    preview_excerpt_end_ms: int | None
    preview_requested_at: str | None
    preview_started_at: str | None
    preview_completed_at: str | None
    preview_expired_at: str | None
    preview_error_code: str | None
    preview_error_message: str | None
    has_user_action_candidates: bool
    has_auto_fixable_eq_issues: bool
    preview_required: bool
    user_action_required: bool
    auto_preview_generated: bool
    validator_mode: str
    validator_result: ValidatorOutcome | None
    critic_mode: str
    critic_result: CriticOutcome | None
    revise_count: int
    max_revise_count: int
    latest_artifact_id: str | None
    mongo_artifact_ids: list[str]
    failure_code: str | None
    failure_message: str | None
    requested_by: int | None
    started_at: str | None
    completed_at: str | None
    notes: NotRequired[list[str]]


# Backward-compatible aliases while the rest of the AI app converges on WorkflowState.
RuntimeState = WorkflowState
ApplyState = WorkflowState


def utc_now() -> str:
    try:
        return datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    except ZoneInfoNotFoundError:
        return datetime.now(UTC).isoformat()


def build_workflow_initial_state(
    job_id: int,
    project_id: int,
    **overrides: object,
) -> WorkflowState:
    issue_types = overrides.pop("issue_types", None)
    state: WorkflowState = {
        "job_id": job_id,
        "project_id": project_id,
        "dispatch_type": None,
        "phase": "queued",
        "current_node": "load_entry_context",
        "progress": 0,
        "heartbeat_at": utc_now(),
        "transition_log": [],
        "runtime_status": "queued",
        "durable_status": "REQUESTED",
        "langgraph_thread_id": f"lg-thread:{job_id}",
        "timeline_snapshot_id": None,
        "project_duration_ms": None,
        "bpm": None,
        "numerator": None,
        "denominator": None,
        "bar_mapping": [],
        "clip_index": [],
        "track_eq_map": {},
        "track_ids": [],
        "track_name_map": {},
        "sampled_clip_ids": [],
        "track_representative_specs": [],
        "role_candidate_track_ids": [],
        "inferred_roles": {},
        "track_role_scores": {},
        "track_role_confidences": {},
        "issue_types": [
            "band_overlap",
            "track_clipping",
            "master_clipping",
            "sibilance",
            "high_band_harshness",
        ],
        "detected_issues": [],
        "analysis_region_ids": [],
        "analysis_regions": [],
        "master_clipping_candidates": [],
        "master_clipping_contributors": [],
        "promoted_track_clipping_regions": [],
        "ranked_candidate_ids": [],
        "ranking_scores": {},
        "request_mode": None,
        "selected_region_id": None,
        "preserve_clip_id": None,
        "selected_region_selections": [],
        "issue_id": None,
        "action_type": None,
        "action_payload": None,
        "user_feedback_message": None,
        "user_decision": None,
        "user_feedback_recorded_at": None,
        "clip_feature_artifact_id": None,
        "dsp_scan_summary": {},
        **RAW_DSP_STATE_DEFAULTS,
        "vocal_detected": False,
        "clipping_fix_applied": False,
        "clipping_fix_log_id": None,
        "sibilance_fix_applied": False,
        "sibilance_fix_log_id": None,
        "high_band_harshness_fix_applied": False,
        "auto_fix_log_artifact_id": None,
        "auto_fix_recipe_artifact_id": None,
        "plan_payload": {},
        "planner_raw_text": None,
        "planner_artifact_id": None,
        "plan_status": None,
        "plan_revision_notes": [],
        "batch_candidate_plans": [],
        "batch_failed_regions": [],
        "batch_final_track_envelopes": [],
        "batch_failed_envelopes": [],
        "batch_validation_summary": {},
        "critic_raw_text": None,
        "critic_artifact_id": None,
        "suggestion_payload": {},
        "suggestion_group_id": None,
        "preview_id": None,
        "preview_status": None,
        "preview_render_no": 1,
        "preview_excerpt_start_ms": None,
        "preview_excerpt_end_ms": None,
        "preview_requested_at": None,
        "preview_started_at": None,
        "preview_completed_at": None,
        "preview_expired_at": None,
        "preview_error_code": None,
        "preview_error_message": None,
        "has_user_action_candidates": False,
        "has_auto_fixable_eq_issues": False,
        "preview_required": False,
        "user_action_required": False,
        "auto_preview_generated": False,
        "validator_mode": "PASS",
        "validator_result": None,
        "critic_mode": "PASS",
        "critic_result": None,
        "revise_count": 0,
        "max_revise_count": 5,
        "latest_artifact_id": None,
        "mongo_artifact_ids": [],
        "failure_code": None,
        "failure_message": None,
        "requested_by": None,
        "started_at": None,
        "completed_at": None,
        "notes": [],
    }
    if issue_types is not None:
        state["issue_types"] = _normalize_issue_types(issue_types)
    state.update(overrides)
    return state


def build_runtime_initial_state(job_id: int, project_id: int, **overrides: object) -> RuntimeState:
    return build_workflow_initial_state(job_id=job_id, project_id=project_id, **overrides)


def build_apply_initial_state(
    job_id: int,
    project_id: int,
    preview_id: str,
    suggestion_group_id: str,
    **overrides: object,
) -> ApplyState:
    return build_workflow_initial_state(
        job_id=job_id,
        project_id=project_id,
        preview_id=preview_id,
        suggestion_group_id=suggestion_group_id,
        **overrides,
    )


def _normalize_issue_types(issue_types: object) -> list[IssueType]:
    normalized: list[IssueType] = []
    for issue in issue_types or []:
        issue_name = str(issue)
        if issue_name == "clipping":
            for alias in ("track_clipping", "master_clipping"):
                if alias not in normalized:
                    normalized.append(alias)  # type: ignore[arg-type]
            continue
        if issue_name in {
            "band_overlap",
            "track_clipping",
            "master_clipping",
            "sibilance",
            "high_band_harshness",
        } and issue_name not in normalized:
            normalized.append(issue_name)  # type: ignore[arg-type]
    return normalized
