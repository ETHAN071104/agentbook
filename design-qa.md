# Practice page design QA

## Evidence

- Source visual truth: `design-audit/practice-redesign/reference-practice.png`
- Browser-rendered implementation: `design-audit/practice-redesign/implementation-comment-viewport-final.png`
- Mobile evidence: `design-audit/practice-redesign/implementation-mobile-viewport.png`
- Combined comparison input: `design-audit/practice-redesign/comparison-notebook-selector-final.png`
- Route and state: `http://127.0.0.1:5173/study-actions`, light theme, Quiz setup, Specific topic selected, Notebook selector expanded in its empty-project state, 3 questions.
- Source raster: 1448 × 1086 px; reference density not declared.
- Desktop implementation: 1301 × 902 px viewport capture from a 1316 × 912 CSS viewport at device scale factor 1.
- Mobile implementation: 390 × 844 px viewport capture at 390 × 844 CSS px and device scale factor 1.
- Density normalization: the side-by-side comparison scales both source and implementation to 1086 px high without changing aspect ratio. Source and implementation remain clearly separated; the implementation includes the retained Agentbook sidebar as explicitly requested.

## Full-view comparison evidence

The final combined comparison confirms the reference hierarchy is preserved: compact page intro, one dominant quiz-generator surface, a left-to-right Step 1 / Step 2 split, one full-width primary action, and the secondary-action section below. Per the browser annotations, the two source choices now stack vertically, the two supporting fact panels are removed, and Specific topic reveals a real Notebook selector. Intentional product differences are the retained Agentbook sidebar, the requested `More practice options` heading, and existing Agentbook Review queue / Study plan / AI coaching destinations.

The implementation uses the project's Outfit type family, royal-blue tokens, border radii, shadows, and Lucide icon family so the new layout belongs to the redesigned Home/Library system rather than appearing as a detached clone.

## Focused-region comparison evidence

No separate focused crop was required. At original resolution, the combined comparison keeps the generator controls, labels, icon treatment, card borders, supporting panels, CTA, and all three lower option cards readable enough to assess typography, spacing, colors, icons, and copy.

## Required fidelity surfaces

- Fonts and typography: passed. Outfit retains the project's established look while matching the reference's heavy headings, compact step labels, and readable supporting copy. No clipping or awkward wrapping is visible at desktop or 390 px mobile.
- Spacing and layout rhythm: passed. Desktop preserves the two-column quiz flow while stacking All materials above Specific topic; mobile keeps the same source order without overlap.
- Colors and visual tokens: passed. White cards, pale-blue page field, royal-blue selection state, subtle blue borders, and primary CTA match the reference direction and existing application tokens.
- Image quality and asset fidelity: passed. The reference contains no required photographic or branded raster asset. Decorative emoji-like symbols were implemented with the project's existing Lucide icon family, not CSS art or placeholder graphics.
- Copy and content: passed. `All materials` and `Specific topic` are the only Step 1 choices. `More practice options` uses the project's actual Review queue, Study plan, and AI coaching functionality.
- Icons and affordances: passed. Selection controls expose radio semantics and `aria-checked`; the three secondary actions remain real buttons with selected states.
- Responsiveness and accessibility: passed. 390 × 844 validation shows stable stacking, practical tap targets, labelled fields, semantic headings, radio-group behavior, and no horizontal overflow.

## Primary interactions tested

- Selected `Specific topic` and verified `aria-checked="true"`.
- Confirmed that Specific topic loads `/api/notebooks`, renders a labelled Notebook select, and disables Generate quiz until a scope is available.
- Added an integration test proving that selecting Notebook `42` sends `notebook_id: "42"` to the existing quiz-generation API.
- Opened `Review queue` from More practice options and confirmed the real Review workspace rendered.
- Opened `Study plan` and confirmed the real Adaptive study plan workspace rendered.
- Reloaded the default Quiz state and verified both labelled inputs plus the Generate quiz action were present.
- Verified desktop and 390 px mobile layouts in the in-app browser.
- Browser console/page-error collection is not exposed by the available in-app browser capability; no uncaught-error UI, failed render, or broken interaction surfaced during the browser pass.

## Findings

- No actionable P0, P1, or P2 mismatches remain.
- P3 acceptable deviation: the reference pre-fills `cellular respiration`; the implementation uses it as a placeholder so the live product does not imply that a topic was already chosen.

## Comparison history

### Pass 1

- Finding: existing automated tests still targeted the removed visible Quiz tab, which no longer belongs to the reference-led layout.
- Fix: updated the three quiz-flow checks to wait for the new `Generate your quiz` heading instead of retaining a hidden legacy tab in production markup.
- Post-fix evidence: `comparison-final.png`, full test run (15 files / 82 tests), and production build all pass.

### Pass 2

- No P0/P1/P2 visual or interaction findings. Desktop and mobile evidence both pass.

### Pass 3 — browser annotation follow-up

- Earlier finding: Specific topic did not provide a real Notebook choice, the source cards were side by side, and the Included sources / Personalization cards were no longer wanted.
- Fix: connected the real Notebook list endpoint, added selected `notebook_id` to quiz generation, stacked both source choices vertically, removed both supporting fact cards, and added loading/error/empty Notebook states.
- Post-fix evidence: `comparison-notebook-selector-final.png`, a new Notebook-scope integration test, full test run (15 files / 83 tests), and production build all pass.

## Verification

- `npm.cmd test -- --run`: 15 test files, 83 tests passed.
- `npm.cmd run build`: TypeScript check and Vite production build passed.

final result: passed
