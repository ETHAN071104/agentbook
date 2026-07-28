# Confirmed Learning Agent Write Tools Implementation

## Product behavior

Agentbook's Learning Agent can prepare two low-risk Study Task actions:

- create one Study Task;
- complete one exact pending Study Task.

The initial natural-language request never writes to the database. It produces
either a normal read-only answer, a truthful clarification/no-match answer, or
a visible confirmation proposal. Only an explicit confirmation request can
execute the stored operation.

The Agent does not reopen, cancel, archive, edit, or delete tasks; modify Study
Plans; write Learner Memory; create reminders or recurring work; integrate with
calendars; or run background or multi-agent workflows.

## Confirmation architecture

```text
authenticated Agent query
  -> bounded planner
  -> optional approved read-only tools
  -> action-specific validation
  -> server-stored ten-minute proposal
  -> safe confirmation card

explicit Confirm
  -> protected proposal-specific endpoint
  -> workspace-owned proposal lookup
  -> expiry/status/hash/target-state validation
  -> one Unit of Work
       -> existing Study Task service
       -> existing lifecycle event
       -> proposal status completed
  -> persisted task response
```

The planner supports exactly three modes: `answer_only`, `read_only_tools`, and
`propose_write`. `propose_write` permits at most one action. The LLM may prepare
candidate values, but hardcoded schemas and application code make every
authorization, matching, validation, and execution decision.

## Proposal persistence design

Phase 8B reuses the existing `workflow_states` table with workflow type
`agent_action_proposal`; no migration is required.

Each proposal stores:

- an opaque UUID proposal ID;
- workspace ownership in the workflow row;
- one allowlisted action;
- normalized action-specific arguments;
- a short safe evidence summary and learner-facing rationale;
- an operation hash bound to the proposal ID, workspace, action, and normalized
  arguments;
- pending/completed/expired state, version, and timestamps;
- a ten-minute expiry.

The stored payload excludes raw prompts, hidden reasoning, document content,
embeddings, credentials, bearer data, database settings, SQL, and arbitrary
unvalidated metadata.

The browser receives only a safe projection: proposal ID, action, display
labels, task preview, evidence summary, expiry, and low-risk classification.
It never receives the internal task target, expected version, workspace,
operation hash, or idempotency storage.

## Create Study Task

The proposal accepts only title, description, topic, timezone-aware due
timestamp, and priority. Candidate input is normalized through
`StudyTaskService.prepare_create_task`, so Phase 8B uses the same limits and
timestamp rules as the normal Study Task API.

Evidence-assisted requests may use an actual weak-topic or current-plan tool
result. If no evidence supplies a concrete topic, Agentbook returns a truthful
no-proposal answer rather than inventing a weakness.

Confirmation derives a server-only idempotency key from the proposal ID and
calls the existing `StudyTaskService.create_task`.

## Complete Study Task

Completion uses an internal, bounded lookup of at most 50 pending tasks in the
authenticated workspace. Matching considers normalized title and topic:

- zero matches returns a truthful no-match answer;
- one exact match produces a proposal;
- multiple matches return up to three safe task labels and ask for an exact
  title;
- no public or internal ID is shown in the confirmation card.

The server-stored proposal contains the server-resolved public task ID,
expected pending status, expected version, and a safe display snapshot. The
model cannot supply or override the target. Confirmation rejects a missing,
completed, cancelled, archived, or edited target.

## API

### Initial request

```text
POST /api/agent/query
```

The existing protected endpoint may now return
`confirmation_required=true` and one safe proposal. It never reports a task as
created or completed before confirmation.

### Confirmation

```text
POST /api/agent/actions/{proposal_id}/confirm
```

The body is exactly:

```json
{"confirm": true}
```

Unknown fields are rejected. The endpoint accepts no workspace, action,
task-ID, title, due-date, provider, model, SQL, metadata, or idempotency
override.

The response contains `executed`, the action, the persisted task's normal safe
projection, a user-facing message, and `open_study_tasks`.

## Idempotency, replay, and race safety

Proposal validation, task mutation, lifecycle-event insertion, and workflow
completion run on the same Unit of Work connection.

- SQLite uses `BEGIN IMMEDIATE` to serialize confirmation writers.
- CockroachDB uses the existing serializable Unit of Work and bounded SQLSTATE
  `40001` retry callback.
- Create retries use the proposal-derived server idempotency key.
- Completion retries use the pending-state transition and stored expected
  version.
- A consumed workflow cannot execute again.
- Parallel confirmations execute at most once.
- If proposal completion conflicts, the task mutation and event roll back.
- If task execution fails, the workflow remains unconsumed.
- Repeated completion cannot add a second completion lifecycle event.

## Workspace isolation

Both the workflow repository and Study Task repository are created from the
same request-scoped `ApplicationDependencies` bundle. Each filters directly by
workspace. Cross-workspace proposal confirmation returns the same safe
not-found response as a nonexistent proposal, and another workspace's task
cannot be selected by the completion matcher.

## Frontend confirmation UX

The Ask Agentbook page displays:

- Create or Complete Study Task;
- title, current/proposed status, topic, due date, priority, and applicable
  description;
- safe evidence/rationale;
- low-risk and expiry information;
- Confirm and Cancel controls.

States include ready, confirming, confirmed, locally cancelled, expired,
already executed, and safe error. The UI says that nothing has changed before
confirmation. After success, the Confirm button is removed, Study Task caches
are invalidated, and an Open Study Tasks link is shown. Double-clicks share one
in-flight confirmation request.

Cancel is a local dismissal and performs no mutation. The unused server
proposal expires automatically.

## Audit behavior

Actual task creation and completion reuse existing lifecycle events:

- `study_task_created`
- `study_task_completed`

Proposal-specific audit rows were not added because the existing workflow row
already records safe pending/completed/expired state without expanding the
Study Task event model. No prompt, model reasoning, or task content is copied
into lifecycle events.

## Security review

- The LLM never receives database credentials and never executes SQL.
- The LLM never calls repositories or chooses a workspace.
- The browser cannot modify proposal arguments or swap the task target.
- Proposal ownership is server-bound and checked at query and confirmation.
- Confirmation is short-lived, single-use, and explicitly learner-triggered.
- The original Agent query never writes a Study Task.
- Unsupported actions and fields are rejected by literals, typed models, and
  hardcoded dispatch.
- Prompt requests for SQL, another workspace, or bypassed confirmation are
  refused.
- No hidden chain-of-thought is stored or returned.
- Task text remains untrusted plain text if later used as model input.
- CockroachDB Managed MCP is not used by the runtime Agent.

## Known limitations

- Agent actions are limited to create and complete.
- The Agent is single-turn and has no conversation-reference resolution for
  phrases such as “this topic” unless current evidence supplies a concrete
  item.
- “Tomorrow” uses the backend host's local timezone and proposes 09:00 local
  time because Agentbook has no learner-timezone preference yet.
- Cancel is a local dismissal; the server proposal remains non-executable from
  the visible card and expires within ten minutes.
- The Study Tasks `Current` filter remains an explicit final UI-polish backlog
  item. It should become All or Pending and have unnecessary states simplified.

## Validation

Completed validation:

- Python compileall passed for the backend and tests.
- 25 targeted Agent write-tool tests passed.
- 86 combined Agent write-tool, Learning Agent, and Study Task tests passed.
- The full backend suite passed: 225 tests, with 6 opt-in live tests skipped.
- The targeted Learning Agent frontend suite passed: 17 tests.
- The full frontend suite passed: 71 tests across 14 files.
- The TypeScript and Vite production build passed.
- Alembic reports the unchanged single head
  `0004_persisted_study_tasks`; Phase 8B adds no migration.
- Credential-pattern scanning and `git diff --check` passed.
