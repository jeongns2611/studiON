from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
PROMPTS_DIR = ROOT_DIR / "prompts"

from app.core.config import get_settings  # noqa: E402
from app.services.plan_critic_llm import (  # noqa: E402
    PlanCriticLLMError,
    PlanCriticLLMResponse,
    _critic_system_prompt,
    _extract_anthropic_text,
    _parse_json_object as parse_critic_json,
    _require_string,
)
from app.services.planning_llm import (  # noqa: E402
    PlanningLLMError,
    _extract_openai_message_content,
    _parse_json_object as parse_planner_json,
    _planner_system_prompt,
    _validate_plan_payload_shape,
)
from scripts.planner_critic_eval_report import _mode_label, render_case_table, render_summary_text  # noqa: E402
from scripts.planner_critic_eval_support import (  # noqa: E402
    CaseContext,
    EvalCaseResult,
    EvalSummary,
    build_case_contexts,
    replay_case_with_plan,
    replay_non_plan_case,
    summarize_results,
)


@dataclass(frozen=True)
class VariantConfig:
    label: str
    planner_prompt: str | None
    critic_prompt: str | None


def _read_prompt_file(path: str | None) -> str | None:
    if path is None:
        return None
    return Path(path).read_text(encoding="utf-8")


def _default_prompt_path(filename: str) -> str:
    return str(PROMPTS_DIR / filename)


def _call_live_planner(context: CaseContext, planner_prompt: str | None) -> tuple[dict[str, object], str]:
    settings = get_settings()
    if not settings.planning_llm_enabled:
        raise PlanningLLMError("PLANNING_LLM_DISABLED", "Planning LLM is disabled.")
    if not settings.planning_llm_base_url:
        raise PlanningLLMError("PLANNING_LLM_URL_MISSING", "Planning LLM URL is not configured.")
    if not settings.planning_llm_api_key:
        raise PlanningLLMError("PLANNING_LLM_API_KEY_MISSING", "Planning LLM API key is not configured.")

    region = next(
        region
        for region in context.state["analysis_regions"]
        if int(region["id"]) == int(context.state["selected_region_id"])
    )
    involved_track_ids = {int(track_id) for track_id in region.get("involved_track_ids", [])}
    affected_clip_ids = {int(clip_id) for clip_id in region.get("affected_clip_ids", [])}

    preserve_clip_id = context.state.get("preserve_clip_id")
    if preserve_clip_id is not None:
        affected_clip_ids.add(int(preserve_clip_id))

    clip_context = [
        {
            "clip_id": int(clip["clip_id"]),
            "track_id": int(clip["track_id"]),
            "start_ms": clip.get("start_ms"),
            "end_ms": clip.get("end_ms"),
            "is_preserve_target": preserve_clip_id is not None and int(clip["clip_id"]) == int(preserve_clip_id),
        }
        for clip in context.state["clip_index"]
        if int(clip["clip_id"]) in affected_clip_ids or int(clip["track_id"]) in involved_track_ids
    ]

    request_payload = {
        "model": settings.planning_llm_model,
        "messages": [
            {"role": "developer", "content": planner_prompt or _planner_system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "selectedRegionId": int(context.state["selected_region_id"]),
                        "preserveClipId": preserve_clip_id,
                        "userFeedbackMessage": context.state.get("user_feedback_message"),
                        "revisionNotes": list(context.state.get("plan_revision_notes", [])),
                        "region": region,
                        "clipContext": clip_context,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.planning_llm_api_key}",
    }
    timeout = httpx.Timeout(
        timeout=settings.planning_llm_timeout_seconds,
        connect=settings.planning_llm_connect_timeout_seconds,
    )
    with httpx.Client(timeout=timeout) as client:
        response = client.post(settings.planning_llm_base_url, headers=headers, json=request_payload)
    response.raise_for_status()
    payload = response.json()
    message_content = _extract_openai_message_content(payload)
    plan_payload = parse_planner_json(message_content)
    _validate_plan_payload_shape(plan_payload)
    return plan_payload, "live planner response"


def _call_live_critic(
    context: CaseContext,
    plan_payload: dict[str, object],
    critic_prompt: str | None,
) -> PlanCriticLLMResponse:
    settings = get_settings()
    if not settings.plan_critic_enabled:
        raise PlanCriticLLMError("PLAN_CRITIC_DISABLED", "Plan critic LLM is disabled.")
    if not settings.plan_critic_base_url:
        raise PlanCriticLLMError("PLAN_CRITIC_URL_MISSING", "Plan critic LLM URL is not configured.")
    if not settings.plan_critic_api_key:
        raise PlanCriticLLMError("PLAN_CRITIC_API_KEY_MISSING", "Plan critic LLM API key is not configured.")

    region = next(
        region
        for region in context.state["analysis_regions"]
        if int(region["id"]) == int(context.state["selected_region_id"])
    )
    request_payload = {
        "model": settings.plan_critic_model,
        "max_tokens": settings.plan_critic_max_tokens,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "selectedRegionId": int(context.state["selected_region_id"]),
                        "preserveClipId": context.state.get("preserve_clip_id"),
                        "userFeedbackMessage": context.state.get("user_feedback_message"),
                        "revisionNotes": list(context.state.get("plan_revision_notes", [])),
                        "region": region,
                        "planPayload": plan_payload,
                    },
                    ensure_ascii=False,
                ),
            }
        ],
        "system": critic_prompt or _critic_system_prompt(),
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.plan_critic_api_key,
        "anthropic-version": settings.plan_critic_anthropic_version,
    }
    timeout = httpx.Timeout(
        timeout=settings.plan_critic_timeout_seconds,
        connect=settings.plan_critic_connect_timeout_seconds,
    )
    with httpx.Client(timeout=timeout) as client:
        response = client.post(settings.plan_critic_base_url, headers=headers, json=request_payload)
    response.raise_for_status()
    payload = response.json()
    message_content = _extract_anthropic_text(payload)
    parsed = parse_critic_json(message_content)
    result = _require_string(parsed, "result").upper()
    note = _require_string(parsed, "note")
    return PlanCriticLLMResponse(result=result, note=note)


def _build_error_result(context: CaseContext, mode: str, message: str) -> EvalCaseResult:
    expected_review = (
        context.case["expected_seed_review"] if mode == "seed_bad_plan" else context.case["expected_review"]
    )
    expected_plan = context.case.get("expected_plan") or {}
    expected_target_track_id = expected_plan.get("target_track_id")
    return EvalCaseResult(
        case_id=str(context.case["case_id"]),
        title=str(context.case["title"]),
        mode=mode,
        validator_result="ERROR",
        critic_result="ERROR",
        validator_expected=str(expected_review["validator"]),
        critic_expected=str(expected_review["critic"]),
        planner_match_expected=False if mode == "expected_plan" else None,
        actual_action_type=None,
        expected_action_type=str(expected_plan.get("action_type")) if mode == "expected_plan" else None,
        actual_target_track_id=None,
        expected_target_track_id=int(expected_target_track_id) if expected_target_track_id is not None and mode == "expected_plan" else None,
        passed=False,
        details=message,
        quality_focus=tuple(str(item) for item in context.case.get("quality_focus", [])),
    )


def evaluate_live_variant(dataset_id: str, variant: VariantConfig) -> tuple[list[EvalCaseResult], EvalSummary]:
    contexts = build_case_contexts(dataset_id)
    results: list[EvalCaseResult] = []
    for context in contexts:
        if context.expected_plan_payload is None:
            results.append(
                replay_non_plan_case(
                    context=context,
                    mode=context.expected_case_mode,
                    details="policy-gated case skipped by live planner compare",
                )
            )
        else:
            try:
                plan_payload, planner_details = _call_live_planner(context, variant.planner_prompt)
                results.append(
                    replay_case_with_plan(
                        context=context,
                        plan_payload=plan_payload,
                        mode="expected_plan",
                        details=planner_details,
                        critic_callable=lambda ctx, plan: _call_live_critic(ctx, plan, variant.critic_prompt),
                    )
                )
            except (PlanningLLMError, PlanCriticLLMError, httpx.HTTPError, ValueError) as exc:
                results.append(_build_error_result(context, "expected_plan", f"live planner failed: {exc}"))

        if context.seed_bad_plan_payload is not None:
            try:
                results.append(
                    replay_case_with_plan(
                        context=context,
                        plan_payload=context.seed_bad_plan_payload,
                        mode="seed_bad_plan",
                        details="live critic on seeded bad plan",
                        critic_callable=lambda ctx, plan: _call_live_critic(ctx, plan, variant.critic_prompt),
                    )
                )
            except (PlanCriticLLMError, httpx.HTTPError, ValueError) as exc:
                results.append(_build_error_result(context, "seed_bad_plan", f"live critic failed on seeded bad plan: {exc}"))

    return results, summarize_results(dataset_id=f"{dataset_id}:{variant.label}", results=results)


def render_variant_section(
    *,
    label: str,
    summary: EvalSummary,
    results: list[EvalCaseResult],
) -> str:
    lines = [f"variant: {label}", "", render_summary_text(summary), render_case_table(results)]
    return "\n".join(lines)


def _delta_text(summary_a: EvalSummary, summary_b: EvalSummary, label_a: str, label_b: str) -> str:
    lines = [
        "",
        f"delta: {label_b} - {label_a}",
        f"- planner matches: {summary_b.expected_plan_planner_matches - summary_a.expected_plan_planner_matches}",
        f"- action-type matches: {summary_b.expected_plan_action_type_matches - summary_a.expected_plan_action_type_matches}",
        f"- target-track matches: {summary_b.expected_plan_target_track_matches - summary_a.expected_plan_target_track_matches}",
        f"- time-range matches: {summary_b.expected_plan_time_range_matches - summary_a.expected_plan_time_range_matches}",
        f"- band-range matches: {summary_b.expected_plan_band_range_matches - summary_a.expected_plan_band_range_matches}",
        f"- eq-cut matches: {summary_b.expected_plan_eq_cut_matches - summary_a.expected_plan_eq_cut_matches}",
        f"- validator passes: {summary_b.expected_plan_validator_passes - summary_a.expected_plan_validator_passes}",
        f"- critic passes: {summary_b.expected_plan_critic_passes - summary_a.expected_plan_critic_passes}",
        f"- full passes: {summary_b.expected_plan_full_passes - summary_a.expected_plan_full_passes}",
        f"- bad-plan full rejects: {summary_b.seed_bad_plan_full_rejects - summary_a.seed_bad_plan_full_rejects}",
    ]
    return "\n".join(lines)


def _write_markdown_report(
    *,
    path: Path,
    dataset: str,
    label_a: str,
    results_a: list[EvalCaseResult],
    summary_a: EvalSummary,
    label_b: str | None,
    results_b: list[EvalCaseResult] | None,
    summary_b: EvalSummary | None,
) -> None:
    parts = [f"# Planner/Critic Live Compare\n\ndataset: `{dataset}`\n\n"]
    parts.append(
        f"## {label_a}\n\n```\n{render_variant_section(label=label_a, summary=summary_a, results=results_a).strip()}\n```\n\n"
    )
    if label_b and results_b is not None and summary_b is not None:
        parts.append(
            f"## {label_b}\n\n```\n{render_variant_section(label=label_b, summary=summary_b, results=results_b).strip()}\n```\n\n"
        )
        parts.append(f"## Delta\n\n```\n{_delta_text(summary_a, summary_b, label_a, label_b).strip()}\n```\n")
    path.write_text("".join(parts), encoding="utf-8")


def _write_csv_report(
    *,
    path: Path,
    dataset: str,
    variant_rows: list[tuple[str, list[EvalCaseResult]]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset",
                "variant",
                "case_id",
                "mode",
                "passed",
                "planner_match",
                "action_type_match",
                "target_track_match",
                "time_range_match",
                "band_range_match",
                "validator_result",
                "validator_expected",
                "critic_result",
                "critic_expected",
                "actual_action_type",
                "expected_action_type",
                "actual_target_track_id",
                "expected_target_track_id",
                "title",
                "quality_focus",
                "details",
            ],
        )
        writer.writeheader()
        for variant, results in variant_rows:
            for result in results:
                writer.writerow(
                    {
                        "dataset": dataset,
                        "variant": variant,
                        "case_id": result.case_id,
                        "mode": _mode_label(result.mode),
                        "passed": result.passed,
                        "planner_match": result.planner_match_expected,
                        "action_type_match": result.action_type_match,
                        "target_track_match": result.target_track_match,
                        "time_range_match": result.time_range_match,
                        "band_range_match": result.band_range_match,
                        "validator_result": result.validator_result,
                        "validator_expected": result.validator_expected,
                        "critic_result": result.critic_result,
                        "critic_expected": result.critic_expected,
                        "actual_action_type": result.actual_action_type,
                        "expected_action_type": result.expected_action_type,
                        "actual_target_track_id": result.actual_target_track_id,
                        "expected_target_track_id": result.expected_target_track_id,
                        "title": result.title,
                        "quality_focus": ", ".join(result.quality_focus),
                        "details": result.details,
                    }
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare live planner/critic outputs against fixture expectations.")
    parser.add_argument("--dataset", default="p1_dual_vocal_bed", help="Fixture dataset ID.")
    parser.add_argument("--label-a", default="baseline", help="Variant A label.")
    parser.add_argument(
        "--planner-prompt-file-a",
        default=_default_prompt_path("planner-baseline.txt"),
        help="Variant A planner prompt file.",
    )
    parser.add_argument(
        "--critic-prompt-file-a",
        default=_default_prompt_path("critic-baseline.txt"),
        help="Variant A critic prompt file.",
    )
    parser.add_argument("--label-b", help="Variant B label.")
    parser.add_argument("--planner-prompt-file-b", help="Variant B planner prompt file.")
    parser.add_argument("--critic-prompt-file-b", help="Variant B critic prompt file.")
    parser.add_argument("--output-md", help="Write a markdown report to this path.")
    parser.add_argument("--output-csv", help="Write a CSV report to this path.")
    args = parser.parse_args()

    variant_a = VariantConfig(
        label=args.label_a,
        planner_prompt=_read_prompt_file(args.planner_prompt_file_a),
        critic_prompt=_read_prompt_file(args.critic_prompt_file_a),
    )
    results_a, summary_a = evaluate_live_variant(args.dataset, variant_a)
    print(f"dataset: {args.dataset}\n")
    print(render_variant_section(label=variant_a.label, summary=summary_a, results=results_a))

    results_b = None
    summary_b = None
    if args.label_b:
        variant_b = VariantConfig(
            label=args.label_b,
            planner_prompt=_read_prompt_file(args.planner_prompt_file_b),
            critic_prompt=_read_prompt_file(args.critic_prompt_file_b),
        )
        results_b, summary_b = evaluate_live_variant(args.dataset, variant_b)
        print("")
        print(render_variant_section(label=variant_b.label, summary=summary_b, results=results_b))
        print(_delta_text(summary_a, summary_b, variant_a.label, variant_b.label))

    if args.output_md:
        _write_markdown_report(
            path=Path(args.output_md),
            dataset=args.dataset,
            label_a=variant_a.label,
            results_a=results_a,
            summary_a=summary_a,
            label_b=args.label_b,
            results_b=results_b,
            summary_b=summary_b,
        )
    if args.output_csv:
        variant_rows = [(variant_a.label, results_a)]
        if args.label_b and results_b is not None:
            variant_rows.append((args.label_b, results_b))
        _write_csv_report(path=Path(args.output_csv), dataset=args.dataset, variant_rows=variant_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
