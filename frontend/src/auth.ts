const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL ?? "").replace(/\/+$/, "");
const SUPABASE_PUBLISHABLE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? "";
const SESSION_KEY = "researchpilot.supabase.session";

type AuthUser = { id: string; email?: string };
export type AuthSession = {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: AuthUser;
};
type AuthPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_at?: number;
  expires_in?: number;
  user?: AuthUser;
  msg?: string;
  message?: string;
  error_description?: string;
  error?: string;
};

export function isAuthConfigured(): boolean {
  if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) return false;
  try {
    const url = new URL(SUPABASE_URL);
    return (url.protocol === "https:" || url.hostname === "localhost" || url.hostname === "127.0.0.1")
      && !url.username && !url.password && !url.search && !url.hash;
  } catch {
    return false;
  }
}

function readStoredSession(): AuthSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.access_token || !parsed.refresh_token || !Number.isFinite(parsed.expires_at) || !parsed.user?.id) {
      sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return parsed;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

function saveSession(payload: AuthPayload): AuthSession | null {
  if (!payload.access_token || !payload.refresh_token || !payload.user?.id) return null;
  const session: AuthSession = {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    expires_at: payload.expires_at ?? Math.floor(Date.now() / 1000) + (payload.expires_in ?? 3600),
    user: payload.user,
  };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

async function authRequest(path: string, body?: Record<string, string>, accessToken?: string): Promise<AuthPayload> {
  if (!isAuthConfigured()) throw new Error("Supabase Auth is not configured.");
  const headers: Record<string, string> = {
    apikey: SUPABASE_PUBLISHABLE_KEY,
    "Content-Type": "application/json",
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
    method: "POST",
    headers,
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const payload = await response.json().catch(() => ({})) as AuthPayload;
  if (!response.ok) {
    const message = payload.msg ?? payload.message ?? payload.error_description ?? payload.error;
    throw new Error(message || "Supabase Auth request failed.");
  }
  return payload;
}

export async function signIn(email: string, password: string): Promise<AuthSession> {
  const payload = await authRequest("token?grant_type=password", { email, password });
  const session = saveSession(payload);
  if (!session) throw new Error("Sign-in succeeded without a session. Check your email confirmation settings.");
  return session;
}

export async function signUp(email: string, password: string): Promise<AuthSession | null> {
  const payload = await authRequest("signup", { email, password });
  return saveSession(payload);
}

async function refreshSession(current: AuthSession): Promise<AuthSession | null> {
  try {
    const payload = await authRequest("token?grant_type=refresh_token", { refresh_token: current.refresh_token });
    return saveSession(payload);
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export async function restoreSession(): Promise<AuthSession | null> {
  const current = readStoredSession();
  if (!current) return null;
  if (current.expires_at <= Math.floor(Date.now() / 1000) + 60) return refreshSession(current);
  return current;
}

export async function getValidAccessToken(): Promise<string | null> {
  const session = await restoreSession();
  return session?.access_token ?? null;
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const token = await getValidAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

export async function signOut(): Promise<void> {
  const current = readStoredSession();
  try {
    if (current?.access_token && isAuthConfigured()) {
      await authRequest("logout", undefined, current.access_token);
    }
  } catch {
    // Clear the local session even when the provider is temporarily unreachable.
  } finally {
    sessionStorage.removeItem(SESSION_KEY);
  }
}
