from __future__ import annotations

import json
from pathlib import Path

from backend.services.mcp_diagnostics.models import DiagnosticsReport
from backend.services.mcp_diagnostics.sanitizer import sanitize_value


def sanitized_report_dict(report: DiagnosticsReport) -> dict[str, object]:
    value = sanitize_value(report.as_dict())
    if not isinstance(value, dict):
        raise TypeError("Sanitized report must be a mapping.")
    return value


def render_markdown(report: DiagnosticsReport) -> str:
    value = sanitized_report_dict(report)
    connection = value["connection"]
    schema = value["schema"]
    vectors = value["vector_indexes"]
    workspace = value["workspace_safety"]
    weak = value["weak_topic_query"]
    plans = value["query_plans"]
    assert isinstance(connection, dict)
    assert isinstance(schema, dict)
    assert isinstance(vectors, dict)
    assert isinstance(workspace, dict)
    assert isinstance(weak, dict)
    assert isinstance(plans, list)

    lines = [
        "# Agentbook CockroachDB MCP Diagnostics",
        "",
        "## Overall status",
        "",
        f"**{value['overall_status']}**",
        "",
        "## MCP connectivity",
        "",
        f"**{connection['status']}** — {connection['finding']}",
        "",
        "## Required schema",
        "",
        f"**{schema['status']}** — {schema['finding']}",
        "",
        "## Distributed vector indexes",
        "",
        f"**{vectors['status']}** — {vectors['finding']}",
        "",
        "## Workspace-safe query validation",
        "",
        f"**{workspace['status']}** — {workspace['finding']}",
        "",
        "## Weak-topic query",
        "",
        f"**{weak['status']}** — {weak['finding']}",
        "",
        "## Query-plan findings",
        "",
    ]
    for plan in plans:
        assert isinstance(plan, dict)
        lines.append(
            f"- **{plan['name']} — {plan['status']}**: {plan['finding']}"
        )
    lines.extend(
        [
            "",
            "## Privacy boundary",
            "",
            str(value["privacy_boundary"]),
            "",
            "## Limitations",
            "",
        ]
    )
    for limitation in value["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def write_reports(
    report: DiagnosticsReport,
    output_directory: Path,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "latest-report.json"
    markdown_path = output_directory / "latest-report.md"
    safe = sanitized_report_dict(report)
    json_path.write_text(
        json.dumps(safe, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
