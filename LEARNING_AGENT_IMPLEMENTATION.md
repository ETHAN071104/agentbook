# Learning Agent implementation

## Product behavior

Agentbook uses a controlled, read-only tool layer to ground personalized
learning guidance in the authenticated learner's own workspace. The new
**Ask Agentbook** page supports questions about weak topics, recent mistakes,
indexed study materials, and the current adaptive study plan.

The Agent remains single-turn and does not persist Agent messages, change study
plans, submit quizzes, or save learner memory. Phase 8B can prepare one Study
Task creation or completion, but no task write occurs until the learner
explicitly confirms the server-stored proposal.

## Architecture

```text
authenticated learner
  -> POST /api/agent/query
  -> bounded intent planner
  -> validated allowlisted calls
  -> request-scoped application tools
  -> scoped repositories/vector retrieval
  -> sanitized ToolResult envelopes
  -> grounded answer generator
  -> deterministic evidence metadata
```

`backend/application/learning_agent/` contains the typed models, planner, safe
tool projections, and orchestration service. Provider and tool collaborators
are injectable for deterministic tests.

## Approved tools

### `get_weak_topics`

Reuses `backend.application.weak_topics.get_weak_topics`. Limit is 1–5 and
recent history is 1–365 days or unbounded. Output is the already approved weak
topic contract with public document IDs converted to decimal strings before it
reaches the model.

### `get_recent_mistakes`

Reads a bounded recent attempt window from the scoped quiz repository. It
returns at most ten incorrect or skipped outcomes, newest first. Correct
options, explanations, answer keys, raw payloads, and full source excerpts are
not projected.

### `search_study_materials`

Reuses the existing workspace-filtered document chunk retrieval service. It
accepts at most five results, rejects empty, meaningless, and SQL-like
requests, omits embeddings and distance, and limits excerpts to 400 characters.

### `get_current_study_plan`

Calls the deterministic plan builder directly, bypassing the mutation in the
plan API wrapper. It returns at most five recommended items for 10–240
available minutes. The current data model has no persisted completion state or
deadline, so items are labeled `recommended` and deadlines are `null`.

## Tool result envelope

Every tool returns:

- `tool_name`
- `success`
- `data` containing only an explicit safe projection
- `safe_summary`
- `warning`
- `evidence_count`

Repository and ORM objects are never serialized directly to the model or API.
Tool failures are replaced with a generic safe envelope.

## Planner validation and fallback

The provider receives the user message, descriptions of exactly four tools,
and a strict Pydantic output schema. Structured output is validated again
against:

- a fixed tool-name allowlist;
- one call per tool;
- at most four total calls;
- per-tool argument schemas and limits;
- meaningful material queries;
- rejection of SQL-like search inputs; and
- no tool calls in general-answer mode.

One bounded repair request is attempted. If model creation, structured output,
validation, or repair fails, a narrow deterministic router handles obvious
weakness, mistake, material, and plan terms. It otherwise selects no tools.
Only a one-sentence routing summary is accepted, and that summary is never
returned to the client.

## Answer grounding

Answer generation receives only the user question and sanitized tool
envelopes. Personalized claims must use supplied evidence; general advice must
be labeled; missing evidence must be acknowledged; and the model may not claim
that an action was completed. Provider failure, empty output, excessive output,
or output containing sensitive internal markers triggers a deterministic safe
answer.

Evidence metadata is computed by application code, not the model:

- tools used;
- safe evidence summaries;
- related document public IDs;
- related quiz-attempt public IDs;
- weak topics used; and
- one suggested UI action.

The UI action is advisory. The frontend displays a link but never navigates or
executes an action automatically.

## Workspace security model

The agent router is registered with the same
`bind_protected_workspace` dependency as other protected APIs. The bearer
session selects a server-built request-scoped dependency bundle. The request
schema accepts only `message` and forbids extra fields, including
`workspace_id`, provider choices, tool overrides, SQL, prompts, or metadata.

The model never receives database connection settings, SQL credentials, session
or creation-key hashes, raw embeddings, unrestricted repositories, or another
workspace identifier. CockroachDB Managed MCP remains a development-only
facility and is not called at runtime.

## API and frontend

`POST /api/agent/query` accepts a non-empty message of at most 2,000 characters.
Its response contains a concise answer, tool names, evidence metadata, and a
suggested UI action. Public IDs serialize as decimal strings.

The `/agent` page adds:

- a visible **Ask Agentbook** shell entry;
- three starter prompts;
- bounded message input;
- loading and safe error states;
- an answer card;
- a human-readable **Based on** section; and
- a non-automatic suggested action link.

Internal tool names, public IDs, workspace identifiers, provider details, SQL,
and embeddings are not rendered.

## Tests

`tests/test_learning_agent.py` covers bounded routing, all four intents,
argument rejection, tool caps, structured-output repair/fallback, safe partial
failure, no-data behavior, prompt-injection refusal, output sanitization,
public IDs, protected API validation, and real SQLite Guest Workspace
isolation.

`frontend/src/test/learning-agent.integration.test.tsx` covers answer, loading,
error, evidence, suggested action, starter prompt submission, and suppression
of internal IDs/tool names.

## Known limitations

- Single-turn only; no agent conversation history is stored.
- The agent computes a current adaptive recommendation rather than reading a
  persisted task plan.
- Study-plan completion and deadline tracking do not yet exist.
- Read-only suggested links do not mutate anything. The two Phase 8B Study Task
  actions use a separate explicit confirmation endpoint.
- Provider requests use existing provider retry controls; there is no separate
  per-tool asynchronous timeout layer in this synchronous MVP.
- Material search quality depends on indexed document chunks and the configured
  embedding provider.
