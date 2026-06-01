import shutil
from pathlib import Path
from tempfile import gettempdir
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import resample_poly

from app.graph import nodes
from app.graph.nodes import analysis as analysis_nodes
from app.graph.nodes import review as review_nodes
from app.graph.nodes import runtime as runtime_nodes
from app.graph.nodes import suggestion as suggestion_nodes
from app.graph.state import build_workflow_initial_state
from app.graph.workflow import build_workflow_response, run_workflow_graph
from app.services.clap_inference import CLAPInferenceError, CLAPTrackPrediction
from app.services.plan_critic_llm import PlanCriticLLMResponse
from app.services.planning_llm import PlanningLLMError, PlanningLLMResponse
from app.services.workflow_artifacts import WorkflowArtifactDocument, get_workflow_artifact_store
from app.services.workflow_audio_paths import AudioPathResolutionError, resolve_clip_audio_path
from app.services.workflow_audio_metadata import AudioMetadataRecord
from app.services.workflow_preview_renderer import PREVIEW_CONTEXT_PADDING_MS
from app.services.workflow_snapshots import ProjectSnapshot, build_snapshot_runtime_context

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
    audio_path = audio_dir / f"track-{track_id}-{'vocal' if vocal_like else 'support'}.wav"
    if not audio_path.exists():
        sf.write(audio_path, signal, sample_rate)
    return str(audio_path)


def _clip_id(track_id: int, ordinal: int) -> int:
    return (track_id * 1000) + ordinal


def _audio_metadata_id(track_id: int, ordinal: int) -> int:
    return (track_id * 1000) + ordinal


def _register_audio_metadata(metadata_id: int, audio_path: str, *, duration_ms: int = 4800) -> int:
    _TEST_AUDIO_METADATA[metadata_id] = AudioMetadataRecord(
        id=metadata_id,
        object_key=audio_path,
        duration_ms=duration_ms,
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
                    vocal_score=0.93 if is_vocal else 0.22,
                    confidence=0.89 if is_vocal else 0.71,
                    predicted_role="vocal-like" if is_vocal else "supporting",
                    excerpt_scores=[],
                )
            )
        return predictions


@pytest.fixture(autouse=True)
def patch_clap_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.graph.nodes.analysis.get_clap_inference_client",
        lambda: _FakeCLAPInferenceClient(),
    )


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
            issue_type = str(region.get("issue_type"))
            if issue_type == "clipping":
                action = {
                    "actionType": "GAIN_TRIM",
                    "targetScope": "MASTER",
                    "targetTrackId": None,
                    "targetClipId": None,
                    "startMs": int(region["start_ms"]),
                    "endMs": int(region["end_ms"]),
                    "bandLowHz": None,
                    "bandHighHz": None,
                    "gainDeltaDb": -2.2,
                    "params": {
                        "preGainDb": -2.2,
                        "postAction": "TRUE_PEAK_LIMITER",
                        "ceilingDbfs": -1.0,
                    },
                }
            else:
                preserve_track_id = next(
                    (
                        int(item["track_id"])
                        for item in clip_context
                        if bool(item.get("is_preserve_target"))
                    ),
                    None,
                )
                involved_track_ids = [
                    int(track_id) for track_id in region.get("involved_track_ids", [])
                ]
                target_track_id = next(
                    (
                        track_id
                        for track_id in involved_track_ids
                        if preserve_track_id is None or track_id != preserve_track_id
                    ),
                    int(region.get("track_id") or 0),
                )
                action = {
                    "actionType": "DYNAMIC_EQ",
                    "targetScope": "TRACK",
                    "targetTrackId": target_track_id,
                    "targetClipId": None,
                    "startMs": int(region["start_ms"]),
                    "endMs": int(region["end_ms"]),
                    "bandLowHz": int(region.get("band_low_hz") or 250),
                    "bandHighHz": int(region.get("band_high_hz") or 1200),
                    "gainDeltaDb": -2.4,
                    "params": {"threshold": -19, "ratio": 2.0},
                }
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": f"Plan for {issue_type}",
                    "strategySummary": "Planner-generated strategy summary",
                    "summary": "Planner-generated summary",
                    "explanation": "Planner-generated explanation",
                    "candidate": {"action": action},
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


@pytest.fixture(autouse=True)
def reset_preview_related_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    _TEST_AUDIO_METADATA.clear()
    cache_dir = Path(gettempdir()) / "studion-ai-audio-cache-test"
    shutil.rmtree(cache_dir, ignore_errors=True)
    settings = SimpleNamespace(
        mongo_url=None,
        mongo_database="studion_ai",
        mongo_snapshot_collection="timeline_snapshots",
        mongo_artifact_collection="workflow_artifacts",
        audio_root=None,
        audio_cache_dir=str(cache_dir),
        audio_download_timeout_seconds=10.0,
        audio_download_connect_timeout_seconds=2.0,
    )
    monkeypatch.setattr("app.services.workflow_artifacts.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.workflow_snapshots.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.workflow_audio_paths.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.workflow_snapshots.get_workflow_audio_metadata_store",
        lambda: _FakeAudioMetadataStore(),
    )
    monkeypatch.setattr("app.services.workflow_artifacts._mongo_store", None)
    monkeypatch.setattr("app.services.workflow_snapshots._mongo_store", None)
    artifact_store = get_workflow_artifact_store()
    snapshot_store = analysis_nodes.get_workflow_snapshot_store()
    artifact_store.reset()
    snapshot_store.reset()
    yield
    artifact_store.reset()
    snapshot_store.reset()
    _TEST_AUDIO_METADATA.clear()
    shutil.rmtree(cache_dir, ignore_errors=True)


def test_resolve_clip_audio_path_downloads_and_caches_audio_url(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_path = Path(_ensure_test_audio_file(77, vocal_like=True))
    payload = audio_path.read_bytes()
    captured_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> _FakeResponse:
            captured_urls.append(url)
            return _FakeResponse(payload)

    monkeypatch.setattr("app.services.workflow_audio_paths.httpx.Client", _FakeClient)
    clip = {"clip_id": 77001, "audio_url": "https://cdn.test/audio/77.wav"}

    resolved_first = resolve_clip_audio_path(clip)
    resolved_second = resolve_clip_audio_path(clip)

    assert resolved_first is not None
    assert resolved_second == resolved_first
    assert Path(resolved_first).read_bytes() == payload
    assert captured_urls == ["https://cdn.test/audio/77.wav"]


def test_resolve_clip_audio_path_raises_on_audio_download_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str):
            raise RuntimeError("unexpected")

    def _raising_client(*args, **kwargs):
        raise AudioPathResolutionError(
            "AUDIO_DOWNLOAD_FAILED",
            "Failed to download audio source: https://cdn.test/audio/88.wav",
        )

    monkeypatch.setattr("app.services.workflow_audio_paths.httpx.Client", _FakeClient)
    monkeypatch.setattr("app.services.workflow_audio_paths._resolve_audio_url", _raising_client)

    with pytest.raises(AudioPathResolutionError) as exc:
        resolve_clip_audio_path({"clip_id": 88001, "audio_url": "https://cdn.test/audio/88.wav"})

    assert exc.value.code == "AUDIO_DOWNLOAD_FAILED"


def build_project_snapshot(
    *,
    track_ids: list[int],
    track_eqs: list[dict[str, object]] | None = None,
) -> ProjectSnapshot:
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
    return ProjectSnapshot.model_validate(
        {
            "duration_ms": 4800,
            "bpm": 120,
            "numerator": 4,
            "denominator": 4,
            "tracks": [
                {"track_id": track_id, "name": f"Track {track_id}"} for track_id in track_ids
            ],
            "clips": clips,
            "track_eqs": track_eqs or [],
        }
    )


def build_project_snapshot_with_audio(
    *,
    track_audio_paths: dict[int, str],
    duration_ms: int = 4800,
    track_eqs: list[dict[str, object]] | None = None,
) -> ProjectSnapshot:
    return ProjectSnapshot.model_validate(
        {
            "duration_ms": duration_ms,
            "bpm": 120,
            "numerator": 4,
            "denominator": 4,
            "tracks": [
                {"track_id": track_id, "name": f"Track {track_id}"}
                for track_id in track_audio_paths.keys()
            ],
            "clips": [
                {
                    "clip_id": _clip_id(track_id, 1),
                    "track_id": track_id,
                    "start_ms": 0,
                    "end_ms": duration_ms,
                    "audio_metadata_id": _register_audio_metadata(
                        _audio_metadata_id(track_id, 1),
                        audio_path,
                        duration_ms=duration_ms,
                    ),
                    "audio_start_ms": 0,
                    "audio_duration_ms": duration_ms,
                }
                for track_id, audio_path in track_audio_paths.items()
            ],
            "track_eqs": track_eqs or [],
        }
    )


def build_plan_input(
    state: dict,
    *,
    user_feedback_message: str | None = None,
) -> dict[str, object]:
    selected_region_id = state["ranked_candidate_ids"][0]
    region = next(
        region for region in state["analysis_regions"] if region["id"] == selected_region_id
    )
    preserve_clip_id = region["affected_clip_ids"][0]
    payload = {
        "selected_region_id": selected_region_id,
        "preserve_clip_id": preserve_clip_id,
    }
    if user_feedback_message is not None:
        payload["user_feedback_message"] = user_feedback_message
    return payload


def test_workflow_waits_for_user_mix_intent_before_suggestions() -> None:
    result = run_workflow_graph(
        {
            "job_id": 10001,
            "project_id": 20001,
            "project_snapshot": build_project_snapshot(track_ids=[12, 18]),
            "issue_types": ["band_overlap", "clipping"],
        }
    )

    assert result["runtime_status"] == "waiting_for_user"
    assert result["durable_status"] == "WAITING_USER"
    assert result["current_node"] == "wait_user_plan_input"
    assert result["preview_id"] is None
    assert result["suggestion_group_id"] is None
    assert result["suggestion_payload"]["activeIssueId"] is not None
    assert len(result["suggestion_payload"]["issues"]) >= 1


def test_workflow_waits_for_user_even_when_active_issue_id_differs_from_ranked_region() -> None:
    waiting = run_workflow_graph(
        {
            "job_id": 100011,
            "project_id": 200011,
            "project_snapshot": build_project_snapshot(track_ids=[12, 18]),
            "issue_types": ["band_overlap", "sibilance"],
        }
    )

    ranked_region_id = waiting["ranked_candidate_ids"][0]
    waiting["suggestion_payload"]["activeIssueId"] = f"{waiting['job_id']}-issue-auto-1"

    resumed_waiting = run_workflow_graph(waiting)

    assert ranked_region_id == resumed_waiting["ranked_candidate_ids"][0]
    assert resumed_waiting["current_node"] == "wait_user_plan_input"
    assert resumed_waiting["phase"] == "waiting_for_user_plan_input"
    assert resumed_waiting["runtime_status"] == "waiting_for_user"


def test_workflow_finalize_without_user_action_when_no_suggestions_exist() -> None:
    result = run_workflow_graph(
        {
            "job_id": 10002,
            "project_id": 20002,
            "project_snapshot": build_project_snapshot(track_ids=[9]),
            "issue_types": [],
        }
    )

    assert result["current_node"] == "finalize_output"
    assert result["runtime_status"] == "completed"
    assert result["durable_status"] == "COMPLETED"


def test_workflow_plan_loop_runs_for_band_overlap_and_clipping() -> None:
    waiting = run_workflow_graph(
        {
            "job_id": 10003,
            "project_id": 20003,
            "project_snapshot": build_project_snapshot(track_ids=[3, 4]),
            "issue_types": ["band_overlap", "clipping"],
        }
    )
    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})
    artifact_store = get_workflow_artifact_store()
    execution_plan_artifact_id = next(
        artifact_id
        for artifact_id in reversed(result["mongo_artifact_ids"])
        if "execution-plan" in artifact_id
    )
    execution_plan_artifact = artifact_store.get_artifact(execution_plan_artifact_id)

    assert result["current_node"] == "finalize_output"
    assert result["runtime_status"] == "completed"
    assert result["plan_status"] == "APPROVED"
    assert result["preview_status"] == "READY"
    assert result["preview_excerpt_start_ms"] is not None
    assert result["preview_excerpt_end_ms"] is not None
    assert result["preview_excerpt_end_ms"] > result["preview_excerpt_start_ms"]
    assert execution_plan_artifact is not None
    assert execution_plan_artifact.artifact_type == "execution_plan"
    preview_band = execution_plan_artifact.payload["previewBandSpecs"][0]
    planned_issue = next(
        issue
        for issue in result["suggestion_payload"]["issues"]
        if issue["issueType"] == "band_overlap" and issue["actions"]
    )
    planned_action = planned_issue["actions"][0]
    assert preview_band["jobId"] == 10003
    assert preview_band["targetTrackId"] is not None
    assert preview_band["bandOrder"] == 1
    assert preview_band["eqTypeCode"] == 1
    assert preview_band["statusCode"] == 1
    assert isinstance(preview_band["previewExpiresAt"], str)
    assert planned_action["frequencyHz"] == preview_band["frequencyHz"]
    assert planned_action["q"] == preview_band["q"]
    assert planned_action["sourceType"] == "AI_CONFIRM"
    assert planned_action["jobId"] == 10003
    assert len(result["suggestion_payload"]["issues"]) >= 2
    assert any(issue["uiMode"] == "master_limiter" for issue in result["suggestion_payload"]["issues"])


def test_materialize_execution_plan_fails_before_internal_approval() -> None:
    state = build_workflow_initial_state(
        job_id=10041,
        project_id=20041,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "clipping",
                "start_ms": 0,
                "end_ms": 400,
                "affected_clip_ids": [1],
            }
        ],
        selected_region_id=1,
        preserve_clip_id=1,
        plan_status="DRAFT",
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionId": "10041-action-1",
                    "actionType": "GAIN_TRIM",
                    "targetScope": "MASTER",
                    "targetTrackId": None,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": None,
                    "bandHighHz": None,
                    "gainDeltaDb": -2.0,
                    "params": {"preGainDb": -2.0},
                }
            },
        },
    )

    result = suggestion_nodes.materialize_execution_plan(state)

    assert result["current_node"] == "fail_workflow"
    assert result["failure_code"] == "PLAN_NOT_APPROVED"


def test_plan_rule_validator_rejects_non_band_overlap_planning_issue() -> None:
    state = build_workflow_initial_state(
        job_id=10043,
        project_id=20043,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "sibilance",
                "start_ms": 0,
                "end_ms": 400,
                "track_id": 8,
                "band_low_hz": 6000,
                "band_high_hz": 8500,
            }
        ],
        selected_region_id=1,
        preserve_clip_id=1,
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionType": "DE_ESSER",
                    "targetScope": "TRACK",
                    "targetTrackId": 8,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": 6000,
                    "bandHighHz": 8500,
                    "gainDeltaDb": -2.0,
                    "params": {"threshold": -18},
                }
            },
        },
    )

    result = nodes.plan_rule_validator(state)

    assert result["validator_result"] == "REJECT"
    assert any("only supports band_overlap" in note for note in result["plan_revision_notes"])


def test_plan_rule_validator_rejects_band_overlap_gain_over_9db() -> None:
    state = build_workflow_initial_state(
        job_id=100431,
        project_id=200431,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "band_overlap",
                "band_overlap_subtype": "low_mid_overlap",
                "start_ms": 0,
                "end_ms": 400,
                "track_id": 8,
                "band_low_hz": 250,
                "band_high_hz": 420,
            }
        ],
        selected_region_id=1,
        preserve_clip_id=1,
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetScope": "TRACK",
                    "targetTrackId": 8,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": 250,
                    "bandHighHz": 420,
                    "gainDeltaDb": -9.5,
                    "params": {"threshold": -18},
                }
            },
        },
    )

    result = nodes.plan_rule_validator(state)

    assert result["validator_result"] == "REJECT"
    assert any("within 9 dB" in note for note in result["plan_revision_notes"])


def test_plan_rule_validator_rejects_presence_overlap_gain_over_4db() -> None:
    state = build_workflow_initial_state(
        job_id=100432,
        project_id=200432,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "band_overlap",
                "band_overlap_subtype": "presence_overlap",
                "start_ms": 0,
                "end_ms": 400,
                "track_id": 8,
                "band_low_hz": 2800,
                "band_high_hz": 4200,
            }
        ],
        selected_region_id=1,
        preserve_clip_id=1,
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetScope": "TRACK",
                    "targetTrackId": 8,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": 2800,
                    "bandHighHz": 4200,
                    "gainDeltaDb": -4.3,
                    "params": {"threshold": -18},
                }
            },
        },
    )

    result = nodes.plan_rule_validator(state)

    assert result["validator_result"] == "REJECT"
    assert any("within 4 dB" in note for note in result["plan_revision_notes"])


def test_plan_rule_validator_rejects_upper_mid_overlap_gain_over_6db() -> None:
    state = build_workflow_initial_state(
        job_id=100433,
        project_id=200433,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "band_overlap",
                "band_overlap_subtype": "upper_mid_overlap",
                "start_ms": 0,
                "end_ms": 400,
                "track_id": 8,
                "band_low_hz": 1280,
                "band_high_hz": 1820,
            }
        ],
        selected_region_id=1,
        preserve_clip_id=1,
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetScope": "TRACK",
                    "targetTrackId": 8,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": 1280,
                    "bandHighHz": 1820,
                    "gainDeltaDb": -6.3,
                    "params": {"threshold": -18},
                }
            },
        },
    )

    result = nodes.plan_rule_validator(state)

    assert result["validator_result"] == "REJECT"
    assert any("within 6 dB" in note for note in result["plan_revision_notes"])


def test_review_selection_context_prefers_user_selected_track_over_preserve_track() -> None:
    state = build_workflow_initial_state(
        job_id=1004331,
        project_id=2004331,
        clip_index=[
            {"clip_id": 9001, "track_id": 9},
            {"clip_id": 17001, "track_id": 17},
        ],
        track_name_map={9: "Vocal", 17: "Guitar"},
        action_payload={"selected_track_ids": [17]},
    )
    region = {
        "id": 1,
        "track_id": 9,
        "secondary_track_id": 17,
        "involved_track_ids": [9, 17],
        "band_overlap_subtype": "low_mid_overlap",
        "band_focus_label": "body",
        "track_body_contributions": {"9": 0.7, "17": 0.3},
    }

    selection_context = review_nodes.build_selection_context(state, region, 9001)

    assert selection_context["selectedTrackId"] == 17
    assert selection_context["preserveTrackId"] == 9
    assert selection_context["selectedTrackIsProtected"] is False
    assert selection_context["nonPreserveOverlappingTrackIds"] == [17]
    assert selection_context["trackNameMap"] == {9: "Vocal", 17: "Guitar"}


def test_suggestion_selection_context_marks_selected_preserve_track_as_protected() -> None:
    state = build_workflow_initial_state(
        job_id=1004332,
        project_id=2004332,
        clip_index=[
            {"clip_id": 17001, "track_id": 17},
        ],
        track_name_map={17: "Lead Vocal"},
        action_payload={"selected_track_ids": [17]},
    )
    region = {
        "id": 1,
        "track_id": 17,
        "secondary_track_id": None,
        "involved_track_ids": [17],
        "band_overlap_subtype": "presence_overlap",
        "band_focus_label": "presence",
        "track_body_contributions": {"17": 1.0},
    }

    selection_context = suggestion_nodes.build_selection_context(state, region, 17001)

    assert selection_context["selectedTrackId"] == 17
    assert selection_context["preserveTrackId"] == 17
    assert selection_context["selectedTrackIsProtected"] is True
    assert selection_context["nonPreserveOverlappingTrackIds"] == []


def test_plan_rule_validator_allows_targeting_user_selected_non_preserve_track() -> None:
    state = build_workflow_initial_state(
        job_id=1004333,
        project_id=2004333,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "band_overlap",
                "band_overlap_subtype": "low_mid_overlap",
                "start_ms": 0,
                "end_ms": 400,
                "track_id": 9,
                "secondary_track_id": 17,
                "involved_track_ids": [9, 17],
                "band_low_hz": 250,
                "band_high_hz": 420,
            }
        ],
        clip_index=[
            {"clip_id": 9001, "track_id": 9},
            {"clip_id": 17001, "track_id": 17},
        ],
        selected_region_id=1,
        preserve_clip_id=9001,
        action_payload={"selected_track_ids": [17]},
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetScope": "TRACK",
                    "targetTrackId": 17,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": 250,
                    "bandHighHz": 420,
                    "gainDeltaDb": -2.8,
                    "params": {"threshold": -18},
                }
            },
        },
    )

    result = nodes.plan_rule_validator(state)

    assert result["validator_result"] == "PASS"
    assert result["plan_revision_notes"] == []


def test_materialize_execution_plan_rejects_master_scope_preview_action() -> None:
    state = build_workflow_initial_state(
        job_id=10044,
        project_id=20044,
        analysis_regions=[
            {
                "id": 1,
                "issue_type": "band_overlap",
                "start_ms": 0,
                "end_ms": 400,
                "track_id": 8,
                "affected_clip_ids": [1],
            }
        ],
        selected_region_id=1,
        preserve_clip_id=1,
        plan_status="APPROVED",
        plan_payload={
            "strategyTitle": "title",
            "strategySummary": "summary",
            "summary": "candidate summary",
            "explanation": "candidate explanation",
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetScope": "MASTER",
                    "targetTrackId": None,
                    "targetClipId": None,
                    "startMs": 0,
                    "endMs": 400,
                    "bandLowHz": 250,
                    "bandHighHz": 1200,
                    "gainDeltaDb": -2.0,
                    "params": {"threshold": -18},
                }
            },
        },
    )

    result = suggestion_nodes.materialize_execution_plan(state)

    assert result["current_node"] == "fail_workflow"
    assert result["failure_code"] == "INVALID_EQ_ONLY_PLAN_ACTION"


def test_workflow_skips_clap_when_not_needed() -> None:
    result = run_workflow_graph(
        {
            "job_id": 10004,
            "project_id": 20004,
            "project_snapshot": build_project_snapshot(track_ids=[2, 5]),
            "issue_types": ["band_overlap"],
        }
    )

    assert result["current_node"] == "wait_user_plan_input"
    assert result["inferred_roles"] == {}


def test_workflow_revises_once_then_passes() -> None:
    waiting = run_workflow_graph(
        {
            "job_id": 10005,
            "project_id": 20005,
            "project_snapshot": build_project_snapshot(track_ids=[7, 8]),
            "issue_types": ["band_overlap"],
            "validator_mode": "REVISE_ONCE",
            "critic_mode": "PASS",
        }
    )
    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    assert result["current_node"] == "finalize_output"
    assert result["transition_log"].count("planning_agent") == 6


def test_workflow_planning_agent_uses_llm_plan_payload_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "LLM plan title",
                    "strategySummary": "LLM plan summary",
                    "summary": "LLM summary",
                    "explanation": "LLM explanation",
                    "candidate": {
                        "action": {
                            "actionType": "DYNAMIC_EQ",
                            "targetScope": "TRACK",
                            "targetTrackId": 24,
                            "targetClipId": None,
                            "startMs": int(region["start_ms"]),
                            "endMs": int(region["end_ms"]),
                            "bandLowHz": int(region.get("band_low_hz") or 250),
                            "bandHighHz": int(region.get("band_high_hz") or 1200),
                            "gainDeltaDb": -2.4,
                            "params": {"threshold": -19, "ratio": 2.0},
                        }
                    },
                }
            )

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _FakePlanningClient(),
    )
    waiting = run_workflow_graph(
        {
            "job_id": 10034,
            "project_id": 20034,
            "project_snapshot": build_project_snapshot(track_ids=[12, 24]),
            "issue_types": ["band_overlap"],
        }
    )

    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    suggestion = result["suggestion_payload"]["suggestions"][0]
    assert result["plan_payload"]["strategyTitle"] == "LLM plan title"
    assert result["plan_payload"]["strategySummary"] == "LLM plan summary"
    assert suggestion["summary"] == "LLM summary"
    assert suggestion["explanation"] == "LLM explanation"


def test_workflow_planning_agent_fails_when_llm_call_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingPlanningClient:
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
            raise PlanningLLMError("PLANNING_LLM_TIMEOUT", "timeout")

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _FailingPlanningClient(),
    )
    waiting = run_workflow_graph(
        {
            "job_id": 10035,
            "project_id": 20035,
            "project_snapshot": build_project_snapshot(track_ids=[14, 15]),
            "issue_types": ["band_overlap"],
        }
    )

    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    assert result["current_node"] == "fail_workflow"
    assert result["failure_code"] == "PLANNING_LLM_TIMEOUT"
    assert result["runtime_status"] == "failed"


def test_workflow_fails_when_validator_rejects() -> None:
    waiting = run_workflow_graph(
        {
            "job_id": 10006,
            "project_id": 20006,
            "project_snapshot": build_project_snapshot(track_ids=[1, 2]),
            "issue_types": ["band_overlap"],
        }
    )
    result = run_workflow_graph(
        {
            **waiting,
            **build_plan_input(waiting),
            "validator_mode": "REJECT",
        }
    )

    assert result["current_node"] == "fail_workflow"
    assert result["runtime_status"] == "failed"
    assert result["durable_status"] == "FAILED"
    assert result["revise_count"] == 5


def test_workflow_retries_once_when_critic_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner_call_count = 0

    class _PlanningClient:
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
            nonlocal planner_call_count
            planner_call_count += 1
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "retryable reject",
                    "strategySummary": "retryable reject summary",
                    "summary": "retryable reject summary",
                    "explanation": "retryable reject explanation",
                    "candidate": {
                        "action": {
                            "actionType": "DYNAMIC_EQ",
                            "targetScope": "TRACK",
                            "targetTrackId": 2,
                            "targetClipId": None,
                            "startMs": 1000,
                            "endMs": 2200,
                            "bandLowHz": 250,
                            "bandHighHz": 1200,
                            "gainDeltaDb": -2.4,
                            "params": {"threshold": -19, "ratio": 2.0},
                        }
                    },
                }
            )

    class _CriticClient:
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
            return PlanCriticLLMResponse(result="REJECT", note="retry with a narrower plan")

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _PlanningClient(),
    )
    monkeypatch.setattr(
        "app.graph.nodes.review.get_plan_critic_llm_client",
        lambda: _CriticClient(),
    )

    waiting = run_workflow_graph(
        {
            "job_id": 10036,
            "project_id": 20036,
            "project_snapshot": build_project_snapshot(track_ids=[1, 2]),
            "issue_types": ["band_overlap"],
        }
    )

    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    assert result["current_node"] == "fail_workflow"
    assert result["runtime_status"] == "failed"
    assert result["durable_status"] == "FAILED"
    assert result["revise_count"] == 5
    assert planner_call_count == 6
    assert any("retry with a narrower plan" in note for note in result["plan_revision_notes"])


def test_workflow_materializes_sibilance_without_planner_loop() -> None:
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
    audio_path = audio_dir / "workflow-sibilance-autofix.wav"
    sf.write(audio_path, vocal_like, sample_rate)

    result = run_workflow_graph(
        {
            "job_id": 10040,
            "project_id": 20040,
            "project_snapshot": build_project_snapshot_with_audio(
                track_audio_paths={8: str(audio_path)}
            ),
            "issue_types": ["sibilance"],
        }
    )
    assert result["current_node"] == "finalize_output"
    assert result["runtime_status"] == "completed"
    assert result["ranked_candidate_ids"] == []
    sibilance_region = next(
        region for region in result["analysis_regions"] if region["issue_type"] == "sibilance"
    )
    assert sibilance_region["requires_user_action"] is False
    sibilance_issue = next(
        issue for issue in result["suggestion_payload"]["issues"] if issue["issueType"] == "sibilance"
    )
    assert sibilance_issue["uiMode"] == "eq_ai"
    assert sibilance_issue["actions"]


def test_workflow_keeps_band_overlap_preview_in_mixed_run() -> None:
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
    audio_path = audio_dir / "workflow-mixed-sibilance.wav"
    sf.write(audio_path, vocal_like, sample_rate)

    waiting = run_workflow_graph(
        {
            "job_id": 10042,
            "project_id": 20042,
            "project_snapshot": build_project_snapshot_with_audio(
                track_audio_paths={
                    8: str(audio_path),
                    9: _ensure_test_audio_file(9, vocal_like=False),
                }
            ),
            "issue_types": ["band_overlap", "sibilance"],
        }
    )
    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    assert result["current_node"] == "finalize_output"
    preview_band = result["suggestion_payload"]["suggestions"][0]["previewBands"][0]
    assert preview_band["jobId"] == 10042
    assert any(
        issue["issueType"] == "band_overlap"
        for issue in result["suggestion_payload"]["issues"]
    )
    assert result["auto_fix_recipe_artifact_id"] is None
    assert result["sibilance_fix_log_id"] is None


def test_workflow_auto_applies_preview_band_spec_and_completes() -> None:
    waiting = run_workflow_graph(
        {
            "job_id": 10037,
            "project_id": 20037,
            "project_snapshot": build_project_snapshot(track_ids=[8, 9]),
            "issue_types": ["band_overlap"],
        }
    )
    selected = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    assert selected["current_node"] == "finalize_output"
    assert selected["runtime_status"] == "completed"
    assert selected["preview_requested_at"] is not None
    assert selected["preview_started_at"] is not None
    assert selected["preview_completed_at"] is not None
    assert selected["preview_expired_at"] is not None
    assert selected["preview_status"] == "READY"


def test_user_action_gate_routes_directly_to_apply_when_action_is_required() -> None:
    original = build_workflow_initial_state(
        job_id=10036,
        project_id=20036,
        phase="analysis_result_persisted",
        suggestion_payload={"suggestions": [{"previewBands": [{"jobId": 10036}]}]},
        preview_required=True,
        user_action_required=True,
    )
    gated = nodes.user_action_gate(original)

    assert gated["phase"] == "user_action_gate_checked"
    from app.graph.edges import route_after_user_action_gate

    assert route_after_user_action_gate({**original, **gated}) == "apply_selected_edit_recipe"


def test_workflow_fails_when_no_preview_action_exists() -> None:
    failed = nodes.apply_selected_edit_recipe(
        build_workflow_initial_state(
            job_id=10017,
            project_id=20017,
            phase="analysis_result_persisted",
            suggestion_payload={},
        )
    )

    assert failed["current_node"] == "fail_workflow"
    assert failed["runtime_status"] == "failed"
    assert failed["failure_code"] == "INVALID_PREVIEW_BAND_SPEC_COUNT"


def test_workflow_accepts_multiple_preview_actions_for_combined_preview() -> None:
    applied = nodes.apply_selected_edit_recipe(
        build_workflow_initial_state(
            job_id=10018,
            project_id=20018,
            phase="analysis_result_persisted",
            preview_required=True,
            suggestion_payload={
                "suggestions": [
                    {
                        "previewBands": [
                            {"jobId": 10018, "bandOrder": 1},
                            {"jobId": 10018, "bandOrder": 2},
                        ]
                    }
                ]
            },
        )
    )

    assert applied["current_node"] == "apply_selected_edit_recipe"
    assert applied["preview_status"] == "PROCESSING"


def test_render_preview_succeeds_without_audio_file_generation() -> None:
    result = nodes.render_preview(
        build_workflow_initial_state(
            job_id=10019,
            project_id=20019,
            selected_region_id=1,
            preview_id="10019-preview",
            suggestion_group_id="10019-group",
            plan_payload={
                "candidate": {
                    "candidateId": "10019-plan-candidate-1",
                    "action": {
                        "actionType": "DYNAMIC_EQ",
                        "targetScope": "TRACK",
                        "targetTrackId": 14,
                        "startMs": 0,
                        "endMs": 1200,
                        "bandLowHz": 180,
                        "bandHighHz": 420,
                        "gainDeltaDb": -2.4,
                        "params": {"q": 1.1},
                    },
                }
            },
            suggestion_payload={
                "suggestions": [
                    {
                        "previewBands": [
                            {
                                "jobId": 10019,
                                "targetTrackId": 14,
                                "bandOrder": 1,
                                "eqTypeCode": 1,
                                "frequencyHz": 275,
                                "q": 1.1,
                                "gainDeltaDb": -2.4,
                                "statusCode": 1,
                                "previewExpiresAt": "2026-05-07T10:00:00+09:00",
                            }
                        ]
                    }
                ]
            },
            analysis_regions=[
                {
                    "id": 1,
                    "issue_type": "band_overlap",
                    "start_ms": 0,
                    "end_ms": 800,
                    "measure_start": 1,
                    "measure_end": 1,
                }
            ],
            clip_index=[
                {
                    "clip_id": _clip_id(10, 1),
                    "track_id": 10,
                    "start_ms": 0,
                    "end_ms": 1200,
                    "audio_path": str(Path(gettempdir()) / "missing-preview-source.wav"),
                    "audio_start_ms": 0,
                    "audio_duration_ms": 1200,
                }
            ],
        )
    )

    assert result["current_node"] == "render_preview"
    assert result["preview_status"] == "READY"
    assert result["preview_excerpt_start_ms"] == 0
    assert result["preview_excerpt_end_ms"] == 1200


def test_resolve_preview_excerpt_range_uses_context_padding() -> None:
    waiting = run_workflow_graph(
        {
            "job_id": 10043,
            "project_id": 20043,
            "project_snapshot": build_project_snapshot(track_ids=[12, 24]),
            "issue_types": ["band_overlap"],
        }
    )
    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    assert result["preview_status"] == "READY"
    assert result["preview_excerpt_start_ms"] == 0
    assert result["preview_excerpt_end_ms"] == 4800


def test_workflow_uses_user_selected_main_track_for_generated_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_planner_context: dict[str, object] = {}
    captured_critic_context: dict[str, object] = {}

    class _CapturingPlanningClient:
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
            captured_planner_context.update(selection_context)
            return PlanningLLMResponse(
                plan_payload={
                    "strategyTitle": "selected track plan",
                    "strategySummary": "selected track summary",
                    "summary": "selected track suggestion",
                    "explanation": "selected track explanation",
                    "candidate": {
                        "action": {
                            "actionType": "DYNAMIC_EQ",
                            "targetScope": "TRACK",
                            "targetTrackId": int(selection_context["selectedTrackId"]),
                            "targetClipId": None,
                            "startMs": int(region["start_ms"]),
                            "endMs": int(region["end_ms"]),
                            "bandLowHz": int(region.get("band_low_hz") or 250),
                            "bandHighHz": int(region.get("band_high_hz") or 1200),
                            "gainDeltaDb": -2.4,
                            "params": {"threshold": -19, "ratio": 2.0},
                        }
                    },
                }
            )

    class _CapturingCriticClient:
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
            captured_critic_context.update(selection_context)
            return PlanCriticLLMResponse(result="PASS", note="")

    monkeypatch.setattr(
        "app.graph.nodes.suggestion.get_planning_llm_client",
        lambda: _CapturingPlanningClient(),
    )
    monkeypatch.setattr(
        "app.graph.nodes.review.get_plan_critic_llm_client",
        lambda: _CapturingCriticClient(),
    )
    waiting = run_workflow_graph(
        {
            "job_id": 10041,
            "project_id": 20041,
            "project_snapshot": build_project_snapshot(track_ids=[11, 22]),
            "issue_types": ["band_overlap"],
        }
    )

    plan_input = build_plan_input(waiting)
    resumed = run_workflow_graph(
        {
            **waiting,
            **plan_input,
            "action_payload": {"selected_track_ids": [22]},
        }
    )

    action = resumed["plan_payload"]["candidate"]["action"]
    assert captured_planner_context["selectedTrackId"] == 22
    assert captured_planner_context["preserveTrackId"] == 11
    assert captured_planner_context["selectedTrackIsProtected"] is False
    assert captured_critic_context["selectedTrackId"] == 22
    assert captured_critic_context["preserveTrackId"] == 11
    assert captured_critic_context["selectedTrackIsProtected"] is False
    assert action["targetTrackId"] == 22


def test_workflow_response_contains_unified_projections() -> None:
    snapshot = build_project_snapshot(track_ids=[10, 20])
    waiting = run_workflow_graph(
        {
            "job_id": 10042,
            "project_id": 20042,
            "project_snapshot": snapshot,
            "issue_types": ["band_overlap", "sibilance"],
        }
    )
    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})
    response = build_workflow_response(result)

    assert response["graph_state"]["job_id"] == 10042
    assert response["projections"]["analysis_job"]["id"] == 10042
    assert response["projections"]["analysis_regions"][0]["job_id"] == 10042
    assert response["projections"]["analysis_regions"][0]["issue_type"] in {
        "BAND_OVERLAP",
        "SIBILANCE",
    }
    overlap_projection = next(
        (
            region
            for region in response["projections"]["analysis_regions"]
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
    assert response["projections"]["user_action_required"] is True
    assert response["projections"]["preview_required"] is True
    assert response["projections"]["auto_preview_generated"] is False
    assert response["projections"]["suggestion_group"]["id"] == "10042-group"
    assert response["projections"]["preview_render"]["id"] == "10042-preview"
    assert response["projections"]["preview_render"]["status"] == "READY"
    assert response["projections"]["preview_render"]["preview_target_region"] == (
        result["selected_region_id"]
    )
    assert response["projections"]["preview_render"]["preview_action_track"] is not None
    assert response["projections"]["preview_render"]["preview_excerpt_range"]["start_ms"] == max(
        0,
        next(
            region["start_ms"]
            for region in result["analysis_regions"]
            if region["id"] == result["selected_region_id"]
        )
        - PREVIEW_CONTEXT_PADDING_MS,
    )
    assert response["projections"]["analysis_regions"][0]["measure_start"] == 1
    assert response["projections"]["analysis_regions"][0]["affected_clip_ids"]
    clipping_projection = next(
        (
            region
            for region in response["projections"]["analysis_regions"]
            if region["issue_type"] in {"TRACK_CLIPPING", "MASTER_CLIPPING"}
        ),
        None,
    )
    assert clipping_projection is not None
    assert clipping_projection["estimated_gain_reduction_db"] is not None
    assert clipping_projection["current_true_peak_dbtp"] is not None
    assert clipping_projection["target_ceiling_dbtp"] == -1.0


def test_persist_analysis_result_marks_auto_preview_without_user_action() -> None:
    state = build_workflow_initial_state(
        job_id=10031,
        project_id=20031,
        suggestion_payload={
            "suggestions": [
                {
                    "previewBands": [
                        {
                            "jobId": 10031,
                            "targetTrackId": 11,
                            "bandOrder": 1,
                            "eqTypeCode": 1,
                            "frequencyHz": 6200,
                            "q": 2.0,
                            "gainDeltaDb": -2.2,
                            "statusCode": 1,
                            "previewExpiresAt": "2026-05-07T10:00:00+09:00",
                        }
                    ]
                }
            ]
        },
    )

    persisted = nodes.persist_analysis_result(state)

    assert persisted["preview_id"] == "10031-preview"
    assert persisted["preview_required"] is True
    assert persisted["user_action_required"] is False
    assert persisted["has_user_action_candidates"] is False


def test_render_preview_uses_auto_preview_focus_region_without_selected_region() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="100311-auto-fix",
            job_id=100311,
            artifact_type="auto_fix_recipe",
            payload={
                "groups": [
                    {
                        "issueType": "sibilance",
                        "regionIds": [9],
                        "trackIds": [14],
                        "regionCount": 1,
                        "recipes": [
                            {
                                "regionId": 9,
                                "actionType": "DYNAMIC_EQ",
                                "targetScope": "TRACK",
                                "targetTrackId": 14,
                                "startMs": 400,
                                "endMs": 1200,
                                "bandLowHz": 6000,
                                "bandHighHz": 7800,
                                "gainDeltaDb": -2.2,
                                "params": {"q": 2.1},
                            }
                        ],
                    }
                ]
            },
        )
    )
    rendered = nodes.render_preview(
        build_workflow_initial_state(
            job_id=100311,
            project_id=200311,
            preview_id="100311-preview",
            preview_required=True,
            auto_fix_recipe_artifact_id="100311-auto-fix",
            suggestion_payload={
                "suggestions": [
                    {
                        "previewBands": [
                            {
                                "jobId": 100311,
                                "targetTrackId": 14,
                                "bandOrder": 1,
                                "eqTypeCode": 1,
                                "frequencyHz": 6200,
                                "q": 2.1,
                                "gainDeltaDb": -2.2,
                                "statusCode": 1,
                                "previewExpiresAt": "2026-05-07T10:00:00+09:00",
                            }
                        ]
                    }
                ]
            },
            analysis_regions=[
                {
                    "id": 9,
                    "issue_type": "sibilance",
                    "requires_user_action": False,
                    "track_id": 14,
                    "start_ms": 400,
                    "end_ms": 1200,
                    "measure_start": 1,
                    "measure_end": 1,
                }
            ],
            clip_index=[
                {
                    "clip_id": _clip_id(14, 1),
                    "track_id": 14,
                    "start_ms": 0,
                    "end_ms": 2400,
                    "audio_path": str(Path(gettempdir()) / "missing-auto-preview-source.wav"),
                    "audio_start_ms": 0,
                    "audio_duration_ms": 2400,
                }
            ],
            project_duration_ms=2400,
        )
    )

    assert rendered["preview_status"] == "READY"
    assert rendered["auto_preview_generated"] is True
    assert rendered["preview_excerpt_start_ms"] == 0
    assert rendered["preview_excerpt_end_ms"] == 2400


def test_render_preview_uses_batch_issue_source_region_without_selected_region() -> None:
    rendered = nodes.render_preview(
        build_workflow_initial_state(
            job_id=100312,
            project_id=200312,
            request_mode="batch",
            preview_id="100312-preview",
            suggestion_group_id="100312-group",
            analysis_regions=[
                {
                    "id": 21,
                    "issue_type": "band_overlap",
                    "track_id": 12,
                    "start_ms": 500,
                    "end_ms": 1500,
                    "measure_start": 2,
                    "measure_end": 3,
                }
            ],
            clip_index=[
                {
                    "clip_id": _clip_id(12, 1),
                    "track_id": 12,
                    "start_ms": 0,
                    "end_ms": 2500,
                    "audio_path": str(Path(gettempdir()) / "missing-batch-preview-source.wav"),
                    "audio_start_ms": 0,
                    "audio_duration_ms": 2500,
                }
            ],
            project_duration_ms=2500,
            suggestion_payload={
                "activeIssueId": "100312-batch-envelope-1",
                "issues": [
                    {
                        "issueId": "100312-batch-envelope-1",
                        "issueType": "band_overlap",
                        "trackId": 12,
                        "sourceRegionIds": [21],
                        "actions": [
                            {
                                "type": "DYNAMIC_EQ",
                                "targetScope": "TRACK",
                                "targetTrackId": 12,
                            }
                        ],
                    }
                ],
                "suggestions": [
                    {
                        "previewBands": [
                            {
                                "jobId": 100312,
                                "targetTrackId": 12,
                                "bandOrder": 1,
                                "eqTypeCode": 1,
                                "frequencyHz": 420,
                                "q": 1.2,
                                "gainDeltaDb": -2.5,
                                "statusCode": 1,
                                "previewExpiresAt": "2026-05-07T10:00:00+09:00",
                            }
                        ]
                    }
                ],
            },
        )
    )

    assert rendered["preview_status"] == "READY"
    assert rendered["preview_excerpt_start_ms"] == 0
    assert rendered["preview_excerpt_end_ms"] == 2500


def test_workflow_analysis_regions_include_detector_metadata() -> None:
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
    supporting = (0.28 * np.sin(2 * np.pi * 330 * time_axis)).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    first_path = audio_dir / "workflow-region-shape-vocal.wav"
    second_path = audio_dir / "workflow-region-shape-support.wav"
    sf.write(first_path, vocal_like, sample_rate)
    sf.write(second_path, supporting, sample_rate)
    snapshot = build_project_snapshot_with_audio(
        track_audio_paths={30: str(first_path), 31: str(second_path)}
    )
    waiting = run_workflow_graph(
        {
            "job_id": 10007,
            "project_id": 20007,
            "project_snapshot": snapshot,
            "issue_types": ["band_overlap", "sibilance", "track_clipping", "master_clipping"],
        }
    )
    result = run_workflow_graph({**waiting, **build_plan_input(waiting)})

    region_by_issue = {region["issue_type"]: region for region in result["analysis_regions"]}
    overlap = region_by_issue["band_overlap"]
    clipping = region_by_issue.get("track_clipping") or region_by_issue.get("master_clipping")
    sibilance = region_by_issue["sibilance"]

    assert overlap["secondary_track_id"] is None
    assert set(overlap["involved_track_ids"]) == {30, 31}
    assert 250 <= overlap["band_low_hz"] < overlap["band_high_hz"] < 1200
    assert overlap["band_overlap_subtype"] in {"low_mid_overlap", "body_overlap"}
    assert overlap["center_hz"] is not None
    assert overlap["band_confidence"] is not None
    assert overlap["measure_start"] == 1
    assert overlap["measure_end"] in {1, 2, 3}
    assert _clip_id(30, 1) in overlap["affected_clip_ids"]
    assert _clip_id(31, 1) in overlap["affected_clip_ids"]
    assert clipping is not None
    assert clipping["requires_user_action"] is False
    assert clipping["recommended_reduction_db"] is not None
    assert clipping["current_true_peak_dbtp"] is not None
    assert clipping["target_ceiling_dbtp"] == -1.0
    assert sibilance["track_id"] == 30
    assert sibilance["requires_user_action"] is False
    assert result["ranking_scores"][overlap["id"]] > 0


def test_merge_analysis_keeps_all_regions_without_issue_cap() -> None:
    initial = build_workflow_initial_state(
        job_id=10019,
        project_id=41,
        issue_types=["band_overlap"],
    )
    context = build_snapshot_runtime_context(build_project_snapshot(track_ids=[101, 202]))
    initial["bar_mapping"] = context.bar_mapping
    initial["clip_index"] = context.clip_index
    initial["analysis_regions"] = [
        {
            "id": index + 1,
            "issue_type": "band_overlap",
            "summary": "Detected likely masking conflict in low-mid body band.",
            "start_ms": 1000 + (index * 500),
            "end_ms": 1360 + (index * 500),
            "severity": "MEDIUM",
            "requires_user_action": True,
            "evidence_doc_id": f"job-all-regions:band-overlap-evidence-{index}",
            "track_id": 101,
            "secondary_track_id": 202,
            "band_low_hz": 250,
            "band_high_hz": 1200,
            "score": 0.6 + (index * 0.01),
            "window_count": 2,
        }
        for index in range(5)
    ]

    result = nodes.merge_analysis(initial)

    assert len(result["analysis_regions"]) == 5
    assert [region["id"] for region in result["analysis_regions"]] == [index + 1 for index in range(5)]


def test_merge_analysis_keeps_highest_score_region_for_same_key() -> None:
    initial = build_workflow_initial_state(
        job_id=10020,
        project_id=51,
        issue_types=["clipping", "band_overlap"],
    )
    initial["analysis_regions"] = [
        {
            "id": 1,
            "issue_type": "clipping",
            "summary": "Lower score clipping region.",
            "start_ms": 1200,
            "end_ms": 1440,
            "severity": "MEDIUM",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-dedup:clipping-evidence-1",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.18,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [101],
        },
        {
            "id": 2,
            "issue_type": "clipping",
            "summary": "Higher score clipping region.",
            "start_ms": 1200,
            "end_ms": 1440,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-dedup:clipping-evidence-2",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.32,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [102],
        },
        {
            "id": 3,
            "issue_type": "band_overlap",
            "summary": "Separate issue should remain.",
            "start_ms": 1800,
            "end_ms": 2160,
            "severity": "MEDIUM",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-dedup:band-overlap-evidence-1",
            "track_id": 2,
            "secondary_track_id": None,
            "involved_track_ids": [2, 3],
            "band_low_hz": 250,
            "band_high_hz": 1200,
            "score": 0.61,
            "window_count": 2,
            "measure_start": 1,
            "measure_end": 2,
            "affected_clip_ids": [103, 104],
        },
    ]

    result = nodes.merge_analysis(initial)

    assert [region["id"] for region in result["analysis_regions"]] == [
        2,
        3,
    ]
    assert result["detected_issues"] == ["clipping", "band_overlap"]
    assert result["analysis_region_ids"] == [
        2,
        3,
    ]
    assert result["analysis_regions"][0]["affected_clip_ids"] == [102]


def test_merge_analysis_keeps_distinct_time_ranges() -> None:
    initial = build_workflow_initial_state(
        job_id=10021,
        project_id=52,
        issue_types=["clipping"],
    )
    initial["analysis_regions"] = [
        {
            "id": 11,
            "issue_type": "clipping",
            "summary": "Earlier clipping region.",
            "start_ms": 500,
            "end_ms": 740,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-time:clipping-evidence-1",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.22,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [201],
        },
        {
            "id": 12,
            "issue_type": "clipping",
            "summary": "Later clipping region.",
            "start_ms": 900,
            "end_ms": 1140,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-time:clipping-evidence-2",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.21,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [202],
        },
    ]

    result = nodes.merge_analysis(initial)

    assert [region["id"] for region in result["analysis_regions"]] == [
        11,
        12,
    ]
    assert result["analysis_region_ids"] == [
        11,
        12,
    ]


def test_merge_analysis_uses_score_as_third_sort_key() -> None:
    initial = build_workflow_initial_state(
        job_id=10022,
        project_id=53,
        issue_types=["clipping"],
    )
    initial["analysis_regions"] = [
        {
            "id": 21,
            "issue_type": "clipping",
            "summary": "Lower score duplicate ordering candidate.",
            "start_ms": 800,
            "end_ms": 1040,
            "severity": "MEDIUM",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-sort:clipping-evidence-1",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.14,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [301],
        },
        {
            "id": 22,
            "issue_type": "clipping",
            "summary": "Higher score duplicate ordering candidate.",
            "start_ms": 800,
            "end_ms": 1040,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-merge-sort:clipping-evidence-2",
            "track_id": 2,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.28,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [302],
        },
    ]

    result = nodes.merge_analysis(initial)

    assert [region["id"] for region in result["analysis_regions"]] == [
        22,
        21,
    ]


def test_candidate_ranking_ignores_auto_fix_only_regions_for_user_candidates() -> None:
    initial = build_workflow_initial_state(
        job_id=10023,
        project_id=61,
        issue_types=["sibilance", "band_overlap"],
    )
    initial["analysis_regions"] = [
        {
            "id": 31,
            "issue_type": "sibilance",
            "summary": "Auto-fix only sibilance region.",
            "start_ms": 900,
            "end_ms": 1280,
            "severity": "HIGH",
            "requires_user_action": False,
            "evidence_doc_id": "job-ranking-autofix:sibilance-evidence-1",
            "track_id": 10,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": 5000,
            "band_high_hz": 9000,
            "score": 0.82,
            "window_count": 2,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [401],
        },
        {
            "id": 32,
            "issue_type": "band_overlap",
            "summary": "User-facing overlap region.",
            "start_ms": 1000,
            "end_ms": 1480,
            "severity": "MEDIUM",
            "requires_user_action": True,
            "evidence_doc_id": "job-ranking-autofix:band-overlap-evidence-1",
            "track_id": 20,
            "secondary_track_id": None,
            "involved_track_ids": [20, 21],
            "band_low_hz": 250,
            "band_high_hz": 1200,
            "score": 0.58,
            "window_count": 2,
            "measure_start": 1,
            "measure_end": 2,
            "affected_clip_ids": [402, 403],
        },
    ]

    result = nodes.candidate_ranking(initial)

    assert result["ranking_scores"][31] > 0
    assert result["ranked_candidate_ids"] == [32]


def test_candidate_ranking_prioritizes_issue_type_before_raw_score() -> None:
    initial = build_workflow_initial_state(
        job_id=10024,
        project_id=62,
        issue_types=["clipping", "band_overlap"],
    )
    initial["analysis_regions"] = [
        {
            "id": 41,
            "issue_type": "band_overlap",
            "summary": "Strong overlap region.",
            "start_ms": 1400,
            "end_ms": 1960,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-ranking-priority:band-overlap-evidence-1",
            "track_id": 2,
            "secondary_track_id": None,
            "involved_track_ids": [2, 3],
            "band_low_hz": 250,
            "band_high_hz": 1200,
            "score": 0.74,
            "window_count": 3,
            "measure_start": 1,
            "measure_end": 2,
            "affected_clip_ids": [501, 502],
        },
        {
            "id": 42,
            "issue_type": "clipping",
            "summary": "Critical clipping should outrank overlap.",
            "start_ms": 1600,
            "end_ms": 1760,
            "severity": "CRITICAL",
            "requires_user_action": True,
            "evidence_doc_id": "job-ranking-priority:clipping-evidence-1",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": None,
            "band_high_hz": None,
            "score": 0.26,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [503],
        },
    ]

    result = nodes.candidate_ranking(initial)

    assert result["ranking_scores"][42] > 0
    assert result["ranked_candidate_ids"] == [41]


def test_candidate_ranking_uses_severity_and_start_time_as_tie_breakers() -> None:
    initial = build_workflow_initial_state(
        job_id=10025,
        project_id=63,
        issue_types=["high_band_harshness"],
    )
    initial["analysis_regions"] = [
        {
            "id": 51,
            "issue_type": "high_band_harshness",
            "summary": "Earlier high-band region.",
            "start_ms": 900,
            "end_ms": 1100,
            "severity": "MEDIUM",
            "requires_user_action": True,
            "evidence_doc_id": "job-ranking-tie:high-band-evidence-1",
            "track_id": 1,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": 5000,
            "band_high_hz": 9000,
            "score": 0.42,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [601],
        },
        {
            "id": 52,
            "issue_type": "high_band_harshness",
            "summary": "Later but more severe high-band region.",
            "start_ms": 1200,
            "end_ms": 1400,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-ranking-tie:high-band-evidence-2",
            "track_id": 2,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": 5000,
            "band_high_hz": 9000,
            "score": 0.382,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [602],
        },
        {
            "id": 53,
            "issue_type": "high_band_harshness",
            "summary": "Same weighted score but earlier start.",
            "start_ms": 600,
            "end_ms": 800,
            "severity": "HIGH",
            "requires_user_action": True,
            "evidence_doc_id": "job-ranking-tie:high-band-evidence-3",
            "track_id": 3,
            "secondary_track_id": None,
            "involved_track_ids": [],
            "band_low_hz": 5000,
            "band_high_hz": 9000,
            "score": 0.382,
            "window_count": 1,
            "measure_start": 1,
            "measure_end": 1,
            "affected_clip_ids": [603],
        },
    ]

    result = nodes.candidate_ranking(initial)

    assert result["ranked_candidate_ids"] == []


def test_run_workflow_graph_derives_timeline_metadata_from_project_snapshot() -> None:
    result = run_workflow_graph(
        {
            "job_id": 10008,
            "project_id": 20008,
            "project_snapshot": build_project_snapshot(track_ids=[7, 8]),
            "issue_types": ["band_overlap"],
        }
    )

    assert result["track_ids"] == [7, 8]
    assert result["bar_mapping"][0]["measure_no"] == 1
    assert result["clip_index"][0]["clip_id"] == _clip_id(7, 1)


def test_workflow_uses_full_stft_summary_when_audio_paths_exist(tmp_path) -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    vocal_like = (
        0.25 * np.sin(2 * np.pi * 440 * time_axis)
        + 0.22 * np.sin(2 * np.pi * 6800 * time_axis)
    ).astype(np.float32)
    supporting = (0.28 * np.sin(2 * np.pi * 330 * time_axis)).astype(np.float32)
    first_path = tmp_path / "track-10.wav"
    second_path = tmp_path / "track-20.wav"
    sf.write(first_path, vocal_like, sample_rate)
    sf.write(second_path, supporting, sample_rate)

    result = run_workflow_graph(
        {
            "job_id": 10009,
            "project_id": 20009,
            "project_snapshot": build_project_snapshot_with_audio(
                track_audio_paths={
                    10: str(first_path),
                    20: str(second_path),
                }
            ),
            "issue_types": ["band_overlap", "sibilance", "clipping"],
        }
    )

    assert result["dsp_scan_summary"]["analysis_source"] == "full_stft"
    assert result["dsp_scan_summary"]["track_windows_preview"]["10"][0]["spectral_centroid_hz"] > 0
    assert result["clip_feature_artifact_id"] is None
    assert result["track_frames"] == {}
    assert result["mix_frames"] == []
    assert result["track_power_spectra"] == {}
    assert result["mix_power_spectra"] == []
    assert result["frequency_bins_hz"] == []
    assert all(
        (
            artifact := get_workflow_artifact_store().get_artifact(artifact_id)
        ) is None
        or artifact.artifact_type != "full_stft_frame_summary"
        for artifact_id in result["mongo_artifact_ids"]
    )
    assert result["sampled_clip_ids"] == [_clip_id(10, 1), _clip_id(20, 1)]
    assert result["track_representative_specs"] == [
        {
            "track_id": 10,
            "clip_id": _clip_id(10, 1),
            "resolved_audio_path": str(first_path),
            "source_format": ".wav",
        },
        {
            "track_id": 20,
            "clip_id": _clip_id(20, 1),
            "resolved_audio_path": str(second_path),
            "source_format": ".wav",
        },
    ]


def test_sample_track_clips_builds_track_representative_specs_across_multiple_clips() -> None:
    state = build_workflow_initial_state(job_id=10010, project_id=20010)
    state["track_ids"] = [10]
    state["clip_index"] = [
        {
            "clip_id": 10001,
            "track_id": 10,
            "start_ms": 0,
            "end_ms": 5000,
            "audio_path": _ensure_test_audio_file(10, vocal_like=True),
            "audio_start_ms": 0,
            "audio_duration_ms": 5000,
        },
        {
            "clip_id": 10002,
            "track_id": 10,
            "start_ms": 6000,
            "end_ms": 11000,
            "audio_path": _ensure_test_audio_file(10, vocal_like=True),
            "audio_start_ms": 1000,
            "audio_duration_ms": 5000,
        },
        {
            "clip_id": 10003,
            "track_id": 10,
            "start_ms": 12000,
            "end_ms": 18000,
            "audio_path": _ensure_test_audio_file(10, vocal_like=True),
            "audio_start_ms": 200,
            "audio_duration_ms": 6000,
        },
        {
            "clip_id": 10004,
            "track_id": 10,
            "start_ms": 19000,
            "end_ms": 23000,
            "audio_path": _ensure_test_audio_file(10, vocal_like=True),
            "audio_start_ms": 0,
            "audio_duration_ms": 4000,
        },
    ]

    result = analysis_nodes.sample_track_clips(state)

    assert result["sampled_clip_ids"] == [10001]
    assert result["track_representative_specs"] == [
        {
            "track_id": 10,
            "clip_id": 10001,
            "resolved_audio_path": _ensure_test_audio_file(10, vocal_like=True),
            "source_format": ".wav",
        }
    ]


def test_select_role_candidates_uses_high_band_issue_tracks() -> None:
    state = build_workflow_initial_state(
        job_id=10011,
        project_id=20011,
    )
    state["issue_types"] = ["sibilance"]
    state["analysis_regions"] = [
        {"issue_type": "high_band_harshness", "track_id": 3},
        {"issue_type": "high_band_harshness", "track_id": 1},
        {"issue_type": "clipping", "track_id": 8},
        {"issue_type": "high_band_harshness", "track_id": 3},
    ]

    result = analysis_nodes.select_role_candidates(state)

    assert result["role_candidate_track_ids"] == [1, 3]


def test_select_role_candidates_falls_back_to_high_band_windows_for_sibilance() -> None:
    state = build_workflow_initial_state(
        job_id=10012,
        project_id=20012,
        issue_types=["sibilance"],
        track_frames={
            2: [
                {
                    "high_band_ratio": 0.36,
                    "presence_energy": 0.08,
                    "spectral_centroid_hz": 3600,
                }
            ],
            7: [
                {
                    "high_band_ratio": 0.2,
                    "presence_energy": 0.04,
                    "spectral_centroid_hz": 2500,
                }
            ],
        },
    )

    result = analysis_nodes.select_role_candidates(state)

    assert result["role_candidate_track_ids"] == [2]


def test_infer_track_roles_calls_clap_and_persists_summary_artifact() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    state = build_workflow_initial_state(job_id=10013, project_id=20013)
    state["clip_index"] = [
        {
            "clip_id": 1001,
            "track_id": 1,
            "start_ms": 0,
            "end_ms": 4800,
            "audio_path": _ensure_test_audio_file(1, vocal_like=True),
            "audio_start_ms": 0,
            "audio_duration_ms": 4800,
        },
        {
            "clip_id": 2001,
            "track_id": 2,
            "start_ms": 0,
            "end_ms": 4800,
            "audio_path": _ensure_test_audio_file(2, vocal_like=False),
            "audio_start_ms": 0,
            "audio_duration_ms": 4800,
        },
    ]
    state["role_candidate_track_ids"] = [1, 2]
    state["track_representative_specs"] = analysis_nodes._build_track_representative_specs(
        state
    )

    result = analysis_nodes.infer_track_roles(state)
    response = build_workflow_response({**state, **result})
    artifact = artifact_store.get_artifact(result["clap_artifact_id"])

    assert result["inferred_roles"] == {1: "vocal-like", 2: "supporting"}
    assert result["track_role_scores"] == {1: 0.93, 2: 0.22}
    assert result["track_role_confidences"] == {1: 0.89, 2: 0.71}
    assert result["vocal_detected"] is True
    assert result["clap_artifact_id"] is not None
    assert artifact is not None
    assert artifact.artifact_type == "clap_track_role_inference"
    assert response["projections"]["track_vocal_predictions"] == [
        {
            "id": "10013-vocal-prediction-1",
            "track_id": 1,
            "job_id": 10013,
            "vocal_score": 0.93,
            "is_vocal": True,
            "confidence": 0.89,
        },
        {
            "id": "10013-vocal-prediction-2",
            "track_id": 2,
            "job_id": 10013,
            "vocal_score": 0.22,
            "is_vocal": False,
            "confidence": 0.71,
        },
    ]


def test_infer_track_roles_fails_without_fallback_when_clap_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RaisingCLAPClient:
        def infer_track_roles(self, *, job_id: int, excerpts: list) -> list[CLAPTrackPrediction]:
            raise CLAPInferenceError("CLAP_INFERENCE_TIMEOUT", "timeout")

    monkeypatch.setattr(
        "app.graph.nodes.analysis.get_clap_inference_client",
        lambda: _RaisingCLAPClient(),
    )
    state = build_workflow_initial_state(job_id=10014, project_id=20014)
    state["clip_index"] = [
        {
            "clip_id": 1001,
            "track_id": 1,
            "start_ms": 0,
            "end_ms": 4800,
            "audio_path": _ensure_test_audio_file(1, vocal_like=True),
            "audio_start_ms": 0,
            "audio_duration_ms": 4800,
        }
    ]
    state["role_candidate_track_ids"] = [1]
    state["track_representative_specs"] = analysis_nodes._build_track_representative_specs(
        state
    )

    result = analysis_nodes.infer_track_roles(state)

    assert result["current_node"] == "infer_track_roles"
    assert result["runtime_status"] == "failed"
    assert result["durable_status"] == "FAILED"
    assert result["failure_code"] == "CLAP_INFERENCE_TIMEOUT"


def test_workflow_fails_when_audio_source_is_missing() -> None:
    result = run_workflow_graph(
        {
            "job_id": 10015,
            "project_id": 20015,
            "project_snapshot": ProjectSnapshot.model_validate(
                {
                    "duration_ms": 4800,
                    "bpm": 120,
                    "numerator": 4,
                    "denominator": 4,
                    "tracks": [{"track_id": 1, "name": "Track 1"}],
                    "clips": [
                        {
                            "clip_id": _clip_id(1, 1),
                            "track_id": 1,
                            "start_ms": 0,
                            "end_ms": 2400,
                            "audio_metadata_id": _audio_metadata_id(1, 1),
                            "audio_start_ms": 0,
                            "audio_duration_ms": 2400,
                        }
                    ],
                }
            ),
            "issue_types": ["band_overlap"],
        }
    )

    assert result["current_node"] == "fail_workflow"
    assert result["runtime_status"] == "failed"
    assert result["failure_code"] == "AUDIO_SOURCE_MISSING"


def test_project_snapshot_rejects_unknown_track_eq_type() -> None:
    with pytest.raises(ValueError, match="track_eq band eq_type"):
        ProjectSnapshot.model_validate(
            {
                "duration_ms": 4800,
                "bpm": 120,
                "numerator": 4,
                "denominator": 4,
                "tracks": [{"track_id": 1, "name": "Track 1"}],
                "clips": [
                    {
                        "clip_id": _clip_id(1, 1),
                        "track_id": 1,
                        "start_ms": 0,
                        "end_ms": 2400,
                        "audio_metadata_id": _register_audio_metadata(
                            _audio_metadata_id(1, 1),
                            _ensure_test_audio_file(1, vocal_like=True),
                        ),
                        "audio_start_ms": 0,
                        "audio_duration_ms": 2400,
                    }
                ],
                "track_eqs": [
                    {
                        "track_id": 1,
                        "bands": [
                            {
                                "band_order": 1,
                                "eq_type": "NOTCH",
                                "frequency_hz": 3200,
                                "q": 1.0,
                                "gain_delta_db": -2.0,
                            }
                        ],
                    }
                ],
            }
        )


def test_snapshot_runtime_context_includes_track_eq_map() -> None:
    snapshot = build_project_snapshot(
        track_ids=[10],
        track_eqs=[
            {
                "track_id": 10,
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
    )

    context = build_snapshot_runtime_context(snapshot)

    assert context.track_eq_map == {
        10: [
            {
                "band_order": 1,
                "eq_type": "BELL",
                "frequency_hz": 4200,
                "q": 1.2,
                "gain_delta_db": -2.5,
            }
        ]
    }


def test_track_eq_changes_dsp_features() -> None:
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    signal = (
        0.28 * np.sin(2 * np.pi * 220 * time_axis)
        + 0.24 * np.sin(2 * np.pi * 480 * time_axis)
        + 0.32 * np.sin(2 * np.pi * 6800 * time_axis)
    ).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "workflow-track-eq-dsp.wav"
    sf.write(audio_path, signal, sample_rate)

    plain_snapshot = build_project_snapshot_with_audio(track_audio_paths={10: str(audio_path)})
    eq_snapshot = build_project_snapshot_with_audio(
        track_audio_paths={10: str(audio_path)},
        track_eqs=[
            {
                "track_id": 10,
                "bands": [
                    {
                        "band_order": 1,
                        "eq_type": "BELL",
                        "frequency_hz": 320,
                        "q": 1.1,
                        "gain_delta_db": 10.0,
                    },
                    {
                        "band_order": 2,
                        "eq_type": "HIGH_SHELF",
                        "frequency_hz": 5000,
                        "q": 0.707,
                        "gain_delta_db": -8.0,
                    },
                ],
            }
        ],
    )

    plain_context = build_snapshot_runtime_context(plain_snapshot)
    eq_context = build_snapshot_runtime_context(eq_snapshot)
    plain_state = build_workflow_initial_state(
        job_id=11001,
        project_id=21001,
        project_duration_ms=plain_context.duration_ms,
        track_ids=plain_context.track_ids,
        bpm=plain_context.bpm,
        numerator=plain_context.numerator,
        denominator=plain_context.denominator,
        bar_mapping=plain_context.bar_mapping,
        clip_index=plain_context.clip_index,
        track_eq_map=plain_context.track_eq_map,
    )
    eq_state = build_workflow_initial_state(
        job_id=11002,
        project_id=21002,
        project_duration_ms=eq_context.duration_ms,
        track_ids=eq_context.track_ids,
        bpm=eq_context.bpm,
        numerator=eq_context.numerator,
        denominator=eq_context.denominator,
        bar_mapping=eq_context.bar_mapping,
        clip_index=eq_context.clip_index,
        track_eq_map=eq_context.track_eq_map,
    )

    _, plain_artifact = analysis_nodes._build_compact_dsp_summary(plain_state)
    _, eq_artifact = analysis_nodes._build_compact_dsp_summary(eq_state)
    plain_frame = plain_artifact["track_frames"]["10"][0]
    eq_frame = eq_artifact["track_frames"]["10"][0]

    assert eq_frame["body_energy"] > plain_frame["body_energy"]
    assert eq_frame["high_band_ratio"] < plain_frame["high_band_ratio"]
    assert eq_frame["peak_dbfs"] != plain_frame["peak_dbfs"]


def test_detect_band_overlap_groups_congested_time_region_across_multiple_tracks() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="job-band-region:cheap-dsp",
            job_id=10026,
            artifact_type="full_stft_frame_summary",
            payload={
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.44,
                            "low_mid_energy": 0.05,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.46,
                            "low_mid_energy": 0.05,
                            "window_energy": 0.1,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.39,
                            "low_mid_energy": 0.04,
                            "window_energy": 0.09,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.4,
                            "low_mid_energy": 0.04,
                            "window_energy": 0.09,
                        },
                    ],
                    "30": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.33,
                            "low_mid_energy": 0.04,
                            "window_energy": 0.08,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.34,
                            "low_mid_energy": 0.04,
                            "window_energy": 0.08,
                        },
                    ],
                    "40": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.1,
                            "low_mid_energy": 0.01,
                            "window_energy": 0.07,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.1,
                            "low_mid_energy": 0.01,
                            "window_energy": 0.07,
                        },
                    ],
                }
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=10026,
        project_id=20026,
        issue_types=["band_overlap"],
        clip_feature_artifact_id="job-band-region:cheap-dsp",
    )

    regions = nodes.detect_band_overlap(state)["analysis_regions"]

    assert {region["band_overlap_subtype"] for region in regions} == {
        "body_overlap",
        "low_mid_overlap",
    }
    for region in regions:
        assert set(region["involved_track_ids"]) == {10, 20, 30}
        assert region["track_id"] == 10
        assert region["secondary_track_id"] is None


def test_detect_band_overlap_refines_region_to_actual_overlap_cluster() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-band-refine",
            job_id=100261,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [100, 250, 400, 550, 700, 1000, 2500, 5000],
                "track_frames": {
                    "10": [
                        {"start_ms": 0, "end_ms": 120, "body_energy": 0.58, "low_mid_energy": 0.07, "window_energy": 0.1},
                        {"start_ms": 120, "end_ms": 240, "body_energy": 0.57, "low_mid_energy": 0.07, "window_energy": 0.1},
                    ],
                    "20": [
                        {"start_ms": 0, "end_ms": 120, "body_energy": 0.49, "low_mid_energy": 0.06, "window_energy": 0.1},
                        {"start_ms": 120, "end_ms": 240, "body_energy": 0.5, "low_mid_energy": 0.06, "window_energy": 0.1},
                    ],
                },
                "track_power_spectra": {
                    "10": [
                        [0.01, 0.08, 0.25, 0.72, 0.84, 0.2, 0.02, 0.01],
                        [0.01, 0.07, 0.24, 0.69, 0.81, 0.18, 0.02, 0.01],
                    ],
                    "20": [
                        [0.01, 0.07, 0.22, 0.66, 0.79, 0.2, 0.02, 0.01],
                        [0.01, 0.07, 0.23, 0.64, 0.76, 0.18, 0.02, 0.01],
                    ],
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100261,
        project_id=200261,
        issue_types=["band_overlap"],
        clip_feature_artifact_id="artifact-band-refine",
    )

    regions = nodes.detect_band_overlap(state)["analysis_regions"]

    body_region = next(
        region for region in regions if region["band_overlap_subtype"] == "body_overlap"
    )

    assert body_region["band_low_hz"] == 400
    assert body_region["band_high_hz"] < 1200
    assert 500 <= body_region["center_hz"] <= 700
    assert body_region["band_confidence"] is not None


def test_band_overlap_target_track_excludes_preserved_clip_track() -> None:
    region = {
        "issue_type": "band_overlap",
        "track_id": 10,
        "involved_track_ids": [10, 20, 30],
        "track_body_contributions": {"10": 0.46, "20": 0.41, "30": 0.35},
        "band_overlap_subtype": "body_overlap",
        "start_ms": 0,
        "end_ms": 240,
        "band_low_hz": 250,
        "band_high_hz": 1200,
    }
    state = build_workflow_initial_state(
        job_id=10016,
        project_id=20016,
        clip_index=[
            {"clip_id": _clip_id(10, 1), "track_id": 10},
            {"clip_id": _clip_id(20, 1), "track_id": 20},
            {"clip_id": _clip_id(30, 1), "track_id": 30},
        ],
    )

    action = suggestion_nodes._build_region_action(
        state,
        region=region,
        preserve_clip_id=_clip_id(10, 1),
        index=1,
    )

    assert action is not None
    assert action["targetTrackId"] == 20


def test_detect_band_overlap_adds_presence_subtype_and_refines_high_band_cluster() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-band-presence",
            job_id=100264,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [250, 500, 900, 1800, 2600, 3200, 3800, 4600, 6000],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.16,
                            "low_mid_energy": 0.02,
                            "presence_energy": 0.22,
                            "high_band_ratio": 0.16,
                            "spectral_centroid_hz": 3100,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.15,
                            "low_mid_energy": 0.02,
                            "presence_energy": 0.21,
                            "high_band_ratio": 0.15,
                            "spectral_centroid_hz": 3000,
                            "window_energy": 0.1,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.14,
                            "low_mid_energy": 0.02,
                            "presence_energy": 0.18,
                            "high_band_ratio": 0.15,
                            "spectral_centroid_hz": 2950,
                            "window_energy": 0.09,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.13,
                            "low_mid_energy": 0.02,
                            "presence_energy": 0.19,
                            "high_band_ratio": 0.16,
                            "spectral_centroid_hz": 3050,
                            "window_energy": 0.09,
                        },
                    ],
                },
                "track_power_spectra": {
                    "10": [
                        [0.01, 0.01, 0.02, 0.03, 0.22, 0.76, 0.85, 0.34, 0.03],
                        [0.01, 0.01, 0.02, 0.03, 0.2, 0.74, 0.82, 0.31, 0.03],
                    ],
                    "20": [
                        [0.01, 0.01, 0.02, 0.03, 0.18, 0.7, 0.79, 0.32, 0.03],
                        [0.01, 0.01, 0.02, 0.03, 0.19, 0.72, 0.81, 0.33, 0.03],
                    ],
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100264,
        project_id=200264,
        issue_types=["band_overlap"],
        clip_feature_artifact_id="artifact-band-presence",
    )

    regions = nodes.detect_band_overlap(state)["analysis_regions"]
    presence_region = next(
        region for region in regions if region["band_overlap_subtype"] == "presence_overlap"
    )

    assert presence_region["issue_type"] == "band_overlap"
    assert presence_region["band_low_hz"] >= 2500
    assert presence_region["band_high_hz"] <= 5000
    assert 3000 <= presence_region["center_hz"] <= 4300


def test_detect_band_overlap_adds_upper_mid_subtype_and_refines_band() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-band-upper-mid",
            job_id=100266,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [300, 700, 1100, 1300, 1500, 1700, 1900, 2400, 3200],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.14,
                            "low_mid_energy": 0.03,
                            "upper_mid_energy": 0.18,
                            "presence_energy": 0.04,
                            "high_band_ratio": 0.05,
                            "spectral_centroid_hz": 1450,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.15,
                            "low_mid_energy": 0.03,
                            "upper_mid_energy": 0.19,
                            "presence_energy": 0.04,
                            "high_band_ratio": 0.05,
                            "spectral_centroid_hz": 1480,
                            "window_energy": 0.1,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.13,
                            "low_mid_energy": 0.02,
                            "upper_mid_energy": 0.17,
                            "presence_energy": 0.05,
                            "high_band_ratio": 0.05,
                            "spectral_centroid_hz": 1500,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.14,
                            "low_mid_energy": 0.02,
                            "upper_mid_energy": 0.18,
                            "presence_energy": 0.05,
                            "high_band_ratio": 0.05,
                            "spectral_centroid_hz": 1520,
                            "window_energy": 0.1,
                        },
                    ],
                },
                "track_power_spectra": {
                    "10": [
                        [0.01, 0.02, 0.08, 0.42, 0.86, 0.74, 0.38, 0.06, 0.02],
                        [0.01, 0.02, 0.08, 0.39, 0.82, 0.71, 0.36, 0.05, 0.02],
                    ],
                    "20": [
                        [0.01, 0.02, 0.07, 0.4, 0.81, 0.72, 0.35, 0.06, 0.02],
                        [0.01, 0.02, 0.07, 0.41, 0.83, 0.73, 0.36, 0.06, 0.02],
                    ],
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100266,
        project_id=200266,
        issue_types=["band_overlap"],
        clip_feature_artifact_id="artifact-band-upper-mid",
    )

    regions = nodes.detect_band_overlap(state)["analysis_regions"]
    upper_mid_region = next(
        region for region in regions if region["band_overlap_subtype"] == "upper_mid_overlap"
    )

    assert upper_mid_region["issue_type"] == "band_overlap"
    assert 1200 <= upper_mid_region["band_low_hz"] <= 1700
    assert 1500 <= upper_mid_region["band_high_hz"] <= 2000
    assert 1350 <= upper_mid_region["center_hz"] <= 1850


def test_detect_band_overlap_keeps_different_subtypes_unmerged() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-band-subtype-merge",
            job_id=100265,
            artifact_type="full_stft_frame_summary",
            payload={
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.56,
                            "low_mid_energy": 0.08,
                            "presence_energy": 0.22,
                            "high_band_ratio": 0.16,
                            "spectral_centroid_hz": 3200,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.55,
                            "low_mid_energy": 0.08,
                            "presence_energy": 0.21,
                            "high_band_ratio": 0.16,
                            "spectral_centroid_hz": 3150,
                            "window_energy": 0.1,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "body_energy": 0.52,
                            "low_mid_energy": 0.06,
                            "presence_energy": 0.18,
                            "high_band_ratio": 0.15,
                            "spectral_centroid_hz": 3000,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "body_energy": 0.51,
                            "low_mid_energy": 0.06,
                            "presence_energy": 0.18,
                            "high_band_ratio": 0.15,
                            "spectral_centroid_hz": 3050,
                            "window_energy": 0.1,
                        },
                    ],
                }
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100265,
        project_id=200265,
        issue_types=["band_overlap"],
        clip_feature_artifact_id="artifact-band-subtype-merge",
    )

    regions = nodes.detect_band_overlap(state)["analysis_regions"]

    assert len(regions) == 3
    assert len({region["band_overlap_subtype"] for region in regions}) == 3


def test_detect_high_band_harshness_refines_band_to_prominent_peak() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-harshness-refine",
            job_id=100262,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [1000, 2500, 4000, 4800, 5400, 6100, 7200, 8400],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "high_band_ratio": 0.38,
                            "presence_energy": 0.09,
                            "spectral_centroid_hz": 4200,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "high_band_ratio": 0.37,
                            "presence_energy": 0.08,
                            "spectral_centroid_hz": 4100,
                            "window_energy": 0.1,
                        },
                    ]
                },
                "track_power_spectra": {
                    "10": [
                        [0.02, 0.04, 0.08, 0.15, 0.82, 0.79, 0.18, 0.07],
                        [0.02, 0.04, 0.08, 0.14, 0.79, 0.77, 0.17, 0.07],
                    ]
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100262,
        project_id=200262,
        issue_types=["high_band_harshness"],
        clip_feature_artifact_id="artifact-harshness-refine",
    )

    regions = nodes.detect_high_band_harshness(state)["analysis_regions"]

    assert len(regions) == 1
    assert regions[0]["band_low_hz"] == 4800
    assert regions[0]["band_high_hz"] < 9000
    assert 5400 <= regions[0]["center_hz"] <= 7000
    assert regions[0]["requires_user_action"] is False


def test_detect_sibilance_refines_band_to_sibilant_cluster() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-sibilance-refine",
            job_id=100263,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [1000, 2500, 4000, 5500, 6200, 7000, 7800, 8400],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "sibilance_ratio": 0.24,
                            "high_band_ratio": 0.26,
                            "spectral_centroid_hz": 2600,
                            "window_energy": 0.1,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "sibilance_ratio": 0.23,
                            "high_band_ratio": 0.25,
                            "spectral_centroid_hz": 2500,
                            "window_energy": 0.1,
                        },
                    ]
                },
                "track_power_spectra": {
                    "10": [
                        [0.02, 0.03, 0.05, 0.09, 0.18, 0.84, 0.8, 0.18],
                        [0.02, 0.03, 0.05, 0.09, 0.17, 0.81, 0.78, 0.17],
                    ]
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100263,
        project_id=200263,
        issue_types=["sibilance"],
        clip_feature_artifact_id="artifact-sibilance-refine",
        inferred_roles={10: "vocal-like"},
        vocal_detected=True,
    )

    regions = nodes.detect_sibilance(state)["analysis_regions"]

    assert len(regions) == 1
    assert regions[0]["band_low_hz"] == 6200
    assert regions[0]["band_high_hz"] < 8500
    assert 6800 <= regions[0]["center_hz"] <= 8000


def test_compute_mix_frames_uses_4x_oversampled_true_peak() -> None:
    signal = (0.98 * np.sin(2 * np.pi * 0.1875 * np.arange(1536))).astype(np.float32)

    frames = analysis_nodes._compute_mix_frames(signal, target_track_id=1)
    first_frame = signal[: analysis_nodes.STFT_WIN_LENGTH]

    expected_true_peak = float(
        np.max(
            np.abs(
                resample_poly(
                    first_frame,
                    up=analysis_nodes.TRUE_PEAK_OVERSAMPLE_FACTOR,
                    down=1,
                )
            )
        )
    )
    assert frames[0]["peak_dbfs"] < 0.0
    assert frames[0]["true_peak_dbfs"] > frames[0]["peak_dbfs"]
    assert frames[0]["true_peak_dbfs"] == round(analysis_nodes._to_dbfs(expected_true_peak), 3)


def test_detect_clipping_can_trigger_on_oversampled_true_peak() -> None:
    signal = (0.98 * np.sin(2 * np.pi * 0.1875 * np.arange(1536))).astype(np.float32)
    mix_frames = analysis_nodes._compute_mix_frames(signal, target_track_id=11)
    state = build_workflow_initial_state(
        job_id=10027,
        project_id=20027,
        issue_types=["master_clipping"],
        clip_feature_artifact_id="artifact-true-peak",
    )
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-true-peak",
            job_id=10027,
            artifact_type="full_stft_frame_summary",
            payload={"mix_frames": mix_frames},
        )
    )

    regions = nodes.detect_master_clipping(state)["analysis_regions"]

    assert mix_frames[0]["peak_dbfs"] < 0.0
    assert mix_frames[0]["true_peak_dbfs"] > 0.0
    assert len(regions) == 1
    assert regions[0]["issue_type"] == "master_clipping"


def test_detect_clipping_ignores_near_ceiling_without_true_peak_overflow() -> None:
    signal = (0.995 * np.sin(2 * np.pi * 0.25 * np.arange(1536))).astype(np.float32)
    mix_frames = analysis_nodes._compute_mix_frames(signal, target_track_id=11)
    state = build_workflow_initial_state(
        job_id=10028,
        project_id=20028,
        issue_types=["master_clipping"],
        clip_feature_artifact_id="artifact-near-ceiling",
    )
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-near-ceiling",
            job_id=10028,
            artifact_type="full_stft_frame_summary",
            payload={"mix_frames": mix_frames},
        )
    )

    regions = nodes.detect_master_clipping(state)["analysis_regions"]

    assert mix_frames[0]["peak_dbfs"] >= -0.1
    assert mix_frames[0]["true_peak_dbfs"] <= 0.0
    assert regions == []


def test_master_clipping_promotes_clear_contributor_to_track_fix() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-master-promote",
            job_id=10034,
            artifact_type="full_stft_frame_summary",
            payload={
                "mix_frames": [
                    {
                        "start_ms": 0,
                        "end_ms": 96,
                        "peak_dbfs": -0.02,
                        "true_peak_dbfs": 0.22,
                        "clip_ratio": 0.02,
                    },
                    {
                        "start_ms": 96,
                        "end_ms": 192,
                        "peak_dbfs": -0.01,
                        "true_peak_dbfs": 0.24,
                        "clip_ratio": 0.02,
                    },
                ],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 96,
                            "peak_dbfs": 0.18,
                            "window_energy": 0.92,
                            "low_mid_energy": 0.08,
                            "body_energy": 0.11,
                            "high_band_ratio": 0.14,
                        },
                        {
                            "start_ms": 96,
                            "end_ms": 192,
                            "peak_dbfs": 0.16,
                            "window_energy": 0.9,
                            "low_mid_energy": 0.07,
                            "body_energy": 0.1,
                            "high_band_ratio": 0.13,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 96,
                            "peak_dbfs": -6.0,
                            "window_energy": 0.12,
                            "low_mid_energy": 0.06,
                            "body_energy": 0.08,
                            "high_band_ratio": 0.09,
                        },
                        {
                            "start_ms": 96,
                            "end_ms": 192,
                            "peak_dbfs": -5.8,
                            "window_energy": 0.11,
                            "low_mid_energy": 0.06,
                            "body_energy": 0.08,
                            "high_band_ratio": 0.08,
                        },
                    ],
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=10034,
        project_id=20034,
        issue_types=["master_clipping"],
        clip_feature_artifact_id="artifact-master-promote",
    )

    result = nodes.detect_master_clipping(state)

    track_regions = [
        region for region in result["analysis_regions"] if region["issue_type"] == "track_clipping"
    ]
    master_regions = [
        region for region in result["analysis_regions"] if region["issue_type"] == "master_clipping"
    ]
    groups = runtime_nodes._build_non_user_issue_recipe_groups(result)

    assert len(track_regions) == 1
    assert master_regions == []
    assert track_regions[0]["track_id"] == 10
    assert track_regions[0]["auto_fix_source"] == "promoted_master_contributor"
    assert len(groups) == 1
    assert groups[0]["issueType"] == "track_clipping"
    assert groups[0]["recipes"][0]["actionType"] == "TRUE_PEAK_LIMITER"
    assert groups[0]["recipes"][0]["targetScope"] == "MASTER"


def test_master_clipping_keeps_master_recipe_when_contributors_are_distributed() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-master-distributed",
            job_id=10035,
            artifact_type="full_stft_frame_summary",
            payload={
                "mix_frames": [
                    {
                        "start_ms": 0,
                        "end_ms": 96,
                        "peak_dbfs": -0.03,
                        "true_peak_dbfs": 0.18,
                        "clip_ratio": 0.02,
                    },
                    {
                        "start_ms": 96,
                        "end_ms": 192,
                        "peak_dbfs": -0.02,
                        "true_peak_dbfs": 0.19,
                        "clip_ratio": 0.02,
                    },
                ],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 96,
                            "peak_dbfs": -0.05,
                            "window_energy": 0.42,
                            "low_mid_energy": 0.11,
                            "body_energy": 0.14,
                            "high_band_ratio": 0.16,
                        },
                        {
                            "start_ms": 96,
                            "end_ms": 192,
                            "peak_dbfs": -0.05,
                            "window_energy": 0.42,
                            "low_mid_energy": 0.11,
                            "body_energy": 0.14,
                            "high_band_ratio": 0.16,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 96,
                            "peak_dbfs": -0.04,
                            "window_energy": 0.41,
                            "low_mid_energy": 0.11,
                            "body_energy": 0.14,
                            "high_band_ratio": 0.16,
                        },
                        {
                            "start_ms": 96,
                            "end_ms": 192,
                            "peak_dbfs": -0.04,
                            "window_energy": 0.41,
                            "low_mid_energy": 0.11,
                            "body_energy": 0.14,
                            "high_band_ratio": 0.16,
                        },
                    ],
                    "30": [
                        {
                            "start_ms": 0,
                            "end_ms": 96,
                            "peak_dbfs": -0.05,
                            "window_energy": 0.4,
                            "low_mid_energy": 0.11,
                            "body_energy": 0.14,
                            "high_band_ratio": 0.16,
                        },
                        {
                            "start_ms": 96,
                            "end_ms": 192,
                            "peak_dbfs": -0.05,
                            "window_energy": 0.4,
                            "low_mid_energy": 0.11,
                            "body_energy": 0.14,
                            "high_band_ratio": 0.16,
                        },
                    ],
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=10035,
        project_id=20035,
        issue_types=["master_clipping"],
        clip_feature_artifact_id="artifact-master-distributed",
    )

    result = nodes.detect_master_clipping(state)

    master_regions = [
        region for region in result["analysis_regions"] if region["issue_type"] == "master_clipping"
    ]
    track_regions = [
        region for region in result["analysis_regions"] if region["issue_type"] == "track_clipping"
    ]
    groups = runtime_nodes._build_non_user_issue_recipe_groups(result)

    assert track_regions == []
    assert len(master_regions) == 1
    assert set(master_regions[0]["contributing_track_ids"]) == {10, 20, 30}
    assert groups == []


def test_detect_track_clipping_marks_band_driven_region_with_precise_band() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-track-clipping-band",
            job_id=100264,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [100, 300, 600, 1200, 3000, 5000, 6500, 7800],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "peak_dbfs": 0.12,
                            "high_band_ratio": 0.31,
                            "window_energy": 0.2,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "peak_dbfs": 0.11,
                            "high_band_ratio": 0.3,
                            "window_energy": 0.2,
                        },
                    ]
                },
                "track_power_spectra": {
                    "10": [
                        [0.01, 0.02, 0.02, 0.03, 0.08, 0.22, 0.85, 0.72],
                        [0.01, 0.02, 0.02, 0.03, 0.08, 0.21, 0.83, 0.69],
                    ]
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100264,
        project_id=200264,
        issue_types=["track_clipping"],
        clip_feature_artifact_id="artifact-track-clipping-band",
    )

    regions = nodes.detect_track_clipping(state)["analysis_regions"]

    assert len(regions) == 1
    assert regions[0]["band_low_hz"] == 5000
    assert regions[0]["band_high_hz"] == 7800
    assert regions[0]["broadband_classification"] == "band_driven"
    assert "high" in regions[0]["band_hints"]
    assert regions[0]["requires_user_action"] is False


def test_detect_track_clipping_uses_true_peak_for_limiter_recommendation() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-track-clipping-true-peak",
            job_id=100266,
            artifact_type="full_stft_frame_summary",
            payload={
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "peak_dbfs": -0.2,
                            "true_peak_dbfs": 0.45,
                            "high_band_ratio": 0.2,
                            "window_energy": 0.2,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "peak_dbfs": -0.22,
                            "true_peak_dbfs": 0.42,
                            "high_band_ratio": 0.19,
                            "window_energy": 0.19,
                        },
                    ]
                }
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100266,
        project_id=200266,
        issue_types=["track_clipping"],
        clip_feature_artifact_id="artifact-track-clipping-true-peak",
    )

    regions = nodes.detect_track_clipping(state)["analysis_regions"]

    assert len(regions) == 1
    assert regions[0]["current_true_peak_dbtp"] > 0.4
    assert regions[0]["recommended_reduction_db"] > 1.3


def test_detect_track_clipping_keeps_broadband_region_without_band() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-track-clipping-broadband",
            job_id=100265,
            artifact_type="full_stft_frame_summary",
            payload={
                "frequency_bins_hz": [100, 300, 600, 1200, 3000, 5000, 6500, 7800],
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "peak_dbfs": 0.12,
                            "high_band_ratio": 0.14,
                            "window_energy": 0.2,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "peak_dbfs": 0.11,
                            "high_band_ratio": 0.14,
                            "window_energy": 0.2,
                        },
                    ]
                },
                "track_power_spectra": {
                    "10": [
                        [0.2, 0.21, 0.19, 0.18, 0.2, 0.19, 0.21, 0.2],
                        [0.19, 0.2, 0.2, 0.19, 0.2, 0.19, 0.2, 0.19],
                    ]
                },
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=100265,
        project_id=200265,
        issue_types=["track_clipping"],
        clip_feature_artifact_id="artifact-track-clipping-broadband",
    )

    regions = nodes.detect_track_clipping(state)["analysis_regions"]

    assert len(regions) == 1
    assert regions[0]["band_low_hz"] is None
    assert regions[0]["band_high_hz"] is None
    assert regions[0]["center_hz"] is None
    assert regions[0]["band_confidence"] is None
    assert regions[0]["broadband_classification"] == "broadband"
    assert regions[0]["band_hints"] == ["broadband"]


def test_track_clipping_recipe_uses_master_limiter_for_high_band_hint() -> None:
    recipe = runtime_nodes._build_track_clipping_fix_recipe(
        {
            "id": 1,
            "track_id": 10,
            "start_ms": 0,
            "end_ms": 200,
            "score": 0.42,
            "band_hints": ["high"],
        }
    )

    assert recipe is not None
    assert recipe["actionType"] == "TRUE_PEAK_LIMITER"
    assert recipe["targetScope"] == "MASTER"
    assert recipe.get("targetTrackId") is None
    assert recipe["params"]["ceilingDbfs"] == -1.0


def test_track_clipping_recipe_keeps_master_limiter_with_refined_band_context() -> None:
    recipe = runtime_nodes._build_track_clipping_fix_recipe(
        {
            "id": 11,
            "track_id": 10,
            "start_ms": 0,
            "end_ms": 200,
            "score": 0.42,
            "band_low_hz": 5200,
            "band_high_hz": 7600,
            "band_hints": ["high"],
            "broadband_classification": "band_driven",
        }
    )

    assert recipe is not None
    assert recipe["actionType"] == "TRUE_PEAK_LIMITER"
    assert recipe["targetScope"] == "MASTER"
    assert recipe["params"]["ceilingDbfs"] == -1.0


def test_track_clipping_recipe_uses_master_limiter_for_low_mid_hint() -> None:
    recipe = runtime_nodes._build_track_clipping_fix_recipe(
        {
            "id": 2,
            "track_id": 11,
            "start_ms": 0,
            "end_ms": 200,
            "score": 0.35,
            "band_hints": ["low_mid"],
        }
    )

    assert recipe is not None
    assert recipe["actionType"] == "TRUE_PEAK_LIMITER"
    assert recipe["targetScope"] == "MASTER"
    assert recipe["params"]["ceilingDbfs"] == -1.0


def test_track_clipping_recipe_keeps_master_limiter_for_broadband_hint() -> None:
    recipe = runtime_nodes._build_track_clipping_fix_recipe(
        {
            "id": 3,
            "track_id": 12,
            "start_ms": 0,
            "end_ms": 200,
            "score": 0.35,
            "band_hints": ["broadband"],
        }
    )

    assert recipe is not None
    assert recipe["actionType"] == "TRUE_PEAK_LIMITER"
    assert recipe["targetScope"] == "MASTER"


def test_workflow_defaults_include_clipping_detection() -> None:
    sample_rate = 16000
    signal = (0.98 * np.sin(2 * np.pi * 0.1875 * np.arange(sample_rate * 2))).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "workflow-default-clipping.wav"
    sf.write(audio_path, signal, sample_rate)

    result = run_workflow_graph(
        {
            "job_id": 10032,
            "project_id": 20032,
            "project_snapshot": build_project_snapshot_with_audio(
                track_audio_paths={10: str(audio_path)}
            ),
        }
    )

    assert (
        "track_clipping" in result["detected_issues"]
        or "master_clipping" in result["detected_issues"]
    )
    if "track_clipping" in result["detected_issues"]:
        assert result["current_node"] == "finalize_output"
        assert result["runtime_status"] == "completed"
        clipping_issue = next(
            issue
            for issue in result["suggestion_payload"]["issues"]
            if issue["issueType"] == "track_clipping"
        )
        assert clipping_issue["uiMode"] == "master_limiter"
    else:
        assert result["current_node"] == "finalize_output"


def test_workflow_skips_sibilance_when_clap_candidate_is_absent() -> None:
    sample_rate = 16000
    duration_seconds = 4.8
    time_axis = np.linspace(
        0,
        duration_seconds,
        int(sample_rate * duration_seconds),
        endpoint=False,
    )
    supporting = (0.24 * np.sin(2 * np.pi * 220 * time_axis)).astype(np.float32)
    audio_dir = Path(gettempdir()) / "studion-ai-test-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "workflow-no-sibilance-candidate.wav"
    sf.write(audio_path, supporting, sample_rate)

    result = run_workflow_graph(
        {
            "job_id": 10033,
            "project_id": 20033,
            "project_snapshot": build_project_snapshot_with_audio(
                track_audio_paths={10: str(audio_path)}
            ),
            "issue_types": ["sibilance"],
        }
    )

    assert result["inferred_roles"] == {}
    assert result["vocal_detected"] is False
    assert "sibilance" not in result["detected_issues"]
    assert result["current_node"] == "finalize_output"


def test_detect_sibilance_uses_only_vocal_like_tracks() -> None:
    artifact_store = get_workflow_artifact_store()
    artifact_store.reset()
    artifact_store.upsert_artifact(
        WorkflowArtifactDocument(
            id="artifact-sibilance-role-aware",
            job_id=10029,
            artifact_type="full_stft_frame_summary",
            payload={
                "track_frames": {
                    "10": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "sibilance_ratio": 0.24,
                            "high_band_ratio": 0.26,
                            "spectral_centroid_hz": 4200,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "sibilance_ratio": 0.23,
                            "high_band_ratio": 0.25,
                            "spectral_centroid_hz": 4100,
                        },
                    ],
                    "20": [
                        {
                            "start_ms": 0,
                            "end_ms": 120,
                            "sibilance_ratio": 0.28,
                            "high_band_ratio": 0.29,
                            "spectral_centroid_hz": 4300,
                        },
                        {
                            "start_ms": 120,
                            "end_ms": 240,
                            "sibilance_ratio": 0.27,
                            "high_band_ratio": 0.28,
                            "spectral_centroid_hz": 4250,
                        },
                    ],
                }
            },
        )
    )
    state = build_workflow_initial_state(
        job_id=10029,
        project_id=20029,
        issue_types=["sibilance"],
        clip_feature_artifact_id="artifact-sibilance-role-aware",
        inferred_roles={10: "vocal-like", 20: "supporting"},
        vocal_detected=True,
    )

    regions = nodes.detect_sibilance(state)["analysis_regions"]

    assert len(regions) == 1
    assert regions[0]["track_id"] == 10
    assert regions[0]["issue_type"] == "sibilance"
    assert regions[0]["requires_user_action"] is False


def test_clipping_autofix_excludes_master_clipping_recipe_groups() -> None:
    result = run_workflow_graph(
        {
            "job_id": 10030,
            "project_id": 20030,
            "project_snapshot": build_project_snapshot(track_ids=[14, 15]),
            "issue_types": ["clipping"],
        }
    )
    artifact_store = get_workflow_artifact_store()
    recipe_artifact = artifact_store.get_artifact(result["auto_fix_recipe_artifact_id"])

    if recipe_artifact is not None:
        assert all(
            group["issueType"] != "master_clipping"
            for group in recipe_artifact.payload["groups"]
        )
