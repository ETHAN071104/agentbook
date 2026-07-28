# Confirmed Learning Agent Write Tools Audit

## Scope

This audit covers the existing Phase 7 Learning Agent, Phase 8A Study Tasks,
Guest Workspace authentication, workflow persistence, API validation, and the
Learning Agent and Study Tasks frontend pages. It defines the smallest safe
Phase 8B architecture for two confirmed actions only:

- `create_study_task`
- `complete_study_task`

No code was changed before this audit was completed.

## Reusable Learning Agent boundaries

The current Learning Agent already has a useful separation:

- `LearningAgentPlanner` produces a Pydantic-validated bounded plan.
- A hardcoded tool allowlist limits runtime tools to four read-only operations.
- `LearningAgentTools` resolves request-scoped application dependencies and
  asserts repository workspace alignment.
- Tool outputs are projected into bounded, sanitized evidence.
- `query_learning_agent` refuses SQL-like, credential-seeking,
  cross-workspace, and prompt-override requests.
- `POST /api/agent/query` is protected by the same
  `bind_protected_workspace` dependency as every other user-data route.
- API models inherit `ApiModel`, whose `extra="forbid"` setting rejects unknown
  request fields.

The planner must be extended from general/personalized routing to the explicit
modes `answer_only`, `read_only_tools`, and `propose_write`. The planner may
propose only one allowlisted write action, and its candidate arguments must be
validated by action-specific Pydantic models. It must never execute an action.

## Reusable Study Task boundaries

`StudyTaskService` is the correct mutation boundary:

- create validation covers title, description, topic, priority, due timestamp,
  and a server-required idempotency key;
- all repositories are request/workspace scoped;
- CockroachDB create idempotency is unique by workspace and operation key;
- mutations join the active Unit of Work transaction;
- completion is idempotent at the repository state-transition layer;
- creation and completion emit exactly one existing Study Task lifecycle event;
- public task IDs are converted to decimal strings by the API schema;
- cross-workspace reads and mutations return the same safe not-found outcome.

Phase 8B should reuse this service rather than call repositories from the Agent
or duplicate task mutation rules.

## Reusable proposal persistence

The existing `workflow_states` persistence is suitable for Phase 8B, so no new
table is necessary. It already provides:

- a UUID workflow/proposal identifier;
- `workspace_id` ownership with cascading workspace deletion;
- a workflow type;
- a server-stored payload;
- pending and terminal statuses;
- created, updated, and expiry timestamps;
- optimistic versioning;
- workspace/type/status/expiry indexing;
- CockroachDB and SQLite implementations;
- request-scoped repository composition;
- transaction participation through the active Unit of Work connection.

The payload can store only a validated action-specific snapshot and a safe
operation hash. It must never store the raw prompt, model reasoning, document
content, credentials, or arbitrary unvalidated metadata.

## Existing frontend behavior

The frontend has one authenticated `ApiClient`. Learning Agent and Study Task
requests already use it, so no second authentication path is needed. Study Task
mutations already invalidate the Study Task cache. Phase 8B confirmation should
use the same client, call only the confirmation endpoint, and invalidate the
same `/api/study/tasks` prefix after success.

The current Learning Agent page renders read-only answers and safe suggested
links. It can be extended with a proposal card without exposing tool JSON,
workspace identity, task identifiers, or stored proposal arguments.

The Study Tasks `Current` filter remains ambiguous. This is a final UI-polish
backlog item; it does not require a task-filter redesign in Phase 8B.

## Confirmation threat model

The confirmation design must defend against:

- a browser modifying the action, title, due date, priority, or target task;
- a model supplying a workspace ID, task ID, idempotency key, SQL, or an
  unsupported action;
- replay through double-clicks, repeated requests, or parallel confirmations;
- confirming another workspace's proposal;
- an expired proposal;
- a proposal consumed by a previous request;
- a target task that was removed, completed, archived, cancelled, or edited
  after the proposal was prepared;
- a partial failure that creates/completes a task but reports the proposal as
  pending, or consumes a proposal without committing the task mutation;
- prompt injection asking the Agent to skip confirmation or execute SQL.

The LLM is untrusted because its output is probabilistic and influenced by user
text and retrieved content. It may help classify intent and prepare candidate
arguments, but it must never receive database credentials, choose a workspace,
generate an executable idempotency key, call repositories, execute SQL, or
claim that a write succeeded.

## Smallest safe architecture

### Proposal creation

1. The protected Agent query resolves the Guest Workspace on the server.
2. The bounded planner selects `propose_write`, at most one action, optional
   read-only tools, and typed candidate arguments.
3. Read-only evidence is gathered when required.
4. The proposal service revalidates create arguments through the normal Study
   Task validation boundary, or resolves one exact pending task through a
   bounded workspace-scoped lookup.
5. The server stores a ten-minute `agent_action_proposal` workflow containing
   only normalized action-specific data, expected task state/version when
   applicable, and a safe operation hash bound to the workspace.
6. The browser receives only an opaque proposal ID and a safe display
   projection.
7. No Study Task write occurs during the Agent query.

### Confirmation

1. The browser posts `{ "confirm": true }` to the protected proposal-specific
   confirmation endpoint. No business arguments are accepted.
2. The server loads the proposal through the authenticated workspace's
   workflow repository.
3. It validates workflow type, pending status, expiry, action allowlist,
   action-specific payload, workspace-bound operation hash, and expected target
   state.
4. One Unit of Work executes the existing Study Task service and marks the
   workflow completed on the same connection.
5. CockroachDB serializable retry behavior can replay the callback safely:
   create uses a server-derived proposal idempotency key and completion uses a
   guarded status transition.
6. The response is constructed only after the transaction commits and contains
   the persisted task's safe public projection.

This transactional ordering means a failed task mutation leaves the proposal
pending, while a failed proposal claim rolls back the task mutation and its
lifecycle event.

## Replay, tampering, and isolation prevention

- **Replay:** workflow status/version is changed from pending to completed in
  the same transaction as the task write. Repeated or parallel confirmations
  cannot perform a second mutation.
- **Create idempotency:** the server derives the Study Task idempotency key from
  the proposal ID; the model and browser cannot supply it.
- **Completion idempotency:** the proposal stores the exact server-resolved
  public task ID, pending status, and version. A changed target is rejected.
- **Tampering:** the browser never returns proposal arguments. The server
  reloads its stored immutable payload and validates it again before execution.
- **Cross-workspace access:** the workflow and task repositories both filter by
  the request-scoped workspace. A proposal from another workspace is
  indistinguishable from a nonexistent proposal.
- **Expiry:** the server compares the stored expiry with the current UTC time;
  expired workflows cannot execute.
- **Unsupported actions and fields:** literals, discriminated action models,
  `extra="forbid"`, and a hardcoded action dispatcher reject them.

## Planned API and UI contract

- `POST /api/agent/query` remains the initial protected endpoint and may return
  `confirmation_required=true` with one safe proposal projection.
- `POST /api/agent/actions/{proposal_id}/confirm` accepts only a positive
  confirmation boolean and returns the persisted task after commit.
- The Learning Agent page displays Create or Complete details, makes clear that
  nothing has changed yet, and offers Confirm and Cancel.
- Cancel is a local dismissal; the server-side proposal remains harmless and
  expires after ten minutes.
- Successful confirmation disables further confirmation, invalidates Study
  Task reads, and offers an Open Study Tasks link.

## Migration conclusion

No Phase 8B migration is required. Reusing `workflow_states` is additive at the
application level, works with the currently deployed CockroachDB schema, avoids
a redundant proposal table, and preserves SQLite compatibility.

