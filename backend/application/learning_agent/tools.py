from __future__ import annotations

import re
from collections.abc import Callable

from backend.application.dependencies import (
    ApplicationDependencies,
    get_application_dependencies,
)
from backend.application.learning_agent.models import (
    CurrentStudyPlanArguments,
    RecentMistakesArguments,
    SearchStudyMaterialsArguments,
    ToolName,
    ToolResult,
    WeakTopicsArguments,
)
from backend.application.weak_topics import get_weak_topics
from backend.rag.rag_service import retrieve_sources
from backend.study.planner import build_adaptive_study_plan


MAX_MATERIAL_EXCERPT = 400
MAX_QUESTION_SUMMARY = 180
_SQL_REQUEST = re.compile(
    r"(?is)^\s*(?:select|insert|update|delete|alter|drop|create|grant|revoke|"
    r"truncate|execute|exec)\b|;\s*(?:--|/\*)"
)
_WHITESPACE = re.compile(r"\s+")


def _compact_text(value: object, maximum: int) -> str:
    compact = _WHITESPACE.sub(" ", str(value)).strip()
    if len(compact) <= maximum:
        return compact
    return compact[: maximum - 1].rstrip() + "…"


def _public_ids(values: object) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return [
        str(value)
        for value in sorted({int(item) for item in values if int(item) > 0})
    ]


class LearningAgentTools:
    """Safe projections over the authenticated workspace's read repositories."""

    def __init__(
        self,
        dependencies: ApplicationDependencies | None = None,
        *,
        source_retriever: Callable[..., object] = retrieve_sources,
        plan_builder: Callable[..., object] = build_adaptive_study_plan,
    ) -> None:
        self.dependencies = dependencies or get_application_dependencies()
        self._source_retriever = source_retriever
        self._plan_builder = plan_builder
        self._assert_scoped_dependencies()

    def _assert_scoped_dependencies(self) -> None:
        workspace_id = str(self.dependencies.workspace_id)
        for repository_name in (
            "quizzes",
            "study_sessions",
            "memories",
            "learning_signals",
            "document_vectors",
        ):
            repository = getattr(self.dependencies, repository_name, None)
            repository_workspace = getattr(repository, "workspace_id", None)
            if (
                repository_workspace is not None
                and str(repository_workspace) != workspace_id
            ):
                raise RuntimeError(
                    "Learning Agent repository scope does not match the "
                    "authenticated workspace."
                )

    def execute(self, tool_name: ToolName, arguments: dict[str, object]) -> ToolResult:
        if tool_name == "get_weak_topics":
            return self.get_weak_topics(WeakTopicsArguments.model_validate(arguments))
        if tool_name == "get_recent_mistakes":
            return self.get_recent_mistakes(
                RecentMistakesArguments.model_validate(arguments)
            )
        if tool_name == "search_study_materials":
            return self.search_study_materials(
                SearchStudyMaterialsArguments.model_validate(arguments)
            )
        if tool_name == "get_current_study_plan":
            return self.get_current_study_plan(
                CurrentStudyPlanArguments.model_validate(arguments)
            )
        raise ValueError("Unsupported Learning Agent tool.")

    def get_weak_topics(self, arguments: WeakTopicsArguments) -> ToolResult:
        topics = get_weak_topics(
            limit=arguments.limit,
            recent_days=arguments.recent_days,
            dependencies=self.dependencies,
        )
        items = [
            {
                "topic": item.topic,
                "weakness_score": item.weakness_score,
                "recent_incorrect_count": item.recent_incorrect_count,
                "skipped_count": item.skipped_count,
                "active_signal_evidence_count": item.active_signal_evidence_count,
                "latest_observed_at": item.latest_observed_at,
                "source_document_public_ids": _public_ids(
                    item.source_document_ids
                ),
                "evidence_summary": item.evidence_summary,
                "recommended_next_action": item.recommended_next_action,
            }
            for item in topics
        ]
        return ToolResult(
            tool_name="get_weak_topics",
            success=True,
            data={"items": items},
            safe_summary=(
                f"Found {len(items)} weak topic"
                f"{'' if len(items) == 1 else 's'} in recent learning evidence."
            ),
            warning=None if items else "No weak-topic evidence is available yet.",
            evidence_count=len(items),
        )

    def get_recent_mistakes(
        self,
        arguments: RecentMistakesArguments,
    ) -> ToolResult:
        # Scan a bounded recent window because one attempt can contain several
        # correct questions before an incorrect or skipped one.
        attempts = list(
            self.dependencies.quizzes.list_attempts(
                limit=min(max(arguments.limit * 3, 10), 30)
            )
        )
        attempts.sort(key=lambda item: item.created_at, reverse=True)
        mistakes: list[dict[str, object]] = []
        for attempt in attempts:
            questions = self.dependencies.quizzes.list_questions(attempt.id)
            for question in questions:
                if not question.presented or (
                    question.is_correct and not question.skipped
                ):
                    continue
                outcome = "skipped" if question.skipped else "incorrect"
                source_ids = _public_ids(
                    [
                        source.document_id
                        for source in self.dependencies.quizzes.list_sources(
                            question.id
                        )
                        if source.document_id is not None
                    ]
                )
                mistakes.append(
                    {
                        "quiz_attempt_public_id": str(attempt.id),
                        "topic": _compact_text(attempt.quiz_topic, 120),
                        "question_summary": _compact_text(
                            question.question,
                            MAX_QUESTION_SUMMARY,
                        ),
                        "outcome": outcome,
                        "occurred_at": attempt.created_at,
                        "source_document_public_ids": source_ids,
                        "learning_evidence": (
                            f"This question was recorded as {outcome} in a "
                            "recent quiz."
                        ),
                        "next_action_hint": (
                            "Review the linked material and retry a short "
                            "focused quiz."
                        ),
                    }
                )
                if len(mistakes) >= arguments.limit:
                    break
            if len(mistakes) >= arguments.limit:
                break
        return ToolResult(
            tool_name="get_recent_mistakes",
            success=True,
            data={"items": mistakes},
            safe_summary=(
                f"Found {len(mistakes)} recent incorrect or skipped quiz "
                f"outcome{'' if len(mistakes) == 1 else 's'}."
            ),
            warning=None if mistakes else "No recent quiz mistakes are available.",
            evidence_count=len(mistakes),
        )

    def search_study_materials(
        self,
        arguments: SearchStudyMaterialsArguments,
    ) -> ToolResult:
        query = _compact_text(arguments.query, 300)
        if len(re.sub(r"[^A-Za-z0-9]+", "", query)) < 2:
            raise ValueError("Study-material search query is not meaningful.")
        if _SQL_REQUEST.search(query):
            raise ValueError("Arbitrary database queries are not supported.")
        sources = list(self._source_retriever(query, k=arguments.limit))
        items: list[dict[str, object]] = []
        for source in sources[: arguments.limit]:
            document_id = getattr(source, "document_id", None)
            if document_id is None or int(document_id) <= 0:
                continue
            items.append(
                {
                    "document_title": _compact_text(
                        getattr(source, "filename", "Study material"),
                        180,
                    ),
                    "document_public_id": str(document_id),
                    "excerpt": _compact_text(
                        getattr(source, "text", ""),
                        MAX_MATERIAL_EXCERPT,
                    ),
                    "page_number": getattr(source, "page_number", None),
                    "slide_number": getattr(source, "slide_number", None),
                    "chunk_index": getattr(source, "chunk_index", None),
                }
            )
        return ToolResult(
            tool_name="search_study_materials",
            success=True,
            data={"query": query, "items": items},
            safe_summary=(
                f"Found {len(items)} relevant excerpt"
                f"{'' if len(items) == 1 else 's'} in this workspace."
            ),
            warning=None if items else "No matching indexed material was found.",
            evidence_count=len(items),
        )

    def get_current_study_plan(
        self,
        arguments: CurrentStudyPlanArguments,
    ) -> ToolResult:
        plan = self._plan_builder(
            total_minutes=arguments.available_minutes,
            max_items=arguments.max_items,
        )
        items = [
            {
                "rank": item.rank,
                "title": _compact_text(item.title, 180),
                "action": _compact_text(item.action, 300),
                "estimated_minutes": item.estimated_minutes,
                "completion_state": "recommended",
                "deadline": None,
                "source_document_public_ids": _public_ids(
                    item.source_document_ids
                ),
            }
            for item in plan.items
        ]
        return ToolResult(
            tool_name="get_current_study_plan",
            success=True,
            data={
                "plan_title": (
                    f"Current {plan.requested_minutes}-minute adaptive study plan"
                ),
                "requested_minutes": plan.requested_minutes,
                "allocated_minutes": plan.allocated_minutes,
                "items": items,
                "recommended_next_item": items[0] if items else None,
                "completion_state": (
                    "ready" if items else "waiting_for_learning_evidence"
                ),
                "deadline": None,
            },
            safe_summary=(
                f"Built a read-only plan with {len(items)} recommended item"
                f"{'' if len(items) == 1 else 's'}."
            ),
            warning=(
                None
                if items
                else "There is not enough learning evidence for a plan yet."
            ),
            evidence_count=len(items),
        )
