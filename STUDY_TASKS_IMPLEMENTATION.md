# Persisted Study Tasks implementation

## Product behavior

Study Tasks are persisted, workspace-scoped learner actions managed through
normal authenticated APIs. Learners can create, list, view, edit, complete,
reopen, cancel, and archive tasks. A task may include a bounded description,
topic, priority, and timezone-aware due date.

Study Tasks are not Learning Agent tools. Phase 8A adds no model-selected write,
automatic task creation, background work, reminders, calendar integration, or
conversation persistence.

## Schema

Alembic revision `0004_persisted_study_tasks` adds:

### `study_tasks`

- internal Cockroach UUID primary key;
- workspace-scoped exact `INT8` public ID;
- workspace ownership foreign key;
- title, description, and topic;
- explicit status and priority;
- optional due, completion, and archive timestamps;
- creation/update timestamps;
- optimistic version counter; and
- nullable creation idempotency key plus SHA-256 request fingerprint.

SQLite test/local compatibility uses an integer primary key as the public ID
and otherwise mirrors the same constraints.

Useful indexes cover:

- workspace, status, due date, and recent update ordering; and
- pending tasks by workspace and due date.

### `study_task_events`

The lifecycle-event table stores only:

- internal event ID;
- workspace-owned task relationship;
- event type;
- previous and new status; and
- creation timestamp.

A composite `(task_id, workspace_id)` foreign key prevents an event from being
related to a task in another workspace. The table contains no description,
prompt, model data, arbitrary JSON, token, or credential field.

## Migration

- Revision: `0004_persisted_study_tasks`
- Parent: `0003_guest_sessions`
- Change type: additive
- Downgrade: drops `study_task_events`, then `study_tasks`
- Production status: not applied automatically

`alembic heads` and `alembic history` recognize `0004` as the single current
head. The SQLite-compatible schema is created in isolated tests through the
existing foundation initializer. No unknown production Cockroach cluster was
modified.

## Status model

Statuses:

- `pending`
- `completed`
- `cancelled`
- `archived`

Allowed transitions:

```text
pending -> completed
completed -> pending
pending -> cancelled
cancelled -> pending
pending/completed/cancelled -> archived
```

Archived tasks are terminal and cannot be edited. Completing an already
completed task, reopening an already pending task, cancelling an already
cancelled task, and archiving an already archived task are idempotent no-ops.
Reopening clears `completed_at`; completing sets it; archiving sets
`archived_at` and preserves prior completion history when applicable.

Priorities are `low`, `normal`, and `high`.

## API

All routes are protected by the existing Guest Workspace bearer dependency:

```text
POST   /api/study/tasks
GET    /api/study/tasks
GET    /api/study/tasks/{task_public_id}
PATCH  /api/study/tasks/{task_public_id}
POST   /api/study/tasks/{task_public_id}/complete
POST   /api/study/tasks/{task_public_id}/reopen
POST   /api/study/tasks/{task_public_id}/cancel
POST   /api/study/tasks/{task_public_id}/archive
```

Lists support bounded status, due-before, due-after, archive inclusion, and
limit filters. The default limit is 50 and maximum is 100. Results order
pending tasks first, then nearest due date, then recent updates. Archived tasks
are excluded unless explicitly requested.

Request models forbid unknown fields. They accept no workspace ID, internal ID,
completion/archive timestamp, event payload, metadata dictionary, provider
setting, prompt, or SQL field.

Responses contain exact decimal-string public IDs and user-facing task fields.
They omit workspace ownership, internal UUIDs, version, idempotency storage,
and event internals.

## Workspace isolation

The bearer session binds a workspace-specific `ApplicationDependencies` bundle
before route execution. `StudyTaskService` rejects a mismatched repository
scope. Every adapter query includes workspace ownership in the SQL statement;
task reads never fetch globally and authorize afterward.

Cross-workspace reads and mutations return the same 404 shape as a nonexistent
task, preventing existence disclosure. Idempotency uniqueness is
`(workspace_id, creation_idempotency_key)`, so one learner's key cannot collide
with another learner's operation.

## Idempotency and concurrency

Task creation requires an `Idempotency-Key` containing 16–200 safe characters.
The service fingerprints canonical validated task input:

- replaying the same key and same input returns the original task;
- replaying the same key with different input returns 409;
- keys are independent across workspaces; and
- duplicate creation writes no second lifecycle event.

Lifecycle changes lock/read the owned task in the Cockroach transaction and
use an expected previous status in the update. SQLite serializes local
mutations through its existing transaction behavior. Identical PATCH replay
and duplicate lifecycle replay create no extra event. The stored version
increments on actual changes but is intentionally not exposed in Phase 8A.

## Audit events

The implementation uses a dedicated task lifecycle event table because
`AdaptationEvent` represents memory/signal-driven AI adaptation rather than a
normal learner CRUD action.

Event types:

- `study_task_created`
- `study_task_updated`
- `study_task_completed`
- `study_task_reopened`
- `study_task_cancelled`
- `study_task_archived`

Task mutation and its event share one repository transaction. Idempotent
replays do not add events.

## Frontend UX

The `/tasks` page and **Study Tasks** navigation entry provide:

- create form with mirrored field limits;
- optional topic, due date, and priority;
- current/pending/completed/cancelled/archived filters;
- accessible loading, empty, and error states;
- status and text treatment for completed tasks;
- edit form;
- complete, reopen, cancel, and archive controls; and
- responsive task cards without drag-and-drop or kanban complexity.

The UI never displays workspace IDs, internal UUIDs, versions, event internals,
or idempotency keys. Public task IDs are used only in API paths.

## Study Plan distinction

Computed Study Plans remain evidence-based recommendations generated by
`build_adaptive_study_plan`. Persisted Study Tasks remain explicit
learner-entered commitments. Phase 8A does not automatically copy plan items
into tasks and does not add write tools to the Learning Agent.

## Security review

- No endpoint accepts or trusts a client workspace ID.
- Every read and mutation filters by workspace in the database query.
- Composite ownership prevents cross-workspace task-event relations.
- Public API output contains no internal UUID, version, event, or idempotency
  storage field.
- Unknown fields and arbitrary status/priority values are rejected.
- Descriptions are stored and rendered as untrusted plain text; they are not
  executed as SQL/templates or sent to an LLM.
- Parameterized SQL carries every learner-entered value.
- Audit rows contain no title, description, source content, prompt, secret, or
  arbitrary payload.
- Source-document linkage is deferred rather than implementing a weak
  cross-workspace relationship.

## Tests

Verification completed with:

- Python compileall: passed;
- Alembic head/history validation: passed, with `0004` as the single head;
- targeted Study Task backend tests: 31 passed;
- complete backend suite: 199 passed, 6 authorized live tests skipped;
- targeted Study Task frontend tests: 11 passed;
- complete frontend suite: 54 passed;
- frontend production build: passed;
- focused Learning Agent, weak-topic, Guest isolation, and public-ID
  regressions: 50 passed;
- targeted Learning Agent plus Study Task frontend regressions: 18 passed;
- credential scan: zero potential credential-bearing files;
- sensitive-config change scan: zero files; and
- `git diff --check`: passed.

The targeted backend suite covers creation, validation, exact public IDs,
workspace isolation, indistinguishable not-found behavior, all lifecycle
transitions, idempotency, due ordering/filtering, archive defaults, audit-event
cardinality, adapter mapping parity, and migration structure.

The frontend suite covers task rendering, empty/loading/error states, creation,
completion, reopen, filtering, editing, form validation, idempotency headers,
and suppression of IDs.

## Known limitations and Phase 8B preparation

- No source-document relation yet; topic text is supported.
- No delete endpoint; archive preserves history.
- No reminders, recurrence, notifications, sharing, or calendar integration.
- No user-visible event history.
- Optimistic version is stored but not yet an API precondition.
- The Phase 8B Learning Agent can prepare confirmed create/complete actions
  only; all other task lifecycle controls remain manual.

The narrow service methods, transactionally audited transitions, scoped
idempotency, and explicit schemas provide the foundation for Phase 8B.
Phase 8B should still require explicit user confirmation and must call these
application services rather than exposing repositories or SQL.
