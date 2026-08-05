import type { Capture } from "./collection";

// Owner: Person B — Rarity Engine & Collection
//
// Stand-in captures, used only while there is no signed-in user, so the Collection and
// Map screens have something to render before Person D's sign-in flow and Person A's
// capture write land. The moment a token exists, the real GET /collection response
// replaces this — see useCollection().
//
// Shaped exactly like the real endpoint's rows, so nothing downstream can tell the
// difference. That is the point: if the mock needed different handling, the screens
// would be testing a path the real data never takes.
//
// Coordinates are on grid centres (39.85, -110.55, ...) because that is what the backend
// actually returns -- every capture is snapped to a ~11 km cell before it is stored, so
// real pins never land on arbitrary decimals. The tiger is the exception, placed exactly
// where it was asked for.

const photo = (keyword: string, lock: number) =>
  `https://loremflickr.com/400/400/${keyword}?lock=${lock}`;

export const MOCK_CAPTURES: Capture[] = [
  {
    id: "mock-tiger",
    species_id: "Panthera tigris",
    image_url: photo("tiger", 2),
    rarity_tier: "legendary", // IUCN Endangered — legendary regardless of sighting count
    lat: 48.87466383515097,
    lng: 2.3451458250295567,
    confidence_score: 0.94,
    confirmed_by_user: false,
    captured_at: "2026-08-05T09:12:00",
  },
  {
    id: "mock-cougar",
    species_id: "Puma concolor",
    image_url: photo("cougar", 5),
    rarity_tier: "rare", // 11,553 US records
    lat: 40.75,
    lng: -111.85,
    confidence_score: 0.81,
    confirmed_by_user: false,
    captured_at: "2026-08-04T17:40:00",
  },
  {
    id: "mock-bear",
    species_id: "Ursus americanus",
    image_url: photo("bear", 6),
    rarity_tier: "uncommon", // 41,892 US records
    lat: 44.45,
    lng: -110.55,
    confidence_score: 0.88,
    confirmed_by_user: true,
    captured_at: "2026-08-03T11:05:00",
  },
  {
    id: "mock-cardinal",
    species_id: "Cardinalis cardinalis",
    image_url: photo("cardinal-bird", 7),
    rarity_tier: "common", // 24.8M US records
    lat: 39.85,
    lng: -98.55,
    confidence_score: 0.96,
    confirmed_by_user: false,
    captured_at: "2026-08-02T08:20:00",
  },
  {
    // Rarity could not be determined. Renders with the dashed "Unknown" badge and a grey
    // pin -- worth having in the mock, because it is the state most likely to be
    // mishandled and the least likely to be seen by accident.
    id: "mock-unknown",
    species_id: "Troglodytidae",
    image_url: photo("wren", 8),
    rarity_tier: null,
    lat: 34.05,
    lng: -118.25,
    confidence_score: 0.42,
    confirmed_by_user: false,
    captured_at: "2026-08-01T15:55:00",
  },
  {
    // No location sent. Appears in the Collection grid but never on the map.
    id: "mock-no-location",
    species_id: "Passer domesticus",
    image_url: photo("sparrow", 9),
    rarity_tier: "common",
    lat: null,
    lng: null,
    confidence_score: 0.91,
    confirmed_by_user: false,
    captured_at: "2026-07-31T12:30:00",
  },
];
