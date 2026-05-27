"""the geographic-map phase — Geographic map figures for the JLG paper.

Produces five publication-quality choropleth maps over the seven the geographic-foundation phase
named regions:

  Figure JLG-1: observed_toponym_density.png       (observed mid values)
  Figure JLG-2: modeled_cbi_only_year260.png       (slavic1 cbi_only canonical)
  Figure JLG-3: modeled_none_year260.png           (slavic1 none ra=0.030)
  Figure JLG-4: observed_vs_modeled_comparison.png (two-panel composite)
  Figure JLG-5: observed_minus_modeled_residuals.png (diverging residual map)

Plus greyscale-converted copies of every figure under
  figures/jlg_maps/_greyscale_check/
for the legibility check.

No new model runs; all numbers are read from existing tracked artifacts:
  data/observed_toponym_density.csv         (this package)
  results/jlg_sweep/sweep_summary.csv       (the parameter sweep)

Region polygons are re-imported from geography.REGION_POLYGONS to keep a
single source of truth.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

import cartopy.crs as ccrs
import cartopy.feature as cfeature

ENGINE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ENGINE_DIR))

from geography import (
    LAT_MAX, LAT_MIN, LON_MAX, LON_MIN,
    REGION_NAMES,
    REGION_POLYGONS,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OBSERVED_CSV = ENGINE_DIR / "data" / "observed_toponym_density.csv"
SWEEP_SUMMARY_CSV = ENGINE_DIR / "results" / "jlg_sweep" / "sweep_summary.csv"
MAPS_DIR = ENGINE_DIR / "figures" / "jlg_maps"
GREYSCALE_DIR = MAPS_DIR / "_greyscale_check"
CAPTIONS_DIR = MAPS_DIR / "captions"
MAPS_DIR.mkdir(parents=True, exist_ok=True)
GREYSCALE_DIR.mkdir(parents=True, exist_ok=True)
CAPTIONS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Figure sizing per the geographic-map phase spec
# ---------------------------------------------------------------------------
CM_TO_INCH = 1.0 / 2.54
SINGLE_COL_IN = 8.5 * CM_TO_INCH       # 3.35"
DOUBLE_COL_IN = 17.4 * CM_TO_INCH      # 6.85"

# Manual label-anchor overrides for regions whose geometric centroid lands
# in an awkward place (Peloponnese centroid sits outside the bounding box
# at lat 36.5; Lower Danubian Frontier's centroid sits near the Danube
# delta which crowds the colorbar). Each entry is (lat, lon).
LABEL_OVERRIDES = {
    "Peloponnese": (38.20, 22.50),
    "Lower Danubian Frontier": (45.00, 26.00),
    "Pannonian Plain": (45.80, 19.00),
    "Carpatho-Balkan Interior": (43.30, 23.00),
    "Aegean Littoral": (40.40, 23.50),
    "Albanian Highlands": (41.30, 20.20),
    "Adriatic Coastal": (43.40, 16.80),
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_observed_mid() -> dict[str, float]:
    """Map region -> observed_density_mid from the CSV."""
    out = {}
    with OBSERVED_CSV.open("r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["region"]] = float(r["observed_density_mid"])
    return out

def load_sweep_share(scenario: str, substrate_config: str,
                     substrate_fraction: str, revassim_rate: str
                     ) -> dict[str, float]:
    """Map region -> year_260 mean Slavic share for one sweep cell.

    Reads results/jlg_sweep/sweep_summary.csv and filters by the four
    parameter columns. Returns only the seven named regions (drops
    'unassigned' since the map figures don't paint it).
    """
    out = {}
    with SWEEP_SUMMARY_CSV.open("r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["scenario"] == scenario
                    and r["substrate_config"] == substrate_config
                    and r["substrate_fraction"] == substrate_fraction
                    and r["revassim_rate"] == revassim_rate
                    and r["region"] in REGION_NAMES):
                out[r["region"]] = float(r["year_260_slavic_share_mean"])
    return out

# ---------------------------------------------------------------------------
# Core choropleth renderer
# ---------------------------------------------------------------------------
def _add_basemap(ax) -> None:
    ax.set_extent([LON_MIN, LON_MAX, LAT_MIN, LAT_MAX], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.OCEAN.with_scale("50m"),
                   facecolor="#eef4fa", edgecolor="none", zorder=0)
    ax.add_feature(cfeature.LAND.with_scale("50m"),
                   facecolor="#f6f3ec", edgecolor="none", zorder=0)
    ax.coastlines(resolution="50m", linewidth=0.4,
                  color="#666666", alpha=0.6, zorder=4)
    gl = ax.gridlines(draw_labels=True, linewidth=0.2, color="#aaaaaa",
                      alpha=0.5, linestyle="--", zorder=5)
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 4}
    gl.ylabel_style = {"size": 4}

def _draw_region_polygons(ax, values: dict[str, float], cmap, norm) -> None:
    """Fill each region polygon with its value's colour and outline it."""
    for region in REGION_NAMES:
        poly = REGION_POLYGONS[region]
        ys = [v[0] for v in poly]
        xs = [v[1] for v in poly]
        v = values.get(region)
        if v is None:
            color = "#dddddd"
        else:
            color = cmap(norm(v))
        ax.fill(xs, ys, color=color, edgecolor="#222222", linewidth=0.4,
                alpha=0.85, zorder=2, transform=ccrs.PlateCarree())

def _draw_region_labels(ax, values: dict[str, float]) -> None:
    """Per-region label at LABEL_OVERRIDES anchor with value below the name."""
    for region in REGION_NAMES:
        lat, lon = LABEL_OVERRIDES[region]
        v = values.get(region)
        v_str = f"{v*100:.1f}%" if v is not None else "n/a"
        # Two-line label: region short name on top, value on bottom.
        short = region.replace("Carpatho-Balkan Interior", "CBI") \
                      .replace("Lower Danubian Frontier", "Lower Danube") \
                      .replace("Albanian Highlands", "Albanian") \
                      .replace("Aegean Littoral", "Aegean") \
                      .replace("Adriatic Coastal", "Adriatic") \
                      .replace("Pannonian Plain", "Pannonia") \
                      .replace("Peloponnese", "Peloponnese*")
        ax.text(lon, lat, f"{short}\n{v_str}",
                transform=ccrs.PlateCarree(),
                ha="center", va="center",
                fontsize=4.5, color="black",
                bbox=dict(facecolor="white", alpha=0.75,
                          edgecolor="none", pad=1.0),
                zorder=6)

def render_choropleth(values: dict[str, float], title: str,
                      output_path: Path, colorbar_label: str,
                      cmap_name: str = "viridis",
                      vmin: float = 0.0, vmax: float = 1.0) -> None:
    cmap = matplotlib.colormaps[cmap_name]
    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)

    fig = plt.figure(figsize=(SINGLE_COL_IN, SINGLE_COL_IN * 0.95), dpi=300)
    ax = plt.axes(projection=ccrs.PlateCarree())
    _add_basemap(ax)
    _draw_region_polygons(ax, values, cmap, norm)
    _draw_region_labels(ax, values)
    ax.set_title(title, fontsize=6)

    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal",
                        fraction=0.05, pad=0.08, shrink=0.85)
    cbar.set_label(colorbar_label, fontsize=5)
    cbar.ax.tick_params(labelsize=4)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {output_path}")

def render_comparison(values_left: dict[str, float],
                      values_right: dict[str, float],
                      titles: tuple[str, str],
                      output_path: Path, colorbar_label: str,
                      cmap_name: str = "viridis",
                      vmin: float = 0.0, vmax: float = 1.0) -> None:
    cmap = matplotlib.colormaps[cmap_name]
    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)

    fig = plt.figure(figsize=(DOUBLE_COL_IN, DOUBLE_COL_IN * 0.55), dpi=300)
    for col, (vals, title) in enumerate(
        [(values_left, titles[0]), (values_right, titles[1])]
    ):
        ax = fig.add_subplot(1, 2, col + 1, projection=ccrs.PlateCarree())
        _add_basemap(ax)
        _draw_region_polygons(ax, vals, cmap, norm)
        _draw_region_labels(ax, vals)
        ax.set_title(title, fontsize=6)

    fig.subplots_adjust(left=0.03, right=0.97, top=0.93,
                        bottom=0.18, wspace=0.08)
    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes([0.20, 0.10, 0.60, 0.025])
    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.set_label(colorbar_label, fontsize=5)
    cbar.ax.tick_params(labelsize=4)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {output_path}")

def render_residuals(observed: dict[str, float], modeled: dict[str, float],
                     output_path: Path) -> None:
    residuals = {r: observed[r] - modeled.get(r, 0.0) for r in REGION_NAMES}
    max_abs = max(abs(v) for v in residuals.values())
    vmax = max(max_abs, 0.01)
    vmin = -vmax
    cmap = matplotlib.colormaps["RdBu_r"]
    norm = matplotlib.colors.TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)

    fig = plt.figure(figsize=(SINGLE_COL_IN, SINGLE_COL_IN * 0.95), dpi=300)
    ax = plt.axes(projection=ccrs.PlateCarree())
    _add_basemap(ax)
    _draw_region_polygons(ax, residuals, cmap, norm)
    _draw_region_labels(ax, residuals)
    ax.set_title("Observed minus modeled (cbi_only) residuals", fontsize=6)

    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal",
                        fraction=0.05, pad=0.08, shrink=0.85)
    cbar.set_label("Residual (observed minus modeled)", fontsize=5)
    cbar.ax.tick_params(labelsize=4)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {output_path}")
    return residuals

# ---------------------------------------------------------------------------
# Greyscale-check copies
# ---------------------------------------------------------------------------
def make_greyscale_copy(src: Path, dst_dir: Path) -> Path:
    img = Image.open(src).convert("L")
    dst = dst_dir / src.name
    img.save(dst, "PNG")
    print(f"  -> greyscale copy {dst}")
    return dst

# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------
CAPTIONS = {
    "figure_jlg_1_caption.txt": (
        "Figure 1. Observed Slavic toponym density across the seven regions "
        "of the Balkan study area, expressed as the proportion of recorded "
        "place names of Slavic origin per region. Values represent midpoint "
        "estimates from the cited toponymic surveys: central-Balkan ~85% per "
        "Skok (1971-1974), Loma (2002), and Zaimov (1973); Albanian Highlands "
        "~25% per Ylli (2000); Peloponnese ~20% per Vasmer (1941) and "
        "Malingoudis (1981); Adriatic and Aegean coastal regions retain "
        "Romance and Greek vernaculars with limited Slavic toponymic "
        "deposition. Region polygon definitions from the present paper's "
        "Section 5. Peloponnese region has lower statistical resolution "
        "due to four-cell grid coverage; see Section 5 limitations."
    ),
    "figure_jlg_2_caption.txt": (
        "Figure 2. Modeled Slavic linguistic share at year 260 under the "
        "substrate-in-Carpatho-Balkan-Interior (cbi_only) configuration of "
        "the agent-based model, with substrate_fraction = 0.30, "
        "reverse_assimilation_rate = 0.030 (the engine default for "
        "scenario slavic1), and fortification_anchor_fraction = 0.30. Values "
        "are mean year-260 shares across 10 seed-42 model runs (per "
        "results/jlg_sweep/sweep_summary.csv). The cbi_only configuration "
        "places the substrate Slavic population only in the Carpatho-Balkan "
        "Interior region; the four coastal destinations retain near-zero "
        "Slavic share through year 260, qualitatively reproducing the "
        "observed regional gradient (cf. Figure 1). Peloponnese has lower "
        "statistical resolution due to four-cell grid coverage."
    ),
    "figure_jlg_3_caption.txt": (
        "Figure 3. Modeled Slavic linguistic share at year 260 under the "
        "no-substrate (none) configuration of the agent-based model, with "
        "reverse_assimilation_rate = 0.030 and "
        "fortification_anchor_fraction = 0.30. Values are mean year-260 "
        "shares across 10 seed-42 model runs. Under the no-substrate null "
        "hypothesis, only the two source regions (Pannonian Plain, Lower "
        "Danubian Frontier) and a small Carpatho-Balkan Interior fraction "
        "retain measurable Slavic share; all four coastal destinations "
        "decay to near-zero. This is the configuration the prior the parent submission "
        "submission's negative result corresponds to. Peloponnese has lower "
        "statistical resolution."
    ),
    "figure_jlg_4_caption.txt": (
        "Figure 4. Side-by-side comparison: (a) observed Slavic toponym "
        "density per region (per Figure 1 sources) and (b) modeled Slavic "
        "share at year 260 under the cbi_only configuration at canonical "
        "parameters (substrate_fraction = 0.30, reverse_assimilation_rate "
        "= 0.030, fortification_anchor_fraction = 0.30; mean over 10 "
        "seed-42 runs). Both panels share the viridis colormap on a [0, 1] "
        "scale. The cbi_only configuration qualitatively reproduces the "
        "observed CBI-high / coast-low gradient. Magnitude differences "
        "remain, particularly in Carpatho-Balkan Interior (observed ~85% "
        "vs. modeled ~15%); these are discussed in the paper's Section 6. "
        "Peloponnese has lower statistical resolution; Adriatic Coastal "
        "observed value averages inland (~25%) and urban-coastal (~5%) "
        "heterogeneity."
    ),
    "figure_jlg_5_caption.txt": (
        "Figure 5. Per-region residuals (observed minus modeled, cbi_only) "
        "of the Slavic linguistic share at year 260. Diverging RdBu_r "
        "colormap centered at zero; positive residuals (red) indicate "
        "observed > modeled (the model under-predicts Slavic presence), "
        "negative residuals (blue) indicate observed < modeled "
        "(over-prediction). Carpatho-Balkan Interior shows the largest "
        "positive residual (observed ~85%, modeled ~15%, residual ~+70 pp), "
        "indicating the model captures the qualitative geographic pattern "
        "but under-predicts the magnitude of interior substrate persistence. "
        "Lower Danubian Frontier shows a small negative residual "
        "(observed ~70%, modeled ~81%, residual ~-11 pp). Coastal residuals "
        "(Aegean, Peloponnese, Albanian, Adriatic) are small to moderate "
        "in absolute terms because the modeled values cluster near zero "
        "while observed values are also low (under 25%)."
    ),
}

def write_captions() -> None:
    for fname, text in CAPTIONS.items():
        path = CAPTIONS_DIR / fname
        path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {path}")

# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def main() -> int:
    observed = load_observed_mid()
    modeled_cbi = load_sweep_share("slavic1", "cbi_only", "0.30", "0.030")
    modeled_none = load_sweep_share("slavic1", "none", "0.30", "0.030")

    if set(observed) != set(REGION_NAMES):
        raise SystemExit(f"observed CSV missing regions: "
                         f"{set(REGION_NAMES) - set(observed)}")
    if set(modeled_cbi) != set(REGION_NAMES):
        raise SystemExit(f"sweep CSV missing cbi_only canonical cell regions: "
                         f"{set(REGION_NAMES) - set(modeled_cbi)}")
    if set(modeled_none) != set(REGION_NAMES):
        raise SystemExit(f"sweep CSV missing none canonical cell regions: "
                         f"{set(REGION_NAMES) - set(modeled_none)}")

    fig1 = MAPS_DIR / "observed_toponym_density.png"
    fig2 = MAPS_DIR / "modeled_cbi_only_year260.png"
    fig3 = MAPS_DIR / "modeled_none_year260.png"
    fig4 = MAPS_DIR / "observed_vs_modeled_comparison.png"
    fig5 = MAPS_DIR / "observed_minus_modeled_residuals.png"

    render_choropleth(observed,
                      title="Observed Slavic toponym density by region",
                      output_path=fig1,
                      colorbar_label="Slavic toponym density "
                                     "(proportion of recorded names)")
    render_choropleth(modeled_cbi,
                      title="Modeled Slavic share at year 260 - "
                            "substrate in CBI",
                      output_path=fig2,
                      colorbar_label="Modeled Slavic share "
                                     "(proportion of regional population)")
    render_choropleth(modeled_none,
                      title="Modeled Slavic share at year 260 - no substrate",
                      output_path=fig3,
                      colorbar_label="Modeled Slavic share "
                                     "(proportion of regional population)")
    render_comparison(observed, modeled_cbi,
                      titles=("(a) Observed Slavic toponym density",
                              "(b) Modeled Slavic share at year 260 "
                              "(cbi_only)"),
                      output_path=fig4,
                      colorbar_label="Slavic share / density "
                                     "(proportion; 0.0 - 1.0)")
    residuals = render_residuals(observed, modeled_cbi, fig5)

    for src in (fig1, fig2, fig3, fig4, fig5):
        make_greyscale_copy(src, GREYSCALE_DIR)

    write_captions()

    # Print the per-region observed-vs-modeled table for the verification
    # report. Captured by the verification step.
    print()
    print("region,observed_mid,modeled_cbi_only,modeled_none,residual_obs_minus_cbi")
    for region in REGION_NAMES:
        o = observed[region]
        m_cbi = modeled_cbi[region]
        m_none = modeled_none[region]
        print(f"{region},{o:.4f},{m_cbi:.4f},{m_none:.4f},{residuals[region]:+.4f}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
