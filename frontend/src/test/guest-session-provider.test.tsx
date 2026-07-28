import { StrictMode } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api, apiClient, setGuestSessionToken } from '../api';
import { GuestSessionProvider, useGuestSession } from '../guest/GuestSessionProvider';
import { useApiQuery } from '../hooks';


const STORAGE_KEY = 'agentbook.guest-session.v1';
const TOKEN_A = 'session-a-test-credential';
const TOKEN_B = 'session-b-test-credential';
const NOW = '2026-07-27T12:00:00Z';

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function inspectResponse(name: string) {
  return {
    status: 'active',
    workspace: { name },
    created_at: NOW,
    last_seen_at: NOW,
    expires_at: null,
  };
}

function createResponse(token: string, name: string) {
  return {
    token,
    session: {
      status: 'active',
      created_at: NOW,
      last_seen_at: NOW,
      expires_at: null,
    },
    workspace: { name },
  };
}

function WorkspaceConsumer() {
  const guest = useGuestSession();
  const documents = useApiQuery(
    'workspace-documents',
    (signal) => api.listDocuments({}, { signal, cacheTtlMs: 0 }),
    { keepPreviousData: false },
  );
  return (
    <div>
      <span>Workspace {guest.session.workspace.name}</span>
      <span>Documents {documents.data?.total ?? 'loading'}</span>
      <button onClick={() => void guest.startNewStudySpace()}>
        Switch workspace
      </button>
    </div>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  setGuestSessionToken(null);
  apiClient.invalidate();
});

afterEach(() => {
  window.localStorage.clear();
  setGuestSessionToken(null);
  apiClient.invalidate();
  vi.unstubAllGlobals();
});

describe('GuestSessionProvider workspace boundary', () => {
  it('waits for restored-session hydration before user-data requests', async () => {
    let resolveInspect: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith('/api/guest-session')) {
          return await new Promise<Response>((resolve) => {
            resolveInspect = resolve;
          });
        }
        if (path.endsWith('/api/documents')) {
          return jsonResponse({ items: [{ id: '1' }], total: 1 });
        }
        throw new Error(`Unexpected request: ${path}`);
      },
    );
    vi.stubGlobal('fetch', fetchMock);
    window.localStorage.setItem(STORAGE_KEY, TOKEN_A);

    render(
      <StrictMode>
        <GuestSessionProvider>
          <WorkspaceConsumer />
        </GuestSessionProvider>
      </StrictMode>,
    );

    expect(await screen.findByText('Opening your study space')).toBeTruthy();
    expect(screen.queryByText(/Documents/)).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    resolveInspect?.(jsonResponse(inspectResponse('A')));
    expect(await screen.findByText('Documents 1')).toBeTruthy();

    const inspectHeaders = new Headers(fetchMock.mock.calls.at(0)?.[1]?.headers);
    const documentHeaders = new Headers(fetchMock.mock.calls.at(1)?.[1]?.headers);
    expect(inspectHeaders.get('Authorization')).toBe(`Bearer ${TOKEN_A}`);
    expect(documentHeaders.get('Authorization')).toBe(`Bearer ${TOKEN_A}`);
  });

  it('creates one session and reloads mounted queries for an intentional switch', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method ?? 'GET';
        const authorization = new Headers(init?.headers).get('Authorization');
        if (path.endsWith('/api/guest-session') && method === 'GET') {
          return jsonResponse(inspectResponse(
            authorization === `Bearer ${TOKEN_B}` ? 'B' : 'A',
          ));
        }
        if (path.endsWith('/api/guest-session') && method === 'POST') {
          return jsonResponse(createResponse(TOKEN_B, 'B'), { status: 201 });
        }
        if (path.endsWith('/api/documents')) {
          return jsonResponse(
            authorization === `Bearer ${TOKEN_B}`
              ? { items: [], total: 0 }
              : { items: [{ id: '1' }], total: 1 },
          );
        }
        throw new Error(`Unexpected request: ${method} ${path}`);
      },
    );
    vi.stubGlobal('fetch', fetchMock);
    window.localStorage.setItem(STORAGE_KEY, TOKEN_A);

    const user = userEvent.setup();
    render(
      <StrictMode>
        <GuestSessionProvider>
          <WorkspaceConsumer />
        </GuestSessionProvider>
      </StrictMode>,
    );

    expect(await screen.findByText('Documents 1')).toBeTruthy();
    await user.dblClick(screen.getByRole('button', { name: 'Switch workspace' }));

    expect(await screen.findByText('Workspace B')).toBeTruthy();
    expect(await screen.findByText('Documents 0')).toBeTruthy();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(TOKEN_B);

    const bootstrapCalls = fetchMock.mock.calls.filter(([input, init]) =>
      String(input).endsWith('/api/guest-session')
      && (init?.method ?? 'GET') === 'POST'
    );
    expect(bootstrapCalls).toHaveLength(1);
    const workspaceBRead = fetchMock.mock.calls.find(([input, init]) =>
      String(input).endsWith('/api/documents')
      && new Headers(init?.headers).get('Authorization') === `Bearer ${TOKEN_B}`
    );
    expect(workspaceBRead).toBeTruthy();
  });

  it('restores the same session after an application refresh', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith('/api/guest-session')) {
          return jsonResponse(inspectResponse('A'));
        }
        if (String(input).endsWith('/api/documents')) {
          return jsonResponse({ items: [{ id: '1' }], total: 1 });
        }
        throw new Error(`Unexpected request: ${String(input)}`);
      },
    );
    vi.stubGlobal('fetch', fetchMock);
    window.localStorage.setItem(STORAGE_KEY, TOKEN_A);

    const first = render(
      <GuestSessionProvider>
        <WorkspaceConsumer />
      </GuestSessionProvider>,
    );
    expect(await screen.findByText('Documents 1')).toBeTruthy();
    first.unmount();

    render(
      <GuestSessionProvider>
        <WorkspaceConsumer />
      </GuestSessionProvider>,
    );
    expect(await screen.findByText('Documents 1')).toBeTruthy();

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(TOKEN_A);
    expect(fetchMock.mock.calls.some(([, init]) =>
      (init?.method ?? 'GET') === 'POST'
    )).toBe(false);
    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get('Authorization')).toBe(
        `Bearer ${TOKEN_A}`,
      );
    }
  });

  it('synchronizes a workspace token changed by another browser tab', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const authorization = new Headers(init?.headers).get('Authorization');
        if (String(input).endsWith('/api/guest-session')) {
          return jsonResponse(inspectResponse(
            authorization === `Bearer ${TOKEN_B}` ? 'B' : 'A',
          ));
        }
        if (String(input).endsWith('/api/documents')) {
          return jsonResponse({
            items: authorization === `Bearer ${TOKEN_B}` ? [] : [{ id: '1' }],
            total: authorization === `Bearer ${TOKEN_B}` ? 0 : 1,
          });
        }
        throw new Error(`Unexpected request: ${String(input)}`);
      },
    );
    vi.stubGlobal('fetch', fetchMock);
    window.localStorage.setItem(STORAGE_KEY, TOKEN_A);

    render(
      <GuestSessionProvider>
        <WorkspaceConsumer />
      </GuestSessionProvider>,
    );
    expect(await screen.findByText('Documents 1')).toBeTruthy();

    window.localStorage.setItem(STORAGE_KEY, TOKEN_B);
    window.dispatchEvent(new StorageEvent('storage', {
      key: STORAGE_KEY,
      oldValue: TOKEN_A,
      newValue: TOKEN_B,
      storageArea: window.localStorage,
    }));

    expect(await screen.findByText('Workspace B')).toBeTruthy();
    expect(await screen.findByText('Documents 0')).toBeTruthy();
  });

  it('ignores a stale session inspection after a cross-tab switch', async () => {
    let resolveInspectA: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const authorization = new Headers(init?.headers).get('Authorization');
        if (
          String(input).endsWith('/api/guest-session')
          && authorization === `Bearer ${TOKEN_A}`
        ) {
          return await new Promise<Response>((resolve) => {
            resolveInspectA = resolve;
          });
        }
        if (String(input).endsWith('/api/guest-session')) {
          return jsonResponse(inspectResponse('B'));
        }
        if (String(input).endsWith('/api/documents')) {
          return jsonResponse({ items: [], total: 0 });
        }
        throw new Error(`Unexpected request: ${String(input)}`);
      },
    );
    vi.stubGlobal('fetch', fetchMock);
    window.localStorage.setItem(STORAGE_KEY, TOKEN_A);

    render(
      <GuestSessionProvider>
        <WorkspaceConsumer />
      </GuestSessionProvider>,
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    window.localStorage.setItem(STORAGE_KEY, TOKEN_B);
    window.dispatchEvent(new StorageEvent('storage', {
      key: STORAGE_KEY,
      oldValue: TOKEN_A,
      newValue: TOKEN_B,
      storageArea: window.localStorage,
    }));

    expect(await screen.findByText('Workspace B')).toBeTruthy();
    expect(await screen.findByText('Documents 0')).toBeTruthy();

    resolveInspectA?.(jsonResponse(inspectResponse('A')));
    await Promise.resolve();
    expect(screen.getByText('Workspace B')).toBeTruthy();
    expect(screen.getByText('Documents 0')).toBeTruthy();
  });
});
