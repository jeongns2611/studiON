from app.services.frame_summary_plot import build_frame_summary_svg


def test_build_frame_summary_svg_renders_mix_and_track_lanes() -> None:
    artifact_payload = {
        "mix_frames": [
            {"start_ms": 0, "peak_dbfs": -12.0},
            {"start_ms": 100, "peak_dbfs": -6.0},
            {"start_ms": 200, "peak_dbfs": -3.0},
        ],
        "track_frames": {
            "10": [
                {"start_ms": 0, "window_energy": 0.1},
                {"start_ms": 100, "window_energy": 0.25},
                {"start_ms": 200, "window_energy": 0.18},
            ]
        },
    }

    svg = build_frame_summary_svg(artifact_payload, title="Test Plot")

    assert "<svg" in svg
    assert "Test Plot" in svg
    assert "Mix" in svg
    assert "Track 10" in svg
    assert "peak_dbfs" in svg
    assert "window_energy" in svg
