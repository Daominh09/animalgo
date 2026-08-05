import { sortCaptures } from "../captures";
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
// Kept faithful to what the database actually holds, so the screens are never developed
// against data the API could not produce:
//   - ids are UUIDs, because the backend returns str(capture.id)
//   - coordinates sit on grid centres (39.85, -110.55, ...), because every capture is
//     snapped to a ~11 km cell before storage, so real pins never land on arbitrary
//     decimals. The tiger is the one exception, placed exactly where it was asked for.
//   - tiers match what score_rarity would actually return for those species' US
//     occurrence counts (Mountain Lion 11,553 -> rare, Black Bear 41,892 -> uncommon)
//   - the list is sorted by the same rule as GET /collection, applied below rather than
//     by hand, so it cannot drift out of order as entries are added

const photo = (keyword: string, lock: number) =>
  `https://loremflickr.com/400/400/${keyword}?lock=${lock}`;

const CAPTURES: Capture[] = [
  {
    id: "0f3b7c1a-5d84-4e29-9b16-2a7c8e4d1f60",
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
    id: "1a2d9e47-6c30-4b81-a5f2-8e0b3c7d9142",
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
    id: "2b4e8f05-7a19-4c63-8d27-9f1a5b6e3c84",
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
    id: "3c5f0a16-8b2d-4e74-9138-0a2b6c7f4d95",
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
    // No location sent. Appears in the Collection grid but never on the map, and the
    // card offers no "Map" link.
    id: "5e718c39-0d4f-4096-b35a-2c4d8e9f6017",
    species_id: "Passer domesticus",
    image_url: photo("sparrow", 9),
    rarity_tier: "common",
    lat: null,
    lng: null,
    confidence_score: 0.91,
    confirmed_by_user: false,
    captured_at: "2026-07-31T12:30:00",
  },
  {
    // Rarity could not be determined. Renders the dashed "Unknown" badge and a grey pin,
    // and sorts last — worth having, because it is the state most likely to be
    // mishandled and the least likely to be seen by accident.
    id: "4d607b28-9c3e-4f85-a249-1b3c7d8e5f06",
    species_id: "Troglodytidae",
    image_url: photo("wren", 8),
    rarity_tier: null,
    lat: 34.05,
    lng: -118.25,
    confidence_score: 0.42,
    confirmed_by_user: false,
    captured_at: "2026-08-01T15:55:00",
  },
];

export const MOCK_CAPTURES: Capture[] = sortCaptures(CAPTURES);
