from app.services import geoprivacy

# Owner: Person B — Rarity Engine & Collection
# Every capture's coordinates are fuzzed to a grid cell. Pure functions, no network,
# no DB.

# Somewhere in Kansas, chosen so the cell it falls in is easy to check by hand:
# floor(39.8283 / 0.1) = 398 -> centre (398 + 0.5) * 0.1 = 39.85
LAT, LNG = 39.8283, -98.5795
SNAPPED_LAT, SNAPPED_LNG = 39.85, -98.55


def test_every_capture_is_fuzzed():
    assert geoprivacy.fuzz_coordinates(LAT, LNG) == {"lat": SNAPPED_LAT, "lng": SNAPPED_LNG}


def test_nearby_points_collapse_to_the_same_cell():
    a = geoprivacy.fuzz_coordinates(39.8010, -98.5990)
    b = geoprivacy.fuzz_coordinates(39.8990, -98.5010)

    assert a == b == {"lat": SNAPPED_LAT, "lng": SNAPPED_LNG}


def test_next_cell_over_gets_a_different_answer():
    # Sanity check that the grid actually has cells rather than swallowing everything.
    assert geoprivacy.fuzz_coordinates(39.9400, LNG)["lat"] == 39.95


def test_values_on_a_cell_boundary_land_in_the_cell_above():
    # 39.8 is the bottom edge of the cell running 39.80-39.90, so it belongs to that
    # cell. In floating point 39.8 / 0.1 is 397.99999999999994, which floors one cell
    # too low -- and round numbers like this are exactly what people type when testing.
    assert geoprivacy.fuzz_coordinates(39.8, -98.5) == {"lat": 39.85, "lng": -98.45}
    assert geoprivacy.fuzz_coordinates(0.3, 0.7) == {"lat": 0.35, "lng": 0.75}


# --- the property that makes snapping worth choosing ----------------------------------


def test_repeated_captures_never_narrow_the_location():
    # The reason this is grid snapping and not random jitter. Twenty captures scattered
    # around one nest all collapse to the same cell centre, so averaging them tells an
    # observer nothing a single capture did not. Random offsets would average out to the
    # true point.
    nest_lat, nest_lng = 39.8283, -98.5795
    published = {
        tuple(geoprivacy.fuzz_coordinates(nest_lat + i * 0.001 - 0.01, nest_lng + i * 0.001 - 0.01).values())
        for i in range(20)
    }

    assert len(published) == 1  # one point, no matter how many observations


def test_output_is_deterministic():
    assert geoprivacy.fuzz_coordinates(LAT, LNG) == geoprivacy.fuzz_coordinates(LAT, LNG)


def test_published_point_is_within_half_a_cell():
    # Snapping to the cell centre, not its edge, keeps the displacement bounded.
    out = geoprivacy.fuzz_coordinates(LAT, LNG)

    assert abs(out["lat"] - LAT) <= geoprivacy.GRID_DEGREES / 2
    assert abs(out["lng"] - LNG) <= geoprivacy.GRID_DEGREES / 2


# --- missing and malformed input ------------------------------------------------------


def test_missing_coordinates_return_nothing():
    for lat, lng in ((None, None), (LAT, None), (None, LNG)):
        assert geoprivacy.fuzz_coordinates(lat, lng) == {"lat": None, "lng": None}


def test_out_of_range_coordinates_are_dropped():
    # Snapping nonsense would produce confident nonsense.
    for lat, lng in ((91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)):
        assert geoprivacy.fuzz_coordinates(lat, lng) == {"lat": None, "lng": None}, (lat, lng)


def test_extremes_never_produce_an_invalid_coordinate():
    # The pole and the antimeridian would snap past the valid range without clamping.
    out = geoprivacy.fuzz_coordinates(90.0, 180.0)

    assert -90 <= out["lat"] <= 90
    assert -180 <= out["lng"] <= 180


def test_southern_and_western_hemispheres_snap_correctly():
    # floor() on negatives rounds away from zero, which keeps cells contiguous across
    # the equator and prime meridian instead of doubling in width at zero.
    out = geoprivacy.fuzz_coordinates(-33.8688, 151.2093)

    assert out == {"lat": -33.85, "lng": 151.25}
