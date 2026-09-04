// Owner: Person B — Rarity Engine & Collection
//
// Rarity presentation, shared by the Collection and Map screens. Mirrors the backend's
// four tiers (app/services/rarity.py).
//
// `null` is a fifth case and not an error: the backend returns rarity_tier: null when a
// species could not be looked up. It means "unknown", NOT "common" — showing it as
// common would quietly present a failed lookup as a real result.

export type RarityTier = "common" | "uncommon" | "rare" | "legendary";

export interface RarityMeta {
  label: string;
  order: number;
  badgeClass: string;
  ringClass: string;
  /** Map pin colour. */
  color: string;
}

export const RARITY_META: Record<RarityTier, RarityMeta> = {
  legendary: { label: "Legendary", order: 0, badgeClass: "bg-amber-100 text-amber-800", ringClass: "border-amber-400", color: "#f59e0b" },
  rare: { label: "Rare", order: 1, badgeClass: "bg-sky-100 text-sky-800", ringClass: "border-sky-400", color: "#0ea5e9" },
  uncommon: { label: "Uncommon", order: 2, badgeClass: "bg-emerald-100 text-emerald-800", ringClass: "border-emerald-400", color: "#10b981" },
  common: { label: "Common", order: 3, badgeClass: "bg-slate-200 text-slate-700", ringClass: "border-slate-300", color: "#64748b" },
};

const UNKNOWN: RarityMeta = {
  label: "Unknown",
  order: 4, // sorts last, matching the backend's ordering
  badgeClass: "bg-slate-100 text-slate-500",
  ringClass: "border-dashed border-slate-300",
  color: "#cbd5e1",
};

/** Presentation for a tier, including the null "we couldn't score this" case. */
export function rarityMeta(tier: string | null | undefined): RarityMeta {
  return (tier && RARITY_META[tier as RarityTier]) || UNKNOWN;
}
