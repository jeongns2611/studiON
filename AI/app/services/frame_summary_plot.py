from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any


@dataclass(frozen=True)
class FrameSeries:
    label: str
    metric_name: str
    color: str
    points: list[tuple[int, float]]


def build_frame_summary_svg(
    artifact_payload: dict[str, Any],
    *,
    title: str = "DSP Frame Summary",
    width: int = 1400,
    lane_height: int = 140,
    margin: int = 48,
) -> str:
    series_list = _build_series_list(artifact_payload)
    if not series_list:
        raise ValueError("Frame summary artifact does not contain plottable frame series.")

    header_height = 56
    footer_height = 24
    chart_width = max(width - (margin * 2), 240)
    height = header_height + footer_height + (lane_height * len(series_list)) + (margin * 2)
    duration_ms = _resolve_duration_ms(series_list)

    lanes: list[str] = []
    chart_top = margin + header_height
    for index, series in enumerate(series_list):
        lane_top = chart_top + (index * lane_height)
        lanes.append(
            _build_lane_svg(
                series,
                lane_top=lane_top,
                lane_height=lane_height,
                chart_left=margin,
                chart_width=chart_width,
                duration_ms=duration_ms,
            )
        )

    svg_lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#fcfcfd" />',
        (
            f'  <text x="{margin}" y="{margin}" '
            'font-family="Segoe UI, Arial, sans-serif" '
            'font-size="26" font-weight="700" fill="#0f172a">'
            f"{escape(title)}</text>"
        ),
        (
            f'  <text x="{margin}" y="{margin + 26}" '
            'font-family="Segoe UI, Arial, sans-serif" '
            'font-size="13" fill="#475569">'
            f"Duration: {duration_ms} ms | Lanes: {len(series_list)}</text>"
        ),
        *lanes,
        "</svg>",
    ]
    return "\n".join(svg_lines) + "\n"


def _build_series_list(artifact_payload: dict[str, Any]) -> list[FrameSeries]:
    series_list: list[FrameSeries] = []
    mix_frames = artifact_payload.get("mix_frames", [])
    if isinstance(mix_frames, list) and mix_frames:
        series_list.append(
            FrameSeries(
                label="Mix",
                metric_name="peak_dbfs",
                color="#2563eb",
                points=_extract_points(mix_frames, metric_name="peak_dbfs"),
            )
        )

    palette = [
        "#dc2626",
        "#059669",
        "#7c3aed",
        "#d97706",
        "#0891b2",
        "#4f46e5",
        "#be185d",
        "#65a30d",
    ]
    track_frames = artifact_payload.get("track_frames", {})
    if isinstance(track_frames, dict):
        for index, track_id in enumerate(sorted(track_frames.keys(), key=str)):
            frames = track_frames[track_id]
            if not isinstance(frames, list) or not frames:
                continue
            series_list.append(
                FrameSeries(
                    label=f"Track {track_id}",
                    metric_name="window_energy",
                    color=palette[index % len(palette)],
                    points=_extract_points(frames, metric_name="window_energy"),
                )
            )
    return series_list


def _extract_points(frames: list[dict[str, Any]], *, metric_name: str) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    for frame in frames:
        start_ms = int(frame.get("start_ms", 0))
        metric_value = frame.get(metric_name)
        if metric_value is None:
            continue
        points.append((start_ms, float(metric_value)))
    return points


def _resolve_duration_ms(series_list: list[FrameSeries]) -> int:
    return max((point[0] for series in series_list for point in series.points), default=0) or 1


def _build_lane_svg(
    series: FrameSeries,
    *,
    lane_top: int,
    lane_height: int,
    chart_left: int,
    chart_width: int,
    duration_ms: int,
) -> str:
    lane_bottom = lane_top + lane_height - 28
    baseline_y = lane_bottom
    top_y = lane_top + 24
    metric_min, metric_max = _metric_range(series.metric_name, series.points)
    polyline_points = " ".join(
        (
            f"{_scale_x(point_ms, chart_left, chart_width, duration_ms):.1f},"
            f"{_scale_y(value, top_y, baseline_y, metric_min, metric_max):.1f}"
        )
        for point_ms, value in series.points
    )
    tick_labels = _build_tick_labels(chart_left, chart_width, baseline_y + 18, duration_ms)
    lane_lines = [
        "  <g>",
        (
            f'    <text x="{chart_left}" y="{lane_top + 10}" '
            'font-family="Segoe UI, Arial, sans-serif" '
            'font-size="15" font-weight="600" fill="#111827">'
            f"{escape(series.label)}</text>"
        ),
        (
            f'    <text x="{chart_left + 86}" y="{lane_top + 10}" '
            'font-family="Segoe UI, Arial, sans-serif" '
            'font-size="12" fill="#64748b">'
            f"{escape(series.metric_name)}</text>"
        ),
        (
            f'    <rect x="{chart_left}" y="{lane_top + 18}" width="{chart_width}" '
            f'height="{lane_height - 34}" rx="10" fill="#ffffff" stroke="#e2e8f0" />'
        ),
        (
            f'    <line x1="{chart_left}" y1="{baseline_y}" '
            f'x2="{chart_left + chart_width}" y2="{baseline_y}" '
            'stroke="#cbd5e1" stroke-width="1" />'
        ),
        (
            f'    <line x1="{chart_left}" y1="{top_y}" '
            f'x2="{chart_left + chart_width}" y2="{top_y}" '
            'stroke="#f1f5f9" stroke-width="1" />'
        ),
        (
            '    <polyline fill="none" '
            f'stroke="{series.color}" stroke-width="2.5" '
            'stroke-linejoin="round" stroke-linecap="round" '
            f'points="{polyline_points}" />'
        ),
        (
            f'    <text x="{chart_left + chart_width - 120}" y="{lane_top + 36}" '
            'font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="11" fill="#64748b">min {metric_min:.3f}</text>'
        ),
        (
            f'    <text x="{chart_left + chart_width - 120}" y="{lane_top + 52}" '
            'font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="11" fill="#64748b">max {metric_max:.3f}</text>'
        ),
        f"    {tick_labels}",
        "  </g>",
    ]
    return "\n".join(lane_lines)


def _metric_range(metric_name: str, points: list[tuple[int, float]]) -> tuple[float, float]:
    if metric_name == "peak_dbfs":
        return (-60.0, 0.0)
    values = [value for _, value in points]
    minimum = min(values, default=0.0)
    maximum = max(values, default=1.0)
    if abs(maximum - minimum) < 1e-9:
        return (minimum, minimum + 1.0)
    return (minimum, maximum)


def _scale_x(point_ms: int, chart_left: int, chart_width: int, duration_ms: int) -> float:
    return chart_left + ((point_ms / max(duration_ms, 1)) * chart_width)


def _scale_y(
    value: float,
    top_y: int,
    baseline_y: int,
    metric_min: float,
    metric_max: float,
) -> float:
    normalized = (value - metric_min) / max(metric_max - metric_min, 1e-9)
    normalized = min(max(normalized, 0.0), 1.0)
    return baseline_y - (normalized * (baseline_y - top_y))


def _build_tick_labels(chart_left: int, chart_width: int, tick_y: int, duration_ms: int) -> str:
    ticks: list[str] = []
    for tick_index in range(5):
        fraction = tick_index / 4
        x = chart_left + (chart_width * fraction)
        tick_ms = int(duration_ms * fraction)
        ticks.append(
            f'<text x="{x:.1f}" y="{tick_y}" text-anchor="middle" '
            'font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="11" fill="#94a3b8">{tick_ms} ms</text>'
        )
    return "".join(ticks)
