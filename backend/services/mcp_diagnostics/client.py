from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class McpDiagnosticError(RuntimeError):
    """Safe MCP failure without raw transport content."""


class McpAuthenticationRequired(McpDiagnosticError):
    pass


class McpUnavailable(McpDiagnosticError):
    pass


class McpTimeout(McpDiagnosticError):
    pass


class McpMalformedResponse(McpDiagnosticError):
    pass


class ManagedMcpClient(Protocol):
    """Normalized adapter boundary for a supported Streamable HTTP MCP client."""

    def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
        *,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        """Call one tool and return a normalized mapping."""


class UnavailableManagedMcpClient:
    """Default until Agentbook has independent read-only MCP authentication."""

    def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
        *,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        del tool_name, arguments, timeout_seconds
        raise McpAuthenticationRequired(
            "Independent backend MCP authentication is not configured."
        )
