import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { App } from "../App";
import { apiClient } from "../api/client";

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
    active_memories: 0,
    archived_memories: 0,
    study_sessions: 0,
    completed_sessions: 0,
    interactions: 0,
    quiz_attempts: 0,
    topics: 0,
  },
  active_session: null,
  recent_sessions: [],
  outcomes: {
    understood: 0,
    partial: 0,
    confused: 0,
    unrated: 0,
  },
  quiz: {
    total: 0,
    completed: 0,
    aborted: 0,
    average_score_percentage: null,
    average_accuracy_percentage: null,
  },
  recent_quizzes: [],
};

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches:
        query.includes("prefers-reduced-motion: reduce") &&
        !query.includes("no-preference"),
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

describe("App routing and request states", () => {
  beforeEach(() => apiClient.invalidate());

  afterEach(() => vi.unstubAllGlobals());

  it("routes unknown paths to the local-safe not-found view", async () => {
    render(
      <MemoryRouter initialEntries={["/does-not-exist"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Page not found" }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go Home" })).toBeTruthy();
  });

  it("shows a dashboard loading state while its GET remains pending", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    render(
      <MemoryRouter initialEntries={["/app"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Preparing your Home page/),
    ).toBeTruthy();
  });

  it("shows a structured dashboard failure with a retry action", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: "dashboard_unavailable",
              message: "Local dashboard could not be read.",
            },
          },
          { status: 503 },
        ),
      ),
    );

    render(
      <MemoryRouter initialEntries={["/app"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Home is unavailable" }),
    ).toBeTruthy();
    expect(screen.getByText("Local dashboard could not be read.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("renders useful empty states for a valid new workspace", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(emptyDashboard)));

    render(
      <MemoryRouter initialEntries={["/app"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Home" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "What you are learning" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Add your first study material" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Upload study material" }),
    ).toBeTruthy();
    expect(screen.queryByText(/Active memories/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /chat/i })).toBeNull();
  });
});

