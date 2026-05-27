"""
Fortification dataset loader and proportional-anchoring algorithm
(the fortification anchoring).

The CSV at data/Justinain_Fortifications_with_Population_Estimates_clean.csv
lists 170 Justinian-era fortifications with c. 600 CE population estimates
expressed as a 50 % CI band ("low-high" in thousands). We parse each row
into a lat/lon/pop_band record, drop unparseable rows, classify each
fortification to one of the JLG geographic regions via point-in-polygon,
and provide an anchoring algorithm that redistributes a region's
non-Slavic agents toward its fortifications according to within-region
fortification weights.

The CSV provides spatial distribution and relative weights, NOT absolute
agent counts: total agents are governed by INITIAL_POP=5000 in the engine
(1 agent ~ 1000 individuals). Fortification anchoring is a within-region
redistribution that does not change total agent counts.
"""

from collections import defaultdict
import csv
import math
import os
from pathlib import Path

from geography import (
    CELL_SIZE_DEG,
    LAT_MAX,
    LON_MIN,
    SEA_MASK_LAND_OVERRIDES,
    build_cell_table,
    region_of,
)

DEFAULT_CSV_PATH = (Path(__file__).resolve().parent
                    / "data"
                    / "Justinain_Fortifications_with_Population_Estimates_clean.csv")

# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_pop_band(text):
    """Parse a CSV pop_band string into (low, mid, high) floats in thousands.

    The field looks like "8-15" (low-high in thousands of individuals).
    Returns None if the field is empty or cannot be parsed (caller logs
    and excludes the row).
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    if "-" not in text:
        return None
    lo_s, hi_s = text.split("-", 1)
    try:
        lo = float(lo_s.strip())
        hi = float(hi_s.strip())
    except ValueError:
        return None
    return (lo, (lo + hi) / 2.0, hi)

def load_fortifications(csv_path=None, log_excluded=False):
    """Load the fortifications CSV; return a list of dicts.

    Each returned dict has keys:
      name (str), country (str, may be ""), lat (float), lon (float),
      accuracy (str: "Exact" or other), pop_low_k, pop_mid_k, pop_high_k.

    Rows with missing/unparseable coordinates or population are dropped.
    If log_excluded is True, the dropped rows' names are printed to
    stderr so a verification log can record them.
    """
    if csv_path is None:
        csv_path = DEFAULT_CSV_PATH
    out = []
    excluded = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Fortification") or "").strip()
            country = (row.get("Modern Country") or "").strip()
            lat_s = (row.get("Latitude") or "").strip()
            lon_s = (row.get("Longitude") or "").strip()
            acc = (row.get("Accuracy") or "").strip()
            pop_s = (row.get("Pop_600AD_k(50%CI)") or "").strip()
            try:
                lat = float(lat_s)
                lon = float(lon_s)
            except ValueError:
                excluded.append((name, "bad coords"))
                continue
            band = _parse_pop_band(pop_s)
            if band is None:
                excluded.append((name, "bad pop"))
                continue
            lo, mid, hi = band
            out.append({
                "name": name,
                "country": country,
                "lat": lat,
                "lon": lon,
                "accuracy": acc,
                "pop_low_k": lo,
                "pop_mid_k": mid,
                "pop_high_k": hi,
            })
    if log_excluded and excluded:
        import sys
        for name, reason in excluded:
            print(f"fortifications: excluded row {name!r} ({reason})",
                  file=sys.stderr)
    return out

# ---------------------------------------------------------------------------
# Region attribution
# ---------------------------------------------------------------------------

def attribute_regions(forts):
    """Attach a "region" field (one of the JLG region labels) to each
    fortification in-place via the cell-table lookup. Returns forts.

    Each fort's lat/lon is mapped to its grid cell (i, j) and the cell's
    region label is read from the cell table. Using the cell table (not
    the bare point-in-polygon `region_of(lat, lon)`) means that the
    Amendment-C sea-mask land-overrides automatically apply: a fort whose
    raw coordinates would fall in a sea polygon but whose cell is in
    SEA_MASK_LAND_OVERRIDES picks up the overridden land region.

    Fortifications in still-unoverridden sea cells receive `"sea"`;
    fortifications outside every region polygon receive `"unassigned"`.
    Both groups remain in the list and are excluded from anchoring by
    fortifications_by_region().
    """
    table = build_cell_table()
    for f in forts:
        cell = latlon_to_cell(f["lat"], f["lon"])
        f["region"] = table[cell]["region"]
    return forts

def latlon_to_cell(lat, lon):
    """Inverse of geography.cell_center: return the grid (i, j) whose cell
    centre is closest to (lat, lon). Clamps to [0, GRID_SIZE_*).
    """
    from geography import GRID_SIZE_I, GRID_SIZE_J
    i = int(round((LAT_MAX - lat) / CELL_SIZE_DEG - 0.5))
    j = int(round((lon - LON_MIN) / CELL_SIZE_DEG - 0.5))
    i = max(0, min(GRID_SIZE_I - 1, i))
    j = max(0, min(GRID_SIZE_J - 1, j))
    return i, j

def fortifications_by_region(forts, pop_band="mid"):
    """Group fortifications by region label and compute within-region weights.

    Returns {region_label: [
        {name, lat, lon, cell, weight, pop_k}, ...
    ]} where weight = pop_k(F) / sum(pop_k for F in R) and pop_k is the
    selected band ("low" / "mid" / "high"). Regions with no fortifications
    or with zero total pop are omitted from the dict.
    """
    band_key = {"low": "pop_low_k", "mid": "pop_mid_k",
                "high": "pop_high_k"}[pop_band]
    grouped = defaultdict(list)
    for f in forts:
        region = f.get("region", "unassigned")
        if region in ("unassigned", "sea"):
            continue
        grouped[region].append({
            "name": f["name"],
            "lat": f["lat"],
            "lon": f["lon"],
            "cell": latlon_to_cell(f["lat"], f["lon"]),
            "pop_k": f[band_key],
        })
    out = {}
    for region, items in grouped.items():
        total = sum(item["pop_k"] for item in items)
        if total <= 0:
            continue
        for item in items:
            item["weight"] = item["pop_k"] / total
        out[region] = items
    return out

# ---------------------------------------------------------------------------
# Anchoring algorithm
# ---------------------------------------------------------------------------

def apply_fortification_anchoring(agents, grid, region_lookup,
                                  forts_by_region, anchor_fraction):
    """Redistribute non-Slavic agents within each region toward
    fortifications, in place.

    Args:
      agents:          the engine's list of agent dicts (mutated).
      grid:            the engine's grid[i][j] -> [agent_ids] (mutated).
      region_lookup:   {(i, j) -> region_label}.
      forts_by_region: output of fortifications_by_region(...).
      anchor_fraction: float in [0, 1]; share of each region's non-Slavic
                       agents to anchor to fortifications. 0 disables
                       anchoring entirely.

    Total agent count is preserved (asserted at function exit).
    Returns the number of agents moved.
    """
    if anchor_fraction <= 0.0:
        return 0

    initial_total = len(agents)

    # Collect non-Slavic agent ids per region.
    non_slavic_by_region = defaultdict(list)
    for a in agents:
        if a["language"] == "slavic":
            continue
        region = region_lookup.get((a["x"], a["y"]))
        if region in forts_by_region:
            non_slavic_by_region[region].append(a["id"])

    # id -> agent dict, for O(1) lookup.
    id_to_agent = {a["id"]: a for a in agents}

    moved_total = 0
    for region, fort_list in forts_by_region.items():
        candidates = non_slavic_by_region.get(region, [])
        if not candidates:
            continue
        n_region = len(candidates)
        # Anchor budget for this region.
        moves_per_fort = []
        for fort in fort_list:
            n_move = math.floor(n_region * anchor_fraction * fort["weight"])
            moves_per_fort.append(n_move)
        total_moves = sum(moves_per_fort)
        # Rounding remainder goes to the largest-weight fort in this region.
        # `max(..., key=...)` is deterministic when weights are unique;
        # in the rare tied case we fall back to first-in-list, which is
        # deterministic because the fort_list iteration order is the CSV
        # iteration order (Python 3.7+ dict insertion order).
        remainder = math.floor(n_region * anchor_fraction) - total_moves
        if remainder > 0 and fort_list:
            largest_idx = max(range(len(fort_list)),
                              key=lambda k: fort_list[k]["weight"])
            moves_per_fort[largest_idx] += remainder

        # Move agents. Use the first n_move candidates to each fort (the
        # candidate order is the agent-creation order, which is deterministic
        # at fixed seed).
        cursor = 0
        for fort, n_move in zip(fort_list, moves_per_fort):
            target_i, target_j = fort["cell"]
            for k in range(n_move):
                if cursor >= len(candidates):
                    break
                aid = candidates[cursor]
                cursor += 1
                agent = id_to_agent[aid]
                old_i, old_j = agent["x"], agent["y"]
                if (old_i, old_j) == (target_i, target_j):
                    continue
                # Remove from old cell.
                grid[old_i][old_j].remove(aid)
                # Move and add to target cell.
                agent["x"] = target_i
                agent["y"] = target_j
                grid[target_i][target_j].append(aid)
                moved_total += 1

    assert len(agents) == initial_total, (
        f"anchoring changed agent count: {initial_total} -> {len(agents)}"
    )
    return moved_total

if __name__ == "__main__":
    forts = load_fortifications(log_excluded=True)
    print(f"loaded {len(forts)} fortifications from {DEFAULT_CSV_PATH}")
    attribute_regions(forts)
    counts = defaultdict(int)
    for f in forts:
        counts[f["region"]] += 1
    print("fortifications by region:")
    for region in sorted(counts):
        print(f"  {region:<28} {counts[region]:>4}")
    grouped = fortifications_by_region(forts, pop_band="mid")
    print("\nfortifications grouped (mid band):")
    for region in sorted(grouped):
        items = grouped[region]
        total = sum(it["pop_k"] for it in items)
        print(f"  {region:<28} {len(items):>3} forts, total_pop_k={total:>6.1f}")
