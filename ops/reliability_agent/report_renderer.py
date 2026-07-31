from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ops.reliability_agent.health_rules import (
    evaluate_backup_configuration,
    evaluate_backup_freshness,
    evaluate_cluster,
    evaluate_restores,
    evaluate_version,
    overall_status,
)
from ops.reliability_agent.models import (
    CollectionResult,
    HealthStatus,
    Operation,
    ReliabilityReport,
)
from ops.reliability_agent.sanitizer import (
    PUBLIC_CLUSTER_NAME,
    sanitize_text,
    sanitize_value,
)


REPORT_VERSION = "1.0"
DATA_ACCESS_STATEMENT = (
    "No learner documents, quiz responses, memories, tasks, embeddings, "
    "or SQL rows were accessed during this check."
)

_COMMAND_LABELS: dict[Operation, str] = {
    Operation.GET_CLI_VERSION: "Check ccloud CLI version",
    Operation.GET_AUTHENTICATED_IDENTITY_STATUS: "Verify ccloud authentication status",
    Operation.LIST_CLUSTERS: "Validate configured target cluster",
    Operation.GET_CLUSTER_INFO: "Inspect cluster availability and configuration",
    Operation.GET_BACKUP_CONFIG: "Inspect managed backup configuration",
    Operation.LIST_BACKUPS: "Inspect managed backup freshness",
    Operation.LIST_RESTORES: "Inspect restore-operation status",
    Operation.LIST_SUPPORTED_VERSIONS: "Inspect CockroachDB version support",
}


def build_report(
    collection: CollectionResult,
    *,
    generated_at: datetime | None = None,
) -> ReliabilityReport:
    now = (generated_at or datetime.now(UTC)).astimezone(UTC)
    checks = (
        evaluate_cluster(collection.cluster),
        evaluate_backup_configuration(collection.backup),
        evaluate_backup_freshness(collection.backup, now=now),
        evaluate_restores(collection.restore, now=now),
        evaluate_version(collection.version, now=now),
    )
    warnings = tuple(
        check.summary
        for check in checks
        if check.status is not HealthStatus.HEALTHY
    )
    actions = tuple(
        dict.fromkeys(
            check.recommended_action
            for check in checks
            if check.recommended_action
        )
    )
    labels = tuple(
        dict.fromkeys(_COMMAND_LABELS[operation] for operation in collection.commands_used)
    )
    return ReliabilityReport(
        report_version=REPORT_VERSION,
        generated_at=now,
        cluster_display_name=PUBLIC_CLUSTER_NAME,
        overall_status=overall_status(checks),
        checks=checks,
        warnings=warnings,
        recommended_actions=actions,
        data_access_statement=DATA_ACCESS_STATEMENT,
        commands_used=labels,
        limitations=collection.limitations,
    )


def report_json_dict(report: ReliabilityReport) -> dict[str, Any]:
    return sanitize_value(report.to_dict())


def render_json(report: ReliabilityReport) -> str:
    return json.dumps(report_json_dict(report), indent=2, sort_keys=True) + "\n"


def _display(value: Any) -> str:
    if value is None:
        return "Not exposed"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "None"
    return sanitize_text(str(value))


def _detail_label(key: str) -> str:
    overrides = {
        "cockroachdb_version": "CockroachDB Version",
        "resource_limit_or_hardware": "Resource Limit or Hardware",
    }
    return overrides.get(key, key.replace("_", " ").title())


def render_markdown(report: ReliabilityReport) -> str:
    payload = report_json_dict(report)
    checks = {item["key"]: item for item in payload["checks"]}
    lines = [
        "# Agentbook Infrastructure Reliability Report",
        "",
        f"**Overall status: {payload['overall_status'].upper()}**",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        f"Target: **{payload['cluster_display_name']}**",
        "",
    ]

    def section(title: str, key: str, detail_keys: tuple[str, ...]) -> None:
        check = checks[key]
        lines.extend(
            [
                f"## {title}",
                "",
                f"**Status: {str(check['status']).upper()}**",
                "",
                str(check["summary"]),
                "",
            ]
        )
        details = check.get("details", {})
        for detail_key in detail_keys:
            if detail_key in details:
                label = _detail_label(detail_key)
                lines.append(f"- {label}: {_display(details[detail_key])}")
        if detail_keys:
            lines.append("")

    section(
        "Cluster availability",
        "cluster_availability",
        (
            "state",
            "plan_type",
            "cloud_provider",
            "regions",
            "cockroachdb_version",
            "resource_limit_or_hardware",
        ),
    )
    section(
        "Managed backup configuration",
        "managed_backup_configuration",
        ("enabled", "frequency_minutes", "retention_days"),
    )
    section(
        "Backup freshness",
        "backup_freshness",
        (
            "latest_backup_time",
            "latest_backup_status",
            "backup_count_observed",
            "age_minutes",
            "freshness_tolerance_minutes",
        ),
    )
    section(
        "Restore status",
        "restore_status",
        (
            "total_restore_count",
            "failed_count",
            "pending_count",
            "incomplete_count",
            "latest_restore_time",
            "latest_restore_status",
        ),
    )
    section(
        "Version support",
        "version_support",
        (
            "running_major_version",
            "support_status",
            "support_end",
            "support_days_remaining",
            "allowed_upgrade_targets",
        ),
    )
    lines.extend(["## Warnings and recommended actions", ""])
    if payload["warnings"]:
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    else:
        lines.append("- No deterministic warning was produced.")
    if payload["recommended_actions"]:
        lines.append("")
        lines.append("Recommended administrator actions:")
        lines.append("")
        lines.extend(f"- {action}" for action in payload["recommended_actions"])
    lines.extend(
        [
            "",
            "## Privacy boundary",
            "",
            payload["data_access_statement"],
            "",
            "The agent used only fixed, read-only CockroachDB Cloud infrastructure "
            "operations. It did not use SQL, a database URL, or learner credentials.",
            "",
            "## Commands used",
            "",
        ]
    )
    lines.extend(f"- {label}" for label in payload["commands_used"])
    lines.extend(["", "## Collection limitations", ""])
    if payload["limitations"]:
        lines.extend(f"- {item}" for item in payload["limitations"])
    else:
        lines.append(
            "- Managed backups were observed and no failed restore record was found. "
            "This does not prove backup recoverability."
        )
    return "\n".join(lines).rstrip() + "\n"


def write_reports(
    report: ReliabilityReport,
    output_directory: Path,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "latest-report.json"
    markdown_path = output_directory / "latest-report.md"
    json_path.write_text(render_json(report), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
