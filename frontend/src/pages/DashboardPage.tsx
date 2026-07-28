import {
  ArrowRight,
  BookOpenCheck,
  Clock3,
  FilePlus2,
  History,
  ListChecks,
  Play,
  TrendingUp,
} from "lucide-react";
import { Link } from "react-router-dom";

import { api, getErrorMessage, type StudyTask } from "../api";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  SectionHeader,
} from "../components";
import { useApiQuery } from "../hooks";

function formatDate(value: string | null) {
  if (!value) return "No due date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function nearestPendingTask(tasks: StudyTask[]): StudyTask | null {
  return (
    tasks
      .filter((task) => task.status === "pending")
      .sort((left, right) => {
        if (!left.due_at && !right.due_at) {
          return Date.parse(left.created_at) - Date.parse(right.created_at);
        }
        if (!left.due_at) return 1;
        if (!right.due_at) return -1;
        return Date.parse(left.due_at) - Date.parse(right.due_at);
      })[0] ?? null
  );
}

export function DashboardPage() {
  const dashboard = useApiQuery(["dashboard", 5], (signal) =>
    api.getDashboard(5, { signal }),
  );
  const tasks = useApiQuery(["home", "study-tasks"], (signal) =>
    api.listStudyTasks(
      { includeArchived: false, limit: 100 },
      { signal, forceRefresh: true, cacheTtlMs: 0 },
    ),
  );
  const reviewQueue = useApiQuery(["home", "review-queue"], (signal) =>
    api.getReviewQueue({ maxItems: 1 }, { signal }),
  );

  if (dashboard.isLoading && !dashboard.data) {
    return <LoadingState message="Preparing your Home page..." />;
  }

  if (dashboard.error && !dashboard.data) {
    return (
      <ErrorState
        title="Home is unavailable"
        message={getErrorMessage(dashboard.error)}
        onRetry={dashboard.retry}
      />
    );
  }

  if (!dashboard.data) return null;

  const data = dashboard.data;
  const hasMaterial = data.counts.documents > 0;
  const pendingTask = nearestPendingTask(tasks.data?.items ?? []);
  const weakArea = reviewQueue.data?.items?.[0] ?? null;
  const recentQuiz = data.recent_quizzes[0] ?? null;
  const latestCompletedTask =
    tasks.data?.items
      ?.filter((task) => task.status === "completed")
      .sort(
        (left, right) =>
          Date.parse(right.completed_at ?? right.updated_at) -
          Date.parse(left.completed_at ?? left.updated_at),
      )[0] ?? null;

  const recentChange = recentQuiz
    ? {
        title: `${Math.round(recentQuiz.score_percentage)}% on ${recentQuiz.quiz_topic}`,
        description:
          recentQuiz.score_percentage < 70
            ? "This result identified material worth reviewing next."
            : "Your latest quiz shows a solid step forward.",
        icon: TrendingUp,
      }
    : latestCompletedTask
      ? {
          title: latestCompletedTask.title,
          description: "You completed this study task.",
          icon: ListChecks,
        }
      : data.outcomes.confused > 0 || data.outcomes.partial > 0
        ? {
            title: "A recent answer needs another look",
            description:
              "Agentbook kept this feedback so your next review can stay focused.",
            icon: TrendingUp,
          }
        : null;

  const nextAction = data.active_session
    ? {
        title: "Continue your active session",
        description: `You started this session ${formatDate(
          data.active_session.started_at,
        )}.`,
        label: "Continue session",
        to: "/chat",
        icon: Play,
      }
    : pendingTask
      ? {
          title: pendingTask.title,
          description: pendingTask.due_at
            ? `Your nearest task is due ${formatDate(pendingTask.due_at)}.`
            : "This is the next open task in your study list.",
          label: "Open task",
          to: "/tasks",
          icon: Clock3,
        }
      : weakArea
        ? {
            title: "Review a recent weak area",
            description: weakArea.question,
            label: "Start review",
            to: "/study-actions?view=review",
            icon: TrendingUp,
          }
        : recentQuiz
          ? {
              title: `Practise ${recentQuiz.quiz_topic}`,
              description: "Build on your most recent quiz while it is fresh.",
              label: "Start quiz",
              to: `/study-actions?view=quiz&topic=${encodeURIComponent(
                recentQuiz.quiz_topic,
              )}`,
              icon: BookOpenCheck,
            }
          : hasMaterial
            ? {
                title: "Practise your material",
                description: "Start a short quiz using your saved study material.",
                label: "Start quiz",
                to: "/study-actions?view=quiz",
                icon: BookOpenCheck,
              }
            : {
                title: "Add your first study material",
                description:
                  "Upload a PDF, presentation, or text file. You can organize it later.",
                label: "Upload study material",
                to: "/notebooks#upload",
                icon: FilePlus2,
              };

  const NextIcon = nextAction.icon;
  const ChangeIcon = recentChange?.icon;

  return (
    <div className="page-stack home-page">
      <PageHeader
        eyebrow="Today"
        title="Home"
        description="See what you are learning, what changed, and the clearest next step."
      />

      {dashboard.isRefreshing ? (
        <LoadingState compact message="Refreshing Home..." />
      ) : null}

      <section className="home-section" aria-labelledby="learning-now-title">
        <SectionHeader
          headingId="learning-now-title"
          title="What you are learning"
        />
        {hasMaterial ? (
          <div className="home-learning-summary">
            <div>
              <p className="home-learning-summary__lead">
                Your study material is ready when you are.
              </p>
              <p className="supporting-text">
                {data.counts.documents} source
                {data.counts.documents === 1 ? "" : "s"}
                {data.counts.notebooks > 0
                  ? ` organized across ${data.counts.notebooks} notebook${
                      data.counts.notebooks === 1 ? "" : "s"
                    }`
                  : ""}
                .
              </p>
            </div>
            <Link className="text-link" to="/notebooks">
              Open Library
            </Link>
          </div>
        ) : (
          <div className="home-empty-copy">
            <p>
              Start by adding material you want to learn from. Notebooks are
              optional and can be used later for organization.
            </p>
          </div>
        )}
      </section>

      <section className="home-section" aria-labelledby="what-changed-title">
        <SectionHeader
          headingId="what-changed-title"
          title="What changed"
          actions={
            <Link className="text-link" to="/progress">
              <History size={17} aria-hidden="true" />
              <span>View learning history</span>
            </Link>
          }
        />
        {recentChange && ChangeIcon ? (
          <div className="home-change">
            <span className="home-change__icon" aria-hidden="true">
              <ChangeIcon size={21} />
            </span>
            <div>
              <h3>{recentChange.title}</h3>
              <p>{recentChange.description}</p>
            </div>
          </div>
        ) : (
          <p className="supporting-text">
            Your first meaningful learning update will appear here after you
            study or complete a task.
          </p>
        )}
      </section>

      <section className="home-section" aria-labelledby="next-up-title">
        <SectionHeader headingId="next-up-title" title="Next up" />
        {!hasMaterial ? (
          <EmptyState
            icon={<FilePlus2 />}
            title={nextAction.title}
            description={nextAction.description}
            action={
              <Link className="button button--primary" to={nextAction.to}>
                <span>{nextAction.label}</span>
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            }
          />
        ) : (
          <Card tone="accent" className="home-next-card">
            <span className="home-next-card__icon" aria-hidden="true">
              <NextIcon size={24} />
            </span>
            <div className="home-next-card__copy">
              <div className="home-next-card__heading">
                <h3>{nextAction.title}</h3>
                <Badge tone="primary">Recommended</Badge>
              </div>
              <p>{nextAction.description}</p>
            </div>
            <Link className="button button--primary" to={nextAction.to}>
              <span>{nextAction.label}</span>
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </Card>
        )}
      </section>
    </div>
  );
}

export default DashboardPage;
