from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from json import dumps, loads
from threading import RLock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from app.core.config import get_settings
from app.graph.state import WorkflowDispatchType, WorkflowState, WorkflowUserDecision
from app.services.workflow_artifacts import (
    WorkflowArtifactDocument,
    get_workflow_artifact_store,
)


# API와 worker 사이에는 최소 dispatch payload만 넘기고,
# 재개에 필요한 큰 상태는 MySQL row + Mongo artifact 조합으로 복원한다.
class WorkflowRegionSelection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    region_id: int = Field(alias="regionId")
    preserve_track_id: int = Field(alias="preserveTrackId")
    preserve_clip_id: int | None = None


class WorkflowDispatchMessage(BaseModel):
    job_id: int
    project_id: int
    dispatch_type: WorkflowDispatchType
    requested_by: int | None = None
    request_mode: str | None = None
    selected_region_id: int | None = None
    preserve_clip_id: int | None = None
    selected_region_selections: list[WorkflowRegionSelection] = Field(default_factory=list)
    issue_id: str | None = None
    action_type: str | None = None
    action_payload: dict[str, object] | None = None
    user_feedback_message: str | None = None
    user_decision: WorkflowUserDecision | None = None


class WorkflowJobRecord(BaseModel):
    id: int
    project_id: int
    status: str
    phase: str
    current_node: str | None = None
    progress: int = 0
    langgraph_thread_id: str | None = None
    timeline_snapshot_id: str | None = None
    requested_by: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    state_artifact_id: str | None = None
    state_snapshot: dict = Field(default_factory=dict)


COMPACT_STATE_KEYS = {
    "job_id",
    "project_id",
    "dispatch_type",
    "phase",
    "current_node",
    "progress",
    "heartbeat_at",
    "transition_log",
    "runtime_status",
    "durable_status",
    "langgraph_thread_id",
    "timeline_snapshot_id",
    "project_duration_ms",
    "bpm",
    "numerator",
    "denominator",
    "track_ids",
    "sampled_clip_ids",
    "role_candidate_track_ids",
    "inferred_roles",
    "track_role_scores",
    "track_role_confidences",
    "issue_types",
    "detected_issues",
    "analysis_region_ids",
    "request_mode",
    "selected_region_id",
    "preserve_clip_id",
    "selected_region_selections",
    "issue_id",
    "action_type",
    "action_payload",
    "user_feedback_message",
    "user_decision",
    "user_feedback_recorded_at",
    "clip_feature_artifact_id",
    "vocal_detected",
    "clipping_fix_applied",
    "clipping_fix_log_id",
    "sibilance_fix_applied",
    "sibilance_fix_log_id",
    "high_band_harshness_fix_applied",
    "auto_fix_log_artifact_id",
    "auto_fix_recipe_artifact_id",
    "plan_status",
    "planner_artifact_id",
    "critic_artifact_id",
    "suggestion_group_id",
    "preview_id",
    "preview_status",
    "preview_render_no",
    "preview_excerpt_start_ms",
    "preview_excerpt_end_ms",
    "preview_requested_at",
    "preview_started_at",
    "preview_completed_at",
    "preview_expired_at",
    "preview_error_code",
    "preview_error_message",
    "has_user_action_candidates",
    "has_auto_fixable_eq_issues",
    "preview_required",
    "user_action_required",
    "auto_preview_generated",
    "validator_mode",
    "validator_result",
    "critic_mode",
    "critic_result",
    "revise_count",
    "max_revise_count",
    "latest_artifact_id",
    "mongo_artifact_ids",
    "failure_code",
    "failure_message",
    "requested_by",
    "started_at",
    "completed_at",
    "notes",
}

SPILLOVER_STATE_KEYS = {
    "bar_mapping",
    "clip_index",
    "track_representative_specs",
    "analysis_regions",
    "master_clipping_candidates",
    "master_clipping_contributors",
    "promoted_track_clipping_regions",
    "ranked_candidate_ids",
    "ranking_scores",
    "dsp_scan_summary",
    "rule_candidate_payload",
    "plan_payload",
    "planner_raw_text",
    "plan_revision_notes",
    "batch_candidate_plans",
    "batch_failed_regions",
    "batch_final_track_envelopes",
    "batch_failed_envelopes",
    "batch_validation_summary",
    "critic_raw_text",
    "suggestion_payload",
}

LEGACY_TO_SNAKE_COLUMNS = {
    "projectId": "project_id",
    "currentNode": "current_node",
    "langgraphThreadId": "langgraph_thread_id",
    "timelineSnapshotId": "timeline_snapshot_id",
    "requestedBy": "requested_by",
    "startedAt": "started_at",
    "completedAt": "completed_at",
    "errorCode": "error_code",
    "errorMessage": "error_message",
    "stateJson": "state_json",
}


class WorkflowJobStore(Protocol):
    def reset(self) -> None: ...
    def create_pending_job(self, state: WorkflowState) -> WorkflowJobRecord: ...
    def get_job(self, job_id: int) -> WorkflowJobRecord | None: ...
    def save_graph_state(self, state: WorkflowState) -> WorkflowJobRecord: ...


class InMemoryWorkflowJobStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._jobs: dict[int, WorkflowJobRecord] = {}

    def reset(self) -> None:
        with self._lock:
            self._jobs.clear()

    def create_pending_job(self, state: WorkflowState) -> WorkflowJobRecord:
        with self._lock:
            job_id = state["job_id"]
            if job_id in self._jobs:
                raise ValueError(f"Workflow job already exists: {job_id}")
            record = _build_record(state)
            self._jobs[job_id] = record
            return record.model_copy(deep=True)

    def get_job(self, job_id: int) -> WorkflowJobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            restored = record.model_copy(deep=True)
            restored.state_snapshot = _inflate_state_snapshot(
                restored.state_snapshot,
                restored.state_artifact_id,
            )
            return restored

    def save_graph_state(self, state: WorkflowState) -> WorkflowJobRecord:
        with self._lock:
            job_id = state["job_id"]
            if job_id not in self._jobs:
                raise KeyError(f"Workflow job does not exist: {job_id}")
            record = _build_record(state)
            self._jobs[job_id] = record
            return record.model_copy(deep=True)


class MySQLWorkflowJobStore:
    def __init__(self, mysql_url: str) -> None:
        self._engine: Engine = create_engine(mysql_url, pool_pre_ping=True)
        self._schema_ready = False
        self._schema_lock = RLock()

    def reset(self) -> None:
        self._ensure_schema()
        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM ai_analysis_job"))

    def create_pending_job(self, state: WorkflowState) -> WorkflowJobRecord:
        self._ensure_schema()
        record = _build_record(state)
        updated = self._update_job_record(record)
        if updated == 0:
            raise KeyError(f"Workflow job does not exist: {state['job_id']}")
        return record

    def get_job(self, job_id: int) -> WorkflowJobRecord | None:
        self._ensure_schema()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        project_id,
                        status,
                        phase,
                        current_node,
                        progress,
                        langgraph_thread_id,
                        timeline_snapshot_id,
                        requested_by,
                        started_at,
                        completed_at,
                        error_code,
                        error_message,
                        state_artifact_id,
                        state_json
                    FROM ai_analysis_job
                    WHERE id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()
        if row is None:
            return None
        return _row_to_record(dict(row))

    def save_graph_state(self, state: WorkflowState) -> WorkflowJobRecord:
        self._ensure_schema()
        record = _build_record(state)
        updated = self._update_job_record(record)
        if updated == 0:
            raise KeyError(f"Workflow job does not exist: {state['job_id']}")
        return record

    def _update_job_record(self, record: WorkflowJobRecord) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE ai_analysis_job
                    SET
                        project_id = :project_id,
                        status = :status,
                        phase = :phase,
                        current_node = :current_node,
                        progress = :progress,
                        langgraph_thread_id = :langgraph_thread_id,
                        timeline_snapshot_id = :timeline_snapshot_id,
                        requested_by = :requested_by,
                        started_at = :started_at,
                        completed_at = :completed_at,
                        error_code = :error_code,
                        error_message = :error_message,
                        state_artifact_id = :state_artifact_id,
                        state_json = :state_json
                    WHERE id = :id
                    """
                ),
                _record_params(record),
            )
        return result.rowcount

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS ai_analysis_job (
                            id VARCHAR(64) NOT NULL PRIMARY KEY,
                            project_id VARCHAR(64) NOT NULL,
                            status VARCHAR(32) NOT NULL,
                            phase VARCHAR(64) NOT NULL,
                            current_node VARCHAR(64) NULL,
                            progress TINYINT NOT NULL DEFAULT 0,
                            langgraph_thread_id VARCHAR(128) NOT NULL,
                            timeline_snapshot_id VARCHAR(128) NULL,
                            requested_by INT NULL,
                            started_at VARCHAR(64) NULL,
                            completed_at VARCHAR(64) NULL,
                            error_code VARCHAR(64) NULL,
                            error_message VARCHAR(255) NULL,
                            state_artifact_id VARCHAR(128) NULL,
                            state_json JSON NOT NULL
                        )
                        """
                    )
                )
                self._ensure_snake_case_columns(conn)
                self._backfill_from_legacy_columns(conn)
            self._schema_ready = True

    def _ensure_snake_case_columns(self, conn: Connection) -> None:
        existing_columns = _get_table_columns(conn, "ai_analysis_job")
        desired_columns = {
            "project_id": "ALTER TABLE ai_analysis_job ADD COLUMN project_id VARCHAR(64) NULL",
            "current_node": "ALTER TABLE ai_analysis_job ADD COLUMN current_node VARCHAR(64) NULL",
            "langgraph_thread_id": (
                "ALTER TABLE ai_analysis_job "
                "ADD COLUMN langgraph_thread_id VARCHAR(128) NULL"
            ),
            "timeline_snapshot_id": (
                "ALTER TABLE ai_analysis_job "
                "ADD COLUMN timeline_snapshot_id VARCHAR(128) NULL"
            ),
            "requested_by": "ALTER TABLE ai_analysis_job ADD COLUMN requested_by INT NULL",
            "started_at": "ALTER TABLE ai_analysis_job ADD COLUMN started_at VARCHAR(64) NULL",
            "completed_at": "ALTER TABLE ai_analysis_job ADD COLUMN completed_at VARCHAR(64) NULL",
            "error_code": "ALTER TABLE ai_analysis_job ADD COLUMN error_code VARCHAR(64) NULL",
            "error_message": (
                "ALTER TABLE ai_analysis_job ADD COLUMN error_message VARCHAR(255) NULL"
            ),
            "state_artifact_id": (
                "ALTER TABLE ai_analysis_job ADD COLUMN state_artifact_id VARCHAR(128) NULL"
            ),
            "state_json": "ALTER TABLE ai_analysis_job ADD COLUMN state_json JSON NULL",
        }
        for column_name, ddl in desired_columns.items():
            if column_name not in existing_columns:
                conn.execute(text(ddl))

    def _backfill_from_legacy_columns(self, conn: Connection) -> None:
        existing_columns = _get_table_columns(conn, "ai_analysis_job")
        assignments = []
        for legacy_name, snake_name in LEGACY_TO_SNAKE_COLUMNS.items():
            if legacy_name in existing_columns and snake_name in existing_columns:
                assignments.append(f"{snake_name} = COALESCE({snake_name}, {legacy_name})")
        if assignments:
            conn.execute(text(f"UPDATE ai_analysis_job SET {', '.join(assignments)}"))


def _build_record(state: WorkflowState) -> WorkflowJobRecord:
    compact_state, state_artifact_id = _sanitize_state_snapshot(state)
    return WorkflowJobRecord(
        id=state["job_id"],
        project_id=state["project_id"],
        status=state.get("durable_status", "PENDING"),
        phase=state.get("phase", "queued"),
        current_node=state.get("current_node"),
        progress=state.get("progress", 0),
        langgraph_thread_id=state.get("langgraph_thread_id", f"lg-thread:{state['job_id']}"),
        timeline_snapshot_id=state.get("timeline_snapshot_id"),
        requested_by=state.get("requested_by"),
        started_at=state.get("started_at"),
        completed_at=state.get("completed_at"),
        error_code=state.get("failure_code"),
        error_message=state.get("failure_message"),
        state_artifact_id=state_artifact_id,
        state_snapshot=compact_state,
    )


def _record_params(record: WorkflowJobRecord) -> dict:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "status": record.status,
        "phase": record.phase,
        "current_node": record.current_node,
        "progress": record.progress,
        "langgraph_thread_id": record.langgraph_thread_id,
        "timeline_snapshot_id": record.timeline_snapshot_id,
        "requested_by": record.requested_by,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "state_artifact_id": record.state_artifact_id,
        "state_json": dumps(record.state_snapshot, ensure_ascii=False),
    }


def _row_to_record(row: dict) -> WorkflowJobRecord:
    state_json = row.get("state_json")
    if isinstance(state_json, str):
        state_snapshot = loads(state_json)
    elif isinstance(state_json, dict):
        state_snapshot = state_json
    else:
        state_snapshot = {}
    state_artifact_id = row.get("state_artifact_id")
    state_snapshot = _inflate_state_snapshot(state_snapshot, state_artifact_id)
    return WorkflowJobRecord(
        id=row["id"],
        project_id=row["project_id"],
        status=row["status"],
        phase=row["phase"],
        current_node=row.get("current_node"),
        progress=int(row.get("progress", 0)),
        langgraph_thread_id=row.get("langgraph_thread_id") or f"lg-thread:{row['id']}",
        timeline_snapshot_id=row.get("timeline_snapshot_id"),
        requested_by=row.get("requested_by"),
        started_at=_normalize_datetime_value(row.get("started_at")),
        completed_at=_normalize_datetime_value(row.get("completed_at")),
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        state_artifact_id=state_artifact_id,
        state_snapshot=state_snapshot,
    )


def _normalize_datetime_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _sanitize_state_snapshot(state: WorkflowState) -> tuple[dict, str | None]:
    snapshot = deepcopy(dict(state))
    snapshot.pop("project_snapshot", None)
    snapshot.pop("track_frames", None)
    snapshot.pop("mix_frames", None)
    snapshot.pop("track_power_spectra", None)
    snapshot.pop("mix_power_spectra", None)
    snapshot.pop("frequency_bins_hz", None)

    compact_state = {key: snapshot[key] for key in COMPACT_STATE_KEYS if key in snapshot}
    spillover_state = {key: snapshot[key] for key in SPILLOVER_STATE_KEYS if key in snapshot}
    if not spillover_state:
        return compact_state, None

    state_artifact_id = _build_state_artifact_id(state)
    get_workflow_artifact_store().upsert_artifact(
        WorkflowArtifactDocument(
            id=state_artifact_id,
            job_id=state["job_id"],
            artifact_type="durable_state_payload",
            payload={"state_fields": spillover_state},
        )
    )
    return compact_state, state_artifact_id


def _inflate_state_snapshot(compact_state: dict, state_artifact_id: str | None) -> dict:
    inflated = deepcopy(compact_state)
    if not state_artifact_id:
        return inflated
    artifact = get_workflow_artifact_store().get_artifact(state_artifact_id)
    if artifact is None:
        return inflated
    state_fields = artifact.payload.get("state_fields")
    if isinstance(state_fields, dict):
        inflated.update(deepcopy(state_fields))
    return inflated


def _build_state_artifact_id(state: WorkflowState) -> str:
    return f"{state['job_id']}:durable-state"


def _get_table_columns(conn: Connection, table_name: str) -> set[str]:
    return {
        row["COLUMN_NAME"]
        for row in conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                """
            ),
            {"table_name": table_name},
        ).mappings()
    }


_memory_store = InMemoryWorkflowJobStore()
_mysql_store: MySQLWorkflowJobStore | None = None


# MySQL 설정이 있으면 durable 저장소를, 없으면 개발용 in-memory 저장소를 반환한다.
def get_workflow_job_store() -> WorkflowJobStore:
    global _mysql_store
    mysql_url = get_settings().resolved_mysql_url
    if not mysql_url:
        return _memory_store
    if _mysql_store is None:
        _mysql_store = MySQLWorkflowJobStore(mysql_url)
    return _mysql_store
