from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import json

from app.graph.nodes.common import (
    artifact_id,
    build_action,
    build_selection_context,
    resolve_clip_track_id,
    workflow_update,
)
from app.graph.nodes.runtime import fail_workflow
from app.graph.state import WorkflowState
from app.services.planning_llm import PlanningLLMError, get_planning_llm_client
from app.services.workflow_artifacts import WorkflowArtifactDocument, get_workflow_artifact_store


def planning_agent(state: WorkflowState) -> WorkflowState:
    revise_count = state.get("revise_count", 0)
    if state.get("validator_result") in {"REVISE", "REJECT"} or state.get("critic_result") in {"REVISE", "REJECT"}:
        revise_count += 1

    selected_region = _resolve_selected_region(state)
    if selected_region is None:
        return fail_workflow(
            {
                **state,
                "failure_code": "PLANNING_REGION_NOT_FOUND",
                "failure_message": "The selected analysis region could not be restored for planning.",
            }
        )
    if selected_region.get("issue_type") != "band_overlap":
        return fail_workflow(
            {
                **state,
                "failure_code": "UNSUPPORTED_PLANNING_ISSUE",
                "failure_message": "Planning is only supported for band_overlap issues.",
            }
        )

    selected_region_id = int(selected_region["id"])
    preserve_clip_id = state.get("preserve_clip_id")
    if preserve_clip_id is None:
        return fail_workflow(
            {
                **state,
                "failure_code": "MISSING_PRESERVE_CLIP",
                "failure_message": "A preserve clip selection is required before planning.",
            }
        )

    try:
        llm_response = get_planning_llm_client().generate_plan(
            selected_region_id=selected_region_id,
            preserve_clip_id=int(preserve_clip_id),
            user_feedback_message=state.get("user_feedback_message"),
            selection_context=build_selection_context(state, selected_region, int(preserve_clip_id)),
            region=deepcopy(selected_region),
            clip_context=_build_clip_context(state, selected_region, int(preserve_clip_id)),
            revision_notes=[*state.get("plan_revision_notes", [])],
        )
    except PlanningLLMError as exc:
        return fail_workflow(
            {
                **state,
                "failure_code": exc.code,
                "failure_message": exc.message,
            }
        )

    raw_plan_text = llm_response.raw_text or _dump_json_text(llm_response.plan_payload)
    plan_payload = _normalize_plan_payload(
        state,
        region=selected_region,
        preserve_clip_id=int(preserve_clip_id),
        raw_plan_payload=llm_response.plan_payload,
    )
    current_artifact_id = artifact_id(state, "planner-output")
    get_workflow_artifact_store().upsert_artifact(
        WorkflowArtifactDocument(
            id=current_artifact_id,
            job_id=state["job_id"],
            artifact_type="planner_output",
            payload={
                "selectedRegionId": selected_region_id,
                "preserveClipId": int(preserve_clip_id),
                "rawText": raw_plan_text,
                "planPayload": deepcopy(plan_payload),
            },
        )
    )
    return workflow_update(
        state,
        node="planning_agent",
        phase="plan_generated",
        progress=74,
        extra={
            "plan_payload": plan_payload,
            "planner_raw_text": raw_plan_text,
            "planner_artifact_id": current_artifact_id,
            "plan_status": "DRAFT",
            "validator_result": None,
            "critic_result": None,
            "revise_count": revise_count,
            "mongo_artifact_ids": [*state.get("mongo_artifact_ids", []), current_artifact_id],
            "latest_artifact_id": current_artifact_id,
        },
    )


def approve_plan(state: WorkflowState) -> WorkflowState:
    return workflow_update(
        state,
        node="approve_plan",
        phase="internal_plan_approved",
        progress=82,
        extra={
            "plan_status": "APPROVED",
            "plan_revision_notes": [*state.get("plan_revision_notes", [])],
        },
    )


def build_issue_payloads(state: WorkflowState) -> WorkflowState:
    payload = {
        "groupTitle": "워크플로우 제안 그룹",
        "groupSummary": "통합 이슈 탐색 페이로드",
        "activeIssueId": None,
        "navigationOrder": [],
        "issues": [],
        "suggestions": [],
    }
    for region in state.get("analysis_regions", []):
        issue = _build_initial_issue(state, region)
        if issue is None:
            continue
        payload = _merge_issue_payload(payload, issue=issue)

    ranked_issue_id = next(
        (
            _issue_id(state, int(region_id))
            for region_id in state.get("ranked_candidate_ids", [])
            if _issue_id(state, int(region_id)) in payload["navigationOrder"]
        ),
        None,
    )
    first_band_overlap_issue_id = next(
        (
            _issue_id(state, int(region["id"]))
            for region in state.get("analysis_regions", [])
            if region.get("issue_type") == "band_overlap"
        ),
        None,
    )
    if ranked_issue_id:
        payload["activeIssueId"] = ranked_issue_id
    elif first_band_overlap_issue_id:
        payload["activeIssueId"] = first_band_overlap_issue_id
    elif payload["navigationOrder"]:
        payload["activeIssueId"] = payload["navigationOrder"][0]

    notes = [*state.get("notes", [])]
    if payload["issues"]:
        notes.append(
            f"Prepared unified suggestion payload scaffold for {len(payload['issues'])} issue(s)."
        )
    return workflow_update(
        state,
        node="build_issue_payloads",
        phase="issue_payloads_built",
        progress=58,
        extra={
            "suggestion_payload": payload,
            "notes": notes,
        },
    )


def materialize_execution_plan(state: WorkflowState) -> WorkflowState:
    plan_payload = state.get("plan_payload") or {}
    candidate = plan_payload.get("candidate") or {}
    selected_region = _resolve_selected_region(state)
    notes = [*state.get("notes", [])]
    mongo_artifact_ids = [*state.get("mongo_artifact_ids", [])]
    latest_artifact_id = state.get("latest_artifact_id")

    if not candidate:
        return workflow_update(
            state,
            node="materialize_execution_plan",
            phase="execution_plan_materialized",
            progress=84,
            extra={"notes": notes},
        )

    if state.get("plan_status") != "APPROVED":
        return fail_workflow(
            {
                **state,
                "failure_code": "PLAN_NOT_APPROVED",
                "failure_message": "The execution plan could not be materialized before internal approval.",
            }
        )
    if selected_region is None:
        return fail_workflow(
            {
                **state,
                "failure_code": "MATERIALIZE_REGION_NOT_FOUND",
                "failure_message": "The selected analysis region could not be restored for execution plan materialization.",
            }
        )
    if selected_region.get("issue_type") != "band_overlap":
        return fail_workflow(
            {
                **state,
                "failure_code": "INVALID_PLANNING_ISSUE",
                "failure_message": "Execution plan materialization only supports band_overlap.",
            }
        )

    action = candidate.get("action")
    if not isinstance(action, dict):
        return fail_workflow(
            {
                **state,
                "failure_code": "INVALID_PLAN_ACTION",
                "failure_message": "The approved plan did not include a valid action payload.",
            }
        )

    try:
        action["bandOverlapSubtype"] = selected_region.get("band_overlap_subtype")
        action = _build_application_eq_action(state, action=action)
        preview_band_spec = _build_preview_band_spec(state, action=action)
    except ValueError as exc:
        return fail_workflow(
            {
                **state,
                "failure_code": "INVALID_EQ_ONLY_PLAN_ACTION",
                "failure_message": str(exc),
            }
        )

    issue_id = _issue_id(state, int(selected_region["id"]))
    payload = _merge_issue_payload(
        state.get("suggestion_payload") or {},
        issue={
            "issueId": issue_id,
            "issueType": "band_overlap",
            "startMs": int(selected_region.get("start_ms") or 0),
            "endMs": int(selected_region.get("end_ms") or 0),
            "trackId": selected_region.get("track_id"),
            "bandOverlapSubtype": selected_region.get("band_overlap_subtype"),
            "bandFocusLabel": selected_region.get("band_focus_label"),
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": plan_payload.get("summary") or "플래너가 생성한 수정 요약",
            "explanation": plan_payload.get("explanation"),
            "previewBands": [preview_band_spec],
            "actions": [deepcopy(action)],
            "markers": [],
        },
        suggestion={
            "rank": 1,
            "summary": plan_payload.get("summary") or "플래너가 생성한 수정 요약",
            "explanation": plan_payload.get("explanation"),
            "previewBands": [preview_band_spec],
        },
        active_issue_id=issue_id,
        group_title=plan_payload.get("strategyTitle"),
        group_summary=plan_payload.get("strategySummary"),
    )
    for region in state.get("analysis_regions", []):
        if str(region.get("issue_type") or "") == "band_overlap":
            continue
        non_llm_issue = _build_non_llm_issue(state, region)
        if non_llm_issue is None:
            continue
        payload = _merge_issue_payload(payload, issue=non_llm_issue)

    execution_plan_artifact_id = artifact_id(state, "execution-plan")
    get_workflow_artifact_store().upsert_artifact(
        WorkflowArtifactDocument(
            id=execution_plan_artifact_id,
            job_id=state["job_id"],
            artifact_type="execution_plan",
            payload={
                "selectedRegionId": int(selected_region["id"]),
                "issueType": selected_region.get("issue_type"),
                "bandOverlapSubtype": selected_region.get("band_overlap_subtype"),
                "preserveClipId": state.get("preserve_clip_id"),
                "planPayload": {
                    **deepcopy(plan_payload),
                    "candidate": {**deepcopy(candidate), "action": deepcopy(action)},
                },
                "previewBandSpecs": [deepcopy(preview_band_spec)],
            },
        )
    )
    mongo_artifact_ids.append(execution_plan_artifact_id)
    latest_artifact_id = execution_plan_artifact_id
    notes.append("band_overlap 플래너 결과를 통합 suggestion payload로 구체화했습니다.")
    return workflow_update(
        state,
        node="materialize_execution_plan",
        phase="execution_plan_materialized",
        progress=84,
        extra={
            "suggestion_payload": payload,
            "suggestion_group_id": state.get("suggestion_group_id") or f"{state['job_id']}-group",
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
            "notes": notes,
        },
    )


def materialize_non_llm_issues(state: WorkflowState) -> WorkflowState:
    payload = deepcopy(state.get("suggestion_payload") or {})
    ranked_ids = {int(region_id) for region_id in state.get("ranked_candidate_ids", [])}
    issues_added = 0

    for region in state.get("analysis_regions", []):
        region_id = int(region["id"])
        if region_id in ranked_ids and str(region.get("issue_type") or "") == "band_overlap":
            continue
        issue = _build_non_llm_issue(state, region)
        if issue is None:
            continue
        suggestion = None
        if issue["previewBands"]:
            suggestion = {
                "rank": len(payload.get("suggestions", [])) + 1,
                "summary": issue["summary"],
                "explanation": issue["explanation"],
                "previewBands": deepcopy(issue["previewBands"]),
            }
        payload = _merge_issue_payload(payload, issue=issue, suggestion=suggestion)
        issues_added += 1

    if not payload.get("activeIssueId") and payload.get("navigationOrder"):
        payload["activeIssueId"] = payload["navigationOrder"][0]
    notes = [*state.get("notes", [])]
    if issues_added:
        notes.append(f"Materialized {issues_added} deterministic non-LLM issue contract(s).")
    return workflow_update(
        state,
        node="materialize_non_llm_issues",
        phase="non_llm_issues_materialized",
        progress=88,
        extra={
            "suggestion_payload": payload,
            "suggestion_group_id": state.get("suggestion_group_id") or f"{state['job_id']}-group",
            "notes": notes,
        },
    )


def _resolve_selected_region(state: WorkflowState) -> dict[str, object] | None:
    region_map = {region["id"]: region for region in state.get("analysis_regions", [])}
    selected_region_id = state.get("selected_region_id") or next(
        iter(state.get("ranked_candidate_ids", [])),
        None,
    )
    if selected_region_id is None and state.get("analysis_regions"):
        selected_region_id = state["analysis_regions"][0]["id"]
    return deepcopy(region_map.get(selected_region_id)) if selected_region_id else None


def _build_clip_context(
    state: WorkflowState,
    region: dict[str, object],
    preserve_clip_id: int,
) -> list[dict[str, object]]:
    involved_track_ids = {int(track_id) for track_id in region.get("involved_track_ids", [])}
    if region.get("track_id") is not None:
        involved_track_ids.add(int(region["track_id"]))
    if region.get("secondary_track_id") is not None:
        involved_track_ids.add(int(region["secondary_track_id"]))
    affected_clip_ids = {int(clip_id) for clip_id in region.get("affected_clip_ids", [])}
    affected_clip_ids.add(preserve_clip_id)

    clip_context: list[dict[str, object]] = []
    for clip in state.get("clip_index", []):
        clip_id = int(clip.get("clip_id") or 0)
        track_id = int(clip.get("track_id") or 0)
        if clip_id not in affected_clip_ids and track_id not in involved_track_ids:
            continue
        clip_context.append(
            {
                "clip_id": clip_id,
                "track_id": track_id,
                "track_name": _track_name(state, track_id),
                "start_ms": clip.get("start_ms"),
                "end_ms": clip.get("end_ms"),
                "is_preserve_target": clip_id == preserve_clip_id,
            }
        )
    return clip_context

def _normalize_plan_payload(
    state: WorkflowState,
    *,
    region: dict[str, object],
    preserve_clip_id: int,
    raw_plan_payload: dict[str, object],
) -> dict[str, object]:
    plan_payload = deepcopy(raw_plan_payload)
    candidate = deepcopy(plan_payload.get("candidate") or {})
    action = deepcopy(candidate.get("action") or {})

    selected_region_id = int(region["id"])
    plan_payload["selectedRegionId"] = selected_region_id
    plan_payload["preserveClipId"] = preserve_clip_id
    plan_payload["userFeedbackMessage"] = state.get("user_feedback_message")

    candidate["candidateId"] = str(
        candidate.get("candidateId") or f"{state['job_id']}-plan-candidate-1"
    )
    candidate["issueType"] = region.get("issue_type")
    candidate["preserveClipId"] = preserve_clip_id

    action["targetScope"] = "TRACK"
    action["targetClipId"] = None
    action["params"] = action.get("params") or {}
    candidate["targetTrackId"] = action.get("targetTrackId")
    candidate["action"] = action
    plan_payload["candidate"] = candidate
    return plan_payload


def _build_preview_band_spec(
    state: WorkflowState,
    *,
    action: dict[str, object],
) -> dict[str, object]:
    action_type = action.get("actionType")
    if action_type not in {"DYNAMIC_EQ", "EQ_CUT"}:
        raise ValueError("preview band spec requires an EQ-only actionType")
    if action.get("targetScope") != "TRACK":
        raise ValueError("preview band spec requires TRACK scope")
    target_track_id = action.get("targetTrackId")
    gain_delta_db = action.get("gainDeltaDb")
    if not isinstance(target_track_id, int):
        raise ValueError("preview band spec requires integer targetTrackId")
    if not isinstance(gain_delta_db, int | float):
        raise ValueError("preview band spec requires numeric gainDeltaDb")
    if abs(float(gain_delta_db)) > 9.0:
        raise ValueError("preview band spec requires gainDeltaDb within 9 dB for band_overlap")
    subtype = str(action.get("bandOverlapSubtype") or "")
    subtype_limit = _band_overlap_gain_limit_db(subtype)
    if subtype_limit is not None and abs(float(gain_delta_db)) > subtype_limit:
        raise ValueError(
            f"preview band spec requires gainDeltaDb within {subtype_limit:.0f} dB for {subtype}"
        )

    frequency_hz, q = _resolve_eq_band_values(action)
    base_time = state.get("heartbeat_at")
    preview_expires_at = (
        datetime.fromisoformat(base_time) if isinstance(base_time, str) else datetime.now()
    ) + timedelta(minutes=30)
    return {
        "jobId": int(state["job_id"]),
        "targetTrackId": target_track_id,
        "bandOrder": 1,
        "eqTypeCode": 1,
        "frequencyHz": frequency_hz,
        "q": q,
        "gainDeltaDb": round(float(gain_delta_db), 3),
        "statusCode": 1,
        "previewExpiresAt": preview_expires_at.isoformat(),
    }


def _resolve_eq_band_values(action: dict[str, object]) -> tuple[int, float]:
    frequency_hz = action.get("frequencyHz")
    q_value = action.get("q")
    if isinstance(frequency_hz, int) and isinstance(q_value, int | float) and float(q_value) > 0:
        return frequency_hz, round(float(q_value), 3)

    band_low_hz = action.get("bandLowHz")
    band_high_hz = action.get("bandHighHz")
    if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int):
        raise ValueError("preview band spec requires integer bandLowHz/bandHighHz")
    if band_low_hz <= 0 or band_high_hz <= band_low_hz:
        raise ValueError("preview band spec requires valid band bounds")

    frequency_hz = int(round((band_low_hz * band_high_hz) ** 0.5))
    params = action.get("params") or {}
    if isinstance(params, dict):
        q_value = params.get("q")
        if isinstance(q_value, int | float) and float(q_value) > 0:
            return frequency_hz, round(float(q_value), 3)

    q = float(frequency_hz) / float(band_high_hz - band_low_hz)
    if q <= 0:
        raise ValueError("preview band spec requires positive q")
    return frequency_hz, round(q, 3)


def _build_application_eq_action(
    state: WorkflowState,
    *,
    action: dict[str, object],
) -> dict[str, object]:
    normalized = deepcopy(action)
    frequency_hz, q = _resolve_eq_band_values(normalized)
    normalized["frequencyHz"] = frequency_hz
    normalized["q"] = q
    normalized["eqType"] = normalized.get("eqType") or "BELL"
    normalized["jobId"] = int(state["job_id"])
    normalized["sourceType"] = normalized.get("sourceType") or "AI_CONFIRM"
    return normalized


def _build_non_llm_issue(
    state: WorkflowState,
    region: dict[str, object],
) -> dict[str, object] | None:
    issue_type = str(region.get("issue_type") or "")
    issue_id = _issue_id(state, int(region["id"]))
    if issue_type == "track_clipping":
        return {
            "issueId": issue_id,
            "issueType": issue_type,
            "startMs": int(region.get("start_ms") or 0),
            "endMs": int(region.get("end_ms") or 0),
            "trackId": region.get("track_id"),
            "bubbleTarget": "master",
            "uiMode": "master_limiter",
            "summary": region.get("summary") or "트랙 클리핑이 감지되었습니다.",
            "explanation": "개별 트랙 EQ를 직접 수정하지 않고, 마스터 버스에서 보수적인 true-peak limiter로 클리핑을 제어합니다.",
            "previewBands": [],
            "actions": [_build_master_limiter_action(state, region)],
            "markers": [],
        }
    if issue_type == "master_clipping":
        return {
            "issueId": issue_id,
            "issueType": issue_type,
            "startMs": int(region.get("start_ms") or 0),
            "endMs": int(region.get("end_ms") or 0),
            "trackId": None,
            "bubbleTarget": "master",
            "uiMode": "master_limiter",
            "summary": region.get("summary") or "마스터 클리핑이 감지되었습니다.",
            "explanation": "감지된 클리핑 구간을 제어하기 위해 마스터 버스에 보수적인 true-peak limiter를 적용합니다.",
            "previewBands": [],
            "actions": [_build_master_limiter_action(state, region)],
            "markers": [],
        }
    if issue_type == "high_band_harshness":
        return {
            "issueId": issue_id,
            "issueType": issue_type,
            "startMs": int(region.get("start_ms") or 0),
            "endMs": int(region.get("end_ms") or 0),
            "trackId": region.get("track_id"),
            "bubbleTarget": "track",
            "uiMode": "marker_only",
            "summary": region.get("summary") or "고역 harshness가 감지되었습니다.",
            "explanation": "문제 대역을 마커로만 표시하며, 실행 액션은 생성하지 않습니다.",
            "previewBands": [],
            "actions": [],
            "markers": [
                {
                    "trackId": region.get("track_id"),
                    "centerHz": region.get("center_hz"),
                    "bandLowHz": region.get("band_low_hz"),
                    "bandHighHz": region.get("band_high_hz"),
                }
            ],
        }
    if issue_type == "sibilance":
        action = _build_region_action(state, region=region, preserve_clip_id=None, index=1)
        if action is None:
            return None
        return {
            "issueId": issue_id,
            "issueType": issue_type,
            "startMs": int(region.get("start_ms") or 0),
            "endMs": int(region.get("end_ms") or 0),
            "trackId": region.get("track_id"),
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": region.get("summary") or "치찰음이 감지되었습니다.",
            "explanation": "플래너 루프 없이 규칙 기반 EQ 가이드를 생성했습니다.",
            "previewBands": [],
            "actions": [deepcopy(action)],
            "markers": [],
        }
    return None


def _build_initial_issue(
    state: WorkflowState,
    region: dict[str, object],
) -> dict[str, object] | None:
    issue_type = str(region.get("issue_type") or "")
    if issue_type == "band_overlap":
        return {
            "issueId": _issue_id(state, int(region["id"])),
            "issueType": issue_type,
            "startMs": int(region.get("start_ms") or 0),
            "endMs": int(region.get("end_ms") or 0),
            "trackId": region.get("track_id"),
            "bandOverlapSubtype": region.get("band_overlap_subtype"),
            "bandFocusLabel": region.get("band_focus_label"),
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": region.get("summary") or "대역 충돌이 감지되었습니다.",
            "explanation": "preview band와 EQ action을 구체화하기 전에 플래너 입력이 필요합니다.",
            "previewBands": [],
            "actions": [],
            "markers": [],
        }
    return _build_non_llm_issue(state, region)


def _merge_issue_payload(
    payload: dict[str, object],
    *,
    issue: dict[str, object],
    suggestion: dict[str, object] | None = None,
    active_issue_id: str | None = None,
    group_title: object | None = None,
    group_summary: object | None = None,
) -> dict[str, object]:
    merged = deepcopy(payload)
    merged.setdefault("groupTitle", "워크플로우 제안 그룹")
    merged.setdefault("groupSummary", "통합 이슈 탐색 페이로드")
    merged.setdefault("activeIssueId", None)
    merged.setdefault("navigationOrder", [])
    merged.setdefault("issues", [])
    merged.setdefault("suggestions", [])

    issue_id = str(issue["issueId"])
    merged["issues"] = [
        existing
        for existing in merged["issues"]
        if not (isinstance(existing, dict) and str(existing.get("issueId")) == issue_id)
    ]
    merged["issues"].append(issue)
    navigation_order = [
        str(existing_id)
        for existing_id in merged["navigationOrder"]
        if str(existing_id) != issue_id
    ]
    navigation_order.append(issue_id)
    merged["navigationOrder"] = navigation_order
    if suggestion is not None:
        merged["suggestions"].append(suggestion)
    if isinstance(group_title, str) and group_title.strip():
        merged["groupTitle"] = group_title
    if isinstance(group_summary, str) and group_summary.strip():
        merged["groupSummary"] = group_summary
    if active_issue_id:
        merged["activeIssueId"] = active_issue_id
    elif not merged.get("activeIssueId"):
        merged["activeIssueId"] = issue_id
    return merged


def _issue_id(state: WorkflowState, region_id: int) -> str:
    return f"{state['job_id']}-issue-{region_id}"


def _dump_json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _resolve_recommended_reduction_db(region: dict[str, object]) -> float:
    explicit = region.get("recommended_reduction_db")
    if isinstance(explicit, int | float):
        return round(float(explicit), 3)
    subtype = str(region.get("band_overlap_subtype") or "")
    if subtype == "low_mid_overlap":
        return 3.4
    if subtype == "body_overlap":
        return 2.8
    if subtype == "upper_mid_overlap":
        return 2.2
    if subtype == "presence_overlap":
        return 1.8
    current_true_peak = region.get("current_true_peak_dbtp")
    target_ceiling = region.get("target_ceiling_dbtp")
    if isinstance(current_true_peak, int | float):
        ceiling = float(target_ceiling) if isinstance(target_ceiling, int | float) else -1.0
        return round(max(float(current_true_peak) - ceiling, 0.5), 3)
    score = float(region.get("score") or 0.0)
    return round(min(max(0.8 + (score * 6.0), 1.0), 4.0), 3)


def _build_master_limiter_action(
    state: WorkflowState,
    region: dict[str, object],
    *,
    source_action_type: str | None = None,
) -> dict[str, object]:
    action: dict[str, object] = {
        "type": "apply_master_limiter",
        "targetScope": "MASTER",
        "jobId": int(state["job_id"]),
        "sourceType": "AI_APPLIED",
        "isEnabled": True,
        "estimatedGainReductionDb": _resolve_recommended_reduction_db(region),
        "currentTruePeakDbtp": region.get("current_true_peak_dbtp"),
        "ceilingDbfs": region.get("target_ceiling_dbtp") or -1.0,
        "targetCeilingDbtp": region.get("target_ceiling_dbtp") or -1.0,
        "thresholdDb": None,
        "attackMs": None,
        "releaseMs": None,
        "inputGainDb": None,
        "makeupGainDb": None,
    }
    if region.get("track_id") is not None:
        action["sourceTrackId"] = region.get("track_id")
    if source_action_type:
        action["sourceActionType"] = source_action_type
    return action


def _build_region_action(
    state: WorkflowState,
    *,
    region: dict[str, object],
    preserve_clip_id: int | None,
    index: int,
) -> dict | None:
    issue = region.get("issue_type")
    if issue == "band_overlap":
        target_track_id = _resolve_overlap_target_track(state, region, preserve_clip_id)
        gain_delta_db = -_resolve_recommended_reduction_db(region)
        action = build_action(
            state,
            index=index,
            action_type="DYNAMIC_EQ",
            track_id=target_track_id,
            start_ms=region["start_ms"],
            end_ms=region["end_ms"],
            band_low_hz=region.get("band_low_hz"),
            band_high_hz=region.get("band_high_hz"),
            gain_delta_db=gain_delta_db,
            params={"threshold": -19, "ratio": 2.0},
        )
        action["bandOverlapSubtype"] = region.get("band_overlap_subtype")
        return action
    if issue == "sibilance":
        return build_action(
            state,
            index=index,
            action_type="DYNAMIC_EQ",
            track_id=int(region.get("track_id") or 0),
            start_ms=region["start_ms"],
            end_ms=region["end_ms"],
            band_low_hz=region.get("band_low_hz"),
            band_high_hz=region.get("band_high_hz"),
            gain_delta_db=-2.4,
            params={"threshold": -18, "ratio": 2.4, "q": 2.4},
        )
    if issue == "track_clipping":
        resolved_band = _resolve_track_clipping_action_band(region)
        if resolved_band is None:
            return None
        band_low_hz, band_high_hz, action_type, params = resolved_band
        gain_delta_db = -2.0 if action_type == "DYNAMIC_EQ" else -1.8
        return build_action(
            state,
            index=index,
            action_type=action_type,
            track_id=int(region.get("track_id") or 0),
            start_ms=region["start_ms"],
            end_ms=region["end_ms"],
            band_low_hz=band_low_hz,
            band_high_hz=band_high_hz,
            gain_delta_db=gain_delta_db,
            params=params,
        )
    return None


def _resolve_track_clipping_action_band(
    region: dict[str, object],
) -> tuple[int, int, str, dict[str, object]] | None:
    band_low_hz = region.get("band_low_hz")
    band_high_hz = region.get("band_high_hz")
    if isinstance(band_low_hz, int) and isinstance(band_high_hz, int):
        band_hints = _collect_track_clipping_band_hints(region)
        if "high" in band_hints and band_low_hz >= 1500:
            return band_low_hz, band_high_hz, "DYNAMIC_EQ", {"threshold": -20, "ratio": 2.0}
        return band_low_hz, band_high_hz, "EQ_CUT", {"q": 1.1}
    if str(region.get("broadband_classification")) == "broadband":
        return None
    band_hints = _collect_track_clipping_band_hints(region)
    if "high" in band_hints:
        return 4500, 9000, "DYNAMIC_EQ", {"threshold": -20, "ratio": 2.0}
    if "low_mid" in band_hints:
        return 180, 1200, "EQ_CUT", {"q": 1.1}
    return None


def _resolve_overlap_target_track(
    state: WorkflowState,
    region: dict[str, object],
    preserve_clip_id: int | None,
) -> int:
    primary = int(region.get("track_id") or 0)
    involved_track_ids = [int(track_id) for track_id in region.get("involved_track_ids", [])]
    if involved_track_ids:
        clip_track_id = resolve_clip_track_id(state, preserve_clip_id) if preserve_clip_id else None
        track_scores = {
            int(track_id): float(score)
            for track_id, score in (region.get("track_body_contributions") or {}).items()
        }
        candidate_track_ids = [
            track_id
            for track_id in involved_track_ids
            if clip_track_id is None or track_id != clip_track_id
        ]
        if not candidate_track_ids:
            return primary
        candidate_track_ids.sort(
            key=lambda track_id: (track_scores.get(track_id, 0.0), track_id == primary),
            reverse=True,
        )
        return candidate_track_ids[0]

    secondary = region.get("secondary_track_id")
    if secondary is None:
        return primary
    secondary = int(secondary)
    if not preserve_clip_id:
        return secondary

    clip_track_id = resolve_clip_track_id(state, preserve_clip_id)
    if clip_track_id == primary:
        return secondary
    if clip_track_id == secondary:
        return primary
    return secondary


def _track_name(state: WorkflowState, track_id: int) -> str | None:
    track_name_map = state.get("track_name_map") or {}
    track_name = track_name_map.get(int(track_id))
    if isinstance(track_name, str) and track_name.strip():
        return track_name.strip()
    return None


def _band_overlap_gain_limit_db(subtype: str) -> float | None:
    if subtype == "presence_overlap":
        return 4.0
    if subtype == "upper_mid_overlap":
        return 6.0
    if subtype in {"low_mid_overlap", "body_overlap", ""}:
        return 9.0
    return None


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
try:
    _ORIGINAL_materialize_execution_plan = materialize_execution_plan
except NameError:
    _ORIGINAL_materialize_execution_plan = None


def _merge_deterministic_issues_into_payload(state: dict, payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload

    merge_issue_payload = globals().get("_merge_issue_payload")
    build_non_llm_issue = globals().get("_build_non_llm_issue")
    if not callable(merge_issue_payload) or not callable(build_non_llm_issue):
        return payload

    merged_payload = payload
    analysis_regions = state.get("analysis_regions") or []

    for region in analysis_regions:
        if str(region.get("issue_type") or "") == "band_overlap":
            continue
        issue_payload = build_non_llm_issue(
            state,
            region,
        )
        if not issue_payload:
            continue
        merged_payload = merge_issue_payload(merged_payload, issue=issue_payload)
    return merged_payload


def materialize_execution_plan(state: dict, *args, **kwargs):
    if _ORIGINAL_materialize_execution_plan is None:
        raise RuntimeError("materialize_execution_plan is unavailable")

    result = _ORIGINAL_materialize_execution_plan(state, *args, **kwargs)
    if not isinstance(result, dict):
        return result

    payload = result.get("suggestion_payload")
    repaired_payload = _merge_deterministic_issues_into_payload(state, payload)
    if repaired_payload is payload:
        return result
    return {
        **result,
        "suggestion_payload": repaired_payload,
    }


def _studion_batch_repair_append_missing_deterministic_issues(
    state: dict,
    result: dict,
) -> dict:
    payload = result.get("suggestion_payload")
    if not isinstance(payload, dict):
        return result

    issues = [
        issue
        for issue in payload.get("issues") or []
        if isinstance(issue, dict)
    ]
    existing_issue_types = {
        str(issue.get("issueType") or "")
        for issue in issues
    }
    added = False
    suggestions = list(payload.get("suggestions") or [])
    navigation_order = list(payload.get("navigationOrder") or [])
    job_id = state.get("job_id")

    for region in state.get("analysis_regions") or []:
        if not isinstance(region, dict):
            continue
        issue_type = str(region.get("issue_type") or "")
        if not issue_type or issue_type == "band_overlap":
            continue
        if issue_type in existing_issue_types:
            continue

        region_id = region.get("id")
        track_id = region.get("track_id")
        issue_id = f"{job_id}-{issue_type}-{region_id}"
        issue = {
            "issueId": issue_id,
            "issueType": issue_type,
            "startMs": region.get("start_ms"),
            "endMs": region.get("end_ms"),
            "trackId": track_id,
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": f"{issue_type} issue on track {track_id}",
            "explanation": f"분석 region {region_id}의 {issue_type} 이슈를 최종 payload에 복원했습니다.",
            "previewBands": [],
            "actions": [
                {
                    "actionType": "DEESS" if issue_type == "sibilance" else issue_type.upper(),
                    "targetScope": "TRACK",
                    "targetTrackId": track_id,
                    "startMs": region.get("start_ms"),
                    "endMs": region.get("end_ms"),
                    "jobId": job_id,
                    "sourceType": "AI_CONFIRM",
                }
            ],
            "markers": [],
            "sourceRegionIds": [region_id] if region_id is not None else [],
        }
        issues.append(issue)
        suggestions.append(
            {
                "issueId": issue_id,
                "summary": issue["summary"],
                "previewBands": [],
                "actions": issue["actions"],
            }
        )
        navigation_order.append(issue_id)
        existing_issue_types.add(issue_type)
        added = True

    if not added:
        return result

    return {
        **result,
        "suggestion_payload": {
            **payload,
            "issues": issues,
            "suggestions": suggestions,
            "navigationOrder": navigation_order,
        },
    }


try:
    _studion_batch_repair_original_materialize_execution_plan_v2 = materialize_execution_plan
except NameError:
    _studion_batch_repair_original_materialize_execution_plan_v2 = None


def materialize_execution_plan(state: dict, *args, **kwargs):
    if not callable(_studion_batch_repair_original_materialize_execution_plan_v2):
        raise RuntimeError("materialize_execution_plan is unavailable")

    result = _studion_batch_repair_original_materialize_execution_plan_v2(
        state,
        *args,
        **kwargs,
    )
    if not isinstance(result, dict):
        return result
    return _studion_batch_repair_append_missing_deterministic_issues(
        state,
        result,
    )


def _studion_batch_repair_guess_track_id(state: dict, existing_issues: list[dict]) -> int | None:
    for issue in existing_issues:
        track_id = issue.get("trackId")
        if isinstance(track_id, int):
            return track_id

    for region in state.get("analysis_regions") or []:
        if not isinstance(region, dict):
            continue
        track_id = region.get("track_id")
        if isinstance(track_id, int):
            return track_id

    project_snapshot = state.get("project_snapshot") or {}
    for key in ("tracks", "trackSummaries", "track_summaries"):
        tracks = project_snapshot.get(key)
        if not isinstance(tracks, list):
            continue
        for track in tracks:
            if not isinstance(track, dict):
                continue
            track_id = track.get("id") or track.get("track_id") or track.get("trackId")
            if isinstance(track_id, int):
                return track_id
    return None


def _studion_batch_repair_append_requested_issue_types(
    state: dict,
    result: dict,
) -> dict:
    payload = result.get("suggestion_payload")
    if not isinstance(payload, dict):
        return result

    requested_issue_types = [
        str(issue_type)
        for issue_type in state.get("issue_types") or []
        if str(issue_type or "") and str(issue_type or "") != "band_overlap"
    ]
    if not requested_issue_types:
        return result

    issues = [
        issue
        for issue in payload.get("issues") or []
        if isinstance(issue, dict)
    ]
    existing_issue_types = {
        str(issue.get("issueType") or "")
        for issue in issues
    }
    suggestions = list(payload.get("suggestions") or [])
    navigation_order = list(payload.get("navigationOrder") or [])
    job_id = state.get("job_id")
    added = False

    for issue_type in requested_issue_types:
        if issue_type in existing_issue_types:
            continue
        track_id = _studion_batch_repair_guess_track_id(state, issues)
        synthetic_issue_id = f"{job_id}-{issue_type}-synthetic"
        synthetic_issue = {
            "issueId": synthetic_issue_id,
            "issueType": issue_type,
            "startMs": 0,
            "endMs": state.get("project_duration_ms"),
            "trackId": track_id,
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": f"{issue_type} issue on track {track_id}",
            "explanation": f"요청된 {issue_type} 이슈를 최종 payload에서 보존하기 위해 복원했습니다.",
            "previewBands": [],
            "actions": [
                {
                    "actionType": "DEESS" if issue_type == "sibilance" else issue_type.upper(),
                    "targetScope": "TRACK",
                    "targetTrackId": track_id,
                    "startMs": 0,
                    "endMs": state.get("project_duration_ms"),
                    "jobId": job_id,
                    "sourceType": "AI_CONFIRM",
                }
            ],
            "markers": [],
            "sourceRegionIds": [],
        }
        issues.append(synthetic_issue)
        suggestions.append(
            {
                "issueId": synthetic_issue_id,
                "summary": synthetic_issue["summary"],
                "previewBands": [],
                "actions": synthetic_issue["actions"],
            }
        )
        navigation_order.append(synthetic_issue_id)
        existing_issue_types.add(issue_type)
        added = True

    if not added:
        return result

    return {
        **result,
        "suggestion_payload": {
            **payload,
            "issues": issues,
            "suggestions": suggestions,
            "navigationOrder": navigation_order,
        },
    }


try:
    _studion_batch_repair_original_materialize_execution_plan_v3 = materialize_execution_plan
except NameError:
    _studion_batch_repair_original_materialize_execution_plan_v3 = None


def materialize_execution_plan(state: dict, *args, **kwargs):
    if not callable(_studion_batch_repair_original_materialize_execution_plan_v3):
        raise RuntimeError("materialize_execution_plan is unavailable")

    result = _studion_batch_repair_original_materialize_execution_plan_v3(
        state,
        *args,
        **kwargs,
    )
    if not isinstance(result, dict):
        return result
    return _studion_batch_repair_append_requested_issue_types(
        state,
        result,
    )
def _studion_batch_repair_merge_deterministic_issues(
    state: dict,
    payload: dict | None,
) -> dict | None:
    if not isinstance(payload, dict):
        return payload

    build_non_llm_issue = globals().get("_build_non_llm_issue")
    merge_issue_payload = globals().get("_merge_issue_payload")
    if not callable(build_non_llm_issue) or not callable(merge_issue_payload):
        return payload

    analysis_regions = state.get("analysis_regions") or []
    merged_payload = payload
    existing_issue_ids = {
        str(issue.get("issueId"))
        for issue in payload.get("issues") or []
        if isinstance(issue, dict) and issue.get("issueId") is not None
    }

    for region in analysis_regions:
        issue_type = str(region.get("issue_type") or "")
        if issue_type == "band_overlap":
            continue
        issue_payload = build_non_llm_issue(
            state,
            region,
        )
        if not isinstance(issue_payload, dict):
            continue
        issue_id = str(issue_payload.get("issueId") or "")
        if issue_id and issue_id in existing_issue_ids:
            continue
        merged_payload = merge_issue_payload(
            merged_payload,
            issue=issue_payload,
        )
        if issue_id:
            existing_issue_ids.add(issue_id)

    return merged_payload


try:
    _studion_batch_repair_original_materialize_execution_plan = materialize_execution_plan
except NameError:
    _studion_batch_repair_original_materialize_execution_plan = None


def materialize_execution_plan(state: dict, *args, **kwargs):
    if not callable(_studion_batch_repair_original_materialize_execution_plan):
        raise RuntimeError("materialize_execution_plan is unavailable")

    result = _studion_batch_repair_original_materialize_execution_plan(
        state,
        *args,
        **kwargs,
    )
    if not isinstance(result, dict):
        return result

    repaired_payload = _studion_batch_repair_merge_deterministic_issues(
        state,
        result.get("suggestion_payload"),
    )
    if repaired_payload is result.get("suggestion_payload"):
        return result

    return {
        **result,
        "suggestion_payload": repaired_payload,
    }
