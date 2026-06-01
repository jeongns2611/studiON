import logging

import structlog

from app.core.config import get_settings


def _resolve_log_level(level: str | None = None) -> int:
    raw_level = (level or get_settings().log_level or "INFO").upper()
    return getattr(logging, raw_level, logging.INFO)


def configure_logging(level: str | None = None) -> None:
    resolved_level = _resolve_log_level(level)
    logging.basicConfig(level=resolved_level, format="%(message)s", force=True)
    for noisy_logger_name in (
        "numba",
        "librosa",
        "matplotlib",
        "httpx",
        "httpcore",
        "pymongo",
        "pymongo.topology",
        "pymongo.serverSelection",
        "pymongo.connection",
    ):
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
    )
