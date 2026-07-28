# Agentbook frontend simplification plan

## Decision

Proceed with a frontend-only simplification in staged tiers. The target information architecture has five primary destinations:

1. **Home** — orient me and give me one next action.
2. **Library** — add, organize, and choose study material.
3. **Practice** — quiz or review material.
4. **Ask Agentbook** — ask source questions or request learning guidance.
5. **Tasks** — manage concrete commitments.

The existing backend, APIs, data model, Guest Workspace boundary, confirmation model, and persistence behavior remain unchanged.

## Proposed information architecture

### Primary navigation

| Label | Canonical route | One job |
|---|---|---|
| Home | `/` | Understand current state and continue with one useful action |
| Library | `/notebooks` | Add or choose material |
| Practice | `/study-actions` | Quiz or review |
| Ask Agentbook | `/agent` | Ask a question or get guidance |
| Tasks | `/tasks` | Manage commitments |

### Contextual routes and views

| Route/view | Treatment |
|---|---|
| `/notebooks/:notebookId` | Keep as Library detail. |
| `/documents/:documentId` | Keep as Library detail; simplify metadata and action priority. |
| `/topics/:topicId` | Preserve during transition, then compose its useful summary/source actions into Library and Ask Agentbook. |
| `/progress` | Keep as a secondary history/detail route linked from Home. |
| `/chat` | Preserve as a compatibility route that opens Ask Agentbook in source-focused mode. |
| Practice `?view=plan` and `?view=coaching` | Preserve deep links; invoke contextually from Ask Agentbook or “More practice options.” |
| `/memory` | Hide from primary navigation; link from Ask Agentbook settings as “What Agentbook remembers.” |
| `/system` | Hide from primary navigation; expose Export/New study space in settings and diagnostics in an advanced disclosure. |
| `*` | Keep the safe not-found recovery page. |

## Proposed page model

### Home

Use three sections only:

1. **What you are learning** — current material or the empty-state upload action.
2. **What changed** — latest meaningful learning result.
3. **Next up** — one dominant action.

Priority for “Next up”:

1. Continue an active session/activity.
2. Open the nearest pending task.
3. Review a weak topic backed by stored evidence.
4. Practise the current source.
5. Upload first material.

Move detailed session and quiz history behind a single “View learning history” link. Do not display Active Memories as a success metric.

### Library

The first-time state should begin with **Upload study material**. Notebook creation is optional and secondary.

After content exists:

- show a single Library search;
- group by notebooks with Unsorted as a normal destination, not an “automatic” technical construct;
- make source cards lead to a clean detail view;
- keep assignment and deletion in secondary menus;
- use “Ready to study” instead of “Indexed”;
- use human source units such as page or slide where available, not chunk count.

### Practice

Primary modes:

- **Quiz**
- **Review**

Rules:

- arriving from a document, notebook, or topic opens Quiz with that source selected;
- arriving from a weak-area recommendation opens Review;
- arriving directly uses the last relevant mode or Quiz for a learner with material;
- Study plan and Coaching remain supported but move under a secondary “More practice options” entry or are launched from Ask Agentbook;
- results show score, one plain-language insight, and one next action before technical detail;
- Learning Signals, adaptation fields, IDs, and changed-property lists are never shown as raw product text.

### Ask Agentbook

Use one composer and one answer model.

- Default: ask about learning progress, mistakes, next steps, or material.
- Optional source chip: **All materials** or a selected notebook/document/topic.
- Source-grounded answers continue to use the existing Chat APIs, citations, outcome rating, and session behavior.
- Guidance continues to use the existing Learning Agent API.
- The UI, not a backend redesign, decides which existing request contract is used based on the selected source/mode and supported intent routing.
- Keep explicit confirmation for task writes. Never auto-execute a write.

### Tasks

Default primary views:

- **To Do** — backend status `pending`; default.
- **Completed** — backend status `completed`.

Secondary views:

- **Archived**
- **History**, containing cancelled items if retaining cancellation visibility is useful.

Remove “Current.” It currently means multiple statuses and duplicates the grouped labels. Move task creation into a compact “Add task” action/drawer or an inline one-line title field; reveal description, topic, due date, and priority only when requested.

## First-time and returning flows

### First-time

`Continue as Guest → Home → Upload study material → optional notebook → source ready → Ask about this / Practice this`

Requirements:

- Home must never make empty Chat the primary next step.
- Library must explain that notebooks are optional.
- Upload success must offer exactly two next actions: Ask or Practice.
- “Workspace,” “access key,” “index,” and storage-provider terms should not be required to understand the flow.

### Returning

`Restore Guest Workspace → Home → Continue / Next up → task, practice, source, or Ask Agentbook`

Requirements:

- Do not require re-onboarding.
- Show one meaningful change since the last visit.
- Prefer a pending commitment or active activity over generic metrics.
- Keep detailed history available but secondary.

## Tiered implementation plan

### Tier 1 — high impact, route-preserving simplification

Scope:

1. Reduce primary navigation from 9 entries to Home, Library, Practice, Ask Agentbook, Tasks.
2. Rename Dashboard, Notebooks, Study actions, and Study Tasks in learner-facing copy.
3. Keep every existing route registered; hide or contextualize Progress, Memory, and System.
4. Change Tasks to default To Do and provide Completed as the second primary view; move Archived/Cancelled to secondary history.
5. Replace the empty Home dashboard grid with one onboarding state whose primary action is Upload study material.
6. Reframe returning Home around Continue, What changed, and Next up.
7. Make Library upload the first-time primary action and notebook creation optional.
8. Change “Study document/notebook/topic” links to open the appropriate Practice mode.
9. Remove raw internal terms and identifier output from primary learner surfaces.
10. Restart the frontend from the correct project root and verify the source/runtime route table before visual acceptance.

Expected impact: very high.  
Risk: low to medium because routes and APIs stay intact.  
Backend work: unnecessary.

Likely frontend files:

- `frontend/src/layouts/AppShell.tsx`
- `frontend/src/App.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/NotebooksPage.tsx`
- `frontend/src/pages/NotebookDetailPage.tsx`
- `frontend/src/pages/DocumentDetailPage.tsx`
- `frontend/src/pages/TopicWorkspacePage.tsx`
- `frontend/src/pages/StudyActionsPage.tsx`
- `frontend/src/pages/StudyTasksPage.tsx`
- `frontend/src/pages/MemoryPage.tsx`
- `frontend/src/pages/SystemPage.tsx`
- `frontend/src/components/SourceCard.tsx`
- `frontend/src/styles/patterns.css`
- relevant frontend integration tests

Required tests:

- primary navigation desktop/mobile and keyboard focus;
- unknown and preserved hidden routes;
- empty and returning Home states;
- Library empty/upload success and optional notebook flow;
- source-to-Practice routing;
- Task default/filter/lifecycle/idempotency behavior;
- no internal/public IDs, raw memory/signal IDs, storage providers, or retrieval scores in rendered learner UI;
- Guest Workspace restoration and isolation;
- existing Learning Agent confirmation tests.

### Tier 2 — merge duplicate responsibilities

Scope:

1. Merge source-grounded Chat into Ask Agentbook with an optional source selector.
2. Make `/chat` a compatibility entry into the merged experience.
3. Move Home’s detailed history to a secondary Progress/history view and remove duplicate summary sections.
4. Make Quiz and Review the only primary Practice modes.
5. Launch Study plan and Coaching contextually from Ask Agentbook or secondary Practice options.
6. Compose topic summary/question actions into Library/Ask Agentbook while preserving `/topics/:topicId` during transition.
7. Move memory correction to Ask Agentbook settings.

Expected impact: high.  
Risk: medium to high because conversational states, session behavior, citations, and intent routing must remain correct.  
Backend work: unnecessary unless later product research identifies a genuinely missing response contract.

Likely frontend files:

- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/LearningAgentPage.tsx`
- `frontend/src/pages/StudyActionsPage.tsx`
- `frontend/src/pages/ProgressPage.tsx`
- `frontend/src/pages/TopicWorkspacePage.tsx`
- `frontend/src/pages/MemoryPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api` types/client only if UI composition needs existing contract typing
- feature-routing, chat, study-flow, Learning Agent, and route integration tests

Required tests:

- source-specific and all-material Ask Agentbook requests;
- citations and evidence-empty behavior;
- session restore/end and outcome rating;
- feature redirects to plan/coaching without automatic navigation;
- task proposal confirm/cancel/expiry/consumed behavior;
- `/chat`, `/progress`, and `/topics/:id` deep-link compatibility;
- mobile composer and source selection accessibility.

### Tier 3 — retire redundant shells after evidence

Scope:

1. After redirects and usage evidence are stable, retire standalone Chat, Topic Workspace, or Progress page components that no longer own a unique job.
2. Split System into learner settings and optional advanced diagnostics; consider excluding diagnostics from production navigation entirely.
3. Remove duplicate Library management controls from detail screens where contextual menus suffice.
4. Consolidate Memory administration into a compact personalization/settings view.

Expected impact: medium.  
Risk: medium because external/deep links and long-tail administration workflows may exist.  
Backend work: unnecessary.

Removal gate:

- compatibility redirects shipped for at least one release;
- no unresolved deep-link regressions;
- equivalent capability reachable from the target owner;
- accessibility and mobile tests pass;
- no API or database deletion is coupled to frontend removal.

## Removal safety

### Safe to remove in Tier 1

- “Current” Task filter.
- Active Memories dashboard metric.
- Repeated empty dashboard cards.
- Raw chunk counts, match distances, storage-provider labels, adaptation property names, and internal memory/signal IDs from learner-facing copy.
- Progress, Memory, and System entries from primary navigation.

These are presentation removals only; their APIs and stored data remain untouched.

### Not safe to remove in Tier 1

- Any registered route or page component.
- Chat/session, citation, outcome, memory, task, report, health, integrity, export, summary, quiz, review, plan, or coaching endpoints.
- Guest Workspace restoration/switching.
- Task confirmation and idempotency behavior.
- Notebook/document/topic deep links.

### Pages that may be retired later

- Standalone `ChatPage` after its full behavior is present in Ask Agentbook and `/chat` redirects safely.
- Standalone `TopicWorkspacePage` after summary, evidence, question, and practice actions have destinations.
- Standalone `ProgressPage` only if Home plus a replacement history view preserve detailed reporting.

No page is safe for immediate physical deletion during Tier 1.

## Acceptance criteria

Implementation is successful when:

- a new learner reaches first upload without choosing among unrelated areas;
- a learner can move from source to quiz in one clear action;
- Ask Agentbook owns both material questions and learning guidance without exposing backend tool names;
- Home communicates one next action and one meaningful change;
- Tasks opens on To Do, and Archived is hidden by default;
- primary navigation contains exactly five entries on desktop and mobile;
- current hidden/deep routes still resolve safely;
- no existing backend contract, database schema, or stored row is changed;
- the running app matches the checked-out source.

## Final recommendation

1. **Current number of primary navigation entries:** 9 in source; the currently running browser showed 8 because it was stale and lacked the new Tasks route.
2. **Recommended number:** 5.
3. **Pages to keep:** Home, Library, Practice, Ask Agentbook, Tasks; notebook/document details and not-found as contextual/utility views.
4. **Pages to merge:** Chat into Ask Agentbook; Progress into Home plus secondary history; Topic Workspace into Library/Ask Agentbook/Practice; plan/coaching into contextual guidance.
5. **Pages to hide:** Learner Memory and System; detailed Progress/history from primary navigation.
6. **Pages safe to remove:** none immediately; retire standalone Chat, Topic Workspace, and possibly Progress only after merge and redirect gates pass.
7. **Filters/defaults that must change:** Tasks defaults to To Do, with Completed primary and Archived/Cancelled secondary; Chat defaults to All materials with source selection disclosed on demand; Library uses one search; Practice prioritizes Quiz/Review.
8. **Top five UX problems:** nine-area navigation; empty Home points to Chat before upload; conversational/guidance duplication; internal terminology/identifier leakage; duplicate reporting and material-management surfaces.
9. **Proposed final journey:** Continue as Guest → Home → upload/choose material → Ask or Practice → see one meaningful result → optionally confirm a Task → return to one Next up action.
10. **Tier 1 implementation scope:** five-item nav, learner-facing renames, simplified Home/Library, Task filter defaults, deterministic source-to-Practice links, terminology cleanup, preserved routes, and runtime/source verification.
11. **Backend untouched:** yes; existing APIs, schemas, persistence, authentication, workspace isolation, and data remain unchanged.
12. **Whether implementation can safely begin:** yes, with Tier 1 only and with the stale frontend runtime corrected before acceptance testing.

## Recommended next action

Approve Tier 1 as the implementation boundary; do not combine it with the Tier 2 Chat/Agent merge in the same change set.
