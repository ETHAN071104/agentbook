from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from backend.api.agent_schemas import (
    AgentActionConfirmationRequest,
    AgentActionConfirmationResponse,
    AgentEvidenceResponse,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentTaskPreviewResponse,
    AgentWriteProposalResponse,
)
from backend.api.errors import ApiError, map_exception
from backend.api.routes.study_tasks import study_task_response
from backend.application.learning_agent import query_learning_agent
from backend.application.learning_agent.write_actions import (
    AgentWriteProposalConflict,
    AgentWriteProposalConsumed,
    AgentWriteProposalExpired,
    AgentWriteProposalInvalid,
    AgentWriteProposalNotFound,
    AgentWriteProposalService,
)


router = APIRouter(prefix="/api/agent", tags=["learning-agent"])


def _proposal_response(result: object) -> AgentWriteProposalResponse:
    proposal = result
    return AgentWriteProposalResponse(
        proposal_id=proposal.proposal_id,
        action=proposal.action,
        display_title=proposal.display_title,
        display_summary=proposal.display_summary,
        task_preview=AgentTaskPreviewResponse(
            title=proposal.task_preview.title,
            description=proposal.task_preview.description,
            topic=proposal.task_preview.topic,
            status=proposal.task_preview.status,
            priority=proposal.task_preview.priority,
            due_at=proposal.task_preview.due_at,
        ),
        evidence_summary=proposal.evidence_summary,
        expires_at=proposal.expires_at,
        confirmation_required=True,
        risk_level="low",
    )


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(payload: AgentQueryRequest) -> AgentQueryResponse:
    try:
        result = query_learning_agent(payload.message)
    except Exception as error:
        raise map_exception(
            error,
            fallback_code="INTERNAL_ERROR",
            context="learning_agent_query",
        ) from error
    return AgentQueryResponse(
        answer=result.answer,
        tools_used=list(result.tools_used),
        evidence=AgentEvidenceResponse(
            summary=list(result.evidence.summary),
            related_document_public_ids=list(
                result.evidence.related_document_public_ids
            ),
            related_quiz_attempt_public_ids=list(
                result.evidence.related_quiz_attempt_public_ids
            ),
            weak_topics_used=list(result.evidence.weak_topics_used),
        ),
        suggested_ui_action=result.suggested_ui_action,
        confirmation_required=result.confirmation_required,
        proposal=(
            _proposal_response(result.proposal)
            if result.proposal is not None
            else None
        ),
    )


def _raise_confirmation_error(error: Exception) -> None:
    if isinstance(error, AgentWriteProposalNotFound):
        raise ApiError(
            status_code=404,
            code="AGENT_PROPOSAL_NOT_FOUND",
            reason="This confirmation is not available.",
            next_action="Ask Agentbook to prepare the action again.",
            retryable=False,
        ) from error
    if isinstance(error, AgentWriteProposalExpired):
        raise ApiError(
            status_code=409,
            code="AGENT_PROPOSAL_EXPIRED",
            reason="This confirmation has expired.",
            next_action="Ask Agentbook to prepare a fresh action.",
            retryable=False,
        ) from error
    if isinstance(error, AgentWriteProposalConsumed):
        raise ApiError(
            status_code=409,
            code="AGENT_PROPOSAL_CONSUMED",
            reason="This confirmation was already executed.",
            next_action="Open Study Tasks to review the persisted result.",
            retryable=False,
        ) from error
    if isinstance(error, AgentWriteProposalConflict):
        raise ApiError(
            status_code=409,
            code="AGENT_PROPOSAL_CONFLICT",
            reason=str(error),
            next_action="Refresh Study Tasks and ask Agentbook again.",
            retryable=False,
        ) from error
    if isinstance(error, AgentWriteProposalInvalid):
        raise ApiError(
            status_code=409,
            code="AGENT_PROPOSAL_INVALID",
            reason="This confirmation could not be safely validated.",
            next_action="Ask Agentbook to prepare the action again.",
            retryable=False,
        ) from error
    raise map_exception(
        error,
        fallback_code="INTERNAL_ERROR",
        context="learning_agent_confirmation",
    ) from error


@router.post(
    "/actions/{proposal_id}/confirm",
    response_model=AgentActionConfirmationResponse,
)
def confirm_agent_action(
    proposal_id: Annotated[
        str,
        Path(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$"),
    ],
    payload: AgentActionConfirmationRequest,
) -> AgentActionConfirmationResponse:
    if payload.confirm is not True:
        raise AssertionError("unreachable")
    try:
        result = AgentWriteProposalService().confirm(proposal_id)
        return AgentActionConfirmationResponse(
            executed=True,
            action=result.action,
            task=study_task_response(result.task),
            message=result.message,
            suggested_ui_action=result.suggested_ui_action,
        )
    except Exception as error:
        _raise_confirmation_error(error)
        raise AssertionError("unreachable")
