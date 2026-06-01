from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings


class PlanCriticLLMError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PlanCriticLLMResponse:
    result: str
    note: str
    raw_text: str | None = None


class PlanCriticLLMClient(Protocol):
    def review_plan(
        self,
        *,
        selected_region_id: int,
        preserve_clip_id: int,
        user_feedback_message: str | None,
        selection_context: dict[str, object],
        region: dict[str, object],
        plan_payload: dict[str, object],
        revision_notes: list[str],
    ) -> PlanCriticLLMResponse: ...


class HTTPPlanCriticLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        anthropic_version: str,
        max_tokens: int,
        timeout_seconds: float,
        connect_timeout_seconds: float,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._anthropic_version = anthropic_version
        self._max_tokens = max_tokens
        self._timeout = httpx.Timeout(timeout=timeout_seconds, connect=connect_timeout_seconds)

    def review_plan(
        self,
        *,
        selected_region_id: int,
        preserve_clip_id: int,
        user_feedback_message: str | None,
        selection_context: dict[str, object],
        region: dict[str, object],
        plan_payload: dict[str, object],
        revision_notes: list[str],
    ) -> PlanCriticLLMResponse:
        request_payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "selectedRegionId": selected_region_id,
                            "preserveClipId": preserve_clip_id,
                            "userFeedbackMessage": user_feedback_message,
                            "selectionContext": selection_context,
                            "revisionNotes": revision_notes,
                            "region": region,
                            "planPayload": plan_payload,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "system": _critic_system_prompt(),
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": self._anthropic_version,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(self._base_url, headers=headers, json=request_payload)
        except httpx.TimeoutException as exc:
            raise PlanCriticLLMError(
                "PLAN_CRITIC_TIMEOUT",
                "Timed out while waiting for the plan critic service.",
            ) from exc
        except httpx.HTTPError as exc:
            raise PlanCriticLLMError(
                "PLAN_CRITIC_REQUEST_FAILED",
                "Failed to reach the plan critic service.",
            ) from exc

        if response.status_code >= 500:
            raise PlanCriticLLMError(
                "PLAN_CRITIC_SERVER_ERROR",
                f"Plan critic service returned {response.status_code}.",
            )
        if response.status_code >= 400:
            raise PlanCriticLLMError(
                "PLAN_CRITIC_BAD_REQUEST",
                f"Plan critic service rejected the request with {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise PlanCriticLLMError(
                "PLAN_CRITIC_INVALID_RESPONSE",
                "Plan critic service returned a non-JSON response body.",
            ) from exc

        message_content = _extract_anthropic_text(payload)
        response_payload = _parse_json_object(message_content)
        result = _require_string(response_payload, "result").upper()
        if result not in {"PASS", "REVISE", "REJECT"}:
            raise PlanCriticLLMError(
                "PLAN_CRITIC_INVALID_RESPONSE",
                "Plan critic response omitted a supported result field.",
            )
        return PlanCriticLLMResponse(
            result=result,
            note=_require_string(response_payload, "note"),
            raw_text=message_content,
        )


def get_plan_critic_llm_client() -> PlanCriticLLMClient:
    settings = get_settings()
    if not settings.plan_critic_enabled:
        raise PlanCriticLLMError(
            "PLAN_CRITIC_DISABLED",
            "Plan critic LLM is disabled in the current AI server configuration.",
        )
    if not settings.plan_critic_base_url:
        raise PlanCriticLLMError(
            "PLAN_CRITIC_URL_MISSING",
            "Plan critic LLM URL is not configured.",
        )
    if not settings.plan_critic_api_key:
        raise PlanCriticLLMError(
            "PLAN_CRITIC_API_KEY_MISSING",
            "Plan critic LLM API key is not configured.",
        )
    return HTTPPlanCriticLLMClient(
        base_url=settings.plan_critic_base_url,
        api_key=settings.plan_critic_api_key,
        model=settings.plan_critic_model,
        anthropic_version=settings.plan_critic_anthropic_version,
        max_tokens=settings.plan_critic_max_tokens,
        timeout_seconds=settings.plan_critic_timeout_seconds,
        connect_timeout_seconds=settings.plan_critic_connect_timeout_seconds,
    )


def _critic_system_prompt() -> str:
    return (
        "Review the proposed EQ-only audio-fix plan and return only a JSON object. "
        'Use this schema: {"result":"PASS|REVISE|REJECT","note":"string"}. '
        "Primary role: protect user intent and preserve-track safety without destabilizing an otherwise valid plan. "
        "Prefer PASS when the plan is already safe, targeted, and aligned with the user request. "
        "Use REVISE only for narrow corrections. Use REJECT only for clear policy or safety violations. "
        "Hard rejection rules: reject plans that modify the preserved track or preserved clip, use MASTER scope, "
        "use DE_ESSER, GAIN_TRIM, or TRUE_PEAK_LIMITER, violate the EQ-only policy, extend outside the selected region, "
        "or ignore explicit user feedback about which track must remain untouched. "
        "Revision rules: revise plans that are technically valid but too broad, too aggressive, or too loose in time/band range. "
        "If the issue is only range, gain, or overreach, do not ask for an actionType change. "
        "If the plan already has the correct target track, do not ask to change targetTrackId. "
        "Only ask to change actionType when the current actionType is clearly invalid for the issue or clearly contradicts the evidence. "
        "Only ask to change targetTrackId when the current target violates preserve-track safety or clearly conflicts with explicit user feedback. "
        "Selection context may include bandOverlapSubtype and bandFocusLabel; use them to calibrate severity. "
        "For upper_mid_overlap, prefer fairly tight bands and revise plans above -6 dB. "
        "For presence_overlap, be stricter about overreach: prefer narrower bands and revise plans above -4 dB. "
        "If a presence_overlap plan uses a wide band span, prefer REVISE over REJECT on the first pass and ask for a narrower pocket before asking for stronger gain. "
        "When the current presence_overlap band span is roughly 1200 Hz or wider, ask to keep gain around -2.5 dB or lower until the band is narrowed, rather than escalating gain across the full wide band. "
        "For low_mid_overlap, stronger cuts can still be acceptable when the masking is sustained, but do not allow unsafe overreaction. "
        "Action-type stability: words like only, exact, local, pocket, exact phrase, or touch only usually mean tighten time, band, or gain first. "
        "However, if those local-pocket words appear and the selected region itself is a short pocket of about 900 ms or less with a band span of about 700 Hz or less, do not PASS DYNAMIC_EQ by default. Prefer EQ_CUT unless the region still behaves like a sustained phrase. "
        "Do not ask to switch from DYNAMIC_EQ to EQ_CUT unless this is clearly a narrow static masking pocket and the current DYNAMIC_EQ choice itself is the main problem. "
        "If a DYNAMIC_EQ plan can be fixed by narrowing the window or reducing gain, prefer that revision. "
        "Do not false-pass a DYNAMIC_EQ plan when the region is clearly a short static pocket, but require both shape evidence and user wording before asking for EQ_CUT. "
        "If the region still behaves like a phrase-level or sustained overlap, prefer keeping DYNAMIC_EQ and revising only time, band, or gain. "
        "Likewise, do not false-pass an EQ_CUT plan for a broader sustained phrase when the correction should move dynamically through time. "
        "Multi-candidate target guidance: if multiple non-preserve tracks overlap, verify the chosen target against user wording, track names, and strongest masking evidence. "
        "If one layer should remain lively or intact and another should step back, prefer the step-back layer. "
        "When the user is under-specified, keep the strongest non-preserve masking contributor unless there is clear wording to override it. Do not PASS a plausible but weaker alternative target just because it is also non-preserve. "
        "User-intent interpretation: treat preserve-language like do not touch the vocal, keep the dialogue intact, leave the guitar alone, or move the pad back as top-priority constraints. "
        "When the feedback asks to preserve texture, warmth, body, vocal character, dialogue clarity, transient punch, or edge, prefer a narrower and more conservative correction. "
        "If revision notes complain about leakage, overreach, or phrase boundaries, and the current action family is otherwise valid, ask for narrower timing or banding rather than switching action type. "
        "If revision notes say exact phrase, phrase boundary, outside the phrase, or before or after it, treat that as a narrow timing correction unless the current action type is explicitly called wrong. "
        "In those exact-phrase cases, prefer notes like Keep current action type and target track. Narrow the time window to the exact phrase pocket only. "
        "Note-writing rules: keep the note short and actionable. Explicitly say what must stay fixed and what should change. Avoid vague notes that could trigger a full redesign."
    )


def _extract_anthropic_text(payload: dict[str, object]) -> str:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        raise PlanCriticLLMError(
            "PLAN_CRITIC_INVALID_RESPONSE",
            "Plan critic response did not include a valid content list.",
        )
    text_chunks: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            text_chunks.append(item["text"])
    if not text_chunks:
        raise PlanCriticLLMError(
            "PLAN_CRITIC_INVALID_RESPONSE",
            "Plan critic response omitted readable text content.",
        )
    return "".join(text_chunks)


def _parse_json_object(content: str) -> dict[str, object]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PlanCriticLLMError(
            "PLAN_CRITIC_INVALID_RESPONSE",
            "Plan critic response was not valid JSON content.",
        ) from exc
    if not isinstance(parsed, dict):
        raise PlanCriticLLMError(
            "PLAN_CRITIC_INVALID_RESPONSE",
            "Plan critic response JSON was not an object.",
        )
    return parsed


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlanCriticLLMError(
            "PLAN_CRITIC_INVALID_RESPONSE",
            f"Plan critic response omitted a valid {key} field.",
        )
    return value.strip()
