from __future__ import annotations

from copy import deepcopy

from app.graph.nodes.common import (
    append_transition,
    artifact_id,
    clear_raw_dsp_state,
    resolve_preserve_clip_id_for_track,
    workflow_update,
)
from app.graph.state import WorkflowState, utc_now
from app.services.workflow_artifacts import WorkflowArtifactDocument, get_workflow_artifact_store
from app.services.workflow_jobs import WorkflowDispatchMessage, get_workflow_job_store
from app.services.workflow_preview_renderer import PreviewRenderError, resolve_preview_excerpt_range

AUTO_PREVIEW_ISSUE_TYPES = (
    "track_clipping",
    "high_band_harshness",
    "sibilance",
)


def load_entry_context(state: WorkflowState) -> WorkflowState:
    dispatch_type = state.get("dispatch_type")
    if dispatch_type:
        return _load_worker_entry_context(state)
    return {
        "current_node": "load_entry_context",
        "phase": state.get("phase", "queued"),
        "progress": state.get("progress", 0),
        "heartbeat_at": utc_now(),
        "transition_log": append_transition(state, "load_entry_context"),
    }


def init_state(state: WorkflowState) -> WorkflowState:
    return workflow_update(
        state,
        node="init_state",
        phase="job_initialized",
        progress=4,
        runtime_status="running",
        durable_status="RUNNING",
        extra={"started_at": state.get("started_at") or utc_now()},
    )


def wait_user_plan_input(state: WorkflowState) -> WorkflowState:
    return workflow_update(
        state,
        node="wait_user_plan_input",
        phase="waiting_for_user_plan_input",
        progress=62,
        runtime_status="waiting_for_user",
        durable_status="WAITING_USER",
    )


def resume_after_plan_input(state: WorkflowState) -> WorkflowState:
    normalized_selections, batch_validation_error = _normalize_batch_plan_input(state)
    if batch_validation_error is not None:
        return fail_workflow(
            {
                **state,
                "failure_code": batch_validation_error[0],
                "failure_message": batch_validation_error[1],
            }
        )
    if len(normalized_selections) > 1:
        notes = [*state.get("notes", [])]
        notes.append(
            f"User submitted batch plan input for {len(normalized_selections)} region(s)."
        )
        if state.get("user_feedback_message"):
            notes.append(f"User feedback: {state['user_feedback_message']}")
        return workflow_update(
            state,
            node="resume_after_plan_input",
            phase="user_plan_input_resolved",
            progress=64,
            runtime_status="running",
            durable_status="RUNNING",
            extra={
                "request_mode": "batch",
                "selected_region_selections": normalized_selections,
                "selected_region_id": None,
                "preserve_clip_id": None,
                "notes": notes,
            },
        )
    if len(normalized_selections) == 1:
        selection = normalized_selections[0]
        state = {
            **state,
            "request_mode": "single",
            "selected_region_selections": normalized_selections,
            "selected_region_id": int(selection["region_id"]),
            "preserve_clip_id": int(selection["preserve_clip_id"]),
        }

    if not state.get("selected_region_id"):
        return fail_workflow(
            {
                **state,
                "failure_code": "MISSING_SELECTED_REGION",
                "failure_message": "A selected region is required before generating a plan.",
            }
        )
    if not state.get("preserve_clip_id"):
        return fail_workflow(
            {
                **state,
                "failure_code": "MISSING_PRESERVE_CLIP",
                "failure_message": "A preserve clip selection is required before planning.",
            }
        )
    validation_error = _validate_plan_input_selection(state)
    if validation_error is not None:
        return fail_workflow(
            {
                **state,
                "failure_code": validation_error[0],
                "failure_message": validation_error[1],
            }
        )
    notes = [*state.get("notes", [])]
    notes.append(
        f"User selected region {state['selected_region_id']} and preserve clip "
        f"{state['preserve_clip_id']} for plan generation."
    )
    if state.get("user_feedback_message"):
        notes.append(f"User feedback: {state['user_feedback_message']}")
    return workflow_update(
        state,
        node="resume_after_plan_input",
        phase="user_plan_input_resolved",
        progress=64,
        runtime_status="running",
        durable_status="RUNNING",
        extra={"request_mode": "single", "notes": notes},
    )


def auto_fix_sibilance(state: WorkflowState) -> WorkflowState:
    sibilance_regions = [
        region
        for region in state.get("analysis_regions", [])
        if region.get("issue_type") == "sibilance"
    ]
    sibilance_fix_applied = bool(sibilance_regions)
    notes = [*state.get("notes", [])]
    auto_fix_recipe_artifact_id = None
    mongo_artifact_ids = [*state.get("mongo_artifact_ids", [])]
    latest_artifact_id = state.get("latest_artifact_id")

    if sibilance_fix_applied:
        recipes = [_build_sibilance_fix_recipe(region) for region in sibilance_regions]
        region_ids = [int(region["id"]) for region in sibilance_regions if region.get("id") is not None]
        track_ids = sorted(
            {
                int(region.get("track_id") or 0)
                for region in sibilance_regions
                if region.get("track_id") is not None
            }
        )
        applied_in_mixed_issue_flow = any(
            region.get("requires_user_action", True)
            for region in state.get("analysis_regions", [])
            if region.get("issue_type") != "sibilance"
        )
        auto_fix_recipe_artifact_id = artifact_id(state, "sibilance-auto-fix")
        get_workflow_artifact_store().upsert_artifact(
            WorkflowArtifactDocument(
                id=auto_fix_recipe_artifact_id,
                job_id=state["job_id"],
                artifact_type="auto_fix_recipe",
                payload={
                    "issueType": "sibilance",
                    "regionIds": region_ids,
                    "trackIds": track_ids,
                    "appliedInMixedIssueFlow": applied_in_mixed_issue_flow,
                    "recipes": recipes,
                },
            )
        )
        mongo_artifact_ids.append(auto_fix_recipe_artifact_id)
        latest_artifact_id = auto_fix_recipe_artifact_id
        notes.append(
            f"Applied deterministic sibilance repair recipe to {len(sibilance_regions)} region(s)."
        )
        if applied_in_mixed_issue_flow:
            notes.append(
                "사용자 승인 이슈와 함께 탐지된 치찰음도 "
                "같은 run에서 자동 보정 artifact로 기록했다."
            )

    return workflow_update(
        state,
        node="auto_fix_sibilance",
        phase="sibilance_autofix_processed",
        progress=88,
        extra={
            "clipping_fix_applied": False,
            "clipping_fix_log_id": None,
            "sibilance_fix_applied": sibilance_fix_applied,
            "auto_fix_recipe_artifact_id": auto_fix_recipe_artifact_id,
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
            "notes": notes,
        },
    )


def log_sibilance_fix(state: WorkflowState) -> WorkflowState:
    sibilance_fix_log_id = None
    mongo_artifact_ids = [*state.get("mongo_artifact_ids", [])]
    latest_artifact_id = state.get("latest_artifact_id")
    notes = [*state.get("notes", [])]

    if state.get("sibilance_fix_applied"):
        sibilance_regions = [
            region
            for region in state.get("analysis_regions", [])
            if region.get("issue_type") == "sibilance"
        ]
        sibilance_fix_log_id = artifact_id(state, "sibilance-fix-log")
        get_workflow_artifact_store().upsert_artifact(
            WorkflowArtifactDocument(
                id=sibilance_fix_log_id,
                job_id=state["job_id"],
                artifact_type="auto_fix_log",
                payload={
                    "logVersion": 1,
                    "issueType": "sibilance",
                    "recipeArtifactId": state.get("auto_fix_recipe_artifact_id"),
                    "applied": True,
                    "regionIds": [
                        int(region["id"])
                        for region in sibilance_regions
                        if region.get("id") is not None
                    ],
                    "trackIds": sorted(
                        {
                            int(region.get("track_id") or 0)
                            for region in sibilance_regions
                            if region.get("track_id") is not None
                        }
                    ),
                    "regionCount": len(sibilance_regions),
                },
            )
        )
        mongo_artifact_ids.append(sibilance_fix_log_id)
        latest_artifact_id = sibilance_fix_log_id
        notes.append(
            f"치찰음 자동 보정 로그 artifact {sibilance_fix_log_id}를 기록했다."
        )

    return workflow_update(
        state,
        node="log_sibilance_fix",
        phase="sibilance_fix_logged",
        progress=90,
        extra={
            "sibilance_fix_log_id": sibilance_fix_log_id,
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
            "notes": notes,
        },
    )


def auto_fix_non_user_issues(state: WorkflowState) -> WorkflowState:
    notes = [*state.get("notes", [])]
    mongo_artifact_ids = [*state.get("mongo_artifact_ids", [])]
    latest_artifact_id = state.get("latest_artifact_id")
    auto_fix_recipe_artifact_id = None
    grouped_recipes = _build_non_user_issue_recipe_groups(state)

    clipping_fix_applied = any(
        group["issueType"] in {"track_clipping", "master_clipping"} for group in grouped_recipes
    )
    sibilance_fix_applied = any(group["issueType"] == "sibilance" for group in grouped_recipes)
    high_band_harshness_fix_applied = any(
        group["issueType"] == "high_band_harshness" for group in grouped_recipes
    )
    auto_preview_suggestions = _build_auto_preview_suggestions(state, grouped_recipes)
    suggestion_payload = _merge_auto_preview_suggestions(
        state.get("suggestion_payload") or {},
        auto_preview_suggestions,
    )

    if grouped_recipes:
        first_group = grouped_recipes[0]
        auto_fix_recipe_artifact_id = artifact_id(state, "non-user-auto-fix")
        get_workflow_artifact_store().upsert_artifact(
            WorkflowArtifactDocument(
                id=auto_fix_recipe_artifact_id,
                job_id=state["job_id"],
                artifact_type="auto_fix_recipe",
                payload={
                    "recipeVersion": 2,
                    "issueType": first_group["issueType"],
                    "regionIds": first_group["regionIds"],
                    "trackIds": first_group["trackIds"],
                    "appliedInMixedIssueFlow": first_group["appliedInMixedIssueFlow"],
                    "containsPromotedMasterContributor": first_group[
                        "containsPromotedMasterContributor"
                    ],
                    "recipes": first_group["recipes"],
                    "groups": grouped_recipes,
                },
            )
        )
        mongo_artifact_ids.append(auto_fix_recipe_artifact_id)
        latest_artifact_id = auto_fix_recipe_artifact_id
        notes.append(
            "Applied deterministic auto-fix recipes to "
            f"{len(grouped_recipes)} non-user issue group(s)."
        )

    return workflow_update(
        state,
        node="auto_fix_non_user_issues",
        phase="non_user_issue_autofix_processed",
        progress=88,
        extra={
            "clipping_fix_applied": clipping_fix_applied,
            "clipping_fix_log_id": None,
            "sibilance_fix_applied": sibilance_fix_applied,
            "sibilance_fix_log_id": None,
            "high_band_harshness_fix_applied": high_band_harshness_fix_applied,
            "auto_fix_log_artifact_id": None,
            "auto_fix_recipe_artifact_id": auto_fix_recipe_artifact_id,
            "has_auto_fixable_eq_issues": bool(auto_preview_suggestions),
            "suggestion_payload": suggestion_payload,
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
            "notes": notes,
        },
    )


def log_non_user_issue_fixes(state: WorkflowState) -> WorkflowState:
    grouped_recipes = _build_non_user_issue_recipe_groups(state)
    mongo_artifact_ids = [*state.get("mongo_artifact_ids", [])]
    latest_artifact_id = state.get("latest_artifact_id")
    notes = [*state.get("notes", [])]
    auto_fix_log_artifact_id = None

    if grouped_recipes:
        first_group = grouped_recipes[0]
        auto_fix_log_artifact_id = artifact_id(state, "non-user-auto-fix-log")
        get_workflow_artifact_store().upsert_artifact(
            WorkflowArtifactDocument(
                id=auto_fix_log_artifact_id,
                job_id=state["job_id"],
                artifact_type="auto_fix_log",
                payload={
                    "logVersion": 2,
                    "recipeArtifactId": state.get("auto_fix_recipe_artifact_id"),
                    "issueType": first_group["issueType"],
                    "regionIds": first_group["regionIds"],
                    "trackIds": first_group["trackIds"],
                    "regionCount": first_group["regionCount"],
                    "groups": [
                        {
                            "issueType": group["issueType"],
                            "applied": True,
                            "regionIds": group["regionIds"],
                            "trackIds": group["trackIds"],
                            "regionCount": group["regionCount"],
                            "containsPromotedMasterContributor": group[
                                "containsPromotedMasterContributor"
                            ],
                        }
                        for group in grouped_recipes
                    ],
                },
            )
        )
        mongo_artifact_ids.append(auto_fix_log_artifact_id)
        latest_artifact_id = auto_fix_log_artifact_id
        notes.append(f"Recorded non-user auto-fix log artifact {auto_fix_log_artifact_id}.")

    return workflow_update(
        state,
        node="log_non_user_issue_fixes",
        phase="non_user_issue_fixes_logged",
        progress=90,
        extra={
            "clipping_fix_log_id": (
                auto_fix_log_artifact_id if state.get("clipping_fix_applied") else None
            ),
            "sibilance_fix_log_id": (
                auto_fix_log_artifact_id if state.get("sibilance_fix_applied") else None
            ),
            "auto_fix_log_artifact_id": auto_fix_log_artifact_id,
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
            "notes": notes,
        },
    )


def persist_analysis_result(state: WorkflowState) -> WorkflowState:
    preview_id = state.get("preview_id")
    payload = state.get("suggestion_payload") or {}
    preview_bands = [
        band
        for suggestion in payload.get("suggestions", [])
        if isinstance(suggestion, dict)
        for band in suggestion.get("previewBands", [])
        if isinstance(band, dict)
    ]
    has_user_action_candidates = bool(state.get("ranked_candidate_ids"))
    has_auto_fixable_eq_issues = bool(preview_bands)
    preview_required = bool(preview_bands)
    user_action_required = has_user_action_candidates
    if preview_required:
        preview_id = preview_id or f"{state['job_id']}-preview"
    return workflow_update(
        state,
        node="persist_analysis_result",
        phase="analysis_result_persisted",
        progress=92,
        extra={
            "preview_id": preview_id,
            "has_user_action_candidates": has_user_action_candidates,
            "has_auto_fixable_eq_issues": has_auto_fixable_eq_issues,
            "preview_required": preview_required,
            "user_action_required": user_action_required,
            "auto_preview_generated": False,
        },
    )


def user_action_gate(state: WorkflowState) -> WorkflowState:
    return workflow_update(
        state,
        node="user_action_gate",
        phase="user_action_gate_checked",
        progress=94,
    )


def apply_selected_edit_recipe(state: WorkflowState) -> WorkflowState:
    preview_band_specs = _resolve_preview_band_specs(state)
    if not preview_band_specs:
        return fail_workflow(
            {
                **state,
                "failure_code": "INVALID_PREVIEW_BAND_SPEC_COUNT",
                "failure_message": (
                    "선택된 제안을 적용하기 전에 "
                    "Spring 저장용 preview band spec이 최소 1개 필요합니다."
                ),
            }
        )
    notes = [*state.get("notes", [])]
    notes.append("대표 plan을 preview band spec으로 고정하고 Spring 저장 대기 상태로 전환했다.")
    requested_at = utc_now()
    return workflow_update(
        state,
        node="apply_selected_edit_recipe",
        phase="selected_recipe_applied",
        progress=96,
        runtime_status="running",
        durable_status="RUNNING",
        extra={
            "preview_status": "PROCESSING",
            "preview_render_no": max(int(state.get("preview_render_no", 1) or 1), 1),
            "preview_excerpt_start_ms": None,
            "preview_excerpt_end_ms": None,
            "preview_requested_at": requested_at,
            "preview_started_at": None,
            "preview_completed_at": None,
            "preview_expired_at": None,
            "preview_error_code": None,
            "preview_error_message": None,
            "notes": notes,
        },
    )

# 실제로 preview를 만드는 함수가 아님
# preview 생성을 위한 메타데이터를 만드는 함수 (preview 시작/종료 시간, preivew에 적용할 action)
def render_preview(state: WorkflowState) -> WorkflowState:
    preview_id = state.get("preview_id") or f"{state['job_id']}-preview"
    started_at = utc_now()
    try:
        focus_region = _resolve_preview_focus_region(state)
        preview_band_specs = _resolve_preview_band_specs(state)
        if not preview_band_specs:
            raise PreviewRenderError(
                "INVALID_PREVIEW_BAND_SPEC_COUNT",
                "프리뷰 렌더링에는 preview band spec 1개가 필요합니다.",
            )
        excerpt_start_ms, excerpt_end_ms = resolve_preview_excerpt_range(
            clip_index=state.get("clip_index", []),
            focus_region=focus_region,
            project_duration_ms=state.get("project_duration_ms"),
        )
    except PreviewRenderError as exc:
        return fail_workflow(
            {
                **state,
                "preview_id": preview_id,
                "preview_status": "FAILED",
                "preview_started_at": started_at,
                "preview_completed_at": utc_now(),
                "preview_error_code": exc.code,
                "preview_error_message": exc.message,
                "failure_code": exc.code,
                "failure_message": exc.message,
            }
        )

    return workflow_update(
        state,
        node="render_preview",
        phase="preview_rendered",
        progress=97,
        extra={
            "preview_id": preview_id,
            "preview_status": "READY",
            "preview_excerpt_start_ms": excerpt_start_ms,
            "preview_excerpt_end_ms": excerpt_end_ms,
            "preview_started_at": started_at,
            "preview_completed_at": utc_now(),
            # Spring은 이 ISO 8601 값을 DATETIME으로 저장하는 계약을 사용한다.
            "preview_expired_at": _resolve_preview_expired_at(preview_band_specs),
            "preview_error_code": None,
            "preview_error_message": None,
            "auto_preview_generated": (
                not bool(state.get("user_action_required"))
                and bool(state.get("preview_required"))
            ),
        },
    )


def finalize_output(state: WorkflowState) -> WorkflowState:
    notes = [*state.get("notes", [])]
    if state.get("preview_status") == "READY":
        notes.append("AI worker는 preview 생성까지만 수행했고 confirm/cancel은 Spring 경계로 넘겼다.")
    return workflow_update(
        state,
        node="finalize_output",
        phase="completed",
        progress=100,
        runtime_status="completed",
        durable_status="COMPLETED",
        extra={"completed_at": utc_now(), "notes": notes, **clear_raw_dsp_state()},
    )


def fail_workflow(state: WorkflowState) -> WorkflowState:
    return workflow_update(
        state,
        node="fail_workflow",
        phase="failed",
        progress=state.get("progress", 0),
        runtime_status="failed",
        durable_status="FAILED",
        extra={
            "completed_at": utc_now(),
            "failure_code": state.get("failure_code") or "WORKFLOW_FAILED",
            "failure_message": state.get("failure_message")
            or "The workflow could not complete successfully.",
            "preview_id": state.get("preview_id"),
            "preview_status": state.get("preview_status"),
            "preview_render_no": state.get("preview_render_no", 1),
            "preview_excerpt_start_ms": state.get("preview_excerpt_start_ms"),
            "preview_excerpt_end_ms": state.get("preview_excerpt_end_ms"),
            "preview_requested_at": state.get("preview_requested_at"),
            "preview_started_at": state.get("preview_started_at"),
            "preview_completed_at": state.get("preview_completed_at"),
            "preview_expired_at": state.get("preview_expired_at"),
            "preview_error_code": state.get("preview_error_code"),
            "preview_error_message": state.get("preview_error_message"),
            **clear_raw_dsp_state(),
        },
    )


def _load_worker_entry_context(state: WorkflowState) -> WorkflowState:
    store = get_workflow_job_store()
    job = store.get_job(state["job_id"])
    if job is None:
        return _entry_failure(
            state,
            failure_code="WORKFLOW_JOB_NOT_FOUND",
            failure_message="The workflow job could not be restored for worker execution.",
        )
    if job.project_id != state["project_id"]:
        return _entry_failure(
            state,
            failure_code="WORKFLOW_PROJECT_MISMATCH",
            failure_message="The queued workflow payload did not match the stored project.",
        )

    dispatch = WorkflowDispatchMessage.model_validate(
        {
            "job_id": state["job_id"],
            "project_id": state["project_id"],
            "dispatch_type": state["dispatch_type"],
            "requested_by": state.get("requested_by"),
            "request_mode": state.get("request_mode"),
            "selected_region_id": state.get("selected_region_id"),
            "preserve_clip_id": state.get("preserve_clip_id"),
            "selected_region_selections": state.get("selected_region_selections", []),
            "issue_id": state.get("issue_id"),
            "action_type": state.get("action_type"),
            "action_payload": state.get("action_payload"),
            "user_feedback_message": state.get("user_feedback_message"),
            "user_decision": state.get("user_decision"),
        }
    )
    failure = _validate_dispatch(job.state_snapshot, dispatch)
    if failure is not None:
        return _entry_failure(state, failure_code=failure[0], failure_message=failure[1])

    restored = deepcopy(job.state_snapshot)
    restored.update(
        {
            "job_id": dispatch.job_id,
            "project_id": dispatch.project_id,
            "dispatch_type": dispatch.dispatch_type,
            "requested_by": dispatch.requested_by
            if dispatch.requested_by is not None
            else restored.get("requested_by"),
            "request_mode": dispatch.request_mode or restored.get("request_mode"),
            "runtime_status": "running",
            "durable_status": "RUNNING",
            "heartbeat_at": utc_now(),
            "transition_log": append_transition(restored, "load_entry_context"),
            "current_node": "load_entry_context",
        }
    )
    if dispatch.selected_region_id is not None:
        restored["selected_region_id"] = dispatch.selected_region_id
    if dispatch.preserve_clip_id is not None:
        restored["preserve_clip_id"] = dispatch.preserve_clip_id
    if dispatch.selected_region_selections:
        restored["selected_region_selections"] = [
            selection.model_dump(mode="python")
            for selection in dispatch.selected_region_selections
        ]
    if dispatch.issue_id is not None:
        restored["issue_id"] = dispatch.issue_id
    if dispatch.action_type is not None:
        restored["action_type"] = dispatch.action_type
    if dispatch.action_payload is not None:
        restored["action_payload"] = dispatch.action_payload
    if dispatch.user_feedback_message is not None:
        restored["user_feedback_message"] = dispatch.user_feedback_message
    if dispatch.user_decision is not None:
        restored["user_decision"] = dispatch.user_decision
    return restored


def _validate_dispatch(
    snapshot: dict,
    dispatch: WorkflowDispatchMessage,
) -> tuple[str, str] | None:
    phase = snapshot.get("phase", "queued")
    if dispatch.dispatch_type == "start":
        if phase != "queued":
            return (
                "INVALID_START_PHASE",
                f"Queued workflow start expected 'queued' phase, got '{phase}'.",
            )
        return None
    if dispatch.dispatch_type == "resume_plan_input":
        if phase != "waiting_for_user_plan_input":
            return (
                "INVALID_RESUME_PHASE",
                f"Plan-input resume expected 'waiting_for_user_plan_input', got '{phase}'.",
            )
        if dispatch.selected_region_selections:
            if len(dispatch.selected_region_selections) > 1 and not str(
                dispatch.user_feedback_message or ""
            ).strip():
                return (
                    "MISSING_BATCH_USER_PROMPT",
                    "userPrompt is required for batch plan-input resume.",
                )
            restored_snapshot = deepcopy(snapshot)
            restored_snapshot["selected_region_selections"] = [
                selection.model_dump(mode="python")
                for selection in dispatch.selected_region_selections
            ]
            restored_snapshot["request_mode"] = (
                "batch" if len(dispatch.selected_region_selections) > 1 else "single"
            )
            selection_error = _normalize_batch_plan_input(restored_snapshot)[1]
            if selection_error is not None:
                return selection_error
            return None
        if dispatch.selected_region_id is None:
            return (
                "MISSING_SELECTED_REGION",
                "selected_region_id is required for plan-input resume.",
            )
        if dispatch.preserve_clip_id is None:
            return (
                "MISSING_PRESERVE_CLIP",
                "preserve_clip_id is required for plan-input resume.",
            )
        restored_snapshot = deepcopy(snapshot)
        restored_snapshot["selected_region_id"] = dispatch.selected_region_id
        restored_snapshot["preserve_clip_id"] = dispatch.preserve_clip_id
        selection_error = _validate_plan_input_selection(restored_snapshot)
        if selection_error is not None:
            return selection_error
        return None
    return (
        "INVALID_RESUME_PHASE",
        f"Resume expected 'waiting_for_user_plan_input', got '{phase}'.",
    )


def _entry_failure(
    state: WorkflowState,
    *,
    failure_code: str,
    failure_message: str,
) -> WorkflowState:
    return {
        "current_node": "load_entry_context",
        "phase": state.get("phase", "queued"),
        "progress": state.get("progress", 0),
        "heartbeat_at": utc_now(),
        "transition_log": append_transition(state, "load_entry_context"),
        "runtime_status": "failed",
        "durable_status": "FAILED",
        "failure_code": failure_code,
        "failure_message": failure_message,
    }


def _validate_plan_input_selection(state: WorkflowState) -> tuple[str, str] | None:
    selected_region_id = state.get("selected_region_id")
    preserve_clip_id = state.get("preserve_clip_id")
    ranked_candidate_ids = [int(region_id) for region_id in state.get("ranked_candidate_ids", [])]
    if selected_region_id is None or preserve_clip_id is None:
        return None
    if int(selected_region_id) not in ranked_candidate_ids:
        return (
            "INVALID_SELECTED_REGION",
            "selected_region_id must reference a ranked user-action candidate.",
        )
    selected_region = next(
        (
            region
            for region in state.get("analysis_regions", [])
            if int(region["id"]) == int(selected_region_id)
        ),
        None,
    )
    if not isinstance(selected_region, dict):
        return (
            "INVALID_SELECTED_REGION",
            "selected_region_id did not match a known analysis region.",
        )
    if not bool(selected_region.get("requires_user_action")):
        return (
            "INVALID_SELECTED_REGION",
            "selected_region_id must reference a user-action issue.",
        )
    affected_clip_ids = {
        int(clip_id)
        for clip_id in selected_region.get("affected_clip_ids", [])
        if clip_id is not None
    }
    if affected_clip_ids and int(preserve_clip_id) not in affected_clip_ids:
        return (
            "INVALID_PRESERVE_CLIP",
            "preserve_clip_id must belong to the selected region.",
        )
    return None


def _normalize_batch_plan_input(
    state: WorkflowState,
) -> tuple[list[dict[str, object]], tuple[str, str] | None]:
    selections = state.get("selected_region_selections") or []
    if not selections:
        return [], None

    region_map = {
        int(region["id"]): region
        for region in state.get("analysis_regions", [])
        if region.get("id") is not None
    }
    ranked_candidate_ids = {int(region_id) for region_id in state.get("ranked_candidate_ids", [])}
    seen_region_ids: set[int] = set()
    normalized: list[dict[str, object]] = []

    for selection in selections:
        region_id = int(selection["region_id"])
        preserve_track_id = int(selection["preserve_track_id"])
        if region_id in seen_region_ids:
            return [], (
                "DUPLICATE_REGION_SELECTION",
                "regionSelections must not contain duplicate regionId values.",
            )
        seen_region_ids.add(region_id)

        region = region_map.get(region_id)
        if not isinstance(region, dict):
            return [], (
                "INVALID_SELECTED_REGION",
                f"regionId {region_id} did not match a known analysis region.",
            )
        if region_id not in ranked_candidate_ids:
            return [], (
                "INVALID_SELECTED_REGION",
                f"regionId {region_id} must reference a ranked user-action candidate.",
            )
        if not bool(region.get("requires_user_action")):
            return [], (
                "INVALID_SELECTED_REGION",
                f"regionId {region_id} must reference a user-action issue.",
            )

        preserve_clip_id = selection.get("preserve_clip_id")
        if preserve_clip_id is None:
            preserve_clip_id = resolve_preserve_clip_id_for_track(state, region, preserve_track_id)
        if preserve_clip_id is None:
            return [], (
                "INVALID_PRESERVE_TRACK",
                f"preserveTrackId {preserve_track_id} must belong to regionId {region_id}.",
            )

        normalized.append(
            {
                "region_id": region_id,
                "preserve_track_id": preserve_track_id,
                "preserve_clip_id": int(preserve_clip_id),
            }
        )

    return normalized, None

# 프리뷰 렌더링을 위한 대표 action 복원 함수
def _resolve_preview_action(state: WorkflowState) -> dict[str, object]:
    plan_payload = state.get("plan_payload") or {}
    candidate = plan_payload.get("candidate") or {}
    action = candidate.get("action")
    if not isinstance(action, dict):
        raise PreviewRenderError(
            "PREVIEW_ACTION_NOT_FOUND",
            "plan_payload에서 preview 비교용 action을 찾지 못했습니다.",
        )
    return action

# 프리뷰 생성을 위한 구간을 확정하는 함수
def _resolve_preview_focus_region(state: WorkflowState) -> dict[str, object]:
    selected_region_id = _resolve_preview_focus_region_id(state)
    if selected_region_id is None:
        raise PreviewRenderError(
            "PREVIEW_REGION_NOT_FOUND",
            "프리뷰 렌더링에는 선택된 문제 구간 정보가 필요합니다.",
        )
    for region in state.get("analysis_regions", []):
        if int(region["id"]) == int(selected_region_id):
            return region
    raise PreviewRenderError(
        "PREVIEW_REGION_NOT_FOUND",
        f"selected region {selected_region_id}를 analysis_regions에서 찾지 못했습니다.",
    )


def _resolve_preview_band_specs(state: WorkflowState) -> list[dict[str, object]]:
    payload = state.get("suggestion_payload") or {}
    preview_band_specs: list[dict[str, object]] = []
    for suggestion in payload.get("suggestions", []):
        for band in suggestion.get("previewBands", []):
            if isinstance(band, dict):
                preview_band_specs.append(band)
    return preview_band_specs


def _resolve_preview_focus_region_id(state: WorkflowState) -> int:
    selected_region_id = state.get("selected_region_id")
    if selected_region_id is not None:
        return int(selected_region_id)
    payload = state.get("suggestion_payload") or {}
    active_issue_id = payload.get("activeIssueId")
    if active_issue_id:
        for issue in payload.get("issues", []):
            if not isinstance(issue, dict) or str(issue.get("issueId")) != str(active_issue_id):
                continue
            source_region_ids = issue.get("sourceRegionIds") or []
            if source_region_ids:
                return int(source_region_ids[0])
    auto_preview_region_id = _resolve_auto_preview_region_id(state)
    if auto_preview_region_id is not None:
        return int(auto_preview_region_id)
    raise PreviewRenderError(
        "PREVIEW_REGION_NOT_FOUND",
        "preview focus region information is required.",
    )


def _resolve_auto_preview_region_id(state: WorkflowState) -> int | None:
    recipe_groups = _load_auto_fix_recipe_groups(state)
    for group in recipe_groups:
        region_ids = group.get("regionIds") or []
        if region_ids:
            return int(region_ids[0])
    for issue_type in AUTO_PREVIEW_ISSUE_TYPES:
        for region in state.get("analysis_regions", []):
            if (
                region.get("issue_type") == issue_type
                and not bool(region.get("requires_user_action"))
            ):
                return int(region["id"])
    return None


def _resolve_preview_expired_at(preview_band_specs: list[dict[str, object]]) -> str | None:
    for band in preview_band_specs:
        preview_expires_at = band.get("previewExpiresAt")
        if isinstance(preview_expires_at, str) and preview_expires_at:
            return preview_expires_at
    return None


def _build_sibilance_fix_recipe(region: dict[str, object]) -> dict[str, object]:
    score = float(region.get("score", 0.0))
    reduction_db = round(min(max(1.2 + (score * 2.8), 1.8), 3.8), 2)
    return {
        "regionId": region.get("id"),
        "actionType": "DYNAMIC_EQ",
        "targetScope": "TRACK",
        "targetTrackId": int(region.get("track_id") or 0),
        "startMs": int(region.get("start_ms") or 0),
        "endMs": int(region.get("end_ms") or 0),
        "bandLowHz": region.get("band_low_hz"),
        "bandHighHz": region.get("band_high_hz"),
        "gainDeltaDb": -reduction_db,
        "params": {
            "threshold": -18,
            "ratio": 2.4,
            "attackMs": 2,
            "releaseMs": 60,
            "q": 2.4,
        },
    }


def _build_non_user_issue_recipe_groups(state: WorkflowState) -> list[dict[str, object]]:
    issue_builders = {
        "track_clipping": _build_track_clipping_fix_recipe,
        "high_band_harshness": _build_high_band_harshness_fix_recipe,
        "sibilance": _build_sibilance_fix_recipe,
    }
    ordered_issue_types = [
        "track_clipping",
        "high_band_harshness",
        "sibilance",
    ]
    mixed_issue_flow = any(
        bool(region.get("requires_user_action")) for region in state.get("analysis_regions", [])
    )
    groups: list[dict[str, object]] = []
    for issue_type in ordered_issue_types:
        regions = [
            region
            for region in state.get("analysis_regions", [])
            if region.get("issue_type") == issue_type
        ]
        if not regions:
            continue
        builder = issue_builders[issue_type]
        recipes = [builder(region) for region in regions]
        recipes = [recipe for recipe in recipes if recipe is not None]
        if not recipes:
            continue
        recipe_region_ids = {
            int(recipe["regionId"]) for recipe in recipes if recipe.get("regionId") is not None
        }
        recipe_track_ids = {
            int(recipe["targetTrackId"])
            for recipe in recipes
            if recipe.get("targetTrackId") is not None
        }
        groups.append(
            {
                "issueType": issue_type,
                "regionIds": sorted(recipe_region_ids),
                "trackIds": sorted(recipe_track_ids),
                "regionCount": len(recipes),
                "appliedInMixedIssueFlow": mixed_issue_flow,
                "containsPromotedMasterContributor": any(
                    region.get("auto_fix_source") == "promoted_master_contributor"
                    for region in regions
                    if region.get("id") in recipe_region_ids
                ),
                "recipes": recipes,
            }
        )
    return groups


def _build_auto_preview_suggestions(
    state: WorkflowState,
    grouped_recipes: list[dict[str, object]],
) -> list[dict[str, object]]:
    suggestions: list[dict[str, object]] = []
    for index, group in enumerate(grouped_recipes, start=1):
        preview_bands = []
        for recipe in group.get("recipes", []):
            if not isinstance(recipe, dict):
                continue
            try:
                preview_bands.append(_build_auto_preview_band_spec(state, recipe=recipe))
            except ValueError:
                continue
        if not preview_bands:
            continue
        suggestions.append(
            {
                "rank": index,
                "summary": _build_auto_preview_summary(group),
                "explanation": _build_auto_preview_explanation(group),
                "previewBands": preview_bands,
                "issue": _build_auto_preview_issue(
                    state,
                    group=group,
                    preview_bands=preview_bands,
                    rank=index,
                ),
            }
        )
    return suggestions


def _merge_auto_preview_suggestions(
    payload: dict[str, object],
    auto_preview_suggestions: list[dict[str, object]],
) -> dict[str, object]:
    merged = deepcopy(payload)
    existing_suggestions = list(merged.get("suggestions", []))
    existing_issues = list(merged.get("issues", []))
    navigation_order = [
        str(issue_id)
        for issue_id in merged.get("navigationOrder", [])
        if isinstance(issue_id, str) and issue_id
    ]
    if auto_preview_suggestions:
        for suggestion in auto_preview_suggestions:
            copied = deepcopy(suggestion)
            issue = copied.pop("issue", None)
            existing_suggestions.append(copied)
            if isinstance(issue, dict):
                existing_issues.append(issue)
                issue_id = issue.get("issueId")
                if isinstance(issue_id, str) and issue_id and issue_id not in navigation_order:
                    navigation_order.append(issue_id)
    if not existing_suggestions and not existing_issues:
        return merged
    merged["groupTitle"] = merged.get("groupTitle") or "워크플로우 제안 그룹"
    merged["groupSummary"] = merged.get("groupSummary") or "프리뷰 가능한 EQ 이슈 액션"
    merged["suggestions"] = existing_suggestions
    if existing_issues:
        merged["issues"] = existing_issues
        merged["navigationOrder"] = navigation_order
        if not merged.get("activeIssueId") and navigation_order:
            merged["activeIssueId"] = navigation_order[0]
    return merged


def _build_auto_preview_issue(
    state: WorkflowState,
    *,
    group: dict[str, object],
    preview_bands: list[dict[str, object]],
    rank: int,
) -> dict[str, object]:
    issue_type = str(group.get("issueType") or "eq_issue")
    region_ids = [int(region_id) for region_id in group.get("regionIds") or []]
    track_ids = [int(track_id) for track_id in group.get("trackIds") or []]
    region_map = {
        int(region["id"]): region
        for region in state.get("analysis_regions", [])
        if region.get("id") is not None
    }
    target_region = region_map.get(region_ids[0]) if region_ids else None
    issue_id = f"{state['job_id']}-issue-auto-{rank}"
    if issue_type in {"track_clipping", "master_clipping"}:
        bubble_target = "master"
        ui_mode = "master_limiter"
    elif issue_type == "high_band_harshness":
        bubble_target = "track"
        ui_mode = "marker_only"
    else:
        bubble_target = "track"
        ui_mode = "eq_ai"

    actions: list[dict[str, object]] = []
    for recipe in group.get("recipes", []):
        if not isinstance(recipe, dict):
            continue
        action = {
            "type": str(recipe.get("actionType") or ""),
            "targetScope": recipe.get("targetScope"),
            "targetTrackId": recipe.get("targetTrackId"),
            "gainDeltaDb": recipe.get("gainDeltaDb"),
            "startMs": recipe.get("startMs"),
            "endMs": recipe.get("endMs"),
            "bandLowHz": recipe.get("bandLowHz"),
            "bandHighHz": recipe.get("bandHighHz"),
            "jobId": int(state["job_id"]),
        }
        if action["type"] in {"DYNAMIC_EQ", "EQ_CUT"}:
            action.update(_build_static_eq_action_fields(recipe))
            action["sourceType"] = "AI_CONFIRM"
        actions.append(action)

    markers: list[dict[str, object]] = []
    if issue_type == "high_band_harshness":
        for region_id in region_ids:
            region = region_map.get(region_id)
            if not isinstance(region, dict):
                continue
            markers.append(
                {
                    "trackId": region.get("track_id"),
                    "centerHz": region.get("center_hz"),
                    "bandLowHz": region.get("band_low_hz"),
                    "bandHighHz": region.get("band_high_hz"),
                }
            )

    if issue_type in {"track_clipping", "master_clipping"} and actions:
        actions = [
            _build_master_limiter_issue_action(
                job_id=int(state["job_id"]),
                action=actions[0],
                source_track_id=track_ids[0] if track_ids else None,
            )
        ]

    return {
        "issueId": issue_id,
        "issueType": issue_type,
        "startMs": target_region.get("start_ms") if isinstance(target_region, dict) else None,
        "endMs": target_region.get("end_ms") if isinstance(target_region, dict) else None,
        "trackId": track_ids[0] if track_ids else None,
        "bubbleTarget": bubble_target,
        "uiMode": ui_mode,
        "summary": _build_auto_preview_summary(group),
        "explanation": _build_auto_preview_explanation(group),
        "previewBands": preview_bands,
        "actions": actions,
        "markers": markers,
    }


def _build_auto_preview_band_spec(
    state: WorkflowState,
    *,
    recipe: dict[str, object],
) -> dict[str, object]:
    action_type = recipe.get("actionType")
    if action_type not in {"DYNAMIC_EQ", "EQ_CUT"}:
        raise ValueError("auto preview band spec requires an EQ-only actionType")
    if recipe.get("targetScope") != "TRACK":
        raise ValueError("auto preview band spec requires TRACK scope")
    target_track_id = recipe.get("targetTrackId")
    gain_delta_db = recipe.get("gainDeltaDb")
    band_low_hz = recipe.get("bandLowHz")
    band_high_hz = recipe.get("bandHighHz")
    if not isinstance(target_track_id, int):
        raise ValueError("auto preview band spec requires integer targetTrackId")
    if not isinstance(gain_delta_db, int | float):
        raise ValueError("auto preview band spec requires numeric gainDeltaDb")
    if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int):
        raise ValueError("auto preview band spec requires integer band bounds")
    if band_low_hz <= 0 or band_high_hz <= band_low_hz:
        raise ValueError("auto preview band spec requires valid band bounds")
    frequency_hz = int(round((band_low_hz * band_high_hz) ** 0.5))
    params = recipe.get("params") or {}
    q_value = None
    if isinstance(params, dict):
        raw_q = params.get("q")
        if isinstance(raw_q, int | float) and float(raw_q) > 0:
            q_value = round(float(raw_q), 3)
    if q_value is None:
        q_value = round(float(frequency_hz) / float(band_high_hz - band_low_hz), 3)
    return {
        "jobId": int(state["job_id"]),
        "targetTrackId": target_track_id,
        "bandOrder": 1,
        "eqTypeCode": 1,
        "frequencyHz": frequency_hz,
        "q": q_value,
        "gainDeltaDb": round(float(gain_delta_db), 3),
        "statusCode": 1,
        "previewExpiresAt": _build_preview_expiry(state),
    }


def _build_preview_expiry(state: WorkflowState) -> str:
    from datetime import datetime, timedelta

    base_time = state.get("heartbeat_at")
    preview_expires_at = (
        datetime.fromisoformat(base_time) if isinstance(base_time, str) else datetime.now()
    ) + timedelta(minutes=30)
    return preview_expires_at.isoformat()


def _build_auto_preview_summary(group: dict[str, object]) -> str:
    issue_type = str(group.get("issueType") or "eq_issue")
    region_count = int(group.get("regionCount") or 0)
    if issue_type in {"track_clipping", "master_clipping"}:
        return f"Auto limiter preview for {issue_type} ({region_count} region(s))"
    return f"Auto EQ preview for {issue_type} ({region_count} region(s))"


def _build_auto_preview_explanation(group: dict[str, object]) -> str:
    track_count = len(group.get("trackIds") or [])
    if str(group.get("issueType") or "") in {"track_clipping", "master_clipping"}:
        return (
            f"Deterministic master limiter preview derived from clipping analysis "
            f"across {track_count} contributing track(s)."
        )
    return (
        f"Deterministic EQ preview derived from non-user issue recipes "
        f"across {track_count} track(s)."
    )


def _load_auto_fix_recipe_groups(state: WorkflowState) -> list[dict[str, object]]:
    artifact_id = state.get("auto_fix_recipe_artifact_id")
    if not artifact_id:
        return []
    artifact = get_workflow_artifact_store().get_artifact(str(artifact_id))
    if artifact is None:
        return []
    groups = artifact.payload.get("groups")
    if isinstance(groups, list):
        return [group for group in groups if isinstance(group, dict)]
    return []


def _build_track_clipping_fix_recipe(region: dict[str, object]) -> dict[str, object] | None:
    reduction_db = _resolve_clipping_limiter_reduction_db(region)
    return {
        "regionId": region.get("id"),
        "actionType": "TRUE_PEAK_LIMITER",
        "targetScope": "MASTER",
        "startMs": int(region.get("start_ms") or 0),
        "endMs": int(region.get("end_ms") or 0),
        "params": {
            "ceilingDbfs": float(region.get("target_ceiling_dbtp") or -1.0),
            "estimatedGainReductionDb": reduction_db,
            "currentTruePeakDbtp": region.get("current_true_peak_dbtp"),
        },
        "origin": region.get("auto_fix_source", "direct_detection"),
        "sourceMasterCandidateId": region.get("source_master_candidate_id"),
        "sourceTrackId": region.get("track_id"),
    }


def _build_static_eq_action_fields(recipe: dict[str, object]) -> dict[str, object]:
    band_low_hz = recipe.get("bandLowHz")
    band_high_hz = recipe.get("bandHighHz")
    if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int):
        raise ValueError("static eq action fields require integer band bounds")
    if band_low_hz <= 0 or band_high_hz <= band_low_hz:
        raise ValueError("static eq action fields require valid band bounds")

    frequency_hz = int(round((band_low_hz * band_high_hz) ** 0.5))
    params = recipe.get("params") or {}
    q_value = params.get("q") if isinstance(params, dict) else None
    if isinstance(q_value, int | float) and float(q_value) > 0:
        q = round(float(q_value), 3)
    else:
        q = round(float(frequency_hz) / float(band_high_hz - band_low_hz), 3)
    return {
        "frequencyHz": frequency_hz,
        "q": q,
        "eqType": "BELL",
    }


def _resolve_clipping_limiter_reduction_db(region: dict[str, object]) -> float:
    explicit = region.get("recommended_reduction_db")
    if isinstance(explicit, int | float):
        return round(float(explicit), 3)
    current_true_peak = region.get("current_true_peak_dbtp")
    target_ceiling = region.get("target_ceiling_dbtp")
    if isinstance(current_true_peak, int | float):
        ceiling = float(target_ceiling) if isinstance(target_ceiling, int | float) else -1.0
        return round(max(float(current_true_peak) - ceiling, 0.5), 3)
    score = float(region.get("score") or region.get("detector_score") or 0.0)
    return round(min(max(0.8 + (score * 6.0), 1.0), 4.0), 3)


def _build_master_limiter_issue_action(
    *,
    job_id: int,
    action: dict[str, object],
    source_track_id: int | None,
) -> dict[str, object]:
    params = action.get("params") if isinstance(action.get("params"), dict) else {}
    issue_action: dict[str, object] = {
        "type": "apply_master_limiter",
        "targetScope": "MASTER",
        "jobId": job_id,
        "sourceType": "AI_APPLIED",
        "isEnabled": True,
        "estimatedGainReductionDb": params.get("estimatedGainReductionDb"),
        "currentTruePeakDbtp": params.get("currentTruePeakDbtp"),
        "ceilingDbfs": params.get("ceilingDbfs") or -1.0,
        "targetCeilingDbtp": params.get("ceilingDbfs") or -1.0,
        "thresholdDb": None,
        "attackMs": None,
        "releaseMs": None,
        "inputGainDb": None,
        "makeupGainDb": None,
        "sourceActionType": action.get("type"),
    }
    if source_track_id is not None:
        issue_action["sourceTrackId"] = source_track_id
    return issue_action


def _build_high_band_harshness_fix_recipe(region: dict[str, object]) -> dict[str, object]:
    score = float(region.get("score", 0.0))
    reduction_db = round(min(max(1.2 + (score * 2.5), 1.5), 3.5), 2)
    return {
        "regionId": region.get("id"),
        "actionType": "DYNAMIC_EQ",
        "targetScope": "TRACK",
        "targetTrackId": int(region.get("track_id") or 0),
        "startMs": int(region.get("start_ms") or 0),
        "endMs": int(region.get("end_ms") or 0),
        "bandLowHz": region.get("band_low_hz"),
        "bandHighHz": region.get("band_high_hz"),
        "gainDeltaDb": -reduction_db,
        "params": {"threshold": -20, "ratio": 2.1},
    }


def _collect_track_clipping_band_hints(region: dict[str, object]) -> set[str]:
    hints: set[str] = set()
    for hint in region.get("band_hints", []) or []:
        hints.add(str(hint))
    contributor_hints = region.get("contributor_band_hints", {})
    track_id = region.get("track_id")
    if track_id is not None and str(track_id) in contributor_hints:
        hints.update(str(hint) for hint in contributor_hints[str(track_id)])
    if track_id in contributor_hints:
        hints.update(str(hint) for hint in contributor_hints[track_id])
    return hints
