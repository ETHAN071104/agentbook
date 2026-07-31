# Phase 8C MCP Diagnostics Implementation

## Outcome

The protected diagnostics implementation is complete behind a normalized MCP
client adapter. Backend-hosted authentication remains pending.

## Architecture

```text
Local Admin/Developer CLI
  -> typed diagnostics operation
  -> fixed diagnostics service
  -> read-only MCP tool router
  -> normalized Streamable HTTP MCP client adapter
  -> CockroachDB Cloud Managed MCP
  -> Agentbook CockroachDB Cluster
```

The current default adapter reports authentication unavailable. It never falls
back to a SQL connection, Codex token cache, Guest token, or application
database credential.

## Fixed operations

The model defines:

- `check_connection`
- `check_required_schema`
- `check_vector_indexes`
- `check_workspace_safety`
- `check_weak_topic_query`
- `check_query_plans`
- `run_full_diagnostics`

The local CLI intentionally exposes only `run_full_diagnostics`. There is no
public method accepting arbitrary tool names, SQL, tables, prompts, cluster
identifiers, or JSON-RPC messages.

## Tool boundary

Allowed:

- `list_databases` with no arguments
- `list_tables` for the fixed Agentbook database
- `get_table_schema` for an enumerated Agentbook table
- `explain_query` for one of four registered query templates

Denied:

- all unknown tools
- all write tools
- arbitrary database or table identifiers
- arbitrary SQL and SQL fragments
- multi-statement SQL
- DDL, DML, transaction control, and `EXPLAIN ANALYZE`

Every call has a fixed 15-second timeout.

## Schema authority

The required list is derived from Alembic revisions
`0001_agentbook_cockroach_schema`, `0003_guest_sessions`, and
`0004_persisted_study_tasks`. It contains 27 current application tables.

The vector indexes are derived from revision
`0002_cockroach_vector_indexes`:

- `idx_document_chunks_workspace_embedding`
- `idx_memory_embeddings_workspace_embedding`

## Workspace evidence

Static inspection uses Python source inspection of the actual Cockroach
repository methods and Guest authentication boundary. It checks:

- weak-topic workspace predicates and limit;
- document-vector workspace predicate and limit;
- learner-memory vector workspace predicate and limit;
- Study Task read workspace predicate and limit;
- confirmation workflow ownership predicate;
- server-side workspace derivation and rejection of client workspace overrides.

Live evidence is designed to use `explain_query` only for fixed templates based
on those production queries. It never fetches learner rows.

## Query templates

The registered templates cover:

- weak-topic aggregation;
- document-vector workspace retrieval;
- learner-memory vector workspace retrieval;
- pending Study Task lookup.

Each template uses a synthetic UUID, a fixed bound, no comments, no
user-supplied identifiers, and no write operation. Vector templates use a
synthetic zero vector only for planning.

## Reports

Live reports are written to:

- `artifacts/mcp-diagnostics/latest-report.json`
- `artifacts/mcp-diagnostics/latest-report.md`

That directory is ignored. Repository examples are synthetic.

The report omits raw MCP responses, plans, rows, embeddings, paths, endpoints,
credentials, cluster identifiers, organization identifiers, and learner
identifiers.

## Deliberate exclusions

- no Admin API or UI;
- no generic MCP proxy;
- no raw SQL endpoint;
- no frontend MCP transport;
- no direct database fallback;
- no service-account creation;
- no OAuth cache access;
- no continuous monitoring claim.
