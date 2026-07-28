# Workspace Data Consistency Audit

## Scope and conclusion

This audit traces Guest Session bootstrap, authenticated frontend requests,
request-scoped backend dependencies, CockroachDB ownership filters, mutation
invalidation, and response mapping across Agentbook.

The primary defect was in the frontend read cache rather than CockroachDB
ownership:

1. `apiClient.invalidate(...)` removed completed cache entries but left matching
   GET requests in flight.
2. A mutation followed by a page reload could therefore subscribe to a GET that
   began before the mutation. Its empty response could arrive after the write
   and repopulate the cache.
3. A deliberate or cross-tab Guest Session change updated the bearer token and
   cleared the cache, but already-mounted page queries were not remounted. They
   could continue displaying data from the previous workspace until another
   route change or full refresh.

This explains why upload and task writes could succeed while document lists,
Dashboard counts, or task lists still showed an older empty snapshot. A
duplicate upload was correctly detected from persisted data even while the
frontend displayed that stale snapshot.

## Controlled write/read trace

The live CockroachDB API was exercised with symbolic sessions only.

| Step | Session | Result |
|---|---|---|
| Inspect Guest Session | A | 200 |
| List notebooks/documents | A | 200; initially empty |
| Upload one harmless text file | A | 200; new document |
| List documents | A | Count increased by one |
| Load Dashboard | A | Document and unsorted-document counts increased |
| Create Study Task | A | 201 |
| List Study Tasks | A | Created task present |
| Reconnect using the same session | A | Identity, document, Dashboard, and task persisted |
| Upload identical bytes again | A | 200; correctly reported as duplicate |
| Initial reads | B | No Session A documents or tasks |
| Upload the same bytes | B | New document, consistent with workspace-scoped duplicate policy |

No credential, token-derived value, workspace identifier, document content, or
internal record identifier was recorded in this report.

## Frontend Guest Session audit

- The storage key is defined once in `GuestSessionProvider`.
- The provider withholds application routes while a stored session is being
  inspected, so user-data queries do not start before hydration succeeds.
- React Strict Mode can invoke the inspection effect twice, but it does not
  create a session. The API client deduplicates the concurrent inspection.
- Session creation occurs only from **Continue as Guest** or
  **Start a new study space**.
- Session creation is now serialized in the provider, preventing rapid repeated
  activation from creating two workspaces.
- Reusing the same restored token no longer invalidates its own inspection.
- A token changed by another same-origin browser tab is now observed through the
  `storage` event and re-inspected before the application resumes.
- A genuine token change increments a private session epoch and remounts
  application data consumers. Queries therefore reload under the new session.
- Invalid, expired, or revoked stored credentials are removed and return the
  user to the safe welcome boundary.

Browser storage remains origin-scoped. `localhost` and `127.0.0.1` are different
browser origins and cannot read each other's `localStorage`. Agentbook's
documented development origin is `http://127.0.0.1:5173`; users should keep one
origin when returning to a study space.

## Frontend authenticated API matrix

All network traffic is implemented through `frontend/src/api/client.ts`.
There is no Axios client, React Query client, page-local `fetch`, or separate
upload client. The only raw `fetch` calls are the canonical JSON request
executor and the canonical export download path.

| Feature | Methods and routes | Client/auth boundary | Cache and refresh behavior |
|---|---|---|---|
| Guest bootstrap | POST `/api/guest-session` | Canonical client; intentionally no bearer | No GET cache |
| Guest restore/inspect | GET `/api/guest-session` | Canonical client; current bearer | Forced fresh, zero TTL |
| Dashboard | GET `/api/dashboard` | Canonical client after auth hydration | Short GET cache; invalidated by library, study, and memory mutations |
| Notebooks | GET/POST/PATCH/DELETE `/api/notebooks...` | Canonical client; current bearer | Library mutations invalidate notebook, document, topic, and Dashboard prefixes |
| Documents/upload | GET/POST/PATCH/DELETE `/api/documents...` | Canonical multipart/JSON client; same current bearer | Upload and assignment invalidate library and Dashboard; page reloads active queries |
| Summaries/topics | GET/POST document/notebook/topic routes | Canonical client; current bearer | Scope-specific invalidation |
| Chat/study sessions | POST/PATCH/GET chat and session routes | Canonical client; current bearer | Study, report, integrity, and Dashboard invalidation |
| Learning Agent | POST `/api/agent/query` | Canonical client; current bearer | No persistent client-side result cache |
| Study Tasks | GET/POST/PATCH lifecycle routes | Canonical client; current bearer and idempotency header | Task prefix invalidated; active task query explicitly reloads |
| Memories | GET/POST/PATCH/DELETE `/api/memories...` | Canonical client; current bearer | Memory, integrity, and Dashboard invalidation |
| Quizzes/study plans/coaching | Study action and quiz routes | Canonical client; current bearer | Study/report/Dashboard invalidation after persisted mutations |
| Reports/quiz history | GET/POST `/api/reports...` | Canonical client; current bearer | Read cache scoped by URL |
| Integrity/export | GET `/api/system/integrity`, `/api/system/export` | Canonical client/download boundary; current bearer | Integrity can be explicitly refreshed; export is uncached |
| Health | GET `/api/health` | Canonical client; public service metadata only | Short GET cache |

Cache invalidation now removes and aborts matching in-flight GET entries as well
as completed entries. A post-mutation reload can no longer reuse a response that
started before the mutation.

## Backend route and workspace matrix

`backend/api/app.py` registers every user-data router with the same
`Depends(bind_protected_workspace)` dependency. The dependency authenticates
the bearer credential, derives the workspace on the server, creates a
workspace-scoped dependency bundle, binds it for the request, and resets it
afterward.

| Feature/router | Authentication | Workspace flow and query scope |
|---|---|---|
| Dashboard | Shared protected dependency | Workspace-scoped dashboard repository; every count and recent-item query filters by workspace |
| Documents/uploads/notebooks | Shared protected dependency | Same scoped library repository for duplicate lookup, insert, assignment, list, and detail |
| Intelligence/topics | Shared protected dependency | Scoped document/notebook/intelligence repositories and owned-source joins |
| Chat/study sessions | Shared protected dependency | Scoped study-session repository and workspace-owned sources |
| Quiz/coaching/plans/weak topics | Shared protected dependency | Scoped quiz, study, signal, workflow, and document repositories |
| Learning Agent | Shared protected dependency | Uses the request dependency bundle; no client-supplied workspace |
| Study Tasks | Shared protected dependency | Scoped task repository for create, list, update, lifecycle, and events |
| Memories/vectors | Shared protected dependency | Scoped relational and vector repositories |
| Reports | Shared protected dependency | Uses the same scoped session, quiz, document, and memory repositories |
| Export/integrity | Shared protected dependency | Receives the server-resolved workspace; no request workspace override |
| Guest Session inspect | Explicit Guest principal dependency | Resolves only the authenticated session's safe metadata |
| Health | Public | Returns service status only; no user data |

Production requests do not accept a `workspace_id` field, query parameter, or
workspace override header. Missing or invalid bearer credentials return a safe
401 rather than binding the default workspace. The legacy default-workspace
path is gated by `ALLOW_LEGACY_DEFAULT_WORKSPACE` and is disabled in the live
application. Default constants that remain in low-level SQLite compatibility
functions and migration tooling are not reachable as a fallback from normal
protected production requests.

## Database and response-contract findings

- CockroachDB document duplicate detection uses the same workspace-scoped
  repository as document listing.
- Dashboard counts and unsorted-document counts filter by the same workspace.
- Study Task create and list operations use the same scoped repository.
- Ownership joins include workspace equality.
- Public IDs remain decimal strings at API and frontend boundaries.
- No production frontend code uses `Number` or `parseInt` for public IDs.
  Numeric conversions found in the UI are limited to bounded form values such
  as question count, duration, and importance.
- Document and task list responses use `{items, total}` and the pages consume
  those envelopes correctly.
- Snake-case response names, null due dates, task statuses, notebook types, and
  Dashboard count field names match the TypeScript contracts.
- Success payloads do not serialize workspace identifiers, internal UUIDs,
  event internals, or idempotency storage.

## Fix

### Frontend

1. Matching invalidation now aborts and removes in-flight GETs before a fresh
   read can start.
2. Setting the same Guest token is a no-op, avoiding Strict Mode self-aborts.
3. Guest Session creation is serialized.
4. Same-origin cross-tab token changes trigger safe re-inspection.
5. A real session change remounts application data consumers through a private
   epoch, forcing all workspace queries to reload with the current bearer.

### Backend

No backend production fix was required. The controlled live flow and repository
audit confirmed consistent request-scoped workspace resolution and direct
workspace filters for writes, reads, counts, and duplicate detection.

## Regression coverage

New or expanded tests cover:

- stale in-flight GET invalidation after a mutation;
- hydration before any user-data query;
- identical bearer use for Dashboard, notebook, upload, document list, task
  create, and task list;
- one session creation under rapid repeated activation;
- refresh restoration without creating another workspace;
- deliberate workspace switching and query remount;
- same-origin cross-tab token synchronization;
- upload/list/Dashboard/task consistency;
- duplicate detection in the writing workspace;
- Session B isolation;
- missing and invalid credentials returning 401;
- workspace-scoped same-file behavior in the live CockroachDB flow;
- decimal-string public IDs and absence of internal workspace fields.

## Manual verification

The live controlled API flow passed for Session A and Session B. Session A's
document, Dashboard counts, and Study Task persisted across a new client
connection. Session B initially saw none of Session A's data. The same file was
duplicate only inside Session A and was a new document in Session B.

The post-fix browser flow also passed on the documented development origin:

- a fresh Session A began with zero documents, notebooks, and tasks;
- uploading one harmless file displayed one unsorted document and increased
  the Dashboard document and unsorted-document counts;
- creating one harmless task displayed it immediately;
- a full page refresh retained the task and a later document-page navigation
  retained the document;
- uploading the same file again showed the duplicate outcome and retained a
  single document;
- after intentionally starting Session B, Dashboard counts were zero, the
  document list was empty, and the task list was empty.

## Validation results

- Python compileall passed.
- Targeted backend Guest Session, document, Dashboard, Study Task, Learning
  Agent, public-ID, and workspace-consistency tests passed: 86 tests.
- Full backend suite passed: 200 tests, with 6 environment-gated skips.
- Targeted frontend API/auth/bootstrap/Study Task/public-ID tests passed:
  28 tests.
- Full frontend suite passed: 61 tests across 14 files.
- TypeScript checking and the Vite production build passed.
- Credential-pattern scanning found no committed or newly added real
  credentials.
- `git diff --check` passed.

## Recoverability and limitations

The fix does not delete or move existing data. Data written into earlier Guest
Workspaces remains in CockroachDB and remains recoverable with the corresponding
browser credential on the same browser origin. Agentbook intentionally cannot
enumerate or expose workspace identifiers to recover a credential that was
cleared from browser storage.

No Phase 8B work is included in this change.
