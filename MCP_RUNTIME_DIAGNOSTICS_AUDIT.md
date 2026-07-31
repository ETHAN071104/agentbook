# MCP Runtime Diagnostics Authentication Audit

## Classification

**Outcome C — No safe backend authentication exists yet.**

Agentbook does not currently have an independent credential or OAuth session
that its backend can safely use with the CockroachDB Cloud Managed MCP Server.
The existing local Codex MCP entry uses remote HTTP transport, a fixed cluster
selector, and Codex-managed OAuth. It does not contain a manually configured
bearer token. The current OAuth refresh attempt returns an expired or invalid
grant, so current read-only consent and live tool availability cannot be
verified.

The Codex OAuth cache was not read, copied, or exposed. Agentbook does not load
Codex configuration or token files.

## Existing evidence

The preserved `MCP_DEVELOPMENT_WORKFLOW.md` and `MCP_QUERY_EVIDENCE.md` record a
previous developer-operated, read-only OAuth session that used:

- `list_databases`
- `list_tables`
- `get_table_schema`
- `select_query`
- `explain_query`

That is valid historical development evidence. It is not evidence that the
Agentbook backend can authenticate today.

## Managed MCP tool inventory

Cockroach Labs currently documents these read tools:

- `list_clusters`
- `get_cluster`
- `list_databases`
- `list_tables`
- `get_table_schema`
- `select_query`
- `explain_query`
- `show_running_queries`

It also documents these write-capable tools:

- `create_database`
- `create_table`
- `insert_rows`

Source: [Connect to the CockroachDB Cloud MCP Server](https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-the-cockroachdb-cloud-mcp-server).

Agentbook Phase 8C permits only:

- `list_databases`
- `list_tables`
- `get_table_schema`
- `explain_query`

The smaller local allowlist is deliberate. It excludes general `select_query`,
cluster enumeration/detail tools, activity inspection, and every write tool.

## Read-only assessment

The application-side tool router is read-only by construction and accepts only
fixed arguments and fixed query templates. Current server-side OAuth consent
could not be verified because the Codex refresh grant is expired. A future
backend adapter must establish read-only consent independently before live
runtime diagnostics are enabled.

## Admin authentication assessment

Agentbook has Guest Workspace isolation, but no independent Admin accounts,
roles, CSRF-protected Admin session, Admin rate limiter, or Admin audit event
store. Guest credentials must not authorize infrastructure diagnostics.

Therefore Phase 8C adds no HTTP endpoint and no frontend page. A hidden route
would not provide authentication.

## Required next authentication step

Choose one:

1. Renew a local developer OAuth session with read-only consent for
   developer-operated diagnostics; or
2. Add a dedicated least-privilege backend identity supported by the official
   MCP client, without reusing a general production credential.

Then implement the normalized `ManagedMcpClient` adapter using a supported MCP
SDK with Streamable HTTP. Do not copy Codex OAuth state into Agentbook.
