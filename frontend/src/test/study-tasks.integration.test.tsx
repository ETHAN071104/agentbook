import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { StudyTasksPage } from "../pages/StudyTasksPage";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function task(overrides: Record<string, unknown> = {}) {
  return {
    id: "3557348663300104065",
    title: "Review database joins",
    description: "Read two worked examples.",
    topic: "SQL",
    status: "pending",
    priority: "normal",
    due_at: null,
    completed_at: null,
    archived_at: null,
    created_at: "2030-01-01T10:00:00+00:00",
    updated_at: "2030-01-01T10:00:00+00:00",
    ...overrides,
  };
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/tasks"]}>
      <StudyTasksPage />
    </MemoryRouter>,
  );
}

async function openCreateForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Add task" }));
}

describe("Study Tasks interface", () => {
  beforeEach(() => apiClient.invalidate());
  afterEach(() => vi.unstubAllGlobals());

  it("renders the task list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ items: [task()], total: 1 })),
    );
    renderPage();
    expect(await screen.findByText("Review database joins")).toBeTruthy();
    expect(screen.getByText("Read two worked examples.")).toBeTruthy();
    expect(screen.getByText("Topic: SQL")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "To Do" })).toBeTruthy();
  });

  it("renders an empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ items: [], total: 0 })),
    );
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "No tasks in this view" }),
    ).toBeTruthy();
  });

  it("creates a task with an idempotency key", async () => {
    const created = task({ title: "Practice recursion" });
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") return jsonResponse(created, { status: 201 });
        return jsonResponse({ items: [], total: 0 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "No tasks in this view" });
    await openCreateForm(user);
    await user.type(screen.getByLabelText("Title"), "Practice recursion");
    await user.click(screen.getByRole("button", { name: "Save task" }));
    await vi.waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        ([, init]) => init?.method === "POST",
      );
      expect(createCall).toBeTruthy();
      const headers = new Headers(createCall![1]?.headers);
      expect(headers.get("Idempotency-Key")?.length).toBeGreaterThanOrEqual(16);
      expect(JSON.parse(String(createCall![1]?.body)).title).toBe(
        "Practice recursion",
      );
      expect(
        screen.getByRole("button", { name: "To Do" }).getAttribute("aria-pressed"),
      ).toBe("true");
    });
  });

  it("reuses one key for duplicate submits in the same in-flight attempt", async () => {
    let resolveCreate!: (response: Response) => void;
    const createResponse = new Promise<Response>((resolve) => {
      resolveCreate = resolve;
    });
    const keys: string[] = [];
    const randomUUID = vi.fn(() => "11111111-1111-4111-8111-111111111111");
    vi.stubGlobal("crypto", { randomUUID });
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          keys.push(new Headers(init.headers).get("Idempotency-Key") ?? "");
          return createResponse;
        }
        return jsonResponse({ items: [], total: 0 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "No tasks in this view" });
    await openCreateForm(user);
    await user.type(screen.getByLabelText("Title"), "Practice recursion");
    const form = screen.getByRole("button", { name: "Save task" }).closest(
      "form",
    );
    expect(form).toBeTruthy();
    fireEvent.submit(form!);
    fireEvent.submit(form!);
    await vi.waitFor(() => expect(keys).toHaveLength(1));
    expect(randomUUID).toHaveBeenCalledTimes(1);
    resolveCreate(jsonResponse(task({ title: "Practice recursion" }), { status: 201 }));
    expect(
      await screen.findByRole("heading", { name: "Practice recursion" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "To Do" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("uses a new key when identical content is recreated after cancellation", async () => {
    const keys: string[] = [];
    const generatedKeys = [
      "11111111-1111-4111-8111-111111111111",
      "22222222-2222-4222-8222-222222222222",
    ];
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => generatedKeys.shift()),
    });
    let items: ReturnType<typeof task>[] = [];
    const byKey = new Map<string, ReturnType<typeof task>>();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST" && url === "/api/study/tasks") {
          const key = new Headers(init.headers).get("Idempotency-Key") ?? "";
          keys.push(key);
          const replay = byKey.get(key);
          if (replay) return jsonResponse(replay);
          const payload = JSON.parse(String(init.body));
          const created = task({
            id: String(3557348663300104065n + BigInt(items.length)),
            title: payload.title,
          });
          items = [...items, created];
          byKey.set(key, created);
          return jsonResponse(created, { status: 201 });
        }
        if (init?.method === "POST" && url.endsWith("/cancel")) {
          const id = url.split("/").at(-2);
          items = items.map((item) =>
            item.id === id ? task({ ...item, status: "cancelled" }) : item,
          );
          return jsonResponse(items.find((item) => item.id === id));
        }
        const status = new URL(url, "http://agentbook.local").searchParams.get(
          "status",
        );
        const visible = status
          ? items.filter((item) => item.status === status)
          : items;
        return jsonResponse({ items: visible, total: visible.length });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "No tasks in this view" });

    await openCreateForm(user);
    const title = screen.getByLabelText("Title");
    await user.type(title, "Practice recursion");
    await user.click(screen.getByRole("button", { name: "Save task" }));
    const firstCard = (
      await screen.findByRole("heading", { name: "Practice recursion" })
    ).closest(".task-card") as HTMLElement | null;
    expect(firstCard).toBeTruthy();
    await user.click(
      within(firstCard!).getByRole("button", { name: "Cancel task" }),
    );
    await screen.findByRole("heading", { name: "No tasks in this view" });

    await openCreateForm(user);
    const secondTitle = screen.getByLabelText("Title");
    await user.type(secondTitle, "Practice recursion");
    await user.click(screen.getByRole("button", { name: "Save task" }));
    expect(
      await screen.findByRole("heading", { name: "Practice recursion" }),
    ).toBeTruthy();
    expect(keys).toEqual([
      "11111111-1111-4111-8111-111111111111",
      "22222222-2222-4222-8222-222222222222",
    ]);
    expect(items).toHaveLength(2);
    expect(items[0]?.status).toBe("cancelled");
    expect(items[1]?.status).toBe("pending");
    expect(typeof items[1]?.id).toBe("string");
    await vi.waitFor(() => {
      const secondCreateIndex = fetchMock.mock.calls.reduce(
        (latest, [input, init], index) =>
          init?.method === "POST" && String(input) === "/api/study/tasks"
            ? index
            : latest,
        -1,
      );
      expect(
        fetchMock.mock.calls
          .slice(secondCreateIndex + 1)
          .some(([, init]) => init?.method === "GET"),
      ).toBe(true);
    });
  });

  it("does not present a cancelled idempotent replay as a new task", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          return jsonResponse(task({ status: "cancelled" }));
        }
        return jsonResponse({ items: [], total: 0 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "No tasks in this view" });
    await openCreateForm(user);
    const title = screen.getByLabelText("Title");
    await user.type(title, "Practice recursion");
    await user.click(screen.getByRole("button", { name: "Save task" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "did not create a new pending task",
    );
    expect((title as HTMLInputElement).value).toBe("Practice recursion");
    expect(
      screen.queryByRole("heading", { name: "Practice recursion" }),
    ).toBeNull();
  });

  it("marks a task complete", async () => {
    let current = task();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST" && url.endsWith("/complete")) {
          current = task({
            status: "completed",
            completed_at: "2030-01-02T10:00:00+00:00",
          });
          return jsonResponse(current);
        }
        return jsonResponse({ items: [current], total: 1 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await user.click(
      await screen.findByRole("button", { name: "Mark complete" }),
    );
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/complete"),
        ),
      ).toBe(true),
    );
  });

  it("reopens a completed task", async () => {
    let current = task({
      status: "completed",
      completed_at: "2030-01-02T10:00:00+00:00",
    });
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST" && String(input).endsWith("/reopen")) {
          current = task();
          return jsonResponse(current);
        }
        return jsonResponse({ items: [current], total: 1 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await user.click(
      await screen.findByRole("button", { name: "Reopen task" }),
    );
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/reopen"),
        ),
      ).toBe(true),
    );
  });

  it("filters by task status", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ items: [], total: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "No tasks in this view" });
    await user.click(screen.getByRole("button", { name: "Completed" }));
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes("status=completed"),
        ),
      ).toBe(true),
    );
  });

  it("shows the loading state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    renderPage();
    expect(await screen.findByText("Loading your tasks...")).toBeTruthy();
  });

  it("shows a safe list error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: "tasks_unavailable",
              message: "Study Tasks are temporarily unavailable.",
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderPage();
    expect(
      await screen.findByRole("heading", {
        name: "Tasks could not be loaded",
      }),
    ).toBeTruthy();
    expect(
      screen.getByText("Study Tasks are temporarily unavailable."),
    ).toBeTruthy();
  });

  it("does not render public or internal IDs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ items: [task()], total: 1 })),
    );
    renderPage();
    await screen.findByText("Review database joins");
    expect(screen.queryByText("3557348663300104065")).toBeNull();
    expect(document.body.textContent).not.toContain("workspace_id");
    expect(document.body.textContent).not.toContain("version");
  });

  it("validates a whitespace-only title", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ items: [], total: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "No tasks in this view" });
    await openCreateForm(user);
    await user.type(screen.getByLabelText("Title"), "   ");
    await user.click(screen.getByRole("button", { name: "Save task" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Enter a task title.",
    );
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(false);
  });

  it("edits task fields", async () => {
    let current = task();
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          current = task({ title: "Review hash joins" });
          return jsonResponse(current);
        }
        return jsonResponse({ items: [current], total: 1 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    const card = (await screen.findByText("Review database joins")).closest(
      ".task-card",
    ) as HTMLElement | null;
    expect(card).toBeTruthy();
    await user.click(within(card!).getByRole("button", { name: "Edit task" }));
    const title = within(card!).getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "Review hash joins");
    await user.click(
      within(card!).getByRole("button", { name: "Save changes" }),
    );
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH"),
      ).toBe(true),
    );
  });
});
