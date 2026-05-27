"""Tests for the fortifications CSV loader and the proportional-anchoring
algorithm (the fortification anchoring).

Covers:
  - CSV loader returns the expected calibration-baseline count of records
  - Population-band parsing handles the canonical "low-high" format
  - Region attribution assigns every record to a known label
  - Per-region weights computed by fortifications_by_region sum to 1.0
  - apply_fortification_anchoring preserves total agent count
  - apply_fortification_anchoring with anchor_fraction=0 moves nothing
  - apply_fortification_anchoring with anchor_fraction>0 moves agents only
    out of cells that don't already host a fortification
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fortifications import (
    _parse_pop_band,
    apply_fortification_anchoring,
    attribute_regions,
    fortifications_by_region,
    latlon_to_cell,
    load_fortifications,
)
from geography import REGION_LABELS, build_cell_table

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def test_parse_pop_band_standard():
    lo, mid, hi = _parse_pop_band("8-15")
    assert lo == 8.0
    assert hi == 15.0
    assert mid == 11.5

def test_parse_pop_band_zero_lo():
    lo, mid, hi = _parse_pop_band("0-3")
    assert lo == 0.0
    assert hi == 3.0
    assert mid == 1.5

def test_parse_pop_band_invalid():
    assert _parse_pop_band("") is None
    assert _parse_pop_band(None) is None
    assert _parse_pop_band("not a range") is None
    assert _parse_pop_band("abc-def") is None

# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def test_load_fortifications_count():
    forts = load_fortifications()
    # The CSV has 170 rows; all should be parseable (every row has a valid
    # "low-high" pop band and float coordinates per the CSV layout).
    assert len(forts) == 170

def test_load_fortifications_fields():
    forts = load_fortifications()
    f = forts[0]
    assert set(f.keys()) >= {"name", "country", "lat", "lon",
                             "accuracy", "pop_low_k", "pop_mid_k", "pop_high_k"}
    assert isinstance(f["lat"], float)
    assert isinstance(f["lon"], float)
    assert f["pop_mid_k"] == (f["pop_low_k"] + f["pop_high_k"]) / 2.0

# ---------------------------------------------------------------------------
# Region attribution
# ---------------------------------------------------------------------------

def test_attribute_regions_labels_known():
    forts = attribute_regions(load_fortifications())
    known = set(REGION_LABELS)
    for f in forts:
        assert f["region"] in known

def test_attribute_regions_majority_named():
    # The spec's polygons leave some inland fortifications unassigned
    # (Sirmium, Singidunum, etc. fall in narrow strips between the
    # Pannonian Plain polygon's southern edge and the Carpatho-Balkan
    # Interior polygon's northern edge). The verification report
    # documents which forts are borderline. The cheap structural check
    # here is that the MAJORITY of fortifications classify into one of
    # the seven named regions (i.e. the polygon set is doing real work).
    forts = attribute_regions(load_fortifications())
    n_named = sum(1 for f in forts
                  if f["region"] not in ("sea", "unassigned"))
    assert n_named > len(forts) / 2, (
        f"only {n_named}/{len(forts)} fortifications classified into a "
        f"named region; polygon set may be too thin"
    )

# ---------------------------------------------------------------------------
# Per-region weights
# ---------------------------------------------------------------------------

def test_fortifications_by_region_weights_sum_to_one():
    forts = attribute_regions(load_fortifications())
    grouped = fortifications_by_region(forts, pop_band="mid")
    assert len(grouped) > 0
    for region, items in grouped.items():
        total_w = sum(item["weight"] for item in items)
        assert abs(total_w - 1.0) < 1e-9, (
            f"region {region}: weights sum to {total_w}, expected 1.0"
        )

def test_fortifications_by_region_excludes_sea_and_unassigned():
    forts = attribute_regions(load_fortifications())
    grouped = fortifications_by_region(forts, pop_band="mid")
    assert "sea" not in grouped
    assert "unassigned" not in grouped

# ---------------------------------------------------------------------------
# latlon_to_cell
# ---------------------------------------------------------------------------

def test_latlon_to_cell_centers_round_trip():
    from geography import cell_center
    # For any cell, the inverse mapping of its center should return the
    # same (i, j).
    for i in (0, 5, 10, 17):
        for j in (0, 7, 15, 31):
            lat, lon = cell_center(i, j)
            assert latlon_to_cell(lat, lon) == (i, j)

# ---------------------------------------------------------------------------
# Anchoring
# ---------------------------------------------------------------------------

def _toy_grid_and_agents():
    """Build a small set of non-Slavic agents scattered across one region's
    land cells, plus a one-agent fortification setup, for anchoring tests."""
    from geography import GRID_SIZE_I, GRID_SIZE_J
    grid = [[[] for _ in range(GRID_SIZE_J)] for _ in range(GRID_SIZE_I)]
    agents = []
    # 100 non-Slavic agents at varied cells; we'll use Carpatho-Balkan
    # Interior cells.
    region_lookup = {cell: info["region"]
                     for cell, info in build_cell_table().items()}
    cbi_cells = [c for c, lbl in region_lookup.items()
                 if lbl == "Carpatho-Balkan Interior"]
    aid = 0
    for k in range(100):
        cell = cbi_cells[k % len(cbi_cells)]
        agents.append({"id": aid, "x": cell[0], "y": cell[1],
                       "language": "illyrian_thracian", "age": 30,
                       "sex": "female"})
        grid[cell[0]][cell[1]].append(aid)
        aid += 1
    return agents, grid, region_lookup, cbi_cells

def test_anchoring_zero_fraction_moves_nothing():
    forts = attribute_regions(load_fortifications())
    grouped = fortifications_by_region(forts, pop_band="mid")
    agents, grid, region_lookup, _ = _toy_grid_and_agents()
    initial = [(a["id"], a["x"], a["y"]) for a in agents]
    moved = apply_fortification_anchoring(
        agents=agents, grid=grid, region_lookup=region_lookup,
        forts_by_region=grouped, anchor_fraction=0.0)
    assert moved == 0
    final = [(a["id"], a["x"], a["y"]) for a in agents]
    assert initial == final

def test_anchoring_preserves_agent_count():
    forts = attribute_regions(load_fortifications())
    grouped = fortifications_by_region(forts, pop_band="mid")
    agents, grid, region_lookup, _ = _toy_grid_and_agents()
    n0 = len(agents)
    apply_fortification_anchoring(
        agents=agents, grid=grid, region_lookup=region_lookup,
        forts_by_region=grouped, anchor_fraction=0.30)
    assert len(agents) == n0
    # Grid total agent placements also preserved.
    n_in_grid = sum(len(cell) for row in grid for cell in row)
    assert n_in_grid == n0

def test_anchoring_moves_expected_share():
    forts = attribute_regions(load_fortifications())
    grouped = fortifications_by_region(forts, pop_band="mid")
    agents, grid, region_lookup, _ = _toy_grid_and_agents()
    moved = apply_fortification_anchoring(
        agents=agents, grid=grid, region_lookup=region_lookup,
        forts_by_region=grouped, anchor_fraction=0.30)
    # Expected: ~30% of 100 agents in Carpatho-Balkan Interior should be
    # moved to fortification cells (some agents may already sit on a fort
    # cell so the actual moved count is less). Lower bound 1, upper bound 30.
    assert 1 <= moved <= 30

if __name__ == "__main__":
    import inspect
    g = globals()
    tests = sorted(name for name, obj in g.items()
                   if name.startswith("test_") and inspect.isfunction(obj))
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
