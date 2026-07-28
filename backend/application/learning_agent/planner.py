from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from backend.application.learning_agent.models import (
    ALLOWED_TOOL_NAMES,
    CompleteStudyTaskCandidate,
    CreateStudyTaskCandidate,
    CurrentStudyPlanArguments,
    PlannerDecision,
    ProposedToolCall,
    RecentMistakesArguments,
    SearchStudyMaterialsArguments,
    ValidatedPlan,
    ValidatedToolCall,
    WeakTopicsArguments,
    WriteAction,
)
from backend.llm.factory import create_chat_model


MAX_TOOL_CALLS = 4
_SQL_LIKE = re.compile(
    r"(?is)^\s*(?:select|insert|update|delete|alter|drop|create|grant|revoke|"
    r"truncate|execute|exec)\b|;\s*(?:--|/\*)"
)
_UNSAFE_PLANNER_TEXT = re.compile(
    r"(?is)\bworkspace_id\b|\bdatabase_url\b|\btoken_hash\b|"
    r"\bcreation_key_hash\b|\bbearer\s+[A-Za-z0-9._~-]{8,}|"
    r"\b(?:postgres|postgresql)://"
)

PLANNER_SYSTEM_PROMPT = """
You route one learner question into exactly one mode:
- answer_only
- read_only_tools
- propose_write

Approved read-only tools:
- get_weak_topics(limit 1-5, recent_days 1-365 or null)
- get_recent_mistakes(limit 1-10)
- search_study_materials(query 2-300 characters, limit 1-5)
- get_current_study_plan(available_minutes 10-240, max_items 1-5)

Approved proposed write actions:
- create_study_task with title, description, topic, due_at, priority
- complete_study_task with only a short task-title/topic query

Choose at most four tools, and never choose the same tool twice. Choose zero
tools for answer_only. propose_write may contain exactly one approved action
and may use read-only evidence first. Never claim a write was completed. Never
include a workspace identifier, task identifier, idempotency key, SQL, hidden
reasoning, or unsupported argument. If a create request depends on the
learner's weakness or recommendation, leave title null and choose the relevant
read-only evidence tool. user_rationale is a short learner-facing explanation.
reasoning_summary is one short routing sentence, not step-by-step analysis.
""".strip()


class PlanValidationError(ValueError):
    pass


def _validated_arguments(call: ProposedToolCall) -> dict[str, Any]:
    try:
        if call.tool_name == "get_weak_topics":
            return WeakTopicsArguments.model_validate(call.arguments).model_dump()
        if call.tool_name == "get_recent_mistakes":
            return RecentMistakesArguments.model_validate(
                call.arguments
            ).model_dump()
        if call.tool_name == "search_study_materials":
            arguments = SearchStudyMaterialsArguments.model_validate(call.arguments)
            if _SQL_LIKE.search(arguments.query):
                raise PlanValidationError("SQL-like search requests are not allowed.")
            if len(re.sub(r"[^A-Za-z0-9]+", "", arguments.query)) < 2:
                raise PlanValidationError("Search query is not meaningful.")
            return arguments.model_dump()
        if call.tool_name == "get_current_study_plan":
            return CurrentStudyPlanArguments.model_validate(
                call.arguments
            ).model_dump()
    except ValidationError as error:
        raise PlanValidationError("Planner supplied invalid tool arguments.") from error
    raise PlanValidationError("Planner selected an unknown tool.")


def _validated_write_arguments(
    action: str,
    arguments: dict[str, Any],
) -> tuple[WriteAction, dict[str, Any]]:
    try:
        if action == "create_study_task":
            validated = CreateStudyTaskCandidate.model_validate(arguments)
            return "create_study_task", validated.model_dump()
        if action == "complete_study_task":
            validated = CompleteStudyTaskCandidate.model_validate(arguments)
            if _SQL_LIKE.search(validated.query):
                raise PlanValidationError("SQL-like task lookup is not allowed.")
            return "complete_study_task", validated.model_dump()
    except ValidationError as error:
        raise PlanValidationError(
            "Planner supplied invalid write proposal arguments."
        ) from error
    raise PlanValidationError("Planner selected an unsupported write action.")


def validate_plan(decision: PlannerDecision, *, used_fallback: bool = False) -> ValidatedPlan:
    if _UNSAFE_PLANNER_TEXT.search(decision.user_rationale):
        raise PlanValidationError("Planner rationale contains unsafe content.")
    if len(decision.selected_tools) > MAX_TOOL_CALLS:
        raise PlanValidationError("Planner selected too many tools.")
    seen: set[str] = set()
    calls: list[ValidatedToolCall] = []
    for proposed in decision.selected_tools:
        if proposed.tool_name not in ALLOWED_TOOL_NAMES:
            raise PlanValidationError("Planner selected an unknown tool.")
        if proposed.tool_name in seen:
            raise PlanValidationError("Planner selected a duplicate tool.")
        seen.add(proposed.tool_name)
        calls.append(
            ValidatedToolCall(
                tool_name=proposed.tool_name,
                arguments=_validated_arguments(proposed),
            )
        )
    if decision.mode == "answer_only" and calls:
        raise PlanValidationError(
            "An answer-only plan cannot include tool calls."
        )
    if decision.mode != "propose_write":
        if decision.proposed_action is not None or decision.candidate_arguments:
            raise PlanValidationError(
                "Only propose-write mode can include a write action."
            )
        action = None
        candidate_arguments: dict[str, Any] = {}
    else:
        if decision.proposed_action is None:
            raise PlanValidationError(
                "A propose-write plan requires one approved action."
            )
        action, candidate_arguments = _validated_write_arguments(
            decision.proposed_action,
            decision.candidate_arguments,
        )
    return ValidatedPlan(
        mode=decision.mode,
        selected_tools=calls,
        proposed_action=action,
        candidate_arguments=candidate_arguments,
        user_rationale=decision.user_rationale,
        reasoning_summary=decision.reasoning_summary,
        used_fallback=used_fallback,
    )


def _tomorrow_due_at(text: str) -> str | None:
    if "tomorrow" not in text.casefold():
        return None
    local_now = datetime.now().astimezone()
    tomorrow = (local_now + timedelta(days=1)).date()
    return datetime.combine(
        tomorrow,
        datetime.min.time().replace(hour=9),
        tzinfo=local_now.tzinfo,
    ).isoformat()


def _create_candidate(message: str) -> dict[str, Any]:
    title = " ".join(message.split()).strip(" .!?")
    title = re.sub(
        r"(?is)^(?:create|add|make)\s+",
        "",
        title,
    )
    title = re.sub(
        r"(?is)^(?:(?:a|one|this)\s+)?(?:study\s+)?task"
        r"(?:\s+(?:to|for|about))?\s*",
        "",
        title,
    )
    title = re.sub(
        r"(?is)^this\s+topic\s+to\s+my\s+tasks?\s*",
        "",
        title,
    )
    title = re.sub(
        r"(?is)^turn\s+(?:that|this)\s+recommendation\s+into\s+"
        r"(?:a\s+)?(?:study\s+)?task\s*",
        "",
        title,
    )
    title = re.sub(r"(?is)\s+(?:for\s+)?tomorrow\s*$", "", title)
    title = re.sub(r"(?is)\s+to\s+my\s+tasks?\s*$", "", title).strip(" .!?")
    if any(
        phrase in message.casefold()
        for phrase in (
            "biggest weakness",
            "currently weak",
            "what i am weak",
            "that recommendation",
            "this recommendation",
            "this topic",
        )
    ):
        title = ""
    if title:
        title = title[0].upper() + title[1:]
    return {
        "title": title or None,
        "description": "",
        "topic": title[:200] if title else "",
        "due_at": _tomorrow_due_at(message),
        "priority": "normal",
    }


def _completion_query(message: str) -> str:
    query = " ".join(message.split()).strip(" .!?")
    query = re.sub(r"(?is)^(?:complete|mark)\s+", "", query)
    query = re.sub(r"(?is)^(?:my|the|a)\s+", "", query)
    query = re.sub(r"(?is)^task\s+(?:about|for)\s+", "", query)
    query = re.sub(
        r"(?is)\s+(?:study\s+)?task(?:\s+as\s+completed)?$",
        "",
        query,
    )
    query = re.sub(r"(?is)\s+as\s+completed$", "", query)
    return query.strip(" .!?")


def deterministic_plan(message: str) -> ValidatedPlan:
    text = " ".join(message.casefold().split())
    calls: list[ProposedToolCall] = []
    complete_intent = bool(
        re.search(
            r"\bcomplete\b.*\btask\b|"
            r"\bmark\b.*\btask\b.*\bcomplete(?:d)?\b",
            text,
        )
    )
    create_intent = bool(
        re.search(
            r"\b(?:create|add|make)\b.*\b(?:task|tasks|to-do)\b|"
            r"\bturn\b.*\b(?:task|to-do)\b",
            text,
        )
    )
    if complete_intent:
        decision = PlannerDecision(
            mode="propose_write",
            proposed_action="complete_study_task",
            candidate_arguments={"query": _completion_query(message)},
            user_rationale="I found a request to complete one existing task.",
            reasoning_summary="Matched a bounded task-completion request.",
        )
        return validate_plan(decision, used_fallback=True)
    if create_intent:
        if any(
            phrase in text
            for phrase in (
                "weak",
                "struggling",
                "biggest weakness",
            )
        ):
            calls.append(
                ProposedToolCall(
                    tool_name="get_weak_topics",
                    arguments={"limit": 5, "recent_days": 30},
                )
            )
        elif "recommendation" in text:
            calls.append(
                ProposedToolCall(
                    tool_name="get_current_study_plan",
                    arguments={"available_minutes": 30, "max_items": 5},
                )
            )
        decision = PlannerDecision(
            mode="propose_write",
            selected_tools=calls,
            proposed_action="create_study_task",
            candidate_arguments=_create_candidate(message),
            user_rationale=(
                "I will use your learning evidence to prepare one task."
                if calls
                else "I prepared the requested task details for review."
            ),
            reasoning_summary="Matched a bounded task-creation request.",
        )
        return validate_plan(decision, used_fallback=True)
    if any(
        phrase in text
        for phrase in (
            "weak",
            "struggling",
            "struggle",
            "what should i study",
        )
    ):
        calls.append(
            ProposedToolCall(
                tool_name="get_weak_topics",
                arguments={"limit": 5, "recent_days": 30},
            )
        )
    elif any(
        phrase in text
        for phrase in ("mistake", "wrong", "incorrect", "recent quiz")
    ):
        calls.append(
            ProposedToolCall(
                tool_name="get_recent_mistakes",
                arguments={"limit": 5},
            )
        )
    elif any(
        phrase in text
        for phrase in (
            "find",
            "search",
            "material",
            "notes",
            "my document",
        )
    ):
        calls.append(
            ProposedToolCall(
                tool_name="search_study_materials",
                arguments={"query": message, "limit": 5},
            )
        )
    elif any(
        phrase in text
        for phrase in ("plan", "task", "schedule", "what is next", "minutes")
    ):
        minute_match = re.search(r"\b(\d{1,3})\s+minutes?\b", text)
        available_minutes = (
            max(10, min(int(minute_match.group(1)), 240))
            if minute_match
            else 30
        )
        calls.append(
            ProposedToolCall(
                tool_name="get_current_study_plan",
                arguments={
                    "available_minutes": available_minutes,
                    "max_items": 5,
                },
            )
        )
    decision = PlannerDecision(
        mode="read_only_tools" if calls else "answer_only",
        selected_tools=calls,
        reasoning_summary=(
            "Used a conservative intent match."
            if calls
            else "No personal workspace evidence is needed."
        ),
    )
    return validate_plan(decision, used_fallback=True)


class LearningAgentPlanner:
    def __init__(
        self,
        model_factory: Callable[..., object] = create_chat_model,
    ) -> None:
        self._model_factory = model_factory

    def plan(self, message: str) -> ValidatedPlan:
        try:
            model = self._model_factory(
                max_tokens=500,
                temperature=0,
                max_retries=1,
            )
            structured = model.with_structured_output(PlannerDecision)
        except Exception:
            return deterministic_plan(message)

        messages: list[tuple[str, str]] = [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("human", message),
        ]
        for attempt in range(2):
            try:
                raw = structured.invoke(messages)
                decision = (
                    raw
                    if isinstance(raw, PlannerDecision)
                    else PlannerDecision.model_validate(raw)
                )
                return validate_plan(decision)
            except Exception:
                if attempt == 0:
                    messages.append(
                        (
                            "human",
                            "The prior routing response was invalid. Return one "
                            "schema-valid decision using approved tools only.",
                        )
                    )
        return deterministic_plan(message)
