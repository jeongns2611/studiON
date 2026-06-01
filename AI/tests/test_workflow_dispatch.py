from __future__ import annotations
from pathlib import Path
from tempfile import gettempdir
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.persistence.projections import build_workflow_projections
from app.graph.state import build_workflow_initial_state
from app.main import create_app
from app.services.clap_inference import CLAPTrackPrediction
from app.services.mongo_documents import normalize_mongo_document_keys
from app.services.plan_critic_llm import PlanCriticLLMResponse
from app.services.planning_llm import PlanningLLMError, PlanningLLMResponse
from app.services.workflow_artifacts import (
    MongoWorkflowArtifactStore,
    WorkflowArtifactDocument,
    get_workflow_artifact_store,
)
from app.services.workflow_audio_metadata import AudioMetadataRecord
from app.services.workflow_jobs import (
    MySQLWorkflowJobStore,
    WorkflowDispatchMessage,
    _build_record,
    _row_to_record,
    get_workflow_job_store,
)
from app.services.workflow_orchestration import (
    WorkflowStartPayload,
    start_workflow_job,
)
from app.services.workflow_snapshots import (
    MongoWorkflowSnapshotStore,
    TimelineSnapshotDocument,
    get_workflow_snapshot_store,
)
from app.services.workflow_worker import run_workflow_dispatch

_TEST_AUDIO_METADATA: dict[int, AudioMetadataRecord] = {}


def _ensure_test_audio_file(track_id: int, *, vocal_like: bool) -> str:
    sample_rate = 16000
    duration_seconds = 6.0
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    signal = (
        0.42 * np.sin(2 * np.pi * 330 * time_axis)
        + 0.34 * np.sin(2 * np.pi * 520 * time_axis)
    )
    if vocal_like:
        signal += 0.28 * np.sin(2 * np.pi * 6800 * time_axis)
    signal = signal.astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"dispatch-track-{track_id}-{'vocal' if vocal_like else 'support'}.wav"
    if not audio_path.exists():
        sf.write(audio_path, signal, sample_rate)
    return str(audio_path)


def _clip_id(track_id: int, ordinal: int) -> int:
    return (track_id * 1000) + ordinal


def _audio_metadata_id(track_id: int, ordinal: int) -> int:
    return (track_id * 1000) + ordinal


def _register_audio_metadata(metadata_id: int, audio_path: str) -> int:
    _TEST_AUDIO_METADATA[metadata_id] = AudioMetadataRecord(
        id=metadata_id,
        object_key=audio_path,
        duration_ms=4800,
    )
    return metadata_id


class _FakeAudioMetadataStore:
    def get_by_ids(self, audio_metadata_ids: list[int]) -> dict[int, AudioMetadataRecord]:
        return {
            int(audio_metadata_id): _TEST_AUDIO_METADATA[int(audio_metadata_id)]
            for audio_metadata_id in audio_metadata_ids
            if int(audio_metadata_id) in _TEST_AUDIO_METADATA
        }


class _FakeCLAPInferenceClient:
    def infer_track_roles(self, *, job_id: int, excerpts: list) -> list[CLAPTrackPrediction]:
        predictions: list[CLAPTrackPrediction] = []
        ordered_track_ids: list[int] = []
        for excerpt in excerpts:
            track_id = int(excerpt.metadata["track_id"])
            if track_id not in ordered_track_ids:
                ordered_track_ids.append(track_id)
        for index, track_id in enumerate(ordered_track_ids):
            is_vocal = index == 0
            predictions.append(
                CLAPTrackPrediction(
                    track_id=track_id,
                    vocal_score=0.91 if is_vocal else 0.24,
                    confidence=0.87 if is_vocal else 0.69,
                    predicted_role="vocal-like" if is_vocal else "supporting",
                    excerpt_scores=[],
                )
            )
        return predictions


class _CaptureCollection:
    def __init__(self) -> None:
        self.filter: dict | None = None
        self.payload: dict | None = None
        self.upsert: bool | None = None

    def replace_one(self, filter_query: dict, payload: dict, *, upsert: bool) -> None:
        self.filter = filter_query
        self.payload = payload
        self.upsert = upsert


@pytest.fixture(autouse=True)
def reset_job_store(monkeypatch: pytest.MonkeyPatch) -> None:
    _TEST_AUDIO_METADATA.clear()
    settings = SimpleNamespace(
        resolved_mysql_url=None,
        mongo_url=None,
        mongo_database="studion_ai",
        mongo_snapshot_collection="timeline_snapshots",
        mongo_artifact_collection="workflow_artifacts",
        audio_root=None,
        audio_cache_dir=str(Path(gettempdir()) / "studion-ai-audio-cache-test"),
        audio_download_timeout_seconds=10.0,
        audio_download_connect_timeout_seconds=2.0,
    )
    monkeypatch.setattr(
        "app.services.workflow_jobs.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr("app.services.workflow_artifacts.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.workflow_snapshots.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.workflow_snapshots.get_workflow_audio_metadata_store",
        lambda: _FakeAudioMetadataStore(),
    )
    monkeypatch.setattr(
        "app.graph.nodes.analysis.get_clap_inference_client",
        lambda: _FakeCLAPInferenceClient(),
    )
    monkeypatch.setattr("app.services.workflow_jobs._mysql_store", None)
    monkeypatch.setattr("app.services.workflow_artifacts._mongo_store", None)
    monkeypatch.setattr("app.services.workflow_snapshots._mongo_store", None)
    store = get_workflow_job_store()
    snapshot_store = get_workflow_snapshot_store()
    artifact_store = get_workflow_artifact_store()
    store.reset()
    snapshot_store.reset()
    artifact_store.reset()
    yield
    store.reset()
    snapshot_store.reset()
    artifact_store.reset()
    _TEST_AUDIO_METADATA.clear()


@pytest.fixture(autouse=True)
def patch_planning_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakePlanningClient:
        def generate_plan(
            self,
            *,
            selected_region_id: int,
            preserve_clip_id: int,
            user_feedback_message: str | None,
            selection_context: dict[str, object],
            region: dict[str, object],
            clip_context: list[dict[str, object]],
            revision_notes: list[str],
        ) -> PlanningLLMResponse:
            preserve_track_id = None
            for clip in clip_context:
                if int(clip.get("clip_id") or 0) == preserve_clip_id:
                    preserve_track_id = int(clip.get("track_id") or 0)
                    break
            target_track_ids = (
                region.get("target_track_ids")
                or region.get("involved_track_ids")
                or ([region["track_id"]] if region.get("track_id") is not None else [])
            )
            target_track_id = None
            if isinstance(target_track_ids, list) and target_track_ids:
                for candidate_track_id in target_track_ids:
                    candidate_value = int(candidate_track_id)
                    if preserve_track_id is None or candidate_value != preserve_track_id:
                        target_track_id = candidate_value
                        break
                if target_track_id is None:
                    target_track_id = int(target_track_ids[0])
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "dispatch test plan",
                    "strategySummary": "dispatch test summary",
                    "summary": "dispatch test suggestion",
                    "explanation": "dispatch test explanation",
                    "candidate": {
                        "action": {
                            "actionType": "DYNAMIC_EQ",
                            "targetScope": "TRACK",
                            "targetTrackId": target_track_id,
                            "targetClipId": preserve_clip_id,
                            "startMs": int(region["start_ms"]),
                            "endMs": int(region["end_ms"]),
                            "bandLowHz": 180,
                            "bandHighHz": 420,
                            "gainDeltaDb": -2.5,
                            "params": {"q": 1.1, "attackMs": 10, "releaseMs": 80},
                        }
                    },
                }
            )

    class _FakeCriticClient:
        def review_plan(
            self,
            *,
            selected_region_id: int,
            preserve_clip_id: int,
            user_feedback_message: str | None,
            selection_context: dict[str, object],
            region: dict[str, object],
            plan_payload: dict[str, object],
            revision_notes: list[str],
        ) -> PlanCriticLLMResponse:
            return PlanCriticLLMResponse(result="PASS", note="")

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _FakePlanningClient(),
    )
    monkeypatch.setattr(
        "app.graph.nodes.review.get_plan_critic_llm_client",
        lambda: _FakeCriticClient(),
    )


def build_project_snapshot(
    *,
    track_ids: list[int],
    track_eqs: list[dict[str, object]] | None = None,
) -> dict:
    clips = []
    for index, track_id in enumerate(track_ids, start=1):
        metadata_id = _register_audio_metadata(
            _audio_metadata_id(track_id, index),
            _ensure_test_audio_file(track_id, vocal_like=index == 1),
        )
        clips.append(
            {
                "clip_id": _clip_id(track_id, index),
                "track_id": track_id,
                "start_ms": (index - 1) * 900,
                "end_ms": ((index - 1) * 900) + 2200,
                "audio_metadata_id": metadata_id,
                "audio_start_ms": 0,
                "audio_duration_ms": 4800,
            }
        )
    return {
        "duration_ms": 4800,
        "bpm": 120,
        "numerator": 4,
        "denominator": 4,
        "tracks": [{"track_id": track_id, "name": f"Track {track_id}"} for track_id in track_ids],
        "clips": clips,
        "track_eqs": track_eqs or [],
    }


def build_plan_input(state: dict) -> dict[str, object]:
    selected_region_id = state["ranked_candidate_ids"][0]
    region = next(
        region for region in state["analysis_regions"] if region["id"] == selected_region_id
    )
    return {
        "selected_region_id": selected_region_id,
        "preserve_clip_id": region["affected_clip_ids"][0],
    }


def build_batch_waiting_state(*, job_id: int, project_id: int) -> dict[str, object]:
    return build_workflow_initial_state(
        job_id=job_id,
        project_id=project_id,
        phase="waiting_for_user_plan_input",
        current_node="wait_user_plan_input",
        progress=62,
        runtime_status="waiting_for_user",
        durable_status="WAITING_USER",
        clip_index=[
            {"clip_id": 11001, "track_id": 11, "start_ms": 0, "end_ms": 2200},
            {"clip_id": 12001, "track_id": 12, "start_ms": 200, "end_ms": 2200},
            {"clip_id": 13001, "track_id": 13, "start_ms": 300, "end_ms": 2200},
        ],
        track_name_map={11: "Lead Vocal", 12: "Synth Bed", 13: "Guitar"},
        analysis_regions=[
            {
                "id": 101,
                "issue_type": "band_overlap",
                "requires_user_action": True,
                "track_id": 11,
                "secondary_track_id": 12,
                "involved_track_ids": [11, 12],
                "affected_clip_ids": [11001, 12001],
                "start_ms": 0,
                "end_ms": 700,
                "band_low_hz": 260,
                "band_high_hz": 520,
                "band_overlap_subtype": "low_mid_overlap",
                "band_focus_label": "body",
            },
            {
                "id": 102,
                "issue_type": "band_overlap",
                "requires_user_action": True,
                "track_id": 11,
                "secondary_track_id": 12,
                "involved_track_ids": [11, 12, 13],
                "affected_clip_ids": [11001, 12001, 13001],
                "start_ms": 900,
                "end_ms": 1900,
                "band_low_hz": 1800,
                "band_high_hz": 3400,
                "band_overlap_subtype": "presence_overlap",
                "band_focus_label": "presence",
            },
        ],
        ranked_candidate_ids=[101, 102],
    )


def test_normalize_mongo_document_keys_recursively_stringifies_numeric_keys() -> None:
    payload = {
        10: {"scores": {20: 0.91}, "windows": [{30: "value"}]},
        "track_frames": {40: [{"frame": 1}]},
    }

    normalized = normalize_mongo_document_keys(payload)

    assert "10" in normalized
    assert normalized["10"]["scores"]["20"] == 0.91
    assert normalized["10"]["windows"][0]["30"] == "value"
    assert normalized["track_frames"]["40"][0]["frame"] == 1


def test_mongo_artifact_store_upsert_normalizes_nested_numeric_keys() -> None:
    capture = _CaptureCollection()
    store = MongoWorkflowArtifactStore.__new__(MongoWorkflowArtifactStore)
    store._collection = capture

    store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-1",
            job_id=1,
            artifact_type="full_stft_frame_summary",
            payload={
                "track_frames": {10: [{"spectral_centroid_hz": 2200.0}]},
                "track_stats": {20: {"vocal_like_score": 0.91}},
            },
        )
    )

    assert capture.filter == {"_id": "artifact-1"}
    assert capture.upsert is True
    assert capture.payload is not None
    assert capture.payload["payload"]["track_frames"]["10"][0]["spectral_centroid_hz"] == 2200.0
    assert capture.payload["payload"]["track_stats"]["20"]["vocal_like_score"] == 0.91


def test_mongo_snapshot_store_upsert_normalizes_nested_numeric_keys() -> None:
    capture = _CaptureCollection()
    store = MongoWorkflowSnapshotStore.__new__(MongoWorkflowSnapshotStore)
    store._collection = capture

    store.upsert_snapshot(
        TimelineSnapshotDocument(
            id="snapshot-1",
            job_id=1,
            project_id=2,
            created_at="2026-04-30T00:00:00+00:00",
            duration_ms=4800,
            track_ids=[10, 20],
            bpm=120.0,
            numerator=4,
            denominator=4,
            bar_mapping=[{"measure_no": 1, "start_ms": 0, "end_ms": 2000}],
            clip_index=[],
            snapshot={
                "tracks": [{10: "Lead Vocal"}],
                "meta": {"role_by_track": {20: "supporting"}},
            },
        )
    )

    assert capture.filter == {"_id": "snapshot-1"}
    assert capture.upsert is True
    assert capture.payload is not None
    assert capture.payload["snapshot"]["tracks"][0]["10"] == "Lead Vocal"
    assert capture.payload["snapshot"]["meta"]["role_by_track"]["20"] == "supporting"


def test_worker_start_dispatch_restores_durable_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20001,
            project_id=30001,
            project_snapshot=build_project_snapshot(track_ids=[12, 18]),
            issue_types=["band_overlap", "sibilance"],
        )
    )

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20001,
            project_id=30001,
            dispatch_type="start",
        )
    )

    stored = get_workflow_job_store().get_job(20001)
    assert result["current_node"] == "wait_user_plan_input"
    assert result["runtime_status"] == "waiting_for_user"
    assert stored is not None
    assert stored.phase == "waiting_for_user_plan_input"
    assert stored.status == "WAITING_USER"


def test_job_status_projection_keeps_active_issue_metadata_out_of_routing() -> None:
    state = build_workflow_initial_state(
        job_id=200010,
        project_id=300010,
        phase="waiting_for_user_plan_input",
        current_node="wait_user_plan_input",
        runtime_status="waiting_for_user",
        durable_status="WAITING_USER",
        ranked_candidate_ids=[101],
        analysis_regions=[
            {
                "id": 101,
                "issue_type": "band_overlap",
                "requires_user_action": True,
                "track_id": 11,
                "secondary_track_id": 12,
                "start_ms": 500,
                "end_ms": 1700,
                "measure_start": 1,
                "measure_end": 2,
                "affected_clip_ids": [11001, 12001],
            },
            {
                "id": 202,
                "issue_type": "sibilance",
                "requires_user_action": False,
                "track_id": 11,
                "start_ms": 800,
                "end_ms": 1200,
                "measure_start": 1,
                "measure_end": 1,
                "affected_clip_ids": [11001],
            },
        ],
        suggestion_payload={
            "activeIssueId": "200010-issue-202",
            "navigationOrder": ["200010-issue-202", "200010-issue-101"],
            "issues": [
                {
                    "issueId": "200010-issue-202",
                    "issueType": "sibilance",
                    "startMs": 800,
                    "endMs": 1200,
                    "trackId": 11,
                    "bubbleTarget": "track",
                    "uiMode": "eq_ai",
                    "summary": "Sibilance",
                    "explanation": "Auto fix",
                    "previewBands": [],
                    "actions": [],
                    "markers": [],
                },
                {
                    "issueId": "200010-issue-101",
                    "issueType": "band_overlap",
                    "startMs": 500,
                    "endMs": 1700,
                    "trackId": 11,
                    "bubbleTarget": "track",
                    "uiMode": "eq_ai",
                    "summary": "Band overlap",
                    "explanation": "Needs plan input",
                    "previewBands": [],
                    "actions": [],
                    "markers": [],
                },
            ],
            "suggestions": [],
        },
    )

    projections = build_workflow_projections(state).model_dump(mode="json")

    assert projections["runtime_status"]["current_node"] == "wait_user_plan_input"
    assert projections["suggestion_group"]["region_id"] == 202
    assert projections["plan_state"] is None
    assert state["ranked_candidate_ids"] == [101]


def test_start_workflow_job_persists_track_eq_map_in_timeline_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )

    start_workflow_job(
        WorkflowStartPayload(
            job_id=29991,
            project_id=39991,
            project_snapshot=build_project_snapshot(
                track_ids=[12],
                track_eqs=[
                    {
                        "track_id": 12,
                        "bands": [
                            {
                                "band_order": 1,
                                "eq_type": "BELL",
                                "frequency_hz": 4200,
                                "q": 1.2,
                                "gain_delta_db": -2.5,
                            }
                        ],
                    }
                ],
            ),
        )
    )

    snapshot = get_workflow_snapshot_store().get_snapshot("29991-timeline-snapshot")

    assert snapshot is not None
    assert snapshot.track_eq_map == {
        "12": [
            {
                "band_order": 1,
                "eq_type": "BELL",
                "frequency_hz": 4200,
                "q": 1.2,
                "gain_delta_db": -2.5,
            }
        ]
    }


def test_worker_start_dispatch_materializes_track_clipping_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20002,
            project_id=30002,
            project_snapshot=build_project_snapshot(track_ids=[8]),
            issue_types=["clipping"],
        )
    )
    resumed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20002,
            project_id=30002,
            dispatch_type="start",
        )
    )

    assert "track_clipping" in resumed["detected_issues"]
    assert resumed["current_node"] == "finalize_output"
    assert resumed["runtime_status"] == "completed"
    clipping_issue = next(
        issue
        for issue in resumed["suggestion_payload"]["issues"]
        if issue["issueType"] == "track_clipping"
    )
    assert clipping_issue["uiMode"] == "master_limiter"


def test_worker_start_dispatch_materializes_sibilance_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    vocal_like = (
        0.26 * np.sin(2 * np.pi * 330 * time_axis)
        + 0.22 * np.sin(2 * np.pi * 520 * time_axis)
        + 0.24 * np.sin(2 * np.pi * 3600 * time_axis)
        + 0.48 * np.sin(2 * np.pi * 6800 * time_axis)
    ).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "dispatch-sibilance-autofix.wav"
    sf.write(audio_path, vocal_like, sample_rate)
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20003,
            project_id=30003,
            project_snapshot={
                "duration_ms": 4800,
                "bpm": 120,
                "numerator": 4,
                "denominator": 4,
                "tracks": [{"track_id": 8, "name": "Track 8"}],
                "clips": [
                    {
                        "clip_id": _clip_id(8, 1),
                        "track_id": 8,
                        "start_ms": 0,
                        "end_ms": 4800,
                        "audio_metadata_id": _register_audio_metadata(
                            _audio_metadata_id(8, 1),
                            str(audio_path),
                        ),
                        "audio_start_ms": 0,
                        "audio_duration_ms": 4800,
                    }
                ],
            },
            issue_types=["sibilance"],
        )
    )

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20003,
            project_id=30003,
            dispatch_type="start",
        )
    )
    assert result["current_node"] == "finalize_output"
    assert result["runtime_status"] == "completed"
    assert result["ranked_candidate_ids"] == []
    sibilance_region = next(
        region for region in result["analysis_regions"] if region["issue_type"] == "sibilance"
    )
    assert sibilance_region["requires_user_action"] is False
    assert any(
        issue["issueType"] == "band_overlap"
        for issue in result["suggestion_payload"]["issues"]
    )
    assert sibilance_issue["uiMode"] == "eq_ai"


def test_job_status_api_does_not_expose_preview_for_non_preview_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    vocal_like = (
        0.26 * np.sin(2 * np.pi * 330 * time_axis)
        + 0.22 * np.sin(2 * np.pi * 520 * time_axis)
        + 0.24 * np.sin(2 * np.pi * 3600 * time_axis)
        + 0.48 * np.sin(2 * np.pi * 6800 * time_axis)
    ).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "dispatch-sibilance-autofix-status.wav"
    sf.write(audio_path, vocal_like, sample_rate)
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=200032,
            project_id=300032,
            project_snapshot={
                "duration_ms": 4800,
                "bpm": 120,
                "numerator": 4,
                "denominator": 4,
                "tracks": [{"track_id": 8, "name": "Track 8"}],
                "clips": [
                    {
                        "clip_id": _clip_id(8, 1),
                        "track_id": 8,
                        "start_ms": 0,
                        "end_ms": 4800,
                        "audio_metadata_id": _register_audio_metadata(
                            _audio_metadata_id(8, 1),
                            str(audio_path),
                        ),
                        "audio_start_ms": 0,
                        "audio_duration_ms": 4800,
                    }
                ],
            },
            issue_types=["sibilance"],
        )
    )
    store = get_workflow_job_store()
    stored = store.get_job(200032)
    assert stored is not None
    auto_state = build_workflow_initial_state(
        job_id=200032,
        project_id=300032,
        timeline_snapshot_id=stored.timeline_snapshot_id,
        project_duration_ms=4800,
        clip_index=stored.state_snapshot["clip_index"],
        track_ids=[8],
        phase="completed",
        current_node="finalize_output",
        runtime_status="completed",
        durable_status="COMPLETED",
        analysis_regions=[
            {
                "id": 9001,
                "issue_type": "track_clipping",
                "requires_user_action": False,
                "track_id": 8,
                "start_ms": 600,
                "end_ms": 1400,
                "measure_start": 1,
                "measure_end": 2,
                "band_low_hz": 4500,
                "band_high_hz": 7800,
            }
        ],
        suggestion_payload={
            "activeIssueId": "200032-issue-9001",
            "navigationOrder": ["200032-issue-9001"],
            "issues": [
                {
                    "issueId": "200032-issue-9001",
                    "issueType": "track_clipping",
                    "startMs": 600,
                    "endMs": 1400,
                    "trackId": 8,
                    "bubbleTarget": "master",
                    "uiMode": "master_limiter",
                    "summary": "Track clipping detected",
                    "explanation": "Master limiter only",
                    "previewBands": [],
                    "actions": [{"type": "apply_master_limiter", "estimatedGainReductionDb": 1.5}],
                    "markers": [],
                }
            ],
            "suggestions": [],
        },
        preview_required=False,
        has_auto_fixable_eq_issues=False,
        user_action_required=False,
        auto_preview_generated=False,
    )
    store.save_graph_state(auto_state)

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/200032")

    assert response.status_code == 200
    projections = response.json()["projections"]
    assert projections["user_action_required"] is False
    assert projections["preview_required"] is False
    assert projections["auto_preview_generated"] is False
    assert projections["preview_render"] is None


def test_preview_compare_api_rejects_non_preview_issue_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    vocal_like = (
        0.26 * np.sin(2 * np.pi * 330 * time_axis)
        + 0.22 * np.sin(2 * np.pi * 520 * time_axis)
        + 0.24 * np.sin(2 * np.pi * 3600 * time_axis)
        + 0.48 * np.sin(2 * np.pi * 6800 * time_axis)
    ).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "dispatch-sibilance-autofix-compare.wav"
    sf.write(audio_path, vocal_like, sample_rate)
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=200033,
            project_id=300033,
            project_snapshot={
                "duration_ms": 4800,
                "bpm": 120,
                "numerator": 4,
                "denominator": 4,
                "tracks": [{"track_id": 8, "name": "Track 8"}],
                "clips": [
                    {
                        "clip_id": _clip_id(8, 1),
                        "track_id": 8,
                        "start_ms": 0,
                        "end_ms": 4800,
                        "audio_metadata_id": _register_audio_metadata(
                            _audio_metadata_id(8, 1),
                            str(audio_path),
                        ),
                        "audio_start_ms": 0,
                        "audio_duration_ms": 4800,
                    }
                ],
            },
            issue_types=["sibilance"],
        )
    )
    store = get_workflow_job_store()
    stored = store.get_job(200033)
    assert stored is not None
    auto_state = build_workflow_initial_state(
        job_id=200033,
        project_id=300033,
        timeline_snapshot_id=stored.timeline_snapshot_id,
        project_duration_ms=4800,
        clip_index=stored.state_snapshot["clip_index"],
        track_ids=[8],
        phase="completed",
        current_node="finalize_output",
        runtime_status="completed",
        durable_status="COMPLETED",
        analysis_regions=[
            {
                "id": 9002,
                "issue_type": "track_clipping",
                "requires_user_action": False,
                "track_id": 8,
                "start_ms": 700,
                "end_ms": 1500,
                "measure_start": 1,
                "measure_end": 2,
                "band_low_hz": 4500,
                "band_high_hz": 7800,
            }
        ],
        suggestion_payload={
            "activeIssueId": "200033-issue-9002",
            "navigationOrder": ["200033-issue-9002"],
            "issues": [
                {
                    "issueId": "200033-issue-9002",
                    "issueType": "track_clipping",
                    "startMs": 700,
                    "endMs": 1500,
                    "trackId": 8,
                    "bubbleTarget": "master",
                    "uiMode": "master_limiter",
                    "summary": "Track clipping detected",
                    "explanation": "Master limiter only",
                    "previewBands": [],
                    "actions": [{"type": "apply_master_limiter", "estimatedGainReductionDb": 1.5}],
                    "markers": [],
                }
            ],
            "suggestions": [],
        },
        preview_required=False,
        has_auto_fixable_eq_issues=False,
        user_action_required=False,
        auto_preview_generated=False,
    )
    store.save_graph_state(auto_state)

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/200033/preview-compare")

    assert response.status_code == 404


def test_worker_start_dispatch_keeps_band_overlap_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    vocal_like = (
        0.26 * np.sin(2 * np.pi * 330 * time_axis)
        + 0.22 * np.sin(2 * np.pi * 520 * time_axis)
        + 0.24 * np.sin(2 * np.pi * 3600 * time_axis)
        + 0.48 * np.sin(2 * np.pi * 6800 * time_axis)
    ).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "dispatch-mixed-sibilance.wav"
    sf.write(audio_path, vocal_like, sample_rate)
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20015,
            project_id=30015,
            project_snapshot={
                "duration_ms": 4800,
                "bpm": 120,
                "numerator": 4,
                "denominator": 4,
                "tracks": [
                    {"track_id": 8, "name": "Track 8"},
                    {"track_id": 9, "name": "Track 9"},
                ],
                "clips": [
                    {
                        "clip_id": _clip_id(8, 1),
                        "track_id": 8,
                        "start_ms": 0,
                        "end_ms": 4800,
                        "audio_metadata_id": _register_audio_metadata(
                            _audio_metadata_id(8, 1),
                            str(audio_path),
                        ),
                        "audio_start_ms": 0,
                        "audio_duration_ms": 4800,
                    },
                    {
                        "clip_id": _clip_id(9, 2),
                        "track_id": 9,
                        "start_ms": 900,
                        "end_ms": 3100,
                        "audio_metadata_id": _register_audio_metadata(
                            _audio_metadata_id(9, 2),
                            _ensure_test_audio_file(9, vocal_like=False),
                        ),
                        "audio_start_ms": 0,
                        "audio_duration_ms": 4800,
                    },
                ],
            },
            issue_types=["band_overlap", "sibilance"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20015,
            project_id=30015,
            dispatch_type="start",
        )
    )
    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20015,
            project_id=30015,
            dispatch_type="resume_plan_input",
            **build_plan_input(waiting),
        )
    )
    assert result["current_node"] == "finalize_output"
    assert result["preview_status"] == "READY"
    assert result["preview_excerpt_start_ms"] is not None
    assert result["preview_excerpt_end_ms"] is not None
    assert result["preview_excerpt_end_ms"] > result["preview_excerpt_start_ms"]
    preview_band = result["suggestion_payload"]["suggestions"][0]["previewBands"][0]
    assert preview_band["jobId"] == 20015
    assert any(
        issue["issueType"] == "band_overlap"
        for issue in result["suggestion_payload"]["issues"]
    )
    assert result["auto_fix_recipe_artifact_id"] is None


def test_worker_rejects_plan_resume_from_completed_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20004,
            project_id=30004,
            project_snapshot=build_project_snapshot(track_ids=[5, 6]),
            issue_types=["band_overlap"],
        )
    )
    started = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20004,
            project_id=30004,
            dispatch_type="start",
        )
    )

    completed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20004,
            project_id=30004,
            dispatch_type="resume_plan_input",
            **build_plan_input(started),
        )
    )
    assert completed["phase"] == "completed"

    failed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20004,
            project_id=30004,
            dispatch_type="resume_plan_input",
            **build_plan_input(started),
        )
    )

    assert failed["current_node"] == "fail_workflow"
    assert failed["runtime_status"] == "failed"
    assert failed["failure_code"] == "INVALID_RESUME_PHASE"


def test_worker_rejects_plan_resume_without_selected_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20005,
            project_id=30005,
            project_snapshot=build_project_snapshot(track_ids=[3, 7]),
            issue_types=["band_overlap"],
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20005,
            project_id=30005,
            dispatch_type="start",
        )
    )
    stored = get_workflow_job_store().get_job(20005)
    assert stored is not None
    preserve_clip_id = build_plan_input(stored.state_snapshot)["preserve_clip_id"]

    failed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20005,
            project_id=30005,
            dispatch_type="resume_plan_input",
            preserve_clip_id=preserve_clip_id,
        )
    )

    assert failed["current_node"] == "fail_workflow"
    assert failed["runtime_status"] == "failed"
    assert failed["failure_code"] == "MISSING_SELECTED_REGION"


def test_worker_rejects_plan_resume_without_preserve_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20006,
            project_id=30006,
            project_snapshot=build_project_snapshot(track_ids=[4, 9]),
            issue_types=["band_overlap"],
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20006,
            project_id=30006,
            dispatch_type="start",
        )
    )
    stored = get_workflow_job_store().get_job(20006)
    assert stored is not None
    selected_region_id = build_plan_input(stored.state_snapshot)["selected_region_id"]

    failed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20006,
            project_id=30006,
            dispatch_type="resume_plan_input",
            selected_region_id=selected_region_id,
        )
    )

    assert failed["current_node"] == "fail_workflow"
    assert failed["runtime_status"] == "failed"
    assert failed["failure_code"] == "MISSING_PRESERVE_CLIP"


def test_worker_rejects_plan_resume_for_non_ranked_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20016,
            project_id=30016,
            project_snapshot=build_project_snapshot(track_ids=[8, 9]),
            issue_types=["band_overlap", "master_clipping"],
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20016,
            project_id=30016,
            dispatch_type="start",
        )
    )
    stored = get_workflow_job_store().get_job(20016)
    assert stored is not None
    non_ranked_region = next(
        region
        for region in stored.state_snapshot["analysis_regions"]
        if region["issue_type"] == "master_clipping"
    )
    preserve_clip_id = non_ranked_region["affected_clip_ids"][0]

    failed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20016,
            project_id=30016,
            dispatch_type="resume_plan_input",
            selected_region_id=non_ranked_region["id"],
            preserve_clip_id=preserve_clip_id,
        )
    )

    assert failed["current_node"] == "fail_workflow"
    assert failed["runtime_status"] == "failed"
    assert failed["failure_code"] == "INVALID_SELECTED_REGION"


def test_worker_rejects_plan_resume_from_non_waiting_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = get_workflow_job_store()
    store.create_pending_job(
        {
            "job_id": 20007,
            "project_id": 30007,
            "phase": "analysis_result_persisted",
            "current_node": "persist_analysis_result",
            "progress": 95,
            "runtime_status": "running",
            "durable_status": "RUNNING",
            "timeline_snapshot_id": "20007-timeline-snapshot",
            "langgraph_thread_id": "lg-thread:20007",
        }
    )

    failed = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20007,
            project_id=30007,
            dispatch_type="resume_plan_input",
            selected_region_id=1,
            preserve_clip_id=1,
        )
    )

    assert failed["current_node"] == "fail_workflow"
    assert failed["runtime_status"] == "failed"
    assert failed["failure_code"] == "INVALID_RESUME_PHASE"


def test_start_api_enqueues_without_running_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    queued_messages: list[WorkflowDispatchMessage] = []
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: queued_messages.append(message),
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/start",
        json={
            "job_id": 20009,
            "project_id": 30009,
            "project_snapshot": build_project_snapshot(track_ids=[1, 2]),
            "issue_types": ["band_overlap"],
            "requested_by": 101,
        },
    )

    assert response.status_code == 200
    assert response.json()["job"]["dispatch_type"] == "start"
    assert len(queued_messages) == 1
    assert queued_messages[0].job_id == 20009
    stored = get_workflow_job_store().get_job(20009)
    assert stored is not None
    assert stored.phase == "queued"
    assert stored.status == "REQUESTED"
    assert "project_snapshot" not in stored.state_snapshot


def test_start_api_allows_cors_preflight() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/internal/workflow/jobs/start",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_start_api_persists_snapshot_only_in_snapshot_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    payload = WorkflowStartPayload(
        job_id=20010,
        project_id=30010,
        project_snapshot=build_project_snapshot(track_ids=[3, 4]),
        issue_types=["band_overlap"],
    )

    start_workflow_job(payload)

    stored = get_workflow_job_store().get_job(20010)
    snapshot = get_workflow_snapshot_store().get_snapshot("20010-timeline-snapshot")

    assert stored is not None
    assert snapshot is not None
    assert stored.timeline_snapshot_id == snapshot.id
    assert "project_snapshot" not in stored.state_snapshot
    assert snapshot.snapshot["clips"][0]["clip_id"] == _clip_id(3, 1)
    assert "master_audio_status" not in stored.state_snapshot
    assert "master_audio_object_key" not in stored.state_snapshot


def test_start_api_returns_not_found_when_be_job_row_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = get_workflow_job_store()

    def _raise_missing_row(state: dict) -> None:
        raise KeyError(f"Workflow job does not exist: {state['job_id']}")

    monkeypatch.setattr(store, "create_pending_job", _raise_missing_row)
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/start",
        json={
            "job_id": 20031,
            "project_id": 30031,
            "project_snapshot": build_project_snapshot(track_ids=[5, 6]),
            "issue_types": ["band_overlap"],
        },
    )

    assert response.status_code == 404
    assert "Workflow job does not exist: 20031" in response.json()["detail"]


def test_resume_api_infers_dispatch_type_from_waiting_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued_messages: list[WorkflowDispatchMessage] = []
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: queued_messages.append(message),
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20011,
            project_id=30011,
            project_snapshot=build_project_snapshot(track_ids=[9, 10]),
            issue_types=["band_overlap"],
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20011,
            project_id=30011,
            dispatch_type="start",
        )
    )
    stored = get_workflow_job_store().get_job(20011)
    assert stored is not None
    plan_input = build_plan_input(stored.state_snapshot)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/resume",
        json={
            "job_id": 20011,
            "project_id": 30011,
            **plan_input,
        },
    )

    assert response.status_code == 200
    assert response.json()["job"]["dispatch_type"] == "resume_plan_input"
    assert len(queued_messages) == 2
    assert queued_messages[-1].selected_region_id == plan_input["selected_region_id"]
    assert queued_messages[-1].preserve_clip_id == plan_input["preserve_clip_id"]


def test_resume_api_rejects_batch_resume_without_user_prompt() -> None:
    store = get_workflow_job_store()
    store.create_pending_job(build_batch_waiting_state(job_id=20040, project_id=30040))
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/resume",
        json={
            "job_id": 20040,
            "project_id": 30040,
            "regionSelections": [
                {"regionId": 101, "preserveTrackId": 11},
                {"regionId": 102, "preserveTrackId": 11},
            ],
        },
    )

    assert response.status_code == 422
    assert "userPrompt is required for batch" in response.json()["detail"]


def test_resume_api_rejects_duplicate_batch_region_ids() -> None:
    store = get_workflow_job_store()
    store.create_pending_job(build_batch_waiting_state(job_id=20041, project_id=30041))
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/resume",
        json={
            "job_id": 20041,
            "project_id": 30041,
            "userPrompt": "Keep the vocal intact.",
            "regionSelections": [
                {"regionId": 101, "preserveTrackId": 11},
                {"regionId": 101, "preserveTrackId": 11},
            ],
        },
    )

    assert response.status_code == 422
    assert "duplicate regionId" in response.json()["detail"]


def test_worker_generates_batch_candidate_plans_and_skips_simple_critic() -> None:
    store = get_workflow_job_store()
    store.create_pending_job(build_batch_waiting_state(job_id=20042, project_id=30042))

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20042,
            project_id=30042,
            dispatch_type="resume_plan_input",
            selected_region_selections=[
                {"regionId": 101, "preserveTrackId": 11},
                {"regionId": 102, "preserveTrackId": 11},
            ],
            user_feedback_message="Keep the vocal intact and only move the masking track.",
        )
    )

    assert result["phase"] == "completed"
    assert result["request_mode"] == "batch"
    assert result["preview_required"] is True
    assert result["preview_status"] == "READY"
    assert len(result["batch_candidate_plans"]) == 2
    assert result["batch_failed_regions"] == []
    assert len(result["batch_final_track_envelopes"]) >= 1
    assert all(
        envelope["trackId"] == 12 for envelope in result["batch_final_track_envelopes"]
    )
    assert result["batch_candidate_plans"][0]["regionId"] == 101
    assert result["batch_candidate_plans"][0]["criticSkipped"] is True
    assert result["batch_candidate_plans"][0]["criticResult"] is None
    assert result["batch_candidate_plans"][0]["mergeStatus"] == "MERGED"
    assert result["batch_candidate_plans"][1]["regionId"] == 102
    assert result["batch_candidate_plans"][1]["criticSkipped"] is False
    assert result["batch_candidate_plans"][1]["criticResult"] == "PASS"
    assert result["batch_candidate_plans"][1]["mergeStatus"] == "MERGED"
    assert result["batch_validation_summary"] == {
        "requestedRegions": 2,
        "successfulRegions": 2,
        "failedRegions": 0,
        "criticRunRegions": 1,
        "criticSkippedRegions": 1,
        "mergedEnvelopeCount": len(result["batch_final_track_envelopes"]),
        "failedEnvelopeCount": 0,
    }
    assert result["suggestion_payload"]["activeIssueId"] == "20042-batch-envelope-1"
    assert len(result["suggestion_payload"]["issues"]) == len(result["batch_final_track_envelopes"])
    assert result["suggestion_payload"]["suggestions"]
    total_preview_band_count = sum(
        len(suggestion.get("previewBands", []))
        for suggestion in result["suggestion_payload"]["suggestions"]
        if isinstance(suggestion, dict)
    )
    assert total_preview_band_count >= 1

    projections = build_workflow_projections(result)
    assert projections.plan_state is not None
    assert projections.plan_state.request_mode == "batch"
    assert len(projections.plan_state.candidatePlans) == 2
    assert projections.plan_state.failedRegions == []
    assert len(projections.plan_state.finalTrackEnvelopes) == len(result["batch_final_track_envelopes"])
    assert projections.plan_state.validationSummary["criticRunRegions"] == 1


def test_worker_keeps_single_resume_path_when_batch_fields_are_absent() -> None:
    store = get_workflow_job_store()
    store.create_pending_job(build_batch_waiting_state(job_id=20044, project_id=30044))

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20044,
            project_id=30044,
            dispatch_type="resume_plan_input",
            selected_region_id=101,
            preserve_clip_id=11001,
            user_feedback_message="Keep the vocal intact.",
        )
    )

    assert result["phase"] == "completed"
    assert result.get("request_mode") == "single"
    assert result["selected_region_id"] == 101
    assert result["batch_candidate_plans"] == []
    assert result["batch_failed_regions"] == []
    assert result["preview_status"] == "READY"


def test_worker_excludes_failed_batch_region_and_keeps_successes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PartiallyFailingPlanningClient:
        def generate_plan(
            self,
            *,
            selected_region_id: int,
            preserve_clip_id: int,
            user_feedback_message: str | None,
            selection_context: dict[str, object],
            region: dict[str, object],
            clip_context: list[dict[str, object]],
            revision_notes: list[str],
        ) -> PlanningLLMResponse:
            if selected_region_id == 102:
                raise PlanningLLMError("PLANNING_TEST_FAILURE", "planner failed for region 102")
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "batch success",
                    "strategySummary": "batch success summary",
                    "summary": "batch success suggestion",
                    "explanation": "batch success explanation",
                    "candidate": {
                        "action": {
                            "actionType": "DYNAMIC_EQ",
                            "targetScope": "TRACK",
                            "targetTrackId": 12,
                            "targetClipId": None,
                            "startMs": 0,
                            "endMs": 700,
                            "bandLowHz": 260,
                            "bandHighHz": 520,
                            "gainDeltaDb": -2.5,
                            "params": {"threshold": -19, "ratio": 2.0},
                        }
                    },
                }
            )

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _PartiallyFailingPlanningClient(),
    )
    store = get_workflow_job_store()
    store.create_pending_job(build_batch_waiting_state(job_id=20043, project_id=30043))

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20043,
            project_id=30043,
            dispatch_type="resume_plan_input",
            selected_region_selections=[
                {"regionId": 101, "preserveTrackId": 11},
                {"regionId": 102, "preserveTrackId": 11},
            ],
            user_feedback_message="Keep the vocal intact and only move the masking track.",
        )
    )

    assert result["phase"] == "completed"
    assert len(result["batch_candidate_plans"]) == 1
    assert result["batch_candidate_plans"][0]["regionId"] == 101
    assert result["batch_candidate_plans"][0]["mergeStatus"] == "MERGED"
    assert len(result["batch_failed_regions"]) == 1
    assert result["batch_failed_regions"][0]["regionId"] == 102
    assert result["batch_failed_regions"][0]["reasonCode"] == "PLANNING_TEST_FAILURE"
    assert result["batch_validation_summary"]["successfulRegions"] == 1
    assert result["batch_validation_summary"]["failedRegions"] == 1
    assert result["batch_validation_summary"]["mergedEnvelopeCount"] == 1
    assert result["preview_status"] == "READY"
    assert len(result["suggestion_payload"]["issues"]) == 1


def test_worker_merges_adjacent_batch_candidates_into_one_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MergingPlanningClient:
        def generate_plan(
            self,
            *,
            selected_region_id: int,
            preserve_clip_id: int,
            user_feedback_message: str | None,
            selection_context: dict[str, object],
            region: dict[str, object],
            clip_context: list[dict[str, object]],
            revision_notes: list[str],
        ) -> PlanningLLMResponse:
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "merge batch",
                    "strategySummary": "merge batch summary",
                    "summary": "merge batch suggestion",
                    "explanation": "merge batch explanation",
                    "candidate": {
                        "action": {
                            "actionType": "DYNAMIC_EQ",
                            "targetScope": "TRACK",
                            "targetTrackId": 12,
                            "targetClipId": None,
                            "startMs": 0 if selected_region_id == 101 else 80,
                            "endMs": 700 if selected_region_id == 101 else 760,
                            "bandLowHz": 260 if selected_region_id == 101 else 300,
                            "bandHighHz": 520 if selected_region_id == 101 else 560,
                            "gainDeltaDb": -2.5 if selected_region_id == 101 else -1.8,
                            "params": {"threshold": -19, "ratio": 2.0, "q": 1.4},
                        }
                    },
                }
            )

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _MergingPlanningClient(),
    )
    store = get_workflow_job_store()
    waiting_state = build_batch_waiting_state(job_id=20046, project_id=30046)
    waiting_state["analysis_regions"][1]["start_ms"] = 80
    waiting_state["analysis_regions"][1]["end_ms"] = 760
    waiting_state["analysis_regions"][1]["band_low_hz"] = 300
    waiting_state["analysis_regions"][1]["band_high_hz"] = 560
    store.create_pending_job(waiting_state)

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20046,
            project_id=30046,
            dispatch_type="resume_plan_input",
            selected_region_selections=[
                {"regionId": 101, "preserveTrackId": 11},
                {"regionId": 102, "preserveTrackId": 11},
            ],
            user_feedback_message="Merge adjacent cuts on the masking track.",
        )
    )

    assert result["phase"] == "completed"
    assert len(result["batch_final_track_envelopes"]) == 1
    assert result["batch_final_track_envelopes"][0]["sourceRegionIds"] == [101, 102]
    assert len(result["suggestion_payload"]["issues"]) == 1
    assert len(result["suggestion_payload"]["suggestions"][0]["previewBands"]) == 2


def test_worker_keeps_dynamic_eq_and_eq_cut_in_separate_batch_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MixedActionPlanningClient:
        def generate_plan(
            self,
            *,
            selected_region_id: int,
            preserve_clip_id: int,
            user_feedback_message: str | None,
            selection_context: dict[str, object],
            region: dict[str, object],
            clip_context: list[dict[str, object]],
            revision_notes: list[str],
        ) -> PlanningLLMResponse:
            action_type = "DYNAMIC_EQ" if selected_region_id == 101 else "EQ_CUT"
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "mixed action batch",
                    "strategySummary": "mixed action batch summary",
                    "summary": "mixed action batch suggestion",
                    "explanation": "mixed action batch explanation",
                    "candidate": {
                        "action": {
                            "actionType": action_type,
                            "targetScope": "TRACK",
                            "targetTrackId": 12,
                            "targetClipId": None,
                            "startMs": 0 if selected_region_id == 101 else 80,
                            "endMs": 700 if selected_region_id == 101 else 760,
                            "bandLowHz": 260 if selected_region_id == 101 else 300,
                            "bandHighHz": 520 if selected_region_id == 101 else 560,
                            "gainDeltaDb": -2.5 if selected_region_id == 101 else -1.8,
                            "params": {"threshold": -19, "ratio": 2.0},
                        }
                    },
                }
            )

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _MixedActionPlanningClient(),
    )
    store = get_workflow_job_store()
    waiting_state = build_batch_waiting_state(job_id=20045, project_id=30045)
    waiting_state["analysis_regions"][1]["start_ms"] = 80
    waiting_state["analysis_regions"][1]["end_ms"] = 760
    waiting_state["analysis_regions"][1]["band_low_hz"] = 300
    waiting_state["analysis_regions"][1]["band_high_hz"] = 560
    store.create_pending_job(waiting_state)

    result = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20045,
            project_id=30045,
            dispatch_type="resume_plan_input",
            selected_region_selections=[
                {"regionId": 101, "preserveTrackId": 11},
                {"regionId": 102, "preserveTrackId": 11},
            ],
            user_feedback_message="Keep separate action families.",
        )
    )

    assert result["phase"] == "completed"
    assert len(result["batch_final_track_envelopes"]) == 2
    assert {
        envelope["actionType"] for envelope in result["batch_final_track_envelopes"]
    } == {"DYNAMIC_EQ", "EQ_CUT"}
    assert len(result["suggestion_payload"]["issues"]) == 2


def test_feedback_api_uses_path_job_id_for_resume_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued_messages: list[WorkflowDispatchMessage] = []
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: queued_messages.append(message),
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20026,
            project_id=30026,
            project_snapshot=build_project_snapshot(track_ids=[13, 14]),
            issue_types=["band_overlap"],
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20026,
            project_id=30026,
            dispatch_type="start",
        )
    )
    stored = get_workflow_job_store().get_job(20026)
    assert stored is not None
    plan_input = build_plan_input(stored.state_snapshot)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/20026/feedback",
        json={
            "project_id": 30026,
            "issue_id": "issue-20026-1",
            "action_type": "apply_master_limiter",
            "action_payload": {"estimatedGainReductionDb": 1.5, "targetCeilingDbtp": -1.0},
            "user_decision": "RESUME",
            **plan_input,
        },
    )

    assert response.status_code == 200
    assert response.json()["job"]["dispatch_type"] == "resume_plan_input"
    assert queued_messages[-1].job_id == 20026
    assert queued_messages[-1].issue_id == "issue-20026-1"
    assert queued_messages[-1].action_type == "apply_master_limiter"
    assert queued_messages[-1].action_payload == {"estimatedGainReductionDb": 1.5, "targetCeilingDbtp": -1.0}
    assert queued_messages[-1].user_decision == "RESUME"


def test_feedback_api_records_confirm_decision_in_status_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20027,
            project_id=30027,
            project_snapshot=build_project_snapshot(track_ids=[15, 16]),
            issue_types=["band_overlap"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20027,
            project_id=30027,
            dispatch_type="start",
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20027,
            project_id=30027,
            dispatch_type="resume_plan_input",
            user_decision="RESUME",
            **build_plan_input(waiting),
        )
    )
    client = TestClient(create_app())

    feedback_response = client.post(
        "/api/v1/internal/workflow/jobs/20027/feedback",
        json={
            "project_id": 30027,
            "user_decision": "CONFIRM",
            "user_feedback_message": "preview accepted",
        },
    )

    assert feedback_response.status_code == 200
    assert feedback_response.json()["job"]["dispatch_type"] == "confirm"

    status_response = client.get("/api/v1/internal/workflow/jobs/20027")

    assert status_response.status_code == 200
    feedback_event = status_response.json()["projections"]["feedback_event"]
    assert feedback_event["payload"]["decision"] == "CONFIRM"
    assert feedback_event["payload"]["user_feedback_message"] == "preview accepted"


def test_job_status_api_returns_job_and_projections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20012,
            project_id=30012,
            project_snapshot=build_project_snapshot(track_ids=[10, 11]),
            issue_types=["band_overlap"],
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20012,
            project_id=30012,
            dispatch_type="start",
        )
    )
    client = TestClient(create_app())

    response = client.get("/api/v1/internal/workflow/jobs/20012")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["id"] == 20012
    assert body["projections"]["analysis_job"]["id"] == 20012
    assert "master_audio" not in body["projections"]
    assert body["projections"]["analysis_regions"][0]["measure_start"] == 1
    overlap_projection = next(
        (
            region
            for region in body["projections"]["analysis_regions"]
            if region["issue_type"] == "BAND_OVERLAP"
        ),
        None,
    )
    assert overlap_projection is not None
    assert overlap_projection["band_overlap_subtype"] in {
        "low_mid_overlap",
        "body_overlap",
        "upper_mid_overlap",
        "presence_overlap",
    }
    assert body["projections"]["suggestion_group"] is not None
    assert body["projections"]["suggestion_group"]["suggestions"] == []


def test_job_status_api_exposes_master_context_preview_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20022,
            project_id=30022,
            project_snapshot=build_project_snapshot(track_ids=[11, 12]),
            issue_types=["band_overlap"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20022,
            project_id=30022,
            dispatch_type="start",
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20022,
            project_id=30022,
            dispatch_type="resume_plan_input",
            **build_plan_input(waiting),
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/20022")

    assert response.status_code == 200
    preview = response.json()["projections"]["preview_render"]
    assert preview["status"] == "READY"
    assert preview["preview_target_region"] is not None
    assert preview["preview_action_track"] is not None
    assert preview["preview_action_type"] == "DYNAMIC_EQ"
    assert preview["preview_excerpt_range"]["start_ms"] <= preview["preview_region_start_ms"]
    assert preview["preview_excerpt_range"]["end_ms"] >= preview["preview_region_end_ms"]


def test_job_status_api_exposes_issue_navigation_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=200221,
            project_id=300221,
            project_snapshot=build_project_snapshot(track_ids=[11, 12]),
            issue_types=["band_overlap"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=200221,
            project_id=300221,
            dispatch_type="start",
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=200221,
            project_id=300221,
            dispatch_type="resume_plan_input",
            **build_plan_input(waiting),
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/200221")

    assert response.status_code == 200
    suggestion_group = response.json()["projections"]["suggestion_group"]
    assert suggestion_group is not None
    assert suggestion_group["suggestions"]
    stored = get_workflow_job_store().get_job(200221)
    assert stored is not None
    payload = stored.state_snapshot["suggestion_payload"]
    assert payload["activeIssueId"]
    assert len(payload["issues"]) == 1
    assert payload["issues"][0]["uiMode"] == "eq_ai"


def test_preview_compare_api_returns_visual_compare_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20023,
            project_id=30023,
            project_snapshot=build_project_snapshot(track_ids=[11, 12]),
            issue_types=["band_overlap"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20023,
            project_id=30023,
            dispatch_type="start",
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20023,
            project_id=30023,
            dispatch_type="resume_plan_input",
            **build_plan_input(waiting),
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/20023/preview-compare")

    assert response.status_code == 200
    body = response.json()
    assert body["preview"]["status"] == "READY"
    assert body["issue_overlay"]["kind"] == "band_overlap"
    assert len(body["before_excerpt"]["waveform_points"]) == 1200
    assert len(body["after_excerpt"]["waveform_points"]) == 1200
    assert len(body["before_excerpt"]["spectrum_bins"]) == 96
    assert body["before_region_summary"]["duration_ms"] > 0
    assert body["before_region_summary"]["duration_ms"] < body["before_excerpt"]["duration_ms"]
    assert body["after_region_summary"]["duration_ms"] == body["before_region_summary"]["duration_ms"]
    assert len(body["before_region_summary"]["waveform_points"]) == 1200
    assert len(body["prompt_feedback_hints"]) >= 2


def test_inspection_report_api_returns_planner_critic_and_preview_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=200231,
            project_id=300231,
            project_snapshot=build_project_snapshot(track_ids=[11, 12]),
            issue_types=["band_overlap"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=200231,
            project_id=300231,
            dispatch_type="start",
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=200231,
            project_id=300231,
            dispatch_type="resume_plan_input",
            **build_plan_input(waiting),
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/200231/inspection-report")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["id"] == 200231
    assert body["snapshot"]["tracks"]
    assert body["analysis"]["regions"]
    assert body["planner"]["raw_text"]
    assert body["planner"]["plan_payload"]["candidate"]["action"]["actionType"] == "DYNAMIC_EQ"
    assert body["critic"]["raw_text"]
    assert body["preview"]["compare"]["issue_overlay"]["kind"] == "band_overlap"
    assert body["preview"]["audio"]["before_excerpt_wav_uri"].startswith("data:audio/wav;base64,")
    assert body["preview"]["audio"]["after_excerpt_wav_uri"].startswith("data:audio/wav;base64,")


def test_preview_compare_api_rejects_non_ready_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20024,
            project_id=30024,
            project_snapshot=build_project_snapshot(track_ids=[21, 22]),
            issue_types=["band_overlap"],
        )
    )
    store = get_workflow_job_store()
    record = store.get_job(20024)
    assert record is not None
    state = build_workflow_initial_state(
        job_id=20024,
        project_id=30024,
        timeline_snapshot_id=record.timeline_snapshot_id,
        project_duration_ms=4800,
        track_ids=[21, 22],
        clip_index=record.state_snapshot["clip_index"],
        issue_types=["band_overlap"],
    )
    state.update(
        {
            "phase": "preview_processing",
            "selected_region_id": 1,
            "analysis_regions": [
                {
                    "id": 1,
                    "issue_type": "band_overlap",
                    "track_id": 21,
                    "secondary_track_id": 22,
                    "start_ms": 400,
                    "end_ms": 1600,
                    "band_low_hz": 200,
                    "band_high_hz": 1200,
                }
            ],
            "suggestion_payload": {
                "suggestions": [
                    {
                        "previewBands": [
                            {
                                "targetTrackId": 21,
                                "jobId": 20024,
                                "bandOrder": 1,
                                "eqTypeCode": 1,
                                "frequencyHz": 490,
                                "q": 0.49,
                                "gainDeltaDb": -2.4,
                                "statusCode": 1,
                                "previewExpiresAt": "2026-05-07T10:00:00+09:00",
                            }
                        ]
                    }
                ]
            },
            "plan_payload": {
                "candidate": {
                    "candidateId": "20024-plan-candidate-1",
                    "action": {
                        "actionType": "DYNAMIC_EQ",
                        "targetScope": "TRACK",
                        "targetTrackId": 21,
                        "targetClipId": None,
                        "startMs": 400,
                        "endMs": 1600,
                        "bandLowHz": 200,
                        "bandHighHz": 1200,
                        "gainDeltaDb": -2.4,
                        "params": {"threshold": -19, "ratio": 2.0},
                    },
                }
            },
            "preview_id": "20024-preview",
            "preview_status": "PROCESSING",
        }
    )
    store.save_graph_state(state)

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/20024/preview-compare")

    assert response.status_code == 409
    assert "not ready" in response.json()["detail"]


def test_preview_compare_api_rejects_non_preview_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_orchestration.enqueue_workflow_dispatch",
        lambda message: None,
    )
    start_workflow_job(
        WorkflowStartPayload(
            job_id=20025,
            project_id=30025,
            project_snapshot=build_project_snapshot(track_ids=[31, 32]),
            issue_types=["band_overlap", "sibilance"],
        )
    )
    waiting = run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20025,
            project_id=30025,
            dispatch_type="start",
        )
    )
    run_workflow_dispatch(
        WorkflowDispatchMessage(
            job_id=20025,
            project_id=30025,
            dispatch_type="resume_plan_input",
            **build_plan_input(waiting),
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/v1/internal/workflow/jobs/20025/preview-compare?mode=applied")

    assert response.status_code == 422
    assert "Unsupported preview compare mode" in response.json()["detail"]


def test_job_record_spills_large_state_into_artifact_store() -> None:
    state = build_workflow_initial_state(job_id=20014, project_id=30014)
    state.update(
        {
            "clip_index": [{"clip_id": "clip-1", "track_id": 1}],
            "bar_mapping": [{"measure_no": 1, "start_ms": 0, "end_ms": 2000}],
            "analysis_regions": [{"id": 1, "issue_type": "clipping"}],
            "plan_payload": {"summary": "summary"},
            "suggestion_payload": {"suggestions": [{"rank": 1, "actions": []}]},
            "plan_revision_notes": ["validator note"],
            "track_frames": {1: [{"start_ms": 0, "end_ms": 96, "window_energy": 0.2}]},
            "mix_frames": [{"start_ms": 0, "end_ms": 96, "clip_ratio": 0.01}],
            "track_power_spectra": {1: [[0.1, 0.2, 0.3]]},
            "mix_power_spectra": [[0.2, 0.3, 0.4]],
            "frequency_bins_hz": [100.0, 200.0, 300.0],
        }
    )

    record = _build_record(state)

    assert "analysis_regions" not in record.state_snapshot
    assert "plan_payload" not in record.state_snapshot
    assert "track_frames" not in record.state_snapshot
    assert "mix_frames" not in record.state_snapshot
    assert "track_power_spectra" not in record.state_snapshot
    assert "mix_power_spectra" not in record.state_snapshot
    assert "frequency_bins_hz" not in record.state_snapshot
    assert record.state_artifact_id == "20014:durable-state"

    artifact = get_workflow_artifact_store().get_artifact(record.state_artifact_id)
    assert artifact is not None
    assert artifact.payload["state_fields"]["analysis_regions"][0]["id"] == 1
    assert artifact.payload["state_fields"]["plan_revision_notes"] == ["validator note"]
    assert "track_frames" not in artifact.payload["state_fields"]
    assert "mix_frames" not in artifact.payload["state_fields"]
    assert "track_power_spectra" not in artifact.payload["state_fields"]
    assert "mix_power_spectra" not in artifact.payload["state_fields"]
    assert "frequency_bins_hz" not in artifact.payload["state_fields"]

    restored = _row_to_record(
        {
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
            "state_json": record.state_snapshot,
        }
    )
    assert restored.state_snapshot["analysis_regions"][0]["id"] == 1
    assert restored.state_snapshot["plan_payload"]["summary"] == "summary"
    assert restored.state_snapshot["plan_revision_notes"] == ["validator note"]


def test_mysql_workflow_job_store_create_pending_job_updates_existing_row() -> None:
    class _FakeResult:
        rowcount = 1

    class _FakeConnection:
        def __init__(self) -> None:
            self.statement = None
            self.params = None

        def execute(self, statement, params):  # noqa: ANN001
            self.statement = str(statement)
            self.params = params
            return _FakeResult()

    class _FakeBegin:
        def __init__(self, connection: _FakeConnection) -> None:
            self._connection = connection

        def __enter__(self) -> _FakeConnection:
            return self._connection

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

    class _FakeEngine:
        def __init__(self, connection: _FakeConnection) -> None:
            self._connection = connection

        def begin(self) -> _FakeBegin:
            return _FakeBegin(self._connection)

    connection = _FakeConnection()
    store = MySQLWorkflowJobStore.__new__(MySQLWorkflowJobStore)
    store._engine = _FakeEngine(connection)
    store._ensure_schema = lambda: None

    state = build_workflow_initial_state(job_id=21001, project_id=31001)

    record = store.create_pending_job(state)

    assert record.id == 21001
    assert connection.statement is not None
    assert "UPDATE ai_analysis_job" in connection.statement
    assert "INSERT INTO ai_analysis_job" not in connection.statement
    assert connection.params["id"] == 21001


def test_mysql_workflow_job_store_create_pending_job_fails_when_row_missing() -> None:
    class _FakeResult:
        rowcount = 0

    class _FakeConnection:
        def execute(self, statement, params):  # noqa: ANN001
            return _FakeResult()

    class _FakeBegin:
        def __init__(self, connection: _FakeConnection) -> None:
            self._connection = connection

        def __enter__(self) -> _FakeConnection:
            return self._connection

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

    class _FakeEngine:
        def __init__(self, connection: _FakeConnection) -> None:
            self._connection = connection

        def begin(self) -> _FakeBegin:
            return _FakeBegin(self._connection)

    store = MySQLWorkflowJobStore.__new__(MySQLWorkflowJobStore)
    store._engine = _FakeEngine(_FakeConnection())
    store._ensure_schema = lambda: None

    with pytest.raises(KeyError, match="Workflow job does not exist: 21002"):
        store.create_pending_job(
            build_workflow_initial_state(job_id=21002, project_id=31002)
        )


def test_workflow_start_payload_defaults_include_clipping() -> None:
    payload = WorkflowStartPayload(
        job_id=20013,
        project_id=30013,
        project_snapshot=build_project_snapshot(track_ids=[1]),
    )

    assert payload.issue_types == [
        "band_overlap",
        "track_clipping",
        "master_clipping",
        "sibilance",
        "high_band_harshness",
    ]


def test_start_api_rejects_clip_without_audio_metadata_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/internal/workflow/jobs/start",
        json={
            "job_id": 20020,
            "project_id": 30020,
            "project_snapshot": {
                "duration_ms": 4800,
                "bpm": 120,
                "numerator": 4,
                "denominator": 4,
                "tracks": [{"track_id": 1, "name": "Track 1"}],
                "clips": [
                    {
                        "clip_id": 1001,
                        "track_id": 1,
                        "start_ms": 0,
                        "end_ms": 4800,
                        "audio_start_ms": 0,
                        "audio_duration_ms": 4800,
                    }
                ],
            },
        },
    )

    assert response.status_code == 422
