from __future__ import annotations

from threading import RLock
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import get_settings


class AnalysisRegionCreate(BaseModel):
    job_id: int
    issue_type: str
    start_ms: int
    end_ms: int
    severity: str
    analysis_summary: str | None = None
    evidence_doc_id: str | None = None
    requires_user_action: bool


class AnalysisRegionRecord(BaseModel):
    id: int
    job_id: int
    issue_type: str
    start_ms: int
    end_ms: int
    severity: str
    analysis_summary: str | None = None
    evidence_doc_id: str | None = None
    requires_user_action: bool


class WorkflowAnalysisRegionStore(Protocol):
    def reset(self) -> None: ...
    def create_region(self, payload: AnalysisRegionCreate) -> AnalysisRegionRecord: ...


class InMemoryWorkflowAnalysisRegionStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[int, AnalysisRegionRecord] = {}
        self._next_id = 1

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._next_id = 1

    def create_region(self, payload: AnalysisRegionCreate) -> AnalysisRegionRecord:
        with self._lock:
            record = AnalysisRegionRecord(
                id=self._next_id,
                job_id=payload.job_id,
                issue_type=payload.issue_type,
                start_ms=payload.start_ms,
                end_ms=payload.end_ms,
                severity=payload.severity,
                analysis_summary=payload.analysis_summary,
                evidence_doc_id=payload.evidence_doc_id,
                requires_user_action=payload.requires_user_action,
            )
            self._records[record.id] = record
            self._next_id += 1
            return record.model_copy(deep=True)


class MySQLWorkflowAnalysisRegionStore:
    def __init__(self, mysql_url: str) -> None:
        self._engine: Engine = create_engine(mysql_url, pool_pre_ping=True)
        self._schema_ready = False
        self._schema_lock = RLock()

    def reset(self) -> None:
        self._ensure_schema()
        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM ai_analysis_region"))

    def create_region(self, payload: AnalysisRegionCreate) -> AnalysisRegionRecord:
        self._ensure_schema()
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO ai_analysis_region (
                        jobId,
                        regionTypeCode,
                        startMs,
                        endMs,
                        severityCode,
                        analysisSummary,
                        evidenceDocId,
                        rankingScore,
                        requiresUserAction
                    ) VALUES (
                        :job_id,
                        :region_type_code,
                        :start_ms,
                        :end_ms,
                        :severity_code,
                        :analysis_summary,
                        :evidence_doc_id,
                        NULL,
                        :requires_user_action
                    )
                    """
                ),
                {
                    "job_id": payload.job_id,
                    "region_type_code": _issue_type_code(payload.issue_type),
                    "start_ms": payload.start_ms,
                    "end_ms": payload.end_ms,
                    "severity_code": _severity_code(payload.severity),
                    "analysis_summary": payload.analysis_summary,
                    "evidence_doc_id": payload.evidence_doc_id,
                    "requires_user_action": payload.requires_user_action,
                },
            )
            record_id = int(result.lastrowid)
        return AnalysisRegionRecord(
            id=record_id,
            job_id=payload.job_id,
            issue_type=payload.issue_type,
            start_ms=payload.start_ms,
            end_ms=payload.end_ms,
            severity=payload.severity,
            analysis_summary=payload.analysis_summary,
            evidence_doc_id=payload.evidence_doc_id,
            requires_user_action=payload.requires_user_action,
        )

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
                        CREATE TABLE IF NOT EXISTS ai_analysis_region (
                            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                            jobId INT NOT NULL,
                            regionTypeCode INT NOT NULL,
                            startMs MEDIUMINT NOT NULL,
                            endMs MEDIUMINT NOT NULL,
                            severityCode TINYINT NOT NULL,
                            analysisSummary VARCHAR(500) NULL,
                            evidenceDocId VARCHAR(64) NULL,
                            rankingScore DECIMAL(8, 6) NULL,
                            requiresUserAction BOOLEAN NOT NULL
                        )
                        """
                    )
                )
                self._ensure_columns(conn)
            self._schema_ready = True

    def _ensure_columns(self, conn: Connection) -> None:
        existing_columns = _get_table_columns(conn, "ai_analysis_region")
        desired_columns = {
            "jobId": "ALTER TABLE ai_analysis_region ADD COLUMN jobId INT NULL",
            "regionTypeCode": (
                "ALTER TABLE ai_analysis_region ADD COLUMN regionTypeCode INT NULL"
            ),
            "startMs": "ALTER TABLE ai_analysis_region ADD COLUMN startMs MEDIUMINT NULL",
            "endMs": "ALTER TABLE ai_analysis_region ADD COLUMN endMs MEDIUMINT NULL",
            "severityCode": (
                "ALTER TABLE ai_analysis_region ADD COLUMN severityCode TINYINT NULL"
            ),
            "analysisSummary": (
                "ALTER TABLE ai_analysis_region ADD COLUMN analysisSummary VARCHAR(500) NULL"
            ),
            "evidenceDocId": (
                "ALTER TABLE ai_analysis_region ADD COLUMN evidenceDocId VARCHAR(64) NULL"
            ),
            "rankingScore": (
                "ALTER TABLE ai_analysis_region ADD COLUMN rankingScore DECIMAL(8, 6) NULL"
            ),
            "requiresUserAction": (
                "ALTER TABLE ai_analysis_region ADD COLUMN requiresUserAction BOOLEAN NULL"
            ),
        }
        for column_name, ddl in desired_columns.items():
            if column_name not in existing_columns:
                conn.execute(text(ddl))
        conn.execute(text("ALTER TABLE ai_analysis_region MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT"))


def _issue_type_code(issue_type: str) -> int:
    return {
        "band_overlap": 1,
        "track_clipping": 2,
        "master_clipping": 3,
        "sibilance": 4,
        "high_band_harshness": 5,
    }.get(issue_type, 0)


def _severity_code(severity: str) -> int:
    return {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }.get(severity, 2)


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


_memory_store = InMemoryWorkflowAnalysisRegionStore()
_mysql_store: MySQLWorkflowAnalysisRegionStore | None = None


def get_workflow_analysis_region_store() -> WorkflowAnalysisRegionStore:
    global _mysql_store
    mysql_url = get_settings().resolved_mysql_url
    if not mysql_url:
        return _memory_store
    if _mysql_store is None:
        _mysql_store = MySQLWorkflowAnalysisRegionStore(mysql_url)
    return _mysql_store
