# MCP Query Evidence: `get_weak_topics`

## Purpose

`get_weak_topics` is the first read-only business tool intended for a future
Agentbook Learning Agent. It ranks recent, repeated learning weaknesses for the
server-resolved workspace without exposing private learning content or internal
database identifiers.

Logical contract:

```python
get_weak_topics(
    *,
    limit: int = 5,
    recent_days: int | None = 30,
) -> list[WeakTopic]
```

There is intentionally no public `workspace_id` argument. The application uses
the request-scoped `ApplicationDependencies` created from the authenticated
guest session.

## Sanitized Live-Schema Findings

- `quiz_attempts` owns the workspace-scoped `quiz_topic` and attempt timestamp.
- `quiz_question_attempts` stores `presented`, `is_correct`, `skipped`, and its
  own live CockroachDB timestamp.
- `quiz_question_sources` connects a question outcome to document and chunk
  UUIDs.
- `documents.public_id` is the safe source identifier returned by the service.
- `learning_signals` stores topic, type, status, occurrence count, confidence,
  importance, and observation timestamps.
- `learning_signals.source_id` and `source_question_id` currently refer to
  workspace-scoped public quiz IDs serialized as strings.
- `learner_memories` and `learner_memory_embeddings` support personalization,
  but they are not factual document evidence.
- No `mastery_score` exists.

## Workspace-Safe CockroachDB Query Design

The implemented CockroachDB repository query follows the MCP-audited plan
below. Parameters are bound values; they are never interpolated into SQL.

```sql
WITH recent_outcomes AS (
    SELECT
        qqa.id AS question_attempt_id,
        qqa.workspace_id,
        qa.quiz_topic AS topic,
        qqa.skipped,
        (
            CASE WHEN qqa.skipped THEN 0.75::FLOAT8 ELSE 1.0::FLOAT8 END
        ) * (
            1.0::FLOAT8
            + 1.0::FLOAT8 / (
                1.0::FLOAT8
                + GREATEST(
                    0.0::FLOAT8,
                    EXTRACT(
                        EPOCH FROM (current_timestamp() - qqa.created_at)
                    )::FLOAT8 / 604800.0::FLOAT8
                )
            )
        ) AS outcome_weight,
        qqa.created_at
    FROM quiz_question_attempts AS qqa
    JOIN quiz_attempts AS qa
      ON qa.id = qqa.quiz_attempt_id
     AND qa.workspace_id = qqa.workspace_id
    WHERE qqa.workspace_id = :workspace_id
      AND qqa.presented
      AND (qqa.skipped OR NOT qqa.is_correct)
      AND qqa.created_at >= :cutoff
),
outcome_scores AS (
    SELECT
        workspace_id,
        topic,
        COUNT(*) FILTER (WHERE NOT skipped) AS incorrect_count,
        COUNT(*) FILTER (WHERE skipped) AS skipped_count,
        SUM(outcome_weight) AS outcome_score,
        MAX(created_at) AS last_outcome_at
    FROM recent_outcomes
    GROUP BY workspace_id, topic
),
signal_scores AS (
    SELECT
        workspace_id,
        topic,
        SUM(
            CASE WHEN status = 'active' THEN occurrence_count ELSE 0 END
        ) AS active_signal_occurrences,
        SUM(
            CASE
                WHEN status = 'active' THEN 1.0::FLOAT8
                WHEN status = 'improving' THEN -0.5::FLOAT8
                ELSE 0.0::FLOAT8
            END
            * occurrence_count::FLOAT8
            * confidence
            * importance
            / (
                1.0::FLOAT8
                + GREATEST(
                    0.0::FLOAT8,
                    EXTRACT(
                        EPOCH FROM (
                            current_timestamp() - last_observed_at
                        )
                    )::FLOAT8 / 604800.0::FLOAT8
                )
            )
        ) AS signal_adjustment,
        MAX(last_observed_at) AS last_signal_at
    FROM learning_signals
    WHERE workspace_id = :workspace_id
      AND status IN ('active', 'improving')
      AND signal_type = 'knowledge_gap'
      AND topic <> ''
      AND last_observed_at >= :cutoff
    GROUP BY workspace_id, topic
),
lineage AS (
    SELECT
        ro.workspace_id,
        ro.topic,
        ARRAY_AGG(DISTINCT d.public_id) AS source_document_public_ids
    FROM recent_outcomes AS ro
    JOIN quiz_question_sources AS qqs
      ON qqs.question_attempt_id = ro.question_attempt_id
     AND qqs.workspace_id = ro.workspace_id
    JOIN document_chunks AS dc
      ON dc.id = qqs.document_chunk_id
     AND dc.workspace_id = qqs.workspace_id
    JOIN documents AS d
      ON d.id = qqs.document_id
     AND d.workspace_id = qqs.workspace_id
     AND dc.document_id = d.id
    GROUP BY ro.workspace_id, ro.topic
)
SELECT
    os.topic,
    GREATEST(
        0.0::FLOAT8,
        os.outcome_score
            + 0.35::FLOAT8
            * COALESCE(ss.signal_adjustment, 0.0::FLOAT8)
    ) AS weakness_score,
    os.incorrect_count,
    os.skipped_count,
    COALESCE(ss.active_signal_occurrences, 0)
        AS active_signal_occurrences,
    COALESCE(
        GREATEST(os.last_outcome_at, ss.last_signal_at),
        os.last_outcome_at
    ) AS last_observed_at,
    COALESCE(
        l.source_document_public_ids,
        ARRAY[]::INT8[]
    ) AS source_document_public_ids
FROM outcome_scores AS os
LEFT JOIN signal_scores AS ss
  ON ss.workspace_id = os.workspace_id
 AND ss.topic = os.topic
LEFT JOIN lineage AS l
  ON l.workspace_id = os.workspace_id
 AND l.topic = os.topic
ORDER BY weakness_score DESC, last_observed_at DESC, os.topic ASC
LIMIT :limit;
```

`recent_days=None` is implemented by omitting both cutoff predicates. The
application validates `limit` as `1..5` and `recent_days` as `1..365` when
present.

The SQLite compatibility query uses the parent quiz-attempt timestamp because
the compatibility schema does not store a question timestamp. It preserves the
same workspace and output guarantees.

## EXPLAIN Summary

`explain_query` successfully planned a sanitized equivalent with a non-real
workspace parameter, a 30-day window, and a limit of five.

- Workspace predicates were pushed into outcome and signal scans.
- The quiz path scans workspace outcomes, applies outcome/date filters, then
  performs a workspace-checked lookup into `quiz_attempts`.
- The lineage path uses the question-source index, followed by
  workspace-checked lookups into chunks and documents.
- The MCP-audited signal path uses `idx_learning_signals_lookup`, filters the
  live active knowledge-gap rows, and aggregates by topic. Repository
  comparison later added the already-supported `improving` state to the same
  bounded predicate as a negative adjustment.
- Topic scores, signals, and lineage are combined with left hash joins before a
  bounded top-five sort.
- `EXPLAIN ANALYZE` was not run.
- Current live tables are small, so production-scale performance conclusions
  remain uncertain.

## Index Observations

Verified vector indexes:

- `idx_document_chunks_workspace_embedding`
- `idx_memory_embeddings_workspace_embedding`

Relevant existing relational indexes:

- `idx_quiz_attempts_workspace`
- `idx_quiz_questions_attempt`
- `quiz_question_sources_question_attempt_id_source_index_key`
- `idx_learning_signals_lookup`
- `idx_documents_workspace`
- `idx_document_chunks_document`

Potential future performance indexes, not required for correctness:

- `quiz_question_attempts (workspace_id, created_at)` with stored outcome/join
  fields
- `learning_signals (workspace_id, status, signal_type, topic)` with stored
  scoring fields
- `quiz_question_sources (workspace_id, question_attempt_id)` with stored
  document/chunk IDs

No index or schema change was applied. These suggestions require validation
against production-scale statistics and write amplification.

## Implemented Code

- `backend/application/weak_topics.py`: safe business result and application
  service.
- `backend/repositories/interfaces/protocols.py`: bounded repository contract.
- `backend/repositories/cockroach/study.py`: live workspace-safe aggregate
  query.
- `backend/study/database.py` and
  `backend/repositories/sqlite/adapters.py`: SQLite-compatible implementation.
- `backend/api/schemas.py`: safe response models with public-ID serialization.
- `backend/api/routes/quiz.py`: protected `GET /api/study/weak-topics`
  endpoint.
- `tests/test_weak_topics.py`: ranking, recency, outcome, signal, isolation,
  tampering, serialization, and leakage tests.

The existing quiz-performance report was not called by the new service because
it materializes private question/report content and does not implement recency
or LearningSignal weighting. The new query reuses the existing repository and
request-scoped dependency boundaries without duplicating that report’s
presentation logic.

## Test Results

Targeted weak-topic tests: 6 passed.

- Complete backend suite: 138 passed, 6 authorized live-database tests skipped.
- Python `compileall`: passed for `backend` and `tests`.
- Guest Workspace isolation and workspace-tampering checks: passed.
- Public-ID string contract checks: passed.
- Credential and token leakage scan: no matches.
- `git diff --check`: passed.

All test runs forced the SQLite persistence backend and disabled opt-in live
CockroachDB tests. Verification did not modify live database data.

## Migration Decision

No schema migration is required. The live schema already provides explicit
outcomes, topics, recency timestamps, signal aggregation, source lineage, public
document IDs, and vector indexes.

Future indexes are optional optimization work only.

## Remaining Limitations

- The current live data volume is too small to predict production-scale query
  performance confidently.
- Signal vocabularies observed in live data are application values, not all
  database constraints.
- The service ranks topics with incorrect or skipped quiz outcomes; active
  signals supplement those topics rather than creating unsupported
  signal-only weaknesses.
- The Learning Agent router and user-facing orchestration remain intentionally
  out of scope.
