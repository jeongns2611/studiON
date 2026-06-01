from __future__ import annotations

import pytest

from scripts.planner_critic_eval_support import evaluate_dataset, summarize_results


@pytest.mark.parametrize(
    "dataset_id, expected_plan_cases, seed_bad_plan_cases, non_plan_cases",
    [
        ("p1_dual_vocal_bed", 6, 1, 0),
        ("p2_three_track_instrumental", 5, 1, 0),
        ("p3_dense_edit", 5, 1, 0),
        ("p5_band_overlap_eq_cut", 5, 1, 0),
        ("p7_critic_guardrail_stress", 6, 6, 0),
        ("p8_recovery_dense_edit", 6, 6, 0),
        ("p9_dialogue_intent_priority", 6, 6, 0),
        ("p10_vocal_preserve_precision", 6, 6, 0),
        ("p11_static_dynamic_boundary", 6, 6, 0),
        ("p12_instrumental_priority", 6, 6, 0),
        ("p13_recovery_revision_matrix", 10, 10, 0),
        ("p14_dialogue_guardrail_matrix", 10, 10, 0),
        ("p15_vocal_preserve_matrix", 10, 10, 0),
        ("p16_boundary_priority_matrix", 10, 10, 0),
        ("p17_instrumental_guardrail_matrix", 10, 10, 0),
        ("p18_dialogue_bandwidth_intent", 6, 0, 0),
        ("p19_vocal_bandwidth_intent", 6, 0, 0),
    ],
)
def test_eval_harness_expected_plans_pass_without_db(
    dataset_id: str,
    expected_plan_cases: int,
    seed_bad_plan_cases: int,
    non_plan_cases: int,
) -> None:
    results, summary = evaluate_dataset(dataset_id)
    expected_results = [result for result in results if result.mode == "expected_plan"]
    bad_plan_results = [result for result in results if result.mode == "seed_bad_plan"]
    non_plan_results = [
        result for result in results if result.mode in {"warning_only", "no_plan_expected"}
    ]

    assert expected_results
    assert len(expected_results) == expected_plan_cases
    assert len(bad_plan_results) == seed_bad_plan_cases
    assert len(non_plan_results) == non_plan_cases
    assert summary.expected_plan_cases == expected_plan_cases
    assert summary.seed_bad_plan_cases == seed_bad_plan_cases
    assert all(result.validator_result == result.validator_expected for result in expected_results)
    assert all(result.critic_result == result.critic_expected for result in expected_results)
    assert all(result.passed for result in non_plan_results)


@pytest.mark.parametrize(
    "dataset_id",
    [
        "p1_dual_vocal_bed",
        "p2_three_track_instrumental",
        "p3_dense_edit",
        "p5_band_overlap_eq_cut",
        "p8_recovery_dense_edit",
        "p9_dialogue_intent_priority",
        "p10_vocal_preserve_precision",
        "p11_static_dynamic_boundary",
        "p12_instrumental_priority",
        "p13_recovery_revision_matrix",
        "p14_dialogue_guardrail_matrix",
        "p15_vocal_preserve_matrix",
        "p16_boundary_priority_matrix",
        "p17_instrumental_guardrail_matrix",
    ],
)
def test_eval_harness_seed_bad_plan_matches_fixture_review_without_db(dataset_id: str) -> None:
    results, _summary = evaluate_dataset(dataset_id)
    bad_plan_results = [result for result in results if result.mode == "seed_bad_plan"]

    assert bad_plan_results
    assert all(result.validator_result == result.validator_expected for result in bad_plan_results)
    assert all(result.critic_result == result.critic_expected for result in bad_plan_results)


def test_eval_harness_summarizes_fixture_scores_without_db() -> None:
    results, summary = evaluate_dataset("p1_dual_vocal_bed")
    recomputed = summarize_results(dataset_id="p1_dual_vocal_bed", results=results)

    assert summary == recomputed
    assert summary.expected_plan_cases == 6
    assert summary.expected_plan_validator_passes == 6
    assert summary.expected_plan_critic_passes == 6
    assert summary.expected_plan_full_passes == 6
    assert summary.expected_plan_planner_matches == 6
    assert summary.expected_plan_action_type_matches == 6
    assert summary.expected_plan_target_track_matches == 6
    assert summary.expected_plan_time_range_matches == 6
    assert summary.expected_plan_band_range_matches == 6
    assert summary.expected_plan_dynamic_eq_cases == 6
    assert summary.expected_plan_dynamic_eq_matches == 6
    assert summary.expected_plan_eq_cut_cases == 0
    assert summary.expected_plan_eq_cut_matches == 0
    assert summary.seed_bad_plan_cases == 1
    assert summary.seed_bad_plan_validator_rejects == 1
    assert summary.seed_bad_plan_critic_rejects == 1
    assert summary.seed_bad_plan_full_rejects == 1


def test_eval_harness_eq_only_policy_dataset_tracks_warning_only_modes() -> None:
    results, summary = evaluate_dataset("p4_eq_only_mixed")

    warning_only = [result for result in results if result.mode == "warning_only"]
    no_plan = [result for result in results if result.mode == "no_plan_expected"]
    seeded_bad = [result for result in results if result.mode == "seed_bad_plan"]

    assert summary.expected_plan_cases == 3
    assert summary.expected_plan_planner_matches == 3
    assert summary.expected_plan_action_type_matches == 3
    assert summary.expected_plan_target_track_matches == 3
    assert summary.expected_plan_time_range_matches == 3
    assert summary.expected_plan_band_range_matches == 3
    assert summary.seed_bad_plan_cases == 1
    assert summary.expected_plan_validator_passes == 0
    assert summary.expected_plan_critic_passes == 0
    assert summary.seed_bad_plan_validator_rejects == 1
    assert summary.seed_bad_plan_critic_rejects == 1
    assert summary.seed_bad_plan_full_rejects == 1
    assert len(warning_only) == 1
    assert warning_only[0].passed is True
    assert len(no_plan) == 1
    assert no_plan[0].passed is True
    assert len(seeded_bad) == 1
    assert seeded_bad[0].validator_result == "REJECT"
    assert seeded_bad[0].critic_result == "REJECT"


def test_eval_harness_band_overlap_eq_cut_dataset_tracks_action_metrics() -> None:
    _results, summary = evaluate_dataset("p5_band_overlap_eq_cut")

    assert summary.expected_plan_cases == 5
    assert summary.expected_plan_validator_passes == 5
    assert summary.expected_plan_critic_passes == 5
    assert summary.expected_plan_full_passes == 5
    assert summary.expected_plan_planner_matches == 5
    assert summary.expected_plan_action_type_matches == 5
    assert summary.expected_plan_target_track_matches == 5
    assert summary.expected_plan_time_range_matches == 5
    assert summary.expected_plan_band_range_matches == 5
    assert summary.expected_plan_dynamic_eq_cases == 1
    assert summary.expected_plan_dynamic_eq_matches == 1
    assert summary.expected_plan_eq_cut_cases == 4
    assert summary.expected_plan_eq_cut_matches == 4
    assert summary.seed_bad_plan_cases == 1
    assert summary.seed_bad_plan_validator_rejects == 0
    assert summary.seed_bad_plan_critic_rejects == 1
    assert summary.seed_bad_plan_full_rejects == 0


def test_eval_harness_critic_guardrail_dataset_tracks_critic_only_rejections() -> None:
    _results, summary = evaluate_dataset("p7_critic_guardrail_stress")

    assert summary.expected_plan_cases == 6
    assert summary.expected_plan_validator_passes == 6
    assert summary.expected_plan_critic_passes == 6
    assert summary.expected_plan_full_passes == 6
    assert summary.expected_plan_planner_matches == 6
    assert summary.expected_plan_action_type_matches == 6
    assert summary.expected_plan_target_track_matches == 6
    assert summary.expected_plan_time_range_matches == 6
    assert summary.expected_plan_band_range_matches == 6
    assert summary.expected_plan_dynamic_eq_cases == 4
    assert summary.expected_plan_dynamic_eq_matches == 4
    assert summary.expected_plan_eq_cut_cases == 2
    assert summary.expected_plan_eq_cut_matches == 2
    assert summary.seed_bad_plan_cases == 6
    assert summary.seed_bad_plan_validator_rejects == 2
    assert summary.seed_bad_plan_critic_rejects == 6
    assert summary.seed_bad_plan_full_rejects == 2
