import httpx
import pytest

from app.services.plan_critic_llm import (
    HTTPPlanCriticLLMClient,
    PlanCriticLLMError,
    _critic_system_prompt,
)


def test_http_plan_critic_llm_client_sends_anthropic_shape(
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
            json={"content": [{"type": "text", "text": '{"result":"PASS","note":"Looks safe."}'}]},
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = HTTPPlanCriticLLMClient(
        base_url="https://gms.ssafy.io/gmsapi/anthropic/v1/messages",
        api_key="critic-key",
        model="claude-sonnet-4-5-20250929",
        anthropic_version="2023-06-01",
        max_tokens=1024,
        timeout_seconds=20.0,
        connect_timeout_seconds=5.0,
    )

    response = client.review_plan(
        selected_region_id=1,
        preserve_clip_id=10,
        user_feedback_message="keep vocal",
        selection_context={"selectedTrackId": 1, "preserveTrackId": 1, "selectedTrackIsProtected": True},
        region={"issue_type": "band_overlap"},
        plan_payload={"strategyTitle": "Strategy"},
        revision_notes=[],
    )

    assert captured["url"] == "https://gms.ssafy.io/gmsapi/anthropic/v1/messages"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "x-api-key": "critic-key",
        "anthropic-version": "2023-06-01",
    }
    body = captured["json"]
    assert body["model"] == "claude-sonnet-4-5-20250929"
    assert body["messages"][0]["role"] == "user"
    assert '"selectionContext"' in body["messages"][0]["content"]
    assert response.result == "PASS"
    assert response.note == "Looks safe."


def test_http_plan_critic_llm_client_rejects_invalid_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not-json"}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = HTTPPlanCriticLLMClient(
        base_url="https://gms.ssafy.io/gmsapi/anthropic/v1/messages",
        api_key="critic-key",
        model="claude-sonnet-4-5-20250929",
        anthropic_version="2023-06-01",
        max_tokens=1024,
        timeout_seconds=20.0,
        connect_timeout_seconds=5.0,
    )

    with pytest.raises(PlanCriticLLMError) as exc_info:
        client.review_plan(
            selected_region_id=1,
            preserve_clip_id=10,
            user_feedback_message=None,
            selection_context={"selectedTrackId": 1, "preserveTrackId": 1, "selectedTrackIsProtected": True},
            region={"issue_type": "clipping"},
            plan_payload={"strategyTitle": "Strategy"},
            revision_notes=[],
        )

    assert exc_info.value.code == "PLAN_CRITIC_INVALID_RESPONSE"


def test_critic_system_prompt_requires_eq_cut_for_short_local_pockets() -> None:
    prompt = _critic_system_prompt()

    assert "short pocket of about 900 ms or less" in prompt
    assert "do not PASS DYNAMIC_EQ by default" in prompt


def test_critic_system_prompt_mentions_presence_overlap_guardrail() -> None:
    prompt = _critic_system_prompt()

    assert "bandOverlapSubtype" in prompt
    assert "upper_mid_overlap" in prompt
    assert "above -6 dB" in prompt
    assert "presence_overlap" in prompt
    assert "above -4 dB" in prompt
    assert "prefer REVISE over REJECT on the first pass" in prompt
    assert "keep gain around -2.5 dB or lower" in prompt
