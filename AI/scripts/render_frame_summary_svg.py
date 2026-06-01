from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.frame_summary_plot import build_frame_summary_svg
from app.services.workflow_artifacts import get_workflow_artifact_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DSP frame summary artifact를 간단한 SVG 그래프로 렌더링한다.",
    )
    parser.add_argument("--artifact-id", help="workflow artifact store에서 읽을 artifact id")
    parser.add_argument("--artifact-json", help="artifact payload JSON 파일 경로")
    parser.add_argument(
        "--workflow-json",
        help="graph_state 또는 build_workflow_response 결과 JSON 파일 경로",
    )
    parser.add_argument(
        "--output",
        default="build/frame-summary.svg",
        help="출력 SVG 파일 경로",
    )
    parser.add_argument("--title", default="DSP Frame Summary")
    return parser.parse_args()


def load_artifact_payload(args: argparse.Namespace) -> dict[str, Any]:
    provided = [bool(args.artifact_id), bool(args.artifact_json), bool(args.workflow_json)]
    if sum(provided) != 1:
        raise SystemExit("하나의 입력만 지정해야 합니다: --artifact-id, --artifact-json, --workflow-json")

    if args.artifact_id:
        document = get_workflow_artifact_store().get_artifact(args.artifact_id)
        if document is None:
            raise SystemExit(f"artifact를 찾지 못했습니다: {args.artifact_id}")
        return document.payload

    if args.artifact_json:
        payload = json.loads(Path(args.artifact_json).read_text(encoding="utf-8"))
        return _unwrap_payload(payload)

    workflow_payload = json.loads(Path(args.workflow_json).read_text(encoding="utf-8"))
    return _load_payload_from_workflow_json(workflow_payload)


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "payload" in payload and isinstance(payload["payload"], dict):
        return payload["payload"]
    return payload


def _load_payload_from_workflow_json(workflow_payload: dict[str, Any]) -> dict[str, Any]:
    graph_state = workflow_payload.get("graph_state", workflow_payload)
    if not isinstance(graph_state, dict):
        raise SystemExit("workflow JSON에서 graph_state를 해석하지 못했습니다.")
    artifact_id = graph_state.get("clip_feature_artifact_id")
    if not artifact_id:
        raise SystemExit("workflow JSON에 clip_feature_artifact_id가 없습니다.")
    document = get_workflow_artifact_store().get_artifact(artifact_id)
    if document is None:
        raise SystemExit(
            "artifact store에서 clip_feature_artifact_id를 찾지 못했습니다. "
            "필요하면 artifact payload를 JSON으로 직접 저장해서 --artifact-json으로 넘기세요."
        )
    return document.payload


def main() -> None:
    args = parse_args()
    artifact_payload = load_artifact_payload(args)
    svg = build_frame_summary_svg(artifact_payload, title=args.title)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(output_path.resolve())


if __name__ == "__main__":
    main()
