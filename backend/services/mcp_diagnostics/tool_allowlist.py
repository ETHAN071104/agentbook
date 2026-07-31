from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from backend.services.mcp_diagnostics.client import ManagedMcpClient


MCP_TIMEOUT_SECONDS = 15
APPLICATION_DATABASE = "defaultdb"


class McpTool(StrEnum):
    LIST_DATABASES = "list_databases"
    LIST_TABLES = "list_tables"
    GET_TABLE_SCHEMA = "get_table_schema"
    EXPLAIN_QUERY = "explain_query"


WRITE_CAPABLE_TOOLS = frozenset(
    {"create_database", "create_table", "insert_rows"}
)


class ToolNotAllowed(ValueError):
    pass


class UnsafeToolArguments(ValueError):
    pass


class ReadOnlyMcpToolRouter:
    """Enforce the complete tool and argument boundary before transport."""

    def __init__(
        self,
        client: ManagedMcpClient,
        *,
        allowed_tables: frozenset[str],
        allowed_queries: frozenset[str],
    ) -> None:
        self._client = client
        self._allowed_tables = allowed_tables
        self._allowed_queries = allowed_queries

    def call(
        self,
        tool: McpTool,
        arguments: Mapping[str, object],
    ) -> Mapping[str, Any]:
        if not isinstance(tool, McpTool):
            raise ToolNotAllowed("Only typed, allowlisted MCP tools may run.")
        normalized = dict(arguments)
        self._validate_arguments(tool, normalized)
        return self._client.call_tool(
            tool.value,
            normalized,
            timeout_seconds=MCP_TIMEOUT_SECONDS,
        )

    def list_databases(self) -> Mapping[str, Any]:
        return self.call(McpTool.LIST_DATABASES, {})

    def list_tables(self) -> Mapping[str, Any]:
        return self.call(
            McpTool.LIST_TABLES,
            {"database": APPLICATION_DATABASE},
        )

    def get_table_schema(self, table: str) -> Mapping[str, Any]:
        return self.call(
            McpTool.GET_TABLE_SCHEMA,
            {"database": APPLICATION_DATABASE, "table": table},
        )

    def explain_query(self, query: str) -> Mapping[str, Any]:
        return self.call(
            McpTool.EXPLAIN_QUERY,
            {"database": APPLICATION_DATABASE, "query": query},
        )

    def _validate_arguments(
        self,
        tool: McpTool,
        arguments: dict[str, object],
    ) -> None:
        if tool is McpTool.LIST_DATABASES:
            if arguments:
                raise UnsafeToolArguments(
                    "list_databases does not accept public arguments."
                )
            return
        if arguments.get("database") != APPLICATION_DATABASE:
            raise UnsafeToolArguments(
                "Only the fixed Agentbook database may be inspected."
            )
        if tool is McpTool.LIST_TABLES:
            if set(arguments) != {"database"}:
                raise UnsafeToolArguments("Unexpected list_tables arguments.")
            return
        if tool is McpTool.GET_TABLE_SCHEMA:
            if (
                set(arguments) != {"database", "table"}
                or arguments.get("table") not in self._allowed_tables
            ):
                raise UnsafeToolArguments(
                    "Only fixed Agentbook tables may be inspected."
                )
            return
        if tool is McpTool.EXPLAIN_QUERY:
            if (
                set(arguments) != {"database", "query"}
                or arguments.get("query") not in self._allowed_queries
            ):
                raise UnsafeToolArguments(
                    "Only fixed diagnostic query templates may be explained."
                )
            return
        raise ToolNotAllowed("The requested MCP tool is not allowlisted.")
