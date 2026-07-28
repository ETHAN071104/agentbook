import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api";
import { apiClient } from "../api/client";
import { LearningAgentPage } from "../pages/LearningAgentPage";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function agentResponse(overrides: Record<string, unknown> = {}) {
  return {
    answer: "Review database joins first, then try a short quiz.",
    tools_used: ["get_weak_topics"],
    evidence: {
      summary: ["Found one weak topic in recent learning evidence."],
      related_document_public_ids: ["3557348663300104065"],
      related_quiz_attempt_public_ids: ["3557348663300104066"],
      weak_topics_used: ["Database joins"],
    },
    suggested_ui_action: "open_weak_topics",
    confirmation_required: false,
    proposal: null,
    ...overrides,
  };
}

function proposalResponse(
  action: "create_study_task" | "complete_study_task" = "create_study_task",
  expiresAt = "2099-07-27T12:10:00Z",
) {
  return agentResponse({
    answer:
      "I prepared a task for your confirmation. Nothing has been changed yet.",
    tools_used: [],
    evidence: {
      summary: [],
      related_document_public_ids: [],
      related_quiz_attempt_public_ids: [],
      weak_topics_used: [],
    },
    suggested_ui_action: "none",
    confirmation_required: true,
    proposal: {
      proposal_id: "12345678-1234-4234-8234-123456789abc",
      action,
      display_title:
        action === "create_study_task"
          ? "Create Study Task"
          : "Complete Study Task",
      display_summary:
        action === "create_study_task"
          ? "Review and confirm this task before it is created."
          : "Review and confirm before this task is marked completed.",
      task_preview: {
        title: "Review database joins",
        description:
          action === "create_study_task"
            ? "Practice a small join example."
            : "",
        topic: "Database joins",
        status: "pending",
        priority: "normal",
        due_at: null,
      },
      evidence_summary: "Prepared from bounded learner input.",
      expires_at: expiresAt,
      confirmation_required: true,
      risk_level: "low",
    },
  });
}

function confirmationResponse(
  action: "create_study_task" | "complete_study_task" = "create_study_task",
) {
  return {
    executed: true,
    action,
    task: {
      id: "3557348663300104999",
      title: "Review database joins",
      description: "Practice a small join example.",
      topic: "Database joins",
      status: action === "complete_study_task" ? "completed" : "pending",
      priority: "normal",
      due_at: null,
      completed_at:
        action === "complete_study_task" ? "2026-07-27T12:00:00Z" : null,
      archived_at: null,
      created_at: "2026-07-27T11:00:00Z",
      updated_at: "2026-07-27T12:00:00Z",
    },
    message:
      action === "create_study_task"
        ? "The task has been created."
        : "The task has been completed.",
    suggested_ui_action: "open_study_tasks",
  };
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/agent"]}>
      <LearningAgentPage />
    </MemoryRouter>,
  );
}

async function askQuestion(question = "What should I study next?") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Ask a learning question"), question);
  await user.click(screen.getByRole("button", { name: "Ask Agentbook" }));
  return user;
}

describe("Learning Agent interface", () => {
  beforeEach(() => apiClient.invalidate());
  afterEach(() => vi.unstubAllGlobals());

  it("renders a grounded answer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(agentResponse())),
    );
    renderPage();
    await askQuestion();
    expect(
      await screen.findByText(
        "Review database joins first, then try a short quiz.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Agentbook’s answer" }),
    ).toBeTruthy();
  });

  it("shows a loading state while evidence is being reviewed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    renderPage();
    await askQuestion();
    expect(
      await screen.findByText("Reviewing your learning evidence…"),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Thinking…" }).hasAttribute("disabled"),
    ).toBe(true);
  });

  it("shows a safe error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: "agent_unavailable",
              message: "Learning guidance is temporarily unavailable.",
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderPage();
    await askQuestion();
    expect(
      await screen.findByRole("heading", {
        name: "Agentbook could not answer",
      }),
    ).toBeTruthy();
    expect(
      screen.getByText("Learning guidance is temporarily unavailable."),
    ).toBeTruthy();
  });

  it("renders the human-readable evidence summary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(agentResponse())),
    );
    renderPage();
    await askQuestion();
    expect(await screen.findByRole("heading", { name: "Based on" })).toBeTruthy();
    expect(
      screen.getByText("Found one weak topic in recent learning evidence."),
    ).toBeTruthy();
    expect(screen.getByText(/Focus areas: Database joins/)).toBeTruthy();
  });

  it("renders the suggested action without navigating automatically", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(agentResponse())),
    );
    renderPage();
    await askQuestion();
    const action = await screen.findByRole("link", {
      name: "Start review",
    });
    expect(action.getAttribute("href")).toBe("/study-actions?view=review");
  });

  it("submits an example prompt", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        jsonResponse(agentResponse()),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", {
        name: "What mistakes have I made recently?",
      }),
    );
    await screen.findByText(
      "Review database joins first, then try a short quiz.",
    );
    const request = fetchMock.mock.calls[0]![1]!;
    expect(JSON.parse(String(request.body))).toEqual({
      message: "What mistakes have I made recently?",
    });
  });

  it("does not display internal tool names or public IDs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(agentResponse())),
    );
    renderPage();
    await askQuestion();
    await screen.findByText(
      "Review database joins first, then try a short quiz.",
    );
    expect(screen.queryByText("get_weak_topics")).toBeNull();
    expect(screen.queryByText("3557348663300104065")).toBeNull();
    expect(screen.queryByText("3557348663300104066")).toBeNull();
    expect(document.body.textContent).not.toContain("workspace_id");
  });

  it("renders a create-task confirmation card", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(proposalResponse())),
    );
    renderPage();
    await askQuestion("Create a task to review database joins");
    expect(
      await screen.findByRole("heading", { name: "Create Study Task" }),
    ).toBeTruthy();
    expect(screen.getByText("Review database joins")).toBeTruthy();
    expect(screen.getByText("Nothing has been changed yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeTruthy();
  });

  it("renders a complete-task confirmation card without marking it complete", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(proposalResponse("complete_study_task")),
      ),
    );
    renderPage();
    await askQuestion("Complete my database joins task");
    expect(
      await screen.findByRole("heading", { name: "Complete Study Task" }),
    ).toBeTruthy();
    expect(screen.getByText("pending")).toBeTruthy();
    expect(screen.queryByText("The task has been completed.")).toBeNull();
  });

  it("Confirm calls only the proposal confirmation endpoint", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, _init?: RequestInit) =>
        String(input).endsWith("/confirm")
          ? jsonResponse(confirmationResponse())
          : jsonResponse(proposalResponse()),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    const user = await askQuestion("Create a task to review joins");
    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("The task has been created.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1]![0])).toBe(
      "/api/agent/actions/12345678-1234-4234-8234-123456789abc/confirm",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1]![1]?.body))).toEqual({
      confirm: true,
    });
  });

  it("Cancel dismisses the proposal without executing", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(proposalResponse()));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    const user = await askQuestion("Create a task to review joins");
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(await screen.findByText("Nothing was changed.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
  });

  it("double-clicking Confirm sends one confirmation request", async () => {
    let resolveConfirm: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/confirm")) {
          return await new Promise<Response>((resolve) => {
            resolveConfirm = resolve;
          });
        }
        return jsonResponse(proposalResponse());
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    const user = await askQuestion("Create a task to review joins");
    await user.dblClick(await screen.findByRole("button", { name: "Confirm" }));
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/confirm"),
      ),
    ).toHaveLength(1);
    resolveConfirm?.(jsonResponse(confirmationResponse()));
    expect(await screen.findByText("The task has been created.")).toBeTruthy();
  });

  it("renders an expired proposal without an active Confirm button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(proposalResponse("create_study_task", "2000-01-01T00:00:00Z")),
      ),
    );
    renderPage();
    await askQuestion("Create a task to review joins");
    expect(
      await screen.findByText("Ask Agentbook to prepare a fresh action. Nothing was changed."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
  });

  it("renders an already-consumed confirmation safely", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).endsWith("/confirm")
          ? jsonResponse(
              {
                error: {
                  code: "AGENT_PROPOSAL_CONSUMED",
                  title: "Already executed",
                  reason: "This confirmation was already executed.",
                  next_action: "Open Study Tasks.",
                  retryable: false,
                  request_id: "1234567890abcdef1234567890abcdef",
                  message: "This confirmation was already executed.",
                },
              },
              { status: 409 },
            )
          : jsonResponse(proposalResponse()),
      ),
    );
    renderPage();
    const user = await askQuestion("Create a task to review joins");
    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    expect(
      await screen.findByText(/This confirmation was already executed/),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open Tasks" })).toBeTruthy();
  });

  it("renders a safe confirmation error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).endsWith("/confirm")
          ? jsonResponse(
              {
                error: {
                  code: "AGENT_PROPOSAL_CONFLICT",
                  title: "Action changed",
                  reason: "The target task changed.",
                  next_action: "Ask again.",
                  retryable: false,
                  request_id: "abcdef1234567890abcdef1234567890",
                  message: "The target task changed.",
                },
              },
              { status: 409 },
            )
          : jsonResponse(proposalResponse("complete_study_task")),
      ),
    );
    renderPage();
    const user = await askQuestion("Complete my joins task");
    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("The target task changed.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeTruthy();
  });

  it("invalidates cached Study Tasks after successful confirmation", async () => {
    let taskListReads = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path.startsWith("/api/study/tasks")) {
          taskListReads += 1;
          return jsonResponse({
            items: taskListReads === 1 ? [] : [confirmationResponse().task],
            total: taskListReads === 1 ? 0 : 1,
          });
        }
        if (path.endsWith("/confirm")) {
          return jsonResponse(confirmationResponse());
        }
        return jsonResponse(proposalResponse());
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    expect((await api.listStudyTasks()).total).toBe(0);
    renderPage();
    const user = await askQuestion("Create a task to review joins");
    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    await screen.findByText("The task has been created.");
    expect((await api.listStudyTasks()).total).toBe(1);
    expect(taskListReads).toBe(2);
  });

  it("does not display proposal IDs or stored internals", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(proposalResponse())),
    );
    renderPage();
    await askQuestion("Create a task to review joins");
    await screen.findByRole("heading", { name: "Create Study Task" });
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("12345678-1234-4234-8234-123456789abc");
    expect(text).not.toContain("operation_hash");
    expect(text).not.toContain("expected_version");
    expect(text).not.toContain("workspace_id");
  });
});
