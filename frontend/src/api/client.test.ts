import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiClient } from './client';

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

describe('apiClient', () => {
  beforeEach(() => {
    apiClient.invalidate();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('deduplicates concurrent GETs and serves the short cache', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ value: 7 }));
    vi.stubGlobal('fetch', fetchMock);

    const [first, second] = await Promise.all([
      apiClient.get<{ value: number }>('/api/test-dedupe'),
      apiClient.get<{ value: number }>('/api/test-dedupe'),
    ]);
    const cached = await apiClient.get<{ value: number }>('/api/test-dedupe');

    expect(first.value).toBe(7);
    expect(second).toEqual(first);
    expect(cached).toEqual(first);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('invalidates matching cache prefixes without clearing unrelated data', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      jsonResponse({ url: String(input) }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.get('/api/documents/1');
    await apiClient.get('/api/dashboard');
    apiClient.invalidate({ prefix: '/api/documents' });
    await apiClient.get('/api/documents/1');
    await apiClient.get('/api/dashboard');

    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('does not reuse a stale in-flight GET after matching invalidation', async () => {
    let resolveStale: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (fetchMock.mock.calls.length === 1) {
          return await new Promise<Response>((resolve, reject) => {
            resolveStale = resolve;
            init?.signal?.addEventListener(
              'abort',
              () => reject(new DOMException('Aborted', 'AbortError')),
              { once: true },
            );
          });
        }
        return jsonResponse({ items: [{ id: '1' }], total: 1 });
      },
    );
    vi.stubGlobal('fetch', fetchMock);

    const stale = apiClient
      .get<{ items: unknown[]; total: number }>('/api/documents')
      .catch((error: unknown) => error);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    apiClient.invalidate({ prefix: '/api/documents' });
    const fresh = apiClient.get<{ items: unknown[]; total: number }>(
      '/api/documents',
      { forceRefresh: true },
    );

    resolveStale?.(jsonResponse({ items: [], total: 0 }));

    await expect(fresh).resolves.toEqual({
      items: [{ id: '1' }],
      total: 1,
    });
    await expect(stale).resolves.toBeInstanceOf(DOMException);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('keeps the server error envelope on ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(
      {
        error: {
          code: 'summary_not_generated',
          message: 'Generate it first.',
          details: { kind: 'document' },
        },
      },
      { status: 404 },
    )));

    await expect(apiClient.get('/api/missing-summary')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'summary_not_generated',
      message: 'Generate it first.',
      details: { kind: 'document' },
    } satisfies Partial<ApiError>);
  });

  it('uploads files as multipart without setting a manual content type', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.body).toBeInstanceOf(FormData);
      expect(new Headers(init?.headers).has('Content-Type')).toBe(false);
      const form = init?.body as FormData;
      expect(form.get('notebook_id')).toBe('3');
      expect((form.get('file') as File).name).toBe('notes.txt');
      return jsonResponse({ status: 'indexed' });
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.upload(
      '/api/documents',
      new File(['study notes'], 'notes.txt', { type: 'text/plain' }),
      { fields: { notebook_id: 3 } },
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
