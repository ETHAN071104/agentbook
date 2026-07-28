import { useMemo, useRef, useState, type FormEvent } from "react";
import {
  Archive,
  CalendarClock,
  Check,
  CheckCircle2,
  Pencil,
  Plus,
  RotateCcw,
  X,
} from "lucide-react";

import {
  api,
  getErrorMessage,
  type PublicId,
  type StudyTask,
  type StudyTaskCreate,
  type StudyTaskPriority,
  type StudyTaskStatus,
  type StudyTaskUpdate,
} from "../api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  Notice,
  PageHeader,
  SectionHeader,
} from "../components";
import { useApiQuery, useAsyncAction } from "../hooks";

type FilterValue = "todo" | "completed" | "archived" | "history";
type LifecycleAction = "complete" | "reopen" | "cancel" | "archive";

interface LifecycleRequest {
  id: PublicId;
  action: LifecycleAction;
}

interface CreateAttempt {
  payload: StudyTaskCreate;
  idempotencyKey: string;
}

interface EditDraft {
  title: string;
  description: string;
  topic: string;
  priority: StudyTaskPriority;
  dueAt: string;
}

const EMPTY_CREATE: StudyTaskCreate = {
  title: "",
  description: "",
  topic: "",
  priority: "normal",
  due_at: null,
};

function operationKey(): string {
  const browserCrypto = globalThis.crypto;
  if (browserCrypto?.randomUUID) return browserCrypto.randomUUID();
  if (!browserCrypto?.getRandomValues) {
    throw new Error("Secure task operation keys are unavailable.");
  }
  const bytes = browserCrypto.getRandomValues(new Uint8Array(24));
  return Array.from(
    bytes,
    (value) => value.toString(16).padStart(2, "0"),
  ).join("");
}

function localInputToIso(value: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? null : parsed.toISOString();
}

function isoToLocalInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.valueOf() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function dueLabel(value: string | null): string {
  if (!value) return "No due date";
  const date = new Date(value);
  const formatted = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
  return date.valueOf() < Date.now() ? `Overdue: ${formatted}` : `Due ${formatted}`;
}

function taskTone(status: StudyTaskStatus) {
  if (status === "completed") return "success" as const;
  if (status === "cancelled") return "warning" as const;
  if (status === "archived") return "neutral" as const;
  return "info" as const;
}

function taskStatusLabel(status: StudyTaskStatus) {
  if (status === "pending") return "To Do";
  if (status === "completed") return "Completed";
  if (status === "cancelled") return "Cancelled";
  return "Archived";
}

export function StudyTasksPage() {
  const [filter, setFilter] = useState<FilterValue>("todo");
  const [createOpen, setCreateOpen] = useState(false);
  const [createDraft, setCreateDraft] = useState<StudyTaskCreate>(EMPTY_CREATE);
  const [createDueAt, setCreateDueAt] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [recentlyCreatedTask, setRecentlyCreatedTask] =
    useState<StudyTask | null>(null);
  const [editingId, setEditingId] = useState<PublicId | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);
  const activeCreateAttempt = useRef<CreateAttempt | null>(null);

  const taskQuery = useApiQuery(
    ["study-tasks", filter],
    (signal) =>
      api.listStudyTasks(
        filter === "todo"
          ? { status: "pending", includeArchived: false, limit: 100 }
          : filter === "history"
            ? { status: "cancelled", includeArchived: false, limit: 100 }
            : {
                status: filter,
                includeArchived: filter === "archived",
                limit: 100,
              },
        { signal, forceRefresh: true, cacheTtlMs: 0 },
      ),
    { keepPreviousData: false },
  );
  const createAction = useAsyncAction(
    (
      attempt: CreateAttempt,
      signal: AbortSignal,
    ) => api.createStudyTask(
      attempt.payload,
      attempt.idempotencyKey,
      { signal },
    ),
  );
  const updateAction = useAsyncAction(
    (
      id: PublicId,
      payload: StudyTaskUpdate,
      signal: AbortSignal,
    ) => api.updateStudyTask(id, payload, { signal }),
  );
  const lifecycle = useAsyncAction(
    ({ id, action }: LifecycleRequest, signal: AbortSignal) =>
      api.studyTasks[action](id, { signal }),
  );

  const sections = useMemo(() => {
    const listedTasks = taskQuery.data?.items ?? [];
    const tasks = (
      recentlyCreatedTask?.status === "pending"
      && !listedTasks.some((task) => task.id === recentlyCreatedTask.id)
    )
      ? [recentlyCreatedTask, ...listedTasks]
      : listedTasks;
    return {
      pending: tasks.filter((task) => task.status === "pending"),
      completed: tasks.filter((task) => task.status === "completed"),
      cancelled: tasks.filter((task) => task.status === "cancelled"),
      archived: tasks.filter((task) => task.status === "archived"),
    };
  }, [recentlyCreatedTask, taskQuery.data]);
  const visibleTaskCount = (
    sections.pending.length
    + sections.completed.length
    + sections.cancelled.length
    + sections.archived.length
  );

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    const title = createDraft.title.trim();
    if (!title) {
      setCreateError("Enter a task title.");
      return;
    }
    if (title.length > 200) {
      setCreateError("Task title must contain at most 200 characters.");
      return;
    }
    const attempt = activeCreateAttempt.current ?? {
      payload: {
          ...createDraft,
          title,
          description: createDraft.description?.trim(),
          topic: createDraft.topic?.trim(),
          due_at: localInputToIso(createDueAt),
        },
      idempotencyKey: operationKey(),
    };
    activeCreateAttempt.current = attempt;
    try {
      const createdTask = await createAction.run(attempt);
      if (createdTask.status !== "pending") {
        setCreateError(
          "The request did not create a new pending task. Submit it again.",
        );
        return;
      }
      setRecentlyCreatedTask(createdTask);
      setCreateDraft(EMPTY_CREATE);
      setCreateDueAt("");
      setFilter("todo");
      setCreateOpen(false);
      taskQuery.reload();
    } catch {
      // The form remains populated for correction or retry.
    } finally {
      if (activeCreateAttempt.current === attempt) {
        activeCreateAttempt.current = null;
      }
    }
  }

  function beginEdit(task: StudyTask) {
    setEditingId(task.id);
    setEditDraft({
      title: task.title,
      description: task.description,
      topic: task.topic,
      priority: task.priority,
      dueAt: isoToLocalInput(task.due_at),
    });
    updateAction.reset();
  }

  async function handleEdit(event: FormEvent<HTMLFormElement>, id: PublicId) {
    event.preventDefault();
    if (!editDraft?.title.trim()) return;
    try {
      const updatedTask = await updateAction.run(id, {
        title: editDraft.title.trim(),
        description: editDraft.description.trim(),
        topic: editDraft.topic.trim(),
        priority: editDraft.priority,
        due_at: localInputToIso(editDraft.dueAt),
      });
      if (recentlyCreatedTask?.id === id) {
        setRecentlyCreatedTask(updatedTask);
      }
      setEditingId(null);
      setEditDraft(null);
      taskQuery.reload();
    } catch {
      // Keep the edit form open.
    }
  }

  async function runLifecycle(id: PublicId, action: LifecycleAction) {
    try {
      const updatedTask = await lifecycle.run({ id, action });
      if (recentlyCreatedTask?.id === id) {
        setRecentlyCreatedTask(
          updatedTask.status === "pending" ? updatedTask : null,
        );
      }
      taskQuery.reload();
    } catch {
      // A safe action error remains visible above the list.
    }
  }

  return (
    <div className="page-stack task-page">
      <PageHeader
        eyebrow="Your study commitments"
        title="Tasks"
        description={
          <p>
            Keep the next concrete actions you want to complete.
          </p>
        }
        actions={
          <Button
            icon={<Plus size={18} aria-hidden="true" />}
            onClick={() => setCreateOpen((open) => !open)}
            aria-expanded={createOpen}
          >
            Add task
          </Button>
        }
      />

      {createOpen ? (
      <Card padding="large" className="task-create-card">
        <SectionHeader
          title="Create a task"
          description="Add one clear action you want to complete."
        />
        <form className="task-form" onSubmit={handleCreate}>
          <label htmlFor="task-title">Title</label>
          <input
            id="task-title"
            maxLength={200}
            required
            value={createDraft.title}
            onChange={(event) => {
              setCreateDraft((current) => ({
                ...current,
                title: event.target.value,
              }));
              setCreateError(null);
            }}
            placeholder="Review chapter 4 examples"
          />
          <details className="task-form__optional">
            <summary>Add details</summary>
            <div className="task-form__optional-fields">
              <label htmlFor="task-description">Description</label>
              <textarea
                id="task-description"
                maxLength={2000}
                rows={3}
                value={createDraft.description}
                onChange={(event) =>
                  setCreateDraft((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
              />
              <div className="task-form__grid">
                <label>
                  <span>Topic</span>
                  <input
                    maxLength={200}
                    value={createDraft.topic}
                    onChange={(event) =>
                      setCreateDraft((current) => ({
                        ...current,
                        topic: event.target.value,
                      }))
                    }
                  />
                </label>
                <label>
                  <span>Due date</span>
                  <input
                    type="datetime-local"
                    value={createDueAt}
                    onChange={(event) => setCreateDueAt(event.target.value)}
                  />
                </label>
                <label>
                  <span>Priority</span>
                  <select
                    value={createDraft.priority}
                    onChange={(event) =>
                      setCreateDraft((current) => ({
                        ...current,
                        priority: event.target.value as StudyTaskPriority,
                      }))
                    }
                  >
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                  </select>
                </label>
              </div>
            </div>
          </details>
          <div className="task-form__actions">
            <p className="field-help">
              {createDraft.title.length}/200 title characters
            </p>
            <Button
              type="submit"
              loading={createAction.isPending}
              loadingText="Creating…"
              icon={<Plus size={18} aria-hidden="true" />}
            >
              Save task
            </Button>
            <Button
              variant="ghost"
              onClick={() => setCreateOpen(false)}
              disabled={createAction.isPending}
            >
              Cancel
            </Button>
          </div>
          {createError ? (
            <p className="field-error" role="alert">{createError}</p>
          ) : null}
          {createAction.error ? (
            <Notice tone="error" title="Task was not created">
              {getErrorMessage(createAction.error)}
            </Notice>
          ) : null}
        </form>
      </Card>
      ) : null}

      <section className="task-list-section" aria-labelledby="task-list-title">
        <SectionHeader
          headingId="task-list-title"
          title="Your tasks"
          actions={
            <div className="task-view-controls">
              <div className="task-view-tabs" role="group" aria-label="Task view">
                <button
                  type="button"
                  className={filter === "todo" ? "is-active" : ""}
                  aria-pressed={filter === "todo"}
                  onClick={() => setFilter("todo")}
                >
                  To Do
                </button>
                <button
                  type="button"
                  className={filter === "completed" ? "is-active" : ""}
                  aria-pressed={filter === "completed"}
                  onClick={() => setFilter("completed")}
                >
                  Completed
                </button>
              </div>
              <details className="task-more-views">
                <summary>More views</summary>
                <div className="task-more-views__options">
                  <button
                    type="button"
                    aria-pressed={filter === "archived"}
                    onClick={() => setFilter("archived")}
                  >
                    Archived
                  </button>
                  <button
                    type="button"
                    aria-pressed={filter === "history"}
                    onClick={() => setFilter("history")}
                  >
                    History
                  </button>
                </div>
              </details>
            </div>
          }
        />

        {taskQuery.isLoading ? (
          <LoadingState message="Loading your tasks..." />
        ) : taskQuery.error ? (
          <ErrorState
            title="Tasks could not be loaded"
            message={getErrorMessage(taskQuery.error)}
            onRetry={taskQuery.retry}
          />
        ) : visibleTaskCount === 0 ? (
          <EmptyState
            icon={<CheckCircle2 />}
            title="No tasks in this view"
            description={
              filter === "todo"
                ? "Add a task when you have a concrete next step."
                : "Choose another view or return to To Do."
            }
          />
        ) : (
          <div className="task-groups">
            {(
              [
                ["pending", "To Do"],
                ["completed", "Completed"],
                ["cancelled", "Cancelled"],
                ["archived", "Archived"],
              ] as const
            ).map(([status, label]) =>
              sections[status].length ? (
                <section key={status} className="task-group">
                  <h3>{label}</h3>
                  <div className="task-list">
                    {sections[status].map((task) => (
                      <Card
                        key={task.id}
                        className={[
                          "task-card",
                          task.status === "completed"
                            ? "task-card--completed"
                            : "",
                        ].filter(Boolean).join(" ")}
                      >
                        <div className="task-card__heading">
                          <div>
                            <h4>{task.title}</h4>
                            <div className="task-card__badges">
                              <Badge tone={taskTone(task.status)}>
                                {taskStatusLabel(task.status)}
                              </Badge>
                              <Badge tone={task.priority === "high" ? "warning" : "neutral"}>
                                {task.priority} priority
                              </Badge>
                            </div>
                          </div>
                          <p className="task-card__due">
                            <CalendarClock size={17} aria-hidden="true" />
                            {dueLabel(task.due_at)}
                          </p>
                        </div>
                        {task.description ? <p>{task.description}</p> : null}
                        {task.topic ? (
                          <p className="supporting-text">Topic: {task.topic}</p>
                        ) : null}

                        {editingId === task.id && editDraft ? (
                          <form
                            className="task-form task-edit-form"
                            onSubmit={(event) => void handleEdit(event, task.id)}
                          >
                            <label>
                              <span>Title</span>
                              <input
                                required
                                maxLength={200}
                                value={editDraft.title}
                                onChange={(event) =>
                                  setEditDraft({
                                    ...editDraft,
                                    title: event.target.value,
                                  })
                                }
                              />
                            </label>
                            <label>
                              <span>Description</span>
                              <textarea
                                rows={3}
                                maxLength={2000}
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft({
                                    ...editDraft,
                                    description: event.target.value,
                                  })
                                }
                              />
                            </label>
                            <div className="task-form__grid">
                              <label>
                                <span>Topic</span>
                                <input
                                  maxLength={200}
                                  value={editDraft.topic}
                                  onChange={(event) =>
                                    setEditDraft({
                                      ...editDraft,
                                      topic: event.target.value,
                                    })
                                  }
                                />
                              </label>
                              <label>
                                <span>Due date</span>
                                <input
                                  type="datetime-local"
                                  value={editDraft.dueAt}
                                  onChange={(event) =>
                                    setEditDraft({
                                      ...editDraft,
                                      dueAt: event.target.value,
                                    })
                                  }
                                />
                              </label>
                              <label>
                                <span>Priority</span>
                                <select
                                  value={editDraft.priority}
                                  onChange={(event) =>
                                    setEditDraft({
                                      ...editDraft,
                                      priority: event.target
                                        .value as StudyTaskPriority,
                                    })
                                  }
                                >
                                  <option value="low">Low</option>
                                  <option value="normal">Normal</option>
                                  <option value="high">High</option>
                                </select>
                              </label>
                            </div>
                            <div className="button-group">
                              <Button
                                type="submit"
                                loading={updateAction.isPending}
                              >
                                Save changes
                              </Button>
                              <Button
                                variant="ghost"
                                onClick={() => {
                                  setEditingId(null);
                                  setEditDraft(null);
                                }}
                              >
                                Close editor
                              </Button>
                            </div>
                            {updateAction.error ? (
                              <Notice tone="error" title="Task was not updated">
                                {getErrorMessage(updateAction.error)}
                              </Notice>
                            ) : null}
                          </form>
                        ) : null}

                        {task.status !== "archived" ? (
                          <div className="task-card__actions">
                            {task.status === "pending" ? (
                              <>
                                <Button
                                  variant="secondary"
                                  icon={<Check size={17} aria-hidden="true" />}
                                  onClick={() =>
                                    void runLifecycle(task.id, "complete")
                                  }
                                >
                                  Mark complete
                                </Button>
                                <Button
                                  variant="ghost"
                                  icon={<X size={17} aria-hidden="true" />}
                                  onClick={() =>
                                    void runLifecycle(task.id, "cancel")
                                  }
                                >
                                  Cancel task
                                </Button>
                              </>
                            ) : (
                              <Button
                                variant="secondary"
                                icon={<RotateCcw size={17} aria-hidden="true" />}
                                onClick={() =>
                                  void runLifecycle(task.id, "reopen")
                                }
                              >
                                Reopen task
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              icon={<Pencil size={17} aria-hidden="true" />}
                              onClick={() => beginEdit(task)}
                            >
                              Edit task
                            </Button>
                            <Button
                              variant="ghost"
                              icon={<Archive size={17} aria-hidden="true" />}
                              onClick={() =>
                                void runLifecycle(task.id, "archive")
                              }
                            >
                              Archive task
                            </Button>
                          </div>
                        ) : null}
                      </Card>
                    ))}
                  </div>
                </section>
              ) : null,
            )}
          </div>
        )}

        {lifecycle.error ? (
          <Notice tone="error" title="Task action was not completed">
            {getErrorMessage(lifecycle.error)}
          </Notice>
        ) : null}
      </section>
    </div>
  );
}
