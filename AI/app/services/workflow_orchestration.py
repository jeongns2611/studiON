from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.graph.state import (
    WorkflowDispatchType,
    WorkflowUserDecision,
    build_workflow_initial_state,
    utc_now,
)
from app.services.workflow_jobs import (
    WorkflowDispatchMessage,
    WorkflowRegionSelection,
    get_workflow_job_store,
)
from app.services.workflow_inspection_report import build_workflow_inspection_report
from app.services.workflow_preview_compare import build_preview_compare_payload
from app.services.workflow_queue import enqueue_workflow_dispatch
from app.services.workflow_snapshots import (
    ProjectSnapshot,
    build_snapshot_id,
    build_timeline_snapshot_document,
    get_workflow_snapshot_store,
)

logger = logging.getLogger(__name__)


class WorkflowDispatchAccepted(BaseModel):
    job_id: int
    project_id: int
    dispatch_type: str
    status: str = "accepted"
    queue_name: str = "workflow"


class WorkflowStartPayload(BaseModel):
    job_id: int
    project_id: int
    project_snapshot: ProjectSnapshot
    issue_types: list[str] = Field(
        default_factory=lambda: [
            "band_overlap",
            "track_clipping",
            "master_clipping",
            "sibilance",
            "high_band_harshness",
        ]
    )
    validator_mode: str = "PASS"
    critic_mode: str = "PASS"
    requested_by: int | None = None


class WorkflowResumePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: int
    project_id: int
    selected_region_id: int | None = None
    preserve_clip_id: int | None = None
    region_selections: list[WorkflowRegionSelection] = Field(
        default_factory=list,
        alias="regionSelections",
    )
    issue_id: str | None = None
    action_type: str | None = None
    action_payload: dict[str, object] | None = None
    user_feedback_message: str | None = None
    user_prompt: str | None = Field(default=None, alias="userPrompt")
    user_decision: WorkflowUserDecision = "RESUME"
    requested_by: int | None = None


def start_workflow_job(payload: WorkflowStartPayload) -> WorkflowDispatchAccepted:
    store = get_workflow_job_store()
    snapshot_store = get_workflow_snapshot_store()
    timeline_snapshot_id = build_snapshot_id(payload.job_id)
    snapshot_document = build_timeline_snapshot_document(
        job_id=payload.job_id,
        project_id=payload.project_id,
        snapshot_id=timeline_snapshot_id,
        snapshot=payload.project_snapshot,
    )
    snapshot_store.upsert_snapshot(snapshot_document)
    initial_state = build_workflow_initial_state(
        job_id=payload.job_id,
        project_id=payload.project_id,
        timeline_snapshot_id=timeline_snapshot_id,
        project_duration_ms=snapshot_document.duration_ms,
        track_ids=snapshot_document.track_ids,
        track_name_map={
            int(track_id): track_name
            for track_id, track_name in snapshot_document.track_name_map.items()
        },
        bpm=snapshot_document.bpm,
        numerator=snapshot_document.numerator,
        denominator=snapshot_document.denominator,
        bar_mapping=snapshot_document.bar_mapping,
        clip_index=snapshot_document.clip_index,
        track_eq_map={
            int(track_id): bands
            for track_id, bands in snapshot_document.track_eq_map.items()
        },
        issue_types=payload.issue_types,
        validator_mode=payload.validator_mode,
        critic_mode=payload.critic_mode,
        requested_by=payload.requested_by,
    )
    try:
        store.create_pending_job(initial_state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    message = WorkflowDispatchMessage(
        job_id=payload.job_id,
        project_id=payload.project_id,
        dispatch_type="start",
        requested_by=payload.requested_by,
    )
    logger.info(
        "workflow dispatch queued | job_id=%s dispatch_type=%s queue=%s",
        payload.job_id,
        message.dispatch_type,
        "workflow",
    )
    enqueue_workflow_dispatch(message)
    return WorkflowDispatchAccepted(
        job_id=payload.job_id,
        project_id=payload.project_id,
        dispatch_type=message.dispatch_type,
    )


def resume_workflow_job(payload: WorkflowResumePayload) -> WorkflowDispatchAccepted:
    if payload.user_decision in {"CONFIRM", "CANCEL"}:
        return record_workflow_feedback(payload)

    store = get_workflow_job_store()
    job = store.get_job(payload.job_id)
    if job is None or job.project_id != payload.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow job was not found.",
        )
    if job.status == "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow job is already running.",
        )

    dispatch_type = _dispatch_type_for_phase(job.phase)
    _validate_resume_inputs(dispatch_type, payload.model_dump(mode="python"))
    effective_feedback_message = payload.user_feedback_message or payload.user_prompt

    message = WorkflowDispatchMessage(
        job_id=payload.job_id,
        project_id=payload.project_id,
        dispatch_type=dispatch_type,
        requested_by=payload.requested_by,
        request_mode="batch" if len(payload.region_selections) > 1 else None,
        selected_region_id=payload.selected_region_id,
        preserve_clip_id=payload.preserve_clip_id,
        selected_region_selections=payload.region_selections,
        issue_id=payload.issue_id,
        action_type=payload.action_type,
        action_payload=payload.action_payload,
        user_feedback_message=effective_feedback_message,
        user_decision=payload.user_decision,
    )
    logger.info(
        "workflow dispatch resumed | job_id=%s dispatch_type=%s queue=%s",
        payload.job_id,
        dispatch_type,
        "workflow",
    )
    enqueue_workflow_dispatch(message)
    return WorkflowDispatchAccepted(
        job_id=payload.job_id,
        project_id=payload.project_id,
        dispatch_type=dispatch_type,
    )


def record_workflow_feedback(payload: WorkflowResumePayload) -> WorkflowDispatchAccepted:
    store = get_workflow_job_store()
    job = store.get_job(payload.job_id)
    if job is None or job.project_id != payload.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow job was not found.",
        )

    restored_state = _build_restored_job_state(job)
    notes = [*restored_state.get("notes", [])]
    notes.append(
        f"User decision recorded: {payload.user_decision}"
        + (
            f" ({payload.user_feedback_message})"
            if payload.user_feedback_message
            else ""
        )
    )
    restored_state.update(
        {
            "selected_region_id": payload.selected_region_id
            if payload.selected_region_id is not None
            else restored_state.get("selected_region_id"),
            "preserve_clip_id": payload.preserve_clip_id
            if payload.preserve_clip_id is not None
            else restored_state.get("preserve_clip_id"),
            "issue_id": payload.issue_id
            if payload.issue_id is not None
            else restored_state.get("issue_id"),
            "action_type": payload.action_type
            if payload.action_type is not None
            else restored_state.get("action_type"),
            "action_payload": payload.action_payload
            if payload.action_payload is not None
            else restored_state.get("action_payload"),
            "user_feedback_message": payload.user_feedback_message,
            "user_decision": payload.user_decision,
            "user_feedback_recorded_at": utc_now(),
            "notes": notes,
        }
    )
    store.save_graph_state(restored_state)
    logger.info(
        "workflow feedback recorded | job_id=%s decision=%s",
        payload.job_id,
        payload.user_decision,
    )
    return WorkflowDispatchAccepted(
        job_id=payload.job_id,
        project_id=payload.project_id,
        dispatch_type=payload.user_decision.lower(),
    )


def get_workflow_job_status(job_id: int) -> dict[str, object]:
    from app.persistence.projections import build_workflow_projections

    store = get_workflow_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow job was not found.",
        )

    state = _build_restored_job_state(job)
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
        "projections": build_workflow_projections(state).model_dump(mode="json"),
    }


def get_workflow_preview_compare(job_id: int, *, mode: str = "preview") -> dict[str, object]:
    store = get_workflow_job_store()
    snapshot_store = get_workflow_snapshot_store()
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
    return build_preview_compare_payload(state, snapshot, mode=mode)


def get_workflow_inspection_report(job_id: int) -> dict[str, object]:
    return build_workflow_inspection_report(job_id)


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


def _dispatch_type_for_phase(phase: str) -> WorkflowDispatchType:
    if phase == "waiting_for_user_plan_input":
        return "resume_plan_input"
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Workflow job cannot be resumed from phase '{phase}'.",
    )


def _validate_resume_inputs(dispatch_type: WorkflowDispatchType, payload: dict[str, Any]) -> None:
    if dispatch_type == "resume_plan_input" and payload.get("selected_region_id") is None:
        region_selections = payload.get("region_selections") or []
        if region_selections:
            _validate_batch_resume_inputs(region_selections, payload)
            return
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="selected_region_id is required for plan-input resume.",
        )
    if dispatch_type == "resume_plan_input" and payload.get("preserve_clip_id") is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="preserve_clip_id is required for plan-input resume.",
        )


def _validate_batch_resume_inputs(
    region_selections: list[dict[str, Any]],
    payload: dict[str, Any],
) -> None:
    seen_region_ids: set[int] = set()
    for selection in region_selections:
        region_id = int(selection["region_id"])
        preserve_track_id = int(selection["preserve_track_id"])
        if region_id in seen_region_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="regionSelections must not contain duplicate regionId values.",
            )
        seen_region_ids.add(region_id)
        if preserve_track_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="regionSelections.preserveTrackId must be a positive integer.",
            )
    if len(region_selections) > 1 and not str(
        payload.get("user_prompt") or payload.get("user_feedback_message") or ""
    ).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="userPrompt is required for batch plan-input resume.",
        )
