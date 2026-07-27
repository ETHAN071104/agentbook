# CockroachDB MCP Development Workflow

## Connection

- Client: Codex
- MCP server: CockroachDB Cloud Managed MCP
- Authentication: OAuth with read-only authorization
- Cluster scope: a single configured cluster
- Application database inspected: `defaultdb`

No database connection string, SQL credential, OAuth token, cluster identifier,
guest credential, or private application row was used in the development
workflow.

## Actual MCP Tools Used

The live audit recorded calls to:

- `list_databases`
- `list_tables`
- `get_table_schema`
- `select_query`
- `explain_query`

The audit produced 37 completed MCP call events. One exploratory MCP request
returned an error and was replaced by supported read-only calls; no finding in
this document depends on the failed request.

No repository files or migration definitions were used as proof of the live
schema. Repository comparison began only after the MCP schema, aggregate, and
query-plan audit completed.

## Live Schemas Inspected

The MCP audit inspected the live tables relevant to the first Agentbook
business tool:

- `workspaces`
- `quiz_attempts`
- `quiz_question_attempts`
- `quiz_question_sources`
- `learning_signals`
- `learner_memories`
- `learner_memory_embeddings`
- `memory_relationships`
- `study_sessions`
- `study_interactions`
- `study_interaction_sources`
- `adaptation_events`
- `workflow_states`
- `documents`
- `document_chunks`
- `embedding_jobs`

The audit also listed all live tables before choosing this bounded set.

## Safe Aggregate Checks

Only totals and health findings were retained:

| Check | Sanitized result |
|---|---:|
| Quiz attempts | 6 |
| Workspaces with attempts | 2 |
| Attempts per workspace: min / average / max | 1 / 3 / 5 |
| Quiz-question rows / presented | 12 / 12 |
| Incorrect / correct / skipped outcomes | 9 / 3 / 0 |
| Active Learning Signals | 9 |
| Active Learner Memories | 11 |
| Active memories missing embeddings | 0 |
| Orphan or cross-workspace memory embeddings | 0 |
| Quiz source rows missing required lineage | 0 |
| Orphan or cross-workspace quiz sources | 0 |
| Document chunks missing embeddings | 0 |
| Pending / processing / failed embedding jobs | 0 / 0 / 0 |

Workspace identifiers, question/answer content, document content, excerpts,
JSON payloads, hashes, embeddings, filenames, and token/session rows were not
reported.

## How MCP Informed the Implementation

The live schema changed the design in several concrete ways:

1. There is no `mastery_score`. Weakness is derived from explicit question
   outcomes, repetition, recency, and Learning Signals.
2. Incorrect outcomes are `presented AND NOT skipped AND NOT is_correct`.
   Skips use the explicit `skipped` flag.
3. The weakness topic is `quiz_attempts.quiz_topic`; live knowledge-gap
   evidence uses `learning_signals.topic`.
4. Signal strength can use `occurrence_count`, `confidence`, `importance`, and
   `last_observed_at`. The live snapshot contains active `knowledge_gap`
   signals. Repository comparison additionally confirmed Agentbook's existing
   `improving` application state, which safely reduces rather than increases a
   weakness score.
5. Source evidence is joined from the question attempt through
   `quiz_question_sources`, `document_chunks`, and `documents`.
6. Live foreign keys are not composite workspace keys. Every owned join in the
   CockroachDB query therefore repeats the same `workspace_id` constraint.
7. Source document IDs exposed by the application are the workspace-scoped
   `documents.public_id` values, serialized as decimal strings at the API
   boundary.
8. Learner Memory content and vectors are excluded from factual source
   evidence.

The result is a migration-free, read-only service with a protected endpoint:

`GET /api/study/weak-topics`

The endpoint accepts only bounded ranking parameters. Workspace identity is
resolved by the authenticated request dependency and is not accepted from the
client.

## Security Boundaries

- MCP access was read-only.
- No write MCP tool or SQL mutation was called.
- No schema or index was created.
- No guest bearer credential was sent to MCP.
- No workspace identifier is returned by the service.
- Every live CockroachDB join preserves workspace ownership.
- The SQLite compatibility query also scopes attempts, outcomes, signals,
  lineage, and documents to one workspace.
- The response contains no question, answer, explanation, excerpt, document
  content, embedding, memory content, token, or private payload.
- Repository-level integer public IDs remain exact integers; API responses use
  decimal strings.

## Verification

Targeted tests cover repeated and recent mistakes, incorrect and skipped
outcomes, signal evidence, empty history, guest isolation, workspace-tampering
rejection, string public IDs, and private-field exclusion. Full-suite results
are recorded in `MCP_QUERY_EVIDENCE.md`.
