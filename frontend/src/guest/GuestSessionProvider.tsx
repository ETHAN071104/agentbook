import {
  createContext,
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { BookOpenText, RefreshCw, ShieldCheck } from 'lucide-react';

import {
  ApiError,
  guestSessionApi,
  setGuestSessionToken,
  toApiError,
} from '../api';
import type { GuestSessionInspectResponse } from '../api';
import { Button, Card, Notice } from '../components';

const STORAGE_KEY = 'agentbook.guest-session.v1';

interface GuestSessionContextValue {
  session: GuestSessionInspectResponse;
  startNewStudySpace: () => Promise<void>;
  startingNew: boolean;
}

const GuestSessionContext = createContext<GuestSessionContextValue | null>(null);

function readStoredToken(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function rememberToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEY, token);
}

function forgetToken(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } finally {
    setGuestSessionToken(null);
  }
}

function creationKey(): string {
  if (typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
}

export function GuestSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<
    'checking' | 'welcome' | 'active' | 'unavailable'
  >('checking');
  const [session, setSession] = useState<GuestSessionInspectResponse | null>(null);
  const [message, setMessage] = useState('');
  const [working, setWorking] = useState(false);
  const [sessionEpoch, setSessionEpoch] = useState(0);
  const activeTokenRef = useRef<string | null>(null);
  const creationRef = useRef<Promise<void> | null>(null);

  const activateSession = useCallback((
    token: string,
    nextSession: GuestSessionInspectResponse,
  ) => {
    setGuestSessionToken(token);
    setSession(nextSession);
    if (activeTokenRef.current !== token) {
      activeTokenRef.current = token;
      setSessionEpoch((value) => value + 1);
    }
    setMessage('');
    setState('active');
  }, []);

  const inspectStoredSession = useCallback(async () => {
    const stored = readStoredToken();
    if (!stored) {
      setGuestSessionToken(null);
      activeTokenRef.current = null;
      setSession(null);
      setState('welcome');
      return;
    }
    setGuestSessionToken(stored);
    setState('checking');
    try {
      const inspected = await guestSessionApi.inspect();
      if (readStoredToken() !== stored) return;
      activateSession(stored, inspected);
    } catch (error) {
      if (readStoredToken() !== stored) return;
      const apiError = toApiError(error);
      if (
        apiError instanceof ApiError
        && apiError.status === 401
        && [
          'GUEST_SESSION_INVALID',
          'GUEST_SESSION_EXPIRED',
          'GUEST_SESSION_REVOKED',
        ].includes(apiError.code)
      ) {
        forgetToken();
        activeTokenRef.current = null;
        setSession(null);
        setMessage('Your previous private study space is no longer available.');
        setState('welcome');
        return;
      }
      setMessage(apiError.reason);
      setState('unavailable');
    }
  }, [activateSession]);

  useEffect(() => {
    void inspectStoredSession();
  }, [inspectStoredSession]);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (
        event.storageArea === window.localStorage
        && event.key === STORAGE_KEY
      ) {
        void inspectStoredSession();
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [inspectStoredSession]);

  const createSession = useCallback((): Promise<void> => {
    if (creationRef.current) return creationRef.current;

    const request = (async () => {
      setWorking(true);
      setMessage('');
      try {
        const created = await guestSessionApi.create(creationKey());
        rememberToken(created.token);
        activateSession(created.token, {
          status: created.session.status,
          workspace: created.workspace,
          created_at: created.session.created_at,
          last_seen_at: created.session.last_seen_at,
          expires_at: created.session.expires_at,
        });
      } catch (error) {
        setMessage(toApiError(error).reason);
        setState(readStoredToken() ? 'unavailable' : 'welcome');
        throw error;
      } finally {
        setWorking(false);
      }
    })();
    creationRef.current = request;
    void request.finally(() => {
      if (creationRef.current === request) creationRef.current = null;
    }).catch(() => undefined);
    return request;
  }, [activateSession]);

  const startNewStudySpace = useCallback(async () => {
    await createSession();
  }, [createSession]);

  const contextValue = useMemo(
    () => session ? {
      session,
      startNewStudySpace,
      startingNew: working,
    } : null,
    [session, startNewStudySpace, working],
  );

  if (state === 'checking') {
    return (
      <main className="guest-gate">
        <Card className="guest-gate__card">
          <span className="guest-gate__icon" aria-hidden="true">
            <BookOpenText size={28} />
          </span>
          <h1>Opening your study space</h1>
          <p>Your private browser session is being checked.</p>
        </Card>
      </main>
    );
  }

  if (state === 'unavailable') {
    return (
      <main className="guest-gate">
        <Card className="guest-gate__card">
          <h1>Agentbook is temporarily unavailable</h1>
          <Notice tone="error">{message}</Notice>
          <Button
            icon={<RefreshCw size={18} aria-hidden="true" />}
            onClick={() => void inspectStoredSession()}
          >
            Try again
          </Button>
          <p className="supporting-text">
            Your saved session was kept in this browser.
          </p>
        </Card>
      </main>
    );
  }

  if (state === 'welcome' || !contextValue) {
    return (
      <main className="guest-gate">
        <Card className="guest-gate__card">
          <span className="guest-gate__icon" aria-hidden="true">
            <ShieldCheck size={28} />
          </span>
          <p className="eyebrow">Private guest study space</p>
          <h1>Continue with your own study space</h1>
          <p>
            Agentbook keeps this study space private in your browser. Keep this
            browser data if you want to return to the same study materials.
          </p>
          {message ? <Notice tone="warning">{message}</Notice> : null}
          <Button
            loading={working}
            loadingText="Creating study space…"
            onClick={() => void createSession().catch(() => undefined)}
          >
            Continue as Guest
          </Button>
        </Card>
      </main>
    );
  }

  return (
    <GuestSessionContext.Provider value={contextValue}>
      <Fragment key={sessionEpoch}>{children}</Fragment>
    </GuestSessionContext.Provider>
  );
}

export function useGuestSession(): GuestSessionContextValue {
  const value = useContext(GuestSessionContext);
  if (!value) {
    throw new Error('Guest session context is unavailable.');
  }
  return value;
}

export function useOptionalGuestSession(): GuestSessionContextValue | null {
  return useContext(GuestSessionContext);
}
