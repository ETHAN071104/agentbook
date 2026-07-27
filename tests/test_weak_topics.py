from __future__ import annotations

import tempfile
import unittest

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routes.guest_sessions import CREATION_LIMITER
from backend.application.dependencies import (
    build_application_dependencies,
    configure_application_dependencies,
    get_application_dependencies,
)
from backend.application.guest_sessions import GuestSessionService
from backend.application.weak_topics import get_weak_topics
from backend.domain import DEFAULT_WORKSPACE_ID
from backend.rag import config
from backend.rag import database as rag_database
from backend.repositories.sqlite import initialize_foundation_schema


TEST_PEPPER = "weak-topics-test-pepper-with-at-least-32-bytes"


class WeakTopicsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.database_path = Path(temporary) / "weak-topics.db"
        self.stack.enter_context(
            patch.object(rag_database, "DATABASE_PATH", self.database_path)
        )
        self.stack.enter_context(
            patch.object(rag_database, "ensure_directories")
        )
        self.stack.enter_context(
            patch.object(config, "PERSISTENCE_BACKEND", "sqlite")
        )
        self.stack.enter_context(
            patch.object(
                config,
                "GUEST_SESSION_TOKEN_PEPPER",
                TEST_PEPPER,
            )
        )
        self.stack.enter_context(
            patch.object(
                config,
                "ALLOW_LEGACY_DEFAULT_WORKSPACE",
                False,
            )
        )
        rag_database.initialize_database()
        from backend.memory.database import initialize_memory_database
        from backend.study.database import initialize_study_database

        initialize_memory_database()
        initialize_study_database()
        initialize_foundation_schema()
        configure_application_dependencies(None)
        self.addCleanup(configure_application_dependencies, None)
        self.dependencies = build_application_dependencies(
            DEFAULT_WORKSPACE_ID
        )
        self.dependencies.workspaces.ensure_default()

    def _seed_document(self, workspace_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with rag_database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    filename, mime_type, file_hash, file_data,
                    chunk_count, created_at, updated_at, workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "private-source.pdf",
                    "application/pdf",
                    f"hash-{workspace_id}-{now}",
                    b"private document bytes",
                    1,
                    now,
                    now,
                    workspace_id,
                ),
            )
            return int(cursor.lastrowid)

    def _seed_outcome(
        self,
        *,
        workspace_id: str,
        topic: str,
        created_at: datetime,
        skipped: bool = False,
        correct: bool = False,
        document_id: int | None = None,
    ) -> None:
        timestamp = created_at.isoformat()
        with rag_database.get_connection() as connection:
            attempt = connection.execute(
                """
                INSERT INTO quiz_attempts (
                    requested_topic, quiz_topic, status,
                    total_questions, presented_questions,
                    answered_questions, skipped_questions,
                    correct_answers, score_percentage,
                    accuracy_percentage, confidence,
                    created_at, workspace_id
                ) VALUES (?, ?, 'completed', 1, 1, ?, ?, ?, ?, ?, 0.9, ?, ?)
                """,
                (
                    topic,
                    topic,
                    0 if skipped else 1,
                    1 if skipped else 0,
                    1 if correct else 0,
                    100.0 if correct else 0.0,
                    None if skipped else (100.0 if correct else 0.0),
                    timestamp,
                    workspace_id,
                ),
            )
            question = connection.execute(
                """
                INSERT INTO quiz_question_attempts (
                    quiz_attempt_id, question_number, question,
                    options_json, presented, selected_option,
                    correct_option, is_correct, skipped,
                    explanation, workspace_id
                ) VALUES (?, 1, ?, ?, 1, ?, 1, ?, ?, ?, ?)
                """,
                (
                    int(attempt.lastrowid),
                    f"private question for {topic}",
                    '["a","b","c","d"]',
                    None if skipped else (1 if correct else 2),
                    1 if correct else 0,
                    1 if skipped else 0,
                    "private explanation",
                    workspace_id,
                ),
            )
            if document_id is not None:
                connection.execute(
                    """
                    INSERT INTO quiz_question_sources (
                        question_attempt_id, source_index, filename,
                        page_number, chunk_index, distance,
                        document_id, mime_type, excerpt, workspace_id
                    ) VALUES (?, 1, ?, 1, 0, 0.1, ?, ?, ?, ?)
                    """,
                    (
                        int(question.lastrowid),
                        "private-source.pdf",
                        document_id,
                        "application/pdf",
                        "private excerpt",
                        workspace_id,
                    ),
                )

    def test_repeated_mistakes_rank_above_single_mistake(self) -> None:
        now = datetime.now(timezone.utc)
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Repeated",
            created_at=now,
        )
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Repeated",
            created_at=now - timedelta(hours=1),
        )
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Single",
            created_at=now,
        )

        topics = get_weak_topics(
            recent_days=30,
            dependencies=self.dependencies,
        )

        self.assertEqual([item.topic for item in topics], [
            "Repeated",
            "Single",
        ])
        self.assertGreater(
            topics[0].weakness_score,
            topics[1].weakness_score,
        )

    def test_recent_mistake_ranks_above_stale_mistake(self) -> None:
        now = datetime.now(timezone.utc)
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Recent",
            created_at=now,
        )
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Stale",
            created_at=now - timedelta(days=180),
        )

        topics = get_weak_topics(
            recent_days=365,
            dependencies=self.dependencies,
        )

        self.assertEqual([item.topic for item in topics], [
            "Recent",
            "Stale",
        ])

    def test_skipped_signal_lineage_and_safe_shape(self) -> None:
        now = datetime.now(timezone.utc)
        document_id = self._seed_document(DEFAULT_WORKSPACE_ID)
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Mixed",
            created_at=now,
            document_id=document_id,
        )
        self._seed_outcome(
            workspace_id=DEFAULT_WORKSPACE_ID,
            topic="Mixed",
            created_at=now - timedelta(minutes=5),
            skipped=True,
            document_id=document_id,
        )
        self.dependencies.learning_signals.create(
            "knowledge_gap",
            "quiz_attempt",
            "1",
            {},
            status="active",
            source_question_id="1",
            topic="Mixed",
            statement="private signal statement",
            evidence=({"private": "payload"},),
            confidence=1.0,
            importance=1.0,
            occurrence_count=3,
            first_observed_at=now.isoformat(),
            last_observed_at=now.isoformat(),
        )

        topic = get_weak_topics(
            recent_days=30,
            dependencies=self.dependencies,
        )[0]

        self.assertEqual(topic.recent_incorrect_count, 1)
        self.assertEqual(topic.skipped_count, 1)
        self.assertEqual(topic.active_signal_evidence_count, 3)
        self.assertEqual(topic.source_document_ids, (document_id,))
        safe_repr = repr(topic)
        self.assertNotIn("private signal statement", safe_repr)
        self.assertNotIn("private excerpt", safe_repr)
        self.assertNotIn("embedding", safe_repr.casefold())

    def test_improving_signal_reduces_ranking_without_active_evidence(self) -> None:
        now = datetime.now(timezone.utc)
        for topic in ("Active gap", "Improving gap"):
            self._seed_outcome(
                workspace_id=DEFAULT_WORKSPACE_ID,
                topic=topic,
                created_at=now,
            )
        self.dependencies.learning_signals.create(
            "knowledge_gap",
            "quiz_attempt",
            "1",
            {},
            status="active",
            topic="Active gap",
            confidence=1.0,
            importance=1.0,
            occurrence_count=2,
            first_observed_at=now.isoformat(),
            last_observed_at=now.isoformat(),
        )
        self.dependencies.learning_signals.create(
            "knowledge_gap",
            "quiz_attempt",
            "2",
            {},
            status="improving",
            topic="Improving gap",
            confidence=1.0,
            importance=1.0,
            occurrence_count=2,
            first_observed_at=now.isoformat(),
            last_observed_at=now.isoformat(),
        )

        topics = get_weak_topics(
            recent_days=30,
            dependencies=self.dependencies,
        )

        self.assertEqual([item.topic for item in topics], [
            "Active gap",
            "Improving gap",
        ])
        self.assertEqual(topics[0].active_signal_evidence_count, 2)
        self.assertEqual(topics[1].active_signal_evidence_count, 0)

    def test_empty_history_returns_empty_list(self) -> None:
        self.assertEqual(
            get_weak_topics(dependencies=self.dependencies),
            [],
        )

    def test_guest_isolation_tampering_and_public_id_serialization(self) -> None:
        CREATION_LIMITER.clear_for_test()
        client = TestClient(
            create_app(allow_legacy_default_workspace=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(client.close)
        created_a = client.post(
            "/api/guest-session",
            headers={"Idempotency-Key": "A" * 32},
        )
        created_b = client.post(
            "/api/guest-session",
            headers={"Idempotency-Key": "B" * 32},
        )
        self.assertEqual(created_a.status_code, 201, created_a.text)
        self.assertEqual(created_b.status_code, 201, created_b.text)
        token_a = created_a.json()["token"]
        token_b = created_b.json()["token"]
        service = GuestSessionService(
            get_application_dependencies(),
            pepper=TEST_PEPPER,
        )
        workspace_a = service.authenticate(token_a).workspace.id
        document_id = self._seed_document(workspace_a)
        self._seed_outcome(
            workspace_id=workspace_a,
            topic="Guest A topic",
            created_at=datetime.now(timezone.utc),
            document_id=document_id,
        )

        response_a = client.get(
            "/api/study/weak-topics",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        response_b = client.get(
            "/api/study/weak-topics",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        self.assertEqual(response_a.status_code, 200, response_a.text)
        self.assertEqual(response_b.status_code, 200, response_b.text)
        self.assertEqual(response_b.json(), {"items": [], "total": 0})
        item = response_a.json()["items"][0]
        self.assertEqual(item["topic"], "Guest A topic")
        self.assertIsInstance(item["source_document_ids"][0], str)
        self.assertEqual(item["source_document_ids"][0], str(document_id))
        unsafe_keys = {
            "workspace_id",
            "question",
            "answer",
            "content",
            "embedding",
            "excerpt",
        }
        self.assertTrue(unsafe_keys.isdisjoint(item))

        tampered = client.get(
            "/api/study/weak-topics",
            params={"workspace_id": DEFAULT_WORKSPACE_ID},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        self.assertEqual(tampered.status_code, 403)
        self.assertEqual(
            tampered.json()["error"]["code"],
            "WORKSPACE_ACCESS_DENIED",
        )


if __name__ == "__main__":
    unittest.main()
