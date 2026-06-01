from __future__ import annotations

import logging
import json
from app.graph.nodes.common import (
    artifact_id,
    build_selection_context,
    decide_validation_result,
    resolve_clip_track_id,
    workflow_update,
)
from app.graph.nodes.runtime import fail_workflow
from app.graph.state import WorkflowState
from app.services.workflow_artifacts import WorkflowArtifactDocument, get_workflow_artifact_store
from app.services.plan_critic_llm import (
    PlanCriticLLMError,
    get_plan_critic_llm_client,
)

logger = logging.getLogger(__name__)

ISSUE_ALLOWED_ACTIONS = {
    "band_overlap": {"DYNAMIC_EQ", "EQ_CUT"},
}


def plan_rule_validator(state: WorkflowState) -> WorkflowState:
    plan_payload = state.get("plan_payload") or {}
    validation_error = _validate_plan_payload(state, plan_payload)
    if validation_error is not None:
        logger.warning(
            "plan validator rejected | job_id=%s selected_region_id=%s reason=%s",
            state.get("job_id"),
            state.get("selected_region_id"),
            validation_error,
        )
        return workflow_update(
            state,
            node="plan_rule_validator",
            phase="plan_rule_validated",
            progress=76,
            extra={
                "validator_result": "REJECT",
                "plan_revision_notes": [*state.get("plan_revision_notes", []), validation_error],
            },
        )

    result = decide_validation_result(state, mode_key="validator_mode")
    revision_notes = [*state.get("plan_revision_notes", [])]
    if result == "REVISE":
        revision_notes.append("Rule validator requested a plan revision.")
    if result == "REJECT":
        revision_notes.append("Rule validator rejected the plan.")
    if result != "PASS":
        logger.warning(
            "plan validator result | job_id=%s selected_region_id=%s result=%s note=%s",
            state.get("job_id"),
            state.get("selected_region_id"),
            result,
            revision_notes[-1] if revision_notes else "",
        )
    return workflow_update(
        state,
        node="plan_rule_validator",
        phase="plan_rule_validated",
        progress=76,
        extra={
            "validator_result": result,
            "plan_revision_notes": revision_notes,
            "plan_status": "UNDER_REVIEW",
        },
    )


def plan_critic(state: WorkflowState) -> WorkflowState:
    selected_region = _resolve_selected_region(state)
    preserve_clip_id = state.get("preserve_clip_id")
    if selected_region is None or preserve_clip_id is None:
        return fail_workflow(
            {
                **state,
                "failure_code": "PLAN_CRITIC_CONTEXT_MISSING",
                "failure_message": "Plan critic could not restore the selected region context.",
            }
        )

    try:
        critic_response = get_plan_critic_llm_client().review_plan(
            selected_region_id=int(selected_region["id"]),
            preserve_clip_id=int(preserve_clip_id),
            user_feedback_message=state.get("user_feedback_message"),
            selection_context=build_selection_context(state, selected_region, int(preserve_clip_id)),
            region=selected_region,
            plan_payload=state.get("plan_payload") or {},
            revision_notes=[*state.get("plan_revision_notes", [])],
        )
    except PlanCriticLLMError as exc:
        return fail_workflow(
            {
                **state,
                "failure_code": exc.code,
                "failure_message": exc.message,
            }
        )

    original_result = critic_response.result
    result = critic_response.result
    critic_note = critic_response.note
    current_artifact_id = artifact_id(state, "plan-critic")
    raw_critic_text = critic_response.raw_text or _dump_critic_text(critic_response.result, critic_response.note)
    revision_notes = [*state.get("plan_revision_notes", [])]

    supplemental_result, supplemental_note = _supplement_critic_decision(
        state=state,
        region=selected_region,
        plan_payload=state.get("plan_payload") or {},
    )
    if supplemental_result is not None:
        result = supplemental_result
        if original_result == "PASS" and supplemental_result != "PASS":
            critic_note = supplemental_note
        else:
            critic_note = _merge_critic_notes(critic_note, supplemental_note)
        raw_critic_text = _dump_critic_text(result, critic_note)

    result, critic_note = _normalize_presence_deadlock_decision(
        state=state,
        region=selected_region,
        result=result,
        critic_note=critic_note,
    )
    raw_critic_text = _dump_critic_text(result, critic_note)

    mode_override = decide_validation_result(state, mode_key="critic_mode")
    if mode_override != "PASS":
        result = mode_override
    if result == "REVISE" and critic_note == "":
        critic_note = "Plan critic requested a semantic revision."
    if result == "REJECT" and critic_note == "":
        critic_note = "Plan critic rejected the strategy."
    if result != "PASS" and critic_note:
        revision_notes.append(critic_note)
    if result != "PASS":
        logger.warning(
            "plan critic result | job_id=%s selected_region_id=%s result=%s note=%s",
            state.get("job_id"),
            state.get("selected_region_id"),
            result,
            revision_notes[-1] if revision_notes else "",
        )

    get_workflow_artifact_store().upsert_artifact(
        WorkflowArtifactDocument(
            id=current_artifact_id,
            job_id=state["job_id"],
            artifact_type="plan_critic",
            payload={
                "selectedRegionId": int(selected_region["id"]),
                "preserveClipId": int(preserve_clip_id),
                "result": result,
                "note": critic_note,
                "rawText": raw_critic_text,
                "planPayload": state.get("plan_payload") or {},
            },
        )
    )

    return workflow_update(
        state,
        node="plan_critic",
        phase="plan_critic_checked",
        progress=80,
        extra={
            "critic_result": result,
            "critic_raw_text": raw_critic_text,
            "critic_artifact_id": current_artifact_id,
            "plan_revision_notes": revision_notes,
            "plan_status": "UNDER_REVIEW",
            "mongo_artifact_ids": [*state.get("mongo_artifact_ids", []), current_artifact_id],
            "latest_artifact_id": current_artifact_id,
        },
    )


def _validate_plan_payload(state: WorkflowState, plan_payload: dict[str, object]) -> str | None:
    if state.get("ranked_candidate_ids") and not plan_payload:
        return "Plan payload is empty despite ranked candidates."

    selected_region = _resolve_selected_region(state)
    if selected_region is None:
        return "Selected region could not be restored for validation."

    candidate = plan_payload.get("candidate")
    if not isinstance(candidate, dict):
        return "Plan payload omitted a valid candidate object."
    action = candidate.get("action")
    if not isinstance(action, dict):
        return "Plan payload omitted a valid candidate action."
    for field_name in ("strategyTitle", "strategySummary", "summary", "explanation"):
        value = plan_payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            return f"Plan payload omitted a valid {field_name} field."

    issue_type = str(selected_region.get("issue_type") or "")
    if issue_type != "band_overlap":
        return "Planner validation only supports band_overlap issues."
    action_type = action.get("actionType")
    if not isinstance(action_type, str):
        return "Plan action omitted a valid actionType."
    allowed_action_types = ISSUE_ALLOWED_ACTIONS.get(issue_type)
    if allowed_action_types is None or action_type not in allowed_action_types:
        return f"Action type {action_type} is not allowed for issue {issue_type}."

    target_scope = action.get("targetScope")
    if target_scope != "TRACK":
        return "Plan action omitted a valid targetScope."
    target_track_id = action.get("targetTrackId")
    if target_track_id is None:
        return "TRACK-scoped actions must include targetTrackId."

    start_ms = action.get("startMs")
    end_ms = action.get("endMs")
    region_start_ms = selected_region.get("start_ms")
    region_end_ms = selected_region.get("end_ms")
    if not isinstance(start_ms, int) or not isinstance(end_ms, int):
        return "Plan action omitted valid startMs/endMs values."
    if start_ms > end_ms:
        return "Plan action startMs must not exceed endMs."
    if isinstance(region_start_ms, int) and start_ms < region_start_ms:
        return "Plan action startMs cannot precede the selected region."
    if isinstance(region_end_ms, int) and end_ms > region_end_ms:
        return "Plan action endMs cannot exceed the selected region."

    band_low_hz = action.get("bandLowHz")
    band_high_hz = action.get("bandHighHz")
    if band_low_hz is not None and band_high_hz is not None:
        if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int):
            return "Plan action band fields must be integers when present."
        if band_low_hz > band_high_hz:
            return "Plan action bandLowHz must not exceed bandHighHz."

    gain_delta_db = action.get("gainDeltaDb")
    if gain_delta_db is not None and not isinstance(gain_delta_db, int | float):
        return "Plan action gainDeltaDb must be numeric when present."
    if isinstance(gain_delta_db, int | float) and abs(float(gain_delta_db)) > 12.0:
        return "Plan action gainDeltaDb exceeded the allowed safety range."
    subtype = str(selected_region.get("band_overlap_subtype") or "")
    if isinstance(gain_delta_db, int | float) and abs(float(gain_delta_db)) > 9.0:
        return "Band-overlap preview actions must keep gainDeltaDb within 9 dB."
    subtype_limit = _band_overlap_gain_limit_db(subtype)
    if (
        subtype_limit is not None
        and isinstance(gain_delta_db, int | float)
        and abs(float(gain_delta_db)) > subtype_limit
    ):
        return f"{subtype} plans must keep gainDeltaDb within {subtype_limit:.0f} dB."

    params = action.get("params")
    if not isinstance(params, dict):
        return "Plan action params must be an object."

    selected_region_id = plan_payload.get("selectedRegionId")
    if selected_region_id is not None and int(selected_region_id) != int(selected_region["id"]):
        return "Plan payload selectedRegionId did not match the selected region."
    preserve_clip_id = state.get("preserve_clip_id")
    if (
        plan_payload.get("preserveClipId") is not None
        and preserve_clip_id is not None
        and int(plan_payload["preserveClipId"]) != int(preserve_clip_id)
    ):
        return "Plan payload preserveClipId did not match the selected preserve clip."

    preserve_track_id = (
        resolve_clip_track_id(state, int(preserve_clip_id))
        if preserve_clip_id
        else None
    )
    if (
        preserve_track_id is not None
        and target_track_id is not None
        and int(target_track_id) == preserve_track_id
    ):
        return "Band-overlap plans must not target the preserved clip track."
    return None


def _dump_critic_text(result: str, note: str) -> str:
    return json.dumps({"result": result, "note": note}, ensure_ascii=False, indent=2)


def _resolve_selected_region(state: WorkflowState) -> dict[str, object] | None:
    region_map = {region["id"]: region for region in state.get("analysis_regions", [])}
    selected_region_id = state.get("selected_region_id") or next(
        iter(state.get("ranked_candidate_ids", [])),
        None,
    )
    if selected_region_id is None and state.get("analysis_regions"):
        selected_region_id = state["analysis_regions"][0]["id"]
    region = region_map.get(selected_region_id) if selected_region_id else None
    return dict(region) if isinstance(region, dict) else None

def _supplement_critic_decision(
    *,
    state: WorkflowState,
    region: dict[str, object],
    plan_payload: dict[str, object],
) -> tuple[str | None, str]:
    candidate = plan_payload.get("candidate")
    if not isinstance(candidate, dict):
        return None, ""
    action = candidate.get("action")
    if not isinstance(action, dict):
        return None, ""

    target_clip_id = action.get("targetClipId")
    if target_clip_id is not None:
        preserve_clip_id = state.get("preserve_clip_id")
        if preserve_clip_id is not None and int(target_clip_id) == int(preserve_clip_id):
            return "REJECT", "TargetClipId가 preserve clip을 가리킵니다. preserve clip은 직접 수정하지 마세요."
        return "REVISE", "TargetClipId를 null로 유지하고 트랙 단위 EQ 계획만 남기세요."

    gain_delta_db = action.get("gainDeltaDb")
    subtype = str(region.get("band_overlap_subtype") or "")
    if isinstance(gain_delta_db, int | float):
        subtype_limit = _band_overlap_gain_limit_db(subtype) or 9.0
        if abs(float(gain_delta_db)) > subtype_limit:
            return "REVISE", f"GainDeltaDb가 과합니다. 이 subtype에서는 {subtype_limit:.0f}dB 이내로 줄이세요."

    user_feedback = str(state.get("user_feedback_message") or "")
    action_type = str(action.get("actionType") or "")
    if (
        action_type == "DYNAMIC_EQ"
        and _looks_local_static_request(user_feedback)
        and _region_supports_static_local_cut(region)
    ):
        return (
            "REVISE",
            "Keep the current target track fixed. This is a short static pocket, so switch the actionType to EQ_CUT and keep the cut tightly inside the exact masking pocket.",
        )
    if _looks_local_static_request(user_feedback) and str(action.get("actionType") or "") == "DYNAMIC_EQ":
        band_low_hz = action.get("bandLowHz")
        band_high_hz = action.get("bandHighHz")
        region_low_hz = region.get("band_low_hz")
        region_high_hz = region.get("band_high_hz")
        if (
            isinstance(band_low_hz, int)
            and isinstance(band_high_hz, int)
            and isinstance(region_low_hz, int)
            and isinstance(region_high_hz, int)
            and (band_high_hz - band_low_hz) >= max((region_high_hz - region_low_hz) - 20, 1)
        ):
            return "REVISE", "현재 actionType과 targetTrackId는 유지하고, 정확한 pocket만 남도록 start/end와 band를 더 좁히세요. action family를 바꾸기보다 timing, band, gain만 보수적으로 줄이세요."

    return None, ""


def _looks_local_static_request(user_feedback: str) -> bool:
    lowered = user_feedback.lower()
    keywords = (
        "only",
        "exact",
        "local",
        "pocket",
        "exact phrase",
        "touch only",
        "딱",
        "정확",
        "부분만",
        "로컬",
    )
    return any(keyword in lowered for keyword in keywords)


def _region_supports_static_local_cut(region: dict[str, object]) -> bool:
    start_ms = region.get("start_ms")
    end_ms = region.get("end_ms")
    band_low_hz = region.get("band_low_hz")
    band_high_hz = region.get("band_high_hz")
    if not all(
        isinstance(value, int)
        for value in (start_ms, end_ms, band_low_hz, band_high_hz)
    ):
        return False
    duration_ms = int(end_ms) - int(start_ms)
    band_span_hz = int(band_high_hz) - int(band_low_hz)
    return duration_ms <= 900 and band_span_hz <= 700


def _merge_critic_notes(primary: str, supplemental: str) -> str:
    if primary and supplemental:
        return f"{primary} {supplemental}".strip()
    return primary or supplemental


def _band_overlap_gain_limit_db(subtype: str) -> float | None:
    if subtype == "presence_overlap":
        return 4.0
    if subtype == "upper_mid_overlap":
        return 6.0
    if subtype in {"low_mid_overlap", "body_overlap", ""}:
        return 9.0
    return None


def _normalize_presence_deadlock_decision(
    *,
    state: WorkflowState,
    region: dict[str, object],
    result: str,
    critic_note: str,
) -> tuple[str, str]:
    if result != "REJECT":
        return result, critic_note
    if str(region.get("band_overlap_subtype") or "") != "presence_overlap":
        return result, critic_note
    if not _looks_presence_deadlock_note(critic_note):
        return result, critic_note
    band_low_hz = region.get("band_low_hz")
    band_high_hz = region.get("band_high_hz")
    if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int):
        return result, critic_note
    if (band_high_hz - band_low_hz) < 1200:
        return result, critic_note
    revise_count = int(state.get("revise_count") or 0)
    max_revise_count = int(state.get("max_revise_count") or 5)
    if revise_count >= max(max_revise_count - 1, 0):
        return result, critic_note
    return (
        "REVISE",
        (
            "Keep the current action type and target track fixed. "
            "Narrow the presence band first toward the densest pocket, preferably around 3 to 4.5 kHz when supported by the region evidence, "
            "and keep gainDeltaDb at or below -2.5 dB until the band span is materially reduced."
        ),
    )


def _looks_presence_deadlock_note(note: str) -> bool:
    lowered = note.lower()
    keywords = (
        "deadlock",
        "no convergence",
        "cannot safely",
        "narrow band selection",
        "narrow band",
        "wide band",
        "band width",
    )
    return any(keyword in lowered for keyword in keywords)
