from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


REDACTED = "[REDACTED]"
PUBLIC_CLUSTER_NAME = "Agentbook CockroachDB Cluster"

_PATTERNS = (
    re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:postgres|postgresql|cockroachdb)://[^\s)\]}>]+", re.IGNORECASE),
    re.compile(r"\bhttps?://[^\s)\]}>]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9.-]+\.cockroachlabs\.cloud(?::\d+)?\b", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*)"),
    re.compile(r"(?<![A-Za-z0-9])/(?:Users|home|root|var|tmp)/[^\s)\]}>]+"),
    re.compile(
        r"\b(?:sk-(?:or-v1-)?|gsk_|cckey_|api[_-]?key[_:= -]*)"
        r"[A-Za-z0-9._~-]{12,}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{8,}\b", re.IGNORECASE),
)

_HIGH_ENTROPY = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")


def _looks_credential_like(value: str) -> bool:
    if len(value) < 32:
        return False
    classes = sum(
        (
            any(character.islower() for character in value),
            any(character.isupper() for character in value),
            any(character.isdigit() for character in value),
            "_" in value or "-" in value,
        )
    )
    return classes >= 3


def sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in _PATTERNS:
        sanitized = pattern.sub(REDACTED, sanitized)
    sanitized = _HIGH_ENTROPY.sub(
        lambda match: REDACTED if _looks_credential_like(match.group(0)) else match.group(0),
        sanitized,
    )
    return sanitized


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key)
            if normalized_key.lower() in {
                "id",
                "cluster_id",
                "organization_id",
                "backup_id",
                "restore_id",
                "email",
                "connection_url",
                "raw_stdout",
                "raw_stderr",
            }:
                continue
            safe[normalized_key] = sanitize_value(item)
        return safe
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_value(item) for item in value]
    return value
