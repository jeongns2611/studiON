from __future__ import annotations

from threading import RLock

from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings


class AudioMetadataRecord(BaseModel):
    id: int
    object_key: str
    original_name: str | None = None
    stored_name: str | None = None
    mime_type: str | None = None
    duration_ms: int | None = None


class WorkflowAudioMetadataStore:
    def __init__(self, mysql_url: str) -> None:
        self._engine: Engine = create_engine(mysql_url, pool_pre_ping=True)

    def get_by_ids(self, audio_metadata_ids: list[int]) -> dict[int, AudioMetadataRecord]:
        if not audio_metadata_ids:
            return {}
        ids = sorted(set(audio_metadata_ids))
        placeholders = ", ".join(f":id_{index}" for index, _ in enumerate(ids))
        params = {f"id_{index}": value for index, value in enumerate(ids)}
        query = text(
            f"""
            SELECT
                id,
                object_key,
                original_name,
                stored_name,
                mime_type,
                duration_ms
            FROM audio_metadata
            WHERE id IN ({placeholders})
            """
        )
        with self._engine.begin() as conn:
            rows = conn.execute(query, params).mappings().all()
        return {
            int(row["id"]): AudioMetadataRecord(
                id=int(row["id"]),
                object_key=str(row["object_key"]),
                original_name=row.get("original_name"),
                stored_name=row.get("stored_name"),
                mime_type=row.get("mime_type"),
                duration_ms=row.get("duration_ms"),
            )
            for row in rows
        }


_store_lock = RLock()
_store: WorkflowAudioMetadataStore | None = None


def get_workflow_audio_metadata_store() -> WorkflowAudioMetadataStore | None:
    global _store
    mysql_url = get_settings().resolved_mysql_url
    if not mysql_url:
        return None
    with _store_lock:
        if _store is None:
            _store = WorkflowAudioMetadataStore(mysql_url)
        return _store
