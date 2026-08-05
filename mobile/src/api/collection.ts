import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";
import { useAppStore } from "../store/useAppStore";

// Owner: Person B — Rarity Engine & Collection
// GET /collection, shared by the Collection grid and the Map pins so both screens show
// the same set of captures and a single fetch serves both.

/** One row from GET /collection. Field names match the backend response exactly. */
export interface Capture {
  id: string;
  /** What the player is shown — "House Sparrow". Null for captures identified only to a
   *  family, and for rows written before the column existed; callers fall back to
   *  species_id via displayName(). */
  common_name: string | null;
  /** Scientific name — "Passer domesticus". Kept for the lookups the rarity engine did,
   *  but not what a player wants to read on a card. */
  species_id: string | null;
  image_url: string;
  /** null when rarity could not be determined. Not the same as "common". */
  rarity_tier: string | null;
  /** Already fuzzed to a ~11 km grid by the backend; null when no location was sent. */
  lat: number | null;
  lng: number | null;
  confidence_score: number | null;
  confirmed_by_user: boolean;
  captured_at: string;
}

/** The player's captures, rarest first.
 *
 * The token is only ever absent for the moment between app start and the session being
 * read, because the root layout redirects anyone without one to the sign-in screen.
 */
export function useCollection() {
  const accessToken = useAppStore((s) => s.accessToken);
  const userId = useAppStore((s) => s.userId);

  return useQuery<Capture[]>({
    // Keyed on the user, NOT the token. Both keep one player's captures out of another's
    // cache, but the token is replaced every hour by the background refresh — so keying
    // on it minted a new cache entry hourly, dropping the Collection grid to a spinner
    // and emptying the Map's pins for no reason. The user id only changes when the
    // player actually does.
    queryKey: ["collection", userId],
    queryFn: () => apiFetch("/collection", {}, accessToken ?? undefined),
    enabled: Boolean(accessToken && userId),
  });
}
