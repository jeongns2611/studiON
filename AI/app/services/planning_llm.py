from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings

ALLOWED_ACTION_TYPES = [
    "EQ_CUT",
    "DYNAMIC_EQ",
]


class PlanningLLMError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PlanningLLMResponse:
    plan_payload: dict[str, object]
    raw_text: str | None = None


class PlanningLLMClient(Protocol):
    def generate_plan(
        self,
        *,
        selected_region_id: int,
        preserve_clip_id: int,
        user_feedback_message: str | None,
        selection_context: dict[str, object],
        region: dict[str, object],
        clip_context: list[dict[str, object]],
        revision_notes: list[str],
    ) -> PlanningLLMResponse: ...


class HTTPPlanningLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        timeout_seconds: float,
        connect_timeout_seconds: float,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._timeout = httpx.Timeout(timeout=timeout_seconds, connect=connect_timeout_seconds)

    def generate_plan(
        self,
        *,
        selected_region_id: int,
        preserve_clip_id: int,
        user_feedback_message: str | None,
        selection_context: dict[str, object],
        region: dict[str, object],
        clip_context: list[dict[str, object]],
        revision_notes: list[str],
    ) -> PlanningLLMResponse:
        request_payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {
                    "role": "developer",
                    "content": _planner_system_prompt(),
                },
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
                            "clipContext": clip_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(self._base_url, headers=headers, json=request_payload)
        except httpx.TimeoutException as exc:
            raise PlanningLLMError(
                "PLANNING_LLM_TIMEOUT",
                "Timed out while waiting for the planning LLM service.",
            ) from exc
        except httpx.HTTPError as exc:
            raise PlanningLLMError(
                "PLANNING_LLM_REQUEST_FAILED",
                "Failed to reach the planning LLM service.",
            ) from exc

        if response.status_code >= 500:
            raise PlanningLLMError(
                "PLANNING_LLM_SERVER_ERROR",
                f"Planning LLM service returned {response.status_code}.",
            )
        if response.status_code >= 400:
            raise PlanningLLMError(
                "PLANNING_LLM_BAD_REQUEST",
                f"Planning LLM service rejected the request with {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise PlanningLLMError(
                "PLANNING_LLM_INVALID_RESPONSE",
                "Planning LLM service returned a non-JSON response body.",
            ) from exc

        message_content = _extract_openai_message_content(payload)
        response_payload = _parse_json_object(message_content)
        _validate_plan_payload_shape(response_payload)
        return PlanningLLMResponse(plan_payload=response_payload, raw_text=message_content)


def get_planning_llm_client() -> PlanningLLMClient:
    settings = get_settings()
    if not settings.planning_llm_enabled:
        raise PlanningLLMError(
            "PLANNING_LLM_DISABLED",
            "Planning LLM is disabled in the current AI server configuration.",
        )
    if not settings.planning_llm_base_url:
        raise PlanningLLMError(
            "PLANNING_LLM_URL_MISSING",
            "Planning LLM URL is not configured.",
        )
    if not settings.planning_llm_api_key:
        raise PlanningLLMError(
            "PLANNING_LLM_API_KEY_MISSING",
            "Planning LLM API key is not configured.",
        )
    return HTTPPlanningLLMClient(
        base_url=settings.planning_llm_base_url,
        api_key=settings.planning_llm_api_key,
        model=settings.planning_llm_model,
        temperature=settings.planning_llm_temperature,
        timeout_seconds=settings.planning_llm_timeout_seconds,
        connect_timeout_seconds=settings.planning_llm_connect_timeout_seconds,
    )


def _planner_system_prompt() -> str:
    return (
        "You are generating one safe EQ-only correction plan for an audio workflow. "
        "Return only a JSON object and do not add markdown or commentary. "
        "Use the selected region, preserve clip, selection context, clip context, and revision notes exactly as given. "
        "Use this exact JSON shape: "
        '{"strategyTitle": string, "strategySummary": string, '
        '"summary": string, "explanation": string, '
        '"candidate": {"action": {"actionType": string, "targetScope": "TRACK", '
        '"targetTrackId": number|null, "targetClipId": number|null, "startMs": number|null, '
        '"endMs": number|null, "bandLowHz": number|null, "bandHighHz": number|null, '
        '"gainDeltaDb": number|null, "params": object}}}. '
        "Core rules: use exactly one action; use only DYNAMIC_EQ or EQ_CUT; use TRACK scope only; "
        "never use DE_ESSER, GAIN_TRIM, TRUE_PEAK_LIMITER, or MASTER scope; never target the preserve clip track; "
        "keep targetClipId null; keep startMs and endMs inside the selected region; keep bandLowHz and bandHighHz inside the selected region band when provided; "
        "keep gainDeltaDb conservative and subtype-aware. "
        "For low_mid_overlap, prefer about -2.5 to -4.5 dB and allow stronger cuts only for clearly sustained masking; never exceed -9 dB. "
        "For body_overlap, prefer about -2.0 to -3.5 dB and keep stronger cuts within -7 dB. "
        "For upper_mid_overlap, prefer about -1.5 to -3.0 dB, keep the band fairly tight, and allow stronger cuts only for clearly sustained masking; never exceed -6 dB. "
        "For presence_overlap, prefer about -1.0 to -2.5 dB, keep the band narrow, and never exceed -4 dB. "
        "For presence_overlap with a wide band span, do not answer user aggressiveness by widening the cut or pushing gain first. Narrow the band first toward the densest pocket, often around 3 to 4.5 kHz when the region evidence supports it. "
        "If a presence_overlap band span is roughly 1200 Hz or wider, keep gainDeltaDb at or below about -2.5 dB until the band has been materially narrowed. "
        "keep the explanation concrete by naming the target track, the band focus, and why the preserve target stays untouched. "
        f"Allowed actionType values: {', '.join(ALLOWED_ACTION_TYPES)}. "
        "Selection context may include bandOverlapSubtype and bandFocusLabel; use them directly when present. "
        "Band-overlap action policy: prefer DYNAMIC_EQ when the overlap is sustained, broader, or dynamic over time. "
        "Prefer EQ_CUT only when the conflict is narrow, static, and a smaller local cut is safer than dynamic control. "
        "For presence_overlap, prefer DYNAMIC_EQ unless the conflict is extremely narrow and static, and avoid broad bands. "
        "Use local or exact wording as supporting evidence for EQ_CUT only when the region is truly a short static pocket. "
        "Do not convert to EQ_CUT from wording alone. The overlap shape in region timing and band span must also support a narrow static fix. "
        "If the overlap duration is around 1200 ms or more, or the band span is around 900 Hz or more, default toward DYNAMIC_EQ even if the user uses local or exact wording. "
        "If the overlap duration is around 900 ms or less and the band span is around 700 Hz or less, EQ_CUT becomes more plausible, but still prefer DYNAMIC_EQ when revision notes emphasize phrase continuity, sustained smoothing, or preserving broader motion through time. "
        "Do not treat words like only, exact, local, or touch only as automatic permission to change a valid DYNAMIC_EQ plan into EQ_CUT. "
        "Use those words mainly to narrow the time window, band range, and gain amount unless the revision note explicitly says the current action type is wrong. "
        "If the issue or band focus is ambiguous, stay conservative and avoid switching to a riskier action type. "
        "Multi-candidate target policy: if multiple non-preserve overlapping tracks are present, choose the non-preserve track that best matches user feedback, track names, and region evidence. "
        "Use user feedback as the first tie-breaker. If the user says one layer should stay lively, intact, or present, do not target that layer first. "
        "If the feedback says a texture, bed, pad, or body layer should step back, prefer that layer over a more transient or leading layer. "
        "When trackBodyContributions shows one non-preserve track has the strongest masking contribution and user feedback does not contradict it, prefer reducing that strongest contributor first. "
        "If user feedback is under-specified and one non-preserve track leads the masking evidence by a meaningful margin, keep that stronger contributor as the first target rather than switching to a merely plausible alternative. "
        "In a three-track overlap, do not default to the first listed non-preserve track. "
        "Revision-note policy: revision notes are narrow corrections, not permission to redesign the whole strategy. "
        "If revision notes mention leakage, range too wide, overreach, or too much collateral change, tighten only the time range, band range, or gain amount. "
        "If revision notes mention the plan was too aggressive, reduce gain and avoid widening the band. "
        "Keep the previous actionType and targetTrackId stable unless the revision note explicitly says the action type is invalid, the wrong track was chosen, or a policy violation occurred. "
        "Do not change both actionType and targetTrackId at the same time unless the revision note explicitly requires both changes. "
        "If the user asks for a local cut, exact pocket, or first local carve, and the selected region is a short pocket of about 900 ms or less with a band span of about 700 Hz or less, prefer EQ_CUT over DYNAMIC_EQ. "
        "Do not keep DYNAMIC_EQ in those short static-pocket cases unless the revision note explicitly says the dynamic behavior itself must be preserved. "
        "If revision notes say exact phrase, phrase boundary, before or after the phrase, or outside the phrase, treat that as a window-tightening request first. Keep the current valid actionType and targetTrackId fixed and narrow only startMs, endMs, bandLowHz, bandHighHz, or gainDeltaDb. "
        "If the current conflict is already a valid broad or sustained DYNAMIC_EQ case, do not convert it to EQ_CUT just because a revision note asks for a narrower fix, exactness, or local handling. Narrow the window first while keeping DYNAMIC_EQ. "
        "If the current conflict is already a valid narrow or static EQ_CUT case, do not convert it to DYNAMIC_EQ unless the revision note explicitly says the static cut choice was wrong. "
        "If the current conflict is already a valid narrow or static EQ_CUT case, do not upgrade it to DYNAMIC_EQ just because the user asks for safety, smoothness, or balance. Keep the cut local and conservative instead. "
        "When revision notes are about leakage, phrase edges, or overreach, keep the current valid action type stable unless the note explicitly says the current action family is wrong. "
        "When user feedback says exact phrase, exact overlap, or do not touch before or after it, do not reinterpret that as permission to switch a valid DYNAMIC_EQ plan into EQ_CUT. Tighten the window first. "
        "Write a short explanation that matches the actual action and the stated user intent."
    )


def _extract_openai_message_content(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response did not include a valid choices list.",
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response included an invalid choice item.",
        )
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response omitted the message payload.",
        )
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_chunks.append(item["text"])
        if text_chunks:
            return "".join(text_chunks)
    raise PlanningLLMError(
        "PLANNING_LLM_INVALID_RESPONSE",
        "Planning LLM response omitted a readable message content field.",
    )


def _parse_json_object(content: str) -> dict[str, object]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response was not valid JSON content.",
        ) from exc
    if not isinstance(parsed, dict):
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response JSON was not an object.",
        )
    return parsed


def _validate_plan_payload_shape(payload: dict[str, object]) -> None:
    for key in ("strategyTitle", "strategySummary", "summary", "explanation"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PlanningLLMError(
                "PLANNING_LLM_INVALID_RESPONSE",
                f"Planning LLM response omitted a valid {key} field.",
            )
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response omitted a valid candidate object.",
        )
    action = candidate.get("action")
    if not isinstance(action, dict):
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response omitted a valid candidate.action object.",
        )
    action_type = action.get("actionType")
    if not isinstance(action_type, str) or action_type not in ALLOWED_ACTION_TYPES:
        raise PlanningLLMError(
            "PLANNING_LLM_INVALID_RESPONSE",
            "Planning LLM response omitted a supported actionType value.",
        )
