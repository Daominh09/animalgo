import type { Capture } from "./api/collection";
import { rarityMeta } from "./rarity";

// Owner: Person B — Rarity Engine & Collection
// Shared capture helpers. Pure functions, kept out of the screens so the Collection grid
// and the Map agree by construction rather than by both being written carefully.

/** Columns in the Collection grid. Shared because `rowIndexFor` has to agree with what
 *  the FlatList was actually given — a mismatch is a crash, not a layout glitch. */
export const GRID_COLUMNS = 2;

/**
 * What to print on a card.
 *
 * Common name first: a player wants "House Sparrow", not "Passer domesticus". The
 * scientific name is what the rarity engine needed, not what anyone wants to read.
 *
 * Falls back to it anyway, because some captures genuinely have no common name — vision
 * sometimes identifies only a family ("Troglodytidae"), and rows written before the
 * column existed have none. A wrong-looking name beats a blank card.
 */
export function displayName(capture: Pick<Capture, "common_name" | "species_id">): string {
  return capture.common_name || capture.species_id || "Unidentified";
}

/**
 * FlatList row containing an item.
 *
 * A multi-column FlatList counts ROWS, not items: internally it groups `data` into
 * chunks of `numColumns`, so a 6-item, 2-column list has indices 0..2. Passing an item
 * index to scrollToIndex therefore throws "out of range" for anything in the second
 * half of the list — item 3 of 6 asks for index 3 of 3.
 */
export function rowIndexFor(itemIndex: number, columns: number = GRID_COLUMNS): number {
  return Math.floor(itemIndex / columns);
}

/**
 * Captures in the order the backend returns them: rarest first, newest first within a
 * tier, unknown rarity last.
 *
 * This mirrors `get_collection` in backend/app/routers/collection.py — the tier ranks in
 * RARITY_META are the same numbers the backend's TIER_ORDER uses. API responses arrive
 * already sorted and are NOT re-sorted, so the backend stays the single authority on
 * ordering; this exists for any list the client assembles itself.
 */
export function sortCaptures(captures: Capture[]): Capture[] {
  return [...captures].sort((a, b) => {
    const byTier = rarityMeta(a.rarity_tier).order - rarityMeta(b.rarity_tier).order;
    if (byTier !== 0) return byTier;
    return new Date(b.captured_at).getTime() - new Date(a.captured_at).getTime();
  });
}
