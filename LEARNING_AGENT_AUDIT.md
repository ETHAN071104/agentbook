# Learning Agent capability audit

## Summary

The smallest safe integration path is a new protected endpoint and page over a
dedicated application-level tool layer. Existing retrieval, weak-topic,
workspace dependency, provider, and study-plan services can be reused without
giving the model repository or database access.

## Existing capability findings

1. **LLM/provider abstraction** — `backend/llm/factory.py` is the shared model
   factory for OpenRouter, Groq, and OpenAI-compatible providers. It centralizes
   provider settings and supports LangChain structured output.
2. **Chat and coaching** — `/api/chat` performs grounded document chat but also
   persists study interactions and may propose learner memories.
   `/api/study/actions/coaching-plan` and the study-plan endpoint record
   adaptation events. Those routes cannot be called by a read-only agent.
3. **Document/vector search** — `backend/rag/rag_service.py:retrieve_sources`
   already validates retrieval scope and uses the request-scoped Cockroach
   vector repository in production. It is the correct read-only reuse point.
4. **Quiz mistakes/history** — the scoped `QuizRepository` exposes bounded
   attempt, question, and source reads. `backend/study/quiz_reporting.py`
   demonstrates how these records relate, but its full report contains more
   detail than the agent should receive.
5. **Study plans** — `backend/study/planner.py:build_adaptive_study_plan` is a
   deterministic, read-only builder. The API wrapper adds adaptation-event
   recording; the agent must call the builder directly.
6. **Frontend chat** — `ChatPage`, shared form/card/state components, the
   centralized typed API client, and `AppShell` provide the appropriate UI
   patterns. Existing chat is intentionally not reused because it persists.
7. **Guest Workspace dependencies** — protected routers use
   `Depends(bind_protected_workspace)`. This binds a server-created
   `ApplicationDependencies` bundle in a context variable. Clients never
   choose the workspace.
8. **API errors** — routes raise `ApiError` or use `map_exception`; installed
   handlers sanitize error content and add structured request metadata.
9. **Public IDs** — `backend/api/public_ids.py` serializes exact Python integers
   as decimal strings. Frontend IDs are typed as `string`.
10. **Provider test doubles** — existing tests patch model factories and model
    `invoke` behavior. The Learning Agent follows the same seam and adds
    injectable planner, tool, and answer-generator protocols.

## Integration decision

The Learning Agent uses:

```text
POST /api/agent/query
  -> authenticated workspace binding
  -> structured planner plus deterministic fallback
  -> four hardcoded read-only business tools
  -> sanitized tool envelopes
  -> grounded answer generation plus deterministic fallback
  -> evidence metadata
```

It does not call chat, coaching, or plan API routes; create study sessions;
record adaptation events; mutate learner memory; accept SQL; or call
CockroachDB Managed MCP at runtime.

## Safety constraints found during audit

- Material excerpts need a smaller agent-specific bound than ordinary RAG
  answer context.
- Quiz records contain correct options and explanations, so the tool must
  project only the question summary, outcome, time, topic, and safe lineage.
- The existing plan is computed from current evidence rather than persisted as
  a task list with completion and deadlines. The agent labels returned items as
  recommendations and reports unavailable deadlines as `null`.
- The answer prompt may receive sanitized evidence only. Evidence metadata must
  be derived deterministically rather than copied from model output.
