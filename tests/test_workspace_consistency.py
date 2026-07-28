from __future__ import annotations

import hashlib
import tempfile
import unittest

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routes.guest_sessions import CREATION_LIMITER
from backend.application.dependencies import (
    configure_application_dependencies,
    get_application_dependencies,
)
from backend.memory.database import initialize_memory_database
from backend.rag import config
from backend.rag import database as rag_database
from backend.repositories.sqlite import initialize_foundation_schema
from backend.study.database import initialize_study_database


TEST_PEPPER = "workspace-consistency-test-pepper-at-least-32-bytes"


class WorkspaceConsistencyApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory())
        database_path = Path(temporary) / "workspace-consistency.db"

        self.stack.enter_context(
            patch.object(rag_database, "DATABASE_PATH", database_path)
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
        initialize_memory_database()
        initialize_study_database()
        initialize_foundation_schema()
        configure_application_dependencies(None)
        self.addCleanup(configure_application_dependencies, None)
        get_application_dependencies().workspaces.ensure_default()
        CREATION_LIMITER.clear_for_test()

        self.stack.enter_context(
            patch(
                "backend.api.routes.notebooks_documents.index_file_bytes",
                side_effect=self._index_file_bytes,
            )
        )
        self.client = self.stack.enter_context(
            TestClient(
                create_app(allow_legacy_default_workspace=False),
                raise_server_exceptions=False,
            )
        )

    @staticmethod
    def _index_file_bytes(
        *,
        filename: str,
        file_data: bytes,
        max_bytes: int,
    ) -> dict[str, object]:
        if not file_data or len(file_data) > max_bytes:
            raise ValueError("Uploaded file is invalid.")
        dependencies = get_application_dependencies()
        repository = dependencies.documents
        # The production Cockroach schema scopes this uniqueness by workspace.
        # Preserve that contract in the lightweight fake indexing boundary even
        # though the legacy SQLite ingestion table has a global hash index.
        file_hash = hashlib.sha256(
            dependencies.workspace_id.encode("utf-8") + b"\0" + file_data
        ).hexdigest()
        existing = repository.find_by_hash(file_hash)
        if existing is not None:
            return {
                "status": "duplicate",
                "document_id": existing.id,
            }
        document_id = repository.insert(
            filename,
            "text/plain",
            file_hash,
            file_data,
        )
        return {
            "status": "indexed",
            "document_id": document_id,
        }

    def _new_guest(self, marker: str) -> dict[str, str]:
        response = self.client.post(
            "/api/guest-session",
            headers={"Idempotency-Key": marker * 32},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_write_read_refresh_duplicate_and_workspace_isolation(self) -> None:
        auth_a = self._new_guest("A")
        auth_b = self._new_guest("B")
        content = b"Public workspace consistency test data."

        identity = self.client.get("/api/guest-session", headers=auth_a)
        self.assertEqual(identity.status_code, 200)

        before_documents = self.client.get("/api/documents", headers=auth_a)
        before_dashboard = self.client.get("/api/dashboard", headers=auth_a)
        self.assertEqual(before_documents.json()["total"], 0)
        self.assertEqual(before_dashboard.json()["counts"]["documents"], 0)

        upload = self.client.post(
            "/api/documents",
            headers=auth_a,
            files={"file": ("consistency.txt", content, "text/plain")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        self.assertFalse(upload.json()["duplicate"])
        document_id = upload.json()["document"]["id"]
        self.assertIsInstance(document_id, str)
        self.assertTrue(document_id.isdecimal())

        documents = self.client.get("/api/documents", headers=auth_a)
        notebooks = self.client.get("/api/notebooks", headers=auth_a)
        dashboard = self.client.get("/api/dashboard", headers=auth_a)
        self.assertEqual(documents.json()["total"], 1)
        self.assertEqual(
            [item["id"] for item in documents.json()["items"]],
            [document_id],
        )
        self.assertEqual(notebooks.json()["total"], 0)
        self.assertEqual(notebooks.json()["unsorted"]["document_count"], 1)
        self.assertEqual(dashboard.json()["counts"]["documents"], 1)
        self.assertEqual(dashboard.json()["counts"]["unsorted_documents"], 1)

        created_task = self.client.post(
            "/api/study/tasks",
            headers={
                **auth_a,
                "Idempotency-Key": "workspace-consistency-task-key",
            },
            json={
                "title": "Workspace consistency task",
                "description": "",
                "topic": "",
                "priority": "normal",
            },
        )
        self.assertEqual(created_task.status_code, 201, created_task.text)
        task_id = created_task.json()["id"]
        self.assertIsInstance(task_id, str)
        self.assertTrue(task_id.isdecimal())

        refreshed_identity = self.client.get(
            "/api/guest-session",
            headers=auth_a,
        )
        refreshed_documents = self.client.get(
            "/api/documents",
            headers=auth_a,
        )
        refreshed_dashboard = self.client.get(
            "/api/dashboard",
            headers=auth_a,
        )
        refreshed_tasks = self.client.get(
            "/api/study/tasks",
            headers=auth_a,
        )
        self.assertEqual(refreshed_identity.status_code, 200)
        self.assertEqual(refreshed_documents.json()["total"], 1)
        self.assertEqual(refreshed_dashboard.json()["counts"]["documents"], 1)
        self.assertEqual(
            [item["id"] for item in refreshed_tasks.json()["items"]],
            [task_id],
        )

        duplicate = self.client.post(
            "/api/documents",
            headers=auth_a,
            files={"file": ("renamed.txt", content, "text/plain")},
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(duplicate.json()["document"]["id"], document_id)

        b_documents = self.client.get("/api/documents", headers=auth_b)
        b_dashboard = self.client.get("/api/dashboard", headers=auth_b)
        b_tasks = self.client.get("/api/study/tasks", headers=auth_b)
        self.assertEqual(b_documents.json()["total"], 0)
        self.assertEqual(b_dashboard.json()["counts"]["documents"], 0)
        self.assertEqual(b_tasks.json()["total"], 0)

        cross_document = self.client.get(
            f"/api/documents/{document_id}",
            headers=auth_b,
        )
        self.assertEqual(cross_document.status_code, 404)

        upload_b = self.client.post(
            "/api/documents",
            headers=auth_b,
            files={"file": ("consistency.txt", content, "text/plain")},
        )
        self.assertEqual(upload_b.status_code, 200, upload_b.text)
        self.assertFalse(upload_b.json()["duplicate"])
        self.assertNotEqual(upload_b.json()["document"]["id"], document_id)

        for path in (
            "/api/documents",
            "/api/notebooks",
            "/api/dashboard",
            "/api/study/tasks",
        ):
            missing = self.client.get(path)
            invalid = self.client.get(
                path,
                headers={"Authorization": "Bearer invalid"},
            )
            self.assertEqual(missing.status_code, 401)
            self.assertEqual(invalid.status_code, 401)
            self.assertNotIn("workspace_id", missing.text)
            self.assertNotIn("workspace_id", invalid.text)
