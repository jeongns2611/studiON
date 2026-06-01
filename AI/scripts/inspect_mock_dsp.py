from __future__ import annotations

import argparse
import json
from typing import Any

from app.graph.workflow import build_workflow_response, run_workflow_graph
from app.utils.logger import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mock DSP 워크플로우를 직접 실행하고 핵심 상태를 출력합니다.",
    )
    parser.add_argument("--job-id", type=int, default=10001)
    parser.add_argument("--project-id", type=int, default=20001)
    parser.add_argument("--track-ids", default="10,20")
    parser.add_argument(
        "--audio-paths",
        default="",
        help="track_ids 순서와 맞는 WAV 경로 CSV입니다.",
    )
    parser.add_argument("--issue-types", default="band_overlap,sibilance,clipping")
    parser.add_argument("--duration-ms", type=int, default=4800)
    parser.add_argument("--bpm", type=float, default=120.0)
    parser.add_argument("--numerator", type=int, default=4)
    parser.add_argument("--denominator", type=int, default=4)
    parser.add_argument("--clips-per-track", type=int, default=2)
    parser.add_argument("--main-track-id", type=int, default=None)
    parser.add_argument(
        "--auto-resume-mix-intent",
        action="store_true",
        help="main_track_id가 있으면 waiting 상태를 자동으로 한 번 더 진행합니다.",
    )
    parser.add_argument(
        "--resume-plan-input",
        action="store_true",
        help="wait_user_plan_input 결과를 사용자 입력으로 바로 재개합니다.",
    )
    parser.add_argument(
        "--selected-region-id",
        type=int,
        default=None,
        help="재개할 때 사용할 선택된 문제 구간 id입니다.",
    )
    parser.add_argument(
        "--preserve-clip-id",
        type=int,
        default=None,
        help="재개할 때 사용할 보존 기준 clip id입니다.",
    )
    parser.add_argument(
        "--user-feedback-message",
        default=None,
        help="사용자가 추가로 남긴 변경 요구사항입니다.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="사람이 읽는 요약 없이 JSON만 출력합니다.",
    )
    parser.add_argument(
        "--full-response",
        action="store_true",
        help="graph_state와 projections 전체를 그대로 출력합니다.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="노드 전이, 랭킹 점수, 메모까지 함께 출력합니다.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="애플리케이션 로그 레벨을 지정합니다.",
    )
    return parser.parse_args()


def build_project_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    track_ids = parse_csv_ints(args.track_ids)
    audio_paths = parse_csv_strings(args.audio_paths)
    audio_path_by_track = {
        track_id: audio_paths[index]
        for index, track_id in enumerate(track_ids)
        if index < len(audio_paths)
    }
    clips: list[dict[str, Any]] = []
    clip_length_ms = max(args.duration_ms // max(args.clips_per_track, 1), 1)
    for track_id in track_ids:
        for clip_index in range(args.clips_per_track):
            start_ms = clip_index * clip_length_ms
            end_ms = min(start_ms + clip_length_ms + 600, args.duration_ms)
            clips.append(
                {
                    "clip_id": (track_id * 1000) + clip_index + 1,
                    "track_id": track_id,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "audio_path": audio_path_by_track.get(track_id),
                    "audio_start_ms": start_ms,
                    "audio_duration_ms": max(end_ms - start_ms, 1),
                }
            )
    return {
        "duration_ms": args.duration_ms,
        "bpm": args.bpm,
        "numerator": args.numerator,
        "denominator": args.denominator,
        "tracks": [{"track_id": track_id, "name": f"Track {track_id}"} for track_id in track_ids],
        "clips": clips,
    }


def parse_csv_ints(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def parse_csv_strings(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    request = {
        "job_id": args.job_id,
        "project_id": args.project_id,
        "project_snapshot": build_project_snapshot(args),
        "issue_types": parse_csv_strings(args.issue_types),
    }
    if args.main_track_id is not None:
        request["main_track_id"] = args.main_track_id
    return request


def run_request(args: argparse.Namespace) -> dict[str, Any]:
    initial_request = build_request(args)
    first_result = run_workflow_graph(initial_request)
    if args.resume_plan_input:
        return _resume_plan_input(first_result, args)
    if not args.auto_resume_mix_intent or args.main_track_id is None:
        return first_result
    if first_result.get("phase") != "waiting_for_user_mix_intent":
        return first_result
    return run_workflow_graph(
        {
            **first_result,
            "main_track_id": args.main_track_id,
        }
    )


def _resume_plan_input(first_result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if first_result.get("phase") != "waiting_for_user_plan_input":
        return first_result

    # 명시 인자가 없으면 실제 UI와 비슷하게 랭킹 1순위 region과 첫 affected clip을 기본값으로 사용한다.
    selected_region_id = args.selected_region_id or _default_selected_region_id(first_result)
    preserve_clip_id = args.preserve_clip_id or _default_preserve_clip_id(
        first_result,
        selected_region_id,
    )
    resume_payload = {
        **first_result,
        "selected_region_id": selected_region_id,
        "preserve_clip_id": preserve_clip_id,
    }
    if args.user_feedback_message:
        resume_payload["user_feedback_message"] = args.user_feedback_message
    return run_workflow_graph(resume_payload)


def _default_selected_region_id(result: dict[str, Any]) -> int | None:
    ranked_candidate_ids = result.get("ranked_candidate_ids", [])
    if ranked_candidate_ids:
        return int(ranked_candidate_ids[0])
    return None


def _default_preserve_clip_id(result: dict[str, Any], selected_region_id: int | None) -> int | None:
    if selected_region_id is None:
        return None
    for region in result.get("analysis_regions", []):
        if int(region["id"]) == int(selected_region_id):
            affected_clip_ids = region.get("affected_clip_ids", [])
            if affected_clip_ids:
                return int(affected_clip_ids[0])
    return None


def build_preview_payload(
    result: dict[str, Any],
    *,
    full_response: bool,
    debug: bool,
) -> dict[str, Any]:
    response = build_workflow_response(result)
    if full_response:
        return response

    dsp_summary = result.get("dsp_scan_summary", {})
    preview_summary = {
        "analysis_source": dsp_summary.get("analysis_source"),
        "frame_ms": dsp_summary.get("frame_ms"),
        "hop_ms": dsp_summary.get("hop_ms"),
        "frame_count": dsp_summary.get("frame_count"),
        "analysis_start_ms": dsp_summary.get("analysis_start_ms"),
        "track_stats": dsp_summary.get("track_stats", {}),
        "mix_windows_preview": dsp_summary.get("mix_windows_preview", []),
        "track_windows_preview": dsp_summary.get("track_windows_preview", {}),
    }
    payload = {
        "request": {
            "job_id": result.get("job_id"),
            "project_id": result.get("project_id"),
            "track_ids": result.get("track_ids"),
            "issue_types": result.get("issue_types"),
            "main_track_id": result.get("main_track_id"),
        },
        "runtime": {
            "phase": result.get("phase"),
            "current_node": result.get("current_node"),
            "runtime_status": result.get("runtime_status"),
            "durable_status": result.get("durable_status"),
            "sampled_clip_ids": result.get("sampled_clip_ids"),
            "detected_issues": result.get("detected_issues"),
            "ranked_candidate_ids": result.get("ranked_candidate_ids"),
        },
        "compact_dsp_summary": preview_summary,
        "analysis_regions": response["projections"]["analysis_regions"],
        "suggestion_group": response["projections"]["suggestion_group"],
        "preview_render": response["projections"]["preview_render"],
    }
    if debug:
        payload["debug"] = {
            "transition_log": result.get("transition_log", []),
            "ranking_scores": result.get("ranking_scores", {}),
            "notes": result.get("notes", []),
            "failure": {
                "failure_code": result.get("failure_code"),
                "failure_message": result.get("failure_message"),
            },
        }
    return payload


def print_human_summary(payload: dict[str, Any]) -> None:
    request = payload.get("request", {})
    runtime = payload.get("runtime", {})
    regions = payload.get("analysis_regions", [])
    suggestion_group = payload.get("suggestion_group")
    preview_render = payload.get("preview_render")
    debug_payload = payload.get("debug", {})

    print("=== Request ===")
    print(f"job_id: {request.get('job_id')}")
    print(f"project_id: {request.get('project_id')}")
    print(f"track_ids: {request.get('track_ids')}")
    print(f"issue_types: {request.get('issue_types')}")
    print(f"main_track_id: {request.get('main_track_id')}")
    print()

    print("=== Runtime ===")
    print(f"phase: {runtime.get('phase')}")
    print(f"current_node: {runtime.get('current_node')}")
    print(f"runtime_status: {runtime.get('runtime_status')}")
    print(f"durable_status: {runtime.get('durable_status')}")
    print(f"sampled_clip_ids: {runtime.get('sampled_clip_ids')}")
    print(f"detected_issues: {runtime.get('detected_issues')}")
    print(f"ranked_candidate_ids: {runtime.get('ranked_candidate_ids')}")
    print()

    print("=== DSP ===")
    print(f"analysis_source: {payload.get('compact_dsp_summary', {}).get('analysis_source')}")
    print(f"frame_ms: {payload.get('compact_dsp_summary', {}).get('frame_ms')}")
    print(f"hop_ms: {payload.get('compact_dsp_summary', {}).get('hop_ms')}")
    print(f"frame_count: {payload.get('compact_dsp_summary', {}).get('frame_count')}")
    print()

    print("=== Regions ===")
    if not regions:
        print("no analysis regions")
    for region in regions:
        print(
            " - "
            f"{region.get('issue_type')} | "
            f"ms {region.get('start_ms')}~{region.get('end_ms')} | "
            f"measure {region.get('measure_start')}~{region.get('measure_end')} | "
            f"severity {region.get('severity')} | "
            f"clips {region.get('affected_clip_ids')}"
        )
    print()

    print("=== Suggestions ===")
    if suggestion_group is None:
        print("suggestion_group: null")
    else:
        print(f"group_id: {suggestion_group.get('id')}")
        print(f"title: {suggestion_group.get('title')}")
        print(f"summary: {suggestion_group.get('summary')}")
        print(f"region_id: {suggestion_group.get('region_id')}")
        print(
            "measure_range: "
            f"{suggestion_group.get('measure_start')}~{suggestion_group.get('measure_end')}"
        )
        for suggestion in suggestion_group.get("suggestions", []):
            print(
                " - "
                f"{suggestion.get('id')} | rank {suggestion.get('rank_no')} | "
                f"{suggestion.get('summary')}"
            )
            for action in suggestion.get("actions", []):
                print(
                    "   action: "
                    f"{action.get('action_type')} | "
                    f"track {action.get('target_track_id')} | "
                    f"ms {action.get('start_ms')}~{action.get('end_ms')} | "
                    f"band {action.get('band_low_hz')}~{action.get('band_high_hz')}"
                )
    print()

    print("=== Preview ===")
    if preview_render is None:
        print("preview_render: null")
    else:
        print(f"preview_id: {preview_render.get('id')}")
        print(f"status: {preview_render.get('status')}")
    print()

    if debug_payload:
        print("=== Debug ===")
        print(f"transition_log: {debug_payload.get('transition_log')}")
        print(f"ranking_scores: {debug_payload.get('ranking_scores')}")
        print(f"notes: {debug_payload.get('notes')}")
        failure = debug_payload.get("failure", {})
        if failure.get("failure_code") or failure.get("failure_message"):
            print(
                "failure: "
                f"{failure.get('failure_code')} | {failure.get('failure_message')}"
            )
        print()


def main() -> None:
    args = parse_args()
    configure_logging(level="DEBUG" if args.debug else args.log_level)
    result = run_request(args)
    preview_payload = build_preview_payload(
        result,
        full_response=args.full_response,
        debug=args.debug,
    )
    if not args.json_only and not args.full_response:
        print_human_summary(preview_payload)
        print("=== JSON ===")
    print(json.dumps(preview_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
