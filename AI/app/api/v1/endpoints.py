from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.graph.state import ApplyState, RuntimeState, WorkflowState, WorkflowUserDecision
from app.graph.workflow import (
    build_apply_graph,
    build_apply_response,
    build_runtime_graph,
    build_runtime_response,
    build_workflow_graph,
    build_workflow_response,
    run_apply_graph,
    run_runtime_graph,
    run_workflow_graph,
)
from app.persistence.projections import (
    ApplyGraphProjections,
    RuntimeGraphProjections,
    WorkflowGraphProjections,
)
from app.services.workflow_orchestration import (
    WorkflowDispatchAccepted,
    WorkflowResumePayload,
    WorkflowStartPayload,
    get_workflow_inspection_report,
    get_workflow_job_status,
    get_workflow_preview_compare,
    resume_workflow_job,
    start_workflow_job,
)
from app.services.workflow_snapshots import ProjectSnapshot

router = APIRouter()


class WorkflowRunRequest(BaseModel):
    job_id: int
    project_id: int
    track_ids: list[int] = Field(default_factory=list)
    project_snapshot: ProjectSnapshot | None = None
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
    selected_region_id: int | None = None
    preserve_clip_id: int | None = None
    user_feedback_message: str | None = None


class RuntimeRunRequest(BaseModel):
    job_id: int
    project_id: int
    track_ids: list[int] = Field(default_factory=list)
    project_snapshot: ProjectSnapshot | None = None
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


class ApplyRunRequest(BaseModel):
    job_id: int
    project_id: int
    preview_id: str
    suggestion_group_id: str


class WorkflowRunResponse(BaseModel):
    graph_state: WorkflowState
    projections: WorkflowGraphProjections


class WorkflowDispatchResponse(BaseModel):
    job: WorkflowDispatchAccepted


class WorkflowFeedbackRequest(BaseModel):
    project_id: int
    issue_id: str | None = None
    action_type: str | None = None
    action_payload: dict[str, Any] | None = None
    selected_region_id: int | None = None
    preserve_clip_id: int | None = None
    user_feedback_message: str | None = None
    user_decision: WorkflowUserDecision
    requested_by: int | None = None


class WorkflowJobView(BaseModel):
    id: int
    project_id: int
    status: str
    phase: str
    current_node: str | None = None
    progress: int = 0
    timeline_snapshot_id: str | None = None
    requested_by: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class WorkflowJobStatusResponse(BaseModel):
    job: WorkflowJobView
    projections: WorkflowGraphProjections


class RuntimeRunResponse(BaseModel):
    graph_state: RuntimeState
    projections: RuntimeGraphProjections


class ApplyRunResponse(BaseModel):
    graph_state: ApplyState
    projections: ApplyGraphProjections


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/graph/workflow")
def workflow_graph_summary() -> dict[str, Any]:
    return {
        "graph": "workflow",
        "entrypoint": "load_entry_context",
        "terminal_nodes": [
            "wait_user_plan_input",
            "finalize_output",
            "fail_workflow",
        ],
        "compiled": build_workflow_graph().name,
    }


@router.get("/graph/runtime")
def runtime_graph_summary() -> dict[str, Any]:
    return {
        "graph": "runtime",
        "delegates_to": "workflow",
        "compiled": build_runtime_graph().name,
    }


@router.get("/graph/apply")
def apply_graph_summary() -> dict[str, Any]:
    return {
        "graph": "apply",
        "delegates_to": "workflow",
        "compiled": build_apply_graph().name,
    }


@router.post("/graph/workflow/run")
def workflow_graph_run(request: WorkflowRunRequest) -> WorkflowRunResponse:
    state = run_workflow_graph(request.model_dump())
    return WorkflowRunResponse.model_validate(build_workflow_response(state))


@router.post("/internal/workflow/jobs/start")
def workflow_job_start(request: WorkflowStartPayload) -> WorkflowDispatchResponse:
    return WorkflowDispatchResponse(job=start_workflow_job(request))


@router.post("/internal/workflow/jobs/resume")
def workflow_job_resume(request: WorkflowResumePayload) -> WorkflowDispatchResponse:
    return WorkflowDispatchResponse(job=resume_workflow_job(request))


@router.post("/internal/workflow/jobs/{job_id}/feedback")
def workflow_job_feedback(
    job_id: int,
    request: WorkflowFeedbackRequest,
) -> WorkflowDispatchResponse:
    return WorkflowDispatchResponse(
        job=resume_workflow_job(
            WorkflowResumePayload(
                job_id=job_id,
                project_id=request.project_id,
                issue_id=request.issue_id,
                action_type=request.action_type,
                action_payload=request.action_payload,
                selected_region_id=request.selected_region_id,
                preserve_clip_id=request.preserve_clip_id,
                user_feedback_message=request.user_feedback_message,
                user_decision=request.user_decision,
                requested_by=request.requested_by,
            )
        )
    )


@router.get("/internal/workflow/jobs/{job_id}")
def workflow_job_status(job_id: int) -> WorkflowJobStatusResponse:
    return WorkflowJobStatusResponse.model_validate(get_workflow_job_status(job_id))


@router.get("/internal/workflow/jobs/{job_id}/preview-compare")
def workflow_job_preview_compare(job_id: int, mode: str = "preview") -> dict[str, Any]:
    return get_workflow_preview_compare(job_id, mode=mode)


@router.get("/internal/workflow/jobs/{job_id}/inspection-report")
def workflow_job_inspection_report(job_id: int) -> dict[str, Any]:
    return get_workflow_inspection_report(job_id)


@router.post("/graph/runtime/run")
def runtime_graph_run(request: RuntimeRunRequest) -> RuntimeRunResponse:
    state = run_runtime_graph(request.model_dump())
    return RuntimeRunResponse.model_validate(build_runtime_response(state))


@router.post("/graph/apply/run")
def apply_graph_run(request: ApplyRunRequest) -> ApplyRunResponse:
    state: ApplyState = {
        "job_id": request.job_id,
        "project_id": request.project_id,
        "preview_id": request.preview_id,
        "suggestion_group_id": request.suggestion_group_id,
    }
    result = run_apply_graph(state)
    return ApplyRunResponse.model_validate(build_apply_response(result))
