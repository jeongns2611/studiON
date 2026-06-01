from __future__ import annotations

import hashlib
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

_cache_lock = RLock()


class AudioPathResolutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_clip_audio_path(clip: dict[str, object]) -> str | None:
    direct_path = clip.get("audio_path")
    if isinstance(direct_path, str) and direct_path.strip():
        candidate = Path(direct_path)
        if candidate.exists():
            return str(candidate)

    audio_url = clip.get("audio_url")
    if isinstance(audio_url, str) and audio_url.strip():
        return _resolve_audio_url(audio_url)

    object_key = clip.get("object_key")
    if not isinstance(object_key, str) or not object_key.strip():
        return None

    object_key_path = Path(object_key)
    if object_key_path.exists():
        return str(object_key_path)

    audio_root = get_settings().audio_root
    if audio_root:
        rooted_path = Path(audio_root) / object_key
        if rooted_path.exists():
            return str(rooted_path)
    return None


def _resolve_audio_url(audio_url: str) -> str | None:
    parsed = urlparse(audio_url)
    if parsed.scheme not in {"http", "https"}:
        return None

    settings = get_settings()
    cache_dir = Path(settings.audio_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(parsed.path).suffix or ".bin"
    cache_key = hashlib.sha256(audio_url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}{suffix}"

    with _cache_lock:
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return str(cache_path)

        timeout = httpx.Timeout(
            timeout=settings.audio_download_timeout_seconds,
            connect=settings.audio_download_connect_timeout_seconds,
        )
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(audio_url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AudioPathResolutionError(
                "AUDIO_DOWNLOAD_TIMEOUT",
                f"Timed out while downloading audio source: {audio_url}",
            ) from exc
        except httpx.HTTPError as exc:
            raise AudioPathResolutionError(
                "AUDIO_DOWNLOAD_FAILED",
                f"Failed to download audio source: {audio_url}",
            ) from exc

        if not response.content:
            raise AudioPathResolutionError(
                "AUDIO_DOWNLOAD_EMPTY",
                f"Downloaded audio source was empty: {audio_url}",
            )

        cache_path.write_bytes(response.content)
        return str(cache_path)
