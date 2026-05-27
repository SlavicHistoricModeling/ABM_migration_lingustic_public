"""Generate figures/regional_population_accounting.png (the per-region accounting figure).

Sanity-check figure: per-region total population trajectories across the
slavic1 scenario at seed 42, 10 runs, with no fortification anchoring
and no substrate. Mean lines per region with +/-1 SD shading. Reads
the per-region CSV produced by the per-region output phase-refactored engine, so the
canonical 10-run slavic1 (with anchoring 0, no substrate) must already
have been generated before running this script.

Expected pattern (per the per-region accounting figure):
  - Carpatho-Balkan Interior dominates by population (~2,000-2,600 agents)
  - Lower Danubian Frontier maintains its Slavic enclave
  - Aegean Littoral substantial population but ~0% Slavic
  - Other regions in the 100-400 range with effectively 0% Slavic
  - Unassigned bucket nonzero only if a cell hosts an out-of-region agent
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "results_slavic1_per_region.csv"
OUT_PATH = REPO_ROOT / "figures" / "regional_population_accounting.png"

# Eight bucket labels in the canonical order used by the engine output.
BUCKETS = (
    "Carpatho-Balkan Interior",
    "Pannonian Plain",
    "Aegean Littoral",
    "Peloponnese",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Lower Danubian Frontier",
    "unassigned",
)

BUCKET_COLOURS = {
    "Carpatho-Balkan Interior": "#5b8a3a",
    "Pannonian Plain":          "#d6a85a",
    "Aegean Littoral":          "#3d7ea6",
    "Peloponnese":              "#a64e6f",
    "Albanian Highlands":       "#8a5a3a",
    "Adriatic Coastal":         "#6fb1c2",
    "Lower Danubian Frontier":  "#bcbf3a",
    "unassigned":               "#888888",
}

def load_per_region_csv(path):
    """Return {bucket: {run: list-of-population-over-years}}."""
    by_bucket = defaultdict(lambda: defaultdict(list))
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            bucket = row["region"]
            run = int(row["run"])
            year = int(row["year"])
            pop = int(row["population"])
            # CSV rows arrive in (run, year, bucket) order; collect into
            # the right bin then sort by year below.
            by_bucket[bucket][run].append((year, pop))
    out = {}
    for bucket, runs in by_bucket.items():
        out[bucket] = {}
        for run, year_pop in runs.items():
            year_pop.sort()
            out[bucket][run] = [p for (_, p) in year_pop]
    return out

def mean_sd(by_bucket, bucket, num_years):
    """Return (mean_array, sd_array) of length num_years for a bucket."""
    runs = by_bucket[bucket]
    arr = np.array([runs[r] for r in sorted(runs)])
    mean = arr.mean(axis=0)
    sd = arr.std(axis=0, ddof=1) if arr.shape[0] > 1 else np.zeros_like(mean)
    return mean, sd

def main():
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run the 10-run slavic1 first:\n"
              f"  python slavic_migration_submited_v1.py --scenario slavic1 "
              f"--num_runs 10 --seed 42 --fortification_anchor_fraction 0.0",
              file=sys.stderr)
        sys.exit(1)

    by_bucket = load_per_region_csv(CSV_PATH)
    # Sniff num_years from one bucket+run.
    any_bucket = next(iter(by_bucket))
    any_run = next(iter(by_bucket[any_bucket]))
    num_years = len(by_bucket[any_bucket][any_run])

    fig, axes = plt.subplots(2, 4, figsize=(14, 6.5), sharex=True)
    axes = axes.flatten()
    years = np.arange(num_years)
    for ax, bucket in zip(axes, BUCKETS):
        if bucket not in by_bucket:
            ax.text(0.5, 0.5, f"no data for\n{bucket}",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=8, color="#888888")
            ax.set_title(bucket, fontsize=9)
            continue
        mean, sd = mean_sd(by_bucket, bucket, num_years)
        colour = BUCKET_COLOURS.get(bucket, "#444444")
        ax.plot(years, mean, color=colour, linewidth=1.2)
        ax.fill_between(years, mean - sd, mean + sd, color=colour, alpha=0.25)
        ax.set_title(bucket, fontsize=9)
        ax.set_xlim(0, num_years - 1)
        ax.set_ylim(bottom=0)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25, linewidth=0.4)

    for ax in axes[4:]:
        ax.set_xlabel("year (offset from scenario start)", fontsize=8)
    axes[0].set_ylabel("agents (mean over 10 runs)", fontsize=8)
    axes[4].set_ylabel("agents (mean over 10 runs)", fontsize=8)

    fig.suptitle("Per-region population trajectory — slavic1 seed 42, "
                 "10 runs, no anchoring, no substrate",
                 fontsize=11, y=0.995)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
    print(f"wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
