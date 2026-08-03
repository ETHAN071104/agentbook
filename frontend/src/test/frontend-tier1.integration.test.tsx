import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { apiClient } from "../api/client";
import { AppShell } from "../layouts/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { NotebooksPage } from "../pages/NotebooksPage";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

const emptyDashboard = {
  counts: {
    documents: 0,
    notebooks: 0,
    unsorted_documents: 0,
    active_memories: 12,
    archived_memories: 0,
    study_sessions: 0,
    completed_sessions: 0,
    interactions: 0,
    quiz_attempts: 0,
    topics: 0,
  },
  active_session: null,
  recent_sessions: [],
  outcomes: { understood: 0, partial: 0, confused: 0, unrated: 0 },
  quiz: {
    total: 0,
    completed: 0,
    aborted: 0,
    average_score_percentage: null,
    average_accuracy_percentage: null,
  },
  recent_quizzes: [],
};

const emptyLibrary = {
  items: [],
  total: 0,
  unsorted: {
    id: null,
    name: "Unsorted Documents",
    description: "Material without a notebook.",
    document_count: 0,
    created_at: null,
    updated_at: null,
    is_virtual: true,
  },
};

function renderHome(fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetchMock);
  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe("Tier 1 navigation", () => {
  beforeEach(() => {
    apiClient.invalidate();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-reduced-motion: reduce"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows exactly five accessible desktop and mobile destinations", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/tasks"]}>
        <AppShell>
          <h1>Tasks route</h1>
        </AppShell>
      </MemoryRouter>,
    );

    const desktopNav = document.querySelector(
      ".app-sidebar nav",
    ) as HTMLElement;
    const desktopLinks = within(desktopNav).getAllByRole("link");
    expect(desktopLinks.map((link) => link.textContent?.trim())).toEqual([
      "Home",
      "Library",
      "Practice",
      "Ask Agentbook",
      "Tasks",
    ]);
    expect(
      within(desktopNav).getByRole("link", { name: "Tasks" }).classList,
    ).toContain("is-active");

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const drawer = screen.getByRole("dialog");
    const mobileLinks = within(drawer).getAllByRole("link");
    expect(mobileLinks.map((link) => link.textContent?.trim())).toEqual([
      "Home",
      "Library",
      "Practice",
      "Ask Agentbook",
      "Tasks",
    ]);
    mobileLinks[0]?.focus();
    expect(document.activeElement).toBe(mobileLinks[0]);
  });

  it("keeps hidden compatibility routes registered", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    for (const path of [
      "/chat",
      "/progress",
      "/memory",
      "/system",
      "/topics/topic-1",
    ]) {
      const view = render(
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>,
      );
      expect(
        screen.queryByRole("heading", { name: "Page not found" }),
      ).toBeNull();
      view.unmount();
    }
  });
});

describe("Tier 1 Home priorities", () => {
  beforeEach(() => apiClient.invalidate());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders one upload-first onboarding state without internal metrics", async () => {
    renderHome(
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/dashboard")) return jsonResponse(emptyDashboard);
        if (url.includes("/api/study/tasks")) {
          return jsonResponse({ items: [], total: 0 });
        }
        return jsonResponse({ items: [], total: 0 });
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Add your first study material",
      }),
    ).toBeTruthy();
    expect(
      screen.getAllByRole("link", { name: "Upload study material" }),
    ).toHaveLength(1);
    expect(document.body.textContent).not.toContain("Active memories");
    expect(screen.getByRole("link", { name: "View learning history" })).toBeTruthy();
  });

  it("prioritizes active work over pending tasks and review", async () => {
    renderHome(
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/dashboard")) {
          return jsonResponse({
            ...emptyDashboard,
            counts: { ...emptyDashboard.counts, documents: 1 },
            active_session: {
              id: "9007199254740993",
              status: "active",
              started_at: "2030-01-01T10:00:00Z",
              ended_at: null,
              interaction_count: 2,
            },
          });
        }
        if (url.includes("/api/study/tasks")) {
          return jsonResponse({
            items: [
              {
                id: "9007199254740994",
                title: "Review joins",
                description: "",
                topic: "SQL",
                status: "pending",
                priority: "normal",
                due_at: "2030-01-02T10:00:00Z",
                completed_at: null,
                archived_at: null,
                created_at: "2030-01-01T10:00:00Z",
                updated_at: "2030-01-01T10:00:00Z",
              },
            ],
            total: 1,
          });
        }
        return jsonResponse({
          items: [
            {
              interaction_id: "9007199254740995",
              question: "Explain joins",
            },
          ],
          total: 1,
        });
      }),
    );

    expect(
      await screen.findByRole("link", { name: /Continue session/ }),
    ).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Open task" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Start review" })).toBeNull();
  });

  it("uses a pending task before the weak-area fallback", async () => {
    renderHome(
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/dashboard")) {
          return jsonResponse({
            ...emptyDashboard,
            counts: { ...emptyDashboard.counts, documents: 1 },
          });
        }
        if (url.includes("/api/study/tasks")) {
          return jsonResponse({
            items: [
              {
                id: "9007199254740994",
                title: "Review joins",
                description: "",
                topic: "SQL",
                status: "pending",
                priority: "normal",
                due_at: null,
                completed_at: null,
                archived_at: null,
                created_at: "2030-01-01T10:00:00Z",
                updated_at: "2030-01-01T10:00:00Z",
              },
            ],
            total: 1,
          });
        }
        return jsonResponse({
          items: [
            {
              interaction_id: "9007199254740995",
              question: "Explain joins",
            },
          ],
          total: 1,
        });
      }),
    );

    expect(await screen.findByText("Review joins")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open task" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Start review" })).toBeNull();
  });

  it("opens Review for the weak-area fallback", async () => {
    renderHome(
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/dashboard")) {
          return jsonResponse({
            ...emptyDashboard,
            counts: { ...emptyDashboard.counts, documents: 1 },
          });
        }
        if (url.includes("/api/study/tasks")) {
          return jsonResponse({ items: [], total: 0 });
        }
        return jsonResponse({
          items: [
            {
              interaction_id: "9007199254740995",
              question: "Explain joins",
            },
          ],
          total: 1,
        });
      }),
    );

    const action = await screen.findByRole("link", { name: "Start review" });
    expect(action.getAttribute("href")).toBe("/study-actions?view=review");
  });
});

describe("Tier 1 Library", () => {
  beforeEach(() => apiClient.invalidate());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("makes upload primary, notebook creation secondary, and presents one search", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).includes("/api/documents")
          ? jsonResponse({ items: [], total: 0 })
          : jsonResponse(emptyLibrary),
      ),
    );
    render(
      <MemoryRouter>
        <NotebooksPage />
      </MemoryRouter>,
    );

    const upload = await screen.findByRole("link", {
      name: "Upload study material",
    });
    const notebook = screen.getByRole("button", { name: "New notebook" });
    expect(upload.classList).toContain("button--primary");
    expect(notebook.classList).toContain("button--secondary");
    expect(screen.getAllByRole("search")).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(
      /\b(indexed|chunk|mime|provider|embedding|vector)\b/i,
    );
  });

  it("offers Ask and Practice after a successful upload", async () => {
    const uploaded = {
      id: "9007199254740996",
      filename: "plants.pdf",
      mime_type: "application/pdf",
      chunk_count: 4,
      created_at: "2030-01-01T10:00:00Z",
      updated_at: "2030-01-01T10:00:00Z",
      notebook_id: null,
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          return jsonResponse(
            { status: "indexed", duplicate: false, document: uploaded },
            { status: 201 },
          );
        }
        return String(input).includes("/api/documents")
          ? jsonResponse({ items: [], total: 0 })
          : jsonResponse(emptyLibrary);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <NotebooksPage />
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole("link", { name: "Upload study material" }),
    );
    const uploadDialog = screen.getByRole("dialog", {
      name: "Upload study material",
    });
    const fileInput = within(uploadDialog).getByLabelText("Study material file");
    await user.upload(
      fileInput,
      new File(["plant notes"], "plants.pdf", { type: "application/pdf" }),
    );
    const uploadButton = within(uploadDialog).getByRole("button", {
      name: "Upload study material",
    }) as HTMLButtonElement;
    await vi.waitFor(() => expect(uploadButton.disabled).toBe(false));
    fireEvent.submit(uploadButton.closest("form")!);
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
      ).toBe(true),
    );

    expect(
      await screen.findByRole("link", { name: "Ask about this" }),
    ).toBeTruthy();
    const practice = screen.getByRole("link", { name: "Practice this" });
    expect(practice.getAttribute("href")).toContain("view=quiz");
    expect(practice.getAttribute("href")).toContain(
      "document_ids=9007199254740996",
    );
  });
});
