# Agentbook Frontend UX Simplification: Tier 1 Implementation

## Approved scope

This change implements Tier 1 from `FRONTEND_UX_AUDIT.md` and
`FRONTEND_SIMPLIFICATION_PLAN.md`. It simplifies the learner-facing frontend
without changing backend source, API contracts, authentication, persistence,
database schemas, task statuses, task confirmation, or idempotency behavior.
Existing routes and page components remain available for compatibility.

## Runtime and source verification

Before implementation, the checked-out source registered `/tasks` and contained
nine primary navigation entries, while the stale running frontend did not expose
the Tasks route. The stale frontend processes were stopped and Vite was started
from `Agentbook/frontend`. The served `App.tsx` was inspected directly, `/tasks`
returned the SPA successfully, and the loaded module was confirmed to contain
the checked-out Tasks route before UX work began.

## Navigation before and after

Before:

1. Dashboard
2. Chat
3. Ask Agentbook
4. Notebooks
5. Study actions
6. Study Tasks
7. Progress
8. Learner Memory
9. System

After:

1. Home (`/`)
2. Library (`/notebooks`)
3. Practice (`/study-actions`)
4. Ask Agentbook (`/agent`)
5. Tasks (`/tasks`)

Desktop and mobile use the same five-entry navigation model. Chat, Progress,
Learner Memory, and System were removed from primary navigation only.

## Home

- Replaced the report-heavy dashboard with exactly three conceptual sections:
  What you are learning, What changed, and Next up.
- Added one upload-first onboarding state for an empty study space.
- Explained that notebooks are optional rather than making organization a
  prerequisite.
- Added one deterministic dominant next action using existing data in this
  order: active work, nearest pending task, evidence-backed review item, recent
  practice source, then first upload.
- Shows at most one meaningful recent change and keeps detailed reporting behind
  View learning history.
- Removed Active Memories and internal identifiers from the learner summary.

## Library

- Kept `/notebooks` as the canonical route and renamed the surface Library.
- Made Upload study material the dominant action and New notebook secondary.
- Replaced the separate searches with one Library search.
- Presents notebooks as optional organization and treats Unsorted as a normal
  group.
- Groups material by notebook and gives each source Ask about this and Practice
  this actions.
- Routes source practice deterministically to Quiz with the existing source
  parameters.
- Places assignment and management controls in secondary disclosures where
  practical while preserving all existing behavior.

## Source detail pages

Notebook, document, and topic routes remain registered. Their learner-facing
action hierarchy now prioritizes Ask about this, then Practice this, followed by
summary/supporting information and secondary management controls. Technical
metadata is reduced or translated.

## Practice

- Renamed Study actions to Practice.
- Made Quiz and Review the two primary tabs.
- Kept Study Plan and Coaching reachable under More practice options.
- Source-based entry opens Quiz unless an explicit existing view is present.
- Weak-topic guidance opens Review, while plan and coaching deep links remain
  supported.
- Reordered quiz results to score, one learning insight, and one recommended
  action before expandable detail.
- Replaced signal, memory, adaptation, confidence, and identifier output with
  learner language such as Areas to review and Why this was recommended.

## Tasks

- Renamed Study Tasks to Tasks.
- Defaults to To Do, with Completed as the second primary view.
- Moved Archived and History, including cancelled tasks, under More views.
- Removed the learner-facing Current filter.
- Replaced the always-open form with a compact Add task control and optional
  details.
- Preserved create, edit, complete, reopen, cancel, archive, confirmation, and
  idempotency behavior.
- A new pending task selects To Do, refreshes the list, and becomes visible.

## Terminology replacements

- Dashboard -> Home
- Notebooks -> Library
- Study actions -> Practice
- Study Tasks -> Tasks
- Indexed -> Ready to study
- Workspace -> Study space where a label is needed
- Learning Signals -> Areas to review
- Learner Memory -> What Agentbook remembers
- Document scope labels -> Source or material
- Technical storage, vector, embedding, chunk, provider, match-distance,
  confidence, importance, adaptation-field, and raw identifier details are
  removed from primary learner UI.

## Hidden routes and contextual access

The following routes remain registered:

- `/chat`
- `/progress`
- `/memory`
- `/system`
- `/topics/:topicId`
- `/notebooks/:notebookId`
- `/documents/:documentId`

Home links to View learning history at `/progress`. Ask Agentbook links to What
Agentbook remembers at `/memory`. System remains an advanced Settings and
diagnostics surface. Unknown routes retain safe recovery to Home.

## Preserved backend capabilities

No backend work was required. Existing Guest Workspace restoration and
isolation, uploads, grounded retrieval, Quiz, Review, Study Plan, Coaching,
learner history, memory workflows, Learning Agent behavior, confirmed Study
Task writes, persistence, CockroachDB integration, and public-ID handling remain
unchanged.

## Test results

- Full frontend suite: 15 test files passed, 82 tests passed.
- Production build: `tsc --noEmit && vite build` passed.
- Added Tier 1 integration coverage for five-entry navigation, active/focus
  behavior, hidden routes, Home priorities, upload-first Library behavior,
  terminology safety, and source-to-Quiz routing.
- Existing Guest Workspace, Learning Agent, task lifecycle, idempotency,
  public-ID, source routing, and study-flow tests remain passing.

## Manual walkthrough

Using the freshly served frontend:

1. Restored the same private guest study space after reload.
2. Opened Home and confirmed the three-section learner summary.
3. Uploaded a text study source from Library.
4. Confirmed upload success exposed Ask about this and Practice this.
5. Opened Practice this and confirmed Quiz setup with the uploaded source
   selected in the URL and UI.
6. Asked Agentbook to create a photosynthesis review task for the next day.
7. Confirmed the explicit proposal card.
8. Opened Tasks and confirmed To Do was selected and the new task was visible.
9. Refreshed Home and confirmed the same study space and one task-based Next up
   action.
10. Opened `/chat`, `/progress`, `/memory`, and `/system` directly and confirmed
    they resolve. The uploaded source did not produce a valid topic identifier,
    so a real `/topics/:topicId` deep link was covered by route tests rather than
    fabricated for the live walkthrough.

## Remaining Tier 2 work

Tier 2 remains exactly:

1. Merge source-grounded Chat into Ask Agentbook with an optional source
   selector.
2. Make `/chat` a compatibility entry into the merged experience.
3. Move Home's detailed history to a secondary Progress/history view and remove
   duplicate summary sections.
4. Make Quiz and Review the only primary Practice modes.
5. Launch Study Plan and Coaching contextually from Ask Agentbook or secondary
   Practice options.
6. Compose topic summary/question actions into Library and Ask Agentbook while
   preserving `/topics/:topicId` during transition.
7. Move memory correction into Ask Agentbook settings.

## Remaining UX backlog

- Complete the Tier 2 conversational and topic consolidation before retiring
  any standalone page.
- Split learner settings from advanced diagnostics.
- Further consolidate repeated Library management controls after route usage is
  observed.
- Consolidate memory administration into a compact personalization/settings
  view.
- Validate long-term responsive behavior with larger real-world libraries and
  study histories.
