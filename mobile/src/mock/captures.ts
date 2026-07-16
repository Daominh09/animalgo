// Owner: Person B — Rarity Engine & Collection
// Week 1: mock capture data so the Collection screen has something to render before the
// real capture → identify → rarity pipeline lands. In Week 2 this is replaced by data
// from GET /collection (see src/api/client.ts). Photos are stand-in emoji until Person
// A's R2 upload flow produces real image URLs.
//
// Rarity tiers + statuses mirror the backend: score_rarity() returns these four tiers,
// and the "legendary" examples below are the IUCN-sensitive species (EN/CR) the rarity
// engine flags — the same ones confirmed via GBIF (tiger=EN, Tonkin monkey=CR).

export type RarityTier = "common" | "uncommon" | "rare" | "legendary";

export interface MockCapture {
  id: string;
  species: string; // common name
  scientificName: string;
  rarity: RarityTier;
  imageUrl: string; // the photo the player took — maps to the capture record's R2 image_url
  region: string; // ISO 3166-1 alpha-2, matches the backend rarity lookups
  capturedAt: string; // ISO date
}

// Placeholder photos standing in for real player captures until Person A's R2 upload flow
// lands. loremflickr returns a real photo for a keyword; `lock` pins each card to a stable
// image. In Week 2 these come from GET /collection as R2 URLs — the <Image> render path is
// identical, so only the data source changes.
const photo = (keyword: string, lock: number) => `https://loremflickr.com/400/400/${keyword}?lock=${lock}`;

// Ordered most-rare first; drives sort order and badge styling. Kept in one place so the
// Collection/Map screens and any future badge component share it.
export const RARITY_META: Record<
  RarityTier,
  { label: string; order: number; badgeClass: string; ringClass: string }
> = {
  legendary: { label: "Legendary", order: 0, badgeClass: "bg-amber-100 text-amber-800", ringClass: "border-amber-400" },
  rare: { label: "Rare", order: 1, badgeClass: "bg-sky-100 text-sky-800", ringClass: "border-sky-400" },
  uncommon: { label: "Uncommon", order: 2, badgeClass: "bg-emerald-100 text-emerald-800", ringClass: "border-emerald-400" },
  common: { label: "Common", order: 3, badgeClass: "bg-slate-200 text-slate-700", ringClass: "border-slate-300" },
};

export const MOCK_CAPTURES: MockCapture[] = [
  { id: "1", species: "Tonkin Snub-nosed Monkey", scientificName: "Rhinopithecus avunculus", rarity: "legendary", imageUrl: photo("monkey", 1), region: "VN", capturedAt: "2026-07-14" },
  { id: "2", species: "Tiger", scientificName: "Panthera tigris", rarity: "legendary", imageUrl: photo("tiger", 2), region: "VN", capturedAt: "2026-07-13" },
  { id: "3", species: "Giant Panda", scientificName: "Ailuropoda melanoleuca", rarity: "rare", imageUrl: photo("panda", 3), region: "US", capturedAt: "2026-07-12" },
  { id: "4", species: "Monarch Butterfly", scientificName: "Danaus plexippus", rarity: "uncommon", imageUrl: photo("butterfly", 4), region: "US", capturedAt: "2026-07-11" },
  { id: "5", species: "Red Fox", scientificName: "Vulpes vulpes", rarity: "uncommon", imageUrl: photo("fox", 5), region: "US", capturedAt: "2026-07-10" },
  { id: "6", species: "House Sparrow", scientificName: "Passer domesticus", rarity: "common", imageUrl: photo("sparrow", 6), region: "US", capturedAt: "2026-07-09" },
  { id: "7", species: "Mallard Duck", scientificName: "Anas platyrhynchos", rarity: "common", imageUrl: photo("duck", 7), region: "US", capturedAt: "2026-07-08" },
  { id: "8", species: "Grey Squirrel", scientificName: "Sciurus carolinensis", rarity: "common", imageUrl: photo("squirrel", 8), region: "US", capturedAt: "2026-07-07" },
];

/** Captures sorted most-rare first — previews Week 2's "collection sorted by rarity". */
export const MOCK_CAPTURES_BY_RARITY: MockCapture[] = [...MOCK_CAPTURES].sort(
  (a, b) => RARITY_META[a.rarity].order - RARITY_META[b.rarity].order,
);
