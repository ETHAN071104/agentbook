from __future__ import annotations

import importlib.util
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
from backend.application.study_tasks import (
    CreateStudyTaskCommand,
    StudyTaskConflictError,
    StudyTaskService,
    StudyTaskValidationError,
)
from backend.rag import config
from backend.rag import database as rag_database
from backend.repositories.sqlite import initialize_foundation_schema


TEST_PEPPER = "study-task-test-pepper-with-at-least-32-bytes"


class StudyTaskApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.database_path = Path(temporary) / "study-tasks.db"
        self.stack.enter_context(
            patch.object(rag_database, "DATABASE_PATH", self.database_path)
        )
        self.stack.enter_context(patch.object(rag_database, "ensure_directories"))
        self.stack.enter_context(
            patch.object(config, "PERSISTENCE_BACKEND", "sqlite")
        )
        self.stack.enter_context(
            patch.object(config, "GUEST_SESSION_TOKEN_PEPPER", TEST_PEPPER)
        )
        self.stack.enter_context(
            patch.object(config, "ALLOW_LEGACY_DEFAULT_WORKSPACE", False)
        )
        rag_database.initialize_database()
        from backend.memory.database import initialize_memory_database
        from backend.study.database import initialize_study_database

        initialize_memory_database()
        initialize_study_database()
        initialize_foundation_schema()
        configure_application_dependencies(None)
        self.addCleanup(configure_application_dependencies, None)
        get_application_dependencies().workspaces.ensure_default()
        CREATION_LIMITER.clear_for_test()
        self.client = TestClient(
            create_app(allow_legacy_default_workspace=False),
            raise_server_exceptions=False,
        )
        self.addCleanup(self.client.close)
        self.token_a = self._new_guest("A")
        self.token_b = self._new_guest("B")
        self.auth_a = {"Authorization": f"Bearer {self.token_a}"}
        self.auth_b = {"Authorization": f"Bearer {self.token_b}"}
        auth = GuestSessionService(
            get_application_dependencies(),
            pepper=TEST_PEPPER,
        )
        self.workspace_a = auth.authenticate(self.token_a).workspace.id
        self.workspace_b = auth.authenticate(self.token_b).workspace.id

    def _new_guest(self, marker: str) -> str:
        response = self.client.post(
            "/api/guest-session",
            headers={"Idempotency-Key": marker * 32},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return str(response.json()["token"])

    def _create(
        self,
        *,
        auth: dict[str, str] | None = None,
        key: str = "task-operation-0001",
        title: str = "Review database joins",
        description: str = "",
        topic: str = "",
        priority: str = "normal",
        due_at: str | None = None,
    ):
        payload: dict[str, object] = {
            "title": title,
            "description": description,
            "topic": topic,
            "priority": priority,
        }
        if due_at is not None:
            payload["due_at"] = due_at
        return self.client.post(
            "/api/study/tasks",
            json=payload,
            headers={**(auth or self.auth_a), "Idempotency-Key": key},
        )

    def _repository(self, workspace_id: str):
        return build_application_dependencies(workspace_id).study_tasks

    def test_create_task_succeeds_with_public_string_id(self) -> None:
        response = self._create(
            description="Read the worked examples.",
            topic="SQL",
            priority="high",
        )
        self.assertEqual(response.status_code, 201, response.text)
        task = response.json()
        self.assertIsInstance(task["id"], str)
        self.assertTrue(task["id"].isdecimal())
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["priority"], "high")
        self.assertNotIn("workspace_id", task)
        self.assertNotIn("version", task)

    def test_title_validation(self) -> None:
        response = self._create(title="   ")
        self.assertEqual(response.status_code, 422)

    def test_description_length_validation(self) -> None:
        response = self._create(description="x" * 2001)
        self.assertEqual(response.status_code, 422)

    def test_creation_requires_idempotency_key(self) -> None:
        response = self.client.post(
            "/api/study/tasks",
            json={"title": "Review indexes"},
            headers=self.auth_a,
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_workspace_and_internal_fields_are_rejected(self) -> None:
        for extra in (
            {"workspace_id": self.workspace_a},
            {"internal_id": "private"},
            {"completed_at": datetime.now(timezone.utc).isoformat()},
            {"metadata": {"unsafe": True}},
        ):
            response = self.client.post(
                "/api/study/tasks",
                json={"title": "Safe title", **extra},
                headers={
                    **self.auth_a,
                    "Idempotency-Key": "reject-field-key-01",
                },
            )
            self.assertEqual(response.status_code, 422, response.text)

    def test_list_tasks_is_workspace_scoped(self) -> None:
        self.assertEqual(self._create(title="Guest A task").status_code, 201)
        self.assertEqual(
            self._create(
                auth=self.auth_b,
                key="task-operation-0002",
                title="Guest B task",
            ).status_code,
            201,
        )
        response_a = self.client.get("/api/study/tasks", headers=self.auth_a)
        response_b = self.client.get("/api/study/tasks", headers=self.auth_b)
        self.assertEqual(
            [item["title"] for item in response_a.json()["items"]],
            ["Guest A task"],
        )
        self.assertEqual(
            [item["title"] for item in response_b.json()["items"]],
            ["Guest B task"],
        )

    def test_guest_cannot_read_update_or_complete_other_task(self) -> None:
        task_id = self._create(title="Guest A private task").json()["id"]
        read = self.client.get(
            f"/api/study/tasks/{task_id}",
            headers=self.auth_b,
        )
        update = self.client.patch(
            f"/api/study/tasks/{task_id}",
            json={"title": "Tampered"},
            headers=self.auth_b,
        )
        complete = self.client.post(
            f"/api/study/tasks/{task_id}/complete",
            headers=self.auth_b,
        )
        self.assertEqual(read.status_code, 404)
        self.assertEqual(update.status_code, 404)
        self.assertEqual(complete.status_code, 404)
        self.assertEqual(
            read.json()["error"]["code"],
            update.json()["error"]["code"],
        )
        self.assertEqual(
            read.json()["error"]["code"],
            complete.json()["error"]["code"],
        )

    def test_missing_and_cross_workspace_responses_are_indistinguishable(self) -> None:
        task_id = self._create().json()["id"]
        cross = self.client.get(
            f"/api/study/tasks/{task_id}",
            headers=self.auth_b,
        )
        missing = self.client.get(
            "/api/study/tasks/999999999",
            headers=self.auth_b,
        )
        self.assertEqual(cross.status_code, 404)
        self.assertEqual(cross.json()["error"]["code"], missing.json()["error"]["code"])
        self.assertEqual(cross.json()["error"]["reason"], missing.json()["error"]["reason"])

    def test_complete_sets_timestamp_and_duplicate_is_idempotent(self) -> None:
        task_id = self._create().json()["id"]
        first = self.client.post(
            f"/api/study/tasks/{task_id}/complete",
            headers=self.auth_a,
        )
        second = self.client.post(
            f"/api/study/tasks/{task_id}/complete",
            headers=self.auth_a,
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertIsNotNone(first.json()["completed_at"])
        self.assertEqual(first.json()["completed_at"], second.json()["completed_at"])
        events = self._repository(self.workspace_a).list_events(int(task_id))
        self.assertEqual(
            [event.event_type for event in events],
            ["study_task_created", "study_task_completed"],
        )

    def test_reopen_completed_task_clears_completed_at(self) -> None:
        task_id = self._create().json()["id"]
        self.client.post(
            f"/api/study/tasks/{task_id}/complete",
            headers=self.auth_a,
        )
        reopened = self.client.post(
            f"/api/study/tasks/{task_id}/reopen",
            headers=self.auth_a,
        )
        duplicate = self.client.post(
            f"/api/study/tasks/{task_id}/reopen",
            headers=self.auth_a,
        )
        self.assertEqual(reopened.json()["status"], "pending")
        self.assertIsNone(reopened.json()["completed_at"])
        self.assertEqual(duplicate.status_code, 200)
        events = self._repository(self.workspace_a).list_events(int(task_id))
        self.assertEqual(
            [event.event_type for event in events].count("study_task_reopened"),
            1,
        )

    def test_cancel_and_reopen_transition(self) -> None:
        task_id = self._create().json()["id"]
        cancelled = self.client.post(
            f"/api/study/tasks/{task_id}/cancel",
            headers=self.auth_a,
        )
        self.assertEqual(cancelled.json()["status"], "cancelled")
        reopened = self.client.post(
            f"/api/study/tasks/{task_id}/reopen",
            headers=self.auth_a,
        )
        self.assertEqual(reopened.json()["status"], "pending")

    def test_archive_transition_and_duplicate_are_idempotent(self) -> None:
        task_id = self._create().json()["id"]
        archived = self.client.post(
            f"/api/study/tasks/{task_id}/archive",
            headers=self.auth_a,
        )
        duplicate = self.client.post(
            f"/api/study/tasks/{task_id}/archive",
            headers=self.auth_a,
        )
        self.assertEqual(archived.json()["status"], "archived")
        self.assertIsNotNone(archived.json()["archived_at"])
        self.assertEqual(duplicate.json()["archived_at"], archived.json()["archived_at"])
        events = self._repository(self.workspace_a).list_events(int(task_id))
        self.assertEqual(
            [event.event_type for event in events].count("study_task_archived"),
            1,
        )

    def test_invalid_transition_is_rejected(self) -> None:
        task_id = self._create().json()["id"]
        self.client.post(
            f"/api/study/tasks/{task_id}/cancel",
            headers=self.auth_a,
        )
        response = self.client.post(
            f"/api/study/tasks/{task_id}/complete",
            headers=self.auth_a,
        )
        self.assertEqual(response.status_code, 409)

    def test_list_status_filtering(self) -> None:
        pending = self._create(title="Pending").json()["id"]
        completed = self._create(
            key="task-operation-0002",
            title="Completed",
        ).json()["id"]
        self.client.post(
            f"/api/study/tasks/{completed}/complete",
            headers=self.auth_a,
        )
        response = self.client.get(
            "/api/study/tasks",
            params={"status": "pending"},
            headers=self.auth_a,
        )
        self.assertEqual([item["id"] for item in response.json()["items"]], [pending])

    def test_due_date_ordering(self) -> None:
        now = datetime.now(timezone.utc)
        later = (now + timedelta(days=3)).isoformat()
        sooner = (now + timedelta(days=1)).isoformat()
        self._create(title="No due date")
        self._create(
            key="task-operation-0002",
            title="Later",
            due_at=later,
        )
        self._create(
            key="task-operation-0003",
            title="Sooner",
            due_at=sooner,
        )
        response = self.client.get("/api/study/tasks", headers=self.auth_a)
        self.assertEqual(
            [item["title"] for item in response.json()["items"]],
            ["Sooner", "Later", "No due date"],
        )

    def test_due_date_filtering(self) -> None:
        now = datetime.now(timezone.utc)
        soon = (now + timedelta(hours=1)).isoformat()
        late = (now + timedelta(days=10)).isoformat()
        self._create(title="Soon", due_at=soon)
        self._create(
            key="task-operation-0002",
            title="Late",
            due_at=late,
        )
        response = self.client.get(
            "/api/study/tasks",
            params={"due_before": (now + timedelta(days=2)).isoformat()},
            headers=self.auth_a,
        )
        self.assertEqual(
            [item["title"] for item in response.json()["items"]],
            ["Soon"],
        )

    def test_archived_tasks_are_excluded_by_default(self) -> None:
        task_id = self._create().json()["id"]
        self.client.post(
            f"/api/study/tasks/{task_id}/archive",
            headers=self.auth_a,
        )
        default = self.client.get("/api/study/tasks", headers=self.auth_a)
        archived = self.client.get(
            "/api/study/tasks",
            params={"status": "archived"},
            headers=self.auth_a,
        )
        self.assertEqual(default.json()["items"], [])
        self.assertEqual([item["id"] for item in archived.json()["items"]], [task_id])

    def test_update_fields_and_clear_due_date(self) -> None:
        task_id = self._create(
            due_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        ).json()["id"]
        updated = self.client.patch(
            f"/api/study/tasks/{task_id}",
            json={
                "title": "Updated title",
                "description": "Updated description",
                "topic": "Indexes",
                "priority": "low",
                "due_at": None,
            },
            headers=self.auth_a,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        body = updated.json()
        self.assertEqual(body["title"], "Updated title")
        self.assertEqual(body["topic"], "Indexes")
        self.assertEqual(body["priority"], "low")
        self.assertIsNone(body["due_at"])

    def test_empty_patch_and_archived_edit_are_rejected(self) -> None:
        task_id = self._create().json()["id"]
        empty = self.client.patch(
            f"/api/study/tasks/{task_id}",
            json={},
            headers=self.auth_a,
        )
        self.assertEqual(empty.status_code, 422)
        self.client.post(
            f"/api/study/tasks/{task_id}/archive",
            headers=self.auth_a,
        )
        archived = self.client.patch(
            f"/api/study/tasks/{task_id}",
            json={"title": "No longer editable"},
            headers=self.auth_a,
        )
        self.assertEqual(archived.status_code, 409)

    def test_naive_due_timestamp_is_rejected(self) -> None:
        response = self._create(due_at="2030-01-01T12:00:00")
        self.assertEqual(response.status_code, 422)

    def test_duplicate_create_same_key_returns_same_task_and_one_event(self) -> None:
        first = self._create()
        second = self._create()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        task_id = int(first.json()["id"])
        events = self._repository(self.workspace_a).list_events(task_id)
        self.assertEqual(
            [event.event_type for event in events],
            ["study_task_created"],
        )

    def test_idempotency_key_conflicts_on_different_input(self) -> None:
        self.assertEqual(self._create(title="First").status_code, 201)
        conflict = self._create(title="Different")
        self.assertEqual(conflict.status_code, 409)
        tasks = self.client.get("/api/study/tasks", headers=self.auth_a).json()
        self.assertEqual(tasks["total"], 1)

    def test_same_idempotency_key_is_independent_across_workspaces(self) -> None:
        task_a = self._create(title="A").json()
        task_b = self._create(auth=self.auth_b, title="B").json()
        self.assertNotEqual(task_a["id"], task_b["id"])

    def test_different_keys_create_separate_tasks(self) -> None:
        first = self._create().json()["id"]
        second = self._create(key="task-operation-0002").json()["id"]
        self.assertNotEqual(first, second)

    def test_cancelled_task_can_be_recreated_with_a_new_key(self) -> None:
        first = self._create()
        first_task = first.json()
        cancelled = self.client.post(
            f"/api/study/tasks/{first_task['id']}/cancel",
            headers=self.auth_a,
        )
        self.assertEqual(cancelled.status_code, 200)

        second = self._create(key="task-operation-0002")
        second_task = second.json()
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first_task["id"], second_task["id"])
        self.assertIsInstance(second_task["id"], str)
        self.assertEqual(second_task["status"], "pending")

        pending = self.client.get(
            "/api/study/tasks?status=pending",
            headers=self.auth_a,
        ).json()
        self.assertEqual(
            [task["id"] for task in pending["items"]],
            [second_task["id"]],
        )

    def test_replaying_first_key_returns_cancelled_task_without_duplicate(self) -> None:
        first = self._create()
        first_task = first.json()
        cancelled = self.client.post(
            f"/api/study/tasks/{first_task['id']}/cancel",
            headers=self.auth_a,
        )
        self.assertEqual(cancelled.status_code, 200)
        second = self._create(key="task-operation-0002")
        self.assertEqual(second.status_code, 201)

        replay = self._create()
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["id"], first_task["id"])
        self.assertEqual(replay.json()["status"], "cancelled")
        tasks = self.client.get(
            "/api/study/tasks",
            headers=self.auth_a,
        ).json()
        self.assertEqual(tasks["total"], 2)

    def test_identical_patch_creates_audit_event_once(self) -> None:
        task_id = self._create().json()["id"]
        for _ in range(2):
            response = self.client.patch(
                f"/api/study/tasks/{task_id}",
                json={"topic": "Joins"},
                headers=self.auth_a,
            )
            self.assertEqual(response.status_code, 200)
        events = self._repository(self.workspace_a).list_events(int(task_id))
        self.assertEqual(
            [event.event_type for event in events].count("study_task_updated"),
            1,
        )

    def test_audit_events_contain_only_narrow_fields(self) -> None:
        task_id = self._create(
            description="Sensitive learner-entered description"
        ).json()["id"]
        events = self._repository(self.workspace_a).list_events(int(task_id))
        serialized = repr(events)
        self.assertNotIn("Sensitive learner-entered description", serialized)
        self.assertNotIn("workspace_id", serialized)
        self.assertNotIn("payload", serialized)

    def test_protected_endpoints_require_guest_session(self) -> None:
        response = self.client.get("/api/study/tasks")
        self.assertEqual(response.status_code, 401)

    def test_service_rejects_repository_scope_mismatch(self) -> None:
        dependencies = build_application_dependencies(self.workspace_a)
        object.__setattr__(
            dependencies.study_tasks,
            "workspace_id",
            self.workspace_b,
        )
        with self.assertRaises(RuntimeError):
            StudyTaskService(dependencies)

    def test_service_validation_and_idempotency_conflict(self) -> None:
        service = StudyTaskService(
            build_application_dependencies(self.workspace_a)
        )
        with self.assertRaises(StudyTaskValidationError):
            service.create_task(
                CreateStudyTaskCommand(title="Task"),
                idempotency_key="short",
            )
        service.create_task(
            CreateStudyTaskCommand(title="Task"),
            idempotency_key="service-operation-01",
        )
        with self.assertRaises(StudyTaskConflictError):
            service.create_task(
                CreateStudyTaskCommand(title="Different"),
                idempotency_key="service-operation-01",
            )


class StudyTaskMigrationTest(unittest.TestCase):
    def test_revision_is_additive_and_has_rollback(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "0004_persisted_study_tasks.py"
        )
        spec = importlib.util.spec_from_file_location(
            "agentbook_study_tasks_migration",
            migration_path,
        )
        assert spec is not None and spec.loader is not None
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.assertEqual(migration.revision, "0004_persisted_study_tasks")
        self.assertEqual(migration.down_revision, "0003_guest_sessions")
        sql = "\n".join(migration.UPGRADE_STATEMENTS)
        self.assertIn("CREATE TABLE study_tasks", sql)
        self.assertIn("CREATE TABLE study_task_events", sql)
        self.assertIn("FOREIGN KEY (task_id, workspace_id)", sql)
        self.assertIn("UNIQUE (workspace_id, creation_idempotency_key)", sql)
        self.assertTrue(callable(migration.downgrade))

    def test_sqlite_and_cockroach_row_mapping_agree(self) -> None:
        from backend.repositories.cockroach.study_tasks import _task as cockroach_task
        from backend.repositories.sqlite.study_tasks import _task as sqlite_task

        created = datetime.now(timezone.utc)
        common = {
            "title": "Review joins",
            "description": "",
            "topic": "SQL",
            "status": "pending",
            "priority": "normal",
            "due_at": None,
            "completed_at": None,
            "archived_at": None,
            "created_at": created,
            "updated_at": created,
            "version": 1,
        }
        cockroach = cockroach_task({**common, "public_id": 42})
        sqlite = sqlite_task(
            {
                **common,
                "id": 42,
                "created_at": created.isoformat(),
                "updated_at": created.isoformat(),
            }
        )
        self.assertEqual(cockroach, sqlite)


if __name__ == "__main__":
    unittest.main()
