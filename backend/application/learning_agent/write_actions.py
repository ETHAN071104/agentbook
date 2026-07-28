from __future__ import annotations

import hashlib
import hmac
import json
import re

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, ValidationError

from backend.application.dependencies import (
    ApplicationDependencies,
    get_application_dependencies,
)
from backend.application.learning_agent.models import (
    AgentModel,
    AgentTaskPreview,
    AgentWriteProposal,
    CompleteStudyTaskCandidate,
    CreateStudyTaskCandidate,
    ToolResult,
    WriteAction,
)
from backend.application.study_tasks import (
    CreateStudyTaskCommand,
    StudyTaskConflictError,
    StudyTaskNotFoundError,
    StudyTaskService,
    StudyTaskValidationError,
)
from backend.domain import StudyTask
from backend.repositories.interfaces import RepositoryConflictError


PROPOSAL_WORKFLOW = "agent_action_proposal"
PROPOSAL_TTL_MINUTES = 10
MAX_TASK_MATCHES = 5
_NORMALIZE = re.compile(r"[^a-z0-9]+")


class AgentWriteActionError(RuntimeError):
    pass


class AgentWriteProposalNotFound(AgentWriteActionError):
    pass


class AgentWriteProposalExpired(AgentWriteActionError):
    pass


class AgentWriteProposalConsumed(AgentWriteActionError):
    pass


class AgentWriteProposalConflict(AgentWriteActionError):
    pass


class AgentWriteProposalInvalid(AgentWriteActionError):
    pass


class StoredCreateArguments(AgentModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=200)
    priority: Literal["low", "normal", "high"]
    due_at: str | None = None


class StoredCompleteArguments(AgentModel):
    task_public_id: int = Field(gt=0)
    expected_version: int = Field(gt=0)
    expected_status: Literal["pending"] = "pending"
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=200)
    priority: Literal["low", "normal", "high"]
    due_at: str | None = None


class StoredAgentProposal(AgentModel):
    action: WriteAction
    arguments: dict[str, Any]
    evidence_summary: str = Field(default="", max_length=500)
    user_rationale: str = Field(default="", max_length=300)
    operation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class PreparedAgentWrite:
    answer: str
    proposal: AgentWriteProposal | None


@dataclass(frozen=True)
class AgentActionExecution:
    executed: bool
    action: WriteAction
    task: StudyTask
    message: str
    suggested_ui_action: Literal["open_study_tasks"] = "open_study_tasks"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AgentWriteProposalInvalid("Proposal timestamp is invalid.")
    return parsed.astimezone(timezone.utc)


def _operation_hash(
    workspace_id: str,
    *,
    proposal_id: str,
    action: WriteAction,
    arguments: dict[str, Any],
    evidence_summary: str,
    user_rationale: str,
) -> str:
    canonical = json.dumps(
        {
            "action": action,
            "arguments": arguments,
            "evidence_summary": evidence_summary,
            "proposal_id": proposal_id,
            "user_rationale": user_rationale,
            "workspace_id": workspace_id,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_label(value: str) -> str:
    return _NORMALIZE.sub(" ", value.casefold()).strip()


def _bounded_summary(results: list[ToolResult], rationale: str) -> str:
    summaries = [
        result.safe_summary
        for result in results
        if result.success and result.evidence_count > 0
    ]
    text = " ".join([rationale, *summaries]).strip()
    return text[:500]


def _evidence_create_values(
    results: list[ToolResult],
) -> tuple[str, str, str] | None:
    for result in results:
        items = result.data.get("items")
        if not result.success or not isinstance(items, list) or not items:
            continue
        first = items[0]
        if not isinstance(first, dict):
            continue
        if result.tool_name == "get_weak_topics":
            topic = str(first.get("topic", "")).strip()
            if topic:
                return f"Review {topic}"[:200], "", topic[:200]
        if result.tool_name == "get_current_study_plan":
            title = str(first.get("title", "")).strip()
            description = str(first.get("action", "")).strip()
            if title:
                return title[:200], description[:2000], ""
    return None


def _match_pending_tasks(
    tasks: tuple[StudyTask, ...],
    query: str,
) -> list[StudyTask]:
    normalized_query = _normalize_label(query)
    if not normalized_query:
        return []
    ranked: list[tuple[int, StudyTask]] = []
    for task in tasks:
        title = _normalize_label(task.title)
        topic = _normalize_label(task.topic)
        score = 0
        if title == normalized_query:
            score = 4
        elif normalized_query in title or title in normalized_query:
            score = 3
        elif topic and topic == normalized_query:
            score = 2
        elif topic and (
            normalized_query in topic or topic in normalized_query
        ):
            score = 1
        if score:
            ranked.append((score, task))
    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].due_at is None,
            item[1].due_at or "",
            -item[1].id,
        )
    )
    exact = [task for score, task in ranked if score == 4]
    if len(exact) == 1:
        return exact
    if len(exact) > 1:
        return exact[:MAX_TASK_MATCHES]
    return [task for _score, task in ranked[:MAX_TASK_MATCHES]]


class AgentWriteProposalService:
    def __init__(
        self,
        dependencies: ApplicationDependencies | None = None,
    ) -> None:
        self.dependencies = dependencies or get_application_dependencies()
        self.tasks = StudyTaskService(self.dependencies)
        for repository in (
            self.dependencies.workflows,
            self.dependencies.study_tasks,
        ):
            if str(repository.workspace_id) != str(self.dependencies.workspace_id):
                raise RuntimeError(
                    "Agent write repository scope does not match the "
                    "authenticated workspace."
                )

    def prepare(
        self,
        action: WriteAction,
        candidate_arguments: dict[str, Any],
        *,
        results: list[ToolResult],
        user_rationale: str,
    ) -> PreparedAgentWrite:
        if action == "create_study_task":
            return self._prepare_create(
                candidate_arguments,
                results=results,
                user_rationale=user_rationale,
            )
        if action == "complete_study_task":
            return self._prepare_complete(
                candidate_arguments,
                user_rationale=user_rationale,
            )
        raise AgentWriteProposalInvalid("Unsupported Agent write action.")

    def _prepare_create(
        self,
        candidate_arguments: dict[str, Any],
        *,
        results: list[ToolResult],
        user_rationale: str,
    ) -> PreparedAgentWrite:
        try:
            candidate = CreateStudyTaskCandidate.model_validate(
                candidate_arguments
            )
        except ValidationError as error:
            raise AgentWriteProposalInvalid(
                "The proposed task input is invalid."
            ) from error
        title = candidate.title
        description = candidate.description
        topic = candidate.topic
        if title is None:
            evidence_values = _evidence_create_values(results)
            if evidence_values is None:
                return PreparedAgentWrite(
                    answer=(
                        "I could not find enough learning evidence to prepare "
                        "a task. Tell me the topic you want to study."
                    ),
                    proposal=None,
                )
            title, evidence_description, evidence_topic = evidence_values
            if not description:
                description = evidence_description
            if not topic:
                topic = evidence_topic
        try:
            prepared = self.tasks.prepare_create_task(
                CreateStudyTaskCommand(
                    title=title,
                    description=description,
                    topic=topic,
                    priority=candidate.priority,
                    due_at=candidate.due_at,
                )
            )
        except StudyTaskValidationError as error:
            raise AgentWriteProposalInvalid(str(error)) from error
        arguments = StoredCreateArguments(
            title=prepared.title,
            description=prepared.description,
            topic=prepared.topic,
            priority=prepared.priority,
            due_at=(
                prepared.due_at
                if isinstance(prepared.due_at, str)
                else None
            ),
        )
        evidence_summary = _bounded_summary(results, user_rationale)
        proposal = self._store(
            action="create_study_task",
            arguments=arguments.model_dump(),
            evidence_summary=evidence_summary,
            user_rationale=user_rationale,
            preview=AgentTaskPreview(
                title=arguments.title,
                description=arguments.description,
                topic=arguments.topic,
                status="pending",
                priority=arguments.priority,
                due_at=arguments.due_at,
            ),
            display_title="Create Study Task",
            display_summary=(
                "Review and confirm this task before it is created."
            ),
        )
        return PreparedAgentWrite(
            answer=(
                "I prepared a task for your confirmation. Nothing has been "
                "changed yet."
            ),
            proposal=proposal,
        )

    def _prepare_complete(
        self,
        candidate_arguments: dict[str, Any],
        *,
        user_rationale: str,
    ) -> PreparedAgentWrite:
        try:
            candidate = CompleteStudyTaskCandidate.model_validate(
                candidate_arguments
            )
        except ValidationError as error:
            raise AgentWriteProposalInvalid(
                "The task lookup request is invalid."
            ) from error
        pending = self.tasks.list_tasks(status="pending", limit=50)
        matches = _match_pending_tasks(pending.items, candidate.query)
        if not matches:
            return PreparedAgentWrite(
                answer=(
                    "I could not find a matching pending task. Nothing has "
                    "been changed."
                ),
                proposal=None,
            )
        if len(matches) > 1:
            labels = "; ".join(task.title for task in matches[:3])
            return PreparedAgentWrite(
                answer=(
                    "I found multiple matching pending tasks: "
                    f"{labels}. Tell me the exact task title to complete. "
                    "Nothing has been changed."
                ),
                proposal=None,
            )
        task = matches[0]
        arguments = StoredCompleteArguments(
            task_public_id=task.id,
            expected_version=task.version,
            title=task.title,
            description=task.description,
            topic=task.topic,
            priority=task.priority,
            due_at=task.due_at,
        )
        proposal = self._store(
            action="complete_study_task",
            arguments=arguments.model_dump(),
            evidence_summary=user_rationale,
            user_rationale=user_rationale,
            preview=AgentTaskPreview(
                title=task.title,
                description="",
                topic=task.topic,
                status=task.status,
                priority=task.priority,
                due_at=task.due_at,
            ),
            display_title="Complete Study Task",
            display_summary=(
                "Review and confirm before this task is marked completed."
            ),
        )
        return PreparedAgentWrite(
            answer=(
                "I prepared this task completion for your confirmation. "
                "Nothing has been changed yet."
            ),
            proposal=proposal,
        )

    def _store(
        self,
        *,
        action: WriteAction,
        arguments: dict[str, Any],
        evidence_summary: str,
        user_rationale: str,
        preview: AgentTaskPreview,
        display_title: str,
        display_summary: str,
    ) -> AgentWriteProposal:
        proposal_id = str(uuid4())
        expires_at = _iso(_utc_now() + timedelta(minutes=PROPOSAL_TTL_MINUTES))
        operation_hash = _operation_hash(
            self.dependencies.workspace_id,
            proposal_id=proposal_id,
            action=action,
            arguments=arguments,
            evidence_summary=evidence_summary,
            user_rationale=user_rationale,
        )
        stored = StoredAgentProposal(
            action=action,
            arguments=arguments,
            evidence_summary=evidence_summary,
            user_rationale=user_rationale,
            operation_hash=operation_hash,
        )
        self.dependencies.workflows.put(
            proposal_id,
            PROPOSAL_WORKFLOW,
            stored.model_dump(mode="json"),
            expires_at,
        )
        return AgentWriteProposal(
            proposal_id=proposal_id,
            action=action,
            display_title=display_title,
            display_summary=display_summary,
            task_preview=preview,
            evidence_summary=evidence_summary,
            expires_at=expires_at,
        )

    def confirm(self, proposal_id: str) -> AgentActionExecution:
        def execute(_unit_of_work: object) -> AgentActionExecution:
            state = self.dependencies.workflows.get(
                proposal_id,
                PROPOSAL_WORKFLOW,
                include_terminal=True,
            )
            if state is None:
                # SQLite marks an expired pending workflow during get(). Read
                # it once more inside the same transaction for a safe status.
                terminal = self.dependencies.workflows.get(
                    proposal_id,
                    PROPOSAL_WORKFLOW,
                    include_terminal=True,
                )
                if terminal is not None and terminal.status == "expired":
                    raise AgentWriteProposalExpired(
                        "This confirmation has expired."
                    )
                raise AgentWriteProposalNotFound(
                    "The requested confirmation was not found."
                )
            if state.workflow_type != PROPOSAL_WORKFLOW:
                raise AgentWriteProposalNotFound(
                    "The requested confirmation was not found."
                )
            if state.status == "completed":
                raise AgentWriteProposalConsumed(
                    "This confirmation was already executed."
                )
            if state.status != "pending":
                if state.status == "expired":
                    raise AgentWriteProposalExpired(
                        "This confirmation has expired."
                    )
                raise AgentWriteProposalConsumed(
                    "This confirmation is no longer available."
                )
            if _parse_time(state.expires_at) <= _utc_now():
                raise AgentWriteProposalExpired(
                    "This confirmation has expired."
                )
            try:
                stored = StoredAgentProposal.model_validate(state.payload)
            except ValidationError as error:
                raise AgentWriteProposalInvalid(
                    "The stored confirmation is invalid."
                ) from error
            expected_hash = _operation_hash(
                self.dependencies.workspace_id,
                proposal_id=proposal_id,
                action=stored.action,
                arguments=stored.arguments,
                evidence_summary=stored.evidence_summary,
                user_rationale=stored.user_rationale,
            )
            if not hmac.compare_digest(
                stored.operation_hash,
                expected_hash,
            ):
                raise AgentWriteProposalInvalid(
                    "The stored confirmation could not be verified."
                )
            if stored.action == "create_study_task":
                try:
                    arguments = StoredCreateArguments.model_validate(
                        stored.arguments
                    )
                    task, _created = self.tasks.create_task(
                        CreateStudyTaskCommand(
                            title=arguments.title,
                            description=arguments.description,
                            topic=arguments.topic,
                            priority=arguments.priority,
                            due_at=arguments.due_at,
                        ),
                        idempotency_key=f"agent-proposal:{proposal_id}",
                    )
                except (ValidationError, StudyTaskValidationError) as error:
                    raise AgentWriteProposalInvalid(
                        "The proposed task is no longer valid."
                    ) from error
                message = "The task has been created."
            elif stored.action == "complete_study_task":
                try:
                    arguments = StoredCompleteArguments.model_validate(
                        stored.arguments
                    )
                except ValidationError as error:
                    raise AgentWriteProposalInvalid(
                        "The proposed completion is invalid."
                    ) from error
                try:
                    current = self.tasks.get_task(arguments.task_public_id)
                except StudyTaskNotFoundError as error:
                    raise AgentWriteProposalConflict(
                        "The target task is no longer available."
                    ) from error
                if (
                    current.status != arguments.expected_status
                    or current.version != arguments.expected_version
                ):
                    raise AgentWriteProposalConflict(
                        "The target task changed after this confirmation was prepared."
                    )
                try:
                    task = self.tasks.complete_task(
                        arguments.task_public_id
                    )
                except (
                    StudyTaskConflictError,
                    StudyTaskNotFoundError,
                ) as error:
                    raise AgentWriteProposalConflict(
                        "The target task can no longer be completed."
                    ) from error
                message = "The task has been completed."
            else:
                raise AgentWriteProposalInvalid(
                    "Unsupported Agent write action."
                )
            try:
                self.dependencies.workflows.decide(
                    proposal_id,
                    state.version,
                    "completed",
                    {"action": stored.action},
                )
            except RepositoryConflictError as error:
                raise AgentWriteProposalConsumed(
                    "This confirmation was already executed."
                ) from error
            return AgentActionExecution(
                executed=True,
                action=stored.action,
                task=task,
                message=message,
            )

        return self.dependencies.unit_of_work().run(execute)
