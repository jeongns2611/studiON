from __future__ import annotations

from typing import Any


def normalize_mongo_document_keys(value: Any) -> Any:
    # MongoDB 문서는 dict key가 반드시 문자열이어야 하므로 저장 직전에 재귀 정규화한다.
    if isinstance(value, dict):
        return {
            str(key): normalize_mongo_document_keys(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [normalize_mongo_document_keys(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_mongo_document_keys(item) for item in value]
    return value
