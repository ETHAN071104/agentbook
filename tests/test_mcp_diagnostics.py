from __future__ import annotations

import json
import re
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.services.mcp_diagnostics.cli import run_check
from backend.services.mcp_diagnostics.client import (
    McpAuthenticationRequired,
    McpTimeout,
)
from backend.services.mcp_diagnostics.diagnostics import (
    EXPECTED_VECTOR_INDEXES,
    REQUIRED_TABLES,
    WEAK_TOPIC_COLUMNS,
    McpDiagnosticsService,
)
from backend.services.mcp_diagnostics.models import (
    DiagnosticOperation,
    DiagnosticStatus,
)
from backend.services.mcp_diagnostics.query_templates import (
    QUERY_TEMPLATES,
    QueryTemplate,
    validate_read_only_query,
)
from backend.services.mcp_diagnostics.report import (
    render_markdown,
    sanitized_report_dict,
    write_reports,
)
from backend.services.mcp_diagnostics.sanitizer import (
    sanitize_text,
    sanitize_value,
)
from backend.services.mcp_diagnostics.tool_allowlist import (
    APPLICATION_DATABASE,
    McpTool,
    ReadOnlyMcpToolRouter,
    ToolNotAllowed,
    UnsafeToolArguments,
)


class FakeMcpClient:
    def __init__(
        self,
        *,
        tables: list[str] | None = None,
        missing_indexes: set[str] | None = None,
        missing_columns: dict[str, set[str]] | None = None,
        full_scan_queries: set[str] | None = None,
        malformed_tool: str | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.tables = tables if tables is not None else list(REQUIRED_TABLES)
        self.missing_indexes = missing_indexes or set()
        self.missing_columns = missing_columns or {}
        self.full_scan_queries = full_scan_queries or set()
        self.malformed_tool = malformed_tool
        self.failure = failure
        self.calls: list[tuple[str, dict[str, object], int]] = []

    def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
        *,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        self.calls.append((tool_name, dict(arguments), timeout_seconds))
        if self.failure is not None:
            raise self.failure
        if tool_name == self.malformed_tool:
            return {"unexpected": object()}
        if tool_name == "list_databases":
            return {"databases": [APPLICATION_DATABASE]}
        if tool_name == "list_tables":
            return {"table_names": list(self.tables)}
        if tool_name == "get_table_schema":
            table = str(arguments["table"])
            columns = set(WEAK_TOPIC_COLUMNS.get(table, {"id", "workspace_id"}))
            columns.add("workspace_id")
            columns -= self.missing_columns.get(table, set())
            index = EXPECTED_VECTOR_INDEXES.get(table)
            indexes = (
                []
                if index is None or table in self.missing_indexes
                else [{"name": index, "columns": ["workspace_id", "embedding"]}]
            )
            return {
                "table": table,
                "columns": sorted(columns),
                "indexes": indexes,
            }
        if tool_name == "explain_query":
            query = str(arguments["query"])
            if query in self.full_scan_queries:
                return {"plan": "full table scan; filter workspace_id; limit"}
            index_name = ""
            if query == QUERY_TEMPLATES[QueryTemplate.DOCUMENT_VECTOR_SEARCH]:
                index_name = EXPECTED_VECTOR_INDEXES["document_chunks"]
            elif query == QUERY_TEMPLATES[QueryTemplate.MEMORY_VECTOR_SEARCH]:
                index_name = EXPECTED_VECTOR_INDEXES[
                    "learner_memory_embeddings"
                ]
            return {
                "plan": f"index scan {index_name}; filter workspace_id; limit"
            }
        raise AssertionError(f"Unexpected tool: {tool_name}")


def full_report(client: FakeMcpClient | None = None):
    return McpDiagnosticsService(client or FakeMcpClient()).run(
        DiagnosticOperation.RUN_FULL_DIAGNOSTICS
    )


class ToolBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeMcpClient()
        self.router = ReadOnlyMcpToolRouter(
            self.client,
            allowed_tables=frozenset(REQUIRED_TABLES),
            allowed_queries=frozenset(QUERY_TEMPLATES.values()),
        )

    def test_only_allowlisted_tools_can_be_called(self) -> None:
        self.router.list_databases()
        self.router.list_tables()
        self.router.get_table_schema("documents")
        self.router.explain_query(QUERY_TEMPLATES[QueryTemplate.WEAK_TOPICS])
        self.assertEqual(
            [call[0] for call in self.client.calls],
            [
                "list_databases",
                "list_tables",
                "get_table_schema",
                "explain_query",
            ],
        )

    def test_write_tools_are_rejected(self) -> None:
        with self.assertRaises(ToolNotAllowed):
            self.router.call(  # type: ignore[arg-type]
                "insert_rows",
                {"database": APPLICATION_DATABASE},
            )

    def test_arbitrary_tool_names_are_rejected(self) -> None:
        with self.assertRaises(ToolNotAllowed):
            self.router.call("show_secrets", {})  # type: ignore[arg-type]

    def test_user_supplied_table_identifier_is_rejected(self) -> None:
        with self.assertRaises(UnsafeToolArguments):
            self.router.get_table_schema("system.users")

    def test_guest_token_cannot_authorize_diagnostics(self) -> None:
        with self.assertRaises(UnsafeToolArguments):
            self.router.call(
                McpTool.LIST_DATABASES,
                {"authorization": "Bearer guest-token"},
            )

    def test_timeout_is_always_bounded(self) -> None:
        self.router.list_databases()
        self.assertGreater(self.client.calls[0][2], 0)
        self.assertLessEqual(self.client.calls[0][2], 60)

    def test_no_write_capable_tool_is_invoked_by_full_diagnostics(self) -> None:
        full_report(self.client)
        self.assertTrue(
            {call[0] for call in self.client.calls}
            <= {
                "list_databases",
                "list_tables",
                "get_table_schema",
                "explain_query",
            }
        )


class QuerySafetyTests(unittest.TestCase):
    def test_registered_queries_are_read_only_and_fixed(self) -> None:
        for query in QUERY_TEMPLATES.values():
            self.assertEqual(validate_read_only_query(query), query)

    def test_arbitrary_sql_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_query("SELECT * FROM learner_memories LIMIT 5")

    def test_multi_statement_sql_is_rejected(self) -> None:
        query = (
            QUERY_TEMPLATES[QueryTemplate.PENDING_STUDY_TASKS]
            + "; SELECT 1"
        )
        with self.assertRaises(ValueError):
            validate_read_only_query(query)

    def test_ddl_and_dml_are_rejected(self) -> None:
        for query in (
            "DROP TABLE documents",
            "INSERT INTO study_tasks VALUES (1)",
            "UPDATE workspaces SET name='x'",
            "DELETE FROM documents",
        ):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    validate_read_only_query(query)

    def test_all_fixed_queries_have_workspace_predicate(self) -> None:
        for query in QUERY_TEMPLATES.values():
            self.assertIn("workspace_id", query.casefold())

    def test_all_fixed_queries_have_bounded_limit(self) -> None:
        for query in QUERY_TEMPLATES.values():
            self.assertRegex(query.casefold(), r"\blimit\s+\d+\b")

    def test_no_query_contains_write_or_analyze(self) -> None:
        combined = "\n".join(QUERY_TEMPLATES.values()).casefold()
        for keyword in (
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "truncate ",
            "explain analyze",
        ):
            self.assertNotIn(keyword, combined)


class DiagnosticBehaviorTests(unittest.TestCase):
    def test_required_tables_match_current_alembic_chain(self) -> None:
        migration_paths = (
            Path("alembic/versions/0001_agentbook_cockroach_schema.py"),
            Path("alembic/versions/0003_guest_sessions.py"),
            Path("alembic/versions/0004_persisted_study_tasks.py"),
        )
        discovered: list[str] = []
        for path in migration_paths:
            discovered.extend(
                re.findall(
                    r"CREATE TABLE\s+([a-z_]+)",
                    path.read_text(encoding="utf-8"),
                    re.IGNORECASE,
                )
            )
        self.assertEqual(tuple(discovered), REQUIRED_TABLES)

    def test_fixed_schema_diagnostic_succeeds(self) -> None:
        report = full_report()
        self.assertEqual(report.schema.status, DiagnosticStatus.PASSED)
        self.assertEqual(
            report.schema.details["required_table_count"],
            len(REQUIRED_TABLES),
        )
        self.assertEqual(report.schema.details["missing_tables"], [])

    def test_missing_required_table_fails(self) -> None:
        tables = list(REQUIRED_TABLES)
        tables.remove("study_tasks")
        report = full_report(FakeMcpClient(tables=tables))
        self.assertEqual(report.schema.status, DiagnosticStatus.FAILED)
        self.assertEqual(report.schema.details["missing_tables"], ["study_tasks"])

    def test_expected_vector_indexes_are_detected(self) -> None:
        report = full_report()
        self.assertEqual(report.vector_indexes.status, DiagnosticStatus.PASSED)
        self.assertEqual(
            report.vector_indexes.details["document_vector_index"],
            "available",
        )
        self.assertEqual(
            report.vector_indexes.details["learner_memory_vector_index"],
            "available",
        )

    def test_missing_vector_index_warns(self) -> None:
        report = full_report(
            FakeMcpClient(missing_indexes={"learner_memory_embeddings"})
        )
        self.assertEqual(report.vector_indexes.status, DiagnosticStatus.WARNING)
        self.assertEqual(
            report.vector_indexes.details["learner_memory_vector_index"],
            "missing",
        )

    def test_workspace_predicate_static_detection_succeeds(self) -> None:
        report = full_report()
        self.assertEqual(report.workspace_safety.status, DiagnosticStatus.PASSED)
        self.assertTrue(
            report.workspace_safety.details["workspace_predicate_present"]
        )
        self.assertTrue(
            report.workspace_safety.details[
                "application_ownership_resolved_server_side"
            ]
        )

    def test_fixed_queries_detect_missing_workspace_predicate(self) -> None:
        unsafe = "SELECT public_id FROM study_tasks LIMIT 5"
        with self.assertRaises(ValueError):
            validate_read_only_query(unsafe)

    def test_weak_topic_explain_succeeds(self) -> None:
        report = full_report()
        self.assertEqual(report.weak_topic_query.status, DiagnosticStatus.PASSED)
        self.assertTrue(report.weak_topic_query.details["explain_successful"])
        self.assertTrue(
            report.weak_topic_query.details["workspace_predicate_detected"]
        )

    def test_missing_weak_topic_column_fails(self) -> None:
        client = FakeMcpClient(
            missing_columns={"learning_signals": {"occurrence_count"}}
        )
        report = full_report(client)
        self.assertEqual(report.weak_topic_query.status, DiagnosticStatus.FAILED)

    def test_full_scan_plan_warns(self) -> None:
        query = QUERY_TEMPLATES[QueryTemplate.DOCUMENT_VECTOR_SEARCH]
        report = full_report(FakeMcpClient(full_scan_queries={query}))
        finding = next(
            item
            for item in report.query_plans
            if item.name == QueryTemplate.DOCUMENT_VECTOR_SEARCH.value
        )
        self.assertEqual(finding.status, DiagnosticStatus.WARNING)
        self.assertTrue(finding.full_scan_observed)

    def test_malformed_response_becomes_unavailable(self) -> None:
        report = full_report(FakeMcpClient(malformed_tool="list_databases"))
        self.assertEqual(report.connection.status, DiagnosticStatus.UNAVAILABLE)
        self.assertEqual(
            report.connection.details["error_category"],
            "connection_unavailable",
        )

    def test_timeout_becomes_unavailable(self) -> None:
        report = full_report(FakeMcpClient(failure=McpTimeout("timeout")))
        self.assertEqual(report.connection.status, DiagnosticStatus.UNAVAILABLE)
        self.assertEqual(report.connection.details["error_category"], "timeout")

    def test_authentication_failure_is_distinct(self) -> None:
        report = full_report(
            FakeMcpClient(
                failure=McpAuthenticationRequired("expired authentication")
            )
        )
        self.assertEqual(
            report.connection.details["error_category"],
            "authentication_required",
        )

    def test_full_diagnostics_aggregates_highest_severity(self) -> None:
        tables = list(REQUIRED_TABLES)
        tables.remove("workspaces")
        report = full_report(FakeMcpClient(tables=tables))
        self.assertEqual(report.overall_status, DiagnosticStatus.FAILED)

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            McpDiagnosticsService(FakeMcpClient()).run(  # type: ignore[arg-type]
                "arbitrary_operation"
            )

    def test_individual_public_operation_cannot_accept_parameters(self) -> None:
        with self.assertRaises(ValueError):
            McpDiagnosticsService(FakeMcpClient()).run(
                DiagnosticOperation.CHECK_QUERY_PLANS
            )


class SanitizerAndReportTests(unittest.TestCase):
    def test_sanitizer_removes_cluster_identifier(self) -> None:
        value = sanitize_text("cluster 123e4567-e89b-42d3-a456-426614174000")
        self.assertNotIn("123e4567", value)

    def test_sanitizer_removes_email(self) -> None:
        value = sanitize_text("administrator@example.com")
        self.assertNotIn("@example.com", value)

    def test_sanitizer_removes_oauth_and_api_tokens(self) -> None:
        value = sanitize_value(
            {
                "oauth_token": "secret",
                "api_key": "sk-abcdefghijklmnop",
                "note": "Bearer abcdefghijklmnop.qrstuvwxyz1234",
            }
        )
        self.assertNotIn("secret", str(value))
        self.assertNotIn("sk-", str(value))
        self.assertNotIn("Bearer ", str(value))

    def test_sanitizer_removes_workspace_and_entity_ids(self) -> None:
        value = sanitize_value(
            {
                "workspace_id": "private",
                "document_id": "private-document",
                "task_id": "private-task",
            }
        )
        self.assertNotIn("private", str(value))

    def test_sanitizer_removes_local_paths_and_urls(self) -> None:
        value = sanitize_text(
            r"C:\Users\person\secret.txt postgres://user:password@host/db"
        )
        self.assertNotIn("Users", value)
        self.assertNotIn("password", value)

    def test_reports_contain_no_learner_rows_or_embeddings(self) -> None:
        report = full_report()
        combined = json.dumps(sanitized_report_dict(report)) + render_markdown(
            report
        )
        for forbidden in (
            "page_content",
            "embedding_values",
            "raw_rows",
            "question_text",
            "answer_text",
        ):
            self.assertNotIn(forbidden, combined)

    def test_json_and_markdown_reports_agree(self) -> None:
        report = full_report()
        with tempfile.TemporaryDirectory() as directory:
            json_path, markdown_path = write_reports(report, Path(directory))
            json_report = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
        self.assertIn(json_report["overall_status"], markdown)
        self.assertIn(json_report["privacy_boundary"], markdown)

    def test_public_reports_do_not_expose_transport_content(self) -> None:
        report = full_report()
        combined = json.dumps(sanitized_report_dict(report))
        self.assertNotIn("jsonrpc", combined.casefold())
        self.assertNotIn("mcp-cluster-id", combined.casefold())
        self.assertNotIn("raw_sql", combined.casefold())

    def test_cli_writes_sanitized_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            exit_code = run_check(
                service=McpDiagnosticsService(FakeMcpClient()),
                output_directory=Path(directory),
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(directory) / "latest-report.json").exists())
            self.assertTrue((Path(directory) / "latest-report.md").exists())

    def test_learning_agent_does_not_import_diagnostics(self) -> None:
        root = Path("backend")
        learner_files = [
            *Path("backend/application/learning_agent").glob("*.py"),
            Path("backend/application/weak_topics.py"),
            Path("backend/application/study_tasks.py"),
        ]
        self.assertTrue(root.exists())
        for path in learner_files:
            with self.subTest(path=path):
                self.assertNotIn(
                    "mcp_diagnostics",
                    path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
