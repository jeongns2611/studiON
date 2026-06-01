from app.graph.nodes.review import (
    plan_critic,
    _region_supports_static_local_cut,
    _supplement_critic_decision,
)
from app.services.plan_critic_llm import PlanCriticLLMResponse


def test_supplemental_critic_requests_eq_cut_for_short_local_static_pocket() -> None:
    result, note = _supplement_critic_decision(
        state={
            "user_feedback_message": "Keep the synth stab lively. The texture should take the first local cut.",
            "preserve_clip_id": 50002,
        },
        region={
            "start_ms": 2580,
            "end_ms": 3120,
            "band_low_hz": 300,
            "band_high_hz": 900,
            "band_overlap_subtype": "body_overlap",
        },
        plan_payload={
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetTrackId": 52,
                    "targetClipId": None,
                    "bandLowHz": 360,
                    "bandHighHz": 820,
                    "gainDeltaDb": -1.5,
                }
            }
        },
    )

    assert result == "REVISE"
    assert "switch the actionType to EQ_CUT" in note


def test_supplemental_critic_does_not_force_eq_cut_for_sustained_phrase_case() -> None:
    result, note = _supplement_critic_decision(
        state={
            "user_feedback_message": "Touch only the masking phrase itself. Keep the chop shape natural.",
            "preserve_clip_id": 50003,
        },
        region={
            "start_ms": 4460,
            "end_ms": 5660,
            "band_low_hz": 912,
            "band_high_hz": 1028,
            "band_overlap_subtype": "low_mid_overlap",
        },
        plan_payload={
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetTrackId": 51,
                    "targetClipId": None,
                    "bandLowHz": 912,
                    "bandHighHz": 1028,
                    "gainDeltaDb": -1.8,
                }
            }
        },
    )

    assert result in {None, "REVISE"}
    assert "switch the actionType to EQ_CUT" not in note


def test_region_supports_static_local_cut_uses_duration_and_band_limits() -> None:
    assert _region_supports_static_local_cut(
        {
            "start_ms": 2580,
            "end_ms": 3120,
            "band_low_hz": 300,
            "band_high_hz": 900,
        }
    )
    assert not _region_supports_static_local_cut(
        {
            "start_ms": 4460,
            "end_ms": 5660,
            "band_low_hz": 912,
            "band_high_hz": 1028,
        }
    )


def test_plan_critic_discards_pass_praise_when_supplemental_revise_overrides(
    monkeypatch,
) -> None:
    class _FakeCriticClient:
        def review_plan(self, **kwargs) -> PlanCriticLLMResponse:
            return PlanCriticLLMResponse(
                result="PASS",
                note=(
                    "Plan is safe, targeted, and aligned with user intent. "
                    "DYNAMIC_EQ on track 52 correctly addresses the masking pocket."
                ),
            )

    captured_artifact = {}

    class _FakeArtifactStore:
        def upsert_artifact(self, artifact) -> None:
            captured_artifact["artifact"] = artifact

    monkeypatch.setattr(
        "app.graph.nodes.review.get_plan_critic_llm_client",
        lambda: _FakeCriticClient(),
    )
    monkeypatch.setattr(
        "app.graph.nodes.review.get_workflow_artifact_store",
        lambda: _FakeArtifactStore(),
    )

    result = plan_critic(
        {
            "job_id": 990001,
            "selected_region_id": 1603,
            "preserve_clip_id": 50002,
            "user_feedback_message": "Create more room in the pocket, but keep the section balanced.",
            "plan_revision_notes": [],
            "analysis_regions": [
                {
                    "id": 1603,
                    "issue_type": "band_overlap",
                    "track_id": 50,
                    "secondary_track_id": 52,
                    "start_ms": 2580,
                    "end_ms": 3120,
                    "band_low_hz": 300,
                    "band_high_hz": 900,
                    "band_overlap_subtype": "body_overlap",
                    "involved_track_ids": [50, 51, 52],
                    "track_body_contributions": {"51": 0.36, "52": 0.61},
                }
            ],
            "clip_index": [
                {"clip_id": 50002, "track_id": 50},
                {"clip_id": 51001, "track_id": 51},
                {"clip_id": 52001, "track_id": 52},
            ],
            "track_name_map": {50: "Lead Vocal Chops", 51: "Synth Stab", 52: "Texture Layer"},
            "plan_payload": {
                "candidate": {
                    "action": {
                        "actionType": "DYNAMIC_EQ",
                        "targetTrackId": 52,
                        "targetClipId": None,
                        "bandLowHz": 300,
                        "bandHighHz": 900,
                        "gainDeltaDb": -2.0,
                    }
                }
            },
            "transition_log": [],
            "mongo_artifact_ids": [],
        }
    )

    assert result["critic_result"] == "REVISE"
    assert result["plan_revision_notes"] == [
        "Keep the current target track fixed. This is a short static pocket, so switch the actionType to EQ_CUT and keep the cut tightly inside the exact masking pocket."
    ]
    assert captured_artifact["artifact"].payload["note"] == result["plan_revision_notes"][-1]


def test_supplemental_critic_revises_presence_overlap_over_4db() -> None:
    result, note = _supplement_critic_decision(
        state={
            "user_feedback_message": "Keep the lead intact and just tuck the bright layer.",
            "preserve_clip_id": 50004,
        },
        region={
            "start_ms": 1800,
            "end_ms": 2600,
            "band_low_hz": 2800,
            "band_high_hz": 4300,
            "band_overlap_subtype": "presence_overlap",
        },
        plan_payload={
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetTrackId": 61,
                    "targetClipId": None,
                    "bandLowHz": 2900,
                    "bandHighHz": 4200,
                    "gainDeltaDb": -4.6,
                }
            }
        },
    )

    assert result == "REVISE"
    assert "4dB" in note


def test_supplemental_critic_revises_upper_mid_overlap_over_6db() -> None:
    result, note = _supplement_critic_decision(
        state={
            "user_feedback_message": "Keep the lead clear and just tame the upper-mid layer.",
            "preserve_clip_id": 50005,
        },
        region={
            "start_ms": 1600,
            "end_ms": 2500,
            "band_low_hz": 1280,
            "band_high_hz": 1820,
            "band_overlap_subtype": "upper_mid_overlap",
        },
        plan_payload={
            "candidate": {
                "action": {
                    "actionType": "DYNAMIC_EQ",
                    "targetTrackId": 71,
                    "targetClipId": None,
                    "bandLowHz": 1320,
                    "bandHighHz": 1780,
                    "gainDeltaDb": -6.4,
                }
            }
        },
    )

    assert result == "REVISE"
    assert "6dB" in note


def test_plan_critic_normalizes_presence_deadlock_reject_to_revise(
    monkeypatch,
) -> None:
    class _FakeCriticClient:
        def review_plan(self, **kwargs) -> PlanCriticLLMResponse:
            return PlanCriticLLMResponse(
                result="REJECT",
                note=(
                    "Policy deadlock: presence_overlap with 2.5 kHz-wide band cannot safely deliver "
                    "the requested aggressiveness. Narrow band selection first."
                ),
            )

    captured_artifact = {}

    class _FakeArtifactStore:
        def upsert_artifact(self, artifact) -> None:
            captured_artifact["artifact"] = artifact

    monkeypatch.setattr(
        "app.graph.nodes.review.get_plan_critic_llm_client",
        lambda: _FakeCriticClient(),
    )
    monkeypatch.setattr(
        "app.graph.nodes.review.get_workflow_artifact_store",
        lambda: _FakeArtifactStore(),
    )

    result = plan_critic(
        {
            "job_id": 990002,
            "selected_region_id": 1701,
            "preserve_clip_id": 50006,
            "user_feedback_message": "Make it more aggressive but keep the lead intact.",
            "plan_revision_notes": [],
            "revise_count": 1,
            "max_revise_count": 5,
            "analysis_regions": [
                {
                    "id": 1701,
                    "issue_type": "band_overlap",
                    "track_id": 60,
                    "secondary_track_id": 61,
                    "start_ms": 1800,
                    "end_ms": 3200,
                    "band_low_hz": 2500,
                    "band_high_hz": 5000,
                    "band_overlap_subtype": "presence_overlap",
                    "involved_track_ids": [60, 61],
                    "track_body_contributions": {"60": 0.18, "61": 0.34},
                }
            ],
            "clip_index": [
                {"clip_id": 50006, "track_id": 60},
                {"clip_id": 61001, "track_id": 61},
            ],
            "track_name_map": {60: "Lead", 61: "Bright Layer"},
            "plan_payload": {
                "candidate": {
                    "action": {
                        "actionType": "DYNAMIC_EQ",
                        "targetTrackId": 61,
                        "targetClipId": None,
                        "bandLowHz": 2500,
                        "bandHighHz": 5000,
                        "gainDeltaDb": -2.5,
                    }
                }
            },
            "transition_log": [],
            "mongo_artifact_ids": [],
        }
    )

    assert result["critic_result"] == "REVISE"
    assert "3 to 4.5 kHz" in result["plan_revision_notes"][-1]
    assert captured_artifact["artifact"].payload["result"] == "REVISE"
