import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";
import { MOCK_CAPTURES } from "./mockCaptures";
import { useAppStore } from "../store/useAppStore";

// Owner: Person B — Rarity Engine & Collection
// GET /collection, shared by the Collection grid and the Map pins so both screens show
// the same set of captures and a single fetch serves both.

/** One row from GET /collection. Field names match the backend response exactly. */
export interface Capture {
  id: string;
  /** Scientific name. The backend has no common name on the capture row yet —
   *  Person A to add it with the Capture write, so cards can read "House Sparrow". */
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
 * Falls back to mock captures when nobody is signed in. Person D's sign-in flow is what
 * sets the token, and until it exists a real request could only 401 -- so the screens
 * would have nothing to render and no way to be worked on. `isMock` is returned rather
 * than hidden, so the UI can say so; silently showing fake data as real is how a broken
 * fetch ends up looking like an empty collection.
 */
export function useCollection() {
  const accessToken = useAppStore((s) => s.accessToken);

  const query = useQuery<Capture[]>({
    // The token is part of the key so switching accounts doesn't serve the previous
    // player's captures out of the cache.
    queryKey: ["collection", accessToken],
    queryFn: () => apiFetch("/collection", {}, accessToken ?? undefined),
    enabled: Boolean(accessToken),
  });

  if (!accessToken) {
    return {
      ...query,
      data: MOCK_CAPTURES,
      isPending: false,
      isError: false,
      isMock: true,
      signedOut: true,
    };
  }
  return { ...query, isMock: false, signedOut: false };
}
