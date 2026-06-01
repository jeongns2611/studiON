from __future__ import annotations

PREVIEW_CONTEXT_PADDING_MS = 4000


class PreviewRenderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# preview 단계는 오디오 파일을 만들지 않고
# 어떤 문제 구간을 preview 대상으로 삼는지만 메타로 확정한다.
def resolve_preview_excerpt_range(
    *,
    clip_index: list[dict[str, object]],
    focus_region: dict[str, object] | None = None,
    project_duration_ms: int | None = None,
) -> tuple[int, int]:
    if focus_region is None:
        raise PreviewRenderError(
            "PREVIEW_REGION_NOT_FOUND",
            "preview excerpt를 계산하려면 focus region이 필요합니다.",
        )

    issue_start_ms = int(focus_region.get("start_ms") or 0)
    issue_end_ms = int(focus_region.get("end_ms") or 0)
    if issue_end_ms <= issue_start_ms:
        raise PreviewRenderError(
            "INVALID_PREVIEW_RANGE",
            "문제 구간이 비어 있어 preview excerpt를 계산할 수 없습니다.",
        )

    timeline_end_ms = _resolve_timeline_end_ms(
        clip_index=clip_index,
        project_duration_ms=project_duration_ms,
    )
    return _expand_range_with_context(
        issue_start_ms=issue_start_ms,
        issue_end_ms=issue_end_ms,
        timeline_end_ms=timeline_end_ms,
    )


def _resolve_timeline_end_ms(
    *,
    clip_index: list[dict[str, object]],
    project_duration_ms: int | None,
) -> int:
    if project_duration_ms is not None and int(project_duration_ms) > 0:
        return int(project_duration_ms)
    if not clip_index:
        raise PreviewRenderError(
            "PREVIEW_CLIP_INDEX_EMPTY",
            "preview excerpt 계산에는 clip_index가 필요합니다.",
        )
    timeline_end_ms = max(int(clip.get("end_ms") or 0) for clip in clip_index)
    if timeline_end_ms <= 0:
        raise PreviewRenderError(
            "INVALID_PREVIEW_RANGE",
            "timeline 끝 구간을 계산할 수 없습니다.",
        )
    return timeline_end_ms


def _expand_range_with_context(
    *,
    issue_start_ms: int,
    issue_end_ms: int,
    timeline_end_ms: int,
) -> tuple[int, int]:
    if issue_end_ms <= issue_start_ms:
        raise PreviewRenderError(
            "INVALID_PREVIEW_RANGE",
            "문제 구간이 비어 있어 앞뒤 문맥을 붙일 수 없습니다.",
        )
    return (
        max(0, issue_start_ms - PREVIEW_CONTEXT_PADDING_MS),
        min(timeline_end_ms, issue_end_ms + PREVIEW_CONTEXT_PADDING_MS),
    )
