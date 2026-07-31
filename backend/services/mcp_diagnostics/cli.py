from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from backend.services.mcp_diagnostics.diagnostics import McpDiagnosticsService
from backend.services.mcp_diagnostics.models import (
    DiagnosticOperation,
    DiagnosticStatus,
)
from backend.services.mcp_diagnostics.report import write_reports


EXIT_CODES = {
    DiagnosticStatus.PASSED: 0,
    DiagnosticStatus.WARNING: 1,
    DiagnosticStatus.FAILED: 2,
    DiagnosticStatus.UNAVAILABLE: 3,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.services.mcp_diagnostics.cli",
        description=(
            "Run fixed, read-only, sanitized CockroachDB Managed MCP diagnostics."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check",
        help="Run the fixed full diagnostics operation.",
    )
    check.add_argument(
        "--output-dir",
        default="artifacts/mcp-diagnostics",
        help="Ignored destination for sanitized live reports.",
    )
    return parser


def run_check(
    *,
    service: McpDiagnosticsService | None = None,
    output_directory: Path = Path("artifacts/mcp-diagnostics"),
) -> int:
    resolved = service or McpDiagnosticsService()
    report = resolved.run(DiagnosticOperation.RUN_FULL_DIAGNOSTICS)
    json_path, markdown_path = write_reports(report, output_directory)
    print(f"Overall status: {report.overall_status.value}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(report.privacy_boundary)
    return EXIT_CODES[report.overall_status]


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "check":
        return run_check(output_directory=Path(arguments.output_dir))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
