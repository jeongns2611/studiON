from __future__ import annotations

from threading import RLock
from typing import Any, Protocol

from pydantic import BaseModel, Field
from pymongo import MongoClient

from app.core.config import get_settings
from app.graph.state import utc_now
from app.services.mongo_documents import normalize_mongo_document_keys


class WorkflowArtifactDocument(BaseModel):
    id: str
    job_id: int
    artifact_type: str
    created_at: str = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifactStore(Protocol):
    def reset(self) -> None: ...
    def upsert_artifact(
        self,
        document: WorkflowArtifactDocument,
    ) -> WorkflowArtifactDocument: ...
    def get_artifact(self, artifact_id: str) -> WorkflowArtifactDocument | None: ...


class InMemoryWorkflowArtifactStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._artifacts: dict[str, WorkflowArtifactDocument] = {}

    def reset(self) -> None:
        with self._lock:
            self._artifacts.clear()

    def upsert_artifact(
        self,
        document: WorkflowArtifactDocument,
    ) -> WorkflowArtifactDocument:
        with self._lock:
            self._artifacts[document.id] = document.model_copy(deep=True)
            return document.model_copy(deep=True)

    def get_artifact(self, artifact_id: str) -> WorkflowArtifactDocument | None:
        with self._lock:
            document = self._artifacts.get(artifact_id)
            return document.model_copy(deep=True) if document else None


class MongoWorkflowArtifactStore:
    def __init__(
        self,
        mongo_url: str,
        database_name: str,
        collection_name: str,
        *,
        heartbeat_frequency_ms: int,
    ) -> None:
        self._client = MongoClient(
            mongo_url,
            heartbeatFrequencyMS=heartbeat_frequency_ms,
        )
        self._collection = self._client[database_name][collection_name]

    def reset(self) -> None:
        self._collection.delete_many({})

    def upsert_artifact(
        self,
        document: WorkflowArtifactDocument,
    ) -> WorkflowArtifactDocument:
        payload = normalize_mongo_document_keys(document.model_dump(mode="python"))
        payload["_id"] = payload.pop("id")
        self._collection.replace_one({"_id": payload["_id"]}, payload, upsert=True)
        return document

    def get_artifact(self, artifact_id: str) -> WorkflowArtifactDocument | None:
        payload = self._collection.find_one({"_id": artifact_id})
        if payload is None:
            return None
        payload["id"] = payload.pop("_id")
        return WorkflowArtifactDocument.model_validate(payload)


_memory_store = InMemoryWorkflowArtifactStore()
_mongo_store: MongoWorkflowArtifactStore | None = None


def get_workflow_artifact_store() -> WorkflowArtifactStore:
    global _mongo_store
    settings = get_settings()
    if not settings.mongo_url:
        return _memory_store
    if _mongo_store is None:
        _mongo_store = MongoWorkflowArtifactStore(
            mongo_url=settings.mongo_url,
            database_name=settings.mongo_database,
            collection_name=settings.mongo_artifact_collection,
            heartbeat_frequency_ms=settings.mongo_heartbeat_frequency_ms,
        )
    return _mongo_store
