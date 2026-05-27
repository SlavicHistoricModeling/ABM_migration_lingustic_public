"""Generate figures/geographic_foundation.png (the geographic-foundation figure).

Map figure showing the JLG coordinate-anchored grid:
  - the bounding box (lat 38-47 N, lon 13-29 E) under PlateCarree projection
  - each land cell coloured by region label (7 named regions + unassigned)
  - the seven region polygon outlines drawn over the cell grid
  - Justinian fortifications overlaid as proportional-sized markers
    (marker area ~ pop_mid_k, so radius ~ sqrt(pop_mid_k))
  - distinct hatching per region for greyscale legibility at 8.5 cm width
"""

import math
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

import cartopy.crs as ccrs
import cartopy.feature as cfeature

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fortifications import attribute_regions, load_fortifications
from geography import (
    CELL_SIZE_DEG,
    LAT_MAX, LAT_MIN, LON_MAX, LON_MIN,
    REGION_NAMES,
    REGION_POLYGONS,
    build_cell_table,
    cell_center,
)

# Colour + hatch per region. Chosen for both colour distinguishability and
# greyscale hatching legibility (the hatches differ enough that even with
# colour stripped the regions are still tellable apart).
REGION_STYLE = {
    "Carpatho-Balkan Interior": {"colour": "#5b8a3a", "hatch": ""},
    "Pannonian Plain":          {"colour": "#d6a85a", "hatch": "///"},
    "Aegean Littoral":          {"colour": "#3d7ea6", "hatch": "..."},
    "Peloponnese":              {"colour": "#a64e6f", "hatch": "xxx"},
    "Albanian Highlands":       {"colour": "#8a5a3a", "hatch": "\\\\\\"},
    "Adriatic Coastal":         {"colour": "#6fb1c2", "hatch": "+++"},
    "Lower Danubian Frontier":  {"colour": "#bcbf3a", "hatch": "ooo"},
    "unassigned":               {"colour": "#cccccc", "hatch": ""},
    "sea":                      {"colour": "#e8f1fa", "hatch": ""},
}

def main():
    out_path = Path(__file__).resolve().parent / "geographic_foundation.png"

    table = build_cell_table()
    forts = attribute_regions(load_fortifications())

    fig = plt.figure(figsize=(8.5 / 2.54, 8.5 / 2.54 * 0.7), dpi=300)
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent([LON_MIN, LON_MAX, LAT_MIN, LAT_MAX], crs=ccrs.PlateCarree())

    # Background: light Natural-Earth coastlines for orientation.
    ax.add_feature(cfeature.LAND.with_scale("50m"),
                   facecolor="#f4f1ea", edgecolor="none", zorder=0)
    ax.add_feature(cfeature.OCEAN.with_scale("50m"),
                   facecolor="#e8f1fa", edgecolor="none", zorder=0)
    ax.coastlines(resolution="50m", linewidth=0.4, color="#666666", zorder=1)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"),
                   linewidth=0.2, edgecolor="#888888", zorder=1)

    # Per-cell coloured squares (one Rectangle per land cell).
    half = CELL_SIZE_DEG / 2.0
    for (i, j), info in table.items():
        if info["is_sea"]:
            continue
        region = info["region"]
        style = REGION_STYLE.get(region, REGION_STYLE["unassigned"])
        lat = info["lat"]
        lon = info["lon"]
        rect = mpatches.Rectangle(
            (lon - half, lat - half),
            CELL_SIZE_DEG, CELL_SIZE_DEG,
            facecolor=style["colour"], edgecolor="none",
            alpha=0.65, zorder=2,
        )
        ax.add_patch(rect)
        if style["hatch"]:
            # Hatch overlay rendered as a separate Rectangle with no fill
            # so we control its transparency and hatch density independently.
            hatch_rect = mpatches.Rectangle(
                (lon - half, lat - half),
                CELL_SIZE_DEG, CELL_SIZE_DEG,
                facecolor="none", edgecolor=style["colour"],
                linewidth=0.0, hatch=style["hatch"], alpha=0.7, zorder=3,
            )
            ax.add_patch(hatch_rect)

    # Region polygon outlines on top.
    for region, poly in REGION_POLYGONS.items():
        ys = [v[0] for v in poly] + [poly[0][0]]
        xs = [v[1] for v in poly] + [poly[0][1]]
        ax.plot(xs, ys, color="#222222", linewidth=0.6, zorder=4,
                transform=ccrs.PlateCarree())

    # Fortifications: marker area proportional to pop_mid_k, so marker
    # radius proportional to sqrt(pop_mid_k) (matplotlib scatter `s`
    # parameter is area in points^2, which is what we pass directly).
    for f in forts:
        size = 4.0 + 6.0 * math.sqrt(max(f["pop_mid_k"], 0.0))
        ax.scatter(f["lon"], f["lat"], s=size,
                   marker="o", facecolor="#222222", edgecolor="white",
                   linewidths=0.3, alpha=0.85, zorder=5,
                   transform=ccrs.PlateCarree())

    # Legend (compact two-column).
    handles = []
    for region in REGION_NAMES:
        style = REGION_STYLE[region]
        handles.append(mpatches.Patch(
            facecolor=style["colour"], edgecolor="black", linewidth=0.3,
            hatch=style["hatch"], label=region))
    handles.append(mpatches.Patch(
        facecolor=REGION_STYLE["unassigned"]["colour"], edgecolor="black",
        linewidth=0.3, label="unassigned"))
    handles.append(plt.Line2D([], [], marker="o", color="#222222",
                              linestyle="None", markersize=4,
                              label="Justinian fort (size ~ pop)"))
    ax.legend(handles=handles, loc="lower left",
              fontsize=4, frameon=True, ncol=2,
              edgecolor="#888888", framealpha=0.85)

    gl = ax.gridlines(draw_labels=True, linewidth=0.2, color="#aaaaaa",
                      alpha=0.6, linestyle="--")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 4}
    gl.ylabel_style = {"size": 4}

    ax.set_title("JLG geographic foundation: regions, grid cells, fortifications",
                 fontsize=6)

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"wrote {out_path}")

if __name__ == "__main__":
    main()
