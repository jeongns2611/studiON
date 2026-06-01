from app.graph.state import WorkflowState


# entry 진입 시에는 실패 복구, interrupt 재진입, 신규 실행 시작 중 무엇인지 먼저 분기한다.
def route_after_entry(state: WorkflowState) -> str:
    if state.get("runtime_status") == "failed" or state.get("durable_status") == "FAILED":
        return "fail_workflow"
    if state.get("phase") == "waiting_for_user_plan_input":
        if (
            (
                state.get("selected_region_id") is not None
                and state.get("preserve_clip_id") is not None
            )
            or state.get("selected_region_selections")
        ):
            return "resume_after_plan_input"
        return "wait_user_plan_input"
    return "init_state"


# DSP 단계에서 이미 실패가 확정되면 이후 detector를 더 세우지 않고 즉시 실패 경로로 보낸다.
def route_after_dsp_scan(state: WorkflowState) -> str:
    return "fail_workflow" if state.get("runtime_status") == "failed" else "detect_band_overlap"


# 사용자 입력이 필요한 후보가 있으면 plan input 대기 상태로, 없으면 바로 실행 계획 구체화로 보낸다.
def route_after_candidate_ranking(state: WorkflowState) -> str:
    if state.get("ranked_candidate_ids"):
        return "wait_user_plan_input"
    return "materialize_non_llm_issues"


# plan input이 채워졌다면 즉시 rule candidate 구성을 시작한다.
def route_after_plan_input(state: WorkflowState) -> str:
    if state.get("request_mode") == "batch":
        return "batch_plan_candidates"
    return "planning_agent"


# validator 통과, 재생성, 실패 중 갈래만 만들고 revise 허용 횟수를 넘기면 실패로 닫는다.
def route_after_validator(state: WorkflowState) -> str:
    if state.get("runtime_status") == "failed" or state.get("current_node") == "fail_workflow":
        return "fail_workflow"
    result = state.get("validator_result")
    if result == "PASS":
        return "plan_critic"
    if result in {"REVISE", "REJECT"} and state.get("revise_count", 0) < state.get("max_revise_count", 5):
        return "planning_agent"
    return "fail_workflow"


# critic도 validator와 같은 규칙으로 pass/revise/fail을 결정한다.
def route_after_critic(state: WorkflowState) -> str:
    if state.get("runtime_status") == "failed" or state.get("current_node") == "fail_workflow":
        return "fail_workflow"
    result = state.get("critic_result")
    if result == "PASS":
        return "approve_plan"
    if result in {"REVISE", "REJECT"} and state.get("revise_count", 0) < state.get("max_revise_count", 5):
        return "planning_agent"
    return "fail_workflow"


# 사용자 선택이 필요한 suggestion/action이 있으면 selection wait로, 없으면 결과를 바로 종료한다.
def route_after_user_action_gate(state: WorkflowState) -> str:
    return "apply_selected_edit_recipe" if state.get("preview_required") else "finalize_output"


# preview 이후에는 confirm/retry/cancel만 허용하고, 그 외 값은 안전하게 END로 닫는다.
