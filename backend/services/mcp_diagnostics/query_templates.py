from __future__ import annotations

import re
from enum import StrEnum


SYNTHETIC_WORKSPACE = "00000000-0000-4000-8000-000000000000"
ZERO_VECTOR = "[" + ",".join("0" for _ in range(384)) + "]"


class QueryTemplate(StrEnum):
    WEAK_TOPICS = "weak_topics"
    DOCUMENT_VECTOR_SEARCH = "document_vector_search"
    MEMORY_VECTOR_SEARCH = "memory_vector_search"
    PENDING_STUDY_TASKS = "pending_study_tasks"


WEAK_TOPIC_QUERY = f"""
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
    WHERE qqa.workspace_id = '{SYNTHETIC_WORKSPACE}'::UUID
      AND qqa.presented
      AND (qqa.skipped OR NOT qqa.is_correct)
      AND qqa.created_at >= TIMESTAMPTZ '1970-01-01T00:00:00Z'
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
            CASE
                WHEN status = 'active' THEN occurrence_count
                ELSE 0
            END
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
    WHERE workspace_id = '{SYNTHETIC_WORKSPACE}'::UUID
      AND status IN ('active', 'improving')
      AND signal_type = 'knowledge_gap'
      AND topic <> ''
      AND last_observed_at >= TIMESTAMPTZ '1970-01-01T00:00:00Z'
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
            + 0.35::FLOAT8 * COALESCE(ss.signal_adjustment, 0.0::FLOAT8)
    ) AS weakness_score,
    os.incorrect_count,
    os.skipped_count,
    COALESCE(ss.active_signal_occurrences, 0) AS active_signal_occurrences,
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
LIMIT 5
""".strip()

DOCUMENT_VECTOR_QUERY = f"""
SELECT c.*,
       d.public_id AS document_public_id,
       c.embedding <=> CAST('{ZERO_VECTOR}' AS VECTOR(384)) AS distance
FROM document_chunks AS c
JOIN documents AS d
  ON d.id = c.document_id
 AND d.workspace_id = c.workspace_id
WHERE c.workspace_id = '{SYNTHETIC_WORKSPACE}'::UUID
  AND c.embedding IS NOT NULL
ORDER BY distance ASC, d.public_id ASC, c.chunk_index ASC
LIMIT 5
""".strip()

MEMORY_VECTOR_QUERY = f"""
SELECT m.*,
       e.embedding <=> CAST('{ZERO_VECTOR}' AS VECTOR(384)) AS distance
FROM learner_memory_embeddings AS e
JOIN learner_memories AS m
  ON m.id = e.memory_id
 AND m.workspace_id = e.workspace_id
WHERE e.workspace_id = '{SYNTHETIC_WORKSPACE}'::UUID
  AND m.status = 'active'
ORDER BY distance ASC, m.public_id ASC
LIMIT 5
""".strip()

PENDING_STUDY_TASK_QUERY = f"""
SELECT *
FROM study_tasks
WHERE workspace_id = '{SYNTHETIC_WORKSPACE}'::UUID
  AND status = 'pending'
ORDER BY
    CASE status
        WHEN 'pending' THEN 0
        WHEN 'completed' THEN 1
        WHEN 'cancelled' THEN 2
        ELSE 3
    END,
    CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
    due_at ASC,
    updated_at DESC,
    public_id DESC
LIMIT 5
""".strip()

QUERY_TEMPLATES = {
    QueryTemplate.WEAK_TOPICS: WEAK_TOPIC_QUERY,
    QueryTemplate.DOCUMENT_VECTOR_SEARCH: DOCUMENT_VECTOR_QUERY,
    QueryTemplate.MEMORY_VECTOR_SEARCH: MEMORY_VECTOR_QUERY,
    QueryTemplate.PENDING_STUDY_TASKS: PENDING_STUDY_TASK_QUERY,
}

_WRITE_OR_DDL = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|UPSERT|CREATE|ALTER|DROP|TRUNCATE|GRANT|"
    r"REVOKE|BEGIN|COMMIT|ROLLBACK|SET|COPY|IMPORT|EXPORT)\b",
    re.IGNORECASE,
)


def validate_read_only_query(query: str) -> str:
    if query not in QUERY_TEMPLATES.values():
        raise ValueError("Only registered fixed diagnostic queries are allowed.")
    if ";" in query or "--" in query or "/*" in query:
        raise ValueError("Multi-statement SQL and SQL comments are not allowed.")
    if _WRITE_OR_DDL.search(query):
        raise ValueError("DDL, DML, and transaction control are not allowed.")
    if not re.match(r"^\s*(?:SELECT|WITH)\b", query, re.IGNORECASE):
        raise ValueError("Only read-only SELECT query templates are allowed.")
    if "workspace_id" not in query.casefold():
        raise ValueError("Diagnostic queries must contain a workspace predicate.")
    if not re.search(r"\bLIMIT\s+\d+\b", query, re.IGNORECASE):
        raise ValueError("Diagnostic queries must contain a fixed result limit.")
    return query


for _query in QUERY_TEMPLATES.values():
    validate_read_only_query(_query)
