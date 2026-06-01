from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings


class CLAPInferenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CLAPExcerptPayload:
    filename: str
    audio_bytes: bytes
    metadata: dict[str, object]


@dataclass(frozen=True)
class CLAPTrackPrediction:
    track_id: int
    vocal_score: float
    confidence: float | None
    predicted_role: str
    excerpt_scores: list[dict[str, object]]


class CLAPInferenceClient(Protocol):
    def infer_track_roles(
        self,
        *,
        job_id: int,
        excerpts: list[CLAPExcerptPayload],
    ) -> list[CLAPTrackPrediction]: ...


class HTTPCLAPInferenceClient:
    def __init__(
        self,
        *,
        inference_url: str,
        timeout_seconds: float,
        connect_timeout_seconds: float,
    ) -> None:
        self._inference_url = inference_url.rstrip("/")
        self._timeout = httpx.Timeout(
            timeout=timeout_seconds,
            connect=connect_timeout_seconds,
        )

    def infer_track_roles(
        self,
        *,
        job_id: int,
        excerpts: list[CLAPExcerptPayload],
    ) -> list[CLAPTrackPrediction]:
        if not excerpts:
            return []

        files: list[tuple[str, tuple[str | None, bytes | str, str]]] = []
        for excerpt in excerpts:
            files.append(
                (
                    "audio_files",
                    (excerpt.filename, excerpt.audio_bytes, "audio/wav"),
                )
            )
        files.append(
            (
                "metadata",
                (
                    None,
                    json.dumps(
                        {
                            "job_id": job_id,
                            "excerpts": [excerpt.metadata for excerpt in excerpts],
                        }
                    ),
                    "application/json",
                ),
            )
        )

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(f"{self._inference_url}/infer-track-roles", files=files)
        except httpx.TimeoutException as exc:
            raise CLAPInferenceError(
                "CLAP_INFERENCE_TIMEOUT",
                "Timed out while waiting for the CLAP inference service.",
            ) from exc
        except httpx.HTTPError as exc:
            raise CLAPInferenceError(
                "CLAP_INFERENCE_REQUEST_FAILED",
                "Failed to reach the CLAP inference service.",
            ) from exc

        if response.status_code >= 500:
            raise CLAPInferenceError(
                "CLAP_INFERENCE_SERVER_ERROR",
                f"CLAP inference service returned {response.status_code}.",
            )
        if response.status_code >= 400:
            raise CLAPInferenceError(
                "CLAP_INFERENCE_BAD_REQUEST",
                f"CLAP inference service rejected the request with {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise CLAPInferenceError(
                "CLAP_INFERENCE_INVALID_RESPONSE",
                "CLAP inference service returned a non-JSON response.",
            ) from exc

        predictions_payload = payload.get("predictions")
        if not isinstance(predictions_payload, list):
            raise CLAPInferenceError(
                "CLAP_INFERENCE_INVALID_RESPONSE",
                "CLAP inference response did not include a valid predictions list.",
            )

        predictions: list[CLAPTrackPrediction] = []
        for item in predictions_payload:
            if not isinstance(item, dict):
                raise CLAPInferenceError(
                    "CLAP_INFERENCE_INVALID_RESPONSE",
                    "CLAP inference response included an invalid prediction item.",
                )
            predicted_role = item.get("predicted_role")
            if predicted_role not in {"vocal-like", "supporting"}:
                raise CLAPInferenceError(
                    "CLAP_INFERENCE_INVALID_RESPONSE",
                    "CLAP inference response included an unsupported predicted_role value.",
                )
            try:
                track_id = int(item["track_id"])
                vocal_score = float(item["vocal_score"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CLAPInferenceError(
                    "CLAP_INFERENCE_INVALID_RESPONSE",
                    "CLAP inference response omitted a valid track_id or vocal_score.",
                ) from exc

            confidence_value = item.get("confidence")
            confidence = float(confidence_value) if confidence_value is not None else None
            excerpt_scores = item.get("excerpt_scores")
            if excerpt_scores is None:
                excerpt_scores = []
            if not isinstance(excerpt_scores, list):
                raise CLAPInferenceError(
                    "CLAP_INFERENCE_INVALID_RESPONSE",
                    "CLAP inference response included invalid excerpt_scores.",
                )
            predictions.append(
                CLAPTrackPrediction(
                    track_id=track_id,
                    vocal_score=vocal_score,
                    confidence=confidence,
                    predicted_role=predicted_role,
                    excerpt_scores=excerpt_scores,
                )
            )
        return predictions


def get_clap_inference_client() -> CLAPInferenceClient:
    settings = get_settings()
    if not settings.clap_enabled:
        raise CLAPInferenceError(
            "CLAP_DISABLED",
            "CLAP inference is disabled in the current AI server configuration.",
        )
    if not settings.clap_inference_url:
        raise CLAPInferenceError(
            "CLAP_INFERENCE_URL_MISSING",
            "CLAP inference URL is not configured.",
        )
    return HTTPCLAPInferenceClient(
        inference_url=settings.clap_inference_url,
        timeout_seconds=settings.clap_timeout_seconds,
        connect_timeout_seconds=settings.clap_connect_timeout_seconds,
    )
