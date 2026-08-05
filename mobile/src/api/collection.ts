import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";
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

/** The player's captures, rarest first. Disabled until there is a token to send. */
export function useCollection() {
  const accessToken = useAppStore((s) => s.accessToken);

  const query = useQuery<Capture[]>({
    // The token is part of the key so switching accounts doesn't serve the previous
    // player's captures out of the cache.
    queryKey: ["collection", accessToken],
    queryFn: () => apiFetch("/collection", {}, accessToken ?? undefined),
    enabled: Boolean(accessToken),
  });

  return { ...query, signedOut: !accessToken };
}
