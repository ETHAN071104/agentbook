import {
  BrainCircuit,
  BookOpenCheck,
  CalendarDays,
  Check,
  ClipboardList,
  FileText,
  Lightbulb,
  ListChecks,
  MessageCircleMore,
  RefreshCw,
  SkipForward,
  Sparkles,
  X,
} from 'lucide-react';
import {
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { apiClient } from '../api/client';
import type {
  CoachingPlan,
  NotebookList,
  PublicId,
  PresentedQuiz,
  QuizAnswer,
  QuizScopeInfo,
  QuizSubmission,
  RetrievalScope,
  ReviewAction,
  ReviewQueue,
  StudyPlan,
  StudyPlanRequest,
} from '../api/types';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  ErrorState,
  LoadingState,
  Notice,
  OutcomeBadge,
  PageHeader,
  ProgressBar,
  SectionHeader,
  SourceCard,
} from '../components';
import { useApiQuery, useAsyncAction } from '../hooks';
import { errorMessage, formatPercent } from '../utils/format';

type ActionView = 'review' | 'quiz' | 'plan' | 'coaching';

const ACTION_VIEWS: ActionView[] = ['quiz', 'review', 'plan', 'coaching'];

interface QuizScopeSelection {
  scope?: RetrievalScope;
  label: string;
  preview: QuizScopePreview;
  issue?: string;
}

type QuizScopePreview = Omit<
  QuizScopeInfo,
  'document_count' | 'resolved_document_ids'
> & {
  document_count?: number;
  resolved_document_ids?: PublicId[];
};

function parseQuizScope(searchParams: URLSearchParams): QuizScopeSelection {
  const topicValues = searchParams.getAll('topic_id');
  const notebookValues = searchParams.getAll('notebook_id');
  const documentValues = searchParams.getAll('document_ids');
  const selectedKinds = [topicValues, notebookValues, documentValues].filter(
    (values) => values.length > 0,
  ).length;
  const requestedLabel =
    searchParams.get('scope_name')?.trim() || searchParams.get('topic')?.trim() || '';

  if (selectedKinds > 1) {
    return invalidQuizScope(
      'This link contains more than one quiz scope. Choose one document, notebook, topic, or global scope.',
    );
  }

  if (topicValues.length) {
    const topicId = topicValues[0]?.trim() ?? '';
    if (topicValues.length !== 1 || !topicId) {
      return invalidQuizScope('The selected topic scope is invalid. Choose the topic again.');
    }
    const label = requestedLabel || 'Selected topic';
    return {
      scope: { topic_id: topicId },
      label,
      preview: {
        type: 'topic',
        label,
        personalized: false,
        description: `Questions will use only material connected to "${label}".`,
      },
    };
  }

  if (notebookValues.length) {
    const rawNotebookId = notebookValues[0] ?? '';
    if (notebookValues.length !== 1 || !/^[1-9]\d*$/.test(rawNotebookId)) {
      return invalidQuizScope('The selected notebook scope is invalid. Choose the notebook again.');
    }
    const label = requestedLabel || 'Selected notebook';
    return {
      scope: { notebook_id: rawNotebookId },
      label,
      preview: {
        type: 'notebook',
        label,
        personalized: false,
        notebook_name: requestedLabel || null,
        description: `Questions will use material in the "${label}" notebook.`,
      },
    };
  }

  if (documentValues.length) {
    const validValues = documentValues.every((value) => /^[1-9]\d*$/.test(value));
    const documentIds = documentValues;
    if (!validValues || new Set(documentIds).size !== documentIds.length) {
      return invalidQuizScope('The selected document scope is invalid. Choose the document again.');
    }
    const singleDocument = documentIds.length === 1;
    const label = requestedLabel || (singleDocument ? 'Selected document' : 'Selected documents');
    return {
      scope: { document_ids: documentIds },
      label,
      preview: {
        type: singleDocument ? 'document' : 'documents',
        label,
        document_count: documentIds.length,
        personalized: false,
        document_name: singleDocument && requestedLabel ? requestedLabel : null,
        description: singleDocument
          ? `Questions will use only "${label}".`
          : `Questions will use only the ${documentIds.length} selected documents.`,
      },
    };
  }

  return {
    label: '',
    preview: {
      type: 'global',
      label: 'All study material',
      personalized: false,
      description: 'Questions may use any material in your Library.',
    },
  };
}

function invalidQuizScope(issue: string): QuizScopeSelection {
  return {
    label: '',
    issue,
    preview: {
      type: 'global',
      label: 'Quiz scope unavailable',
      personalized: false,
      description: issue,
    },
  };
}

export function StudyActionsPage() {
  const [searchParams] = useSearchParams();
  const scopeSelection = useMemo(() => parseQuizScope(searchParams), [searchParams]);
  const { scope, label: scopeLabel, issue: scopeIssue, preview: scopePreview } =
    scopeSelection;
  const requestedView = searchParams.get('view');
  const carriedPrompt = (searchParams.get('prompt') ?? '').trim().slice(0, 4000);
  const initialView = ACTION_VIEWS.includes(requestedView as ActionView)
    ? requestedView as ActionView
    : 'quiz';
  const [view, setView] = useState<ActionView>(initialView);

  return (
    <div className="page-stack practice-page">
      <PageHeader
        eyebrow="Check your understanding"
        title="Practice"
        description={
          scopeIssue
            ? scopeIssue
            : scope
            ? `Work only from ${scopeLabel || 'the selected material'}.`
            : 'Use a quiz for recall or review an area that needs another look.'
        }
        actions={scope ? <Badge tone="primary">Scoped study</Badge> : null}
      />

      <div className="practice-page__content">
        {scopeIssue ? (
          <EmptyState
            title="Selected material needs attention"
            description={scopeIssue}
            action={<a className="text-link" href="/notebooks">Choose a study source</a>}
          />
        ) : (
          <>
            {view === 'review' ? <ReviewWorkspace scope={scope} /> : null}
            {view === 'quiz' ? (
              <QuizWorkspace
                scope={scope}
                initialTopic={scopeLabel}
                scopePreview={scopePreview}
              />
            ) : null}
            {view === 'plan' ? (
              <PlanWorkspace scope={scope} carriedPrompt={carriedPrompt} />
            ) : null}
            {view === 'coaching' ? (
              <CoachingWorkspace scope={scope} carriedPrompt={carriedPrompt} />
            ) : null}
            <PracticeOptions activeView={view} onSelect={setView} />
          </>
        )}
      </div>
    </div>
  );
}

function ReviewWorkspace({ scope }: { scope?: RetrievalScope }) {
  const reviewQueuePath = scope?.topic_id
    ? `/api/study/actions/review-queue?topic_id=${encodeURIComponent(scope.topic_id)}`
    : scope?.notebook_id
      ? `/api/study/actions/review-queue?notebook_id=${scope.notebook_id}`
      : scope?.document_ids
        ? `/api/study/actions/review-queue?${scope.document_ids
            .map((documentId) => `document_ids=${documentId}`)
            .join('&')}`
        : '/api/study/actions/review-queue';
  const queue = useApiQuery<ReviewQueue>(
    ['review-queue', reviewQueuePath],
    (signal) => apiClient.get(reviewQueuePath, { signal }),
  );
  const [result, setResult] = useState<ReviewAction | null>(null);
  const generate = useAsyncAction((interactionId: PublicId, signal: AbortSignal) =>
    apiClient.post<ReviewAction, { interaction_id: PublicId; scope: RetrievalScope | null }>(
      '/api/study/actions/review',
      { interaction_id: interactionId, scope: scope ?? null },
      { signal },
    ),
  );

  async function handleGenerate(interactionId: PublicId) {
    try {
      setResult(await generate.run(interactionId));
    } catch {
      // Queue stays visible for retry.
    }
  }

  return (
    <div className="page-stack">
      <SectionHeader
        title="Review queue"
        description="Partial and confused outcomes rise to the top using deterministic priority."
      />
      {queue.isLoading ? <LoadingState message="Reading unresolved outcomes…" /> : null}
      {queue.error ? (
        <ErrorState message={errorMessage(queue.error)} onRetry={() => void queue.reload()} />
      ) : null}
      {queue.data?.adaptation?.adapted_using_learner_memory ? (
        <Notice tone="info">
          <strong>Why this was recommended:</strong>{" "}
          {queue.data.adaptation.reason}
        </Notice>
      ) : null}
      {queue.data?.items.length ? (
        <div className="review-grid">
          {queue.data.items.map((item) => (
            <Card key={item.interaction_id} className="review-card">
              <div className="review-card__header">
                <OutcomeBadge outcome={item.outcome} />
                <Badge tone="neutral">Priority {item.priority_score}</Badge>
              </div>
              <h3>{item.question}</h3>
              <p>{item.reason}</p>
              <small>{item.source_filenames.join(', ') || 'No source lineage recorded'}</small>
              <Button
                icon={<Sparkles size={18} aria-hidden="true" />}
                onClick={() => void handleGenerate(item.interaction_id)}
                loading={generate.isPending && generate.status === 'pending'}
                loadingText="Generating…"
              >
                Generate review activity
              </Button>
            </Card>
          ))}
        </div>
      ) : !queue.isLoading && !queue.error ? (
        <EmptyState
          title="Review queue is clear"
          description="Mark a chat answer partial or confused when it needs another pass."
        />
      ) : null}
      {generate.error ? (
        <ErrorNotice
          error={generate.error}
          onRetry={() => generate.retry()}
        />
      ) : null}
      {result ? (
        <Card tone="accent" className="reading-card">
          <Badge tone={result.should_generate ? 'success' : 'warning'}>
            {result.should_generate ? result.review_mode : 'Not generated'}
          </Badge>
          <h2>{result.topic || 'Review activity'}</h2>
          {result.adaptation?.adapted_using_learner_memory ? (
            <Notice tone="info">
              <strong>Why this was recommended:</strong>{" "}
              {result.adaptation.reason}
            </Notice>
          ) : null}
          {result.should_generate ? (
            <>
              <h3>Explanation</h3>
              <p>{result.explanation}</p>
              <h3>Worked example</h3>
              <p>{result.worked_example}</p>
              <h3>Check your understanding</h3>
              <p>{result.check_question}</p>
              <details>
                <summary>Show expected answer</summary>
                <p>{result.expected_answer}</p>
              </details>
              <div className="source-grid">
                {result.sources.map((source) => (
                  <SourceCard key={`${source.index}-${source.document_id}`} source={source} />
                ))}
              </div>
            </>
          ) : (
            <p>{result.reason}</p>
          )}
        </Card>
      ) : null}
    </div>
  );
}

function QuizWorkspace({
  scope,
  initialTopic,
  scopePreview,
}: {
  scope?: RetrievalScope;
  initialTopic: string;
  scopePreview: QuizScopePreview;
}) {
  const [topic, setTopic] = useState(initialTopic);
  const [questionCount, setQuestionCount] = useState(3);
  const [sourceMode, setSourceMode] = useState<'all' | 'specific'>(scope ? 'specific' : 'all');
  const [selectedNotebookId, setSelectedNotebookId] = useState(
    scope?.notebook_id ? String(scope.notebook_id) : '',
  );
  const [quiz, setQuiz] = useState<PresentedQuiz | null>(null);
  const [answers, setAnswers] = useState<QuizAnswer[]>([]);
  const [submission, setSubmission] = useState<QuizSubmission | null>(null);
  const [proposalDrafts, setProposalDrafts] = useState<Record<string, string>>({});
  const [decidedProposals, setDecidedProposals] = useState<Record<string, string>>({});
  const notebooks = useAsyncAction((signal: AbortSignal) =>
    apiClient.get<NotebookList>('/api/notebooks', { signal }),
  );
  const selectedScope: RetrievalScope | undefined = selectedNotebookId
    ? { notebook_id: selectedNotebookId }
    : scope;
  const generate = useAsyncAction((
    requestedTopic: string,
    count: number,
    signal: AbortSignal,
  ) =>
    apiClient.post<PresentedQuiz>(
      '/api/study/actions/quizzes/generate',
      {
        topic: requestedTopic,
        question_count: count,
        ...(sourceMode === 'specific' ? selectedScope ?? {} : {}),
      },
      { signal },
    ),
  );
  const submit = useAsyncAction((
    quizId: string,
    responses: QuizAnswer[],
    signal: AbortSignal,
  ) =>
    apiClient.post<QuizSubmission, { responses: QuizAnswer[] }>(
      `/api/study/actions/quizzes/${encodeURIComponent(quizId)}/submit`,
      { responses },
      { signal },
    ),
  );
  const decideProposal = useAsyncAction((
    proposalId: string,
    decision: 'accept' | 'reject',
    editedContent: string | null,
    signal: AbortSignal,
  ) =>
    apiClient.post<{ consumed: boolean }>(
      `/api/memories/proposals/${encodeURIComponent(proposalId)}/decision`,
      {
        decision,
        edited_content: decision === 'accept' ? editedContent : null,
      },
      { signal },
    ),
  );

  const currentQuestion = quiz?.questions[answers.length];
  const availableNotebooks = (notebooks.data?.items ?? []).filter(
    (notebook) => notebook.id !== null && !notebook.is_virtual,
  );

  function chooseSourceMode(mode: 'all' | 'specific') {
    setSourceMode(mode);
    if (mode === 'specific' && !notebooks.data && !notebooks.isPending) {
      void notebooks.run().catch(() => undefined);
    }
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestedTopic = topic.trim();
    if (!requestedTopic) return;
    try {
      setQuiz(await generate.run(requestedTopic, questionCount));
      setAnswers([]);
      setSubmission(null);
    } catch {
      // Preserve quiz setup input.
    }
  }

  function recordAnswer(selectedOption: number | null) {
    if (!currentQuestion || submit.isPending) return;
    setAnswers((current) => [
      ...current,
      {
        question_number: currentQuestion.question_number,
        selected_option: selectedOption,
      },
    ]);
  }

  async function handleSubmit() {
    if (!quiz) return;
    try {
      setSubmission(await submit.run(quiz.quiz_id, answers));
      apiClient.invalidate({ prefix: '/api/reports/quizzes' });
      apiClient.invalidate('/api/dashboard');
    } catch {
      // Pending server quiz is retained after a validation failure.
    }
  }

  async function handleProposalDecision(
    proposalId: string,
    decision: 'accept' | 'reject',
    originalContent: string,
  ) {
    try {
      const draft = proposalDrafts[proposalId] ?? originalContent;
      await decideProposal.run(
        proposalId,
        decision,
        draft === originalContent ? null : draft,
      );
      setDecidedProposals((current) => ({ ...current, [proposalId]: decision }));
      apiClient.invalidate({ prefix: '/api/memories' });
    } catch {
      // The durable proposal remains available for retry.
    }
  }

  function resetQuiz() {
    setQuiz(null);
    setAnswers([]);
    setSubmission(null);
    generate.reset();
    submit.reset();
    decideProposal.reset();
    setProposalDrafts({});
    setDecidedProposals({});
  }

  if (submission) {
    const insight =
      submission.detected_weaknesses?.[0] ??
      (submission.score_percentage >= 80
        ? "You showed strong recall across this quiz."
        : submission.score_percentage >= 60
          ? "You have a useful foundation, with a few areas to strengthen."
          : "A focused review will help before you try this material again.");
    const shouldReview =
      Boolean(submission.detected_weaknesses?.length) ||
      submission.score_percentage < 70;
    return (
      <div className="page-stack">
        <SectionHeader
          title="Quiz result"
          actions={<Button variant="secondary" onClick={resetQuiz}>Start another quiz</Button>}
        />
        <QuizScopeSummary scope={quiz?.scope ?? scopePreview} confirmed={Boolean(quiz?.scope)} />
        <Card tone="accent" className="quiz-result-summary">
          <div>
            <p className="metric-label">Score</p>
            <p className="quiz-result-summary__score">
              {formatPercent(submission.score_percentage)}
            </p>
          </div>
          <div className="quiz-result-summary__insight">
            <h2>Learning insight</h2>
            <p>{insight}</p>
          </div>
          {shouldReview ? (
            <Link className="button button--primary" to="/study-actions?view=review">
              Review next
            </Link>
          ) : (
            <Button onClick={resetQuiz}>Try another quiz</Button>
          )}
        </Card>
        {submission.learning_signals?.length ? (
          <div className="page-stack">
            <SectionHeader
              title="Areas to review"
              description="Patterns from this quiz that can guide your next practice."
            />
            {submission.learning_signals.map((signal) => (
              <Card key={signal.id}>
                <h3>{signal.topic}</h3>
                <p>{signal.statement}</p>
                {signal.occurrence_count > 1 ? (
                  <p className="supporting-text">Recent mistake pattern</p>
                ) : null}
              </Card>
            ))}
          </div>
        ) : null}
        {submission.memory_proposals?.length ? (
          <div className="page-stack">
            <SectionHeader
              title="Suggested study notes"
              description="Choose whether Agentbook should remember these notes for future guidance."
            />
            {submission.memory_proposals.map((proposal) => {
              const decision = decidedProposals[proposal.proposal_id];
              return (
                <Card key={proposal.proposal_id} tone="accent">
                  <Badge tone={decision ? 'success' : 'info'}>
                    {decision ? `${decision}ed` : 'Approval required'}
                  </Badge>
                  <p>{proposal.reason}</p>
                  <label>
                    Suggested note
                    <textarea
                      value={proposalDrafts[proposal.proposal_id] ?? proposal.content}
                      onChange={(event) => setProposalDrafts((current) => ({
                        ...current,
                        [proposal.proposal_id]: event.target.value,
                      }))}
                      disabled={Boolean(decision)}
                      rows={3}
                    />
                  </label>
                  {!decision ? (
                    <div className="card-actions">
                      <Button
                        onClick={() => void handleProposalDecision(proposal.proposal_id, 'accept', proposal.content)}
                        loading={decideProposal.isPending}
                      >
                        Remember note
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => void handleProposalDecision(proposal.proposal_id, 'reject', proposal.content)}
                        disabled={decideProposal.isPending}
                      >
                        Reject
                      </Button>
                    </div>
                  ) : null}
                </Card>
              );
            })}
            {decideProposal.error ? <Notice tone="error">{errorMessage(decideProposal.error)} The proposal remains available.</Notice> : null}
          </div>
        ) : null}
        <details className="quiz-result-details">
          <summary>View detailed results</summary>
          <dl className="stat-list">
            <div>
              <dt>Answered accuracy</dt>
              <dd>{formatPercent(submission.accuracy_percentage)}</dd>
            </div>
            <div>
              <dt>Correct answers</dt>
              <dd>
                {submission.correct_answers}/{submission.total_questions}
              </dd>
            </div>
          </dl>
          <div className="page-stack">
            {submission.feedback.map((feedback) => (
              <Card key={feedback.question_number} className="quiz-feedback">
              <div className="quiz-feedback__header">
                {feedback.is_correct ? (
                  <Badge tone="success" icon={<Check size={16} aria-hidden="true" />}>Correct</Badge>
                ) : feedback.skipped ? (
                  <Badge tone="warning" icon={<SkipForward size={16} aria-hidden="true" />}>Skipped</Badge>
                ) : (
                  <Badge tone="danger" icon={<X size={16} aria-hidden="true" />}>Incorrect</Badge>
                )}
                <span>Question {feedback.question_number}</span>
              </div>
              <h3>{feedback.question}</h3>
              <p>
                Correct option: <strong>{feedback.correct_option}</strong>
              </p>
              <p>{feedback.explanation}</p>
              <div className="source-grid">
                {feedback.sources.map((source) => (
                  <SourceCard key={`${feedback.question_number}-${source.index}`} source={source} />
                ))}
              </div>
              </Card>
            ))}
          </div>
        </details>
      </div>
    );
  }

  if (quiz) {
    const complete = answers.length === quiz.questions.length;
    return (
      <div className="page-stack quiz-workspace">
        <SectionHeader
          title={quiz.topic}
          description={`${answers.length} of ${quiz.questions.length} questions presented.`}
          actions={<Button variant="ghost" onClick={resetQuiz}>Cancel quiz</Button>}
        />
        <QuizScopeSummary scope={quiz.scope ?? scopePreview} confirmed={Boolean(quiz.scope)} />
        {quiz.adaptation?.adapted_using_learner_memory ? (
          <Notice tone="info">
            <strong>Why this quiz was personalized:</strong>{" "}
            {quiz.adaptation.reason}
          </Notice>
        ) : null}
        <ProgressBar value={answers.length} max={quiz.questions.length} label="Quiz progress" />
        {currentQuestion ? (
          <Card className="quiz-question">
            <p className="eyebrow">Question {currentQuestion.question_number}</p>
            <h2>{currentQuestion.question}</h2>
            <div className="quiz-options" role="group" aria-label="Answer options">
              {currentQuestion.options.map((option, index) => (
                <button
                  type="button"
                  key={`${currentQuestion.question_number}-${option}`}
                  onClick={() => recordAnswer(index + 1)}
                >
                  <span>{String.fromCharCode(65 + index)}</span>
                  <span>{option}</span>
                </button>
              ))}
            </div>
            <div className="card-actions">
              <Button
                variant="secondary"
                icon={<SkipForward size={18} aria-hidden="true" />}
                onClick={() => recordAnswer(null)}
              >
                Skip question
              </Button>
              <Button variant="ghost" onClick={() => void handleSubmit()} disabled={!answers.length}>
                Finish now
              </Button>
            </div>
          </Card>
        ) : complete ? (
          <Card tone="accent" className="quiz-ready">
            <ListChecks size={32} aria-hidden="true" />
            <h2>Ready to submit</h2>
            <p>
              The server will derive correctness from its trusted quiz registry. Answers and
              explanations have not been exposed yet.
            </p>
            <Button onClick={() => void handleSubmit()} loading={submit.isPending} loadingText="Scoring…">
              Submit answers
            </Button>
          </Card>
        ) : null}
        {submit.error ? (
          <ErrorNotice
            error={submit.error}
            onRetry={() => submit.retry()}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className="page-stack quiz-builder">
      <Card className="quiz-builder__card" padding="large">
        <div className="quiz-builder__title">
          <span className="quiz-builder__title-icon">
            <BrainCircuit size={28} aria-hidden="true" />
          </span>
          <div>
            <p className="eyebrow">Grounded in your library</p>
            <h2>Generate your quiz</h2>
          </div>
        </div>
        <form className="quiz-builder__form" onSubmit={handleGenerate}>
          <section className="quiz-builder__step" aria-labelledby="quiz-source-heading">
            <div className="quiz-builder__step-heading">
              <span>Step 1</span>
              <h3 id="quiz-source-heading">Select material source</h3>
            </div>
            <div className="quiz-source-options" role="radiogroup" aria-label="Quiz material source">
              <button
                type="button"
                role="radio"
                aria-checked={sourceMode === 'all'}
                className={sourceMode === 'all' ? 'quiz-source-option is-selected' : 'quiz-source-option'}
                onClick={() => chooseSourceMode('all')}
              >
                <span className="quiz-source-option__check"><Check size={18} aria-hidden="true" /></span>
                <BookOpenCheck size={25} aria-hidden="true" />
                <span>
                  <strong>All materials</strong>
                  <small>Questions may use any material in your Library.</small>
                </span>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={sourceMode === 'specific'}
                className={sourceMode === 'specific' ? 'quiz-source-option is-selected' : 'quiz-source-option'}
                onClick={() => chooseSourceMode('specific')}
              >
                <span className="quiz-source-option__check"><Check size={18} aria-hidden="true" /></span>
                <FileText size={25} aria-hidden="true" />
                <span>
                  <strong>Specific topic</strong>
                  <small>Choose a notebook, then focus the quiz with a topic.</small>
                </span>
              </button>
            </div>
            {sourceMode === 'specific' ? (
              <div className="quiz-notebook-picker">
                <label htmlFor="quiz-notebook">
                  Notebook
                  <select
                    id="quiz-notebook"
                    value={selectedNotebookId}
                    onChange={(event) => setSelectedNotebookId(event.target.value)}
                    onFocus={() => {
                      if (!notebooks.data && !notebooks.isPending) {
                        void notebooks.run().catch(() => undefined);
                      }
                    }}
                    required={!scope}
                    disabled={notebooks.isPending && !notebooks.data}
                  >
                    <option value="">
                      {scope ? `Current selection — ${scopePreview.label}` : notebooks.isPending ? 'Loading notebooks…' : 'Choose a notebook'}
                    </option>
                    {scope?.notebook_id && !availableNotebooks.some((notebook) => String(notebook.id) === String(scope.notebook_id)) ? (
                      <option value={String(scope.notebook_id)}>{scopePreview.label}</option>
                    ) : null}
                    {availableNotebooks.map((notebook) => (
                      <option key={String(notebook.id)} value={String(notebook.id)}>
                        {notebook.name} ({notebook.document_count} source{notebook.document_count === 1 ? '' : 's'})
                      </option>
                    ))}
                  </select>
                </label>
                {notebooks.error ? (
                  <div className="quiz-notebook-picker__error">
                    <span>Could not load notebooks.</span>
                    <Button variant="ghost" onClick={() => void notebooks.retry()}>
                      Try again
                    </Button>
                  </div>
                ) : null}
                {notebooks.data && availableNotebooks.length === 0 && !scope ? (
                  <p>
                    No notebooks yet. <Link className="text-link" to="/notebooks">Create one in Library</Link>.
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>
          <section className="quiz-builder__step quiz-builder__step--details" aria-labelledby="quiz-details-heading">
            <div className="quiz-builder__step-heading">
              <span>Step 2</span>
              <h3 id="quiz-details-heading">Refine quiz details</h3>
            </div>
            <div className="quiz-builder__fields">
          <label>
            Quiz topic
            <input
              required
              maxLength={300}
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="For example: cellular respiration"
            />
          </label>
          <label>
            Number of questions
            <select
              value={questionCount}
              onChange={(event) => setQuestionCount(Number(event.target.value))}
            >
              {[1, 2, 3, 4, 5, 6].map((count) => (
                <option value={count} key={count}>
                  {count} {count === 1 ? 'question' : 'questions'}
                </option>
              ))}
            </select>
          </label>
              <p className="quiz-builder__privacy">
                Correct options and explanations stay on the server until you submit.
              </p>
            </div>
          </section>
          {generate.error ? (
            <div className="quiz-builder__error">
            <ErrorNotice
              error={generate.error}
              onRetry={() => generate.retry()}
              alternateAction={
                <a className="text-link" href="/notebooks">
                  Choose or upload study material
                </a>
              }
            />
            </div>
          ) : null}
          <Button
            type="submit"
            className="quiz-builder__submit"
            icon={<BrainCircuit size={21} aria-hidden="true" />}
            loading={generate.isPending}
            disabled={sourceMode === 'specific' && !selectedScope}
            loadingText="Generating grounded quiz…"
          >
            Generate quiz
          </Button>
        </form>
      </Card>
    </div>
  );
}

function PracticeOptions({
  activeView,
  onSelect,
}: {
  activeView: ActionView;
  onSelect: (view: ActionView) => void;
}) {
  const options: Array<{
    id: Exclude<ActionView, 'quiz'>;
    title: string;
    description: string;
    action: string;
    icon: ReactNode;
  }> = [
    {
      id: 'review',
      title: 'Review queue',
      description: 'Revisit weak areas and turn recent learning signals into focused recall.',
      action: 'Open review',
      icon: <RefreshCw size={24} aria-hidden="true" />,
    },
    {
      id: 'plan',
      title: 'Study plan',
      description: 'Create a time-boxed plan ordered around what matters most next.',
      action: 'Build a plan',
      icon: <CalendarDays size={24} aria-hidden="true" />,
    },
    {
      id: 'coaching',
      title: 'AI coaching',
      description: 'Use performance history for a personalized next-step recommendation.',
      action: 'Start coaching',
      icon: <MessageCircleMore size={24} aria-hidden="true" />,
    },
  ];

  return (
    <section className="practice-options" aria-labelledby="practice-options-title">
      <SectionHeader
        title="More practice options"
        headingId="practice-options-title"
        description="Choose another way to reinforce what you are learning."
      />
      <div className="practice-options__grid">
        {options.map((option) => (
          <Card
            key={option.id}
            className={activeView === option.id ? 'practice-option is-active' : 'practice-option'}
          >
            <div className="practice-option__heading">
              <span className="practice-option__icon">{option.icon}</span>
              <h3>{option.title}</h3>
            </div>
            <p>{option.description}</p>
            <Button
              variant={activeView === option.id ? 'primary' : 'secondary'}
              onClick={() => onSelect(option.id)}
              aria-pressed={activeView === option.id}
            >
              {activeView === option.id ? `${option.title} selected` : option.action}
            </Button>
          </Card>
        ))}
      </div>
    </section>
  );
}

function QuizScopeSummary({
  scope,
  pending = false,
  confirmed = false,
}: {
  scope: QuizScopePreview;
  pending?: boolean;
  confirmed?: boolean;
}) {
  const baseType = scope.type.replace('adaptive-', '');
  const typeLabel: Record<string, string> = {
    global: 'All material',
    notebook: 'Notebook',
    document: 'Source',
    documents: 'Sources',
    topic: 'Topic',
  };
  const documentCount = scope.document_count;
  const displayLabel = scope.label.replace(/indexed documents?/gi, "study material");
  const displayDescription = scope.description
    .replace(/indexed documents?/gi, "study material")
    .replace(/indexed source excerpts/gi, "connected material");

  return (
    <Card padding="small" tone="muted" className="quiz-scope-card">
      <div className="quiz-scope-card__header">
        <div>
          <p className="eyebrow">Quiz source</p>
          <h3>{displayLabel}</h3>
        </div>
        <div className="summary-badges">
          <Badge tone="primary">{typeLabel[baseType] ?? 'Scoped'}</Badge>
          {pending ? <Badge tone="info">Resolving sources</Badge> : null}
          {!pending && confirmed && scope.personalized ? (
            <Badge tone="info">Personalized quiz</Badge>
          ) : null}
          {!pending && confirmed && !scope.personalized ? (
            <Badge tone="neutral">Standard quiz</Badge>
          ) : null}
        </div>
      </div>
      <p>{displayDescription}</p>
      <dl className="quiz-scope-card__facts">
        <div>
          <dt>Included sources</dt>
          <dd>{documentCount ?? (pending ? 'Resolving…' : 'Confirmed when generated')}</dd>
        </div>
        <div>
          <dt>Personalization</dt>
          <dd>
            {scope.personalized
              ? 'Relevant learner history applied'
              : confirmed
                ? 'No relevant learner history applied'
                : 'Applied only when relevant history exists'}
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function PlanWorkspace({
  scope,
  carriedPrompt,
}: {
  scope?: RetrievalScope;
  carriedPrompt: string;
}) {
  const [minutes, setMinutes] = useState(45);
  const [maxItems, setMaxItems] = useState(5);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const build = useAsyncAction((payload: StudyPlanRequest, signal: AbortSignal) =>
    apiClient.post<StudyPlan, StudyPlanRequest>('/api/study/actions/plan', payload, { signal }),
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setPlan(
        await build.run({
          total_minutes: minutes,
          max_items: maxItems,
          scope: scope ?? null,
        }),
      );
    } catch {
      // Keep form values for retry.
    }
  }

  return (
    <div className="page-stack">
      <SectionHeader
        title="Adaptive study plan"
        description="Organizes what to learn next, in what order, and how much time to spend."
      />
      {carriedPrompt ? <CarriedPromptNotice prompt={carriedPrompt} /> : null}
      <Card>
        <PlanForm
          minutes={minutes}
          maxItems={maxItems}
          onMinutes={setMinutes}
          onMaxItems={setMaxItems}
          onSubmit={handleSubmit}
          pending={build.isPending}
          submitLabel="Build study plan"
          error={build.error}
          onRetry={() => build.retry()}
        />
      </Card>
      {plan ? <PlanResult plan={plan} /> : null}
    </div>
  );
}

function CoachingWorkspace({
  scope,
  carriedPrompt,
}: {
  scope?: RetrievalScope;
  carriedPrompt: string;
}) {
  const [minutes, setMinutes] = useState(45);
  const [maxItems, setMaxItems] = useState(4);
  const [coaching, setCoaching] = useState<CoachingPlan | null>(null);
  const build = useAsyncAction((payload: StudyPlanRequest, signal: AbortSignal) =>
    apiClient.post<CoachingPlan, StudyPlanRequest>(
      '/api/study/actions/coaching-plan',
      payload,
      { signal },
    ),
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setCoaching(
        await build.run({
          total_minutes: minutes,
          max_items: maxItems,
          scope: scope ?? null,
        }),
      );
    } catch {
      // Preserve setup after provider or evidence failure.
    }
  }

  return (
    <div className="page-stack">
      <SectionHeader
        title="Grounded coaching"
        description="Uses your recent mistakes and study history to suggest what to review."
      />
      {carriedPrompt ? <CarriedPromptNotice prompt={carriedPrompt} /> : null}
      <Card>
        <PlanForm
          minutes={minutes}
          maxItems={maxItems}
          onMinutes={setMinutes}
          onMaxItems={setMaxItems}
          onSubmit={handleSubmit}
          pending={build.isPending}
          submitLabel="Generate coaching plan"
          error={build.error}
          onRetry={() => build.retry()}
        />
      </Card>
      {coaching ? (
        coaching.items.length ? (
          <div className="page-stack">
            {coaching.adaptation ? (
              <Notice tone="info">
                <strong>Why this was recommended:</strong>{" "}
                {coaching.adaptation.reason}
              </Notice>
            ) : null}
            {coaching.items.map((item) => (
              <Card key={`${item.plan_item.rank}-${item.plan_item.title}`} className="reading-card">
                <Badge tone={item.should_generate ? 'success' : 'warning'}>
                  {item.should_generate ? item.coaching_mode : 'Not generated'}
                </Badge>
                <h2>{item.topic || item.plan_item.title}</h2>
                {item.should_generate ? (
                  <div className="coaching-steps">
                    <StudyStep icon={<Lightbulb />} label="Objective" text={item.objective} />
                    <StudyStep icon={<ClipboardList />} label="Review" text={item.review_step} />
                    <StudyStep icon={<BrainCircuit />} label="Practice" text={item.practice_step} />
                    <StudyStep icon={<ListChecks />} label="Reassess" text={item.reassessment_question} />
                    <details>
                      <summary>Show expected answer and completion criteria</summary>
                      <p>{item.expected_answer}</p>
                      <p>{item.completion_criteria}</p>
                    </details>
                    <div className="source-grid">
                      {item.sources.map((source) => (
                        <SourceCard key={`${item.plan_item.rank}-${source.index}`} source={source} />
                      ))}
                    </div>
                  </div>
                ) : (
                  <p>{item.reason}</p>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState title="No coaching items" description="Complete a study session or quiz to collect unresolved evidence first." />
        )
      ) : null}
    </div>
  );
}

function CarriedPromptNotice({ prompt }: { prompt: string }) {
  return (
    <Notice tone="info" title="Question brought from Study Chat">
      {prompt}
    </Notice>
  );
}

interface PlanFormProps {
  minutes: number;
  maxItems: number;
  onMinutes: (value: number) => void;
  onMaxItems: (value: number) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  submitLabel: string;
  error: unknown;
  onRetry: () => Promise<StudyPlan | CoachingPlan> | undefined;
}

function PlanForm({
  minutes,
  maxItems,
  onMinutes,
  onMaxItems,
  onSubmit,
  pending,
  submitLabel,
  error,
  onRetry,
}: PlanFormProps) {
  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <div className="form-grid">
        <label>
          Available minutes
          <input
            type="number"
            min={10}
            max={240}
            value={minutes}
            onChange={(event) => onMinutes(Number(event.target.value))}
          />
        </label>
        <label>
          Maximum items
          <input
            type="number"
            min={1}
            max={20}
            value={maxItems}
            onChange={(event) => onMaxItems(Number(event.target.value))}
          />
        </label>
      </div>
      {error ? <ErrorNotice error={error} onRetry={onRetry} /> : null}
      <Button type="submit" loading={pending} loadingText="Building plan…">
        {submitLabel}
      </Button>
    </form>
  );
}

function PlanResult({ plan }: { plan: StudyPlan }) {
  const allocated = useMemo(
    () => plan.items.reduce((total, item) => total + item.estimated_minutes, 0),
    [plan.items],
  );
  if (!plan.items.length) {
    return <EmptyState title="No unresolved evidence" description="The plan stays empty rather than inventing study work." />;
  }
  return (
    <div className="page-stack">
      {plan.adaptation ? (
        <Notice tone="info">
          <strong>Why this was recommended:</strong> {plan.adaptation.reason}
        </Notice>
      ) : null}
      <ProgressBar label="Time allocated" value={allocated} max={plan.requested_minutes} />
      <ol className="plan-list">
        {plan.items.map((item) => (
          <li key={`${item.rank}-${item.title}`}>
            <Card>
              <div className="plan-item__header">
                <span className="plan-rank">{item.rank}</span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.estimated_minutes} minutes</p>
                </div>
                <Badge tone="info">
                  {item.rank === 1 ? "Start here" : "Next step"}
                </Badge>
              </div>
              <p>{item.action}</p>
              <ul>
                {item.evidence.map((evidence) => (
                  <li key={`${evidence.evidence_type}-${evidence.reference_id}`}>
                    {evidence.detail}
                  </li>
                ))}
              </ul>
            </Card>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StudyStep({ icon, label, text }: { icon: ReactNode; label: string; text: string }) {
  return (
    <div className="study-step">
      <span aria-hidden="true">{icon}</span>
      <div>
        <h3>{label}</h3>
        <p>{text}</p>
      </div>
    </div>
  );
}
