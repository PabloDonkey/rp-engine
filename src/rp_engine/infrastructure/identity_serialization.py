"""Shared (de)serialization helpers for user/group identity storage.

Both the JSON and PostgreSQL identity stores use these so identity metadata is
normalized identically regardless of backend.
"""

from typing import Any


def normalize_identity_metadata(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {
        key: value for key, value in data.items() if isinstance(key, str) and isinstance(value, str)
    }


def identity_from_payload(data: dict[str, Any]) -> tuple[str, dict[str, str]] | None:
    external_id = data.get("external_id")
    if not isinstance(external_id, str):
        return None
    return external_id, normalize_identity_metadata(data.get("metadata", {}))
