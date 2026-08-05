import { useEffect, useState } from "react";

import * as session from "./session";
import { useAppStore } from "../store/useAppStore";

// Owner: Person B — Rarity Engine & Collection (auth built ahead of Person D's slot)
//
// Owns the session lifecycle now that the app signs in through our API rather than
// through supabase-js. Nothing refreshes tokens in the background for us any more, so
// this schedules it.
//
// The timer and the actions are module-level, not hook state, deliberately. A hook
// holding them would give every component that called it its own copy: the sign-in
// screen and the root layout would each load the session and each arm a refresh timer,
// and the timers would multiply with every mount. There is one session, so there is one
// timer.

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/** Publishes a session (or the absence of one) to the store and arms the next refresh. */
function apply(next: session.Session | null): void {
  const { setAccessToken, setUser } = useAppStore.getState();
  setAccessToken(next?.access_token ?? null);
  setUser(next?.user_id ?? null);

  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = null;
  if (!next) return;

  // Refresh shortly before expiry rather than waiting for a request to fail. Clamped to
  // a positive delay: an already-expired session would otherwise schedule in the past
  // and fire immediately, over and over.
  const delay = Math.max(1_000, next.expires_at - Date.now() - 60_000);
  refreshTimer = setTimeout(async () => {
    apply(await session.refresh(next));
  }, delay);
}

/** Restores the stored session at startup, refreshing it first if it went stale while
 *  the app was closed. */
async function bootstrap(): Promise<void> {
  const stored = await session.load();
  const usable = stored && session.isExpiring(stored) ? await session.refresh(stored) : stored;
  apply(usable);
}

export async function signIn(email: string, password: string): Promise<void> {
  apply(await session.signIn(email, password));
}

/** Returns false when the project requires email confirmation — the account exists but
 *  there is no session yet, and the caller has to say so. */
export async function register(email: string, password: string): Promise<boolean> {
  const next = await session.register(email, password);
  apply(next);
  return next !== null;
}

export async function signOut(): Promise<void> {
  await session.clear();
  apply(null);
}

/**
 * Session state for the root layout's guard. Call once, at the root.
 *
 * `loading` stays true until the stored session has been read and, if needed, refreshed
 * — without it a returning player is briefly treated as signed out and bounced to the
 * sign-in screen.
 */
export function useSession() {
  const accessToken = useAppStore((s) => s.accessToken);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    bootstrap().finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  return { loading, signedIn: Boolean(accessToken) };
}

/** Turns an API error into something worth showing a player. */
export function authErrorMessage(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  if (raw.includes("Invalid login credentials")) return "That email and password don't match an account.";
  if (raw.includes("Email not confirmed")) return "Check your inbox and confirm your email first.";
  if (raw.includes("already registered")) return "That email already has an account — try signing in.";
  if (raw.includes("Too many sign-in attempts") || raw.includes("API error 429"))
    return "Too many attempts. Wait 15 minutes and try again.";
  if (raw.includes("Could not reach") || raw.includes("Network request failed"))
    return "Can't reach the server. Check your connection.";
  // apiFetch prefixes "API error <status>: <body>"; the detail is the useful half.
  const detail = raw.match(/"detail":"([^"]+)"/);
  return detail ? detail[1] : raw;
}
