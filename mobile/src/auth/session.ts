import AsyncStorage from "@react-native-async-storage/async-storage";

import { apiFetch } from "../api/client";

// Owner: Person B — session handling against our own /auth endpoints.
//
// The app no longer talks to Supabase directly; it calls the backend, which owns the
// auth rules. That means the token lifecycle is ours to run too — there is no
// supabase-js quietly refreshing in the background any more.
//
// AsyncStorage rather than expo-secure-store: SecureStore has no web implementation and
// caps values at 2048 bytes, which a pair of JWTs can exceed. On web AsyncStorage is
// localStorage, which is where a browser session belongs.

const STORAGE_KEY = "animalgo.session";

/** Refresh this far before expiry, so a request never leaves with a token that expires
 *  mid-flight on a slow connection. */
const REFRESH_MARGIN_MS = 60_000;

export interface Session {
  access_token: string;
  refresh_token: string;
  user_id: string | null;
  /** Absolute epoch ms. Stored rather than the API's relative expires_in, because a
   *  duration is meaningless after the app has been closed for a day. */
  expires_at: number;
}

interface SessionResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user_id: string | null;
}

function toSession(r: SessionResponse): Session {
  return {
    access_token: r.access_token,
    refresh_token: r.refresh_token,
    user_id: r.user_id,
    expires_at: Date.now() + r.expires_in * 1000,
  };
}

export async function save(session: Session): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export async function clear(): Promise<void> {
  await AsyncStorage.removeItem(STORAGE_KEY);
}

export async function load(): Promise<Session | null> {
  const raw = await AsyncStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    // Corrupt or from an older shape. Treat as signed out rather than crashing at
    // startup on something the player cannot fix.
    await clear();
    return null;
  }
}

export function isExpiring(session: Session): boolean {
  return Date.now() >= session.expires_at - REFRESH_MARGIN_MS;
}

export async function signIn(email: string, password: string): Promise<Session> {
  const session = toSession(
    await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  );
  await save(session);
  return session;
}

/** Creates the account. Returns null when the project requires email confirmation, in
 *  which case there is no session yet and the player must confirm first. */
export async function register(email: string, password: string): Promise<Session | null> {
  const body = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (body.confirmation_required) return null;
  const session = toSession(body);
  await save(session);
  return session;
}

/** True when the server actively rejected the refresh token, as opposed to the request
 *  never getting an answer. apiFetch throws "API error <status>: <body>". */
function wasRejected(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /API error 4\d\d/.test(message);
}

/**
 * Trades the refresh token for a new session.
 *
 * Returns null only when the server says the token is no longer valid — that genuinely
 * means signing in again. A network failure keeps the stored session and returns it
 * unchanged: the refresh runs hourly in the background, so treating an offline moment
 * as a rejection would sign players out for going through a tunnel, and would throw away
 * a refresh token that was still perfectly good.
 */
export async function refresh(session: Session): Promise<Session | null> {
  try {
    const next = toSession(
      await apiFetch("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: session.refresh_token }),
      }),
    );
    await save(next);
    return next;
  } catch (error) {
    if (wasRejected(error)) {
      await clear();
      return null;
    }
    // Couldn't reach the server. Keep what we have and let the next attempt try again.
    return session;
  }
}
