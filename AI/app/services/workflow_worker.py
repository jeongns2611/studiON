from __future__ import annotations

import logging

from app.graph.workflow import run_workflow_graph
from app.services.workflow_jobs import WorkflowDispatchMessage, get_workflow_job_store

logger = logging.getLogger(__name__)


# 큐에 들어온 dispatch 메시지를 worker가 받아 실제 LangGraph 실행으로 넘기는 단계다.
# start 요청이면 여기서 run_workflow_graph가 호출되고,
# 이후 그래프 내부에서 load_project_snapshot 같은 노드가 순서대로 실행된다.
def run_workflow_dispatch(message: WorkflowDispatchMessage):
    store = get_workflow_job_store()
    logger.info(
        "워크플로 작업 소비 시작: job_id=%s dispatch_type=%s",
        message.job_id,
        message.dispatch_type,
    )
    # worker는 큐 payload만 받고,
    # 실제 상태 복원은 graph entry에서 durable snapshot 기준으로 수행한다.
    result = run_workflow_graph(
        {
            "job_id": message.job_id,
            "project_id": message.project_id,
            "dispatch_type": message.dispatch_type,
            "requested_by": message.requested_by,
            "request_mode": message.request_mode,
            "selected_region_id": message.selected_region_id,
            "preserve_clip_id": message.preserve_clip_id,
            "selected_region_selections": [
                selection.model_dump(mode="python")
                for selection in message.selected_region_selections
            ],
            "issue_id": message.issue_id,
            "action_type": message.action_type,
            "action_payload": message.action_payload,
            "user_feedback_message": message.user_feedback_message,
            "user_decision": message.user_decision,
        }
    )
    store.save_graph_state(result)
    logger.info(
        "워크플로 작업 소비 완료: job_id=%s phase=%s durable_status=%s",
        message.job_id,
        result.get("phase"),
        result.get("durable_status"),
    )
    return result
