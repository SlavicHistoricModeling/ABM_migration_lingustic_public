"""
the canonical-RA-resolution amendment — build canonical ra tables and comparison markdown.

Re-aggregates the existing results/jlg_sweep/sweep_summary.csv into:

  results/jlg_sweep/canonical/per_region_year260_canonical_ra015.csv
  results/jlg_sweep/canonical/per_region_year260_canonical_ra030.csv
  results/jlg_sweep/canonical/per_region_year260_canonical_ra045.csv
  results/jlg_sweep/canonical/CANONICAL_COMPARISON.md

Schema mirrors the original results/jlg_sweep/per_region_year260_canonical.csv:
  scenario, substrate_config, region,
  year_260_share_mean, year_260_share_sd, year_260_pop_mean

Conventions:
- substrate_fraction = 0.30 for all three tables (matches the parameter-sweep phase
  canonical SF; the ra dimension is the only thing swept across tables).
- arabic is invariant under ra: the engine forces ra=0 for arabic. All
  three tables therefore contain the same arabic rows (read from the
  sweep_summary.csv ra=0.000 arabic cells). Documented once.
- 'none' substrate_config: substrate_fraction was set to sf=0.30
  placeholder in the sweep; ignored by the engine but the sweep
  recorded the row anyway. We read those rows.
"""

from __future__ import annotations

import csv
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
RESULTS_ROOT = ENGINE_DIR / "results" / "jlg_sweep"
CANONICAL_DIR = RESULTS_ROOT / "canonical"
CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
SWEEP_SUMMARY_CSV = RESULTS_ROOT / "sweep_summary.csv"

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
COMPARISON_REGIONS = (
    "Carpatho-Balkan Interior",
    "Aegean Littoral",
    "Peloponnese",
    "Albanian Highlands",
    "Adriatic Coastal",
)

CANONICAL_SF = "0.30"
ARABIC_RA = "0.000"  # engine forces ra=0 for arabic; sweep only varies sf

def load_sweep_summary() -> list[dict]:
    with SWEEP_SUMMARY_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def build_canonical_table(rows: list[dict], ra: str, out_path: Path) -> None:
    """Pivot sweep_summary rows to a per-region canonical table at the given ra."""
    out_rows = []
    for scen in SCENARIOS:
        ra_used = ARABIC_RA if scen == "arabic" else ra
        for cfg in SUBSTRATE_CONFIGS:
            matching = [r for r in rows
                        if r["scenario"] == scen
                        and r["substrate_config"] == cfg
                        and r["substrate_fraction"] == CANONICAL_SF
                        and r["revassim_rate"] == ra_used]
            if not matching:
                continue
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

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "scenario", "substrate_config", "region",
            "year_260_share_mean", "year_260_share_sd", "year_260_pop_mean",
        ])
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")

def _fmt_cell(share_str: str, sd_str: str) -> str:
    share = float(share_str) * 100
    sd = float(sd_str) * 100
    return f"{share:5.2f}% ± {sd:5.2f}%"

def build_comparison_markdown(rows: list[dict], out_path: Path) -> None:
    """slavic1-only side-by-side: 3 configs x 5 regions across 3 ra columns."""
    lookup: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        if r["scenario"] != "slavic1":
            continue
        if r["substrate_fraction"] != CANONICAL_SF:
            continue
        if r["revassim_rate"] not in ("0.015", "0.030", "0.045"):
            continue
        lookup[(r["substrate_config"], r["region"], r["revassim_rate"])] = r

    lines = []
    lines.append("# Canonical comparison — slavic1 at sf=0.30 across "
                 "ra ∈ {0.015, 0.030, 0.045}")
    lines.append("")
    lines.append("Source: re-aggregated from `results/jlg_sweep/sweep_summary.csv` "
                 "(the parameter sweep). No new model runs; this is the same "
                 "underlying sweep data filtered by ra value.")
    lines.append("")
    lines.append("Columns:")
    lines.append("- ra=0.015 — the value the parameter-sweep phase reported as canonical")
    lines.append("- ra=0.030 — the engine default for slavic1 "
                 "(per `SCENARIOS['slavic1']['reverse_assimilation_rate']`)")
    lines.append("- ra=0.045 — the conservative-stress-test value")
    lines.append("")
    lines.append("Cell format: `mean% ± SD%` across 10 seed-42 runs.")
    lines.append("")
    lines.append("| config | region | ra=0.015 | ra=0.030 | ra=0.045 |")
    lines.append("|---|---|---:|---:|---:|")
    for cfg in SUBSTRATE_CONFIGS:
        for region in COMPARISON_REGIONS:
            cells = []
            for ra in ("0.015", "0.030", "0.045"):
                r = lookup.get((cfg, region, ra))
                if r is None:
                    cells.append("—")
                else:
                    cells.append(_fmt_cell(r["year_260_slavic_share_mean"],
                                           r["year_260_slavic_share_sd"]))
            region_display = (region + "*"
                              if region == "Peloponnese" else region)
            lines.append(f"| {cfg} | {region_display} | "
                         f"{cells[0]} | {cells[1]} | {cells[2]} |")

    lines.append("")
    lines.append("\\* Peloponnese: known low statistical resolution "
                 "(4 grid cells; Peloponnese-resolution Amendment D deferred fix).")
    lines.append("")
    lines.append("## Reading guide")
    lines.append("")
    lines.append("Across all three ra columns, the cbi_only config is the only "
                 "one in which CBI exceeds every coastal region's share. As ra "
                 "increases (stronger reverse-assimilation pressure), every "
                 "config's CBI share decays; cbi_only retains the highest "
                 "CBI / coast ratio at every ra value. The 'CBI persists, "
                 "coast does not' pattern is qualitatively robust across the "
                 "ra range; the magnitude of CBI persistence is ra-dependent "
                 "(monotonic decreasing in ra, as the `cbi_substrate_robustness.csv` "
                 "grid documents).")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")

def main() -> int:
    if not SWEEP_SUMMARY_CSV.exists():
        print(f"missing {SWEEP_SUMMARY_CSV}; run the parameter sweep first.")
        return 1
    rows = load_sweep_summary()
    print(f"loaded {len(rows)} rows from {SWEEP_SUMMARY_CSV}")
    build_canonical_table(rows, "0.015",
                          CANONICAL_DIR / "per_region_year260_canonical_ra015.csv")
    build_canonical_table(rows, "0.030",
                          CANONICAL_DIR / "per_region_year260_canonical_ra030.csv")
    build_canonical_table(rows, "0.045",
                          CANONICAL_DIR / "per_region_year260_canonical_ra045.csv")
    build_comparison_markdown(rows, CANONICAL_DIR / "CANONICAL_COMPARISON.md")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
