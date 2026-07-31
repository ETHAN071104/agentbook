from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


REPORT_VERSION = "1.0"
PRIVACY_BOUNDARY = (
    "No learner content, raw rows, embeddings, credentials, workspace "
    "identifiers, or raw MCP messages are returned by these diagnostics."
)


class DiagnosticOperation(StrEnum):
    CHECK_CONNECTION = "check_connection"
    CHECK_REQUIRED_SCHEMA = "check_required_schema"
    CHECK_VECTOR_INDEXES = "check_vector_indexes"
    CHECK_WORKSPACE_SAFETY = "check_workspace_safety"
    CHECK_WEAK_TOPIC_QUERY = "check_weak_topic_query"
    CHECK_QUERY_PLANS = "check_query_plans"
    RUN_FULL_DIAGNOSTICS = "run_full_diagnostics"


class DiagnosticStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


STATUS_SEVERITY = {
    DiagnosticStatus.PASSED: 0,
    DiagnosticStatus.WARNING: 1,
    DiagnosticStatus.FAILED: 2,
    DiagnosticStatus.UNAVAILABLE: 3,
}


@dataclass(frozen=True)
class DiagnosticCheck:
    status: DiagnosticStatus
    title: str
    finding: str
    evidence_category: str
    recommended_action: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryPlanFinding:
    name: str
    status: DiagnosticStatus
    workspace_predicate_present: bool
    bounded_limit_present: bool
    index_reference_detected: bool
    full_scan_observed: bool
    finding: str


@dataclass(frozen=True)
class DiagnosticsReport:
    report_version: str
    generated_at: str
    overall_status: DiagnosticStatus
    connection: DiagnosticCheck
    schema: DiagnosticCheck
    vector_indexes: DiagnosticCheck
    workspace_safety: DiagnosticCheck
    weak_topic_query: DiagnosticCheck
    query_plans: tuple[QueryPlanFinding, ...]
    privacy_boundary: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
