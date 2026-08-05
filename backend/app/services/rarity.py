# Owner: Person B — Rarity Engine & Collection
# Scoring only. Coordinate protection lives in app/services/geoprivacy.py, kept separate
# so the Week 4 privacy audit has one small file to read rather than a scoring module to
# pick through. SENSITIVE_STATUSES is shared with it.
#
# DELIBERATE: occurrence_count is US-only, so a species that is abundant elsewhere but
# barely recorded in the US scores as legendary. Example — Eurasian Blackbird
# (Turdus merula): 7 US records but 13.4M globally, so it scores legendary, the same as
# an endangered tiger. That is intended: this is a location-based game, and finding a
# bird that does not belong here IS the trophy moment. Do not "fix" it by switching to
# global counts without a team decision.
#
# Two consequences to keep in view:
#   - It is an exploit vector. Photographing a foreign species off a screen or in a zoo
#     mints 500 coins, and those are the easiest shots to fake. Anti-cheat (Person D:
#     live-camera enforcement, duplicate-image hashing) is what limits this, not the
#     scoring.
#   - Revisit at the Week 3 balance checkpoint ("adjust regional weighting based on
#     Week 2's spot-check flags") if payouts feel wrong in playtesting.
#
# KNOWN MISMATCH, worth a team decision rather than a threshold tweak: charisma is not
# rarity. A Bald Eagle has 6.36M US records -- more than a Gray Squirrel -- so it scores
# common, which is factually right and will still feel wrong to a player. Recovered
# flagship species are the whole category. Fixing it means a separate "iconic species"
# bonus, not moving a boundary, because any boundary that makes an eagle rare also makes
# a squirrel rare.

SENSITIVE_STATUSES = {"VU", "EN", "CR"}

# Thresholds come from the Week 2 spot-check against live GBIF, not from guesswork.
# The first cut used 10 / 100 / 1000 and collapsed: every species that wasn't
# IUCN-listed scored "common", because real US counts are far larger than that.
#
#   Mountain Lion        11,553      Whooping Crane   78,781
#   American Black Bear  41,892      Eastern Gray Squirrel   234,244
#   Bald Eagle        6,360,035      Northern Cardinal    24,852,472
#
# The numbers span seven orders of magnitude (7 to 24.8M), so the boundaries have to be
# spaced like the data is -- roughly by powers of ten -- or three of the four tiers
# never get used. Fitted to ten species; Week 3's balance checkpoint is where they get
# revisited with playtest data.
LEGENDARY_BELOW = 100
RARE_BELOW = 20_000
UNCOMMON_BELOW = 200_000


def score_rarity(occurrence_count: int, iucn_status: str) -> tuple[str, int]:
    """Returns (rarity_tier, coin_value)."""
    if iucn_status in SENSITIVE_STATUSES or occurrence_count < LEGENDARY_BELOW:
        return "legendary", 500
    if occurrence_count < RARE_BELOW:
        return "rare", 100
    if occurrence_count < UNCOMMON_BELOW:
        return "uncommon", 25
    return "common", 5
