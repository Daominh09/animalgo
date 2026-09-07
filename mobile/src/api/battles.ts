import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";
import { useAppStore } from "../store/useAppStore";

// Owner: Person C — Battle System
//
// Everything the battle screens fetch. Field names match the backend response exactly
// (backend/app/routers/battles.py), so a change on either side shows up as a type error
// here rather than as an undefined on a screen.

/** A capture as it appears in a battle. Deliberately narrower than the Collection's
 *  `Capture`: the backend does not send coordinates to a battle screen, because a card
 *  ends up in front of the other player. */
export interface BattleCapture {
  id: string;
  common_name: string | null;
  species_id: string | null;
  image_url: string;
  /** null when rarity could not be determined — "unknown", not "common". Such a capture
   *  fights with common's base power. */
  rarity_tier: string | null;
  /** "ferocity" | "guile" | "resilience", or null for an unidentified capture. Derived
   *  from the species name on the backend, never stored, and stable forever. */
  trait: string | null;
}

export interface BattleSide {
  user_id: string;
  display_name: string;
  /** Null for the opponent while the challenge is still pending — they have not picked. */
  capture: BattleCapture | null;
  /** Final power, and the die roll inside it. Both null until the battle resolves. */
  total: number | null;
  roll: number | null;
}

export type BattleStatus = "pending" | "resolving" | "resolved" | "declined" | "expired";

export interface Battle {
  id: string;
  status: BattleStatus;
  /** Which side of this battle YOU are. The backend works it out so a screen can say
   *  "you" without re-deriving it from ids. */
  role: "challenger" | "opponent";
  /** Your result, not the challenger's. Null unless the battle resolved. */
  outcome: "won" | "lost" | null;
  created_at: string;
  resolved_at: string | null;
  /** Only set while pending; null once the battle is decided. */
  expires_at: string | null;
  challenger: BattleSide;
  opponent: BattleSide;
  winner_id: string | null;
  trait_advantage: "challenger" | "opponent" | null;
  /** Coins the WINNER earned. Null on an unresolved battle — and also null if the payout
   *  itself failed, which is reported honestly rather than displayed as paid. */
  coins_awarded: number | null;
}

export interface Opponent {
  user_id: string;
  display_name: string;
  capture_count: number;
}

/** Keyed on the user rather than the token, for the same reason useCollection is: the
 *  token is replaced hourly by the background refresh, and keying on it would drop every
 *  battle screen to a spinner once an hour for no reason. */
function useAuth() {
  const accessToken = useAppStore((s) => s.accessToken);
  const userId = useAppStore((s) => s.userId);
  return { accessToken, userId, enabled: Boolean(accessToken && userId) };
}

/** Every battle you are in, newest first — incoming, outgoing and finished together. */
export function useBattles() {
  const { accessToken, userId, enabled } = useAuth();

  return useQuery<Battle[]>({
    queryKey: ["battles", userId],
    queryFn: () => apiFetch("/battles", {}, accessToken ?? undefined),
    enabled,
    // Battles are asynchronous and the other player acts while you are looking at the
    // list, so this is one of the few screens where polling earns its keep. Push
    // notifications cover the app being backgrounded; this covers it being open.
    refetchInterval: 20_000,
  });
}

export function useBattle(battleId: string | undefined) {
  const { accessToken, userId, enabled } = useAuth();

  return useQuery<Battle>({
    queryKey: ["battle", userId, battleId],
    queryFn: () => apiFetch(`/battles/${battleId}`, {}, accessToken ?? undefined),
    enabled: enabled && Boolean(battleId),
  });
}

/** Your captures, as battle cards. Every capture is eligible, including ones whose
 *  rarity never resolved. */
export function useRoster() {
  const { accessToken, userId, enabled } = useAuth();

  return useQuery<BattleCapture[]>({
    queryKey: ["battle-roster", userId],
    queryFn: () => apiFetch("/battles/roster", {}, accessToken ?? undefined),
    enabled,
  });
}

/** Players you can challenge: anyone else holding at least one capture. */
export function useOpponents() {
  const { accessToken, userId, enabled } = useAuth();

  return useQuery<Opponent[]>({
    queryKey: ["battle-opponents", userId],
    queryFn: () => apiFetch("/battles/opponents", {}, accessToken ?? undefined),
    enabled,
  });
}

/** Invalidates everything a resolved or created battle can change.
 *
 * The wallet is in here because winning pays coins, and the collection is not: battles
 * never alter what you own. */
function useBattleInvalidation() {
  const queryClient = useQueryClient();
  const userId = useAppStore((s) => s.userId);

  return () => {
    queryClient.invalidateQueries({ queryKey: ["battles", userId] });
    queryClient.invalidateQueries({ queryKey: ["battle", userId] });
    queryClient.invalidateQueries({ queryKey: ["wallet", userId] });
  };
}

export function useChallenge() {
  const { accessToken } = useAuth();
  const invalidate = useBattleInvalidation();

  return useMutation<Battle, Error, { opponentId: string; captureId: string }>({
    mutationFn: ({ opponentId, captureId }) =>
      apiFetch(
        "/battles/challenge",
        { method: "POST", body: JSON.stringify({ opponent_id: opponentId, capture_id: captureId }) },
        accessToken ?? undefined,
      ),
    onSuccess: invalidate,
  });
}

export function useAcceptBattle() {
  const { accessToken } = useAuth();
  const invalidate = useBattleInvalidation();

  return useMutation<Battle, Error, { battleId: string; captureId: string }>({
    mutationFn: ({ battleId, captureId }) =>
      apiFetch(
        `/battles/${battleId}/accept`,
        { method: "POST", body: JSON.stringify({ capture_id: captureId }) },
        accessToken ?? undefined,
      ),
    onSuccess: invalidate,
  });
}

export function useDeclineBattle() {
  const { accessToken } = useAuth();
  const invalidate = useBattleInvalidation();

  return useMutation<Battle, Error, { battleId: string }>({
    mutationFn: ({ battleId }) =>
      apiFetch(`/battles/${battleId}/decline`, { method: "POST" }, accessToken ?? undefined),
    onSuccess: invalidate,
  });
}
