# Protected CockroachDB MCP Diagnostics

Agentbook Phase 8C provides a local Admin/Developer diagnostics layer for
fixed, read-only checks. It is isolated from learner-facing Agent tools.

## Current status

**Protected diagnostics implementation complete; backend-hosted authentication
pending.**

The existing Codex OAuth refresh grant is expired, and Agentbook has no
independent Managed MCP credential. The CLI therefore produces an honest
`unavailable` report until a supported read-only client adapter is configured.

## Run the fixed diagnostic

```powershell
python -m backend.services.mcp_diagnostics.cli check
```

Optional ignored output directory:

```powershell
python -m backend.services.mcp_diagnostics.cli check `
  --output-dir artifacts/mcp-diagnostics
```

Exit codes:

- `0` — passed
- `1` — warning
- `2` — failed
- `3` — unavailable or configuration error

The command accepts no SQL, prompt, tool name, table name, database name,
cluster identifier, or Guest token.

## What is checked

### MCP connectivity

Checks whether fixed read-only metadata access can start. Output is limited to
connection state, read-only verification state, timestamp, and a sanitized
error category.

### Required schema

Checks the 27 tables declared by the current Alembic chain. It returns counts
and safe missing table names, never column values.

### Distributed vector indexes

Checks the document and learner-memory vector index names from migration
`0002`. It reports availability and workspace-leading strategy without
returning embeddings or raw definitions.

### Workspace-safe query structure

Static inspection verifies actual repository and authentication source
structures. Fixed `EXPLAIN` calls provide live evidence when MCP authentication
is available.

The result means only:

> The inspected critical query templates contain workspace-scoped predicates.

It does not claim that the whole application can never leak data.

### Weak-topic and query plans

The diagnostic validates schema compatibility and runs safe `EXPLAIN` for
fixed weak-topic, vector-retrieval, and pending-task templates. It does not use
`EXPLAIN ANALYZE` or return raw plan text.

## Security boundary

- backend-only adapter;
- fixed typed operation;
- four read-only tools;
- fixed database, tables, and queries;
- bounded timeout and output model;
- no MCP messages sent to the frontend;
- no raw rows, learner content, embeddings, or credentials;
- no Guest authorization;
- no API or UI until independent Admin authentication exists.

See `MCP_RUNTIME_DIAGNOSTICS_AUDIT.md` for the authentication decision and
`MCP_DIAGNOSTICS_IMPLEMENTATION.md` for implementation details.
