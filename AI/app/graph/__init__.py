"""그래프 공개 API를 지연 import로 노출한다."""


def build_apply_graph():
    from app.graph.workflow import build_apply_graph as _build_apply_graph

    return _build_apply_graph()


def build_runtime_graph():
    from app.graph.workflow import build_runtime_graph as _build_runtime_graph

    return _build_runtime_graph()


def build_workflow_graph():
    from app.graph.workflow import build_workflow_graph as _build_workflow_graph

    return _build_workflow_graph()


def run_apply_graph(state):
    from app.graph.workflow import run_apply_graph as _run_apply_graph

    return _run_apply_graph(state)


def run_runtime_graph(state):
    from app.graph.workflow import run_runtime_graph as _run_runtime_graph

    return _run_runtime_graph(state)


def run_workflow_graph(state):
    from app.graph.workflow import run_workflow_graph as _run_workflow_graph

    return _run_workflow_graph(state)


__all__ = [
    "build_apply_graph",
    "build_runtime_graph",
    "build_workflow_graph",
    "run_apply_graph",
    "run_runtime_graph",
    "run_workflow_graph",
]
