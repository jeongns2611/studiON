from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime

from app.graph.nodes.common import (
    resolve_clip_track_id,
    resolve_preserve_clip_id_for_track,
    workflow_update,
)
from app.graph.nodes.review import plan_critic, plan_rule_validator
from app.graph.nodes.runtime import fail_workflow
from app.graph.nodes.suggestion import (
    _build_application_eq_action,
    _build_preview_band_spec,
    _merge_issue_payload,
    planning_agent,
)
from app.graph.state import WorkflowState

logger = logging.getLogger(__name__)

BATCH_CRITIC_MIN_INVOLVED_TRACKS = 3
BATCH_CRITIC_GAIN_THRESHOLD_DB = 3.0
BATCH_CRITIC_BAND_SPAN_THRESHOLD_HZ = 1200
BATCH_MERGE_TIME_GAP_MS = 120
BATCH_MERGE_BAND_GAP_HZ = 80
BATCH_MAX_CUMULATIVE_GAIN_DB = 6.0
BATCH_MAX_TIME_LEAKAGE_MS = 180
BATCH_MAX_BAND_LEAKAGE_HZ = 250
BATCH_MAX_DEFAULT_BAND_SPAN_HZ = 2400
BATCH_SUBTYPE_GAIN_LIMIT_DB = {
    "low_mid_overlap": 3.6,
    "body_overlap": 3.2,
    "upper_mid_overlap": 2.6,
    "presence_overlap": 2.2,
}
BATCH_SUBTYPE_BAND_SPAN_LIMIT_HZ = {
    "low_mid_overlap": 2400,
    "body_overlap": 2200,
    "upper_mid_overlap": 1800,
    "presence_overlap": 1500,
}


def batch_plan_candidates(state: WorkflowState) -> WorkflowState:
    selections, validation_error = _normalize_selected_region_selections(state)
    if validation_error is not None:
        return fail_workflow(
            {
                **state,
                "failure_code": validation_error[0],
                "failure_message": validation_error[1],
            }
        )

    candidate_plans: list[dict[str, object]] = []
    failed_regions: list[dict[str, object]] = []
    critic_run_regions = 0
    critic_skipped_regions = 0

    for selection in selections:
        region_id = int(selection["region_id"])
        logger.info(
            "batch plan region started | job_id=%s region_id=%s preserve_track_id=%s",
            state["job_id"],
            region_id,
            selection["preserve_track_id"],
        )
        outcome = _generate_batch_region_candidate(state, selection)
        if outcome["status"] == "success":
            candidate_plan = deepcopy(outcome["candidate_plan"])
            candidate_plans.append(candidate_plan)
            if candidate_plan.get("criticSkipped"):
                critic_skipped_regions += 1
            else:
                critic_run_regions += 1
            logger.info(
                "batch plan region succeeded | job_id=%s region_id=%s critic_skipped=%s",
                state["job_id"],
                region_id,
                candidate_plan.get("criticSkipped"),
            )
            continue

        failed_region = deepcopy(outcome["failed_region"])
        failed_regions.append(failed_region)
        logger.warning(
            "batch plan region failed | job_id=%s region_id=%s reason=%s",
            state["job_id"],
            region_id,
            failed_region["reasonCode"],
        )

    final_track_envelopes, failed_envelopes, merge_summary = _build_batch_track_envelopes(
        state,
        candidate_plans=candidate_plans,
    )
    failed_regions.extend(deepcopy(failed_envelopes))
    suggestion_payload = _materialize_batch_suggestion_payload(
        state,
        final_track_envelopes=final_track_envelopes,
    )

    notes = [*state.get("notes", [])]
    notes.append(
        "batch plan 후보안 생성을 완료했습니다. "
        f"성공 {len(candidate_plans)}개, 실패 {len(failed_regions)}개 region입니다."
    )

    return workflow_update(
        state,
        node="batch_plan_candidates",
        phase="batch_candidate_plans_generated",
        progress=90,
        extra={
            "request_mode": "batch",
            "selected_region_selections": selections,
            "selected_region_id": None,
            "preserve_clip_id": None,
            "plan_status": "BATCH_CANDIDATES_READY",
            "plan_payload": {},
            "planner_raw_text": None,
            "planner_artifact_id": None,
            "validator_result": None,
            "critic_result": None,
            "critic_raw_text": None,
            "critic_artifact_id": None,
            "plan_revision_notes": [],
            "batch_candidate_plans": candidate_plans,
            "batch_failed_regions": failed_regions,
            "batch_final_track_envelopes": final_track_envelopes,
            "batch_failed_envelopes": failed_envelopes,
            "batch_validation_summary": {
                "requestedRegions": len(selections),
                "successfulRegions": len(candidate_plans),
                "failedRegions": len(failed_regions),
                "criticRunRegions": critic_run_regions,
                "criticSkippedRegions": critic_skipped_regions,
                **merge_summary,
            },
            "suggestion_payload": suggestion_payload,
            "suggestion_group_id": state.get("suggestion_group_id") or f"{state['job_id']}-group",
            "preview_required": bool(suggestion_payload.get("suggestions")),
            "user_action_required": False,
            "has_user_action_candidates": False,
            "has_auto_fixable_eq_issues": bool(suggestion_payload.get("suggestions")),
            "auto_preview_generated": False,
            "notes": notes,
        },
    )


def _generate_batch_region_candidate(
    base_state: WorkflowState,
    selection: dict[str, object],
) -> dict[str, object]:
    region_id = int(selection["region_id"])
    preserve_clip_id = int(selection["preserve_clip_id"])
    temp_state: WorkflowState = deepcopy(base_state)
    temp_state.update(
        {
            "request_mode": "single",
            "selected_region_id": region_id,
            "preserve_clip_id": preserve_clip_id,
            "user_feedback_message": base_state.get("user_feedback_message"),
            "plan_payload": {},
            "planner_raw_text": None,
            "planner_artifact_id": None,
            "plan_status": None,
            "plan_revision_notes": [],
            "validator_result": None,
            "critic_result": None,
            "critic_raw_text": None,
            "critic_artifact_id": None,
            "revise_count": 0,
            "selected_region_selections": [],
            "transition_log": [
                *base_state.get("transition_log", []),
                f"batch-region-{region_id}",
            ],
        }
    )

    planning_delta = planning_agent(temp_state)
    planning_state = {**temp_state, **planning_delta}
    if planning_state.get("runtime_status") == "failed":
        return {
            "status": "failed",
            "failed_region": _build_failed_region(
                selection=selection,
                stage="planner",
                reason_code=str(planning_state.get("failure_code") or "PLANNER_FAILED"),
                message=str(planning_state.get("failure_message") or "Planner failed."),
            ),
        }

    validator_delta = plan_rule_validator(planning_state)
    validator_state = {**planning_state, **validator_delta}
    validator_result = str(validator_state.get("validator_result") or "")
    if validator_result != "PASS":
        return {
            "status": "failed",
            "failed_region": _build_failed_region(
                selection=selection,
                stage="validator",
                reason_code=f"PLAN_VALIDATOR_{validator_result or 'FAILED'}",
                message=_latest_revision_note(
                    validator_state,
                    default_message="Validator rejected the batch candidate plan.",
                ),
            ),
        }

    critic_skipped = not _should_run_batch_critic(validator_state)
    final_state = validator_state
    if not critic_skipped:
        critic_delta = plan_critic(validator_state)
        critic_state = {**validator_state, **critic_delta}
        if critic_state.get("runtime_status") == "failed":
            return {
                "status": "failed",
                "failed_region": _build_failed_region(
                    selection=selection,
                    stage="critic",
                    reason_code=str(critic_state.get("failure_code") or "CRITIC_FAILED"),
                    message=str(critic_state.get("failure_message") or "Critic failed."),
                ),
            }
        critic_result = str(critic_state.get("critic_result") or "")
        if critic_result != "PASS":
            return {
                "status": "failed",
                "failed_region": _build_failed_region(
                    selection=selection,
                    stage="critic",
                    reason_code=f"PLAN_CRITIC_{critic_result or 'FAILED'}",
                    message=_latest_revision_note(
                        critic_state,
                        default_message="Critic rejected the batch candidate plan.",
                    ),
                ),
            }
        final_state = critic_state

    candidate_plan = {
        "regionId": region_id,
        "preserveTrackId": int(selection["preserve_track_id"]),
        "preserveClipId": preserve_clip_id,
        "validatorResult": final_state.get("validator_result"),
        "criticResult": None if critic_skipped else final_state.get("critic_result"),
        "criticSkipped": critic_skipped,
        "planPayload": deepcopy(final_state.get("plan_payload") or {}),
        "revisionNotes": [*final_state.get("plan_revision_notes", [])],
        "mergeStatus": "PENDING",
        "mergedIntoTrackId": None,
    }
    _enrich_candidate_plan(candidate_plan)
    return {"status": "success", "candidate_plan": candidate_plan}


def _enrich_candidate_plan(candidate_plan: dict[str, object]) -> None:
    action = (((candidate_plan.get("planPayload") or {}).get("candidate") or {}).get("action") or {})
    candidate_plan["actionType"] = action.get("actionType")
    candidate_plan["targetTrackId"] = action.get("targetTrackId")
    candidate_plan["targetScope"] = action.get("targetScope")
    candidate_plan["startMs"] = action.get("startMs")
    candidate_plan["endMs"] = action.get("endMs")
    candidate_plan["bandLowHz"] = action.get("bandLowHz")
    candidate_plan["bandHighHz"] = action.get("bandHighHz")
    candidate_plan["gainDeltaDb"] = action.get("gainDeltaDb")
    candidate_plan["params"] = deepcopy(action.get("params") or {})


def _build_batch_track_envelopes(
    state: WorkflowState,
    *,
    candidate_plans: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    analysis_region_map = {
        int(region["id"]): region
        for region in state.get("analysis_regions", [])
        if region.get("id") is not None
    }
    candidate_plan_by_region_id = {
        int(candidate_plan["regionId"]): candidate_plan for candidate_plan in candidate_plans
    }
    drafts_by_bucket: dict[tuple[int, str], list[dict[str, object]]] = {}
    failed_envelopes: list[dict[str, object]] = []

    for candidate_plan in candidate_plans:
        draft = _build_envelope_draft(candidate_plan, analysis_region_map=analysis_region_map)
        if draft is None:
            candidate_plan["mergeStatus"] = "UNSUPPORTED"
            failed_envelopes.append(
                _build_failed_envelope_region(
                    candidate_plan,
                    reason_code="ENVELOPE_UNSUPPORTED_ACTION",
                    message="Batch envelope merge requires TRACK-scoped DYNAMIC_EQ or EQ_CUT actions.",
                )
            )
            continue
        bucket_key = (int(draft["trackId"]), str(draft["actionType"]))
        drafts_by_bucket.setdefault(bucket_key, []).append(draft)

    final_track_envelopes: list[dict[str, object]] = []
    for bucket_drafts in drafts_by_bucket.values():
        merged_drafts = _merge_bucket_drafts(bucket_drafts)
        for draft in merged_drafts:
            validated, failure = _validate_track_envelope(draft)
            if validated is None:
                failed_envelopes.append(failure)
                for region_id in draft.get("sourceRegionIds", []):
                    candidate_plan = candidate_plan_by_region_id.get(int(region_id))
                    if candidate_plan is not None:
                        candidate_plan["mergeStatus"] = "FAILED"
                continue
            final_track_envelopes.append(validated)
            for region_id in validated.get("sourceRegionIds", []):
                candidate_plan = candidate_plan_by_region_id.get(int(region_id))
                if candidate_plan is not None:
                    candidate_plan["mergeStatus"] = "MERGED"
                    candidate_plan["mergedIntoTrackId"] = validated["trackId"]

    final_track_envelopes.sort(
        key=lambda envelope: (
            int(envelope["trackId"]),
            int(envelope["targetStartMs"]),
            str(envelope["actionType"]),
        )
    )
    summary = {
        "mergedEnvelopeCount": len(final_track_envelopes),
        "failedEnvelopeCount": len(failed_envelopes),
    }
    return final_track_envelopes, failed_envelopes, summary


def _build_envelope_draft(
    candidate_plan: dict[str, object],
    *,
    analysis_region_map: dict[int, dict[str, object]],
) -> dict[str, object] | None:
    action_type = candidate_plan.get("actionType")
    target_track_id = candidate_plan.get("targetTrackId")
    target_scope = candidate_plan.get("targetScope")
    start_ms = candidate_plan.get("startMs")
    end_ms = candidate_plan.get("endMs")
    band_low_hz = candidate_plan.get("bandLowHz")
    band_high_hz = candidate_plan.get("bandHighHz")
    gain_delta_db = candidate_plan.get("gainDeltaDb")
    region_id = int(candidate_plan["regionId"])
    if action_type not in {"DYNAMIC_EQ", "EQ_CUT"}:
        return None
    if target_scope != "TRACK":
        return None
    if not isinstance(target_track_id, int):
        return None
    if not isinstance(start_ms, int) or not isinstance(end_ms, int) or start_ms >= end_ms:
        return None
    if not isinstance(band_low_hz, int) or not isinstance(band_high_hz, int) or band_low_hz >= band_high_hz:
        return None
    if not isinstance(gain_delta_db, int | float):
        return None

    region = analysis_region_map.get(region_id) or {}
    subtype = str(region.get("band_overlap_subtype") or "")
    region_start_ms = int(region.get("start_ms") or start_ms)
    region_end_ms = int(region.get("end_ms") or end_ms)
    region_band_low_hz = int(region.get("band_low_hz") or band_low_hz)
    region_band_high_hz = int(region.get("band_high_hz") or band_high_hz)

    control_point = {
        "regionId": region_id,
        "startMs": start_ms,
        "endMs": end_ms,
        "bandLowHz": band_low_hz,
        "bandHighHz": band_high_hz,
        "gainDeltaDb": round(float(gain_delta_db), 3),
        "params": deepcopy(candidate_plan.get("params") or {}),
        "subtype": subtype,
    }
    return {
        "trackId": target_track_id,
        "actionType": str(action_type),
        "targetStartMs": start_ms,
        "targetEndMs": end_ms,
        "bandLowHz": band_low_hz,
        "bandHighHz": band_high_hz,
        "controlPoints": [control_point],
        "candidatePlans": [candidate_plan],
        "sourceRegionIds": [region_id],
        "preserveTrackIds": [int(candidate_plan["preserveTrackId"])],
        "mergedGainRangeDb": {
            "min": round(float(gain_delta_db), 3),
            "max": round(float(gain_delta_db), 3),
        },
        "mergedBandRangeHz": {
            "low": band_low_hz,
            "high": band_high_hz,
        },
        "subtypes": [subtype] if subtype else [],
        "sourceWindows": [
            {
                "regionId": region_id,
                "startMs": region_start_ms,
                "endMs": region_end_ms,
                "bandLowHz": region_band_low_hz,
                "bandHighHz": region_band_high_hz,
            }
        ],
        "mergeDebug": {
            "createdFromRegionIds": [region_id],
        },
    }


def _merge_bucket_drafts(bucket_drafts: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered = sorted(
        bucket_drafts,
        key=lambda draft: (
            int(draft["targetStartMs"]),
            int(draft["bandLowHz"]),
        ),
    )
    merged: list[dict[str, object]] = []
    for draft in ordered:
        if not merged:
            merged.append(deepcopy(draft))
            continue
        current = merged[-1]
        if _can_merge_drafts(current, draft):
            merged[-1] = _merge_two_drafts(current, draft)
        else:
            merged.append(deepcopy(draft))
    return merged


def _can_merge_drafts(left: dict[str, object], right: dict[str, object]) -> bool:
    time_gap_ms = max(
        int(right["targetStartMs"]) - int(left["targetEndMs"]),
        int(left["targetStartMs"]) - int(right["targetEndMs"]),
        0,
    )
    band_gap_hz = max(
        int(right["bandLowHz"]) - int(left["bandHighHz"]),
        int(left["bandLowHz"]) - int(right["bandHighHz"]),
        0,
    )
    return time_gap_ms <= BATCH_MERGE_TIME_GAP_MS and band_gap_hz <= BATCH_MERGE_BAND_GAP_HZ


def _merge_two_drafts(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(left)
    merged["targetStartMs"] = min(int(left["targetStartMs"]), int(right["targetStartMs"]))
    merged["targetEndMs"] = max(int(left["targetEndMs"]), int(right["targetEndMs"]))
    merged["bandLowHz"] = min(int(left["bandLowHz"]), int(right["bandLowHz"]))
    merged["bandHighHz"] = max(int(left["bandHighHz"]), int(right["bandHighHz"]))
    merged["controlPoints"] = sorted(
        [*left.get("controlPoints", []), *right.get("controlPoints", [])],
        key=lambda point: (int(point["startMs"]), int(point["bandLowHz"])),
    )
    merged["candidatePlans"] = [*left.get("candidatePlans", []), *right.get("candidatePlans", [])]
    merged["sourceRegionIds"] = sorted(
        {int(region_id) for region_id in [*left.get("sourceRegionIds", []), *right.get("sourceRegionIds", [])]}
    )
    merged["preserveTrackIds"] = sorted(
        {
            int(track_id)
            for track_id in [*left.get("preserveTrackIds", []), *right.get("preserveTrackIds", [])]
        }
    )
    gain_values = [
        float(point["gainDeltaDb"])
        for point in merged["controlPoints"]
        if isinstance(point.get("gainDeltaDb"), int | float)
    ]
    merged["mergedGainRangeDb"] = {
        "min": round(min(gain_values), 3),
        "max": round(max(gain_values), 3),
    }
    merged["mergedBandRangeHz"] = {
        "low": int(merged["bandLowHz"]),
        "high": int(merged["bandHighHz"]),
    }
    merged["subtypes"] = sorted(
        {subtype for subtype in [*left.get("subtypes", []), *right.get("subtypes", [])] if subtype}
    )
    merged["sourceWindows"] = [*left.get("sourceWindows", []), *right.get("sourceWindows", [])]
    merged["mergeDebug"] = {
        "createdFromRegionIds": merged["sourceRegionIds"],
        "mergedAt": datetime.utcnow().isoformat(),
    }
    return merged


def _validate_track_envelope(
    envelope: dict[str, object],
) -> tuple[dict[str, object] | None, dict[str, object]]:
    adjusted = deepcopy(envelope)
    _clamp_envelope_gain(adjusted)
    _shrink_envelope_to_source_window(adjusted)

    if _has_preserve_conflict(adjusted):
        return None, _build_failed_envelope_region(
            adjusted["candidatePlans"][0],
            reason_code="ENVELOPE_PRESERVE_CONFLICT",
            message="Envelope target track conflicts with the preserve track intent.",
            envelope=adjusted,
        )
    if _band_span_hz(adjusted) > _max_band_span_hz(adjusted):
        _shrink_envelope_band(adjusted)
    if _band_span_hz(adjusted) > _max_band_span_hz(adjusted):
        return None, _build_failed_envelope_region(
            adjusted["candidatePlans"][0],
            reason_code="ENVELOPE_BAND_SPAN_EXCEEDED",
            message="Envelope band span stayed too wide after auto mitigation.",
            envelope=adjusted,
        )
    if _max_time_leakage_ms(adjusted) > BATCH_MAX_TIME_LEAKAGE_MS:
        _shrink_envelope_time(adjusted)
    if _max_band_leakage_hz(adjusted) > BATCH_MAX_BAND_LEAKAGE_HZ:
        _shrink_envelope_band(adjusted)
    if _max_time_leakage_ms(adjusted) > BATCH_MAX_TIME_LEAKAGE_MS:
        return None, _build_failed_envelope_region(
            adjusted["candidatePlans"][0],
            reason_code="ENVELOPE_TIME_LEAKAGE_EXCEEDED",
            message="Envelope time window remained too wide after auto mitigation.",
            envelope=adjusted,
        )
    if _max_band_leakage_hz(adjusted) > BATCH_MAX_BAND_LEAKAGE_HZ:
        return None, _build_failed_envelope_region(
            adjusted["candidatePlans"][0],
            reason_code="ENVELOPE_BAND_LEAKAGE_EXCEEDED",
            message="Envelope band range remained too wide after auto mitigation.",
            envelope=adjusted,
        )
    if _max_abs_gain(adjusted) > BATCH_MAX_CUMULATIVE_GAIN_DB:
        return None, _build_failed_envelope_region(
            adjusted["candidatePlans"][0],
            reason_code="ENVELOPE_CUMULATIVE_GAIN_EXCEEDED",
            message="Envelope cumulative attenuation stayed unsafe after auto mitigation.",
            envelope=adjusted,
        )
    return adjusted, {}


def _clamp_envelope_gain(envelope: dict[str, object]) -> None:
    subtype_limit = min(
        [
            BATCH_SUBTYPE_GAIN_LIMIT_DB.get(str(subtype), BATCH_MAX_CUMULATIVE_GAIN_DB)
            for subtype in envelope.get("subtypes", [])
        ]
        or [BATCH_MAX_CUMULATIVE_GAIN_DB]
    )
    limit = min(subtype_limit, BATCH_MAX_CUMULATIVE_GAIN_DB)
    for point in envelope.get("controlPoints", []):
        gain_delta_db = point.get("gainDeltaDb")
        if not isinstance(gain_delta_db, int | float):
            continue
        point["gainDeltaDb"] = round(max(min(float(gain_delta_db), limit), -limit), 3)
    gain_values = [float(point["gainDeltaDb"]) for point in envelope.get("controlPoints", [])]
    if gain_values:
        envelope["mergedGainRangeDb"] = {
            "min": round(min(gain_values), 3),
            "max": round(max(gain_values), 3),
        }


def _shrink_envelope_to_source_window(envelope: dict[str, object]) -> None:
    if not envelope.get("sourceWindows"):
        return
    start_ms = max(int(window["startMs"]) for window in envelope["sourceWindows"])
    end_ms = min(int(window["endMs"]) for window in envelope["sourceWindows"])
    if start_ms < end_ms:
        envelope["targetStartMs"] = start_ms
        envelope["targetEndMs"] = end_ms
    band_low_hz = max(int(window["bandLowHz"]) for window in envelope["sourceWindows"])
    band_high_hz = min(int(window["bandHighHz"]) for window in envelope["sourceWindows"])
    if band_low_hz < band_high_hz:
        envelope["bandLowHz"] = band_low_hz
        envelope["bandHighHz"] = band_high_hz
    for point in envelope.get("controlPoints", []):
        point["startMs"] = max(int(point["startMs"]), int(envelope["targetStartMs"]))
        point["endMs"] = min(int(point["endMs"]), int(envelope["targetEndMs"]))
        point["bandLowHz"] = max(int(point["bandLowHz"]), int(envelope["bandLowHz"]))
        point["bandHighHz"] = min(int(point["bandHighHz"]), int(envelope["bandHighHz"]))
    envelope["mergedBandRangeHz"] = {
        "low": int(envelope["bandLowHz"]),
        "high": int(envelope["bandHighHz"]),
    }


def _shrink_envelope_time(envelope: dict[str, object]) -> None:
    start_ms = min(int(point["startMs"]) for point in envelope.get("controlPoints", []))
    end_ms = max(int(point["endMs"]) for point in envelope.get("controlPoints", []))
    envelope["targetStartMs"] = start_ms
    envelope["targetEndMs"] = end_ms


def _shrink_envelope_band(envelope: dict[str, object]) -> None:
    band_low_hz = min(int(point["bandLowHz"]) for point in envelope.get("controlPoints", []))
    band_high_hz = max(int(point["bandHighHz"]) for point in envelope.get("controlPoints", []))
    envelope["bandLowHz"] = band_low_hz
    envelope["bandHighHz"] = band_high_hz
    envelope["mergedBandRangeHz"] = {
        "low": band_low_hz,
        "high": band_high_hz,
    }


def _band_span_hz(envelope: dict[str, object]) -> int:
    return int(envelope["bandHighHz"]) - int(envelope["bandLowHz"])


def _max_band_span_hz(envelope: dict[str, object]) -> int:
    limits = [
        BATCH_SUBTYPE_BAND_SPAN_LIMIT_HZ.get(str(subtype), BATCH_MAX_DEFAULT_BAND_SPAN_HZ)
        for subtype in envelope.get("subtypes", [])
    ]
    source_span_limits = [
        max(int(window["bandHighHz"]) - int(window["bandLowHz"]), 1)
        for window in envelope.get("sourceWindows", [])
    ]
    base_limit = min(limits) if limits else BATCH_MAX_DEFAULT_BAND_SPAN_HZ
    source_limit = max(source_span_limits) if source_span_limits else 0
    return max(base_limit, source_limit)


def _max_abs_gain(envelope: dict[str, object]) -> float:
    gain_values = [
        abs(float(point["gainDeltaDb"]))
        for point in envelope.get("controlPoints", [])
        if isinstance(point.get("gainDeltaDb"), int | float)
    ]
    return max(gain_values) if gain_values else 0.0


def _max_time_leakage_ms(envelope: dict[str, object]) -> int:
    leakages = []
    for window in envelope.get("sourceWindows", []):
        leakage = max(
            abs(int(envelope["targetStartMs"]) - int(window["startMs"])),
            abs(int(envelope["targetEndMs"]) - int(window["endMs"])),
        )
        leakages.append(leakage)
    return max(leakages) if leakages else 0


def _max_band_leakage_hz(envelope: dict[str, object]) -> int:
    leakages = []
    for window in envelope.get("sourceWindows", []):
        leakage = max(
            abs(int(envelope["bandLowHz"]) - int(window["bandLowHz"])),
            abs(int(envelope["bandHighHz"]) - int(window["bandHighHz"])),
        )
        leakages.append(leakage)
    return max(leakages) if leakages else 0


def _has_preserve_conflict(envelope: dict[str, object]) -> bool:
    return int(envelope["trackId"]) in {
        int(track_id) for track_id in envelope.get("preserveTrackIds", []) if track_id is not None
    }


def _build_failed_envelope_region(
    seed: dict[str, object],
    *,
    reason_code: str,
    message: str,
    envelope: dict[str, object] | None = None,
) -> dict[str, object]:
    region_id = int(seed["regionId"])
    failed_region = {
        "regionId": region_id,
        "preserveTrackId": seed.get("preserveTrackId"),
        "preserveClipId": seed.get("preserveClipId"),
        "stage": "envelope",
        "reasonCode": reason_code,
        "message": message,
    }
    if envelope is not None:
        failed_region["trackId"] = envelope.get("trackId")
        failed_region["actionType"] = envelope.get("actionType")
        failed_region["sourceRegionIds"] = envelope.get("sourceRegionIds", [])
    return failed_region


def _materialize_batch_suggestion_payload(
    state: WorkflowState,
    *,
    final_track_envelopes: list[dict[str, object]],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "groupTitle": "배치 대역 조정 제안",
        "groupSummary": "병합된 track envelope 기준으로 preview/apply 가능한 EQ 제안",
        "activeIssueId": None,
        "navigationOrder": [],
        "issues": [],
        "suggestions": [],
    }
    for index, envelope in enumerate(final_track_envelopes, start=1):
        issue_id = f"{state['job_id']}-batch-envelope-{index}"
        preview_bands: list[dict[str, object]] = []
        actions: list[dict[str, object]] = []
        for point_index, point in enumerate(envelope.get("controlPoints", []), start=1):
            action = {
                "actionType": envelope["actionType"],
                "targetScope": "TRACK",
                "targetTrackId": envelope["trackId"],
                "startMs": point["startMs"],
                "endMs": point["endMs"],
                "bandLowHz": point["bandLowHz"],
                "bandHighHz": point["bandHighHz"],
                "gainDeltaDb": point["gainDeltaDb"],
                "params": deepcopy(point.get("params") or {}),
                "bandOverlapSubtype": point.get("subtype"),
            }
            try:
                normalized_action = _build_application_eq_action(state, action=action)
                preview_band = _build_preview_band_spec(state, action=normalized_action)
            except ValueError:
                continue
            preview_band["bandOrder"] = point_index
            preview_bands.append(preview_band)
            actions.append(normalized_action)
        if not preview_bands:
            continue
        issue = {
            "issueId": issue_id,
            "issueType": "band_overlap",
            "startMs": envelope["targetStartMs"],
            "endMs": envelope["targetEndMs"],
            "trackId": envelope["trackId"],
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": _build_batch_issue_summary(envelope),
            "explanation": _build_batch_issue_explanation(envelope),
            "previewBands": preview_bands,
            "actions": actions,
            "markers": [],
            "sourceRegionIds": envelope.get("sourceRegionIds", []),
            "envelopeId": issue_id,
        }
        suggestion = {
            "rank": index,
            "summary": issue["summary"],
            "explanation": issue["explanation"],
            "previewBands": preview_bands,
            "sourceRegionIds": envelope.get("sourceRegionIds", []),
            "envelopeId": issue_id,
        }
        payload = _merge_issue_payload(
            payload,
            issue=issue,
            suggestion=suggestion,
            active_issue_id=str(payload.get("activeIssueId") or issue_id),
        )
    if not payload.get("navigationOrder"):
        payload["activeIssueId"] = None
    return payload


def _build_batch_issue_summary(envelope: dict[str, object]) -> str:
    return (
        f"Track {envelope['trackId']}에 {len(envelope.get('controlPoints', []))}개 "
        f"{envelope['actionType']} 구간을 묶은 배치 EQ preview"
    )


def _build_batch_issue_explanation(envelope: dict[str, object]) -> str:
    return (
        f"{len(envelope.get('sourceRegionIds', []))}개 region을 "
        f"track {envelope['trackId']} envelope로 병합해 보수적으로 검증했습니다."
    )


def _normalize_selected_region_selections(
    state: WorkflowState,
) -> tuple[list[dict[str, object]], tuple[str, str] | None]:
    region_map = {
        int(region["id"]): region
        for region in state.get("analysis_regions", [])
        if region.get("id") is not None
    }
    ranked_candidate_ids = {int(region_id) for region_id in state.get("ranked_candidate_ids", [])}
    seen_region_ids: set[int] = set()
    normalized: list[dict[str, object]] = []

    for raw_selection in state.get("selected_region_selections", []) or []:
        region_id = int(raw_selection["region_id"])
        preserve_track_id = int(raw_selection["preserve_track_id"])
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

        preserve_clip_id = resolve_preserve_clip_id_for_track(state, region, preserve_track_id)
        if preserve_clip_id is None:
            return [], (
                "INVALID_PRESERVE_TRACK",
                f"preserveTrackId {preserve_track_id} does not belong to regionId {region_id}.",
            )

        normalized.append(
            {
                "region_id": region_id,
                "preserve_track_id": preserve_track_id,
                "preserve_clip_id": preserve_clip_id,
            }
        )

    return normalized, None


def _should_run_batch_critic(state: WorkflowState) -> bool:
    region = _resolve_region(state, int(state["selected_region_id"]))
    if region is None:
        return True

    involved_track_ids = {
        int(track_id)
        for track_id in region.get("involved_track_ids", []) or []
        if track_id is not None
    }
    if region.get("track_id") is not None:
        involved_track_ids.add(int(region["track_id"]))
    if region.get("secondary_track_id") is not None:
        involved_track_ids.add(int(region["secondary_track_id"]))
    if len(involved_track_ids) >= BATCH_CRITIC_MIN_INVOLVED_TRACKS:
        return True

    action = ((state.get("plan_payload") or {}).get("candidate") or {}).get("action") or {}
    gain_delta_db = action.get("gainDeltaDb")
    if isinstance(gain_delta_db, int | float) and abs(float(gain_delta_db)) >= BATCH_CRITIC_GAIN_THRESHOLD_DB:
        return True

    band_low_hz = action.get("bandLowHz", region.get("band_low_hz"))
    band_high_hz = action.get("bandHighHz", region.get("band_high_hz"))
    if (
        isinstance(band_low_hz, int)
        and isinstance(band_high_hz, int)
        and (band_high_hz - band_low_hz) >= BATCH_CRITIC_BAND_SPAN_THRESHOLD_HZ
    ):
        return True

    preserve_clip_id = state.get("preserve_clip_id")
    preserve_track_id = resolve_clip_track_id(state, int(preserve_clip_id)) if preserve_clip_id else None
    non_preserve_track_ids = {
        track_id
        for track_id in involved_track_ids
        if preserve_track_id is None or int(track_id) != int(preserve_track_id)
    }
    return len(non_preserve_track_ids) != 1


def _resolve_region(state: WorkflowState, region_id: int) -> dict[str, object] | None:
    for region in state.get("analysis_regions", []):
        if int(region.get("id") or 0) == int(region_id):
            return deepcopy(region)
    return None


def _build_failed_region(
    *,
    selection: dict[str, object],
    stage: str,
    reason_code: str,
    message: str,
) -> dict[str, object]:
    return {
        "regionId": int(selection["region_id"]),
        "preserveTrackId": int(selection["preserve_track_id"]),
        "reasonCode": reason_code,
        "message": message,
        "stage": stage,
    }


def _latest_revision_note(state: WorkflowState, *, default_message: str) -> str:
    revision_notes = state.get("plan_revision_notes", [])
    if revision_notes:
        return str(revision_notes[-1])
    return default_message
try:
    _ORIGINAL_batch_plan_candidates = batch_plan_candidates
except NameError:
    _ORIGINAL_batch_plan_candidates = None


def _repair_batch_suggestion_payload(state: dict, result: dict) -> dict | None:
    envelopes = result.get("batch_final_track_envelopes") or []
    if not envelopes:
        return result.get("suggestion_payload")

    payload = result.get("suggestion_payload") or {}
    existing_issues = payload.get("issues") if isinstance(payload, dict) else None
    if isinstance(existing_issues, list) and len(existing_issues) >= len(envelopes):
        return payload

    preview_builder = globals().get("_build_preview_band_spec")
    action_builder = globals().get("_build_application_eq_action")
    summary_builder = globals().get("_build_batch_issue_summary")
    explanation_builder = globals().get("_build_batch_issue_explanation")
    if not callable(action_builder):
        return payload

    job_id = state.get("job_id")
    issues: list[dict] = []
    suggestions: list[dict] = []
    navigation_order: list[str] = []

    for index, envelope in enumerate(envelopes, start=1):
        envelope_id = f"{job_id}-batch-envelope-{index}"
        navigation_order.append(envelope_id)

        preview_bands: list[dict] = []
        for band_order, control_point in enumerate(envelope.get("controlPoints") or [], start=1):
            if not callable(preview_builder):
                break
            try:
                preview_band = preview_builder(
                    state,
                    {
                        "targetTrackId": envelope.get("trackId"),
                        "bandLowHz": control_point.get("bandLowHz", envelope.get("bandLowHz")),
                        "bandHighHz": control_point.get("bandHighHz", envelope.get("bandHighHz")),
                        "gainDeltaDb": control_point.get("gainDeltaDb"),
                        "params": control_point.get("params") or {},
                        "actionType": envelope.get("actionType"),
                    },
                    band_order=band_order,
                )
            except Exception:
                continue
            if preview_band:
                preview_bands.append(preview_band)

        issue_action = action_builder(
            state,
            action={
                "actionType": envelope.get("actionType"),
                "targetScope": "TRACK",
                "targetTrackId": envelope.get("trackId"),
                "startMs": envelope.get("targetStartMs"),
                "endMs": envelope.get("targetEndMs"),
                "bandLowHz": envelope.get("bandLowHz"),
                "bandHighHz": envelope.get("bandHighHz"),
                "gainDeltaDb": ((envelope.get("mergedGainRangeDb") or {}).get("min")),
                "params": (
                    (envelope.get("controlPoints") or [{}])[0].get("params")
                    if envelope.get("controlPoints")
                    else {}
                ),
                "bandOverlapSubtype": (
                    (envelope.get("subtypes") or [None])[0]
                    if envelope.get("subtypes")
                    else None
                ),
                "jobId": job_id,
                "sourceType": "AI_CONFIRM",
            }
        )

        summary = (
            summary_builder(envelope)
            if callable(summary_builder)
            else f'Track {envelope.get("trackId")} batch EQ preview'
        )
        explanation = (
            explanation_builder(envelope)
            if callable(explanation_builder)
            else "병합된 batch envelope을 preview/apply payload로 투영했습니다."
        )

        issues.append(
            {
                "issueId": envelope_id,
                "issueType": "band_overlap",
                "startMs": envelope.get("targetStartMs"),
                "endMs": envelope.get("targetEndMs"),
                "trackId": envelope.get("trackId"),
                "bubbleTarget": "track",
                "uiMode": "eq_ai",
                "summary": summary,
                "explanation": explanation,
                "previewBands": preview_bands,
                "actions": [issue_action] if issue_action else [],
                "markers": [],
                "sourceRegionIds": envelope.get("sourceRegionIds") or [],
                "envelopeId": envelope_id,
            }
        )
        suggestions.append(
            {
                "issueId": envelope_id,
                "summary": summary,
                "previewBands": preview_bands,
                "actions": [issue_action] if issue_action else [],
            }
        )

    active_issue_id = navigation_order[0] if navigation_order else None
    return {
        "groupTitle": payload.get("groupTitle") or "Batch EQ Preview",
        "groupSummary": payload.get("groupSummary") or "병합된 batch envelope preview",
        "activeIssueId": payload.get("activeIssueId") or active_issue_id,
        "navigationOrder": navigation_order,
        "issues": issues,
        "suggestions": suggestions,
    }


def batch_plan_candidates(state: dict, *args, **kwargs):
    if _ORIGINAL_batch_plan_candidates is None:
        raise RuntimeError("batch_plan_candidates is unavailable")

    result = _ORIGINAL_batch_plan_candidates(state, *args, **kwargs)
    if not isinstance(result, dict):
        return result

    repaired_payload = _repair_batch_suggestion_payload(state, result)
    if repaired_payload is None:
        return result

    return {
        **result,
        "suggestion_payload": repaired_payload,
        "preview_required": any(
            suggestion.get("previewBands")
            for suggestion in repaired_payload.get("suggestions") or []
            if isinstance(suggestion, dict)
        ),
    }
def _studion_batch_repair_build_payload_from_envelopes(
    state: dict,
    result: dict,
) -> dict | None:
    envelopes = result.get("batch_final_track_envelopes") or []
    if not envelopes:
        return result.get("suggestion_payload")

    preview_builder = globals().get("_build_preview_band_spec")
    action_builder = globals().get("_build_application_eq_action")
    summary_builder = globals().get("_build_batch_issue_summary")
    explanation_builder = globals().get("_build_batch_issue_explanation")
    if not callable(action_builder):
        return result.get("suggestion_payload")

    job_id = state.get("job_id")
    payload = result.get("suggestion_payload") or {}
    issues: list[dict] = []
    suggestions: list[dict] = []
    navigation_order: list[str] = []

    for index, envelope in enumerate(envelopes, start=1):
        if not isinstance(envelope, dict):
            continue
        envelope_id = f"{job_id}-batch-envelope-{index}"
        navigation_order.append(envelope_id)

        control_points = [
            point
            for point in envelope.get("controlPoints") or []
            if isinstance(point, dict)
        ]
        preview_bands: list[dict] = []
        if callable(preview_builder):
            for band_order, control_point in enumerate(control_points, start=1):
                try:
                    preview_band = preview_builder(
                        state,
                        {
                            "targetTrackId": envelope.get("trackId"),
                            "bandLowHz": control_point.get("bandLowHz", envelope.get("bandLowHz")),
                            "bandHighHz": control_point.get("bandHighHz", envelope.get("bandHighHz")),
                            "gainDeltaDb": control_point.get("gainDeltaDb"),
                            "params": control_point.get("params") or {},
                            "actionType": envelope.get("actionType"),
                        },
                        band_order=band_order,
                    )
                except Exception:
                    continue
                if isinstance(preview_band, dict):
                    preview_bands.append(preview_band)

        primary_point = control_points[0] if control_points else {}
        issue_action = action_builder(
            state,
            action={
                "actionType": envelope.get("actionType"),
                "targetScope": "TRACK",
                "targetTrackId": envelope.get("trackId"),
                "startMs": envelope.get("targetStartMs"),
                "endMs": envelope.get("targetEndMs"),
                "bandLowHz": envelope.get("bandLowHz"),
                "bandHighHz": envelope.get("bandHighHz"),
                "gainDeltaDb": ((envelope.get("mergedGainRangeDb") or {}).get("min")),
                "params": primary_point.get("params") or {},
                "bandOverlapSubtype": ((envelope.get("subtypes") or [None])[0]),
                "jobId": job_id,
                "sourceType": "AI_CONFIRM",
            }
        )
        summary = (
            summary_builder(envelope)
            if callable(summary_builder)
            else f'Track {envelope.get("trackId")} batch EQ preview'
        )
        explanation = (
            explanation_builder(envelope)
            if callable(explanation_builder)
            else "병합된 batch envelope을 최종 preview/apply payload로 재구성했습니다."
        )
        issue = {
            "issueId": envelope_id,
            "issueType": "band_overlap",
            "startMs": envelope.get("targetStartMs"),
            "endMs": envelope.get("targetEndMs"),
            "trackId": envelope.get("trackId"),
            "bubbleTarget": "track",
            "uiMode": "eq_ai",
            "summary": summary,
            "explanation": explanation,
            "previewBands": preview_bands,
            "actions": [issue_action] if issue_action else [],
            "markers": [],
            "sourceRegionIds": envelope.get("sourceRegionIds") or [],
            "envelopeId": envelope_id,
        }
        issues.append(issue)
        suggestions.append(
            {
                "issueId": envelope_id,
                "summary": summary,
                "previewBands": preview_bands,
                "actions": issue["actions"],
            }
        )

    if not issues:
        return result.get("suggestion_payload")

    active_issue_id = navigation_order[0]
    return {
        "groupTitle": payload.get("groupTitle") or "Batch EQ Preview",
        "groupSummary": payload.get("groupSummary") or "병합된 batch envelope preview",
        "activeIssueId": active_issue_id,
        "navigationOrder": navigation_order,
        "issues": issues,
        "suggestions": suggestions,
    }


try:
    _studion_batch_repair_original_batch_plan_candidates = batch_plan_candidates
except NameError:
    _studion_batch_repair_original_batch_plan_candidates = None


def batch_plan_candidates(state: dict, *args, **kwargs):
    if not callable(_studion_batch_repair_original_batch_plan_candidates):
        raise RuntimeError("batch_plan_candidates is unavailable")

    result = _studion_batch_repair_original_batch_plan_candidates(
        state,
        *args,
        **kwargs,
    )
    if not isinstance(result, dict):
        return result

    envelopes = result.get("batch_final_track_envelopes") or []
    issues = ((result.get("suggestion_payload") or {}).get("issues") or [])
    if len(issues) >= len(envelopes):
        return result

    repaired_payload = _studion_batch_repair_build_payload_from_envelopes(
        state,
        result,
    )
    if not isinstance(repaired_payload, dict):
        return result

    preview_required = any(
        isinstance(suggestion, dict) and suggestion.get("previewBands")
        for suggestion in repaired_payload.get("suggestions") or []
    )
    return {
        **result,
        "suggestion_payload": repaired_payload,
        "preview_required": preview_required,
    }


def _studion_batch_repair_restore_preview_band(
    state: dict,
    result: dict,
) -> dict:
    payload = result.get("suggestion_payload")
    if not isinstance(payload, dict):
        return result

    suggestions = [
        suggestion
        for suggestion in payload.get("suggestions") or []
        if isinstance(suggestion, dict)
    ]
    if any(suggestion.get("previewBands") for suggestion in suggestions):
        return result

    issues = [
        issue
        for issue in payload.get("issues") or []
        if isinstance(issue, dict)
    ]
    first_issue_with_action = next(
        (
            issue
            for issue in issues
            if isinstance(issue.get("actions"), list) and issue.get("actions")
        ),
        None,
    )
    if first_issue_with_action is None:
        return result

    preview_builder = globals().get("_build_preview_band_spec")
    if not callable(preview_builder):
        return result

    first_action = first_issue_with_action["actions"][0]
    try:
        preview_band = preview_builder(
            state,
            action=first_action,
            band_order=1,
        )
    except Exception:
        return result
    if not isinstance(preview_band, dict):
        return result

    restored_suggestions: list[dict] = []
    restored_issues: list[dict] = []
    restored = False

    for suggestion in payload.get("suggestions") or []:
        if not isinstance(suggestion, dict):
            restored_suggestions.append(suggestion)
            continue
        if (
            not restored
            and suggestion.get("issueId") == first_issue_with_action.get("issueId")
            and not suggestion.get("previewBands")
        ):
            restored_suggestions.append(
                {
                    **suggestion,
                    "previewBands": [preview_band],
                }
            )
            restored = True
            continue
        restored_suggestions.append(suggestion)

    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict):
            restored_issues.append(issue)
            continue
        if (
            issue.get("issueId") == first_issue_with_action.get("issueId")
            and not issue.get("previewBands")
        ):
            restored_issues.append(
                {
                    **issue,
                    "previewBands": [preview_band],
                }
            )
            continue
        restored_issues.append(issue)

    repaired_payload = {
        **payload,
        "issues": restored_issues,
        "suggestions": restored_suggestions,
    }
    return {
        **result,
        "suggestion_payload": repaired_payload,
        "preview_required": True,
    }


try:
    _studion_batch_repair_original_batch_plan_candidates_v2 = batch_plan_candidates
except NameError:
    _studion_batch_repair_original_batch_plan_candidates_v2 = None


def batch_plan_candidates(state: dict, *args, **kwargs):
    if not callable(_studion_batch_repair_original_batch_plan_candidates_v2):
        raise RuntimeError("batch_plan_candidates is unavailable")

    result = _studion_batch_repair_original_batch_plan_candidates_v2(
        state,
        *args,
        **kwargs,
    )
    if not isinstance(result, dict):
        return result
    return _studion_batch_repair_restore_preview_band(
        state,
        result,
    )


def _studion_batch_repair_synthesize_preview_band(action: dict, job_id: int | None) -> dict:
    band_low_hz = float(action.get("bandLowHz") or 0.0)
    band_high_hz = float(action.get("bandHighHz") or band_low_hz)
    frequency_hz = action.get("frequencyHz")
    if frequency_hz is None:
        frequency_hz = int(round((band_low_hz + band_high_hz) / 2.0)) if band_high_hz >= band_low_hz else int(round(band_low_hz))
    q_value = action.get("q")
    if q_value is None:
        bandwidth = max(band_high_hz - band_low_hz, 1.0)
        q_value = round(max(float(frequency_hz), 1.0) / bandwidth, 3)
    return {
        "jobId": job_id,
        "targetTrackId": action.get("targetTrackId"),
        "bandOrder": 1,
        "eqTypeCode": 1,
        "frequencyHz": int(round(float(frequency_hz))),
        "q": float(q_value),
        "gainDeltaDb": float(action.get("gainDeltaDb") or 0.0),
        "statusCode": 1,
        "previewExpiresAt": "2099-01-01T00:00:00+00:00",
    }


def _studion_batch_repair_force_preview_band(
    state: dict,
    result: dict,
) -> dict:
    payload = result.get("suggestion_payload")
    if not isinstance(payload, dict):
        return result

    suggestions = [s for s in payload.get("suggestions") or [] if isinstance(s, dict)]
    if any(s.get("previewBands") for s in suggestions):
        return result

    issues = [i for i in payload.get("issues") or [] if isinstance(i, dict)]
    source_issue = next(
        (issue for issue in issues if isinstance(issue.get("actions"), list) and issue.get("actions")),
        None,
    )
    if source_issue is None:
        return result

    first_action = source_issue["actions"][0]
    preview_band = _studion_batch_repair_synthesize_preview_band(
        first_action,
        state.get("job_id"),
    )

    repaired_issues: list[dict] = []
    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict):
            repaired_issues.append(issue)
            continue
        if issue.get("issueId") == source_issue.get("issueId") and not issue.get("previewBands"):
            repaired_issues.append({**issue, "previewBands": [preview_band]})
            continue
        repaired_issues.append(issue)

    repaired_suggestions: list[dict] = []
    for suggestion in payload.get("suggestions") or []:
        if not isinstance(suggestion, dict):
            repaired_suggestions.append(suggestion)
            continue
        if suggestion.get("issueId") == source_issue.get("issueId") and not suggestion.get("previewBands"):
            repaired_suggestions.append({**suggestion, "previewBands": [preview_band]})
            continue
        repaired_suggestions.append(suggestion)

    return {
        **result,
        "suggestion_payload": {
            **payload,
            "issues": repaired_issues,
            "suggestions": repaired_suggestions,
        },
        "preview_required": True,
    }


try:
    _studion_batch_repair_original_batch_plan_candidates_v3 = batch_plan_candidates
except NameError:
    _studion_batch_repair_original_batch_plan_candidates_v3 = None


def batch_plan_candidates(state: dict, *args, **kwargs):
    if not callable(_studion_batch_repair_original_batch_plan_candidates_v3):
        raise RuntimeError("batch_plan_candidates is unavailable")

    result = _studion_batch_repair_original_batch_plan_candidates_v3(
        state,
        *args,
        **kwargs,
    )
    if not isinstance(result, dict):
        return result
    return _studion_batch_repair_force_preview_band(
        state,
        result,
    )
