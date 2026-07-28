import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CalendarClock,
  Check,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  api,
  getErrorMessage,
  type LearningAgentResponse,
  type LearningAgentSuggestedAction,
} from "../api";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  Notice,
  PageHeader,
} from "../components";
import { useAsyncAction } from "../hooks";

const EXAMPLE_PROMPTS = [
  "What should I study next?",
  "What mistakes have I made recently?",
  "Find material about database joins.",
] as const;

const ACTIONS: Record<
  Exclude<LearningAgentSuggestedAction, "none">,
  { label: string; path: (response: LearningAgentResponse) => string }
> = {
  open_weak_topics: {
    label: "Start review",
    path: () => "/study-actions?view=review",
  },
  open_recent_quiz: {
    label: "Review quiz progress",
    path: () => "/progress",
  },
  open_document: {
    label: "Open related material",
    path: (response) => {
      const documentId = response.evidence.related_document_public_ids[0];
      return documentId ? `/documents/${documentId}` : "/notebooks";
    },
  },
  open_study_plan: {
    label: "Open study plan",
    path: () => "/study-actions?view=plan",
  },
  start_quiz: {
    label: "Start a focused quiz",
    path: () => "/study-actions?view=quiz",
  },
  open_study_tasks: {
    label: "Open Tasks",
    path: () => "/tasks",
  },
};

function displayDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Not set";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function LearningAgentPage() {
  const [message, setMessage] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [cancelledProposalId, setCancelledProposalId] = useState<string | null>(
    null,
  );
  const query = useAsyncAction(
    (payload: { message: string }, signal: AbortSignal) =>
      api.queryLearningAgent(payload, { signal }),
  );
  const confirmation = useAsyncAction(
    (proposalId: string, signal: AbortSignal) =>
      api.confirmLearningAgentAction(proposalId, { signal }),
  );

  async function submit(question: string) {
    const cleaned = question.trim();
    setFormError(null);
    if (!cleaned) {
      setFormError("Enter a learning question before sending.");
      return;
    }
    confirmation.reset();
    setCancelledProposalId(null);
    try {
      const response = await query.run({ message: cleaned });
      setSubmittedQuestion(cleaned);
      setMessage("");
      return response;
    } catch {
      // The hook keeps the structured error available for the safe error state.
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(message);
  }

  const response = query.data;
  const proposal = response?.proposal ?? null;
  const proposalCancelled =
    proposal !== null && cancelledProposalId === proposal.proposal_id;
  const proposalExpired =
    proposal !== null && Date.parse(proposal.expires_at) <= Date.now();
  const confirmationExpired =
    confirmation.error?.code === "AGENT_PROPOSAL_EXPIRED";
  const confirmationConsumed =
    confirmation.error?.code === "AGENT_PROPOSAL_CONSUMED";
  const action =
    response && response.suggested_ui_action !== "none"
      ? ACTIONS[response.suggested_ui_action]
      : null;

  return (
    <div className="page-stack agent-page">
      <PageHeader
        eyebrow="Personal learning guidance"
        title="Ask Agentbook"
        description={
          <p>
            Get a focused answer grounded in your study activity and saved
            material.
          </p>
        }
        actions={
          <Link className="text-link" to="/memory">
            What Agentbook remembers
          </Link>
        }
      />

      {!response && !query.isPending && !query.error ? (
        <EmptyState
          icon={<Sparkles />}
          title="What would you like help with?"
          description={
            <div className="agent-examples">
              <p>Try one of these questions:</p>
              <div className="agent-examples__buttons">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <Button
                    key={prompt}
                    variant="secondary"
                    onClick={() => {
                      setMessage(prompt);
                      void submit(prompt);
                    }}
                  >
                    {prompt}
                  </Button>
                ))}
              </div>
            </div>
          }
        />
      ) : null}

      {query.isPending ? (
        <Card tone="accent" className="agent-loading-card">
          <LoadingState message="Reviewing your learning evidence…" compact />
        </Card>
      ) : null}

      {query.error ? (
        <ErrorState
          title="Agentbook could not answer"
          message={getErrorMessage(query.error)}
          onRetry={() => void query.retry()}
        />
      ) : null}

      {response ? (
        <section className="agent-answer" aria-labelledby="agent-answer-title">
          <Card padding="large" className="agent-answer__card">
            <div className="agent-answer__heading">
              <span className="agent-answer__icon" aria-hidden="true">
                <BookOpenCheck />
              </span>
              <div>
                <p className="eyebrow">Your question</p>
                <p>{submittedQuestion}</p>
              </div>
            </div>
            <h2 id="agent-answer-title">Agentbook’s answer</h2>
            <p className="answer-copy">{response.answer}</p>

            {response.evidence.summary.length > 0 ||
            response.evidence.weak_topics_used.length > 0 ? (
              <div className="agent-evidence">
                <h3>Based on</h3>
                <ul>
                  {response.evidence.summary.map((summary) => (
                    <li key={summary}>{summary}</li>
                  ))}
                  {response.evidence.weak_topics_used.length > 0 ? (
                    <li>
                      Focus areas:{" "}
                      {response.evidence.weak_topics_used.join(", ")}
                    </li>
                  ) : null}
                </ul>
              </div>
            ) : (
              <p className="supporting-text">
                This answer uses general guidance rather than personal learning
                evidence.
              </p>
            )}

            {action ? (
              <Link
                className="button button--secondary agent-answer__action"
                to={action.path(response)}
              >
                <span>{action.label}</span>
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            ) : null}

            {proposal ? (
              <div
                className="agent-confirmation"
                aria-labelledby="agent-confirmation-title"
              >
                <div className="agent-confirmation__heading">
                  <div>
                    <p className="eyebrow">Confirmation required</p>
                    <h3 id="agent-confirmation-title">
                      {proposal.display_title}
                    </h3>
                  </div>
                  <span className="agent-confirmation__risk">Low risk</span>
                </div>
                <p>{proposal.display_summary}</p>

                <dl className="agent-confirmation__details">
                  <div>
                    <dt>Title</dt>
                    <dd>{proposal.task_preview.title}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{proposal.task_preview.status}</dd>
                  </div>
                  {proposal.task_preview.topic ? (
                    <div>
                      <dt>Topic</dt>
                      <dd>{proposal.task_preview.topic}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Due</dt>
                    <dd>
                      {proposal.task_preview.due_at
                        ? displayDate(proposal.task_preview.due_at)
                        : "No due date"}
                    </dd>
                  </div>
                  <div>
                    <dt>Priority</dt>
                    <dd>{proposal.task_preview.priority}</dd>
                  </div>
                  {proposal.task_preview.description ? (
                    <div className="agent-confirmation__description">
                      <dt>Description</dt>
                      <dd>{proposal.task_preview.description}</dd>
                    </div>
                  ) : null}
                </dl>

                {proposal.evidence_summary ? (
                  <p className="supporting-text">
                    Why this was prepared: {proposal.evidence_summary}
                  </p>
                ) : null}
                <p className="supporting-text agent-confirmation__expiry">
                  <CalendarClock size={16} aria-hidden="true" />
                  Confirmation expires {displayDate(proposal.expires_at)}
                </p>

                {confirmation.data ? (
                  <Notice tone="success" title="Action confirmed">
                    {confirmation.data.message}
                  </Notice>
                ) : proposalCancelled ? (
                  <Notice tone="info" title="Proposal cancelled">
                    Nothing was changed.
                  </Notice>
                ) : proposalExpired || confirmationExpired ? (
                  <Notice tone="warning" title="Confirmation expired">
                    Ask Agentbook to prepare a fresh action. Nothing was changed.
                  </Notice>
                ) : confirmationConsumed ? (
                  <Notice tone="info" title="Already executed">
                    This confirmation was already executed. Open Tasks to
                    review the result.
                  </Notice>
                ) : confirmation.error ? (
                  <Notice tone="error" title="Action was not confirmed">
                    {getErrorMessage(confirmation.error)}
                  </Notice>
                ) : (
                  <Notice tone="info" title="Nothing has been changed yet">
                    Review the exact task action, then confirm or cancel it.
                  </Notice>
                )}

                <div className="agent-confirmation__actions">
                  {confirmation.data || confirmationConsumed ? (
                    <Link
                      className="button button--secondary"
                      to="/tasks"
                    >
                      <span>Open Tasks</span>
                      <ArrowRight size={18} aria-hidden="true" />
                    </Link>
                  ) : null}
                  {!confirmation.data &&
                  !proposalCancelled &&
                  !proposalExpired &&
                  !confirmationExpired &&
                  !confirmationConsumed ? (
                    <>
                      <Button
                        loading={confirmation.isPending}
                        loadingText="Confirming..."
                        disabled={confirmation.isPending}
                        icon={<Check size={18} aria-hidden="true" />}
                        onClick={() =>
                          void confirmation.run(proposal.proposal_id).catch(
                            () => undefined,
                          )
                        }
                      >
                        Confirm
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={confirmation.isPending}
                        icon={<X size={18} aria-hidden="true" />}
                        onClick={() => {
                          setCancelledProposalId(proposal.proposal_id);
                          confirmation.reset();
                        }}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            ) : null}
          </Card>
        </section>
      ) : null}

      <form className="chat-composer agent-composer" onSubmit={handleSubmit}>
        <label htmlFor="agent-message">Ask a learning question</label>
        <textarea
          id="agent-message"
          rows={4}
          maxLength={2000}
          value={message}
          onChange={(event) => {
            setMessage(event.target.value);
            setFormError(null);
            if (query.error) query.reset({ preserveData: true });
          }}
          placeholder="What should I focus on today?"
          disabled={query.isPending}
          aria-invalid={Boolean(formError)}
          aria-describedby="agent-message-help agent-message-error"
        />
        <div className="chat-composer__footer">
          <p id="agent-message-help" className="field-help">
            {message.length}/2000 characters
          </p>
          <Button
            type="submit"
            loading={query.isPending}
            loadingText="Thinking…"
            icon={<Send size={18} aria-hidden="true" />}
          >
            Ask Agentbook
          </Button>
        </div>
        {formError ? (
          <p id="agent-message-error" className="field-error" role="alert">
            {formError}
          </p>
        ) : null}
      </form>
    </div>
  );
}
