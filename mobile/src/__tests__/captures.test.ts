import type { Capture } from "../api/collection";
import { GRID_COLUMNS, rowIndexFor, sortCaptures } from "../captures";
import { boundsFor, capturesToPins, computeBounds } from "../map/mapHtml";
import { rarityMeta } from "../rarity";

// Owner: Person B — Rarity Engine & Collection
// The pure helpers behind the Collection grid and the Map. Everything here is a plain
// function, so no renderer, no network and no navigation are involved.

function capture(over: Partial<Capture> = {}): Capture {
  return {
    id: "id",
    species_id: "Passer domesticus",
    image_url: "https://r2.test/p.jpg",
    rarity_tier: "common",
    lat: 39.85,
    lng: -98.55,
    confidence_score: 0.9,
    confirmed_by_user: false,
    captured_at: "2026-08-01T00:00:00",
    ...over,
  };
}

// --- rowIndexFor ---------------------------------------------------------------------
// This is the one that crashed: "scrollToIndex out of range: requested index 3 is out
// of 0 to 2". A multi-column FlatList counts rows, not items.

describe("rowIndexFor", () => {
  it("maps item indices to the row containing them", () => {
    expect([0, 1, 2, 3, 4, 5].map((i) => rowIndexFor(i, 2))).toEqual([0, 0, 1, 1, 2, 2]);
  });

  it("never returns a row outside the list", () => {
    // The exact shape of the crash: 6 items in 2 columns is 3 rows, so every item must
    // map into 0..2.
    const items = 6;
    const rows = Math.ceil(items / GRID_COLUMNS);
    for (let i = 0; i < items; i++) {
      const row = rowIndexFor(i);
      expect(row).toBeGreaterThanOrEqual(0);
      expect(row).toBeLessThan(rows);
    }
  });

  it("defaults to the grid's own column count", () => {
    expect(rowIndexFor(3)).toBe(rowIndexFor(3, GRID_COLUMNS));
  });
});

// --- sortCaptures --------------------------------------------------------------------
// Mirrors get_collection in backend/app/routers/collection.py.

describe("sortCaptures", () => {
  it("orders rarest first", () => {
    const out = sortCaptures([
      capture({ id: "c", rarity_tier: "common" }),
      capture({ id: "l", rarity_tier: "legendary" }),
      capture({ id: "u", rarity_tier: "uncommon" }),
      capture({ id: "r", rarity_tier: "rare" }),
    ]);
    expect(out.map((c) => c.id)).toEqual(["l", "r", "u", "c"]);
  });

  it("puts unknown rarity last, not first", () => {
    // A failed lookup must not outrank a legendary just by having no tier.
    const out = sortCaptures([
      capture({ id: "unknown", rarity_tier: null }),
      capture({ id: "common", rarity_tier: "common" }),
    ]);
    expect(out.map((c) => c.id)).toEqual(["common", "unknown"]);
  });

  it("orders newest first within a tier", () => {
    const out = sortCaptures([
      capture({ id: "old", captured_at: "2026-08-01T00:00:00" }),
      capture({ id: "new", captured_at: "2026-08-09T00:00:00" }),
      capture({ id: "mid", captured_at: "2026-08-05T00:00:00" }),
    ]);
    expect(out.map((c) => c.id)).toEqual(["new", "mid", "old"]);
  });

  it("does not mutate its input", () => {
    const input = [capture({ id: "c", rarity_tier: "common" }), capture({ id: "l", rarity_tier: "legendary" })];
    sortCaptures(input);
    expect(input.map((c) => c.id)).toEqual(["c", "l"]);
  });
});

// --- map helpers ----------------------------------------------------------------------

describe("capturesToPins", () => {
  it("drops captures with no coordinates rather than defaulting them", () => {
    // A pin at 0,0 would be a lie; the Collection screen still lists them.
    const pins = capturesToPins([
      capture({ id: "here" }),
      capture({ id: "nowhere", lat: null, lng: null }),
    ]);
    expect(pins.map((p) => p.id)).toEqual(["here"]);
  });

  it("drops a capture missing only one half of its coordinates", () => {
    expect(capturesToPins([capture({ lat: 39.85, lng: null })])).toEqual([]);
    expect(capturesToPins([capture({ lat: null, lng: -98.55 })])).toEqual([]);
  });

  it("carries the tier through so the pin can be coloured", () => {
    const [pin] = capturesToPins([capture({ rarity_tier: "legendary" })]);
    expect(pin.rarity).toBe("legendary");
    expect(rarityMeta(pin.rarity).color).toBe(rarityMeta("legendary").color);
  });
});

describe("computeBounds", () => {
  it("returns null when there is nothing to frame", () => {
    expect(computeBounds([])).toBeNull();
  });

  it("wraps every pin", () => {
    const pins = capturesToPins([
      capture({ id: "a", lat: 40.75, lng: -111.85 }),
      capture({ id: "b", lat: 34.05, lng: -118.25 }),
    ]);
    expect(computeBounds(pins)).toEqual([
      [-118.25, 34.05],
      [-111.85, 40.75],
    ]);
  });

  it("handles a single pin as a zero-size box", () => {
    // fitBounds copes via maxZoom; the important part is that it isn't null.
    const pins = capturesToPins([capture({ lat: 39.85, lng: -98.55 })]);
    expect(computeBounds(pins)).toEqual([
      [-98.55, 39.85],
      [-98.55, 39.85],
    ]);
  });
});

describe("boundsFor", () => {
  const pins = capturesToPins([
    capture({ id: "a", lat: 40.75, lng: -111.85 }),
    capture({ id: "b", lat: 34.05, lng: -118.25 }),
  ]);

  it("frames every pin when nothing is focused", () => {
    expect(boundsFor(pins, null)).toEqual(computeBounds(pins));
  });

  it("frames only the focused capture", () => {
    expect(boundsFor(pins, "a")).toEqual([
      [-111.85, 40.75],
      [-111.85, 40.75],
    ]);
  });

  it("falls back to every pin when the focused capture is gone", () => {
    // Arriving from a card whose capture has since disappeared should still show a
    // usable map, not an empty default view.
    expect(boundsFor(pins, "deleted")).toEqual(computeBounds(pins));
  });

  it("returns null only when there are no pins at all", () => {
    expect(boundsFor([], "anything")).toBeNull();
  });
});

// --- rarity presentation ---------------------------------------------------------------

describe("rarityMeta", () => {
  it("treats null as unknown, not common", () => {
    expect(rarityMeta(null).label).toBe("Unknown");
    expect(rarityMeta(null).label).not.toBe(rarityMeta("common").label);
  });

  it("sorts unknown after every real tier", () => {
    for (const tier of ["legendary", "rare", "uncommon", "common"]) {
      expect(rarityMeta(null).order).toBeGreaterThan(rarityMeta(tier).order);
    }
  });

  it("falls back to unknown for a tier the backend never sends", () => {
    expect(rarityMeta("mythic").label).toBe("Unknown");
  });
});
