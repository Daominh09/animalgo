import type { Battle, BattleCapture, BattleSide } from "../api/battles";
import {
  battleSummary,
  captureName,
  groupBattles,
  mySide,
  needsMyAnswer,
  theirSide,
  timeLeft,
  TRAIT_META,
  traitMatchup,
  traitMeta,
  type Trait,
} from "../battles";

// Owner: Person C — Battle System
// The pure helpers behind the battle screens. Plain functions only: no renderer, no
// network, no navigation.

function capture(over: Partial<BattleCapture> = {}): BattleCapture {
  return {
    id: "cap-1",
    common_name: "Red Fox",
    species_id: "Vulpes vulpes",
    image_url: "https://r2.test/fox.jpg",
    rarity_tier: "common",
    trait: "ferocity",
    ...over,
  };
}

function side(over: Partial<BattleSide> = {}): BattleSide {
  return {
    user_id: "user-1",
    display_name: "Alice",
    capture: capture(),
    total: null,
    roll: null,
    ...over,
  };
}

function battle(over: Partial<Battle> = {}): Battle {
  return {
    id: "battle-1",
    status: "pending",
    role: "challenger",
    outcome: null,
    created_at: "2026-09-01T00:00:00+00:00",
    resolved_at: null,
    expires_at: "2026-09-03T00:00:00+00:00",
    challenger: side({ user_id: "alice", display_name: "Alice" }),
    opponent: side({ user_id: "bob", display_name: "Bob" }),
    winner_id: null,
    trait_advantage: null,
    coins_awarded: null,
    ...over,
  };
}

// --- Traits ---------------------------------------------------------------------------
// The cycle here has to agree with backend/app/services/battle_resolution.py. If the two
// disagree, the app tells a player a capture counters their opponent and then it loses.

describe("trait cycle", () => {
  it("beats exactly one trait and loses to exactly one", () => {
    const traits = Object.keys(TRAIT_META) as Trait[];
    for (const trait of traits) {
      const others = traits.filter((t) => t !== trait);
      expect(others.filter((o) => traitMatchup(trait, o) === "advantage")).toHaveLength(1);
      expect(others.filter((o) => traitMatchup(trait, o) === "disadvantage")).toHaveLength(1);
    }
  });

  it("matches the backend cycle: ferocity > guile > resilience > ferocity", () => {
    expect(traitMatchup("ferocity", "guile")).toBe("advantage");
    expect(traitMatchup("guile", "resilience")).toBe("advantage");
    expect(traitMatchup("resilience", "ferocity")).toBe("advantage");
  });

  it("is symmetric: what beats me is what I lose to", () => {
    expect(traitMatchup("guile", "ferocity")).toBe("disadvantage");
  });

  it("gives neither side an edge for the same trait", () => {
    expect(traitMatchup("ferocity", "ferocity")).toBeNull();
  });

  it("gives neither side an edge when a capture has no trait", () => {
    // An unidentified capture doesn't hand its opponent a free bonus, matching the
    // backend. Showing "Countered" here would be a lie the server never told.
    expect(traitMatchup(null, "ferocity")).toBeNull();
    expect(traitMatchup("ferocity", null)).toBeNull();
  });

  it("ignores a trait this build doesn't know about", () => {
    // A newer backend could add one. Claiming an advantage we can't reason about is
    // worse than claiming none.
    expect(traitMatchup("psychic", "ferocity")).toBeNull();
  });

  it("has presentation for the null trait", () => {
    expect(traitMeta(null).label).toBe("No trait");
    expect(traitMeta("ferocity").label).toBe("Ferocity");
  });
});

// --- Sides ----------------------------------------------------------------------------

describe("mySide / theirSide", () => {
  it("follows the role rather than the column", () => {
    // Viewed by Alice, who sent it.
    const asChallenger = battle({ role: "challenger" });
    expect(mySide(asChallenger).display_name).toBe("Alice");
    expect(theirSide(asChallenger).display_name).toBe("Bob");

    // The same row, viewed by Bob.
    const asOpponent = battle({ role: "opponent" });
    expect(mySide(asOpponent).display_name).toBe("Bob");
    expect(theirSide(asOpponent).display_name).toBe("Alice");
  });
});

// --- Grouping -------------------------------------------------------------------------

describe("groupBattles", () => {
  it("puts a challenge aimed at me in 'your turn' and one I sent in 'waiting'", () => {
    const incoming = battle({ id: "in", status: "pending", role: "opponent" });
    const outgoing = battle({ id: "out", status: "pending", role: "challenger" });

    const groups = groupBattles([incoming, outgoing]);

    expect(groups.incoming.map((b) => b.id)).toEqual(["in"]);
    expect(groups.outgoing.map((b) => b.id)).toEqual(["out"]);
    expect(groups.finished).toHaveLength(0);
  });

  it("treats resolved, declined and expired battles as history for both sides", () => {
    const rows = [
      battle({ id: "a", status: "resolved", role: "opponent" }),
      battle({ id: "b", status: "declined", role: "challenger" }),
      battle({ id: "c", status: "expired", role: "opponent" }),
    ];

    const groups = groupBattles(rows);

    expect(groups.finished.map((b) => b.id)).toEqual(["a", "b", "c"]);
    expect(groups.incoming).toHaveLength(0);
  });

  it("does not show 'resolving' as something I can act on", () => {
    // It is a server-side state that lasts milliseconds. Offering an Accept button for it
    // would produce a 409 every time it was tapped.
    const groups = groupBattles([battle({ status: "resolving", role: "opponent" })]);

    expect(groups.incoming).toHaveLength(0);
    expect(needsMyAnswer(battle({ status: "resolving", role: "opponent" }))).toBe(false);
  });

  it("preserves the order the backend sent", () => {
    // The backend sorts newest first and is the single authority on ordering.
    const rows = [
      battle({ id: "1", status: "resolved" }),
      battle({ id: "2", status: "resolved" }),
      battle({ id: "3", status: "resolved" }),
    ];

    expect(groupBattles(rows).finished.map((b) => b.id)).toEqual(["1", "2", "3"]);
  });

  it("assigns every battle to exactly one group", () => {
    const rows: Battle[] = (["pending", "resolving", "resolved", "declined", "expired"] as const).flatMap(
      (status) => [battle({ status, role: "challenger" }), battle({ status, role: "opponent" })],
    );

    const groups = groupBattles(rows);

    expect(groups.incoming.length + groups.outgoing.length + groups.finished.length).toBe(rows.length);
  });
});

// --- Summaries ------------------------------------------------------------------------

describe("battleSummary", () => {
  it("says who has to act on a pending challenge", () => {
    expect(battleSummary(battle({ status: "pending", role: "opponent" }))).toBe("Alice challenged you");
  });

  it("names the other player, whichever side you are on", () => {
    // role: challenger -> the other player is the opponent, "Bob".
    expect(battleSummary(battle({ status: "pending", role: "challenger" }))).toBe("Waiting for Bob");
  });

  it("reports a result from your point of view, not the challenger's", () => {
    expect(battleSummary(battle({ status: "resolved", role: "opponent", outcome: "won" }))).toBe(
      "You beat Alice",
    );
    expect(battleSummary(battle({ status: "resolved", role: "challenger", outcome: "lost" }))).toBe(
      "Bob beat you",
    );
  });

  it("distinguishes declining from being declined", () => {
    expect(battleSummary(battle({ status: "declined", role: "challenger" }))).toBe("Bob declined");
    expect(battleSummary(battle({ status: "declined", role: "opponent" }))).toBe("You declined");
  });

  it("falls back to the raw status for one this build doesn't know", () => {
    // A newer backend adding a status must not crash an older app.
    const unknown = battle({ status: "abandoned" as Battle["status"] });
    expect(battleSummary(unknown)).toBe("abandoned");
  });
});

describe("captureName", () => {
  it("prefers the common name", () => {
    expect(captureName(capture())).toBe("Red Fox");
  });

  it("falls back to the scientific name for a family-level identification", () => {
    expect(captureName(capture({ common_name: null, species_id: "Troglodytidae" }))).toBe("Troglodytidae");
  });

  it("labels an empty slot rather than rendering nothing", () => {
    // The opponent's side while a challenge is still pending.
    expect(captureName(null)).toBe("Not chosen yet");
  });
});

// --- Countdown ------------------------------------------------------------------------

describe("timeLeft", () => {
  const now = new Date("2026-09-01T12:00:00Z");

  it("counts down in days, hours and minutes", () => {
    expect(timeLeft("2026-09-03T12:00:00Z", now)).toBe("2d left");
    expect(timeLeft("2026-09-01T17:00:00Z", now)).toBe("5h left");
    expect(timeLeft("2026-09-01T12:30:00Z", now)).toBe("30m left");
  });

  it("never shows a negative or zero countdown", () => {
    // The client's clock is not the server's. The server decides what is expired, so a
    // client rendering "-3m left" would be asserting something it does not know.
    expect(timeLeft("2026-09-01T11:00:00Z", now)).toBeNull();
    expect(timeLeft("2026-09-01T12:00:00Z", now)).toBeNull();
  });

  it("rounds a nearly-elapsed challenge up to a minute rather than to zero", () => {
    expect(timeLeft("2026-09-01T12:00:30Z", now)).toBe("1m left");
  });

  it("shows nothing for a battle with no deadline", () => {
    // Resolved, declined and expired battles all come back with expires_at: null.
    expect(timeLeft(null, now)).toBeNull();
  });

  it("shows nothing rather than NaN for an unparseable timestamp", () => {
    expect(timeLeft("not a date", now)).toBeNull();
  });
});
