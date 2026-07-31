from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.services.mcp_diagnostics.client import (
    ManagedMcpClient,
    McpAuthenticationRequired,
    McpDiagnosticError,
    McpMalformedResponse,
    McpTimeout,
    UnavailableManagedMcpClient,
)
from backend.services.mcp_diagnostics.models import (
    REPORT_VERSION,
    PRIVACY_BOUNDARY,
    STATUS_SEVERITY,
    DiagnosticCheck,
    DiagnosticOperation,
    DiagnosticStatus,
    DiagnosticsReport,
    QueryPlanFinding,
)
from backend.services.mcp_diagnostics.query_templates import (
    QUERY_TEMPLATES,
    QueryTemplate,
    validate_read_only_query,
)
from backend.services.mcp_diagnostics.tool_allowlist import ReadOnlyMcpToolRouter


REQUIRED_TABLES = (
    "workspaces",
    "notebooks",
    "documents",
    "document_blobs",
    "notebook_documents",
    "cached_intelligence",
    "topics",
    "document_chunks",
    "topic_sources",
    "study_sessions",
    "study_interactions",
    "study_interaction_sources",
    "quiz_attempts",
    "quiz_question_attempts",
    "quiz_question_sources",
    "learner_memories",
    "memory_relationships",
    "learner_memory_embeddings",
    "workflow_states",
    "learning_signals",
    "adaptation_events",
    "embedding_jobs",
    "migration_runs",
    "migration_items",
    "guest_sessions",
    "study_tasks",
    "study_task_events",
)
REQUIRED_TABLE_SET = frozenset(REQUIRED_TABLES)
EXPECTED_VECTOR_INDEXES = {
    "document_chunks": "idx_document_chunks_workspace_embedding",
    "learner_memory_embeddings": "idx_memory_embeddings_workspace_embedding",
}
WEAK_TOPIC_COLUMNS = {
    "quiz_question_attempts": {
        "id",
        "workspace_id",
        "quiz_attempt_id",
        "presented",
        "is_correct",
        "skipped",
        "created_at",
    },
    "quiz_attempts": {"id", "workspace_id", "quiz_topic"},
    "learning_signals": {
        "workspace_id",
        "topic",
        "status",
        "signal_type",
        "occurrence_count",
        "confidence",
        "importance",
        "last_observed_at",
    },
    "quiz_question_sources": {
        "workspace_id",
        "question_attempt_id",
        "document_id",
        "document_chunk_id",
    },
    "document_chunks": {"id", "workspace_id", "document_id"},
    "documents": {"id", "workspace_id"},
}


def _safe_check(
    status: DiagnosticStatus,
    title: str,
    finding: str,
    evidence: str,
    *,
    action: str | None = None,
    details: dict[str, Any] | None = None,
) -> DiagnosticCheck:
    return DiagnosticCheck(
        status=status,
        title=title,
        finding=finding,
        evidence_category=evidence,
        recommended_action=action,
        details=details or {},
    )


class McpDiagnosticsService:
    """Run only fixed, sanitized CockroachDB MCP diagnostics."""

    def __init__(
        self,
        client: ManagedMcpClient | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        self._router = ReadOnlyMcpToolRouter(
            client or UnavailableManagedMcpClient(),
            allowed_tables=REQUIRED_TABLE_SET,
            allowed_queries=frozenset(QUERY_TEMPLATES.values()),
        )
        self._generated_at = (now or datetime.now(UTC)).astimezone(UTC)
        self._schema_cache: dict[str, Mapping[str, Any]] = {}

    def run(
        self,
        operation: DiagnosticOperation,
    ) -> DiagnosticsReport:
        if not isinstance(operation, DiagnosticOperation):
            raise ValueError("Only typed diagnostic operations may run.")
        if operation is not DiagnosticOperation.RUN_FULL_DIAGNOSTICS:
            raise ValueError(
                "The local CLI exposes only the fixed full diagnostics operation."
            )
        return self.run_full_diagnostics()

    def run_full_diagnostics(self) -> DiagnosticsReport:
        connection = self._check_connection()
        schema = self._check_required_schema()
        vectors = self._check_vector_indexes()
        workspace = self._check_workspace_safety()
        plans = self._check_query_plans()
        weak_topic = self._check_weak_topic_query(plans)
        statuses = [
            connection.status,
            schema.status,
            vectors.status,
            workspace.status,
            weak_topic.status,
            *(finding.status for finding in plans),
        ]
        overall = max(statuses, key=STATUS_SEVERITY.__getitem__)
        limitations = [
            "Checks cover only the inspected critical query templates.",
            "A passing result does not prove the whole application can never leak data.",
            "No continuous scheduling or production monitoring is provided.",
        ]
        if connection.status is DiagnosticStatus.UNAVAILABLE:
            limitations.append(
                "Independent backend MCP authentication is not configured or available."
            )
        return DiagnosticsReport(
            report_version=REPORT_VERSION,
            generated_at=self._generated_at.isoformat(),
            overall_status=overall,
            connection=connection,
            schema=schema,
            vector_indexes=vectors,
            workspace_safety=workspace,
            weak_topic_query=weak_topic,
            query_plans=plans,
            privacy_boundary=PRIVACY_BOUNDARY,
            limitations=tuple(limitations),
        )

    def _check_connection(self) -> DiagnosticCheck:
        try:
            response = self._router.list_databases()
            _extract_names(response, ("databases", "database_names"))
            return _safe_check(
                DiagnosticStatus.PASSED,
                "MCP connectivity",
                "Managed MCP connectivity and read-only metadata access succeeded.",
                "live_mcp_metadata",
                details={
                    "connected": True,
                    "read_only_mode": "enforced_by_local_allowlist",
                    "target": "Agentbook CockroachDB Cluster",
                },
            )
        except McpAuthenticationRequired:
            return _safe_check(
                DiagnosticStatus.UNAVAILABLE,
                "MCP connectivity",
                "Managed MCP authentication is required.",
                "mcp_authentication",
                action="Renew read-only OAuth or configure a least-privilege backend adapter.",
                details={
                    "connected": False,
                    "read_only_mode": "not_verified",
                    "error_category": "authentication_required",
                },
            )
        except McpTimeout:
            return self._unavailable_connection("timeout")
        except (McpDiagnosticError, ValueError, TypeError):
            return self._unavailable_connection("connection_unavailable")

    def _unavailable_connection(self, category: str) -> DiagnosticCheck:
        return _safe_check(
            DiagnosticStatus.UNAVAILABLE,
            "MCP connectivity",
            "Managed MCP connectivity could not be verified.",
            "mcp_connectivity",
            action="Verify the read-only MCP client configuration and retry.",
            details={
                "connected": False,
                "read_only_mode": "not_verified",
                "error_category": category,
            },
        )

    def _check_required_schema(self) -> DiagnosticCheck:
        try:
            names = _extract_names(
                self._router.list_tables(),
                ("tables", "table_names"),
            )
        except (McpDiagnosticError, ValueError, TypeError):
            return _safe_check(
                DiagnosticStatus.UNAVAILABLE,
                "Required schema",
                "Required Agentbook table availability could not be verified.",
                "live_mcp_schema",
                action="Restore read-only MCP access and rerun diagnostics.",
                details={
                    "required_table_count": len(REQUIRED_TABLES),
                    "present_table_count": 0,
                    "missing_tables": [],
                    "migration_compatibility": "unknown",
                },
            )
        present = {name.rsplit(".", 1)[-1] for name in names}
        missing = sorted(REQUIRED_TABLE_SET - present)
        status = DiagnosticStatus.PASSED if not missing else DiagnosticStatus.FAILED
        return _safe_check(
            status,
            "Required schema",
            (
                "Required Agentbook tables were detected."
                if not missing
                else "Required Agentbook tables are missing."
            ),
            "live_mcp_schema",
            action=(
                None
                if not missing
                else "Apply the expected additive Alembic migrations."
            ),
            details={
                "required_table_count": len(REQUIRED_TABLES),
                "present_table_count": len(REQUIRED_TABLE_SET & present),
                "missing_tables": missing,
                "migration_compatibility": (
                    "compatible" if not missing else "incompatible"
                ),
            },
        )

    def _check_vector_indexes(self) -> DiagnosticCheck:
        availability: dict[str, str] = {}
        workspace_strategy: dict[str, bool] = {}
        try:
            for table, expected_index in EXPECTED_VECTOR_INDEXES.items():
                schema = self._schema(table)
                flattened = _flatten_response(schema).casefold()
                availability[table] = (
                    "available"
                    if expected_index.casefold() in flattened
                    else "missing"
                )
                workspace_strategy[table] = "workspace_id" in flattened
        except (McpDiagnosticError, ValueError, TypeError):
            return _safe_check(
                DiagnosticStatus.UNAVAILABLE,
                "Distributed vector indexes",
                "Vector-index availability could not be verified.",
                "live_mcp_schema",
                action="Restore read-only MCP schema access and rerun diagnostics.",
                details={
                    "document_vector_index": "unknown",
                    "learner_memory_vector_index": "unknown",
                    "workspace_strategy_verified": False,
                },
            )
        missing = [
            table for table, state in availability.items() if state != "available"
        ]
        workspace_verified = all(workspace_strategy.values())
        status = (
            DiagnosticStatus.PASSED
            if not missing and workspace_verified
            else DiagnosticStatus.WARNING
        )
        return _safe_check(
            status,
            "Distributed vector indexes",
            (
                "The expected vector indexes were detected."
                if status is DiagnosticStatus.PASSED
                else "One or more vector-index expectations need review."
            ),
            "live_mcp_schema",
            action=(
                None
                if status is DiagnosticStatus.PASSED
                else "Verify migration 0002 and workspace-leading index definitions."
            ),
            details={
                "document_vector_index": availability["document_chunks"],
                "learner_memory_vector_index": availability[
                    "learner_memory_embeddings"
                ],
                "workspace_strategy_verified": workspace_verified,
                "definition_summary": (
                    "Workspace-scoped cosine vector indexes; raw definitions omitted."
                ),
            },
        )

    def _check_workspace_safety(self) -> DiagnosticCheck:
        evidence = _inspect_repository_workspace_evidence()
        passed = all(evidence.values())
        return _safe_check(
            DiagnosticStatus.PASSED if passed else DiagnosticStatus.FAILED,
            "Workspace-safe query validation",
            (
                "The inspected critical query templates contain workspace-scoped predicates."
                if passed
                else "One or more inspected critical query templates lack required safeguards."
            ),
            "static_repository_inspection",
            action=(
                None
                if passed
                else "Review the named repository and request-authentication boundaries."
            ),
            details={
                "workspace_predicate_present": evidence[
                    "workspace_predicates"
                ],
                "bounded_limit_present": evidence["bounded_limits"],
                "application_ownership_resolved_server_side": evidence[
                    "server_resolved_ownership"
                ],
                "plan_inspected": False,
                "scope": (
                    "Weak topics, document and memory vector searches, Study Task "
                    "reads, and confirmation proposal lookup."
                ),
            },
        )

    def _check_query_plans(self) -> tuple[QueryPlanFinding, ...]:
        findings: list[QueryPlanFinding] = []
        expected_index = {
            QueryTemplate.DOCUMENT_VECTOR_SEARCH: EXPECTED_VECTOR_INDEXES[
                "document_chunks"
            ],
            QueryTemplate.MEMORY_VECTOR_SEARCH: EXPECTED_VECTOR_INDEXES[
                "learner_memory_embeddings"
            ],
        }
        for name, query in QUERY_TEMPLATES.items():
            validate_read_only_query(query)
            try:
                response = self._router.explain_query(query)
                plan = _extract_plan(response)
            except (McpDiagnosticError, ValueError, TypeError):
                findings.append(
                    QueryPlanFinding(
                        name=name.value,
                        status=DiagnosticStatus.UNAVAILABLE,
                        workspace_predicate_present="workspace_id" in query.casefold(),
                        bounded_limit_present=_has_limit(query),
                        index_reference_detected=False,
                        full_scan_observed=False,
                        finding="The fixed EXPLAIN plan was unavailable.",
                    )
                )
                continue
            normalized_plan = plan.casefold()
            index_found = (
                expected_index.get(name, "").casefold() in normalized_plan
                if name in expected_index
                else "index" in normalized_plan
            )
            full_scan = any(
                marker in normalized_plan
                for marker in ("full scan", "full table scan", "scan all")
            )
            status = DiagnosticStatus.WARNING if full_scan else DiagnosticStatus.PASSED
            findings.append(
                QueryPlanFinding(
                    name=name.value,
                    status=status,
                    workspace_predicate_present="workspace_id" in query.casefold(),
                    bounded_limit_present=_has_limit(query),
                    index_reference_detected=index_found,
                    full_scan_observed=full_scan,
                    finding=(
                        "EXPLAIN completed for the fixed query."
                        if not full_scan
                        else "EXPLAIN completed; a full scan needs review."
                    ),
                )
            )
        return tuple(findings)

    def _check_weak_topic_query(
        self,
        plans: tuple[QueryPlanFinding, ...],
    ) -> DiagnosticCheck:
        try:
            schema_compatible = True
            for table, columns in WEAK_TOPIC_COLUMNS.items():
                flattened = _flatten_response(self._schema(table)).casefold()
                if any(column.casefold() not in flattened for column in columns):
                    schema_compatible = False
        except (McpDiagnosticError, ValueError, TypeError):
            schema_compatible = False
            schemas_available = False
        else:
            schemas_available = True
        plan = next(
            item for item in plans if item.name == QueryTemplate.WEAK_TOPICS.value
        )
        query = QUERY_TEMPLATES[QueryTemplate.WEAK_TOPICS]
        query_valid = validate_read_only_query(query) == query
        if not schemas_available or plan.status is DiagnosticStatus.UNAVAILABLE:
            status = DiagnosticStatus.UNAVAILABLE
        elif schema_compatible and query_valid:
            status = DiagnosticStatus.PASSED
        else:
            status = DiagnosticStatus.FAILED
        return _safe_check(
            status,
            "Weak-topic query",
            (
                "EXPLAIN completed for the fixed weak-topic query."
                if status is DiagnosticStatus.PASSED
                else "The fixed weak-topic query could not be fully verified."
            ),
            "live_mcp_schema_and_explain",
            action=(
                None
                if status is DiagnosticStatus.PASSED
                else "Restore MCP access or reconcile the query with the current schema."
            ),
            details={
                "schema_compatible": schema_compatible if schemas_available else "unknown",
                "query_valid": query_valid,
                "explain_successful": plan.status is not DiagnosticStatus.UNAVAILABLE,
                "workspace_predicate_detected": "workspace_id" in query.casefold(),
                "bounded_result_behavior_detected": _has_limit(query),
                "plan_summary": plan.finding,
            },
        )

    def _schema(self, table: str) -> Mapping[str, Any]:
        if table not in self._schema_cache:
            self._schema_cache[table] = self._router.get_table_schema(table)
        return self._schema_cache[table]


def _extract_names(
    response: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[str, ...]:
    for key in keys:
        value = response.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value)
    raise McpMalformedResponse("The MCP metadata response was malformed.")


def _extract_plan(response: Mapping[str, Any]) -> str:
    for key in ("plan", "explain", "summary", "lines"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return "\n".join(value)
    raise McpMalformedResponse("The MCP EXPLAIN response was malformed.")


def _flatten_response(response: Mapping[str, Any]) -> str:
    try:
        return json.dumps(response, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise McpMalformedResponse("The MCP schema response was malformed.") from error


def _has_limit(query: str) -> bool:
    return bool(__import__("re").search(r"\bLIMIT\s+\d+\b", query, __import__("re").I))


def _inspect_repository_workspace_evidence() -> dict[str, bool]:
    project_root = Path(__file__).resolve().parents[3]

    def source(relative_path: str) -> str:
        return (project_root / relative_path).read_text(encoding="utf-8")

    study = source("backend/repositories/cockroach/study.py")
    vectors = source("backend/repositories/cockroach/vectors.py")
    tasks = source("backend/repositories/cockroach/study_tasks.py")
    workflow = source("backend/repositories/cockroach/foundation.py")
    auth = source("backend/api/guest_auth.py")
    return {
        "workspace_predicates": all(
            "workspace_id" in content
            for content in (study, vectors, tasks, workflow)
        ),
        "bounded_limits": (
            "def list_weak_topics" in study
            and "LIMIT :limit" in study
            and vectors.count("LIMIT :limit") >= 2
            and "def list_tasks" in tasks
            and "LIMIT :limit" in tasks
        ),
        "server_resolved_ownership": (
            "principal.workspace.id" in auth
            and "workspace_id" in auth
            and "WORKSPACE_HEADER_KEYS" in auth
        ),
    }
