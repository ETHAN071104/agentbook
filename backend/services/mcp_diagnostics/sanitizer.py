from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL = re.compile(r"\b(?:postgres(?:ql)?|https?)://[^\s<>]+", re.IGNORECASE)
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")
_POSIX_PATH = re.compile(r"(?<!\w)/(?:home|Users|tmp|var|opt)/[^\s<>]+")
_TOKEN = re.compile(
    r"\b(?:Bearer\s+[A-Za-z0-9._~-]{16,}|"
    r"sk-[A-Za-z0-9_-]{12,}|"
    r"[A-Za-z0-9_-]{32,}\.[A-Za-z0-9._-]{12,})\b",
    re.IGNORECASE,
)
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "bearer_token",
    "cluster_id",
    "connection_string",
    "database_url",
    "document_id",
    "guest_token",
    "notebook_id",
    "oauth_token",
    "organization_id",
    "password",
    "sql_url",
    "task_id",
    "token",
    "workspace_id",
}


def sanitize_text(value: str) -> str:
    cleaned = _URL.sub("[redacted-url]", value)
    cleaned = _EMAIL.sub("[redacted-email]", cleaned)
    cleaned = _UUID.sub("[redacted-id]", cleaned)
    cleaned = _WINDOWS_PATH.sub("[redacted-path]", cleaned)
    cleaned = _POSIX_PATH.sub("[redacted-path]", cleaned)
    cleaned = _TOKEN.sub("[redacted-token]", cleaned)
    return cleaned


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in _SENSITIVE_KEYS or normalized.endswith("_secret"):
                output[str(key)] = "[redacted]"
            else:
                output[str(key)] = sanitize_value(item)
        return output
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_value(item) for item in value]
    return value
