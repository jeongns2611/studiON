from __future__ import annotations

from functools import lru_cache

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from app.core.config import get_settings
from app.services.workflow_jobs import WorkflowDispatchMessage
from app.services.workflow_worker import run_workflow_dispatch


@lru_cache(maxsize=1)
def get_dramatiq_broker():
    settings = get_settings()
    if settings.dramatiq_broker_url:
        return RedisBroker(url=settings.dramatiq_broker_url)
    return StubBroker()


def configure_dramatiq() -> None:
    # 그래프는 broker 구현을 몰라야 하므로, 큐 선택은 여기서 한 번만 설정한다.
    dramatiq.set_broker(get_dramatiq_broker())


configure_dramatiq()


@dramatiq.actor(queue_name=get_settings().workflow_queue_name)
def workflow_dispatch_actor(payload: dict) -> None:
    # 큐 소비는 worker 경계에서 끝내고, durable 상태 복원은 아래 계층에서 시작해
    # LangGraph 노드가 Dramatiq를 직접 다루지 않게 유지한다.
    run_workflow_dispatch(WorkflowDispatchMessage.model_validate(payload))


def enqueue_workflow_dispatch(message: WorkflowDispatchMessage):
    return workflow_dispatch_actor.send(message.model_dump(mode="json"))
