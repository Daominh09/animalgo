import math

# Owner: Person B — Rarity Engine & Collection
#
# Every capture's coordinates are fuzzed. No exceptions, no conditions.
#
# Deliberately blunt. The alternative -- fuzz only threatened species -- means the
# privacy of an endangered animal depends on a species lookup being correct and
# available, and it leaves exact points lying around that can be used to work out where
# a fuzzed one was (photograph a sparrow next to an eagle's nest and the sparrow gives
# away the nest). Fuzzing everything has neither problem, and there is nothing to get
# wrong. This is a prototype; a rule with no branches is worth more than a clever one.
#
# It runs BEFORE anything is persisted, not as a display filter. Once a raw coordinate
# reaches Postgres it is queryable, joinable, and in every backup and export from then
# on -- deleting it later does not un-leak it.
#
# WHY GRID SNAPPING AND NOT RANDOM JITTER
# Random offsets average out: photograph the same nest twenty times and the mean of the
# twenty published points converges on the truth. Snapping is a function of position --
# same place in, same answer out -- so twenty captures publish twenty identical points
# and repetition reveals nothing extra.

# ~11 km north-south; 7-11 km east-west across US latitudes. Coarse enough that the
# search area protects a specific nest or den, fine enough that the Map screen still
# puts a capture in the right area. Revisit at the Week 4 privacy audit.
GRID_DEGREES = 0.1


def _snap(value: float, limit: float) -> float:
    """Round to the centre of the grid cell the value falls in. Centre rather than edge
    so the shift is at most half a cell in any direction, instead of always south-west."""
    # round() before floor(): neither 0.1 nor most coordinates are exact in binary, so
    # 39.8 / 0.1 evaluates to 397.99999999999994 and would floor one cell too low. The
    # rounding is well inside a centimetre, so it only ever corrects that error.
    centre = (math.floor(round(value / GRID_DEGREES, 6)) + 0.5) * GRID_DEGREES
    # A point exactly on a pole or the antimeridian would otherwise snap outside the
    # valid range. Unreachable for a US-only app; two lines to never emit a coordinate
    # that isn't a coordinate.
    return round(max(-limit, min(limit, centre)), 6)


def fuzz_coordinates(lat: float | None, lng: float | None) -> dict:
    """The only location the rest of the system may use.

    Returns {"lat", "lng"}, both None when there was no usable coordinate. Callers must
    persist and return THIS, never the lat/lng passed in, and must not log the raw values.
    """
    if lat is None or lng is None:
        return {"lat": None, "lng": None}

    # Out-of-range input is a client bug, and snapping nonsense produces confident
    # nonsense. Drop it rather than storing a coordinate that means nothing.
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return {"lat": None, "lng": None}

    return {"lat": _snap(lat, 90), "lng": _snap(lng, 180)}
