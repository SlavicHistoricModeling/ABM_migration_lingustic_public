"""
Build the three summary tables from sweep_summary.csv.

Inputs:
  results/jlg_sweep/sweep_summary.csv   (one row per cell x region tuple)

Outputs:
  results/jlg_sweep/aggregate_by_scenario.csv
  results/jlg_sweep/per_region_year260_canonical.csv
  results/jlg_sweep/cbi_substrate_robustness.csv

Conventions:
  Canonical parameters:
    substrate_fraction = 0.30
    revassim_rate      = 0.015 (slavic1/2/3); 0.0 (arabic)
  "Aggregate share" per cell = land-weighted aggregate Slavic share across
    the seven named regions plus unassigned. Computed as
    sum(slavic_share * year_260_pop_mean) / sum(year_260_pop_mean).
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
RESULTS_ROOT = ENGINE_DIR / "results" / "jlg_sweep"
SWEEP_SUMMARY_CSV = RESULTS_ROOT / "sweep_summary.csv"

OUT_AGGREGATE = RESULTS_ROOT / "aggregate_by_scenario.csv"
OUT_PER_REGION_CANONICAL = RESULTS_ROOT / "per_region_year260_canonical.csv"
OUT_CBI_ROBUSTNESS = RESULTS_ROOT / "cbi_substrate_robustness.csv"

CANONICAL_SF = "0.30"
CANONICAL_RA_SLAVIC = "0.015"
CANONICAL_RA_ARABIC = "0.000"

SCENARIOS = ("slavic1", "slavic2", "slavic3", "arabic")
SUBSTRATE_CONFIGS = ("none", "uniform", "cbi_only")
REGION_BUCKETS = (
    "Carpatho-Balkan Interior",
    "Pannonian Plain",
    "Aegean Littoral",
    "Peloponnese",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Lower Danubian Frontier",
    "unassigned",
)

def load_sweep_summary() -> list[dict]:
    with SWEEP_SUMMARY_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def cell_key(row: dict) -> tuple[str, str, str, str]:
    return (row["scenario"], row["substrate_config"],
            row["substrate_fraction"], row["revassim_rate"])

def aggregate_share_for_cell(rows: list[dict]) -> float:
    """Land-weighted aggregate Slavic share across the eight buckets."""
    total_pop = 0.0
    total_slavic = 0.0
    for r in rows:
        pop = float(r["year_260_pop_mean"])
        share = float(r["year_260_slavic_share_mean"])
        total_pop += pop
        total_slavic += share * pop
    return total_slavic / total_pop if total_pop > 0 else 0.0

def build_aggregate_by_scenario(rows: list[dict]) -> None:
    by_cell: dict[tuple, list[dict]] = {}
    for r in rows:
        by_cell.setdefault(cell_key(r), []).append(r)
    cell_agg = {k: aggregate_share_for_cell(v) for k, v in by_cell.items()}

    out_rows = []
    for scen in SCENARIOS:
        for cfg in SUBSTRATE_CONFIGS:
            shares = [s for k, s in cell_agg.items()
                      if k[0] == scen and k[1] == cfg]
            if not shares:
                continue
            out_rows.append({
                "scenario": scen,
                "substrate_config": cfg,
                "aggregate_share_mean_across_params":
                    f"{statistics.mean(shares):.6f}",
                "aggregate_share_min": f"{min(shares):.6f}",
                "aggregate_share_max": f"{max(shares):.6f}",
                "n_cells": len(shares),
            })

    with OUT_AGGREGATE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "scenario", "substrate_config",
            "aggregate_share_mean_across_params",
            "aggregate_share_min", "aggregate_share_max", "n_cells",
        ])
        w.writeheader()
        w.writerows(out_rows)

def build_per_region_canonical(rows: list[dict]) -> None:
    out_rows = []
    for scen in SCENARIOS:
        ra = CANONICAL_RA_ARABIC if scen == "arabic" else CANONICAL_RA_SLAVIC
        for cfg in SUBSTRATE_CONFIGS:
            # `none` ignores substrate_fraction; the sweep uses sf030 for none.
            sf = CANONICAL_SF
            matching = [r for r in rows
                        if r["scenario"] == scen
                        and r["substrate_config"] == cfg
                        and r["substrate_fraction"] == sf
                        and r["revassim_rate"] == ra]
            if not matching:
                continue
            # Preserve REGION_BUCKETS order.
            by_region = {r["region"]: r for r in matching}
            for region in REGION_BUCKETS:
                r = by_region.get(region)
                if not r:
                    continue
                out_rows.append({
                    "scenario": scen,
                    "substrate_config": cfg,
                    "region": region,
                    "year_260_share_mean": r["year_260_slavic_share_mean"],
                    "year_260_share_sd": r["year_260_slavic_share_sd"],
                    "year_260_pop_mean": r["year_260_pop_mean"],
                })

    with OUT_PER_REGION_CANONICAL.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "scenario", "substrate_config", "region",
            "year_260_share_mean", "year_260_share_sd", "year_260_pop_mean",
        ])
        w.writeheader()
        w.writerows(out_rows)

def build_cbi_robustness(rows: list[dict]) -> None:
    out_rows = []
    for r in rows:
        if (r["scenario"] == "slavic1"
                and r["substrate_config"] == "cbi_only"
                and r["region"] == "Carpatho-Balkan Interior"):
            out_rows.append({
                "substrate_fraction": r["substrate_fraction"],
                "revassim_rate": r["revassim_rate"],
                "cbi_year260_share_mean": r["year_260_slavic_share_mean"],
                "cbi_year260_share_sd": r["year_260_slavic_share_sd"],
                "cbi_year260_pop_mean": r["year_260_pop_mean"],
            })
    out_rows.sort(key=lambda d: (float(d["substrate_fraction"]),
                                 float(d["revassim_rate"])))

    with OUT_CBI_ROBUSTNESS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "substrate_fraction", "revassim_rate",
            "cbi_year260_share_mean", "cbi_year260_share_sd",
            "cbi_year260_pop_mean",
        ])
        w.writeheader()
        w.writerows(out_rows)

def main() -> int:
    if not SWEEP_SUMMARY_CSV.exists():
        print(f"missing {SWEEP_SUMMARY_CSV}; run the sweep first.")
        return 1
    rows = load_sweep_summary()
    print(f"loaded {len(rows)} rows from {SWEEP_SUMMARY_CSV}")
    build_aggregate_by_scenario(rows)
    print(f"wrote {OUT_AGGREGATE}")
    build_per_region_canonical(rows)
    print(f"wrote {OUT_PER_REGION_CANONICAL}")
    build_cbi_robustness(rows)
    print(f"wrote {OUT_CBI_ROBUSTNESS}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
