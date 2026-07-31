from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Sequence

from ops.reliability_agent.collectors import (
    AuthenticationRequired,
    NoAccessibleClusters,
    ReliabilityCollector,
    TargetClusterNotConfigured,
    TargetClusterNotFound,
    TargetClusterSelectionFailed,
)
from ops.reliability_agent.command_runner import (
    CCloudExecutionFailure,
    CCloudNotInstalled,
    ReliabilityCommandError,
)
from ops.reliability_agent.models import HealthStatus
from ops.reliability_agent.report_renderer import build_report, write_reports
from ops.reliability_agent.sanitizer import sanitize_text


EXIT_CODES = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.WARNING: 1,
    HealthStatus.CRITICAL: 2,
    HealthStatus.UNKNOWN: 3,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ops.reliability_agent.cli",
        description=(
            "Run fixed, read-only ccloud infrastructure reliability checks "
            "for one configured Agentbook cluster."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check",
        help="Generate sanitized JSON and Markdown reliability reports.",
    )
    check.add_argument(
        "--output-dir",
        default="artifacts/reliability",
        help="Directory for ignored live reports (default: artifacts/reliability).",
    )
    check.add_argument(
        "--cluster-name",
        metavar="NAME",
        help=(
            "Exact CockroachDB Cloud cluster name. Overrides "
            "AGENTBOOK_CCLOUD_CLUSTER; Cluster IDs and command fragments are rejected."
        ),
    )
    check.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Skip only the local confirmation for an automatically selected "
            "single cluster. Discovery and validation still run."
        ),
    )
    return parser


def run_check(
    *,
    collector: ReliabilityCollector | None = None,
    output_directory: Path = Path("artifacts/reliability"),
    cluster_name: str | None = None,
    yes: bool = False,
    environment: Mapping[str, str] | None = None,
    input_function: Callable[[str], str] = input,
) -> int:
    resolved = collector or ReliabilityCollector()
    source_environment = os.environ if environment is None else environment
    if cluster_name is not None:
        target = cluster_name
    elif "AGENTBOOK_CCLOUD_CLUSTER" in source_environment:
        target = source_environment["AGENTBOOK_CCLOUD_CLUSTER"]
    else:
        target = None
    try:
        prerequisite = resolved.verify_prerequisites(target)
    except CCloudNotInstalled:
        print(
            "The ccloud executable was not found in this Python process PATH. "
            "Install it manually from Cockroach Labs documentation; "
            "this agent will not install or upgrade it."
        )
        return 3
    except CCloudExecutionFailure:
        print(
            "The ccloud executable was found, but it failed to start. "
            "Check local execute permissions and the ccloud installation."
        )
        return 3
    except AuthenticationRequired:
        print(
            "No valid ccloud session was verified. "
            "Run `ccloud auth login` manually, then retry."
        )
        return 3
    except NoAccessibleClusters:
        print("No accessible CockroachDB Cloud cluster was found.")
        return 3
    except TargetClusterNotConfigured as error:
        print("More than one accessible CockroachDB Cloud cluster was found.")
        print("Available cluster names:")
        for name in error.available_names:
            print(f"- {sanitize_text(name)}")
        print(
            "Set AGENTBOOK_CCLOUD_CLUSTER or pass --cluster-name with one exact "
            "cluster name. Cluster IDs are not accepted."
        )
        return 3
    except TargetClusterNotFound as error:
        print(str(error))
        return 3
    except TargetClusterSelectionFailed:
        print(
            "CockroachDB Cloud cluster selection failed before any "
            "cluster-specific checks ran."
        )
        return 3
    except (ReliabilityCommandError, ValueError) as error:
        print(f"Reliability check could not start safely: {error}")
        return 3

    if prerequisite.auto_selected:
        display_name = sanitize_text(prerequisite.target_cluster)
        print(f"Automatically selected the only accessible cluster: {display_name}")
        if not yes:
            try:
                response = input_function(
                    f"Run live read-only checks against {display_name}? [y/N]: "
                )
            except (EOFError, KeyboardInterrupt):
                response = ""
                print()
            if response.strip().casefold() not in {"y", "yes"}:
                print(
                    "Live checks were cancelled locally; no cluster-specific "
                    "checks were run."
                )
                return 3

    collection = resolved.collect(prerequisite)
    report = build_report(collection)
    json_path, markdown_path = write_reports(report, output_directory)
    print(f"Overall status: {report.overall_status.value}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(report.data_access_statement)
    return EXIT_CODES[report.overall_status]


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "check":
        return run_check(
            output_directory=Path(arguments.output_dir),
            cluster_name=arguments.cluster_name,
            yes=arguments.yes,
        )
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
