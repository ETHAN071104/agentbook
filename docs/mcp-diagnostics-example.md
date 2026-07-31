# Agentbook CockroachDB MCP Diagnostics

> Synthetic sanitized example — not a current live result.

## Overall status

**passed**

## MCP connectivity

**passed** — Managed MCP connectivity and read-only metadata access succeeded.

## Required schema

**passed** — Required Agentbook tables were detected.

## Distributed vector indexes

**passed** — The expected vector indexes were detected.

## Workspace-safe query validation

**passed** — The inspected critical query templates contain workspace-scoped predicates.

## Weak-topic query

**passed** — EXPLAIN completed for the fixed weak-topic query.

## Query-plan findings

- **weak_topics — passed**: EXPLAIN completed for the fixed query.

## Privacy boundary

No learner content, raw rows, embeddings, credentials, workspace identifiers, or raw MCP messages are returned by these diagnostics.

## Limitations

- Synthetic example; no live learner data was inspected.
- Checks cover only the inspected critical query templates.
