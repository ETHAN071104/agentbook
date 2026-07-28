# Persisted Study Tasks audit

## Summary

Agentbook's existing Study Plan is a deterministic recommendation computed from
current study outcomes, quiz history, learner memories, and learning signals.
It is not a persisted plan or task list. Phase 8A should therefore add Study
Tasks as a separate workspace-owned product aggregate and leave Study Plan and
the read-only Learning Agent unchanged.

The smallest safe integration path is:

```text
protected /api/study/tasks routes
  -> request-scoped StudyTaskService
  -> workspace-bound StudyTaskRepository
  -> study_tasks plus study_task_events
  -> typed frontend API
  -> dedicated /tasks page
```

## Existing capability findings

1. **Study Plan models and services** — `backend/study/planner.py` defines
   immutable computed `AdaptiveStudyPlan`, `StudyPlanItem`, and evidence models.
   `build_adaptive_study_plan` reads current evidence and returns a value; it
   does not persist tasks.
2. **Study Plan API and frontend** — the Study Actions API wrapper records an
   `AdaptationEvent` after computing a plan. `StudyActionsPage` displays the
   returned recommendation in process memory. There is no task CRUD or
   completion state.
3. **Repository protocols** — `ApplicationDependencies` supplies repositories
   already bound to one server-resolved workspace. Protocol methods operate on
   public integer IDs and adapters put `workspace_id` directly in their
   queries.
4. **Cockroach adapter conventions** — Cockroach records use UUID primary keys
   plus workspace-unique `INT8 public_id` values derived from UUIDs. SQLAlchemy
   `text()` statements use named parameters, and response models convert
   timestamps to UTC ISO strings.
5. **SQLite adapter conventions** — legacy/test records use integer primary
   keys as public IDs. `initialize_foundation_schema` creates additive
   workspace-owned tables and indexes in isolated test databases.
6. **Migration conventions** — Cockroach schema changes use Alembic SQL
   revisions under `alembic/versions`. Revision `0003_guest_sessions` is the
   current head. Phase 8A requires an additive `0004` revision; it must not be
   applied automatically to an unknown cluster.
7. **Public IDs** — API inputs use `PublicIdInput`; outputs use `PublicId`, which
   serializes exact Python integers as decimal strings. Cockroach lookup
   queries match both `workspace_id` and `public_id`.
8. **Audit events** — `AdaptationEvent` records how learner memories and
   learning signals changed AI workflows. Its required memory/signal fields and
   workflow meaning are inappropriate for ordinary task lifecycle auditing.
9. **Idempotency** — Guest-session creation already accepts bounded
   `Idempotency-Key` headers and relies on workspace-safe uniqueness.
   Study-task creation can reuse the HTTP convention while scoping keys to a
   workspace and binding each key to a request fingerprint.
10. **Frontend conventions** — routes use typed endpoint modules,
    `useApiQuery`, `useAsyncAction`, shared cards/buttons/states, explicit cache
    invalidation, accessible labels, and React Router shell navigation.
11. **Guest Workspace flow** — protected routers use
    `Depends(bind_protected_workspace)`. This authenticates the bearer session
    and binds a workspace-specific dependency bundle before the route runs.
12. **Time and enums** — stored timestamps are UTC ISO strings in SQLite and
    `TIMESTAMPTZ` values normalized to UTC in Cockroach. Small status enums are
    enforced in application validation and database checks.

## Reuse

- Protected-router workspace binding and request-scoped dependencies.
- Exact public-ID parsing and serialization.
- Cockroach UUID/public-ID generation and timestamp helpers.
- SQLite foundation initialization for test compatibility.
- Existing typed API client, hooks, and UI state components.
- Existing `RepositoryConflictError` mapping conventions.
- `Idempotency-Key` header shape and CORS allowance.

## Required additions

- `StudyTask` and `StudyTaskEvent` domain models.
- A workspace-bound `StudyTaskRepository` protocol.
- SQLite and Cockroach implementations.
- An additive Cockroach Alembic revision.
- A validation/transition application service.
- Protected task CRUD/lifecycle routes and schemas.
- A dedicated `/tasks` frontend page and typed API methods.
- Backend, frontend, migration, isolation, and regression tests.

## Persisted tasks versus computed plans

| Computed Study Plan | Persisted Study Task |
| --- | --- |
| Rebuilt from current evidence | Stored until archived or deleted by retention policy |
| Recommendation only | Explicit learner-owned action |
| No completion/deadline state | Pending/completed/cancelled/archived lifecycle |
| May cite study and quiz evidence | Manually entered title, description, topic, and due time |
| Adaptation event describes recommendation logic | Task event records a narrow lifecycle change |
| Read-only Learning Agent may summarize it | Learning Agent receives no task write capability in Phase 8A |

No plan recommendation will be silently converted into a task.

## Data-model decision

Cockroach `study_tasks` will use an internal UUID and a workspace-unique exact
integer public ID. SQLite will use its integer primary key as the public ID.
Both will store:

- workspace ownership;
- title, bounded description, optional topic;
- status: `pending`, `completed`, `cancelled`, or `archived`;
- priority: `low`, `normal`, or `high`;
- optional UTC due time;
- completion/archive timestamps;
- creation/update timestamps;
- optimistic version counter; and
- nullable creation idempotency key plus SHA-256 request fingerprint.

`study_task_events` will store only the task relation, event type,
previous/new status, and timestamp. It intentionally omits descriptions,
prompts, arbitrary JSON, credentials, and model data.

## Source-link decision

Phase 8A supports an optional bounded topic but defers source-document linkage.
The current `documents` table does not expose a composite foreign key target for
`(workspace_id, public_id)`. Adding a weak document foreign key would allow a
future adapter bug to create a cross-workspace relation, while adding and
validating a new composite uniqueness contract expands this phase unnecessarily.
A future additive revision can add a workspace-safe source relation.

## Status and idempotency decision

- `pending -> completed`
- `completed -> pending`
- `pending -> cancelled`
- `cancelled -> pending`
- any non-archived status `-> archived`
- duplicate complete, reopen, cancel, and archive calls are no-ops
- archived tasks are terminal

Creation requires an `Idempotency-Key`. The key is unique only within its
workspace and is bound to a canonical request fingerprint. Replaying the same
request returns the original task without a second event; reusing the key with
different input returns a conflict. PATCH replay with identical values and
duplicate lifecycle calls likewise create no duplicate event.

## Security boundary

Task routes will accept no workspace, internal ID, lifecycle timestamp,
arbitrary metadata, event payload, provider setting, or SQL input. Every
repository read and mutation will include workspace ownership in the database
statement. Cross-workspace misses will use the same not-found response as
missing tasks. Task text remains untrusted display data and is not sent to an
LLM in Phase 8A.
