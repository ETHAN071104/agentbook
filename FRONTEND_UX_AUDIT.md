# Agentbook frontend UX simplification audit

## Audit scope and constraints

This is an audit-only decision document. No frontend source, backend source, route, API, database schema, or application data was changed.

Evidence reviewed:

- Route registration and page composition in `frontend/src/App.tsx`.
- Desktop and mobile navigation in `frontend/src/layouts/AppShell.tsx`.
- Every page in `frontend/src/pages`.
- Frontend API use, routing tests, public-ID tests, Guest Workspace tests, Study Task tests, Learning Agent tests, and study-flow tests.
- A read-only walkthrough of the running application at an empty Guest Workspace. Screenshots were captured locally for the dashboard, mobile navigation, library, chat, Ask Agentbook, practice, progress, learner memory, and system screens. They were intentionally not added to the repository because the requested deliverables are exactly these two Markdown files.

Accessibility observations are limited to source semantics and the states available in the empty workspace. The audit did not run a screen reader or automated contrast checker, and it did not submit forms, upload material, create tasks, or inspect private rows.

## Executive verdict

Agentbook has strong individual capabilities, but it currently presents its architecture as the product. The source defines **9 primary navigation entries** for what is fundamentally a five-job learning loop:

1. orient me;
2. manage my material;
3. practise;
4. ask for guidance;
5. manage commitments.

The product should therefore converge on **5 primary entries: Home, Library, Practice, Ask Agentbook, Tasks**. Existing routes and APIs can remain available while the frontend is simplified.

The biggest issue is not visual polish. It is responsibility overlap:

- Dashboard and Progress both report outcomes, quiz performance, and recent activity.
- Chat, Ask Agentbook, and Topic Workspace all answer learning questions.
- Study plan, Coaching, Review, Ask Agentbook, and Tasks all compete to express “what should I do next?”
- Library, Notebook Detail, and Document Detail repeat upload, assignment, study, and summary entry points.
- Learner Memory and System expose implementation controls and platform vocabulary as primary learner features.

## Runtime/source consistency finding

The current source defines 9 navigation entries, including `Study Tasks`, at `frontend/src/layouts/AppShell.tsx:38`. The running browser session displayed only 8 entries and returned the not-found page for `/tasks`, even though the source registers `/tasks` at `frontend/src/App.tsx:38`.

This is a stale-runtime or wrong-build finding, not an information-architecture recommendation. Before any UX implementation is evaluated, the normal frontend process should be restarted from this project root and the loaded build should be confirmed to contain the current route table.

## Current frontend inventory

### Primary navigation

| Current label | Route | Current source position | Classification | Reason |
|---|---|---:|---|---|
| Dashboard | `/` | 1 of 9 | SIMPLIFY | Rename to Home and make it answer “what now?” rather than repeat every report. |
| Chat | `/chat` | 2 of 9 | MERGE | Merge its source-grounded Q&A into Ask Agentbook; preserve the route as a compatibility redirect or source-focused entry. |
| Ask Agentbook | `/agent` | 3 of 9 | KEEP | This is the clearest differentiated product concept and should own learner questions and guidance. |
| Notebooks | `/notebooks` | 4 of 9 | SIMPLIFY | Rename to Library; make upload/material selection the first-time job and organization secondary. |
| Study actions | `/study-actions` | 5 of 9 | SIMPLIFY | Rename to Practice; keep Quiz and Review primary, with plan/coaching contextual. |
| Study Tasks | `/tasks` | 6 of 9 | SIMPLIFY | Rename to Tasks; reduce status filters and move creation out of the always-open long form. |
| Progress | `/progress` | 7 of 9 | MERGE | Put the useful summary on Home and retain detailed history as a secondary view. |
| Learner memory | `/memory` | 8 of 9 | HIDE | Keep capability behind Ask Agentbook settings/“What Agentbook remembers”; it is not a daily destination. |
| System | `/system` | 9 of 9 | HIDE | Keep diagnostics, export, and new-space controls in settings/help; remove from learner navigation. |

Current navigation evidence: `frontend/src/layouts/AppShell.tsx:38-47`.

### Route and page inventory

| Route/page | Current label and one job | Primary / secondary actions | Data used | Overlap | First-time clarity | Core demo | Deployment need |
|---|---|---|---|---|---|---|---|
| `/` — `DashboardPage` | “Study dashboard”; summarize the workspace | Start studying / metric links, Open chat, View progress, Study actions | Dashboard counts, outcomes, quiz summary, recent sessions/quizzes | Heavy overlap with Progress, Library, Memory, Chat, Practice | Low: “Start studying” opens an empty chat before the user has material | Yes, after simplification | Yes |
| `/chat` — `ChatPage` | “Study chat”; ask source-grounded questions | Send question / choose source, rate answer, decide memory proposal, end session | Notebooks, documents, topics, sessions, chat responses, citations, outcomes | Heavy overlap with Ask Agentbook and Topic Workspace | Medium-low: “Global,” “scope,” “retrieval,” and “chunks” require system knowledge | Capability yes; standalone page no | No standalone page required |
| `/agent` — `LearningAgentPage` | “Ask Agentbook”; guidance grounded in learning activity | Ask Agentbook / example prompts, suggested action, confirm/cancel task proposal | Agent answer, human-readable evidence, suggested UI action, confirmation proposal | Overlaps Chat, plan, coaching, Tasks | High: examples clarify the value | Yes | Yes |
| `/notebooks` — `NotebooksPage` | “Notebooks and documents”; organize and upload material | New notebook / search notebooks, upload, search documents, reassign | Notebook list, document list, upload and assignment mutations | Repeats upload/assignment in Notebook Detail and assignment in Document Detail | Medium-low: “New notebook” is more prominent than the essential first upload | Yes, renamed Library | Yes |
| `/notebooks/:notebookId` — `NotebookDetailPage` | Inspect one notebook | Study notebook / edit, delete, search, move, upload, generate summary | Notebook, documents, notebook options, cached/generated summary | Repeats Library upload/assignment and Document Detail | Medium once reached contextually | Yes as a contextual detail | Yes |
| `/documents/:documentId` — `DocumentDetailPage` | Inspect one document | Study document / assign, summarize, delete | Document, notebook options, cached/generated summary | Repeats Library assignment and Topic/Notebook summaries | Low-medium because MIME, chunks, index timestamps, SQLite, embeddings, and Chroma dominate | Yes as a contextual detail | Yes, with simplified copy |
| `/topics/:topicId` — `TopicWorkspacePage` | Summarize and question one derived topic | Study topic / generate summary, ask, rate answer | Topic, cached/generated summary, Q&A response and sources | Duplicates Chat, Document Detail summary, and Practice | Low: “topic workspace” and chunk-pair language are implementation-led | No standalone page | No standalone page required |
| `/study-actions` — `StudyActionsPage` | “Study actions”; Review, Quiz, Study plan, Coaching | Varies by four equal tabs | Review queue, quiz workflows, proposals, plan, coaching | Plan/coaching overlap Ask Agentbook; proposals overlap Memory | Low-medium: four equal jobs and internal adaptation vocabulary | Yes, renamed Practice | Yes |
| `/tasks` — `StudyTasksPage` | “Study Tasks”; create and manage commitments | Create task / filter, edit, complete, cancel, reopen, archive | Task list, create/update/lifecycle APIs | Complements Agent proposals; `Current` duplicates four status groups | Medium: the long creation form precedes the learner’s list | Yes | Yes |
| `/progress` — `ProgressPage` | “Learning progress”; view outcomes, scores, and history | Read-only detail disclosures | Progress report, session history, quiz performance | Almost entirely repeats Dashboard sections | High in isolation, low in the overall IA because it repeats Home | Supporting capability | Yes as secondary detail |
| `/memory` — `MemoryPage` | “What your companion remembers”; manage learner memory | Save memory / search, edit, archive, delete, consolidate | Memory list, semantic search, proposals, consolidation | Proposals also appear in Chat/Quiz; adaptation appears in Practice | Low: memory type, confidence, importance, match distance, and consolidation are expert controls | No as primary page | Capability yes, page hidden |
| `/system` — `SystemPage` | “System health”; diagnostics, backup, new study space | Check again / export, start new space | Health, integrity, export, Guest Workspace switch | New-space entry overlaps guest onboarding; diagnostics expose deployment architecture | Low for learners | No | Diagnostics optional; export/new-space capability useful |
| `*` — `NotFoundPage` | Recover from an invalid route | Go to dashboard | None | None | High | Utility only | Yes |

Route evidence: `frontend/src/App.tsx:30-42`.

### Page sections, controls, empty states, and duplicate entry points

| Surface | Major sections and controls | Empty/error states | Audit |
|---|---|---|---|
| Home | 4 metric cards; active-session card; learning outcomes; quiz performance; recent sessions; recent quizzes; 5 links into other areas | Separate empty cards for session, outcomes, quiz attempts, sessions, and quizzes | Too many zero-state cards. One empty-state story and one primary action would be clearer. |
| Chat | Source-type filter; conditional second source filter; scope summary; transcript; citations; outcome buttons; memory proposal; composer; end-session dialog | First question, no citations, unavailable scopes, send/rating/proposal failures | Useful capability, but the source controls and routing language overwhelm the basic question job. |
| Ask Agentbook | Three example prompts; answer; evidence summary; suggested action; low-risk confirmation card; composer | Helpful first prompt, loading, safe error, expired/cancelled/consumed proposal states | Best first-time surface. Confirmation flow is a strong pattern to keep. |
| Library | New notebook; notebook search; Unsorted card; notebook cards; upload form; document search; assignment controls; create/edit/delete dialogs | No matching notebooks, no documents, upload/assignment errors | First-time priority is inverted: organization appears before adding learning material. Two independent search forms are unnecessary for small libraries. |
| Notebook detail | Study; edit/delete; metadata; document search/list/move; upload; summary; dialogs | Invalid/unavailable notebook, empty notebook, missing summary | Contextually useful, but repeats Library management and exposes re-indexing terminology. |
| Document detail | Study; delete; MIME/chunk/index metadata; notebook assignment; summary | Invalid/unavailable document, missing summary | Study and summary are relevant; storage metadata and destructive action are over-prominent. |
| Topic workspace | Study topic; summary; Q&A; ratings; topic evidence sidebar | Missing topic/summary, Q&A redirect/error | Three jobs on one derived-data page; merge into Library + Ask Agentbook + Practice. |
| Practice | Four tabs; Review queue; Quiz generation and run; result, learning signals, memory proposals; Plan form; Coaching form/results | Clear review queue, missing evidence, quiz/plan/coaching failures | Capability-rich but responsibility-heavy. Quiz and Review are practice; planning/coaching are guidance. |
| Tasks | Always-open create form; Current/Pending/Completed/Cancelled/Archived filter; grouped task cards; inline editing; lifecycle buttons | Task load/create/update/lifecycle errors, no tasks in view | Filters encode storage status rather than learner intent. Creation form pushes the task list below the fold. |
| Progress | 4 metrics; understanding outcomes; quiz performance; topic table; full session disclosures | No rated questions, no completed sessions, incomplete refresh | Good detail view but redundant as primary navigation. Session disclosures can expose long private answers and should remain intentional, secondary detail. |
| Memory | Add form with type and two sliders; semantic search; active/archived lists; consolidation; edit/archive/delete dialogs | No memories/results and mutation errors | Advanced administration, not a primary learning journey. “Match distance” is a retrieval score exposed directly. |
| System | Health; integrity; export; new study space | Health/integrity failures | Combines developer diagnostics, privacy/export, and workspace switching. Split by audience and hide diagnostics. |

## Journey simulations

### Journey A — brand-new learner

Expected: Continue as Guest → arrive somewhere understandable → upload first material → optionally create a notebook → know what to do next.

Observed:

1. Guest onboarding is understandable, although “workspace” and “private access key” are system-oriented (`frontend/src/guest/GuestSessionProvider.tsx:228-240`).
2. Empty Home presents four zero metrics, five empty sections, and “Start studying,” which opens Chat.
3. Chat does not surface “Upload your first source” before the learner asks a question.
4. Library places “New notebook” above “Upload a document,” even though a notebook is optional.

Result: **fails the shortest first-value path**. The learner can succeed, but the product does not make the required first step obvious.

Recommended path: Continue as Guest → Home with one “Upload study material” CTA → Library upload → optional “Organize into a notebook” → “Ask about this” or “Start a quiz.”

### Journey B — practice

Expected: upload → choose source → quiz → complete → see progress.

Observed:

1. Upload is available in Library and Notebook Detail.
2. Document and notebook detail pages provide “Study document/notebook.”
3. That action opens Practice with a source encoded in the URL, but the default view remains Review except for topic links (`frontend/src/pages/StudyActionsPage.tsx:182-188`).
4. Quiz setup then asks for a topic and exposes scope/personalization details.
5. Quiz result immediately expands into weaknesses, learning signals, memory proposals, answer feedback, and progress.
6. Progress is another top-level destination and repeats Home reporting.

Result: **capability works conceptually, but the transition from “study this source” to Quiz is not deterministic and the completion state has too many competing next steps**.

Recommended path: Library source → “Practice this” → Practice opens Quiz with the source already selected → complete quiz → one result summary + one “Review weak areas” action → Home reflects the change.

### Journey C — Learning Agent

Expected: open Ask Agentbook → ask “What should I study next?” → inspect evidence → receive recommendation → optionally create a task.

Observed:

1. Ask Agentbook has the strongest empty state and example prompts.
2. It shows human-readable evidence and does not auto-navigate.
3. It proposes task writes with explicit confirm/cancel and safe expiry/consumed states.
4. After confirmation, the user is sent to Study Tasks.
5. The conceptual problem is adjacent duplication: Chat answers source questions; Study Plan and Coaching also recommend next work.

Result: **passes as an isolated flow, but its product responsibility is artificially narrow**.

Recommended path: Ask Agentbook becomes the single conversational surface. A quiet source selector handles material-specific questions. Planning/coaching responses remain suggested actions, and task creation retains explicit confirmation.

### Journey D — return visit

Expected: reopen app → recover same Guest Workspace → understand recent activity → continue.

Observed:

1. Guest-session code is designed to restore the saved workspace.
2. Home can show an active session, outcomes, quizzes, and recent lists.
3. The same information is split again across Progress, Practice Review, Tasks, and Memory.
4. Home does not promote a due task or a single computed next action.

Result: **persistence is supported, but continuity is diluted by summaries and destinations competing equally**.

Recommended path: restored Home → “Continue” card for the last meaningful activity → one “Next up” item chosen from pending task, weak-area review, or source continuation → supporting “What changed” summary.

## “One page, one job” assessment

| Page | Intended single job | Assessment |
|---|---|---|
| Home | Decide what to do next | FAIL — currently also library report, progress report, history browser, and session launcher. |
| Library | Add and choose learning material | PARTIAL — notebook administration and document administration dominate first value. |
| Practice | Practise recalled material | PARTIAL — Quiz/Review fit; Study plan/Coaching are guidance. |
| Ask Agentbook | Ask for an answer or guidance | PASS, and should absorb Chat’s duplicate conversational job. |
| Tasks | See and manage commitments | PARTIAL — creation form and five-way status taxonomy dominate. |
| Progress | Inspect detailed learning history | PASS in isolation, but should be secondary because Home already owns the summary. |
| Memory | Inspect/edit personalization | PARTIAL — advanced tuning and vector-search concepts make it an administrator surface. |
| System | Maintain the installation | FAIL — mixes developer diagnostics, export, and account/workspace switching. |

## Classification register

Every major route, primary navigation entry, filter, and page section has one classification below.

### Routes/pages

| Item | Classification | Destination or treatment | Backend preserved | Risk and required tests |
|---|---|---|---|---|
| `/` Dashboard | SIMPLIFY | Home with “What am I learning / What changed / What next” | Yes | Medium; empty/returning/active-session integration tests |
| `/chat` | MERGE | Ask Agentbook source-focused state; preserve redirect/deep link | Yes, chat/session/outcome/memory APIs | High; chat, citation, routing, session and memory-decision tests |
| `/agent` | KEEP | Ask Agentbook | Yes | Medium as it absorbs source Q&A; Learning Agent tests |
| `/notebooks` | SIMPLIFY | Library | Yes | Medium; upload/notebook/assignment tests |
| `/notebooks/:id` | KEEP | Contextual Library detail, never primary nav | Yes | Low; deep-link and CRUD tests |
| `/documents/:id` | SIMPLIFY | Contextual Library detail with learner-facing metadata | Yes | Medium; citation, assignment, delete confirmation, summary tests |
| `/topics/:id` | MERGE | Library topic detail + Ask Agentbook/Practice actions; keep compatibility route first | Yes | Medium; topic deep-link, summary, Q&A redirect tests |
| `/study-actions` | SIMPLIFY | Practice | Yes | Medium; tab keyboard, scoped quiz, review, plan/coaching routing tests |
| `/tasks` | SIMPLIFY | Tasks | Yes | Medium; list/filter/lifecycle/idempotency/public-ID tests |
| `/progress` | MERGE | Home summary plus secondary “View history”; keep route during transition | Yes | Medium; reporting and history disclosure tests |
| `/memory` | HIDE | Ask Agentbook settings / “What Agentbook remembers” | Yes | Medium; memory CRUD/proposal/consolidation tests |
| `/system` | HIDE | Settings/help; diagnostics behind an advanced disclosure | Yes | Low-medium; export, refresh, new-space confirmation tests |
| `*` not found | KEEP | Recovery utility | N/A | Low; unknown-route test |

### Filters and modes

| Item | Classification | Recommendation |
|---|---|---|
| Tasks `Current` | REMOVE | It mixes pending, completed, and cancelled and therefore has no learner-intent meaning. |
| Tasks `Pending` | SIMPLIFY | Rename to **To Do** and make it the default. |
| Tasks `Completed` | KEEP | Keep as the second primary view. |
| Tasks `Cancelled` | HIDE | Place in a secondary History/status menu. |
| Tasks `Archived` | HIDE | Place in a secondary Archived view, excluded by default. |
| Chat `Global / Notebook / Document / Topic` | SIMPLIFY | Default label **All materials**; reveal “Use a specific source” only when requested. |
| Chat second source selector | KEEP | Keep contextually after choosing a specific source type. |
| Library notebook search | HIDE | Reveal when notebook count is large or after a search action. |
| Library document search | SIMPLIFY | One Library search across material; use type filters only if needed later. |
| Practice Review | KEEP | Primary practice mode. |
| Practice Quiz | KEEP | Primary practice mode and default when arriving from a source. |
| Practice Study plan | MERGE | Ask Agentbook recommendation/action; retain deep link `?view=plan`. |
| Practice Coaching | MERGE | Ask Agentbook recommendation/action; retain deep link `?view=coaching`. |
| Memory type | HIDE | Use sensible defaults; show under advanced edit only. |
| Memory confidence / importance | HIDE | Treat as system-derived by default; expose only in advanced controls if required. |
| Memory semantic search score | REMOVE | Never display “match distance” to a learner. |

### Dashboard and major sections

| Item | Classification | Recommendation |
|---|---|---|
| Documents + Notebooks metric cards | MERGE | One “Your material” summary under “What am I learning?” |
| Study sessions metric | MERGE | Fold into “What changed” only when meaningful. |
| Active memories metric | REMOVE | Not a learner success metric. |
| Active session card | KEEP | Make it the dominant “Continue” card when present. |
| Learning outcomes card | SIMPLIFY | One plain-language change signal, not four progress bars on empty data. |
| Quiz performance card | SIMPLIFY | Latest score/trend with one Practice action. |
| Recent sessions list | MERGE | Secondary activity/history disclosure. |
| Recent quizzes list | MERGE | Secondary activity/history disclosure. |
| Five simultaneous empty states | REMOVE | Replace with one onboarding empty state and progressive disclosure. |
| System service health | HIDE | Advanced diagnostics. |
| System data integrity | HIDE | Advanced diagnostics. |
| System export | KEEP | Secondary settings/privacy action. |
| System new study space | KEEP | Secondary settings/account action with confirmation. |

## Dashboard audit: the three questions

### What am I learning?

Show the current notebook/source or, for an empty account, the one action required to create it. Do not lead with document/notebook counts.

### What changed?

Show one meaningful delta: latest quiz result, a newly identified review topic, or the last completed task. Counts without change should be secondary.

### What should I do next?

Show exactly one recommended primary action:

1. resume active work;
2. complete the nearest pending task;
3. review an evidence-backed weak area;
4. practise the current source;
5. upload material when empty.

This ordering can be implemented in the frontend using already-available data. No new backend model is required for Tier 1.

## Terminology audit

| Current term/example | Location | Problem | Learner-facing replacement |
|---|---|---|---|
| local, deterministic, workspace | Home/AppShell | Describes architecture/deployment | today, your study space |
| global, scope, retrieval, chunks | Chat | Retrieval-system vocabulary | all materials, use a specific source, cited passage |
| indexed, chunk count, MIME type | Library/Document | Ingestion internals | ready to study, pages/slides/text where useful |
| SQLite, Chroma, embeddings, vector entry | Document/Memory/System | Storage implementation | saved material, search index, remove saved memory |
| source of truth, provider | System | Operator vocabulary | hide in advanced diagnostics |
| Learning Signals, Learner Memories, adaptation | Practice | Domain implementation presented as controls | what changed, why this was recommended |
| memory/signal IDs and changed property names | Study plan result | Internal identifiers leak into product UI (`frontend/src/pages/StudyActionsPage.tsx:1069-1071`) | human-readable reason only |
| memory type: episodic/procedural; confidence; importance | Memory | Expert taxonomy | preference/learning note; advanced details hidden |
| match distance | Memory search | Raw retrieval score | remove; optionally say “Relevant” |
| public IDs | Tests protect several surfaces | Correctly treated as internal | continue testing that they are never rendered |
| CockroachDB/MCP | System/source search | Deployment/integration vocabulary | never show in primary learner UI |

## Duplication map

| Learner need | Current entry points | Recommended owner |
|---|---|---|
| Ask a question | Chat, Ask Agentbook, Topic Workspace | Ask Agentbook |
| Decide what to study next | Home, Ask Agentbook, Review, Study plan, Coaching, Tasks | Home for the next action; Ask Agentbook for reasoning; Tasks for commitments |
| See progress | Home, Progress, quiz result, Review queue | Home summary; Progress/history secondary |
| Add/manage material | Library, Notebook Detail, Document Detail | Library hierarchy |
| Start practice | Home, Document Detail, Notebook Detail, Topic Workspace, Practice | Contextual “Practice this” actions leading to Practice |
| Manage personalization | Chat proposals, quiz proposals, Memory | Confirmation in context; hidden memory settings for later correction |
| Start a new guest space | Guest onboarding, System | Settings/account action after initial onboarding |

## Top five UX problems

1. **The navigation exposes nine product areas for five learner jobs.**
2. **The empty Home sends a material-less learner to Chat instead of guiding the first upload.**
3. **Chat, Ask Agentbook, Topic Workspace, Study plan, and Coaching divide one conversational/guidance responsibility.**
4. **Internal architecture language and identifiers leak into learner-facing screens, especially Practice, Memory, Document, and System.**
5. **Home/Progress and Library/detail screens repeat the same information and actions, increasing decision cost without adding capability.**

## Safety conclusion

Frontend simplification can begin safely as a route-preserving, API-preserving change. The first tier should not delete page components or routes. It should alter navigation, labels, defaults, progressive disclosure, and composition while keeping backend contracts untouched. Standalone components should only be retired after compatibility redirects and deep-link tests are in place.
