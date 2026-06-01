from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import lfilter, resample_poly

from app.core.config import get_settings
from app.graph.nodes.common import artifact_id, clear_raw_dsp_state, workflow_update
from app.graph.state import WorkflowState, utc_now
from app.services.clap_inference import (
    CLAPExcerptPayload,
    CLAPInferenceError,
    get_clap_inference_client,
)
from app.services.workflow_artifacts import (
    WorkflowArtifactDocument,
    get_workflow_artifact_store,
)
from app.services.workflow_analysis_regions import (
    AnalysisRegionCreate,
    get_workflow_analysis_region_store,
)
from app.services.workflow_audio_paths import AudioPathResolutionError, resolve_clip_audio_path
from app.services.workflow_snapshots import get_workflow_snapshot_store

# 실제 DSP는 프로젝트 전체 타임라인을 기준으로 STFT를 계산한다.
# state에는 전체 행렬을 남기지 않고, frame 단위 요약은 Mongo/in-memory artifact에 저장한다.
# DSP_TARGET_SR: 분석용 공통 샘플레이트
# STFT_N_FFT: 한 frame의 FFT 크기
# STFT_WIN_LENGTH: 실제 분석 window 길이
# STFT_HOP_LENGTH: frame 이동 간격
# STFT_WINDOW: STFT 창 함수
# MERGE_GAP_MS: region 병합 허용 간격

DSP_TARGET_SR = 16000
STFT_N_FFT = 1024
STFT_WIN_LENGTH = 1024
STFT_HOP_LENGTH = 256
STFT_WINDOW = "hann"
MERGE_GAP_MS = 96
TRUE_PEAK_OVERSAMPLE_FACTOR = 4
MASTER_CLIPPING_CONTRIBUTOR_SCORE_THRESHOLD = 0.34
MASTER_CLIPPING_PROMOTION_MARGIN = 0.12
MASTER_CLIPPING_DISTRIBUTED_COUNT = 3
MASTER_CLIPPING_DISTRIBUTED_TOP_SCORE = 0.5

BAND_RANGES = {
    "low_mid": (180, 420),
    "body": (250, 1200),
    "upper_mid": (1200, 2000),
    "presence": (2500, 5000),
    "harshness": (4500, 9000),
    "sibilance": (6000, 8500),
}
# LangGraph
ISSUE_MIN_DURATION_MS = {
    "band_overlap": 180,
    "track_clipping": 80,
    "master_clipping": 80,
    "sibilance": 96,
    "high_band_harshness": 160,
}
BAND_OVERLAP_FRAME_MIN_WINDOW_ENERGY = 0.01
BAND_OVERLAP_FRAME_MIN_BODY_ENERGY = 0.18
BAND_OVERLAP_FRAME_MIN_LOW_MID_ENERGY = 0.04
BAND_OVERLAP_FRAME_MIN_ACTIVE_TRACKS = 2
BAND_OVERLAP_FRAME_MIN_BODY_SUM = 1.05
BAND_OVERLAP_FRAME_MIN_LOW_MID_SUM = 0.12
BAND_OVERLAP_SUBTYPE_CONFIG = {
    "low_mid_overlap": {
        "focus_energy_key": "low_mid_energy",
        "support_energy_key": "body_energy",
        "min_track_energy": 0.04,
        "min_support_energy": 0.18,
        "min_focus_sum": 0.12,
        "min_support_sum": 0.78,
        "min_active_tracks": 2,
        "fallback_band": BAND_RANGES["low_mid"],
        "refine_band": BAND_RANGES["low_mid"],
        "summary": "트랙들이 겹치는 구간에서 저중역이 서로 부딪혀 답답하게 들릴 수 있습니다.",
        "ranking_adjustment": 0.035,
    },
    "body_overlap": {
        "focus_energy_key": "body_energy",
        "support_energy_key": "low_mid_energy",
        "min_track_energy": 0.18,
        "min_support_energy": 0.04,
        "min_focus_sum": 1.05,
        "min_support_sum": 0.12,
        "min_active_tracks": 2,
        "fallback_band": BAND_RANGES["body"],
        "refine_band": BAND_RANGES["body"],
        "summary": "트랙들이 겹치는 구간에서 바디 대역이 몰려 소리가 두껍고 혼탁하게 들릴 수 있습니다.",
        "ranking_adjustment": 0.0,
    },
    "upper_mid_overlap": {
        "focus_energy_key": "upper_mid_energy",
        "support_energy_key": "body_energy",
        "min_track_energy": 0.12,
        "min_support_energy": 0.08,
        "min_focus_sum": 0.28,
        "min_support_sum": 0.26,
        "min_active_tracks": 2,
        "min_centroid_hz": 900,
        "fallback_band": BAND_RANGES["upper_mid"],
        "refine_band": BAND_RANGES["upper_mid"],
        "summary": "중고역 존재감이 겹치면서 소리가 동시에 앞으로 튀어 들릴 수 있습니다.",
        "ranking_adjustment": -0.015,
    },
    "presence_overlap": {
        "focus_energy_key": "presence_energy",
        "support_energy_key": "high_band_ratio",
        "min_track_energy": 0.1,
        "min_support_energy": 0.12,
        "min_focus_sum": 0.34,
        "min_support_sum": 0.3,
        "min_active_tracks": 2,
        "min_centroid_hz": 2200,
        "fallback_band": BAND_RANGES["presence"],
        "refine_band": BAND_RANGES["presence"],
        "summary": "트랙들이 겹치는 구간에서 프레즌스 대역이 부딪혀 선명함이 과하게 경쟁하고 있습니다.",
        "ranking_adjustment": -0.04,
    },
}
REFINEMENT_SMOOTHING_BINS = 5
REFINEMENT_CLUSTER_PEAK_RATIO = 0.6
REFINEMENT_CLUSTER_FLOOR = 1e-4
CLIPPING_BAND_DRIVEN_MIN_SHARE = 0.22
CLIPPING_BAND_DRIVEN_MIN_CONSISTENCY = 0.55
CLIPPING_ANALYSIS_MIN_HZ = 120
CLIPPING_ANALYSIS_MAX_HZ = 9000


class DSPBuildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# start API에서 저장한 timeline snapshot 기준선을 다시 읽어 state에 복원한다.
def load_project_snapshot(state: WorkflowState) -> WorkflowState:
    current_artifact_id = artifact_id(state, "snapshot")
    snapshot_id = state.get("timeline_snapshot_id") or f"{state['job_id']}-timeline-snapshot"
    snapshot_document = get_workflow_snapshot_store().get_snapshot(snapshot_id)
    extra: dict[str, object] = {
        "timeline_snapshot_id": snapshot_id,
        "mongo_artifact_ids": [*state.get("mongo_artifact_ids", []), current_artifact_id],
        "latest_artifact_id": current_artifact_id,
    }
    if snapshot_document is not None:
        extra.update(
            {
                "project_duration_ms": state.get("project_duration_ms")
                or snapshot_document.duration_ms,
                "track_ids": state.get("track_ids") or snapshot_document.track_ids,
                "bpm": state.get("bpm") or snapshot_document.bpm,
                "numerator": state.get("numerator") or snapshot_document.numerator,
                "denominator": state.get("denominator") or snapshot_document.denominator,
                "bar_mapping": state.get("bar_mapping") or snapshot_document.bar_mapping,
                "clip_index": state.get("clip_index") or snapshot_document.clip_index,
                "track_eq_map": state.get("track_eq_map") or {
                    int(track_id): bands
                    for track_id, bands in snapshot_document.track_eq_map.items()
                },
            }
        )
    return workflow_update(
        state,
        node="load_project_snapshot",
        phase="project_snapshot_loaded",
        progress=8,
        extra=extra,
    )


# 각 트랙에서 대표 clip id 하나씩을 뽑아 이후 응답과 디버깅에 쓴다.
# 트랙마다 여기서 고른 원본 wav/mp3 파일을 CLAP에 보냄.
def sample_track_clips(state: WorkflowState) -> WorkflowState:
    """
    representative_specs
    {
      "track_id": 10,
      "clip_id": "clip-10-1",
      "resolved_audio_path": ".../track-10.wav",
      "source_format": ".wav",
    }
    """
    representative_specs = _build_track_representative_specs(
        state
    )  # 트랙별 CLAP 판정에 들어갈 원본 파일 중간 데이터
    sampled_clip_ids = [int(spec["clip_id"]) for spec in representative_specs]
    return workflow_update(
        state,
        node="sample_track_clips",
        phase="track_clips_sampled",
        progress=12,
        extra={
            "sampled_clip_ids": sampled_clip_ids,
            "track_representative_specs": representative_specs,
        },
    )


# 프로젝트 전체 타임라인 signal을 복원한 뒤 track별 full STFT를 계산한다.
# 결과는 frame 요약 artifact로 저장하고, state에는 작은 summary만 남긴다.
"""
- analysis_regions :
  최종적으로 workflow state에 저장되는 분석 구간 목록, 하나의 원소는 region 하나를 뜻함
- detected_issues : 이번 job에서 실제로 발견된 이슈 타입들의 목록 (예시 : ["clipping", "sibilance"])
- materialized_regions : state에 넣기 직전의 완성된 region 리스트
"""
def cheap_dsp_scan(state: WorkflowState) -> WorkflowState:
    try:
        summary, raw_dsp_payload = _build_compact_dsp_summary(state)
    except DSPBuildError as exc:
        return workflow_update(
            state,
            node="cheap_dsp_scan",
            phase="failed",
            progress=18,
            runtime_status="failed",
            durable_status="FAILED",
            extra={
                "completed_at": utc_now(),
                "failure_code": exc.code,
                "failure_message": exc.message,
                **clear_raw_dsp_state(),
            },
        )
    return workflow_update(
        state,
        node="cheap_dsp_scan",
        phase="cheap_dsp_scanned",
        progress=18,
        extra={
            "analysis_regions": deepcopy(state.get("analysis_regions", [])),
            "dsp_scan_summary": summary,
            **raw_dsp_payload,
        },
    )


def detect_band_overlap(state: WorkflowState) -> WorkflowState:
    return _detect_issue_regions(
        state,
        node="detect_band_overlap",
        phase="band_overlap_detected",
        progress=24,
        issue="band_overlap",
        detector=_find_band_overlap_regions,
    )


def detect_track_clipping(state: WorkflowState) -> WorkflowState:
    return _detect_issue_regions(
        state,
        node="detect_track_clipping",
        phase="track_clipping_detected",
        progress=28,
        issue="track_clipping",
        detector=_find_track_clipping_regions,
    )


def detect_master_clipping_candidates(state: WorkflowState) -> WorkflowState:
    candidates = _find_master_clipping_candidate_regions(state)
    normalized_candidates = [
        {
            **candidate,
            "candidate_id": f"{state['job_id']}-master-candidate-{index}",
        }
        for index, candidate in enumerate(candidates, start=1)
    ]
    return workflow_update(
        state,
        node="detect_master_clipping_candidates",
        phase="master_clipping_candidates_detected",
        progress=30,
        extra={
            "master_clipping_candidates": normalized_candidates,
            "master_clipping_contributors": [],
            "promoted_track_clipping_regions": [],
        },
    )


def analyze_master_clipping_contributors(state: WorkflowState) -> WorkflowState:
    candidates = deepcopy(state.get("master_clipping_candidates", []))
    contributors = _analyze_master_clipping_candidate_contributors(state, candidates)
    return workflow_update(
        state,
        node="analyze_master_clipping_contributors",
        phase="master_clipping_contributors_analyzed",
        progress=31,
        extra={
            "master_clipping_candidates": candidates,
            "master_clipping_contributors": contributors,
        },
    )


def detect_residual_master_clipping(state: WorkflowState) -> WorkflowState:
    return _detect_residual_master_clipping(state)


def detect_master_clipping(state: WorkflowState) -> WorkflowState:
    candidate_delta = detect_master_clipping_candidates(state)
    candidate_state: WorkflowState = {**state, **candidate_delta}
    contributor_delta = analyze_master_clipping_contributors(candidate_state)
    contributor_state: WorkflowState = {**candidate_state, **contributor_delta}
    residual_delta = detect_residual_master_clipping(contributor_state)
    return {**contributor_state, **residual_delta}


def detect_clipping(state: WorkflowState) -> WorkflowState:
    return detect_master_clipping(state)


def detect_high_band_harshness(state: WorkflowState) -> WorkflowState:
    return _detect_issue_regions(
        state,
        node="detect_high_band_harshness",
        phase="high_band_harshness_detected",
        progress=32,
        issue="high_band_harshness",
        detector=_find_high_band_harshness_regions,
    )


def select_role_candidates(state: WorkflowState) -> WorkflowState:
    role_candidates = _find_role_candidate_track_ids(state)
    return workflow_update(
        state,
        node="select_role_candidates",
        phase="role_candidates_selected",
        progress=36,
        extra={
            "role_candidate_track_ids": role_candidates,
        },
    )


def _find_role_candidate_track_ids(state: WorkflowState) -> list[int]:
    if "sibilance" not in state.get("issue_types", []):
        return []

    candidate_track_ids = {
        int(region["track_id"])
        for region in state.get("analysis_regions", [])
        if region.get("issue_type") == "high_band_harshness" and region.get("track_id") is not None
    }
    if candidate_track_ids:
        return sorted(candidate_track_ids)

    artifact = _load_dsp_feature_artifact(state)
    track_frames_by_id = {
        int(track_id): frames for track_id, frames in artifact.get("track_frames", {}).items()
    }
    for track_id, windows in track_frames_by_id.items():
        for window in windows:
            if (
                window["high_band_ratio"] >= 0.38
                and window["presence_energy"] >= 0.08
                and window["spectral_centroid_hz"] >= 3600
            ):
                candidate_track_ids.add(track_id)
                break
    return sorted(candidate_track_ids)


def clap_gate(state: WorkflowState) -> WorkflowState:
    return workflow_update(
        state,
        node="clap_gate",
        phase="clap_need_decided",
        progress=38,
    )

# sample_track_clips를 읽어서 실제 파일 bytes를 만들고 CLAP 요청 payload 생성
def infer_track_roles(state: WorkflowState) -> WorkflowState:
    current_artifact_id = artifact_id(state, "clap-track-roles")
    notes = [*state.get("notes", [])]
    try:
        excerpt_payloads, excerpt_metadata = _build_clap_track_payloads(state)
        threshold = float(get_settings().clap_vocal_threshold)
        predictions = get_clap_inference_client().infer_track_roles(
            job_id=state["job_id"],
            excerpts=excerpt_payloads,
        )
    except (DSPBuildError, CLAPInferenceError) as exc:
        return workflow_update(
            state,
            node="infer_track_roles",
            phase="failed",
            progress=44,
            runtime_status="failed",
            durable_status="FAILED",
            extra={
                "completed_at": utc_now(),
                "failure_code": exc.code,
                "failure_message": exc.message,
            },
        )

    prediction_by_track_id = {prediction.track_id: prediction for prediction in predictions}
    candidate_track_ids = [int(track_id) for track_id in state.get("role_candidate_track_ids", [])]
    missing_track_ids = [
        track_id for track_id in candidate_track_ids if track_id not in prediction_by_track_id
    ]
    if missing_track_ids:
        return workflow_update(
            state,
            node="infer_track_roles",
            phase="failed",
            progress=44,
            runtime_status="failed",
            durable_status="FAILED",
            extra={
                "completed_at": utc_now(),
                "failure_code": "CLAP_INFERENCE_INCOMPLETE",
                "failure_message": (
                    "CLAP inference did not return predictions for candidate tracks: "
                    + ", ".join(str(track_id) for track_id in missing_track_ids)
                ),
            },
        )

    inferred_roles: dict[int, str] = {}
    track_role_scores: dict[int, float] = {}
    track_role_confidences: dict[int, float] = {}
    artifact_predictions: list[dict[str, object]] = []
    for track_id in candidate_track_ids:
        prediction = prediction_by_track_id[track_id]
        track_role_scores[track_id] = round(float(prediction.vocal_score), 4)
        if prediction.confidence is not None:
            track_role_confidences[track_id] = round(float(prediction.confidence), 4)
        inferred_roles[track_id] = (
            "vocal-like"
            if float(prediction.vocal_score) >= threshold
            else "supporting"
        )
        artifact_predictions.append(
            {
                "track_id": track_id,
                "vocal_score": float(prediction.vocal_score),
                "confidence": prediction.confidence,
                "predicted_role": prediction.predicted_role,
                "excerpt_scores": prediction.excerpt_scores,
            }
        )
        track_excerpt_count = sum(
            1 for item in excerpt_metadata if int(item["track_id"]) == track_id
        )
        notes.append(
            f"CLAP track role inference completed for track {track_id} "
            f"with {track_excerpt_count} track files."
        )

    get_workflow_artifact_store().upsert_artifact(
        WorkflowArtifactDocument(
            id=current_artifact_id,
            job_id=state["job_id"],
            artifact_type="clap_track_role_inference",
            payload={
                "threshold": threshold,
                "candidate_track_ids": candidate_track_ids,
                "excerpt_count": len(excerpt_metadata),
                "excerpts": excerpt_metadata,
                "predictions": artifact_predictions,
            },
        )
    )
    return workflow_update(
        state,
        node="infer_track_roles",
        phase="track_roles_inferred",
        progress=44,
        extra={
            "clap_artifact_id": current_artifact_id,
            "inferred_roles": inferred_roles,
            "track_role_scores": track_role_scores,
            "track_role_confidences": track_role_confidences,
            "vocal_detected": any(role == "vocal-like" for role in inferred_roles.values()),
            "mongo_artifact_ids": [*state.get("mongo_artifact_ids", []), current_artifact_id],
            "latest_artifact_id": current_artifact_id,
            "notes": notes,
        },
    )


def detect_sibilance(state: WorkflowState) -> WorkflowState:
    return _detect_issue_regions(
        state,
        node="detect_sibilance",
        phase="sibilance_detected",
        progress=48,
        issue="sibilance",
        detector=_find_sibilance_regions,
    )


def merge_analysis(state: WorkflowState) -> WorkflowState:
    regions = _finalize_analysis_regions(state.get("analysis_regions", []))
    detected_issues = list(dict.fromkeys(region["issue_type"] for region in regions))
    region_ids = [region["id"] for region in regions]
    return workflow_update(
        state,
        node="merge_analysis",
        phase="analysis_merged",
        progress=54,
        extra={
            "analysis_regions": regions,
            "detected_issues": detected_issues,
            "analysis_region_ids": region_ids,
        },
    )


def candidate_ranking(state: WorkflowState) -> WorkflowState:
    ranking_scores: dict[int, float] = {}
    ranked_candidates: list[dict[str, object]] = []
    for region in state.get("analysis_regions", []):
        score = ranking_score(region)
        ranking_scores[region["id"]] = score
        if (
            region.get("issue_type") == "band_overlap"
            and region.get("requires_user_action", True)
        ):
            ranked_candidates.append(region)
    ranked_candidate_ids = [
        int(region["id"]) for region in sorted(ranked_candidates, key=_candidate_ranking_sort_key)
    ]
    return workflow_update(
        state,
        node="candidate_ranking",
        phase="candidates_ranked",
        progress=60,
        extra={
            "ranking_scores": ranking_scores,
            "ranked_candidate_ids": ranked_candidate_ids,
        },
    )


def build_compact_dsp_summary(state: WorkflowState) -> dict[str, object]:
    summary, _ = _build_compact_dsp_summary(state)
    return summary


def ranking_score(region: dict[str, object]) -> float:
    issue_priority_weight = {
        "clipping": 0.42,
        "band_overlap": 0.42,
        "track_clipping": 0.0,
        "master_clipping": 0.0,
        "high_band_harshness": 0.14,
        "sibilance": 0.08,
    }
    severity_weight = {
        "CRITICAL": 1.25,
        "HIGH": 1.1,
        "MEDIUM": 0.92,
        "LOW": 0.8,
    }
    duration_ms = max(int(region["end_ms"]) - int(region["start_ms"]), 1)
    duration_weight = min(duration_ms / 1000, 1.0) * 0.18
    base = float(region.get("score", 0.0))
    weighted = base * severity_weight.get(region.get("severity", "MEDIUM"), 1.0)
    issue_weight = issue_priority_weight.get(str(region.get("issue_type", "")), 0.0)
    subtype_adjustment = 0.0
    if region.get("issue_type") == "band_overlap":
        subtype_adjustment = float(
            BAND_OVERLAP_SUBTYPE_CONFIG.get(
                str(region.get("band_overlap_subtype") or ""),
                {},
            ).get("ranking_adjustment", 0.0)
        )
    return round(weighted + duration_weight + issue_weight + subtype_adjustment, 3)


def _candidate_ranking_sort_key(region: dict[str, object]) -> tuple[float, float, int]:
    return (
        -_issue_priority(region.get("issue_type")),
        -ranking_score(region),
        -_severity_priority(region.get("severity")),
        int(region.get("start_ms", 0)),
    )


def _build_track_representative_specs(
    state: WorkflowState,
) -> list[dict[str, object]]:
    clip_index = state.get("clip_index", [])
    clips_by_track: dict[int, list[dict[str, object]]] = {}
    for clip in clip_index:
        track_id = int(clip["track_id"])
        clips_by_track.setdefault(track_id, []).append(clip)

    representative_specs: list[dict[str, object]] = []
    for track_id in sorted(clips_by_track):
        ranked_clips = sorted(
            clips_by_track[track_id],
            key=lambda clip: (
                int(clip.get("start_ms") or 0),
                int(clip.get("clip_id") or 0),
            ),
        )
        selected_clip: dict[str, object] | None = None
        for clip in ranked_clips:
            try:
                resolved_audio_path = resolve_clip_audio_path(clip)
            except AudioPathResolutionError:
                continue
            if resolved_audio_path is None:
                continue
            selected_clip = {**clip, "resolved_audio_path": resolved_audio_path}
            break
        if selected_clip is None:
            continue
        representative_specs.append(
            {
                "track_id": track_id,
                "clip_id": int(selected_clip["clip_id"]),
                "resolved_audio_path": str(selected_clip["resolved_audio_path"]),
                "source_format": Path(str(selected_clip["resolved_audio_path"])).suffix or ".wav",
            }
        )
    return representative_specs


def _detect_issue_regions(
    state: WorkflowState,
    *,
    node: str,
    phase: str,
    progress: int,
    issue: str,
    detector,
) -> WorkflowState:
    # state에서 analysis_regions, detected_issues 복사
    analysis_regions = deepcopy(state.get("analysis_regions", []))
    detected_issues = [*state.get("detected_issues", [])]

    # 파라미터로 입력받은 detector로 raw_regions 목록을 받음
    raw_regions = detector(state)
    # raw_regions -> analysis_regions로 변환
    analysis_regions, detected_issues, mongo_artifact_ids, latest_artifact_id = (
        _append_materialized_regions(
            state,
            analysis_regions=analysis_regions,
            detected_issues=detected_issues,
            issue=issue,
            raw_regions=raw_regions,
        )
    )
    return workflow_update(
        state,
        node=node,
        phase=phase,
        progress=progress,
        extra={
            "detected_issues": detected_issues,
            "analysis_regions": analysis_regions,
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
        },
    )


# 전체 타임라인 signal을 트랙별로 복원하고 full STFT를 계산한다.
def _build_compact_dsp_summary(state: WorkflowState) -> tuple[dict[str, object], dict[str, object]]:
    clip_index = state.get("clip_index", [])
    if not clip_index:
        raise DSPBuildError(
            "AUDIO_SOURCE_MISSING",
            "The project snapshot did not include any clips for DSP analysis.",
        )

    duration_ms = int(state.get("project_duration_ms") or 0)
    if duration_ms <= 0:
        raise DSPBuildError(
            "AUDIO_TIMELINE_RENDER_FAILED",
            "The project duration is required before running full STFT analysis.",
        )

    track_ids = state.get("track_ids") or sorted({int(clip["track_id"]) for clip in clip_index})
    track_sample_count = _ms_to_samples(duration_ms)
    resolved_clips = _resolve_all_clip_audio(clip_index)

    audio_cache = {
        path: _load_audio_clip(path)
        for path in sorted({str(clip["resolved_audio_path"]) for clip in resolved_clips})
    }
    track_eq_map = {
        int(track_id): list(bands)
        for track_id, bands in (state.get("track_eq_map") or {}).items()
    }
    track_signals: dict[int, np.ndarray] = {}
    mix_signal = np.zeros(track_sample_count, dtype=np.float32)
    for track_id in track_ids:
        # 각 트랙마다 "프로젝트 전체 길이" 기준의 연속 파형을 하나씩 복원한다.
        signal = _build_track_timeline_signal(
            resolved_clips=resolved_clips,
            audio_cache=audio_cache,
            track_id=int(track_id),
            total_samples=track_sample_count,
        )
        # 복원된 트랙 파형은 이후 트랙 단위 STFT 분석에 사용한다.
        signal = _apply_track_eq(signal, track_eq_map.get(int(track_id), []))
        track_signals[int(track_id)] = signal
        # 모든 트랙 파형을 더해 mix 파형도 함께 만든다.
        mix_signal += signal

    frequency_bins_hz = _stft_frequency_bins()
    track_frames: dict[int, list[dict[str, object]]] = {}
    track_power_spectra: dict[int, list[list[float]]] = {}
    for track_id, signal in track_signals.items():
        track_frames[track_id], track_power_spectra[track_id] = _compute_track_frame_summary(signal)
    mix_frames = _compute_mix_frames(mix_signal, target_track_id=int(track_ids[0]))
    mix_power_spectra = _compute_mix_power_spectra(mix_signal)
    track_stats = {
        track_id: _compute_track_stats(track_frames[track_id]) for track_id in track_ids
    }

    summary = {
        "analysis_source": "full_stft",
        "sample_rate": DSP_TARGET_SR,
        "n_fft": STFT_N_FFT,
        "win_length": STFT_WIN_LENGTH,
        "hop_length": STFT_HOP_LENGTH,
        "frame_ms": _samples_to_ms(STFT_WIN_LENGTH),
        "hop_ms": _samples_to_ms(STFT_HOP_LENGTH),
        "analysis_start_ms": 0,
        "duration_ms": duration_ms,
        "frame_count": len(mix_frames),
        "track_stats": track_stats,
        "track_windows_preview": {
            str(track_id): frames[:4] for track_id, frames in track_frames.items()
        },
        "mix_windows_preview": mix_frames[:4],
        "track_eqs_applied": {
            str(track_id): bands for track_id, bands in track_eq_map.items()
        },
    }
    artifact_payload = {
        "analysis_source": "full_stft",
        "sample_rate": DSP_TARGET_SR,
        "n_fft": STFT_N_FFT,
        "win_length": STFT_WIN_LENGTH,
        "hop_length": STFT_HOP_LENGTH,
        "duration_ms": duration_ms,
        "frame_count": len(mix_frames),
        "track_frames": {str(track_id): frames for track_id, frames in track_frames.items()},
        "mix_frames": mix_frames,
        "frequency_bins_hz": frequency_bins_hz,
        "track_power_spectra": {
            str(track_id): spectra for track_id, spectra in track_power_spectra.items()
        },
        "mix_power_spectra": mix_power_spectra,
        "track_eqs_applied": {
            str(track_id): bands for track_id, bands in track_eq_map.items()
        },
    }
    return summary, artifact_payload


def _resolve_all_clip_audio(clip_index: list[dict[str, object]]) -> list[dict[str, object]]:
    resolved_clips: list[dict[str, object]] = []
    missing_clip_ids: list[int] = []
    for clip in clip_index:
        try:
            audio_path = resolve_clip_audio_path(clip)
        except AudioPathResolutionError as exc:
            raise DSPBuildError(exc.code, exc.message) from exc
        if audio_path is None:
            missing_clip_ids.append(int(clip["clip_id"]))
            continue
        resolved_clips.append({**clip, "resolved_audio_path": audio_path})
    if missing_clip_ids:
        raise DSPBuildError(
            "AUDIO_SOURCE_MISSING",
            "Missing resolvable audio source for clips: "
            + ", ".join(str(clip_id) for clip_id in missing_clip_ids),
        )
    return resolved_clips


def _build_clap_track_payloads(
    state: WorkflowState,
) -> tuple[list[CLAPExcerptPayload], list[dict[str, object]]]:
    role_candidate_track_ids = [
        int(track_id) for track_id in state.get("role_candidate_track_ids", [])
    ]
    if not role_candidate_track_ids:
        return [], []

    representative_specs = {
        int(spec["track_id"]): spec for spec in state.get("track_representative_specs", [])
    }
    excerpt_payloads: list[CLAPExcerptPayload] = []
    excerpt_metadata: list[dict[str, object]] = []
    for track_id in role_candidate_track_ids:
        spec = representative_specs.get(track_id)
        if spec is None:
            raise DSPBuildError(
                "CLAP_SAMPLE_MISSING",
                f"Missing representative source audio for CLAP candidate track {track_id}.",
            )
        clip_id = int(spec["clip_id"])
        resolved_audio_path = str(spec["resolved_audio_path"])
        metadata = {
            "track_id": track_id,
            "clip_id": clip_id,
        }
        excerpt_payloads.append(
            CLAPExcerptPayload(
                filename=f"track-{track_id}{Path(resolved_audio_path).suffix or '.wav'}",
                audio_bytes=_read_audio_file_bytes(resolved_audio_path),
                metadata=metadata,
            )
        )
        excerpt_metadata.append(metadata)
    return excerpt_payloads, excerpt_metadata


def _load_audio_clip(path: str) -> tuple[np.ndarray, int]:
    try:
        waveform, sample_rate = sf.read(path, always_2d=False)
    except Exception as exc:  # noqa: BLE001
        raise DSPBuildError("AUDIO_DECODE_FAILED", f"Failed to decode audio file: {path}") from exc
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    waveform = waveform.astype(np.float32)
    if sample_rate != DSP_TARGET_SR:
        waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=DSP_TARGET_SR)
        sample_rate = DSP_TARGET_SR
    return waveform, sample_rate


def _read_audio_file_bytes(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise DSPBuildError(
            "AUDIO_SOURCE_READ_FAILED",
            f"Failed to read audio file bytes for CLAP inference: {path}",
        ) from exc


def _build_track_timeline_signal(
    *,
    resolved_clips: list[dict[str, object]],
    audio_cache: dict[str, tuple[np.ndarray, int]],
    track_id: int,
    total_samples: int,
) -> np.ndarray:
    # 이 함수의 반환값은 특정 트랙 하나를 프로젝트 타임라인 길이로 펼친 연속 파형이다.
    signal = np.zeros(total_samples, dtype=np.float32)
    # 모든 clip을 돌면서 현재 track_id에 속한 clip만 골라 타임라인 위에 다시 배치한다.
    for clip in resolved_clips:
        # 다른 트랙 clip이면 현재 트랙 파형에는 반영하지 않는다.
        if int(clip["track_id"]) != track_id:
            continue
        # 프로젝트 타임라인에서 clip이 시작하는 지점을 샘플 단위로 변환한다.
        clip_start_sample = _ms_to_samples(int(clip["start_ms"]))
        # 프로젝트 타임라인에서 clip이 끝나는 지점을 샘플 단위로 변환한다.
        # total_samples를 넘지 않도록 잘라 프로젝트 전체 길이 안에 맞춘다.
        clip_end_sample = min(_ms_to_samples(int(clip["end_ms"])), total_samples)
        # start/end가 뒤집히거나 길이가 0 이하인 clip은 무시한다.
        if clip_end_sample <= clip_start_sample:
            continue

        # 미리 로드해 둔 원본 오디오 파형과 샘플레이트를 가져온다.
        waveform, sample_rate = audio_cache[str(clip["resolved_audio_path"])]
        # 원본 오디오에서 실제로 읽기 시작할 위치를 샘플 단위로 변환한다.
        source_start_sample = _ms_to_samples(int(clip.get("audio_start_ms") or 0))
        # 원본 오디오에서 얼마만큼 사용할지 길이를 계산한다.
        # audio_duration_ms가 없으면 타임라인에 놓인 clip 길이를 기본값으로 사용한다.
        available_duration_ms = int(
            clip.get("audio_duration_ms") or max(int(clip["end_ms"]) - int(clip["start_ms"]), 1)
        )
        # 원본 오디오에서 읽을 끝 지점을 계산하되 실제 waveform 길이를 넘지 않게 자른다.
        source_end_sample = min(
            source_start_sample + _ms_to_samples(available_duration_ms),
            waveform.size,
        )
        # 타임라인에 놓을 수 있는 길이와 원본에서 실제로 읽을 수 있는 길이 중 더 짧은 쪽을 택한다.
        timeline_length = min(
            clip_end_sample - clip_start_sample,
            source_end_sample - source_start_sample,
        )
        # 실제로 붙일 수 있는 샘플이 없으면 건너뛴다.
        if timeline_length <= 0:
            continue
        # 원본 오디오의 일부 구간을 잘라 현재 트랙의 타임라인 위치에 더한다.
        # 같은 트랙 내에서 clip이 겹치면 이 덧셈으로 자연스럽게 합쳐진다.
        signal[clip_start_sample : clip_start_sample + timeline_length] += waveform[
            source_start_sample : source_start_sample + timeline_length
        ]
    # 이렇게 만들어진 signal은 "해당 트랙의 전체 타임라인 복원 파형"이다.
    return signal


def _apply_track_eq(signal: np.ndarray, bands: list[dict[str, object]]) -> np.ndarray:
    if signal.size == 0 or not bands:
        return signal

    filtered = signal.astype(np.float32, copy=True)
    for band in sorted(bands, key=lambda item: int(item["band_order"])):
        b, a = _design_eq_biquad(
            eq_type=str(band["eq_type"]),
            frequency_hz=float(band["frequency_hz"]),
            q=float(band["q"]),
            gain_delta_db=float(band["gain_delta_db"]),
        )
        filtered = lfilter(b, a, filtered).astype(np.float32, copy=False)
    return filtered


def _design_eq_biquad(
    *,
    eq_type: str,
    frequency_hz: float,
    q: float,
    gain_delta_db: float,
) -> tuple[np.ndarray, np.ndarray]:
    nyquist_hz = DSP_TARGET_SR / 2.0
    normalized_frequency_hz = min(max(frequency_hz, 1.0), nyquist_hz - 1.0)
    omega = (2.0 * math.pi * normalized_frequency_hz) / DSP_TARGET_SR
    sin_omega = math.sin(omega)
    cos_omega = math.cos(omega)
    alpha = sin_omega / (2.0 * max(q, 1e-6))
    amplitude = math.pow(10.0, gain_delta_db / 40.0)

    if eq_type == "BELL":
        b0 = 1.0 + alpha * amplitude
        b1 = -2.0 * cos_omega
        b2 = 1.0 - alpha * amplitude
        a0 = 1.0 + alpha / amplitude
        a1 = -2.0 * cos_omega
        a2 = 1.0 - alpha / amplitude
    elif eq_type == "LOW_SHELF":
        sqrt_a = math.sqrt(amplitude)
        two_sqrt_a_alpha = 2.0 * sqrt_a * alpha
        b0 = amplitude * ((amplitude + 1.0) - (amplitude - 1.0) * cos_omega + two_sqrt_a_alpha)
        b1 = 2.0 * amplitude * ((amplitude - 1.0) - (amplitude + 1.0) * cos_omega)
        b2 = amplitude * ((amplitude + 1.0) - (amplitude - 1.0) * cos_omega - two_sqrt_a_alpha)
        a0 = (amplitude + 1.0) + (amplitude - 1.0) * cos_omega + two_sqrt_a_alpha
        a1 = -2.0 * ((amplitude - 1.0) + (amplitude + 1.0) * cos_omega)
        a2 = (amplitude + 1.0) + (amplitude - 1.0) * cos_omega - two_sqrt_a_alpha
    elif eq_type == "HIGH_SHELF":
        sqrt_a = math.sqrt(amplitude)
        two_sqrt_a_alpha = 2.0 * sqrt_a * alpha
        b0 = amplitude * ((amplitude + 1.0) + (amplitude - 1.0) * cos_omega + two_sqrt_a_alpha)
        b1 = -2.0 * amplitude * ((amplitude - 1.0) + (amplitude + 1.0) * cos_omega)
        b2 = amplitude * ((amplitude + 1.0) + (amplitude - 1.0) * cos_omega - two_sqrt_a_alpha)
        a0 = (amplitude + 1.0) - (amplitude - 1.0) * cos_omega + two_sqrt_a_alpha
        a1 = 2.0 * ((amplitude - 1.0) - (amplitude + 1.0) * cos_omega)
        a2 = (amplitude + 1.0) - (amplitude - 1.0) * cos_omega - two_sqrt_a_alpha
    else:
        raise DSPBuildError("SNAPSHOT_TRACK_EQ_INVALID", f"Unsupported EQ type: {eq_type}")

    b = np.array([b0 / a0, b1 / a0, b2 / a0], dtype=np.float64)
    a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float64)
    return b, a


def _stft_frequency_bins() -> list[float]:
    return [float(value) for value in librosa.fft_frequencies(sr=DSP_TARGET_SR, n_fft=STFT_N_FFT)]


def _compute_track_frame_summary(signal: np.ndarray) -> tuple[list[dict[str, object]], list[list[float]]]:
    if signal.size < STFT_WIN_LENGTH:
        padded = np.zeros(STFT_WIN_LENGTH, dtype=np.float32)
        padded[: signal.size] = signal
        signal = padded

    stft = librosa.stft(
        signal,
        n_fft=STFT_N_FFT,
        hop_length=STFT_HOP_LENGTH,
        win_length=STFT_WIN_LENGTH,
        window=STFT_WINDOW,
        center=False,
    )
    power = np.abs(stft) ** 2
    freqs = librosa.fft_frequencies(sr=DSP_TARGET_SR, n_fft=STFT_N_FFT)
    frames: list[dict[str, object]] = []
    spectra: list[list[float]] = []
    for frame_index in range(power.shape[1]):
        start_sample = frame_index * STFT_HOP_LENGTH
        end_sample = min(start_sample + STFT_WIN_LENGTH, signal.size)
        time_slice = signal[start_sample:end_sample]
        frame_power = power[:, frame_index]
        total_energy = float(np.sum(frame_power) + 1e-9)
        frames.append(
            {
                "index": frame_index,
                "start_ms": _samples_to_ms(start_sample),
                "end_ms": _samples_to_ms(end_sample),
                "low_mid_energy": round(
                    _band_ratio(frame_power, freqs, *BAND_RANGES["low_mid"], total_energy),
                    3,
                ),
                "body_energy": round(
                    _band_ratio(frame_power, freqs, *BAND_RANGES["body"], total_energy),
                    3,
                ),
                "upper_mid_energy": round(
                    _band_ratio(frame_power, freqs, *BAND_RANGES["upper_mid"], total_energy),
                    3,
                ),
                "presence_energy": round(
                    _band_ratio(frame_power, freqs, *BAND_RANGES["presence"], total_energy),
                    3,
                ),
                "high_band_ratio": round(
                    _band_ratio(frame_power, freqs, *BAND_RANGES["harshness"], total_energy),
                    3,
                ),
                "sibilance_ratio": round(
                    _band_ratio(frame_power, freqs, *BAND_RANGES["sibilance"], total_energy),
                    3,
                ),
                "peak_dbfs": round(
                    _to_dbfs(float(np.max(np.abs(time_slice))) if time_slice.size else 0.0),
                    3,
                ),
                "spectral_centroid_hz": round(_spectral_centroid(frame_power, freqs), 1),
                "window_energy": round(
                    float(np.sqrt(np.mean(time_slice**2))) if time_slice.size else 0.0,
                    3,
                ),
            }
        )
        spectra.append([round(float(value), 8) for value in frame_power.tolist()])
    return frames, spectra


def _compute_track_frames(signal: np.ndarray) -> list[dict[str, object]]:
    frames, _ = _compute_track_frame_summary(signal)
    return frames


def _compute_mix_frames(signal: np.ndarray, *, target_track_id: int) -> list[dict[str, object]]:
    if signal.size < STFT_WIN_LENGTH:
        padded = np.zeros(STFT_WIN_LENGTH, dtype=np.float32)
        padded[: signal.size] = signal
        signal = padded

    frame_count = 1 + max((signal.size - STFT_WIN_LENGTH) // STFT_HOP_LENGTH, 0)
    frames: list[dict[str, object]] = []
    for frame_index in range(frame_count):
        start_sample = frame_index * STFT_HOP_LENGTH
        end_sample = min(start_sample + STFT_WIN_LENGTH, signal.size)
        time_slice = signal[start_sample:end_sample]
        peak = float(np.max(np.abs(time_slice))) if time_slice.size else 0.0
        true_peak = _oversampled_true_peak(time_slice)
        rms = float(np.sqrt(np.mean(time_slice**2))) if time_slice.size else 0.0
        frames.append(
            {
                "index": frame_index,
                "start_ms": _samples_to_ms(start_sample),
                "end_ms": _samples_to_ms(end_sample),
                "peak_dbfs": round(_to_dbfs(peak), 3),
                "true_peak_dbfs": round(_to_dbfs(true_peak), 3),
                "clip_ratio": round(
                    float(np.mean(np.abs(time_slice) >= 0.999)) if time_slice.size else 0.0,
                    4,
                ),
                "crest_factor": round(max(_to_dbfs(peak) - _to_dbfs(rms), 0.0), 3),
                "target_track_id": target_track_id,
            }
        )
    return frames


def _compute_mix_power_spectra(signal: np.ndarray) -> list[list[float]]:
    if signal.size < STFT_WIN_LENGTH:
        padded = np.zeros(STFT_WIN_LENGTH, dtype=np.float32)
        padded[: signal.size] = signal
        signal = padded
    stft = librosa.stft(
        signal,
        n_fft=STFT_N_FFT,
        hop_length=STFT_HOP_LENGTH,
        win_length=STFT_WIN_LENGTH,
        window=STFT_WINDOW,
        center=False,
    )
    power = np.abs(stft) ** 2
    return [[round(float(value), 8) for value in power[:, frame_index].tolist()] for frame_index in range(power.shape[1])]


def _oversampled_true_peak(time_slice: np.ndarray) -> float:
    if time_slice.size == 0:
        return 0.0
    if time_slice.size == 1:
        return float(np.max(np.abs(time_slice)))
    # 실제 true peak에 더 가깝게 보기 위해 frame 파형을 4배 업샘플링한 뒤 최대 진폭을 잰다.
    oversampled = resample_poly(time_slice, up=TRUE_PEAK_OVERSAMPLE_FACTOR, down=1)
    return float(np.max(np.abs(oversampled)))


def _compute_track_stats(track_frames: list[dict[str, object]]) -> dict[str, float]:
    if not track_frames:
        return {
            "vocal_like_score": 0.0,
            "dominant_low_mid": 0.0,
            "dominant_presence": 0.0,
        }
    active_frames = [frame for frame in track_frames if frame["window_energy"] >= 0.01]
    frames_for_stats = active_frames or track_frames
    low_mid = float(np.mean([frame["low_mid_energy"] for frame in frames_for_stats]))
    presence = float(np.mean([frame["presence_energy"] for frame in frames_for_stats]))
    sibilance = float(np.mean([frame["sibilance_ratio"] for frame in frames_for_stats]))
    high_band = float(np.mean([frame["high_band_ratio"] for frame in frames_for_stats]))
    centroid = float(np.mean([frame["spectral_centroid_hz"] for frame in frames_for_stats]))
    vocal_like_score = min(
        1.0,
        max(
            0.0,
            (presence * 0.8)
            + (sibilance * 1.8)
            + (high_band * 1.1)
            + (min(centroid / 5000.0, 1.0) * 0.4),
        ),
    )
    return {
        "vocal_like_score": round(vocal_like_score, 3),
        "dominant_low_mid": round(low_mid, 3),
        "dominant_presence": round(presence, 3),
    }


def _band_ratio(
    frame_power: np.ndarray,
    freqs: np.ndarray,
    low_hz: int,
    high_hz: int,
    total_energy: float,
) -> float:
    mask = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(mask):
        return 0.0
    return float(np.sum(frame_power[mask]) / total_energy)


def _spectral_centroid(frame_power: np.ndarray, freqs: np.ndarray) -> float:
    magnitude_sum = float(np.sum(frame_power))
    if magnitude_sum <= 1e-9:
        return 0.0
    return float(np.sum(freqs * frame_power) / magnitude_sum)


def _to_dbfs(amplitude: float) -> float:
    return 20.0 * math.log10(max(amplitude, 1e-6))


def _samples_to_ms(sample_index: int) -> int:
    return int(round((sample_index / DSP_TARGET_SR) * 1000))


def _ms_to_samples(duration_ms: int) -> int:
    return max(int(round((duration_ms / 1000) * DSP_TARGET_SR)), 1)


def _load_dsp_feature_artifact(state: WorkflowState) -> dict[str, Any]:
    raw_track_frames = state.get("track_frames") or {}
    raw_mix_frames = state.get("mix_frames") or []
    raw_track_power_spectra = state.get("track_power_spectra") or {}
    raw_mix_power_spectra = state.get("mix_power_spectra") or []
    raw_frequency_bins_hz = state.get("frequency_bins_hz") or []
    if (
        raw_track_frames
        or raw_mix_frames
        or raw_track_power_spectra
        or raw_mix_power_spectra
        or raw_frequency_bins_hz
    ):
        return {
            "track_frames": raw_track_frames,
            "mix_frames": raw_mix_frames,
            "track_power_spectra": raw_track_power_spectra,
            "mix_power_spectra": raw_mix_power_spectra,
            "frequency_bins_hz": raw_frequency_bins_hz,
        }
    artifact_id_value = state.get("clip_feature_artifact_id")
    if not artifact_id_value:
        return {}
    artifact = get_workflow_artifact_store().get_artifact(artifact_id_value)
    return artifact.payload if artifact is not None else {}


def _artifact_frequency_bins(artifact: dict[str, Any]) -> np.ndarray:
    bins = artifact.get("frequency_bins_hz") or []
    if not bins:
        return np.array([], dtype=np.float64)
    return np.asarray(bins, dtype=np.float64)


def _artifact_track_power_spectra(artifact: dict[str, Any], track_id: int) -> list[list[float]]:
    track_spectra = artifact.get("track_power_spectra", {})
    if str(track_id) in track_spectra:
        return list(track_spectra[str(track_id)])
    if track_id in track_spectra:
        return list(track_spectra[track_id])
    return []


def _collect_frame_indices_for_region(
    frames: list[dict[str, object]],
    *,
    start_ms: int,
    end_ms: int,
) -> list[int]:
    return [
        index
        for index, frame in enumerate(frames)
        if int(frame.get("start_ms", 0)) < end_ms and int(frame.get("end_ms", 0)) > start_ms
    ]


def _average_power_spectrum(
    spectra: list[list[float]],
    frame_indices: list[int],
) -> np.ndarray | None:
    if not spectra or not frame_indices:
        return None
    selected = [
        np.asarray(spectra[index], dtype=np.float64)
        for index in frame_indices
        if 0 <= index < len(spectra)
    ]
    if not selected:
        return None
    stacked = np.vstack(selected)
    return np.mean(stacked, axis=0)


def _smooth_score_map(score_map: np.ndarray, kernel_size: int = REFINEMENT_SMOOTHING_BINS) -> np.ndarray:
    if score_map.size == 0 or kernel_size <= 1:
        return score_map
    kernel_size = min(kernel_size, int(score_map.size))
    kernel = np.ones(kernel_size, dtype=np.float64) / float(kernel_size)
    return np.convolve(score_map, kernel, mode="same")


def _extract_peak_cluster(
    freqs: np.ndarray,
    score_map: np.ndarray,
    *,
    min_hz: int | None = None,
    max_hz: int | None = None,
    peak_ratio: float = REFINEMENT_CLUSTER_PEAK_RATIO,
) -> dict[str, object] | None:
    if freqs.size == 0 or score_map.size == 0 or freqs.size != score_map.size:
        return None
    mask = np.ones(freqs.shape, dtype=bool)
    if min_hz is not None:
        mask &= freqs >= min_hz
    if max_hz is not None:
        mask &= freqs <= max_hz
    masked_indices = np.flatnonzero(mask)
    if masked_indices.size == 0:
        return None
    masked_scores = np.maximum(score_map[masked_indices], 0.0)
    peak_score = float(np.max(masked_scores))
    if peak_score <= REFINEMENT_CLUSTER_FLOOR:
        return None
    threshold = max(peak_score * peak_ratio, REFINEMENT_CLUSTER_FLOOR)
    peak_local_index = int(np.argmax(masked_scores))
    peak_index = int(masked_indices[peak_local_index])
    left = peak_index
    right = peak_index
    while left - 1 >= 0 and mask[left - 1] and score_map[left - 1] >= threshold:
        left -= 1
    while right + 1 < score_map.size and mask[right + 1] and score_map[right + 1] >= threshold:
        right += 1
    cluster_scores = np.maximum(score_map[left : right + 1], 0.0)
    cluster_energy = float(np.sum(cluster_scores))
    if cluster_energy <= REFINEMENT_CLUSTER_FLOOR:
        return None
    full_energy = float(np.sum(np.maximum(score_map[masked_indices], 0.0)))
    weighted_center = float(
        np.sum(freqs[left : right + 1] * cluster_scores) / max(cluster_energy, 1e-9)
    )
    return {
        "band_low_hz": int(round(float(freqs[left]))),
        "band_high_hz": int(round(float(freqs[right]))),
        "center_hz": int(round(weighted_center)),
        "band_confidence": round(cluster_energy / max(full_energy, 1e-9), 3),
        "peak_score": peak_score,
        "cluster_energy": cluster_energy,
    }


def _apply_refined_band(
    region: dict[str, object],
    refinement: dict[str, object] | None,
    *,
    fallback_low_hz: int | None = None,
    fallback_high_hz: int | None = None,
) -> dict[str, object]:
    updated = deepcopy(region)
    if refinement is None:
        updated["center_hz"] = None
        updated["band_confidence"] = None
        if "broadband_classification" not in updated:
            updated["broadband_classification"] = "fallback"
        if fallback_low_hz is not None:
            updated["band_low_hz"] = fallback_low_hz
        if fallback_high_hz is not None:
            updated["band_high_hz"] = fallback_high_hz
        return updated
    updated["band_low_hz"] = refinement["band_low_hz"]
    updated["band_high_hz"] = refinement["band_high_hz"]
    updated["center_hz"] = refinement["center_hz"]
    updated["band_confidence"] = refinement["band_confidence"]
    return updated


def _refine_band_overlap_region(
    artifact: dict[str, Any],
    region: dict[str, object],
) -> dict[str, object]:
    subtype = str(region.get("band_overlap_subtype") or "body_overlap")
    config = BAND_OVERLAP_SUBTYPE_CONFIG.get(
        subtype,
        BAND_OVERLAP_SUBTYPE_CONFIG["body_overlap"],
    )
    fallback_low_hz, fallback_high_hz = config["fallback_band"]
    refine_low_hz, refine_high_hz = config["refine_band"]
    involved_track_ids = [int(track_id) for track_id in region.get("involved_track_ids", [])]
    freqs = _artifact_frequency_bins(artifact)
    if len(involved_track_ids) < 2 or freqs.size == 0:
        return _apply_refined_band(
            region,
            None,
            fallback_low_hz=int(region.get("band_low_hz") or fallback_low_hz),
            fallback_high_hz=int(region.get("band_high_hz") or fallback_high_hz),
        )
    normalized_spectra: list[np.ndarray] = []
    for track_id in involved_track_ids:
        frames = artifact.get("track_frames", {}).get(str(track_id)) or artifact.get("track_frames", {}).get(track_id) or []
        frame_indices = _collect_frame_indices_for_region(
            frames,
            start_ms=int(region["start_ms"]),
            end_ms=int(region["end_ms"]),
        )
        spectrum = _average_power_spectrum(_artifact_track_power_spectra(artifact, track_id), frame_indices)
        if spectrum is None:
            continue
        normalized_spectra.append(spectrum / max(float(np.sum(spectrum)), 1e-9))
    if len(normalized_spectra) < 2:
        return _apply_refined_band(
            region,
            None,
            fallback_low_hz=int(region.get("band_low_hz") or fallback_low_hz),
            fallback_high_hz=int(region.get("band_high_hz") or fallback_high_hz),
        )
    overlap_score = np.zeros_like(normalized_spectra[0], dtype=np.float64)
    for left_index in range(len(normalized_spectra)):
        for right_index in range(left_index + 1, len(normalized_spectra)):
            overlap_score += np.minimum(
                normalized_spectra[left_index],
                normalized_spectra[right_index],
            )
    refinement = _extract_peak_cluster(
        freqs,
        _smooth_score_map(overlap_score),
        min_hz=refine_low_hz,
        max_hz=refine_high_hz,
    )
    return _apply_refined_band(
        region,
        refinement,
        fallback_low_hz=int(region.get("band_low_hz") or fallback_low_hz),
        fallback_high_hz=int(region.get("band_high_hz") or fallback_high_hz),
    )


def _refine_prominent_high_band_region(
    artifact: dict[str, Any],
    region: dict[str, object],
    *,
    min_hz: int,
    max_hz: int,
) -> dict[str, object]:
    track_id = region.get("track_id")
    freqs = _artifact_frequency_bins(artifact)
    if track_id is None or freqs.size == 0:
        return _apply_refined_band(
            region,
            None,
            fallback_low_hz=int(region.get("band_low_hz") or min_hz),
            fallback_high_hz=int(region.get("band_high_hz") or max_hz),
        )
    frames = artifact.get("track_frames", {}).get(str(track_id)) or artifact.get("track_frames", {}).get(track_id) or []
    frame_indices = _collect_frame_indices_for_region(
        frames,
        start_ms=int(region["start_ms"]),
        end_ms=int(region["end_ms"]),
    )
    spectrum = _average_power_spectrum(_artifact_track_power_spectra(artifact, int(track_id)), frame_indices)
    if spectrum is None:
        return _apply_refined_band(
            region,
            None,
            fallback_low_hz=int(region.get("band_low_hz") or min_hz),
            fallback_high_hz=int(region.get("band_high_hz") or max_hz),
        )
    log_power = np.log10(np.maximum(spectrum, 1e-9))
    envelope = _smooth_score_map(log_power, kernel_size=13)
    prominence = np.maximum(log_power - envelope, 0.0)
    refinement = _extract_peak_cluster(
        freqs,
        _smooth_score_map(prominence),
        min_hz=min_hz,
        max_hz=max_hz,
    )
    return _apply_refined_band(
        region,
        refinement,
        fallback_low_hz=int(region.get("band_low_hz") or min_hz),
        fallback_high_hz=int(region.get("band_high_hz") or max_hz),
    )


def _classify_track_clipping_band(
    artifact: dict[str, Any],
    region: dict[str, object],
) -> dict[str, object]:
    track_id = region.get("track_id")
    freqs = _artifact_frequency_bins(artifact)
    if track_id is None or freqs.size == 0:
        updated = deepcopy(region)
        updated["broadband_classification"] = "fallback"
        updated["center_hz"] = None
        updated["band_confidence"] = None
        return updated
    frames = artifact.get("track_frames", {}).get(str(track_id)) or artifact.get("track_frames", {}).get(track_id) or []
    frame_indices = _collect_frame_indices_for_region(
        frames,
        start_ms=int(region["start_ms"]),
        end_ms=int(region["end_ms"]),
    )
    spectrum = _average_power_spectrum(_artifact_track_power_spectra(artifact, int(track_id)), frame_indices)
    if spectrum is None:
        updated = deepcopy(region)
        updated["broadband_classification"] = "fallback"
        updated["center_hz"] = None
        updated["band_confidence"] = None
        return updated
    analysis_mask = (freqs >= CLIPPING_ANALYSIS_MIN_HZ) & (freqs <= CLIPPING_ANALYSIS_MAX_HZ)
    normalized = spectrum / max(float(np.sum(spectrum[analysis_mask])), 1e-9)
    smoothed = _smooth_score_map(normalized)
    refinement = _extract_peak_cluster(
        freqs,
        smoothed,
        min_hz=CLIPPING_ANALYSIS_MIN_HZ,
        max_hz=CLIPPING_ANALYSIS_MAX_HZ,
        peak_ratio=0.72,
    )
    updated = deepcopy(region)
    if refinement is None:
        updated["band_low_hz"] = None
        updated["band_high_hz"] = None
        updated["center_hz"] = None
        updated["band_confidence"] = None
        updated["band_hints"] = ["broadband"]
        updated["broadband_classification"] = "broadband"
        return updated
    cluster_mask = (freqs >= refinement["band_low_hz"]) & (freqs <= refinement["band_high_hz"])
    cluster_share = float(np.sum(normalized[cluster_mask]))
    per_frame_scores: list[float] = []
    for index in frame_indices:
        spectra = _artifact_track_power_spectra(artifact, int(track_id))
        if not (0 <= index < len(spectra)):
            continue
        frame_spectrum = np.asarray(spectra[index], dtype=np.float64)
        frame_total = float(np.sum(frame_spectrum[analysis_mask]))
        if frame_total <= 1e-9:
            continue
        per_frame_scores.append(float(np.sum(frame_spectrum[cluster_mask]) / frame_total))
    time_consistency = float(np.mean([score >= max(cluster_share * 0.7, 0.12) for score in per_frame_scores])) if per_frame_scores else 0.0
    mean_score = float(np.mean(smoothed[analysis_mask])) if np.any(analysis_mask) else 0.0
    peak_to_mean_ratio = float(refinement["peak_score"]) / max(mean_score, 1e-9)
    if (
        cluster_share < CLIPPING_BAND_DRIVEN_MIN_SHARE
        or time_consistency < CLIPPING_BAND_DRIVEN_MIN_CONSISTENCY
        or peak_to_mean_ratio < 1.6
    ):
        updated["band_low_hz"] = None
        updated["band_high_hz"] = None
        updated["center_hz"] = None
        updated["band_confidence"] = None
        updated["band_hints"] = ["broadband"]
        updated["broadband_classification"] = "broadband"
        return updated
    updated["band_low_hz"] = refinement["band_low_hz"]
    updated["band_high_hz"] = refinement["band_high_hz"]
    updated["center_hz"] = refinement["center_hz"]
    updated["band_confidence"] = round(min(refinement["band_confidence"], cluster_share), 3)
    updated["broadband_classification"] = "band_driven"
    updated["band_hints"] = _derive_track_clipping_band_hints(
        updated["band_low_hz"],
        updated["band_high_hz"],
    )
    return updated


def _derive_track_clipping_band_hints(band_low_hz: int | None, band_high_hz: int | None) -> list[str]:
    if band_low_hz is None or band_high_hz is None:
        return ["broadband"]
    hints: list[str] = []
    if band_low_hz < 1500:
        hints.append("low_mid")
    if band_high_hz >= 4500:
        hints.append("high")
    if not hints:
        hints.append("broadband")
    return hints


def _find_band_overlap_regions(state: WorkflowState) -> list[dict[str, object]]:
    if "band_overlap" not in state.get("issue_types", []):
        return []
    artifact = _load_dsp_feature_artifact(state)
    track_frames_by_id = {
        int(track_id): frames for track_id, frames in artifact.get("track_frames", {}).items()
    }
    track_ids = sorted(track_frames_by_id)
    if len(track_ids) < 2:
        return []

    frame_count = min(len(track_frames_by_id[track_id]) for track_id in track_ids)
    candidates: list[dict[str, object]] = []
    for frame_index in range(frame_count):
        frame_windows = {
            track_id: track_frames_by_id[track_id][frame_index]
            for track_id in track_ids
        }
        for subtype, config in BAND_OVERLAP_SUBTYPE_CONFIG.items():
            candidate = _build_band_overlap_subtype_candidate(
                subtype=subtype,
                config=config,
                frame_windows=frame_windows,
            )
            if candidate is not None:
                candidates.append(candidate)
    merged = _merge_candidate_windows("band_overlap", candidates)
    return [_refine_band_overlap_region(artifact, candidate) for candidate in merged]


def _build_band_overlap_subtype_candidate(
    *,
    subtype: str,
    config: dict[str, object],
    frame_windows: dict[int, dict[str, object]],
) -> dict[str, object] | None:
    focus_energy_key = str(config["focus_energy_key"])
    support_energy_key = str(config["support_energy_key"])
    active_tracks: list[tuple[int, dict[str, object]]] = []
    for track_id, window in frame_windows.items():
        if float(window.get("window_energy", 0.0)) < BAND_OVERLAP_FRAME_MIN_WINDOW_ENERGY:
            continue
        if float(window.get(focus_energy_key, 0.0)) < float(config["min_track_energy"]):
            continue
        if float(window.get(support_energy_key, 0.0)) < float(config["min_support_energy"]):
            continue
        min_centroid_hz = config.get("min_centroid_hz")
        if min_centroid_hz is not None and float(window.get("spectral_centroid_hz", 0.0)) < float(min_centroid_hz):
            continue
        active_tracks.append((track_id, window))
    if len(active_tracks) < int(config["min_active_tracks"]):
        return None

    focus_sum = sum(float(window.get(focus_energy_key, 0.0)) for _, window in active_tracks)
    support_sum = sum(float(window.get(support_energy_key, 0.0)) for _, window in active_tracks)
    if focus_sum < float(config["min_focus_sum"]) or support_sum < float(config["min_support_sum"]):
        return None

    sorted_tracks = sorted(
        active_tracks,
        key=lambda item: (
            float(item[1].get(focus_energy_key, 0.0)),
            float(item[1].get(support_energy_key, 0.0)),
        ),
        reverse=True,
    )
    primary_track_id = sorted_tracks[0][0]
    involved_track_ids = [track_id for track_id, _ in sorted_tracks]
    track_body_contributions = {
        str(track_id): round(float(window.get(focus_energy_key, 0.0)), 3)
        for track_id, window in sorted_tracks
    }
    reference_window = sorted_tracks[0][1]
    band_low_hz, band_high_hz = config["fallback_band"]
    score = round(
        (focus_sum * 0.46)
        + (support_sum * 0.2)
        + (min(len(involved_track_ids) / 4.0, 1.0) * 0.34),
        3,
    )
    return {
        "track_id": primary_track_id,
        "secondary_track_id": None,
        "involved_track_ids": involved_track_ids,
        "track_body_contributions": track_body_contributions,
        "band_overlap_subtype": subtype,
        "band_focus_label": _band_focus_label_for_subtype(subtype),
        "start_ms": reference_window["start_ms"],
        "end_ms": reference_window["end_ms"],
        "band_low_hz": band_low_hz,
        "band_high_hz": band_high_hz,
        "score": score,
        "summary": str(config["summary"]),
        "recommended_reduction_db": _default_band_overlap_reduction_db(subtype, score),
    }


def _find_track_clipping_regions(state: WorkflowState) -> list[dict[str, object]]:
    if "track_clipping" not in state.get("issue_types", []):
        return []
    artifact = _load_dsp_feature_artifact(state)
    track_frames_by_id = {
        int(track_id): frames for track_id, frames in artifact.get("track_frames", {}).items()
    }
    candidates = []
    for track_id, windows in track_frames_by_id.items():
        for window in windows:
            true_peak_dbfs = float(window.get("true_peak_dbfs", window["peak_dbfs"]))
            if true_peak_dbfs < -0.1:
                continue
            peak_near_ceiling = max(true_peak_dbfs + 0.1, 0.0)
            score = round(
                (peak_near_ceiling * 1.15)
                + (float(window.get("high_band_ratio", 0.0)) * 0.25)
                + (float(window.get("window_energy", 0.0)) * 0.2),
                3,
            )
            candidates.append(
                {
                    "track_id": track_id,
                    "start_ms": window["start_ms"],
                    "end_ms": window["end_ms"],
                    "score": score,
                    "summary": "이 구간에서 트랙 레벨이 높아 클리핑이 생길 가능성이 있습니다.",
                    "recommended_reduction_db": round(max(peak_near_ceiling + 0.9, 1.0), 3),
                    "current_true_peak_dbtp": round(true_peak_dbfs, 3),
                    "target_ceiling_dbtp": -1.0,
                }
            )
    merged = _merge_candidate_windows("track_clipping", candidates)
    return [_classify_track_clipping_band(artifact, candidate) for candidate in merged]


def _find_master_clipping_regions(state: WorkflowState) -> list[dict[str, object]]:
    return _find_master_clipping_candidate_regions(state)


def _find_high_band_harshness_regions(state: WorkflowState) -> list[dict[str, object]]:
    if "high_band_harshness" not in state.get("issue_types", []):
        return []
    artifact = _load_dsp_feature_artifact(state)
    track_frames_by_id = {
        int(track_id): frames for track_id, frames in artifact.get("track_frames", {}).items()
    }
    candidates = []
    for track_id, windows in track_frames_by_id.items():
        for window in windows:
            if (
                window["high_band_ratio"] >= 0.34
                and window["presence_energy"] >= 0.06
                and window["spectral_centroid_hz"] >= 3200
            ):
                score = round(
                    (window["high_band_ratio"] * 0.48)
                    + (window["presence_energy"] * 0.22)
                    + (min(window["spectral_centroid_hz"] / 8000.0, 1.0) * 0.3),
                    3,
                )
                candidates.append(
                    {
                        "track_id": track_id,
                        "start_ms": window["start_ms"],
                        "end_ms": window["end_ms"],
                        "band_low_hz": BAND_RANGES["harshness"][0],
                        "band_high_hz": BAND_RANGES["harshness"][1],
                        "score": score,
                    "summary": "이 구간의 고역이 거칠게 튀어 들릴 수 있어 한 번 더 확인이 필요합니다.",
                    }
                )
    merged = _merge_candidate_windows("high_band_harshness", candidates)
    return [
        _refine_prominent_high_band_region(
            artifact,
            candidate,
            min_hz=BAND_RANGES["harshness"][0],
            max_hz=BAND_RANGES["harshness"][1],
        )
        for candidate in merged
    ]


def _find_sibilance_regions(state: WorkflowState) -> list[dict[str, object]]:
    if "sibilance" not in state.get("issue_types", []):
        return []
    inferred_roles = state.get("inferred_roles", {})
    # 치찰음은 보컬 계열 트랙에서만 의미가 있으므로
    # CLAP이 보컬 track을 확정하지 못하면 탐지를 진행하지 않는다.
    if not state.get("vocal_detected") or not inferred_roles:
        return []
    artifact = _load_dsp_feature_artifact(state)
    track_frames_by_id = {
        int(track_id): frames for track_id, frames in artifact.get("track_frames", {}).items()
    }
    vocal_tracks = [
        track_id
        for track_id, role in inferred_roles.items()
        if role == "vocal-like"
    ]
    if not vocal_tracks:
        return []
    candidates = []
    for track_id in vocal_tracks:
        for window in track_frames_by_id.get(track_id, []):
            # sibilance_ratio는 치찰 대역 집중도를, high_band_ratio는 전반적 고역 치우침을,
            # spectral_centroid는 소리가 실제로 밝은 쪽에 몰려 있는지를 본다.
            # 셋을 함께 써서 단순 고역 harshness와 보컬 치찰음을 구분한다.
            if (
                window["sibilance_ratio"] >= 0.18
                and window["high_band_ratio"] >= 0.18
                and window["spectral_centroid_hz"] >= 1400
            ):
                score = round(
                    (window["sibilance_ratio"] * 0.45)
                    + (window["high_band_ratio"] * 0.25)
                    + (min(window["spectral_centroid_hz"] / 8000.0, 1.0) * 0.3),
                    3,
                )
                candidates.append(
                    {
                        "track_id": track_id,
                        "start_ms": window["start_ms"],
                        "end_ms": window["end_ms"],
                        "band_low_hz": BAND_RANGES["sibilance"][0],
                        "band_high_hz": BAND_RANGES["sibilance"][1],
                        "score": score,
                        "summary": "보컬 계열 트랙에서 치찰음이 도드라질 수 있는 구간이 감지되었습니다.",
                    }
                )
    merged = _merge_candidate_windows("sibilance", candidates)
    return [
        _refine_prominent_high_band_region(
            artifact,
            candidate,
            min_hz=BAND_RANGES["sibilance"][0],
            max_hz=BAND_RANGES["sibilance"][1],
        )
        for candidate in merged
    ]


def _merge_candidate_windows(
    issue: str,
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not candidates:
        return []
    candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate["track_id"],
            candidate.get("secondary_track_id"),
            tuple(candidate.get("involved_track_ids", [])),
            candidate.get("band_overlap_subtype"),
            candidate.get("band_low_hz"),
            candidate["start_ms"],
        ),
    )
    merged = [deepcopy(candidates[0])]
    merged[0]["window_count"] = 1
    merged[0]["_score_total"] = merged[0]["score"]
    for candidate in candidates[1:]:
        previous = merged[-1]
        same_group = (
            previous["track_id"] == candidate["track_id"]
            and previous.get("secondary_track_id") == candidate.get("secondary_track_id")
            and previous.get("involved_track_ids") == candidate.get("involved_track_ids")
            and previous.get("band_overlap_subtype") == candidate.get("band_overlap_subtype")
            and previous.get("band_low_hz") == candidate.get("band_low_hz")
            and previous.get("band_high_hz") == candidate.get("band_high_hz")
        )
        if same_group and candidate["start_ms"] - previous["end_ms"] <= MERGE_GAP_MS:
            previous["end_ms"] = candidate["end_ms"]
            previous["window_count"] += 1
            previous["_score_total"] += candidate["score"]
            if "track_body_contributions" in previous and "track_body_contributions" in candidate:
                for track_id, value in candidate["track_body_contributions"].items():
                    previous["track_body_contributions"][track_id] = round(
                        previous["track_body_contributions"].get(track_id, 0.0) + value,
                        3,
                    )
        else:
            item = deepcopy(candidate)
            item["window_count"] = 1
            item["_score_total"] = item["score"]
            merged.append(item)
    min_duration_ms = ISSUE_MIN_DURATION_MS[issue]
    finalized = []
    for candidate in merged:
        duration_ms = candidate["end_ms"] - candidate["start_ms"]
        if duration_ms < min_duration_ms:
            continue
        candidate["score"] = round(candidate["_score_total"] / candidate["window_count"], 3)
        candidate.pop("_score_total", None)
        if "track_body_contributions" in candidate:
            candidate["track_body_contributions"] = {
                track_id: round(value / candidate["window_count"], 3)
                for track_id, value in candidate["track_body_contributions"].items()
            }
        finalized.append(candidate)
    return finalized


def _detect_residual_master_clipping(state: WorkflowState) -> WorkflowState:
    analysis_regions = deepcopy(state.get("analysis_regions", []))
    detected_issues = [*state.get("detected_issues", [])]
    artifact = _load_dsp_feature_artifact(state)
    contributors_by_candidate = {
        str(item["candidate_id"]): item for item in state.get("master_clipping_contributors", [])
    }
    promoted_regions: list[dict[str, object]] = []
    residual_regions: list[dict[str, object]] = []

    for candidate in state.get("master_clipping_candidates", []):
        contributor = contributors_by_candidate.get(str(candidate.get("candidate_id")))
        promoted_tracks = _promote_master_contributors(candidate, contributor)
        if promoted_tracks:
            promoted_regions.extend(
                _classify_track_clipping_band(artifact, promoted_track)
                for promoted_track in promoted_tracks
            )
            if _should_keep_residual_master_region(candidate, contributor, promoted_tracks):
                residual_regions.append(
                    _build_residual_master_region(candidate, contributor, promoted_tracks)
                )
            continue
        residual_regions.append(_build_residual_master_region(candidate, contributor, []))

    analysis_regions, detected_issues, mongo_artifact_ids, latest_artifact_id = (
        _append_materialized_regions(
            state,
            analysis_regions=analysis_regions,
            detected_issues=detected_issues,
            issue="track_clipping",
            raw_regions=promoted_regions,
        )
    )
    analysis_regions, detected_issues, mongo_artifact_ids, latest_artifact_id = (
        _append_materialized_regions(
            state,
            analysis_regions=analysis_regions,
            detected_issues=detected_issues,
            issue="master_clipping",
            raw_regions=residual_regions,
            mongo_artifact_ids=mongo_artifact_ids,
            latest_artifact_id=latest_artifact_id,
        )
    )
    return workflow_update(
        state,
        node="detect_residual_master_clipping",
        phase="master_clipping_detected",
        progress=32,
        extra={
            "detected_issues": detected_issues,
            "analysis_regions": analysis_regions,
            "promoted_track_clipping_regions": promoted_regions,
            "mongo_artifact_ids": mongo_artifact_ids,
            "latest_artifact_id": latest_artifact_id,
        },
    )


def _append_materialized_regions(
    state: WorkflowState,
    *,
    analysis_regions: list[dict[str, object]],
    detected_issues: list[str],
    issue: str,
    raw_regions: list[dict[str, object]],
    mongo_artifact_ids: list[str] | None = None,
    latest_artifact_id: str | None = None,
) -> tuple[list[dict[str, object]], list[str], list[str], str | None]:
    materialized_regions = _materialize_regions(state, issue=issue, raw_regions=raw_regions)
    if materialized_regions and issue not in detected_issues:
        detected_issues.append(issue)
    analysis_regions.extend(materialized_regions)
    mongo_ids = [*(mongo_artifact_ids or state.get("mongo_artifact_ids", []))]
    latest_id = latest_artifact_id or state.get("latest_artifact_id")
    for region in materialized_regions:
        current_artifact_id = str(region["evidence_doc_id"])
        mongo_ids.append(current_artifact_id)
        latest_id = current_artifact_id
    return analysis_regions, detected_issues, mongo_ids, latest_id


def _find_master_clipping_candidate_regions(state: WorkflowState) -> list[dict[str, object]]:
    if "master_clipping" not in state.get("issue_types", []):
        return []
    artifact = _load_dsp_feature_artifact(state)
    mix_frames = artifact.get("mix_frames", [])
    candidates = []
    for window in mix_frames:
        true_peak_dbfs = float(window["true_peak_dbfs"])
        if true_peak_dbfs <= 0.0:
            continue
        peak_near_ceiling = max(float(window["peak_dbfs"]) + 0.1, 0.0)
        score = round(
            (true_peak_dbfs * 0.75)
            + (peak_near_ceiling * 0.25)
            + (float(window["clip_ratio"]) * 12),
            3,
        )
        candidates.append(
            {
                "track_id": None,
                "start_ms": window["start_ms"],
                "end_ms": window["end_ms"],
                "score": score,
                "summary": "마스터 출력이 순간적으로 높아져 클리핑으로 이어질 수 있는 구간이 있습니다.",
                "true_peak_dbfs": true_peak_dbfs,
                "mix_peak_dbfs": float(window["peak_dbfs"]),
                "clip_ratio": float(window["clip_ratio"]),
            }
        )
    return _merge_candidate_windows("master_clipping", candidates)


def _analyze_master_clipping_candidate_contributors(
    state: WorkflowState,
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    artifact = _load_dsp_feature_artifact(state)
    track_frames_by_id = {
        int(track_id): frames for track_id, frames in artifact.get("track_frames", {}).items()
    }
    contributor_results: list[dict[str, object]] = []
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        contributor_items: list[dict[str, object]] = []
        total_overlap_energy = 0.0
        energy_by_track: dict[int, float] = {}
        for track_id, frames in track_frames_by_id.items():
            overlapping = [
                frame
                for frame in frames
                if int(frame["start_ms"]) < int(candidate["end_ms"])
                and int(frame["end_ms"]) > int(candidate["start_ms"])
            ]
            if not overlapping:
                continue
            overlap_energy = float(
                sum(float(frame.get("window_energy", 0.0)) for frame in overlapping)
            )
            if overlap_energy <= 0.0:
                continue
            energy_by_track[track_id] = overlap_energy
            total_overlap_energy += overlap_energy

        for track_id, overlap_energy in energy_by_track.items():
            overlapping = [
                frame
                for frame in track_frames_by_id[track_id]
                if int(frame["start_ms"]) < int(candidate["end_ms"])
                and int(frame["end_ms"]) > int(candidate["start_ms"])
            ]
            energy_share = overlap_energy / max(total_overlap_energy, 1e-6)
            avg_peak_dbfs = float(
                np.mean([float(frame.get("peak_dbfs", -120.0)) for frame in overlapping])
            )
            peak_near_ceiling = min(max((avg_peak_dbfs + 0.3) / 0.6, 0.0), 1.0)
            avg_low_mid = float(
                np.mean([float(frame.get("low_mid_energy", 0.0)) for frame in overlapping])
            )
            avg_body = float(
                np.mean([float(frame.get("body_energy", 0.0)) for frame in overlapping])
            )
            avg_high = float(
                np.mean([float(frame.get("high_band_ratio", 0.0)) for frame in overlapping])
            )
            band_focus = min(max(avg_low_mid, avg_body, avg_high), 1.0)
            contributor_score = round(
                (energy_share * 0.55) + (peak_near_ceiling * 0.3) + (band_focus * 0.15),
                3,
            )
            band_hints = _infer_contributor_band_hints(
                low_mid_energy=avg_low_mid,
                body_energy=avg_body,
                high_band_ratio=avg_high,
            )
            contributor_items.append(
                {
                    "track_id": track_id,
                    "energy_share": round(energy_share, 3),
                    "avg_peak_dbfs": round(avg_peak_dbfs, 3),
                    "peak_near_ceiling": round(peak_near_ceiling, 3),
                    "avg_low_mid_energy": round(avg_low_mid, 3),
                    "avg_body_energy": round(avg_body, 3),
                    "avg_high_band_ratio": round(avg_high, 3),
                    "contributor_score": contributor_score,
                    "band_hints": band_hints,
                }
            )

        contributor_items.sort(
            key=lambda item: (
                -float(item["contributor_score"]),
                -float(item["energy_share"]),
                int(item["track_id"]),
            )
        )
        candidate["contributing_track_ids"] = [item["track_id"] for item in contributor_items]
        candidate["track_contribution_scores"] = {
            item["track_id"]: item["contributor_score"] for item in contributor_items
        }
        candidate["contributor_band_hints"] = {
            item["track_id"]: item["band_hints"] for item in contributor_items
        }
        contributor_results.append(
            {
                "candidate_id": candidate_id,
                "start_ms": candidate["start_ms"],
                "end_ms": candidate["end_ms"],
                "contributing_track_ids": candidate["contributing_track_ids"],
                "track_contribution_scores": candidate["track_contribution_scores"],
                "contributor_band_hints": candidate["contributor_band_hints"],
                "contributors": contributor_items,
            }
        )
    return contributor_results


def _infer_contributor_band_hints(
    *,
    low_mid_energy: float,
    body_energy: float,
    high_band_ratio: float,
) -> list[str]:
    hints: list[str] = []
    if low_mid_energy >= 0.12 or body_energy >= 0.28:
        hints.append("low_mid")
    if high_band_ratio >= 0.28:
        hints.append("high")
    if not hints:
        hints.append("broadband")
    return hints


def _promote_master_contributors(
    candidate: dict[str, object],
    contributor: dict[str, object] | None,
) -> list[dict[str, object]]:
    if contributor is None:
        return []
    contributors = list(contributor.get("contributors", []))
    if not contributors:
        return []
    top_score = float(contributors[0]["contributor_score"])
    if (
        len(contributors) >= MASTER_CLIPPING_DISTRIBUTED_COUNT
        and top_score < MASTER_CLIPPING_DISTRIBUTED_TOP_SCORE
    ):
        return []
    promoted = []
    for item in contributors:
        score = float(item["contributor_score"])
        if score < MASTER_CLIPPING_CONTRIBUTOR_SCORE_THRESHOLD:
            continue
        if top_score - score > MASTER_CLIPPING_PROMOTION_MARGIN:
            continue
        promoted.append(
            {
                "track_id": int(item["track_id"]),
                "start_ms": candidate["start_ms"],
                "end_ms": candidate["end_ms"],
                "score": max(float(candidate["score"]), score),
                "summary": "마스터 클리핑에 크게 기여하는 트랙으로 보여 우선 보정 후보로 올렸습니다.",
                "recommended_reduction_db": round(max(float(candidate.get("true_peak_dbfs", 0.0)) + 1.0, 1.0), 3),
                "current_true_peak_dbtp": round(float(candidate.get("true_peak_dbfs", 0.0)), 3),
                "target_ceiling_dbtp": -1.0,
                "source_master_candidate_id": candidate["candidate_id"],
                "auto_fix_source": "promoted_master_contributor",
                "contributing_track_ids": contributor.get("contributing_track_ids", []),
                "track_contribution_scores": contributor.get("track_contribution_scores", {}),
                "contributor_band_hints": contributor.get("contributor_band_hints", {}),
                "promoted_track_id": int(item["track_id"]),
                "band_hints": list(item.get("band_hints", [])),
            }
        )
    return promoted


def _should_keep_residual_master_region(
    candidate: dict[str, object],
    contributor: dict[str, object] | None,
    promoted_tracks: list[dict[str, object]],
) -> bool:
    if contributor is None:
        return True
    contributors = list(contributor.get("contributors", []))
    if not contributors:
        return True
    top_score = float(contributors[0]["contributor_score"])
    if (
        len(contributors) >= MASTER_CLIPPING_DISTRIBUTED_COUNT
        and top_score < MASTER_CLIPPING_DISTRIBUTED_TOP_SCORE
    ):
        return True
    if len(promoted_tracks) < len(contributors) and float(candidate.get("window_count", 1)) >= 4:
        return True
    return False


def _build_residual_master_region(
    candidate: dict[str, object],
    contributor: dict[str, object] | None,
    promoted_tracks: list[dict[str, object]],
) -> dict[str, object]:
    summary = "기여 트랙을 추려도 마스터 클리핑 위험이 남아 있습니다."
    if promoted_tracks:
        summary = "기여 트랙을 보정하더라도 마스터 보호가 더 필요해 보이는 구간입니다."
    region = {
        "track_id": None,
        "start_ms": candidate["start_ms"],
        "end_ms": candidate["end_ms"],
        "score": candidate["score"],
        "summary": summary,
        "recommended_reduction_db": round(max(float(candidate.get("true_peak_dbfs", 0.0)) + 1.0, 1.0), 3),
        "current_true_peak_dbtp": round(float(candidate.get("true_peak_dbfs", 0.0)), 3),
        "target_ceiling_dbtp": -1.0,
        "source_master_candidate_id": candidate["candidate_id"],
        "auto_fix_source": "residual_master_clipping",
        "promoted_track_ids": [int(item["track_id"]) for item in promoted_tracks],
        "contributing_track_ids": [],
        "track_contribution_scores": {},
        "contributor_band_hints": {},
    }
    if contributor is not None:
        region["contributing_track_ids"] = contributor.get("contributing_track_ids", [])
        region["track_contribution_scores"] = contributor.get("track_contribution_scores", {})
        region["contributor_band_hints"] = contributor.get("contributor_band_hints", {})
    return region


def _materialize_regions(
    state: WorkflowState,
    *,
    issue: str,
    raw_regions: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not raw_regions:
        return []
    existing_count = sum(
        1 for region in state.get("analysis_regions", []) if region.get("issue_type") == issue
    )
    materialized = []
    for offset, region in enumerate(raw_regions, start=1):
        evidence_doc_id = artifact_id(state, f"{issue}-evidence-{existing_count + offset}")
        severity = _severity_from_score(issue=issue, score=region["score"])
        requires_user_action = issue == "band_overlap"
        region_record = get_workflow_analysis_region_store().create_region(
            AnalysisRegionCreate(
                job_id=state["job_id"],
                issue_type=issue,
                start_ms=int(region["start_ms"]),
                end_ms=int(region["end_ms"]),
                severity=severity,
                analysis_summary=str(region["summary"]),
                evidence_doc_id=evidence_doc_id,
                requires_user_action=requires_user_action,
            )
        )
        materialized_region = {
                "id": region_record.id,
                "issue_type": issue,
                "summary": region["summary"],
                "start_ms": region["start_ms"],
                "end_ms": region["end_ms"],
                "severity": severity,
                # clipping과 다른 user-facing 이슈는 사용자가 구간을 보고 선택한다.
                # sibilance만 자동 보정 경로로 넘긴다.
                "requires_user_action": requires_user_action,
                "evidence_doc_id": evidence_doc_id,
                "track_id": region.get("track_id"),
                "secondary_track_id": region.get("secondary_track_id"),
                "involved_track_ids": region.get("involved_track_ids", []),
                "track_body_contributions": region.get("track_body_contributions", {}),
                "band_overlap_subtype": region.get("band_overlap_subtype"),
                "band_focus_label": region.get("band_focus_label"),
                "band_low_hz": region.get("band_low_hz"),
                "band_high_hz": region.get("band_high_hz"),
                "center_hz": region.get("center_hz"),
                "band_confidence": region.get("band_confidence"),
                "score": region["score"],
                "window_count": region.get("window_count", 1),
                "recommended_reduction_db": region.get("recommended_reduction_db"),
                "current_true_peak_dbtp": region.get("current_true_peak_dbtp"),
                "target_ceiling_dbtp": region.get("target_ceiling_dbtp"),
                "source_master_candidate_id": region.get("source_master_candidate_id"),
                "auto_fix_source": region.get("auto_fix_source", "direct_detection"),
                "contributing_track_ids": region.get("contributing_track_ids", []),
                "track_contribution_scores": region.get("track_contribution_scores", {}),
                "contributor_band_hints": region.get("contributor_band_hints", {}),
                "band_hints": region.get("band_hints", []),
                "broadband_classification": region.get("broadband_classification"),
                **_project_region_timeline(
                    state,
                    start_ms=int(region["start_ms"]),
                    end_ms=int(region["end_ms"]),
                    involved_track_ids=region.get("involved_track_ids"),
                ),
            }
        get_workflow_artifact_store().upsert_artifact(
            WorkflowArtifactDocument(
                id=evidence_doc_id,
                job_id=state["job_id"],
                artifact_type="analysis_region_evidence",
                payload={
                    "regionId": materialized_region["id"],
                    "issueType": issue,
                    "summary": region["summary"],
                    "startMs": region["start_ms"],
                    "endMs": region["end_ms"],
                    "score": region["score"],
                    "windowCount": region.get("window_count", 1),
                    "recommendedReductionDb": region.get("recommended_reduction_db"),
                    "currentTruePeakDbtp": region.get("current_true_peak_dbtp"),
                    "targetCeilingDbtp": region.get("target_ceiling_dbtp"),
                    "sourceMasterCandidateId": region.get("source_master_candidate_id"),
                    "autoFixSource": region.get("auto_fix_source", "direct_detection"),
                    "contributingTrackIds": region.get("contributing_track_ids", []),
                    "trackContributionScores": region.get("track_contribution_scores", {}),
                    "contributorBandHints": region.get("contributor_band_hints", {}),
                    "bandOverlapSubtype": region.get("band_overlap_subtype"),
                    "bandFocusLabel": region.get("band_focus_label"),
                    "bandLowHz": region.get("band_low_hz"),
                    "bandHighHz": region.get("band_high_hz"),
                    "centerHz": region.get("center_hz"),
                    "bandConfidence": region.get("band_confidence"),
                    "refinementIssueType": issue,
                    "broadbandClassification": region.get("broadband_classification"),
                    "rawRegion": deepcopy(region),
                },
            )
        )
        materialized.append(materialized_region)
    return materialized


def _finalize_analysis_regions(regions: list[dict[str, object]]) -> list[dict[str, object]]:
    if not regions:
        return []
    deduped: dict[tuple, dict[str, object]] = {}
    for region in regions:
        key = _analysis_region_dedup_key(region)
        current = deduped.get(key)
        if current is None or region.get("score", 0.0) > current.get("score", 0.0):
            deduped[key] = region
    return sorted(
        deduped.values(),
        key=lambda region: (
            int(region["start_ms"]),
            str(region["issue_type"]),
            -float(region.get("score", 0.0)),
        ),
    )


def _analysis_region_dedup_key(region: dict[str, object]) -> tuple[object, ...]:
    return (
        region["issue_type"],
        region.get("track_id"),
        region.get("secondary_track_id"),
        tuple(region.get("involved_track_ids", [])),
        region.get("band_overlap_subtype"),
        region.get("band_low_hz"),
        region.get("band_high_hz"),
        region.get("center_hz"),
        region["start_ms"],
        region["end_ms"],
    )


def _severity_from_score(*, issue: str, score: float) -> str:
    if issue in {"clipping", "master_clipping"}:
        if score >= 0.16:
            return "CRITICAL"
        if score >= 0.08:
            return "HIGH"
        return "MEDIUM"
    if issue == "track_clipping":
        if score >= 0.14:
            return "HIGH"
        if score >= 0.07:
            return "MEDIUM"
        return "LOW"
    if score >= 0.72:
        return "HIGH"
    if score >= 0.48:
        return "MEDIUM"
    return "LOW"


def _severity_priority(severity: object) -> int:
    ranking = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }
    return ranking.get(str(severity), 0)


def _issue_priority(issue_type: object) -> int:
    ranking = {
        "clipping": 4,
        "band_overlap": 4,
        "track_clipping": 0,
        "master_clipping": 0,
        "high_band_harshness": 2,
        "sibilance": 1,
    }
    return ranking.get(str(issue_type), 0)


def _project_region_timeline(
    state: WorkflowState,
    *,
    start_ms: int,
    end_ms: int,
    involved_track_ids: list[int] | None = None,
) -> dict[str, object]:
    involved_track_ids_set = {int(track_id) for track_id in involved_track_ids or []}
    overlapped_measures = [
        bar
        for bar in state.get("bar_mapping", [])
        if int(bar["start_ms"]) < end_ms and int(bar["end_ms"]) > start_ms
    ]
    affected_clip_ids = [
        int(clip["clip_id"])
        for clip in state.get("clip_index", [])
        if int(clip["start_ms"]) < end_ms and int(clip["end_ms"]) > start_ms
        and (
            not involved_track_ids_set
            or int(clip["track_id"]) in involved_track_ids_set
        )
    ]
    if not overlapped_measures:
        return {
            "measure_start": None,
            "measure_end": None,
            "affected_clip_ids": affected_clip_ids,
        }
    return {
        "measure_start": int(overlapped_measures[0]["measure_no"]),
        "measure_end": int(overlapped_measures[-1]["measure_no"]),
        "affected_clip_ids": affected_clip_ids,
    }


def _band_focus_label_for_subtype(subtype: str) -> str:
    if subtype == "upper_mid_overlap":
        return "중고역"
        return "?ì¤‘ê³ ì—­"
    return {
        "low_mid_overlap": "저중역",
        "body_overlap": "바디",
        "presence_overlap": "프레즌스",
    }.get(subtype, "바디")


def _default_band_overlap_reduction_db(subtype: str, score: float) -> float:
    if subtype == "low_mid_overlap":
        if score >= 1.0:
            return 6.4
        if score >= 0.78:
            return 4.2
        return 3.2
    if subtype == "upper_mid_overlap":
        if score >= 0.95:
            return 6.0
        if score >= 0.68:
            return 3.0
        return 2.2
    if subtype == "presence_overlap":
        if score >= 0.74:
            return 2.5
        return 1.8
    if score >= 1.0:
        return 3.5
    return 2.8
