"""Tests for the coordinate-anchored grid and region-polygon classification.

Covers Subtasks 1.1 (grid + sea mask) and 1.2 (region polygons) of
the geographic-foundation phase. Cell-count assertions match the calibration baseline recorded
in  and are intentionally tied to the exact
polygon vertices in geography.py — if a follow-up commit retunes a
polygon, the test fails loudly so the baseline is updated rather than
silently drifting.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geography import (
    LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, CELL_SIZE_DEG,
    GRID_SIZE_I, GRID_SIZE_J,
    cell_center,
    point_in_polygon,
    is_sea,
    region_of,
    build_cell_table,
    build_region_lookup,
    region_cell_counts,
    land_cells,
    REGION_NAMES,
    REGION_LABELS,
)

# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

def test_grid_dimensions():
    assert GRID_SIZE_I == 18
    assert GRID_SIZE_J == 32
    assert GRID_SIZE_I * GRID_SIZE_J == 576

def test_cell_center_corners():
    # i=0 is the northern row, j=0 is the western column.
    lat, lon = cell_center(0, 0)
    assert abs(lat - 46.75) < 1e-9
    assert abs(lon - 13.25) < 1e-9
    lat, lon = cell_center(GRID_SIZE_I - 1, GRID_SIZE_J - 1)
    assert abs(lat - 38.25) < 1e-9
    assert abs(lon - 28.75) < 1e-9

def test_cell_centers_inside_bounding_box():
    for i in range(GRID_SIZE_I):
        for j in range(GRID_SIZE_J):
            lat, lon = cell_center(i, j)
            assert LAT_MIN <= lat <= LAT_MAX
            assert LON_MIN <= lon <= LON_MAX

# ---------------------------------------------------------------------------
# Point-in-polygon
# ---------------------------------------------------------------------------

def test_point_in_polygon_square():
    square = [(0, 0), (0, 10), (10, 10), (10, 0)]
    assert point_in_polygon(5, 5, square) is True
    assert point_in_polygon(20, 5, square) is False
    assert point_in_polygon(-1, 5, square) is False

def test_point_in_polygon_triangle():
    triangle = [(0, 0), (10, 0), (5, 10)]
    assert point_in_polygon(5, 3, triangle) is True
    assert point_in_polygon(5, 11, triangle) is False

# ---------------------------------------------------------------------------
# Sea mask
# ---------------------------------------------------------------------------

def test_known_sea_points():
    # Middle of the Aegean (lat 38.5, lon 25) is sea.
    assert is_sea(38.5, 25.0) is True
    # Middle of the Adriatic (lat 43, lon 15) is sea.
    assert is_sea(43.0, 15.0) is True

def test_known_land_points():
    # Belgrade (44.81, 20.46) is land.
    assert is_sea(44.81, 20.46) is False
    # Sofia (42.7, 23.32) is land.
    assert is_sea(42.7, 23.32) is False
    # Thessaloniki (40.65, 22.95) is land.
    assert is_sea(40.65, 22.95) is False

# ---------------------------------------------------------------------------
# Region polygon classification
# ---------------------------------------------------------------------------

def test_named_regions_are_seven():
    assert len(REGION_NAMES) == 7
    assert set(REGION_NAMES) == {
        "Carpatho-Balkan Interior", "Pannonian Plain", "Aegean Littoral",
        "Peloponnese", "Albanian Highlands", "Adriatic Coastal",
        "Lower Danubian Frontier",
    }

def test_known_city_regions():
    # Belgrade should sit at the northwest tip of the Carpatho-Balkan
    # Interior polygon (the polygon starts at the Sava-Danube confluence
    # exactly at Belgrade).
    assert region_of(44.5, 21.0) == "Carpatho-Balkan Interior"
    # Sofia: deep inside Carpatho-Balkan Interior.
    assert region_of(42.7, 23.3) == "Carpatho-Balkan Interior"
    # Thessaloniki: Aegean Littoral.
    assert region_of(40.65, 22.95) == "Aegean Littoral"
    # Tirana (Albania): Albanian Highlands.
    assert region_of(41.3, 19.8) == "Albanian Highlands"
    # Split (Croatia, Dalmatian coast): Adriatic Coastal.
    assert region_of(43.5, 16.4) == "Adriatic Coastal"

def test_sea_check_runs_first():
    # A point inside an Aegean Littoral polygon vertex range but in the
    # open Aegean must classify as "sea", not as the region.
    assert region_of(39.0, 25.0) == "sea"

def test_region_label_set_closed():
    # Every cell on the grid classifies into one of the documented labels.
    table = build_cell_table()
    known = set(REGION_LABELS)
    for cell, info in table.items():
        assert info["region"] in known

# ---------------------------------------------------------------------------
# Calibration baseline — cell counts per region
# ---------------------------------------------------------------------------
# These are the actual counts produced by the current polygon vertex set
# (the spec's "actual counts should be recorded as the calibration
# baseline" guidance). If a follow-up commit retunes a polygon, update
# these expected values and document the retune in CHANGES_jlg.md.

EXPECTED_BASELINE_COUNTS = {
    "Carpatho-Balkan Interior": 79,
    "Pannonian Plain": 27,                # the geographic-foundation refinements B: +9 from Sava-Danube extension
    "Aegean Littoral": 35,                # the geographic-foundation refinements B/C: +15 central Greece + Chalkidiki overrides
    "Peloponnese": 4,                     # the geographic-foundation refinements D: structural; deferred fix
    "Albanian Highlands": 15,
    "Adriatic Coastal": 11,
    "Lower Danubian Frontier": 69,        # the geographic-foundation refinements B/C: +40 north + 3 Danube delta overrides
    "sea": 181,                           # the geographic-foundation refinements C: -6 from sea-mask land overrides (7 cells overridden; 1 was already land)
    "unassigned": 155,                    # the geographic-foundation refinements B: -58 absorbed by polygon extensions
}

def test_calibration_baseline_cell_counts():
    counts = region_cell_counts()
    for label, expected in EXPECTED_BASELINE_COUNTS.items():
        assert counts[label] == expected, (
            f"region {label!r}: expected {expected}, got {counts[label]}. "
            f"Polygon vertex set has drifted from the calibration baseline; "
            f"update EXPECTED_BASELINE_COUNTS and CHANGES_jlg.md."
        )
    assert sum(counts.values()) == GRID_SIZE_I * GRID_SIZE_J

def test_total_land_cell_count():
    land = land_cells()
    # 576 - 181 sea = 395 land cells after the geographic-foundation refinements C
    # added 7 sea-mask land overrides (Danube delta + Chalkidiki). Of
    # those 395 land cells, 240 are in one of the seven named regions
    # (the simulation-active study area) and 155 are unassigned (mostly
    # the Italian peninsula and the strip north of the Pannonian Plain
    # polygon - outside the historical Balkan study area). Documented
    # in the post-amendment verification report.
    assert len(land) == 395

def test_region_lookup_matches_cell_table():
    table = build_cell_table()
    lookup = build_region_lookup()
    assert len(lookup) == len(table)
    for cell, info in table.items():
        assert lookup[cell] == info["region"]

if __name__ == "__main__":
    # Run each test in alphabetical order for a quick CLI check.
    import inspect
    g = globals()
    tests = sorted(
        name for name, obj in g.items()
        if name.startswith("test_") and inspect.isfunction(obj)
    )
    failures = 0
    for name in tests:
        try:
            g[name]()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: {e}")
    print(f"\n{len(tests) - failures} / {len(tests)} passed")
    sys.exit(1 if failures else 0)
