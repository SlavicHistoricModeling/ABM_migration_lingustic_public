"""
Build the three sweep figures.

Inputs (read from results/jlg_sweep/):
  per_region_year260_canonical.csv
  cbi_substrate_robustness.csv
  sweep_summary.csv

Outputs (written to figures/jlg_sweep/):
  regional_outcomes_canonical.png      panel (a)
  cbi_substrate_heatmap.png            panel (b)
  coastal_substrate_decay.png          panel (c)

All figures: greyscale-readable (distinct hatches/line styles), 8.5 cm
single-column width target, PNG 300 dpi.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ENGINE_DIR = Path(__file__).resolve().parent.parent
RESULTS_ROOT = ENGINE_DIR / "results" / "jlg_sweep"
FIGURES_ROOT = ENGINE_DIR / "figures" / "jlg_sweep"
FIGURES_ROOT.mkdir(parents=True, exist_ok=True)

CM_TO_INCH = 1.0 / 2.54
SINGLE_COL_W_IN = 8.5 * CM_TO_INCH
DOUBLE_COL_W_IN = 17.4 * CM_TO_INCH

SCENARIOS = ("slavic1", "slavic2", "slavic3", "arabic")
SUBSTRATE_CONFIGS = ("none", "uniform", "cbi_only")
HATCHES = {"none": "", "uniform": "////", "cbi_only": "xxxx"}
GREYS = {"none": "0.85", "uniform": "0.55", "cbi_only": "0.25"}

REGION_DISPLAY_ORDER = (
    "Carpatho-Balkan Interior",
    "Aegean Littoral",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Peloponnese",
    "Pannonian Plain",
    "Lower Danubian Frontier",
    "unassigned",
)
COASTAL_REGIONS = (
    "Aegean Littoral",
    "Peloponnese",
    "Albanian Highlands",
    "Adriatic Coastal",
)
COASTAL_LINESTYLES = {
    "Aegean Littoral": "-",
    "Peloponnese": "--",
    "Albanian Highlands": ":",
    "Adriatic Coastal": "-.",
}

def load_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------------------
# Figure (a): regional_outcomes_canonical.png
# ---------------------------------------------------------------------------
def figure_regional_outcomes_canonical() -> None:
    rows = load_csv(RESULTS_ROOT / "per_region_year260_canonical.csv")
    by_key = {(r["scenario"], r["substrate_config"], r["region"]): r for r in rows}

    fig, axes = plt.subplots(4, 1, figsize=(SINGLE_COL_W_IN * 2.1, 9.5),
                             sharex=True, constrained_layout=True)

    n_regions = len(REGION_DISPLAY_ORDER)
    n_cfgs = len(SUBSTRATE_CONFIGS)
    bar_width = 0.26
    x = np.arange(n_regions)

    for ax, scen in zip(axes, SCENARIOS):
        for i, cfg in enumerate(SUBSTRATE_CONFIGS):
            heights = []
            errs = []
            for region in REGION_DISPLAY_ORDER:
                r = by_key.get((scen, cfg, region))
                if r is None:
                    heights.append(0.0)
                    errs.append(0.0)
                    continue
                heights.append(float(r["year_260_share_mean"]) * 100)
                errs.append(float(r["year_260_share_sd"]) * 100)
            offsets = (i - (n_cfgs - 1) / 2.0) * bar_width
            ax.bar(x + offsets, heights, width=bar_width,
                   yerr=errs, capsize=2,
                   color=GREYS[cfg], hatch=HATCHES[cfg],
                   edgecolor="black", linewidth=0.6,
                   label=cfg)
        ax.set_title(f"{scen}", fontsize=9, loc="left")
        ax.set_ylabel("year-260 Slavic share (%)", fontsize=8)
        ax.set_ylim(0, 105)
        ax.tick_params(axis="both", labelsize=7)
        ax.grid(axis="y", alpha=0.3, linewidth=0.4)

    # Highlight CBI bars across panels
    for ax in axes:
        cbi_idx = REGION_DISPLAY_ORDER.index("Carpatho-Balkan Interior")
        ax.axvspan(cbi_idx - 0.5, cbi_idx + 0.5,
                   color="gold", alpha=0.12, zorder=0)

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(
        [r.replace(" ", "\n", 1) for r in REGION_DISPLAY_ORDER],
        rotation=0, fontsize=7,
    )
    axes[0].legend(title="substrate_config", fontsize=7, title_fontsize=7,
                   loc="upper right", framealpha=0.95, ncol=3)
    fig.suptitle("Per-region year-260 Slavic share at canonical parameters\n"
                 "(substrate_fraction=0.30; revassim_rate=0.015 slavic, 0.000 arabic)",
                 fontsize=9)
    out = FIGURES_ROOT / "regional_outcomes_canonical.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")

# ---------------------------------------------------------------------------
# Figure (b): cbi_substrate_heatmap.png
# ---------------------------------------------------------------------------
def figure_cbi_substrate_heatmap() -> None:
    rows = load_csv(RESULTS_ROOT / "cbi_substrate_robustness.csv")
    sf_set = sorted({float(r["substrate_fraction"]) for r in rows})
    ra_set = sorted({float(r["revassim_rate"]) for r in rows})

    mean_grid = np.full((len(sf_set), len(ra_set)), np.nan)
    sd_grid = np.full((len(sf_set), len(ra_set)), np.nan)
    for r in rows:
        i = sf_set.index(float(r["substrate_fraction"]))
        j = ra_set.index(float(r["revassim_rate"]))
        mean_grid[i, j] = float(r["cbi_year260_share_mean"]) * 100
        sd_grid[i, j] = float(r["cbi_year260_share_sd"]) * 100

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W_IN * 1.4, SINGLE_COL_W_IN * 1.2),
                           constrained_layout=True)
    im = ax.imshow(mean_grid, aspect="auto", origin="lower", cmap="Greys",
                   vmin=0, vmax=max(np.nanmax(mean_grid), 1.0))
    ax.set_xticks(range(len(ra_set)))
    ax.set_xticklabels([f"{r:.3f}" for r in ra_set], fontsize=7)
    ax.set_yticks(range(len(sf_set)))
    ax.set_yticklabels([f"{s:.2f}" for s in sf_set], fontsize=7)
    ax.set_xlabel("reverse_assimilation_rate", fontsize=8)
    ax.set_ylabel("substrate_fraction", fontsize=8)
    ax.set_title("CBI year-260 Slavic share under cbi_only (slavic1)",
                 fontsize=8)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("year-260 Slavic share (%)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    for i in range(len(sf_set)):
        for j in range(len(ra_set)):
            v = mean_grid[i, j]
            sd = sd_grid[i, j]
            if np.isnan(v):
                continue
            txt_color = "white" if v > mean_grid.max() * 0.55 else "black"
            ax.text(j, i, f"{v:.1f}\n±{sd:.1f}",
                    ha="center", va="center", fontsize=6, color=txt_color)

    out = FIGURES_ROOT / "cbi_substrate_heatmap.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")

# ---------------------------------------------------------------------------
# Figure (c): coastal_substrate_decay.png
# ---------------------------------------------------------------------------
def figure_coastal_substrate_decay() -> None:
    rows = load_csv(RESULTS_ROOT / "sweep_summary.csv")
    canonical_ra = "0.015"

    sf_values = sorted({float(r["substrate_fraction"]) for r in rows
                        if r["substrate_config"] == "uniform"})

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W_IN * 1.5, SINGLE_COL_W_IN * 1.1),
                           constrained_layout=True)

    # Coastal lines (uniform, slavic1, canonical_ra).
    for region in COASTAL_REGIONS:
        ys = []
        for sf in sf_values:
            sf_str = f"{sf:.2f}"
            matches = [r for r in rows
                       if r["scenario"] == "slavic1"
                       and r["substrate_config"] == "uniform"
                       and r["substrate_fraction"] == sf_str
                       and r["revassim_rate"] == canonical_ra
                       and r["region"] == region]
            ys.append(float(matches[0]["year_260_slavic_share_mean"]) * 100
                      if matches else np.nan)
        ax.plot(sf_values, ys, marker="o",
                linestyle=COASTAL_LINESTYLES[region],
                color="black", linewidth=1.0, markersize=3.5,
                label=region)

    # CBI comparison line.
    cbi_ys = []
    for sf in sf_values:
        sf_str = f"{sf:.2f}"
        matches = [r for r in rows
                   if r["scenario"] == "slavic1"
                   and r["substrate_config"] == "uniform"
                   and r["substrate_fraction"] == sf_str
                   and r["revassim_rate"] == canonical_ra
                   and r["region"] == "Carpatho-Balkan Interior"]
        cbi_ys.append(float(matches[0]["year_260_slavic_share_mean"]) * 100
                      if matches else np.nan)
    ax.plot(sf_values, cbi_ys, marker="s",
            linestyle="-", color="0.4", linewidth=1.5, markersize=4.5,
            label="Carpatho-Balkan Interior")

    ax.set_xlabel("substrate_fraction", fontsize=8)
    ax.set_ylabel("year-260 Slavic share (%)", fontsize=8)
    ax.set_title(
        "Coastal substrate decay under uniform configuration "
        "(slavic1, revassim_rate=0.015)",
        fontsize=8,
    )
    ax.tick_params(axis="both", labelsize=7)
    ax.set_ylim(bottom=-2)
    ax.grid(alpha=0.3, linewidth=0.4)
    ax.legend(fontsize=6, framealpha=0.95, loc="upper left")

    out = FIGURES_ROOT / "coastal_substrate_decay.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")

def main() -> int:
    figure_regional_outcomes_canonical()
    figure_cbi_substrate_heatmap()
    figure_coastal_substrate_decay()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
