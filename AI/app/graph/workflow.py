from __future__ import annotations

import asyncio
import html
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph import edges, nodes
from app.graph.state import (
    ApplyState,
    RuntimeState,
    WorkflowState,
    build_apply_initial_state,
    build_runtime_initial_state,
    build_workflow_initial_state,
)
from app.persistence.projections import (
    build_apply_projections,
    build_runtime_projections,
    build_workflow_projections,
)
from app.services.workflow_snapshots import build_snapshot_runtime_context

PYPPETEER_HOME = Path.cwd() / ".pyppeteer"
os.environ["PYPPETEER_HOME"] = str(PYPPETEER_HOME)

BROWSER_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)

ENTRY_PATH_MAP = {
    "resume_after_plan_input": "resume_after_plan_input",
    "init_state": "init_state",
    "fail_workflow": "fail_workflow",
    "wait_user_plan_input": "wait_user_plan_input",
    "apply_selected_edit_recipe": "apply_selected_edit_recipe",
}

DSP_SCAN_PATH_MAP = {
    "detect_band_overlap": "detect_band_overlap",
    "fail_workflow": "fail_workflow",
}

RANKING_PATH_MAP = {
    "wait_user_plan_input": "wait_user_plan_input",
    "materialize_non_llm_issues": "materialize_non_llm_issues",
}

PLAN_INPUT_PATH_MAP = {
    "planning_agent": "planning_agent",
    "batch_plan_candidates": "batch_plan_candidates",
}

VALIDATOR_PATH_MAP = {
    "plan_critic": "plan_critic",
    "planning_agent": "planning_agent",
    "fail_workflow": "fail_workflow",
}

CRITIC_PATH_MAP = {
    "approve_plan": "approve_plan",
    "planning_agent": "planning_agent",
    "fail_workflow": "fail_workflow",
}

USER_ACTION_GATE_PATH_MAP = {
    "apply_selected_edit_recipe": "apply_selected_edit_recipe",
    "finalize_output": "finalize_output",
}

WORKFLOW_NODE_LABELS = {
    "__start__": "__start__ / 시작",
    "load_entry_context": "load_entry_context / 진입 문맥 복원",
    "resume_after_plan_input": "resume_after_plan_input / 사용자 plan 입력 반영",
    "init_state": "init_state / 상태 초기화",
    "load_project_snapshot": "load_project_snapshot / 프로젝트 스냅샷 복원",
    "sample_track_clips": "sample_track_clips / 트랙 대표 클립 샘플링",
    "cheap_dsp_scan": "cheap_dsp_scan / 전체 DSP 스캔",
    "detect_band_overlap": "detect_band_overlap / 대역 중복 탐지",
    "detect_track_clipping": "detect_track_clipping / 트랙 클리핑 탐지",
    "detect_master_clipping_candidates": (
        "detect_master_clipping_candidates / 마스터 클리핑 후보 수집"
    ),
    "analyze_master_clipping_contributors": (
        "analyze_master_clipping_contributors / 마스터 기여 트랙 분석"
    ),
    "detect_residual_master_clipping": (
        "detect_residual_master_clipping / 잔여 마스터 클리핑 탐지"
    ),
    "detect_high_band_harshness": (
        "detect_high_band_harshness / 고역 harshness 탐지"
    ),
    "select_role_candidates": "select_role_candidates / 역할 추론 후보 선택",
    "merge_analysis": "merge_analysis / 분석 결과 병합",
    "candidate_ranking": "candidate_ranking / 사용자 후보 정렬",
    "wait_user_plan_input": "wait_user_plan_input / 사용자 입력 대기",
    "planning_agent": "planning_agent / band overlap 계획 생성",
    "plan_rule_validator": "plan_rule_validator / 계획 규칙 검증",
    "plan_critic": "plan_critic / 계획 2차 검토",
    "approve_plan": "approve_plan / 계획 승인",
    "materialize_execution_plan": "materialize_execution_plan / 실행 계획 구체화",
    "auto_fix_non_user_issues": "auto_fix_non_user_issues / 자동 수정 recipe 생성",
    "log_non_user_issue_fixes": "log_non_user_issue_fixes / 자동 수정 로그 기록",
    "persist_analysis_result": "persist_analysis_result / 분석 결과 저장",
    "user_action_gate": "user_action_gate / 사용자 액션 필요 여부 판단",
    "apply_selected_edit_recipe": "apply_selected_edit_recipe / 선택 액션 적용",
    "render_preview": "render_preview / 프리뷰 렌더링",
    "finalize_output": "finalize_output / 결과 마무리",
    "fail_workflow": "fail_workflow / 실패 종료",
    "__end__": "__end__ / 종료",
}


# 워크플로우 그래프는 구조가 고정돼 있으므로
# 매 호출마다 다시 compile하지 않고 한 번 만든 결과를 재사용한다.
@lru_cache(maxsize=1)
def build_workflow_graph():
    graph = StateGraph(WorkflowState)

    graph.add_node("load_entry_context", nodes.load_entry_context)
    graph.add_node("resume_after_plan_input", nodes.resume_after_plan_input)
    graph.add_node("init_state", nodes.init_state)
    graph.add_node("load_project_snapshot", nodes.load_project_snapshot)
    graph.add_node("sample_track_clips", nodes.sample_track_clips)
    graph.add_node("cheap_dsp_scan", nodes.cheap_dsp_scan)
    graph.add_node("detect_band_overlap", nodes.detect_band_overlap)
    graph.add_node("detect_track_clipping", nodes.detect_track_clipping)
    graph.add_node(
        "detect_master_clipping_candidates",
        nodes.detect_master_clipping_candidates,
    )
    graph.add_node(
        "analyze_master_clipping_contributors",
        nodes.analyze_master_clipping_contributors,
    )
    graph.add_node(
        "detect_residual_master_clipping",
        nodes.detect_residual_master_clipping,
    )
    graph.add_node("detect_high_band_harshness", nodes.detect_high_band_harshness)
    graph.add_node("select_role_candidates", nodes.select_role_candidates)
    graph.add_node("merge_analysis", nodes.merge_analysis)
    graph.add_node("build_issue_payloads", nodes.build_issue_payloads)
    graph.add_node("candidate_ranking", nodes.candidate_ranking)
    graph.add_node("wait_user_plan_input", nodes.wait_user_plan_input)
    graph.add_node("planning_agent", nodes.planning_agent)
    graph.add_node("batch_plan_candidates", nodes.batch_plan_candidates)
    graph.add_node("plan_rule_validator", nodes.plan_rule_validator)
    graph.add_node("plan_critic", nodes.plan_critic)
    graph.add_node("approve_plan", nodes.approve_plan)
    graph.add_node("materialize_execution_plan", nodes.materialize_execution_plan)
    graph.add_node("materialize_non_llm_issues", nodes.materialize_non_llm_issues)
    graph.add_node("persist_analysis_result", nodes.persist_analysis_result)
    graph.add_node("user_action_gate", nodes.user_action_gate)
    graph.add_node("apply_selected_edit_recipe", nodes.apply_selected_edit_recipe)
    graph.add_node("render_preview", nodes.render_preview)
    graph.add_node("finalize_output", nodes.finalize_output)
    graph.add_node("fail_workflow", nodes.fail_workflow)

    graph.add_edge(START, "load_entry_context")
    graph.add_conditional_edges("load_entry_context", edges.route_after_entry, ENTRY_PATH_MAP)
    graph.add_edge("init_state", "load_project_snapshot")
    graph.add_edge("load_project_snapshot", "sample_track_clips")
    graph.add_edge("sample_track_clips", "cheap_dsp_scan")
    graph.add_conditional_edges(
        "cheap_dsp_scan",
        edges.route_after_dsp_scan,
        DSP_SCAN_PATH_MAP,
    )
    graph.add_edge("detect_band_overlap", "detect_track_clipping")
    graph.add_edge("detect_track_clipping", "detect_master_clipping_candidates")
    graph.add_edge(
        "detect_master_clipping_candidates",
        "analyze_master_clipping_contributors",
    )
    graph.add_edge(
        "analyze_master_clipping_contributors",
        "detect_residual_master_clipping",
    )
    graph.add_edge("detect_residual_master_clipping", "detect_high_band_harshness")
    graph.add_edge("detect_high_band_harshness", "select_role_candidates")
    graph.add_edge("select_role_candidates", "merge_analysis")
    graph.add_edge("merge_analysis", "build_issue_payloads")
    graph.add_edge("build_issue_payloads", "candidate_ranking")
    graph.add_conditional_edges(
        "candidate_ranking",
        edges.route_after_candidate_ranking,
        RANKING_PATH_MAP,
    )
    graph.add_edge("wait_user_plan_input", END)
    graph.add_conditional_edges(
        "resume_after_plan_input",
        edges.route_after_plan_input,
        PLAN_INPUT_PATH_MAP,
    )
    graph.add_edge("batch_plan_candidates", "persist_analysis_result")
    graph.add_edge("planning_agent", "plan_rule_validator")
    graph.add_conditional_edges(
        "plan_rule_validator",
        edges.route_after_validator,
        VALIDATOR_PATH_MAP,
    )
    graph.add_conditional_edges(
        "plan_critic",
        edges.route_after_critic,
        CRITIC_PATH_MAP,
    )
    graph.add_edge("approve_plan", "materialize_execution_plan")
    graph.add_edge("materialize_execution_plan", "materialize_non_llm_issues")
    graph.add_edge("materialize_non_llm_issues", "persist_analysis_result")
    graph.add_edge("persist_analysis_result", "user_action_gate")
    graph.add_conditional_edges(
        "user_action_gate",
        edges.route_after_user_action_gate,
        USER_ACTION_GATE_PATH_MAP,
    )
    graph.add_edge("apply_selected_edit_recipe", "render_preview")
    graph.add_edge("render_preview", "finalize_output")
    graph.add_edge("finalize_output", END)
    graph.add_edge("fail_workflow", END)

    compiled = graph.compile()
    compiled.name = "studion-workflow-graph"
    return compiled


def build_runtime_graph():
    return build_workflow_graph()


def build_apply_graph():
    return build_workflow_graph()


def run_workflow_graph(state: WorkflowState | dict) -> WorkflowState:
    raw_state = dict(state)
    project_snapshot = raw_state.pop("project_snapshot", None)
    if project_snapshot is not None:
        # 동기 실행 테스트나 graph 직접 호출도 start API와 같은 snapshot 파생 메타를 쓰게 맞춘다.
        context = build_snapshot_runtime_context(project_snapshot)
        raw_state.setdefault("project_duration_ms", context.duration_ms)
        raw_state.setdefault("track_ids", context.track_ids)
        raw_state.setdefault("track_name_map", context.track_name_map)
        raw_state.setdefault("bpm", context.bpm)
        raw_state.setdefault("numerator", context.numerator)
        raw_state.setdefault("denominator", context.denominator)
        raw_state.setdefault("bar_mapping", context.bar_mapping)
        raw_state.setdefault("clip_index", context.clip_index)
        raw_state.setdefault("track_eq_map", context.track_eq_map)
    initial = build_workflow_initial_state(
        job_id=raw_state["job_id"],
        project_id=raw_state["project_id"],
        **{key: value for key, value in raw_state.items() if key not in {"job_id", "project_id"}},
    )
    return build_workflow_graph().invoke(initial, config={"recursion_limit": 100})


def run_runtime_graph(state: RuntimeState | dict) -> RuntimeState:
    initial = build_runtime_initial_state(
        job_id=state["job_id"],
        project_id=state["project_id"],
        **{key: value for key, value in dict(state).items() if key not in {"job_id", "project_id"}},
    )
    return run_workflow_graph(initial)


def run_apply_graph(state: ApplyState | dict) -> ApplyState:
    initial = build_apply_initial_state(
        job_id=state["job_id"],
        project_id=state["project_id"],
        preview_id=state["preview_id"],
        suggestion_group_id=state["suggestion_group_id"],
        **{
            key: value
            for key, value in dict(state).items()
            if key not in {"job_id", "project_id", "preview_id", "suggestion_group_id"}
        },
    )
    return run_workflow_graph(initial)


def build_workflow_response(state: WorkflowState) -> dict[str, Any]:
    return {
        "graph_state": dict(state),
        "projections": build_workflow_projections(state).model_dump(mode="json"),
    }


def build_runtime_response(state: RuntimeState) -> dict[str, Any]:
    return {
        "graph_state": dict(state),
        "projections": build_runtime_projections(state).model_dump(mode="json"),
    }


def build_apply_response(state: ApplyState) -> dict[str, Any]:
    return {
        "graph_state": dict(state),
        "projections": build_apply_projections(state).model_dump(mode="json"),
    }


def draw_workflow_graph_mermaid() -> str:
    return _apply_node_labels(
        build_workflow_graph().get_graph().draw_mermaid(),
        WORKFLOW_NODE_LABELS,
    )


def draw_runtime_graph_mermaid() -> str:
    return draw_workflow_graph_mermaid()


def draw_apply_graph_mermaid() -> str:
    return draw_workflow_graph_mermaid()


def draw_workflow_graph_png(output_file_path: str | None = None) -> bytes:
    return _render_mermaid_png(draw_workflow_graph_mermaid(), output_file_path=output_file_path)


def draw_runtime_graph_png(output_file_path: str | None = None) -> bytes:
    return draw_workflow_graph_png(output_file_path=output_file_path)


def draw_apply_graph_png(output_file_path: str | None = None) -> bytes:
    return draw_workflow_graph_png(output_file_path=output_file_path)


def export_graph_pngs(output_dir: str | None = None) -> Path:
    target_dir = Path(output_dir or Path.cwd()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = target_dir / "workflow-graph.png"
    draw_workflow_graph_png(str(workflow_path))
    return workflow_path


def open_graph_pngs(output_dir: str | None = None) -> Path:
    workflow_path = export_graph_pngs(output_dir)
    os.startfile(workflow_path)
    return workflow_path


def _resolve_browser_executable() -> str:
    for candidate in BROWSER_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("No local Chrome or Edge executable was found for Mermaid rendering.")


def _apply_node_labels(mermaid_source: str, labels: dict[str, str]) -> str:
    pattern = re.compile(r"^(\s*)([A-Za-z0-9_]+)\((.*)\)$", re.MULTILINE)

    def replace(match: re.Match[str]) -> str:
        indent, node_id, body = match.groups()
        label = labels.get(node_id)
        if label is None:
            return match.group(0)

        if body.startswith("<p>") and body.endswith("</p>"):
            content = html.escape(label).replace(" / ", "<br/>")
            return f"{indent}{node_id}(<p>{content}</p>)"

        content = html.escape(label).replace(" / ", "<br/>")
        return f'{indent}{node_id}("{content}")'

    return pattern.sub(replace, mermaid_source)


def _render_mermaid_png(mermaid_source: str, output_file_path: str | None = None) -> bytes:
    return asyncio.run(_render_mermaid_png_async(mermaid_source, output_file_path))


async def _render_mermaid_png_async(
    mermaid_source: str,
    output_file_path: str | None,
) -> bytes:
    from pyppeteer import launch

    browser = await launch(
        executablePath=_resolve_browser_executable(),
        headless=True,
        autoClose=True,
        args=[
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-software-rasterizer",
        ],
    )
    try:
        page = await browser.newPage()
        await page.setViewport({"width": 3200, "height": 5600, "deviceScaleFactor": 3})
        await page.setContent(_mermaid_html(mermaid_source))
        await page.waitForSelector("svg")
        container = await page.querySelector("#graph")
        if container is None:
            raise RuntimeError("Rendered Mermaid graph container was not found.")
        screenshot_options = {"path": output_file_path} if output_file_path else {}
        image_bytes = await container.screenshot(screenshot_options)
        return image_bytes
    finally:
        await browser.close()


def _mermaid_html(mermaid_source: str) -> str:
    escaped_source = html.escape(mermaid_source)
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #ffffff;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", Arial, sans-serif;
    }}
    #graph {{
      display: inline-block;
      background: #ffffff;
      padding: 16px;
    }}
    #graph svg text,
    #graph .nodeLabel,
    #graph foreignObject,
    #graph div {{
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", Arial, sans-serif;
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
</head>
<body>
  <div id="graph">
    <pre class="mermaid">{escaped_source}</pre>
  </div>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      securityLevel: "loose",
      flowchart: {{ htmlLabels: true }},
      fontFamily: '"Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", Arial, sans-serif'
    }});
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    if "--png" in sys.argv or "--open" in sys.argv:
        workflow_path = export_graph_pngs()
        print(f"workflow graph png: {workflow_path}")
        if "--open" in sys.argv:
            os.startfile(workflow_path)
    else:
        print("[workflow]")
        print(draw_workflow_graph_mermaid())
