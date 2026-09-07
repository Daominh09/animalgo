import type { Battle, BattleCapture } from "./api/battles";

// Owner: Person C — Battle System
// Pure helpers for the battle screens, kept out of the components so the hub, the
// challenge flow and the result screen agree by construction rather than by each being
// written carefully. Mirrors how Person B split captures.ts out of the Collection screen.

// --- Traits ----------------------------------------------------------------------
//
// The counterplay cycle, mirroring backend/app/services/battle_resolution.py: ferocity
// beats guile, guile beats resilience, resilience beats ferocity. The backend is the
// authority on who actually won -- this exists so the player can see a matchup BEFORE
// committing a capture, which is the entire point of the mechanic.

export type Trait = "ferocity" | "guile" | "resilience";

export interface TraitMeta {
  label: string;
  /** One glyph, so a roster card can show the trait without a second line of text. */
  icon: string;
  badgeClass: string;
  /** The trait this one beats. */
  beats: Trait;
}

export const TRAIT_META: Record<Trait, TraitMeta> = {
  ferocity: { label: "Ferocity", icon: "🔥", badgeClass: "bg-rose-100 text-rose-700", beats: "guile" },
  guile: { label: "Guile", icon: "🌀", badgeClass: "bg-violet-100 text-violet-700", beats: "resilience" },
  resilience: { label: "Resilience", icon: "🛡", badgeClass: "bg-teal-100 text-teal-700", beats: "ferocity" },
};

const UNKNOWN_TRAIT: TraitMeta = {
  label: "No trait",
  icon: "—",
  badgeClass: "bg-slate-100 text-slate-500",
  // Never consulted: traitMatchup() short-circuits on a null trait before reading this.
  beats: "ferocity",
};

/** Presentation for a trait, including the null case (a capture whose species never
 *  resolved — it neither gains an advantage nor grants one). */
export function traitMeta(trait: string | null | undefined): TraitMeta {
  return (trait && TRAIT_META[trait as Trait]) || UNKNOWN_TRAIT;
}

/** Which side the trait cycle favours, from `mine`'s point of view.
 *
 * Returns null for "neither", which covers three cases that all mean the same thing to a
 * player: the same trait on both sides, and either capture being unidentified. */
export function traitMatchup(mine: string | null, theirs: string | null): "advantage" | "disadvantage" | null {
  if (!mine || !theirs) return null;
  if (!(mine in TRAIT_META) || !(theirs in TRAIT_META)) return null;
  if (TRAIT_META[mine as Trait].beats === theirs) return "advantage";
  if (TRAIT_META[theirs as Trait].beats === mine) return "disadvantage";
  return null;
}

// --- Battle list ------------------------------------------------------------------

/** A battle waiting on YOU: someone challenged you and you have not answered.
 *
 * The distinction the Battle tab is built around -- these are the only rows with an
 * action attached, so they sort to the top and everything else is history. */
export function needsMyAnswer(battle: Battle): boolean {
  return battle.status === "pending" && battle.role === "opponent";
}

/** A challenge you sent that is still waiting on them. */
export function awaitingThem(battle: Battle): boolean {
  return (battle.status === "pending" || battle.status === "resolving") && battle.role === "challenger";
}

export interface BattleSections {
  incoming: Battle[];
  outgoing: Battle[];
  finished: Battle[];
}

/**
 * Splits the flat list the backend returns into the three groups the hub renders.
 *
 * Order within each group is preserved -- the backend already sorts newest first, and
 * re-sorting here would make it the second authority on ordering.
 *
 * `resolving` is a brief server-side state (a battle mid-resolution). It is grouped with
 * outgoing/finished rather than given a section of its own, because a player should never
 * see a heading for a state that lasts milliseconds.
 */
export function groupBattles(battles: Battle[]): BattleSections {
  return {
    incoming: battles.filter(needsMyAnswer),
    outgoing: battles.filter(awaitingThem),
    finished: battles.filter((b) => !needsMyAnswer(b) && !awaitingThem(b)),
  };
}

/** The other player, whichever side of the battle you are on. */
export function theirSide(battle: Battle) {
  return battle.role === "challenger" ? battle.opponent : battle.challenger;
}

/** Your own side. */
export function mySide(battle: Battle) {
  return battle.role === "challenger" ? battle.challenger : battle.opponent;
}

/** What to print on a battle card. Common name first, same fallback chain as a capture
 *  card — some captures genuinely have no common name. */
export function captureName(capture: Pick<BattleCapture, "common_name" | "species_id"> | null): string {
  if (!capture) return "Not chosen yet";
  return capture.common_name || capture.species_id || "Unidentified";
}

/**
 * A one-line summary of where a battle stands, from your point of view.
 *
 * Centralised because every status has a different subject: a pending challenge is about
 * who has to act, a resolved one is about who won. Spreading that across three screens is
 * how they end up disagreeing.
 */
export function battleSummary(battle: Battle): string {
  const them = theirSide(battle).display_name;
  switch (battle.status) {
    case "pending":
      return battle.role === "opponent" ? `${them} challenged you` : `Waiting for ${them}`;
    case "resolving":
      return "Resolving…";
    case "resolved":
      return battle.outcome === "won" ? `You beat ${them}` : `${them} beat you`;
    case "declined":
      return battle.role === "challenger" ? `${them} declined` : "You declined";
    case "expired":
      return "Challenge expired";
    default:
      // A status this build does not know about. Showing the raw value beats showing
      // nothing, and beats crashing on an exhaustiveness assumption that a newer backend
      // has broken.
      return battle.status;
  }
}

/**
 * How long a pending challenge has left, as "2d left" / "5h left" / "12m left".
 *
 * Null when there is nothing to count down to -- no expiry (the battle is decided) or the
 * deadline has already passed. Clamping to null at zero rather than showing "0m left"
 * matters because the client's clock is not the server's: the server decides what is
 * expired, and a client that renders a negative countdown is asserting something it does
 * not know.
 */
export function timeLeft(expiresAt: string | null, now: Date = new Date()): string | null {
  if (!expiresAt) return null;
  const remaining = new Date(expiresAt).getTime() - now.getTime();
  if (!Number.isFinite(remaining) || remaining <= 0) return null;

  const minutes = Math.floor(remaining / 60_000);
  if (minutes < 60) return `${Math.max(1, minutes)}m left`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h left`;
  return `${Math.floor(hours / 24)}d left`;
}
