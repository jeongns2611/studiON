from __future__ import annotations

from threading import RLock
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings


class PreviewRenderRecord(BaseModel):
    id: int
    job_id: int
    analysis_region_id: int
    suggestion_id: str | None = None
    status: str
    render_no: int
    object_key: str | None = None
    duration_ms: int | None = None
    requested_by: int | None = None
    requested_at: str
    started_at: str | None = None
    completed_at: str | None = None
    expired_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    user_feedback_message: str | None = None
    preserve_clip_id: int | None = None


class PreviewRenderCreate(BaseModel):
    job_id: int
    analysis_region_id: int
    suggestion_id: str | None = None
    requested_by: int | None = None
    requested_at: str
    started_at: str | None = None
    user_feedback_message: str | None = None
    preserve_clip_id: int | None = None


class PreviewRenderReadyUpdate(BaseModel):
    record_id: int
    object_key: str | None = None
    duration_ms: int | None = None
    completed_at: str
    expired_at: str | None = None


class PreviewRenderFailedUpdate(BaseModel):
    record_id: int
    error_code: str | None = None
    error_message: str | None = None
    completed_at: str


class PreviewRenderStore(Protocol):
    def reset(self) -> None: ...
    def create_processing_render(self, payload: PreviewRenderCreate) -> PreviewRenderRecord: ...
    def mark_ready(self, payload: PreviewRenderReadyUpdate) -> PreviewRenderRecord: ...
    def mark_failed(self, payload: PreviewRenderFailedUpdate) -> PreviewRenderRecord: ...
    def list_job_renders(self, job_id: int) -> list[PreviewRenderRecord]: ...
    def get_latest_render(
        self,
        job_id: int,
        *,
        analysis_region_id: int | None = None,
        only_ready: bool = False,
    ) -> PreviewRenderRecord | None: ...


class InMemoryPreviewRenderStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[int, PreviewRenderRecord] = {}
        self._next_id = 1

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._next_id = 1

    def create_processing_render(self, payload: PreviewRenderCreate) -> PreviewRenderRecord:
        with self._lock:
            record = PreviewRenderRecord(
                id=self._next_id,
                job_id=payload.job_id,
                analysis_region_id=payload.analysis_region_id,
                suggestion_id=payload.suggestion_id,
                status="PROCESSING",
                render_no=self._next_render_no_locked(
                    payload.job_id,
                    payload.analysis_region_id,
                ),
                requested_by=payload.requested_by,
                requested_at=payload.requested_at,
                started_at=payload.started_at,
                user_feedback_message=payload.user_feedback_message,
                preserve_clip_id=payload.preserve_clip_id,
            )
            self._records[record.id] = record
            self._next_id += 1
            return record.model_copy(deep=True)

    def mark_ready(self, payload: PreviewRenderReadyUpdate) -> PreviewRenderRecord:
        with self._lock:
            record = self._records[payload.record_id]
            updated = record.model_copy(
                update={
                    "status": "READY",
                    "object_key": payload.object_key,
                    "duration_ms": payload.duration_ms,
                    "completed_at": payload.completed_at,
                    "expired_at": payload.expired_at,
                    "error_code": None,
                    "error_message": None,
                }
            )
            self._records[payload.record_id] = updated
            return updated.model_copy(deep=True)

    def mark_failed(self, payload: PreviewRenderFailedUpdate) -> PreviewRenderRecord:
        with self._lock:
            record = self._records[payload.record_id]
            updated = record.model_copy(
                update={
                    "status": "FAILED",
                    "completed_at": payload.completed_at,
                    "error_code": payload.error_code,
                    "error_message": payload.error_message,
                }
            )
            self._records[payload.record_id] = updated
            return updated.model_copy(deep=True)

    def list_job_renders(self, job_id: int) -> list[PreviewRenderRecord]:
        with self._lock:
            return [
                record.model_copy(deep=True)
                for record in _sorted_records(
                    record for record in self._records.values() if record.job_id == job_id
                )
            ]

    def get_latest_render(
        self,
        job_id: int,
        *,
        analysis_region_id: int | None = None,
        only_ready: bool = False,
    ) -> PreviewRenderRecord | None:
        with self._lock:
            records = _sorted_records(
                record
                for record in self._records.values()
                if record.job_id == job_id
                and (analysis_region_id is None or record.analysis_region_id == analysis_region_id)
                and (not only_ready or record.status == "READY")
            )
            if not records:
                return None
            return records[-1].model_copy(deep=True)

    def _next_render_no_locked(self, job_id: int, analysis_region_id: int) -> int:
        latest = self.get_latest_render(job_id, analysis_region_id=analysis_region_id)
        if latest is None:
            return 1
        return int(latest.render_no) + 1


class MySQLPreviewRenderStore:
    def __init__(self, mysql_url: str) -> None:
        self._engine: Engine = create_engine(mysql_url, pool_pre_ping=True)
        self._schema_ready = False
        self._schema_lock = RLock()

    def reset(self) -> None:
        self._ensure_schema()
        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM ai_preview_render"))

    def create_processing_render(self, payload: PreviewRenderCreate) -> PreviewRenderRecord:
        self._ensure_schema()
        with self._engine.begin() as conn:
            render_no = int(
                conn.execute(
                    text(
                        """
                        SELECT COALESCE(MAX(render_no), 0) + 1
                        FROM ai_preview_render
                        WHERE job_id = :job_id
                          AND analysis_region_id = :analysis_region_id
                        """
                    ),
                    {
                        "job_id": payload.job_id,
                        "analysis_region_id": payload.analysis_region_id,
                    },
                ).scalar_one()
            )
            result = conn.execute(
                text(
                    """
                    INSERT INTO ai_preview_render (
                        job_id,
                        analysis_region_id,
                        suggestion_id,
                        status,
                        render_no,
                        requested_by,
                        requested_at,
                        started_at,
                        user_feedback_message,
                        preserve_clip_id
                    ) VALUES (
                        :job_id,
                        :analysis_region_id,
                        :suggestion_id,
                        'PROCESSING',
                        :render_no,
                        :requested_by,
                        :requested_at,
                        :started_at,
                        :user_feedback_message,
                        :preserve_clip_id
                    )
                    """
                ),
                {
                    "job_id": payload.job_id,
                    "analysis_region_id": payload.analysis_region_id,
                    "suggestion_id": payload.suggestion_id,
                    "render_no": render_no,
                    "requested_by": payload.requested_by,
                    "requested_at": payload.requested_at,
                    "started_at": payload.started_at,
                    "user_feedback_message": payload.user_feedback_message,
                    "preserve_clip_id": payload.preserve_clip_id,
                },
            )
            record_id = int(result.lastrowid)
        record = self.get_render(record_id)
        if record is None:
            raise KeyError(f"Preview render does not exist: {record_id}")
        return record

    def mark_ready(self, payload: PreviewRenderReadyUpdate) -> PreviewRenderRecord:
        self._ensure_schema()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE ai_preview_render
                    SET
                        status = 'READY',
                        object_key = :object_key,
                        duration_ms = :duration_ms,
                        completed_at = :completed_at,
                        expired_at = :expired_at,
                        error_code = NULL,
                        error_message = NULL
                    WHERE id = :record_id
                    """
                ),
                payload.model_dump(mode="python"),
            )
        record = self.get_render(payload.record_id)
        if record is None:
            raise KeyError(f"Preview render does not exist: {payload.record_id}")
        return record

    def mark_failed(self, payload: PreviewRenderFailedUpdate) -> PreviewRenderRecord:
        self._ensure_schema()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE ai_preview_render
                    SET
                        status = 'FAILED',
                        completed_at = :completed_at,
                        error_code = :error_code,
                        error_message = :error_message
                    WHERE id = :record_id
                    """
                ),
                payload.model_dump(mode="python"),
            )
        record = self.get_render(payload.record_id)
        if record is None:
            raise KeyError(f"Preview render does not exist: {payload.record_id}")
        return record

    def list_job_renders(self, job_id: int) -> list[PreviewRenderRecord]:
        self._ensure_schema()
        with self._engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        job_id,
                        analysis_region_id,
                        suggestion_id,
                        status,
                        render_no,
                        object_key,
                        duration_ms,
                        requested_by,
                        requested_at,
                        started_at,
                        completed_at,
                        expired_at,
                        error_code,
                        error_message,
                        user_feedback_message,
                        preserve_clip_id
                    FROM ai_preview_render
                    WHERE job_id = :job_id
                    ORDER BY requested_at ASC, render_no ASC, id ASC
                    """
                ),
                {"job_id": job_id},
            ).mappings()
            return [_row_to_record(dict(row)) for row in rows]

    def get_latest_render(
        self,
        job_id: int,
        *,
        analysis_region_id: int | None = None,
        only_ready: bool = False,
    ) -> PreviewRenderRecord | None:
        self._ensure_schema()
        conditions = ["job_id = :job_id"]
        params: dict[str, object] = {"job_id": job_id}
        if analysis_region_id is not None:
            conditions.append("analysis_region_id = :analysis_region_id")
            params["analysis_region_id"] = analysis_region_id
        if only_ready:
            conditions.append("status = 'READY'")
        query = f"""
            SELECT
                id,
                job_id,
                analysis_region_id,
                suggestion_id,
                status,
                render_no,
                object_key,
                duration_ms,
                requested_by,
                requested_at,
                started_at,
                completed_at,
                expired_at,
                error_code,
                error_message,
                user_feedback_message,
                preserve_clip_id
            FROM ai_preview_render
            WHERE {' AND '.join(conditions)}
            ORDER BY requested_at DESC, render_no DESC, id DESC
            LIMIT 1
        """
        with self._engine.begin() as conn:
            row = conn.execute(text(query), params).mappings().first()
        if row is None:
            return None
        return _row_to_record(dict(row))

    def get_render(self, record_id: int) -> PreviewRenderRecord | None:
        self._ensure_schema()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        job_id,
                        analysis_region_id,
                        suggestion_id,
                        status,
                        render_no,
                        object_key,
                        duration_ms,
                        requested_by,
                        requested_at,
                        started_at,
                        completed_at,
                        expired_at,
                        error_code,
                        error_message,
                        user_feedback_message,
                        preserve_clip_id
                    FROM ai_preview_render
                    WHERE id = :record_id
                    """
                ),
                {"record_id": record_id},
            ).mappings().first()
        if row is None:
            return None
        return _row_to_record(dict(row))

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
                        CREATE TABLE IF NOT EXISTS ai_preview_render (
                            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                            job_id INT NOT NULL,
                            analysis_region_id INT NOT NULL,
                            suggestion_id VARCHAR(128) NULL,
                            status VARCHAR(32) NOT NULL,
                            render_no INT NOT NULL DEFAULT 1,
                            object_key VARCHAR(1024) NULL,
                            duration_ms INT NULL,
                            requested_by INT NULL,
                            requested_at VARCHAR(64) NOT NULL,
                            started_at VARCHAR(64) NULL,
                            completed_at VARCHAR(64) NULL,
                            expired_at VARCHAR(64) NULL,
                            error_code VARCHAR(64) NULL,
                            error_message VARCHAR(1000) NULL,
                            user_feedback_message VARCHAR(1000) NULL,
                            preserve_clip_id INT NULL,
                            INDEX idx_ai_preview_render_job_requested (job_id, requested_at),
                            INDEX idx_ai_preview_render_region_requested (
                                analysis_region_id,
                                requested_at
                            )
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        ALTER TABLE ai_preview_render
                        MODIFY COLUMN analysis_region_id INT NOT NULL
                        """
                    )
                )
            self._schema_ready = True


def _sorted_records(records: object) -> list[PreviewRenderRecord]:
    return sorted(
        list(records),
        key=lambda record: (record.requested_at, int(record.render_no), int(record.id)),
    )


def _row_to_record(row: dict[str, object]) -> PreviewRenderRecord:
    return PreviewRenderRecord(
        id=int(row["id"]),
        job_id=int(row["job_id"]),
        analysis_region_id=int(row["analysis_region_id"]),
        suggestion_id=str(row["suggestion_id"]) if row.get("suggestion_id") is not None else None,
        status=str(row["status"]),
        render_no=int(row["render_no"]),
        object_key=str(row["object_key"]) if row.get("object_key") is not None else None,
        duration_ms=(
            int(row["duration_ms"]) if row.get("duration_ms") is not None else None
        ),
        requested_by=(
            int(row["requested_by"]) if row.get("requested_by") is not None else None
        ),
        requested_at=str(row["requested_at"]),
        started_at=str(row["started_at"]) if row.get("started_at") is not None else None,
        completed_at=(
            str(row["completed_at"]) if row.get("completed_at") is not None else None
        ),
        expired_at=str(row["expired_at"]) if row.get("expired_at") is not None else None,
        error_code=str(row["error_code"]) if row.get("error_code") is not None else None,
        error_message=(
            str(row["error_message"]) if row.get("error_message") is not None else None
        ),
        user_feedback_message=(
            str(row["user_feedback_message"])
            if row.get("user_feedback_message") is not None
            else None
        ),
        preserve_clip_id=(
            int(row["preserve_clip_id"]) if row.get("preserve_clip_id") is not None else None
        ),
    )


_memory_store = InMemoryPreviewRenderStore()
_mysql_store: MySQLPreviewRenderStore | None = None


def get_workflow_preview_render_store() -> PreviewRenderStore:
    global _mysql_store
    mysql_url = get_settings().resolved_mysql_url
    if not mysql_url:
        return _memory_store
    if _mysql_store is None:
        _mysql_store = MySQLPreviewRenderStore(mysql_url)
    return _mysql_store
