from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ops.reliability_agent.command_runner import validate_cluster_name
from ops.reliability_agent.models import (
    BackupHealthInput,
    ClusterHealthInput,
    RestoreHealthInput,
    VersionHealthInput,
)


class OutputParseError(ValueError):
    pass


_PROGRESS_PREFIXES = ("...", "∙∙∙", "retrieving ", "loading ")
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%SZ",
    "%Y-%m-%d",
)


def _non_progress_lines(output: str) -> list[str]:
    lines: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if not line or any(lowered.startswith(prefix) for prefix in _PROGRESS_PREFIXES):
            continue
        lines.append(line)
    return lines


def _json_value(output: str) -> Any | None:
    cleaned = output.strip()
    if not cleaned or cleaned[0] not in "[{":
        return None
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise OutputParseError("Malformed JSON output.") from error


def _parse_time(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "N/A", "UNKNOWN"}:
        return None
    normalized = text.replace(" UTC", "+0000")
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)
    except ValueError:
        pass
    for pattern in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(normalized, pattern)
            return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)
        except ValueError:
            continue
    return None


def _key_values(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _non_progress_lines(output):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        if normalized:
            values[normalized] = value.strip()
    return values


def _first(mapping: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _record_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("items", "clusters", "backups", "restores", "versions"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def parse_cli_version(output: str) -> str:
    lines = _non_progress_lines(output)
    if not lines:
        raise OutputParseError("The ccloud version output was empty.")
    match = re.search(r"\bv?\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9.-]+)?\b", " ".join(lines))
    if not match:
        raise OutputParseError("The ccloud version could not be parsed.")
    return match.group(0)


def parse_cluster_names(output: str) -> tuple[str, ...]:
    json_value = _json_value(output)
    names: list[str] = []
    had_candidate_records = False
    if json_value is not None:
        if isinstance(json_value, list):
            records = [item for item in json_value if isinstance(item, dict)]
        elif isinstance(json_value, dict):
            records = []
            recognized = False
            for key in ("items", "clusters"):
                if key not in json_value:
                    continue
                recognized = True
                nested = json_value[key]
                if not isinstance(nested, list):
                    raise OutputParseError(
                        "The cluster-list JSON shape was not recognized."
                    )
                records = [item for item in nested if isinstance(item, dict)]
                break
            if not recognized:
                raise OutputParseError(
                    "The cluster-list JSON shape was not recognized."
                )
        else:
            raise OutputParseError("The cluster-list JSON shape was not recognized.")
        had_candidate_records = bool(records)
        for record in records:
            name = _first(record, "name", "cluster_name")
            if isinstance(name, str):
                try:
                    names.append(validate_cluster_name(name))
                except ValueError:
                    continue
    else:
        lines = _non_progress_lines(output)
        header_index = next(
            (index for index, line in enumerate(lines) if line.upper().startswith("NAME")),
            None,
        )
        if header_index is None:
            if any("no cluster" in line.lower() for line in lines):
                return ()
            raise OutputParseError("The cluster-list header was not recognized.")
        data_lines = lines[header_index + 1 :]
        if any("no cluster" in line.lower() for line in data_lines):
            return ()
        had_candidate_records = bool(data_lines)
        for line in data_lines:
            candidate = re.split(r"\s{2,}|\t+", line, maxsplit=1)[0].strip()
            if not candidate:
                continue
            try:
                names.append(validate_cluster_name(candidate))
            except ValueError:
                continue
    unique = tuple(dict.fromkeys(names))
    if had_candidate_records and not unique:
        raise OutputParseError("No valid cluster names were present.")
    return unique


def parse_cluster_info(
    output: str,
    *,
    collected_at: datetime,
) -> ClusterHealthInput:
    json_value = _json_value(output)
    if isinstance(json_value, dict):
        source = json_value.get("cluster", json_value)
        if not isinstance(source, dict):
            raise OutputParseError("The cluster-info JSON shape was not recognized.")
    else:
        source = _key_values(output)
    state = _first(source, "state", "cluster_state", "status")
    if state is None:
        raise OutputParseError("Cluster state was missing.")
    regions_value = _first(source, "regions", "region")
    if isinstance(regions_value, list):
        regions = tuple(str(item).strip() for item in regions_value if str(item).strip())
    else:
        regions = tuple(
            part.strip()
            for part in re.split(r"[,;]", str(regions_value or ""))
            if part.strip()
        )
    hardware_parts = [
        _first(source, "resource_limit", "spend_limit", "storage_gib"),
        _first(source, "node_hardware", "vcpu", "vcpus", "nodes"),
    ]
    hardware = "; ".join(str(item) for item in hardware_parts if item not in (None, ""))
    return ClusterHealthInput(
        state=str(state).strip(),
        plan_type=(
            str(_first(source, "plan_type", "plan", "cluster_plan")).strip()
            if _first(source, "plan_type", "plan", "cluster_plan") is not None
            else None
        ),
        cloud_provider=(
            str(_first(source, "cloud_provider", "cloud", "provider")).strip()
            if _first(source, "cloud_provider", "cloud", "provider") is not None
            else None
        ),
        regions=regions,
        cockroachdb_version=(
            str(_first(source, "version", "cockroachdb_version")).strip()
            if _first(source, "version", "cockroachdb_version") is not None
            else None
        ),
        resource_limit_or_hardware=hardware or None,
        collected_at=collected_at,
    )


def parse_backup_config(output: str) -> tuple[bool | None, int | None, int | None]:
    json_value = _json_value(output)
    source = json_value if isinstance(json_value, dict) else _key_values(output)
    if not isinstance(source, dict):
        raise OutputParseError("The backup configuration shape was not recognized.")
    enabled_value = _first(source, "backups_enabled", "enabled")
    enabled: bool | None
    if isinstance(enabled_value, bool):
        enabled = enabled_value
    elif enabled_value is None:
        enabled = None
    else:
        lowered = str(enabled_value).strip().lower()
        if lowered in {"yes", "true", "enabled", "on"}:
            enabled = True
        elif lowered in {"no", "false", "disabled", "off"}:
            enabled = False
        else:
            enabled = None
    frequency_value = _first(source, "frequency_minutes", "frequency")
    retention_value = _first(source, "retention_days", "retention")
    frequency_match = re.search(r"\d+", str(frequency_value or ""))
    retention_match = re.search(r"\d+", str(retention_value or ""))
    frequency = int(frequency_match.group(0)) if frequency_match else None
    retention = int(retention_match.group(0)) if retention_match else None
    if enabled is None and frequency is None and retention is None:
        raise OutputParseError("Backup configuration fields were missing.")
    return enabled, frequency, retention


@dataclass(frozen=True)
class _BackupRecord:
    observed_at: datetime
    status: str | None


def _backup_records(output: str) -> list[_BackupRecord]:
    json_value = _json_value(output)
    records: list[_BackupRecord] = []
    if json_value is not None:
        for item in _record_list(json_value):
            observed = _parse_time(
                _first(item, "as_of_time", "created_at", "timestamp", "time")
            )
            if observed is not None:
                status = _first(item, "status", "state")
                records.append(
                    _BackupRecord(
                        observed_at=observed,
                        status=str(status).strip() if status is not None else None,
                    )
                )
        return records
    lines = _non_progress_lines(output)
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "BACKUP ID" in line.upper() and ("TIME" in line.upper() or "CREATED" in line.upper())
        ),
        None,
    )
    if header_index is None:
        if any("no backup" in line.lower() for line in lines):
            return []
        raise OutputParseError("The backup-list header was not recognized.")
    for line in lines[header_index + 1 :]:
        time_match = re.search(
            r"\d{4}-\d{2}-\d{2}(?:T|\s)\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\s[+-]\d{4}|\sUTC)?",
            line,
        )
        if not time_match:
            continue
        observed = _parse_time(time_match.group(0))
        if observed is None:
            continue
        status_match = re.search(
            r"\b(COMPLETE|COMPLETED|SUCCESS|FAILED|PENDING|IN_PROGRESS)\b",
            line,
            re.IGNORECASE,
        )
        records.append(
            _BackupRecord(
                observed_at=observed,
                status=status_match.group(1).upper() if status_match else None,
            )
        )
    return records


def parse_backup_health(
    config_output: str,
    backups_output: str,
    *,
    collected_at: datetime,
) -> BackupHealthInput:
    enabled, frequency, retention = parse_backup_config(config_output)
    records = _backup_records(backups_output)
    latest = max(records, key=lambda item: item.observed_at) if records else None
    return BackupHealthInput(
        enabled=enabled,
        frequency_minutes=frequency,
        retention_days=retention,
        latest_backup_time=latest.observed_at if latest else None,
        latest_backup_status=latest.status if latest else None,
        backup_count_observed=len(records),
        collected_at=collected_at,
    )


@dataclass(frozen=True)
class _RestoreRecord:
    status: str
    created_at: datetime | None


def _restore_records(output: str) -> list[_RestoreRecord]:
    json_value = _json_value(output)
    records: list[_RestoreRecord] = []
    if json_value is not None:
        for item in _record_list(json_value):
            status = _first(item, "status", "state")
            if status is None:
                continue
            records.append(
                _RestoreRecord(
                    status=str(status).strip().upper(),
                    created_at=_parse_time(
                        _first(item, "created_at", "started_at", "timestamp")
                    ),
                )
            )
        return records
    lines = _non_progress_lines(output)
    if any("no restore" in line.lower() for line in lines):
        return []
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.upper().startswith("ID") and "STATUS" in line.upper()
        ),
        None,
    )
    if header_index is None:
        raise OutputParseError("The restore-list header was not recognized.")
    for line in lines[header_index + 1 :]:
        status_match = re.search(
            r"\b(SUCCESS|SUCCEEDED|COMPLETE|COMPLETED|FAILED|ERROR|PENDING|"
            r"IN_PROGRESS|RUNNING|INCOMPLETE|CANCELLED)\b",
            line,
            re.IGNORECASE,
        )
        if not status_match:
            continue
        time_match = re.search(
            r"\d{4}-\d{2}-\d{2}(?:T|\s)\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\s[+-]\d{4}|\sUTC)?",
            line,
        )
        records.append(
            _RestoreRecord(
                status=status_match.group(1).upper(),
                created_at=_parse_time(time_match.group(0)) if time_match else None,
            )
        )
    return records


def parse_restore_health(
    output: str,
    *,
    collected_at: datetime,
) -> RestoreHealthInput:
    records = _restore_records(output)
    failed_states = {"FAILED", "ERROR", "CANCELLED"}
    pending_states = {"PENDING", "IN_PROGRESS", "RUNNING"}
    incomplete_states = {"INCOMPLETE"}
    failed = [item for item in records if item.status in failed_states]
    pending = [item for item in records if item.status in pending_states]
    incomplete = [item for item in records if item.status in incomplete_states]
    dated = [item for item in records if item.created_at is not None]
    latest = max(dated, key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC)) if dated else None
    open_dated = [
        item
        for item in (*pending, *incomplete)
        if item.created_at is not None
    ]
    oldest_open = (
        min(open_dated, key=lambda item: item.created_at or collected_at)
        if open_dated
        else None
    )
    return RestoreHealthInput(
        total_restore_count=len(records),
        failed_count=len(failed),
        pending_count=len(pending),
        incomplete_count=len(incomplete),
        latest_restore_time=latest.created_at if latest else None,
        latest_restore_status=latest.status if latest else None,
        oldest_open_restore_time=oldest_open.created_at if oldest_open else None,
        collected_at=collected_at,
    )


def _major_version(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"v?(\d+\.\d+)", value, re.IGNORECASE)
    return f"v{match.group(1)}" if match else None


def parse_version_health(
    output: str,
    *,
    running_version: str | None,
    collected_at: datetime,
) -> VersionHealthInput:
    running_major = _major_version(running_version)
    if running_major is None:
        return VersionHealthInput(
            running_major_version=None,
            support_status=None,
            support_end=None,
            allowed_upgrade_targets=(),
            collected_at=collected_at,
        )
    json_value = _json_value(output)
    rows: list[dict[str, Any]] = []
    if json_value is not None:
        rows = _record_list(json_value)
    else:
        lines = _non_progress_lines(output)
        header_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.upper().startswith("VERSION") and "SUPPORT STATUS" in line.upper()
            ),
            None,
        )
        if header_index is None:
            raise OutputParseError("The versions-list header was not recognized.")
        for line in lines[header_index + 1 :]:
            version_match = re.match(r"(v?\d+\.\d+)\s+", line, re.IGNORECASE)
            status_match = re.search(
                r"\b(SUPPORTED|UNSUPPORTED|DEPRECATED|EOL|END_OF_LIFE)\b",
                line,
                re.IGNORECASE,
            )
            if not version_match or not status_match:
                continue
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", line)
            tail = line[status_match.end() :]
            upgrades = tuple(
                dict.fromkeys(
                    f"v{match}"
                    for match in re.findall(r"v?(\d+\.\d+)", tail, re.IGNORECASE)
                    if f"v{match}" != running_major
                )
            )
            rows.append(
                {
                    "version": version_match.group(1),
                    "support_status": status_match.group(1),
                    "support_end": dates[0] if dates else None,
                    "allowed_upgrades": upgrades,
                }
            )
    for row in rows:
        version = _major_version(
            str(_first(row, "version", "major_version") or "")
        )
        if version != running_major:
            continue
        status = _first(row, "support_status", "status")
        support_end = _parse_time(_first(row, "support_end", "support_end_date"))
        upgrades_value = _first(
            row,
            "allowed_upgrades",
            "allowed_upgrade_targets",
            "upgrade_targets",
        )
        if isinstance(upgrades_value, (list, tuple)):
            upgrades = tuple(
                value
                for item in upgrades_value
                if (value := _major_version(str(item))) is not None
            )
        else:
            upgrades = tuple(
                value
                for item in re.split(r"[, ]+", str(upgrades_value or ""))
                if (value := _major_version(item)) is not None
            )
        return VersionHealthInput(
            running_major_version=running_major,
            support_status=str(status).upper() if status is not None else None,
            support_end=support_end,
            allowed_upgrade_targets=tuple(dict.fromkeys(upgrades)),
            collected_at=collected_at,
        )
    return VersionHealthInput(
        running_major_version=running_major,
        support_status=None,
        support_end=None,
        allowed_upgrade_targets=(),
        collected_at=collected_at,
    )
