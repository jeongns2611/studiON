from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from pydantic import BaseModel, Field, model_validator
from pymongo import MongoClient

from app.core.config import get_settings
from app.graph.state import utc_now
from app.services.mongo_documents import normalize_mongo_document_keys
from app.services.workflow_audio_metadata import get_workflow_audio_metadata_store


class ProjectTrack(BaseModel):
    track_id: int
    name: str | None = None


class ProjectClip(BaseModel):
    clip_id: int
    track_id: int
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    audio_metadata_id: int = Field(gt=0)
    audio_start_ms: int = Field(default=0, ge=0)
    audio_duration_ms: int | None = Field(default=None, gt=0)
    audio_url: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> ProjectClip:
        if self.end_ms <= self.start_ms:
            raise ValueError("clip end_ms must be greater than start_ms")
        if self.audio_duration_ms is not None and self.audio_duration_ms <= 0:
            raise ValueError("clip audio_duration_ms must be greater than 0")
        return self


class ProjectTrackEqBand(BaseModel):
    band_order: int = Field(ge=1)
    eq_type: str
    frequency_hz: int = Field(gt=0)
    q: float = Field(gt=0)
    gain_delta_db: float

    @model_validator(mode="after")
    def validate_eq_type(self) -> ProjectTrackEqBand:
        if self.eq_type not in {"BELL", "LOW_SHELF", "HIGH_SHELF"}:
            raise ValueError("track_eq band eq_type must be one of BELL, LOW_SHELF, HIGH_SHELF")
        return self


class ProjectTrackEq(BaseModel):
    track_id: int
    bands: list[ProjectTrackEqBand] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_band_orders(self) -> ProjectTrackEq:
        band_orders = [band.band_order for band in self.bands]
        if len(set(band_orders)) != len(band_orders):
            raise ValueError("track_eq bands must have unique band_order values")
        return self


class ProjectSnapshot(BaseModel):
    duration_ms: int = Field(gt=0)
    bpm: float = Field(gt=0)
    numerator: int = Field(default=4, ge=1)
    denominator: int = Field(default=4, ge=1)
    tracks: list[ProjectTrack] = Field(min_length=1)
    clips: list[ProjectClip] = Field(min_length=1)
    track_eqs: list[ProjectTrackEq] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_links(self) -> ProjectSnapshot:
        known_tracks = {track.track_id for track in self.tracks}
        unknown = sorted(
            {clip.track_id for clip in self.clips if clip.track_id not in known_tracks}
        )
        if unknown:
            raise ValueError(f"clips reference unknown track ids: {unknown}")
        unknown_eq_tracks = sorted(
            {track_eq.track_id for track_eq in self.track_eqs if track_eq.track_id not in known_tracks}
        )
        if unknown_eq_tracks:
            raise ValueError(f"track_eqs reference unknown track ids: {unknown_eq_tracks}")
        return self


class TimelineSnapshotDocument(BaseModel):
    id: str
    job_id: int
    project_id: int
    created_at: str
    duration_ms: int
    track_ids: list[int] = Field(default_factory=list)
    track_name_map: dict[str, str | None] = Field(default_factory=dict)
    bpm: float
    numerator: int
    denominator: int
    bar_mapping: list[dict[str, int]] = Field(default_factory=list)
    clip_index: list[dict[str, object | None]] = Field(default_factory=list)
    track_eq_map: dict[str, list[dict[str, object]]] = Field(default_factory=dict)
    snapshot: dict


@dataclass(slots=True)
class SnapshotRuntimeContext:
    duration_ms: int
    track_ids: list[int]
    track_name_map: dict[int, str | None]
    bpm: float
    numerator: int
    denominator: int
    bar_mapping: list[dict[str, int]]
    clip_index: list[dict[str, object | None]]
    track_eq_map: dict[int, list[dict[str, object]]]


class WorkflowSnapshotStore(Protocol):
    def reset(self) -> None: ...
    def upsert_snapshot(self, document: TimelineSnapshotDocument) -> TimelineSnapshotDocument: ...
    def get_snapshot(self, snapshot_id: str) -> TimelineSnapshotDocument | None: ...


class InMemoryWorkflowSnapshotStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshots: dict[str, TimelineSnapshotDocument] = {}

    def reset(self) -> None:
        with self._lock:
            self._snapshots.clear()

    def upsert_snapshot(self, document: TimelineSnapshotDocument) -> TimelineSnapshotDocument:
        with self._lock:
            self._snapshots[document.id] = document.model_copy(deep=True)
            return document.model_copy(deep=True)

    def get_snapshot(self, snapshot_id: str) -> TimelineSnapshotDocument | None:
        with self._lock:
            document = self._snapshots.get(snapshot_id)
            return document.model_copy(deep=True) if document else None


class MongoWorkflowSnapshotStore:
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

    def upsert_snapshot(self, document: TimelineSnapshotDocument) -> TimelineSnapshotDocument:
        payload = normalize_mongo_document_keys(document.model_dump(mode="python"))
        payload["_id"] = payload.pop("id")
        self._collection.replace_one({"_id": payload["_id"]}, payload, upsert=True)
        return document

    def get_snapshot(self, snapshot_id: str) -> TimelineSnapshotDocument | None:
        payload = self._collection.find_one({"_id": snapshot_id})
        if payload is None:
            return None
        payload["id"] = payload.pop("_id")
        return TimelineSnapshotDocument.model_validate(payload)


def build_snapshot_id(job_id: int) -> str:
    return f"{job_id}-timeline-snapshot"


def build_snapshot_runtime_context(snapshot: ProjectSnapshot | dict) -> SnapshotRuntimeContext:
    # start 요청 원문 전체는 Mongo에 두고, graph/state에는 투영 계산용 파생 메타만 남긴다.
    snapshot = ProjectSnapshot.model_validate(snapshot)
    return SnapshotRuntimeContext(
        duration_ms=snapshot.duration_ms,
        track_ids=sorted({track.track_id for track in snapshot.tracks}),
        track_name_map={
            int(track.track_id): track.name.strip() if isinstance(track.name, str) and track.name.strip() else None
            for track in snapshot.tracks
        },
        bpm=round(snapshot.bpm, 6),
        numerator=snapshot.numerator,
        denominator=snapshot.denominator,
        bar_mapping=_build_bar_mapping(
            duration_ms=snapshot.duration_ms,
            bpm=snapshot.bpm,
            numerator=snapshot.numerator,
            denominator=snapshot.denominator,
        ),
        clip_index=_build_clip_index(snapshot),
        track_eq_map=_build_track_eq_map(snapshot),
    )


def build_timeline_snapshot_document(
    *,
    job_id: int,
    project_id: int,
    snapshot_id: str,
    snapshot: ProjectSnapshot | dict,
) -> TimelineSnapshotDocument:
    # 프론트가 보낸 snapshot 원문은 이후 stale 비교와 재투영을 위해 문서째로 보존한다.
    snapshot = ProjectSnapshot.model_validate(snapshot)
    context = build_snapshot_runtime_context(snapshot)
    return TimelineSnapshotDocument(
        id=snapshot_id,
        job_id=job_id,
        project_id=project_id,
        created_at=utc_now(),
        duration_ms=context.duration_ms,
        track_ids=context.track_ids,
        track_name_map={
            str(track_id): track_name
            for track_id, track_name in context.track_name_map.items()
        },
        bpm=context.bpm,
        numerator=context.numerator,
        denominator=context.denominator,
        bar_mapping=context.bar_mapping,
        clip_index=context.clip_index,
        track_eq_map={str(track_id): bands for track_id, bands in context.track_eq_map.items()},
        snapshot=snapshot.model_dump(mode="python"),
    )


def _build_bar_mapping(
    *,
    duration_ms: int,
    bpm: float,
    numerator: int,
    denominator: int,
) -> list[dict[str, int]]:
    bars: list[dict[str, int]] = []
    measure_no = 1
    cursor = 0.0
    bar_length_ms = (60000.0 / bpm) * numerator * (4.0 / denominator)
    while cursor < duration_ms:
        start_ms = int(round(cursor))
        next_cursor = min(cursor + bar_length_ms, duration_ms)
        end_ms = min(int(round(next_cursor)), duration_ms)
        if end_ms <= start_ms:
            end_ms = min(start_ms + 1, duration_ms)
        bars.append(
            {
                "measure_no": measure_no,
                "start_ms": start_ms,
                "end_ms": end_ms,
            }
        )
        measure_no += 1
        cursor = next_cursor
    return bars


def _build_clip_index(snapshot: ProjectSnapshot) -> list[dict[str, object | None]]:
    audio_metadata_store = get_workflow_audio_metadata_store()
    audio_metadata_ids = [
        clip.audio_metadata_id for clip in snapshot.clips if not clip.audio_url
    ]
    audio_metadata_map = (
        audio_metadata_store.get_by_ids(
            [int(audio_metadata_id) for audio_metadata_id in audio_metadata_ids]
        )
        if audio_metadata_store is not None and audio_metadata_ids
        else {}
    )
    return [
        {
            "clip_id": clip.clip_id,
            "track_id": clip.track_id,
            "start_ms": clip.start_ms,
            "end_ms": clip.end_ms,
            "audio_metadata_id": clip.audio_metadata_id,
            "audio_url": clip.audio_url,
            "object_key": (
                audio_metadata_map[int(clip.audio_metadata_id)].object_key
                if int(clip.audio_metadata_id) in audio_metadata_map
                else None
            ),
            "audio_start_ms": clip.audio_start_ms,
            "audio_duration_ms": clip.audio_duration_ms or (clip.end_ms - clip.start_ms),
        }
        for clip in sorted(
            snapshot.clips,
            key=lambda item: (item.start_ms, item.track_id, item.clip_id),
        )
    ]


def _build_track_eq_map(snapshot: ProjectSnapshot) -> dict[int, list[dict[str, object]]]:
    return {
        int(track_eq.track_id): [
            {
                "band_order": int(band.band_order),
                "eq_type": band.eq_type,
                "frequency_hz": int(band.frequency_hz),
                "q": float(band.q),
                "gain_delta_db": float(band.gain_delta_db),
            }
            for band in sorted(track_eq.bands, key=lambda item: item.band_order)
        ]
        for track_eq in snapshot.track_eqs
    }


_memory_store = InMemoryWorkflowSnapshotStore()
_mongo_store: MongoWorkflowSnapshotStore | None = None


def get_workflow_snapshot_store() -> WorkflowSnapshotStore:
    global _mongo_store
    settings = get_settings()
    if not settings.mongo_url:
        return _memory_store
    if _mongo_store is None:
        _mongo_store = MongoWorkflowSnapshotStore(
            mongo_url=settings.mongo_url,
            database_name=settings.mongo_database,
            collection_name=settings.mongo_snapshot_collection,
            heartbeat_frequency_ms=settings.mongo_heartbeat_frequency_ms,
        )
    return _mongo_store
