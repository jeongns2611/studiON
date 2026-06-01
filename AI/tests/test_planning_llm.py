import httpx
import pytest

from app.services.planning_llm import (
    HTTPPlanningLLMClient,
    PlanningLLMError,
    _planner_system_prompt,
)


def test_http_planning_llm_client_sends_gms_chat_completions_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> httpx.Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"strategyTitle":"Strategy","strategySummary":"Summary",'
                                '"summary":"Suggestion","explanation":"Explanation",'
                                '"candidate":{"action":{"actionType":"DYNAMIC_EQ","targetScope":"TRACK",'
                                '"targetTrackId":20,"targetClipId":null,"startMs":1000,"endMs":2200,'
                                '"bandLowHz":250,"bandHighHz":1200,"gainDeltaDb":-2.4,'
                                '"params":{"threshold":-19,"ratio":2.0}}}}'
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = HTTPPlanningLLMClient(
        base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions",
        api_key="secret-key",
        model="gpt-5.2",
        temperature=0.0,
        timeout_seconds=20.0,
        connect_timeout_seconds=5.0,
    )

    response = client.generate_plan(
        selected_region_id=1,
        preserve_clip_id=10,
        user_feedback_message="keep vocal",
        selection_context={"selectedTrackId": 1, "preserveTrackId": 1, "selectedTrackIsProtected": True},
        region={"issue_type": "band_overlap", "start_ms": 1000, "end_ms": 2200},
        clip_context=[{"clip_id": 10, "track_id": 1, "is_preserve_target": True}],
        revision_notes=[],
    )

    assert captured["url"] == "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-key",
    }
    body = captured["json"]
    assert body["model"] == "gpt-5.2"
    assert body["temperature"] == 0.0
    assert body["messages"][0]["role"] == "developer"
    assert body["messages"][1]["role"] == "user"
    assert '"selectionContext"' in body["messages"][1]["content"]
    assert response.plan_payload["strategyTitle"] == "Strategy"
    assert response.plan_payload["candidate"]["action"]["actionType"] == "DYNAMIC_EQ"


def test_http_planning_llm_client_rejects_invalid_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = HTTPPlanningLLMClient(
        base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions",
        api_key="secret-key",
        model="gpt-5.2",
        temperature=0.0,
        timeout_seconds=20.0,
        connect_timeout_seconds=5.0,
    )

    with pytest.raises(PlanningLLMError) as exc_info:
        client.generate_plan(
            selected_region_id=1,
            preserve_clip_id=10,
            user_feedback_message=None,
            selection_context={"selectedTrackId": 1, "preserveTrackId": 1, "selectedTrackIsProtected": True},
            region={"issue_type": "clipping", "start_ms": 1000, "end_ms": 2200},
            clip_context=[],
            revision_notes=[],
        )

    assert exc_info.value.code == "PLANNING_LLM_INVALID_RESPONSE"


def test_planner_system_prompt_marks_short_local_pockets_as_eq_cut_candidates() -> None:
    prompt = _planner_system_prompt()

    assert "short pocket of about 900 ms or less" in prompt
    assert "prefer EQ_CUT over DYNAMIC_EQ" in prompt


def test_planner_system_prompt_includes_band_overlap_subtype_gain_policy() -> None:
    prompt = _planner_system_prompt()

    assert "For low_mid_overlap, prefer about -2.5 to -4.5 dB" in prompt
    assert "never exceed -9 dB" in prompt
    assert "For upper_mid_overlap, prefer about -1.5 to -3.0 dB" in prompt
    assert "never exceed -6 dB" in prompt
    assert "For presence_overlap, prefer about -1.0 to -2.5 dB" in prompt
    assert "Narrow the band first toward the densest pocket" in prompt
    assert "roughly 1200 Hz or wider" in prompt
    assert "bandOverlapSubtype" in prompt
