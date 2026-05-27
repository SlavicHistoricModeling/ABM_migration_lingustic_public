"""
Geographic foundation for the jlg-geographic-extension branch (the geographic-foundation phase).

This module replaces the parent-submission engine's abstract 50x50 toroidal grid with a
coordinate-anchored grid covering the Balkan study region. It provides:

  - The grid: bounding box lat 38.0-47.0 N, lon 13.0-29.0 E;
    cell size 0.5 deg x 0.5 deg; 18 x 32 = 576 raw cells; index (i, j) where
    i runs north->south (i=0 is the northern row, lat_center = 46.75) and j
    runs west->east (j=0 is the western column, lon_center = 13.25).

  - The hand-coded sea mask: coarse polygon outlines of
    the Adriatic, Ionian, Aegean, Marmara, and Black seas inside the
    bounding box. Cells whose center falls inside any sea polygon are
    flagged is_sea=True and excluded from agent placement. Targeted land
    count after sea masking: ~250-280 cells.

  - The seven-region polygon classification: each region
    is an ordered (lat, lon) vertex list approximating 6th-9th century
    cultural-geographic boundaries (see the geographic foundation for the
    historical anchors). Classification is by ray-casting point-in-polygon
    on cell centers. Cells outside every region polygon AND not in a sea
    are flagged "unassigned" and reported in verification so the polygon
    set can be extended in follow-up commits if needed.

The integer-grid lookup `{(i, j) -> region_label}` is built once at
init by `build_region_lookup()` and reused by every per-region snapshot
in the engine, keeping per-region accounting O(agents) per year.
"""

# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

LAT_MIN = 38.0
LAT_MAX = 47.0
LON_MIN = 13.0
LON_MAX = 29.0
CELL_SIZE_DEG = 0.5

GRID_SIZE_I = int(round((LAT_MAX - LAT_MIN) / CELL_SIZE_DEG))  # 18 rows (N->S)
GRID_SIZE_J = int(round((LON_MAX - LON_MIN) / CELL_SIZE_DEG))  # 32 cols (W->E)

def cell_center(i, j):
    """Cell (i, j) -> (lat_center, lon_center).

    i = 0 is the northernmost row (lat_center = LAT_MAX - 0.5*CELL_SIZE);
    j = 0 is the westernmost column (lon_center = LON_MIN + 0.5*CELL_SIZE).
    """
    lat = LAT_MAX - (i + 0.5) * CELL_SIZE_DEG
    lon = LON_MIN + (j + 0.5) * CELL_SIZE_DEG
    return lat, lon

# ---------------------------------------------------------------------------
# Point-in-polygon (ray casting)
# ---------------------------------------------------------------------------

def point_in_polygon(lat, lon, polygon):
    """Ray-casting point-in-polygon test.

    polygon is an ordered list of (lat, lon) vertices; the polygon is
    treated as closed (first vertex implicitly repeated). Vertices on
    edges count as inside for one of the two cells sharing the edge,
    which is good enough for cell-center classification.
    """
    n = len(polygon)
    inside = False
    j_prev = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j_prev]
        # Standard ray-cast: ray to the +lon direction; count edge crossings.
        if ((lat_i > lat) != (lat_j > lat)) and \
           (lon < (lon_j - lon_i) * (lat - lat_i) / (lat_j - lat_i) + lon_i):
            inside = not inside
        j_prev = i
    return inside

# ---------------------------------------------------------------------------
# Sea mask (hand-coded coarse polygons)
# ---------------------------------------------------------------------------
# Each sea polygon is an ordered (lat, lon) vertex list, drawn approximately
# from the coastline (Natural Earth visual reference). The polygons overlap
# slightly so border cells are unambiguously sea. The "coarse" descriptor in
# the spec is honoured by the small vertex counts; the alternative (loading
# Natural Earth coastline polygons via cartopy/geopandas at runtime) adds
# weight and is deferred.

SEA_POLYGONS = {
    # Adriatic Sea: a triangle running from NW corner of the box down the
    # Italian coast and across to the Albanian coast. The Dalmatian/Istrian
    # mainland strip and the Slovenian coast sit east/north of this polygon
    # and are classified as land (-> Adriatic Coastal region).
    "Adriatic": [
        (47.0, 13.0),
        (45.5, 13.0),
        (45.0, 13.4),
        (44.5, 13.6),
        (44.0, 14.5),
        (43.5, 15.5),
        (43.0, 16.0),
        (42.5, 17.0),
        (42.0, 17.5),
        (41.5, 18.0),
        (40.7, 18.5),
        (40.0, 18.7),
        (38.5, 18.7),
        (38.0, 18.0),
        (38.0, 13.0),
    ],
    # Ionian Sea: the SW corner south of the Greek coast.
    "Ionian": [
        (40.0, 17.5),
        (39.5, 19.0),
        (38.5, 20.5),
        (37.7, 21.0),
        (37.0, 21.5),
        (38.0, 22.0),
        (38.0, 17.5),
    ],
    # Aegean Sea: the south-central / SE waters, including the Greek
    # archipelago (cells over the open Aegean are sea; only mainland and
    # the very westernmost Aegean coast remain land).
    "Aegean": [
        (40.5, 23.5),
        (41.0, 24.5),
        (40.7, 26.5),
        (40.0, 27.5),
        (39.0, 27.0),
        (38.0, 26.0),
        (38.0, 24.5),
        (38.5, 23.5),
        (39.0, 23.0),
        (39.5, 22.5),
        (39.7, 23.0),
        (40.0, 23.0),
    ],
    # Sea of Marmara + Bosphorus area: the NE corner east of European Turkey.
    "Marmara": [
        (40.7, 26.5),
        (41.2, 28.0),
        (41.0, 29.0),
        (40.0, 29.0),
        (40.0, 27.0),
        (40.4, 26.5),
    ],
    # Black Sea: the east edge of the box from ~lat 42 N northward.
    "Black": [
        (47.0, 28.5),
        (47.0, 29.0),
        (43.0, 29.0),
        (42.5, 28.0),
        (43.5, 27.7),
        (45.0, 28.0),
        (46.0, 28.3),
    ],
}

def is_sea(lat, lon):
    """True if (lat, lon) falls inside any of the SEA_POLYGONS."""
    return any(point_in_polygon(lat, lon, poly) for poly in SEA_POLYGONS.values())

# ---------------------------------------------------------------------------
# Sea-mask land overrides (Sea-mask-override Amendment C)
# ---------------------------------------------------------------------------
# The coarse SEA_POLYGONS slightly overshoot the coastline in two places:
# (a) the Danube delta / lower Danube mouth, where the Black Sea polygon
#     swallows three Roman fortifications that historically sat on the
#     Danube's right bank just inland of the delta; and
# (b) the Chalkidiki peninsulas (Kassandra, Sithonia, Athos), where the
#     Aegean Sea polygon swallows ~13 fortifications that historically
#     sat on the peninsular lobes.
#
# Constantinople is *not* in the parent-submission-inherited fortifications CSV at
# all, and Thessalonica (90 k mid-band, the dataset's largest non-Slavic
# urban anchor) was already classified as land after Amendment B
# extended the Aegean Littoral polygon — so the famous coastal cities
# the amendment text mentions are covered without any further override.
#
# Each entry is (i, j) -> region_label. build_cell_table() applies the
# overrides AFTER the sea-mask check, reclassifying these cells as land
# and assigning the explicit region. This is the targeted manual fix
# the amendment requests; the longer-term Natural Earth coastline path
# remains deferred.
SEA_MASK_LAND_OVERRIDES = {
    (3, 30): "Lower Danubian Frontier",  # Noviodunum area (Danube delta, north bank)
    (4, 29): "Lower Danubian Frontier",  # Capidava / Carsium (Danube right bank)
    (5, 30): "Lower Danubian Frontier",  # Axiopolis (lower Danube)
    (12, 22): "Aegean Littoral",         # Brebate / Aulon area (NE Chalkidiki coast)
    (13, 20): "Aegean Littoral",         # Cassandria / Capaza (Kassandra peninsula)
    (13, 22): "Aegean Littoral",         # Boulpiansus / Colophonia / Martius (Sithonia + N coast)
    (13, 23): "Aegean Littoral",         # Athos peninsula cluster (Sceminites, Epidunta, Aoion, Thesaurus, Gentianum)
}

# ---------------------------------------------------------------------------
# Region polygons
# ---------------------------------------------------------------------------
# Vertex lists copied directly from the geographic foundation. Polygons are
# approximate, drawn to track 6th-9th century cultural-geographic boundaries
# (Sava-Danube line, Stara Planina ridge, Rhodope-Pirin axis, Sar-Pindus,
# Dinarides, etc.) rather than modern political borders.

REGION_POLYGONS = {
    "Carpatho-Balkan Interior": [
        (44.8, 20.5),   # Sava-Danube confluence
        (44.0, 27.5),   # eastward along the Danube
        (42.5, 27.0),   # south along the Stara Planina ridge
        (41.3, 23.5),   # southwest along Rhodope-Pirin axis
        (41.5, 20.5),   # west across the Sar-Pindus axis
        (43.5, 19.5),   # north along the Dinarides eastern slope
    ],
    # Pannonian Plain — extended in Polygon-refinement Amendment B:
    # southern edge now runs from (44.8 N, 19.0 E) along the Sava to the
    # Sava-Danube confluence (44.8 N, 20.5 E) and then along the Danube
    # down to (44.5 N, 21.5 E), tightening the previous polygon's south
    # boundary so Sirmium, Singidunum, Bassianae, and Acumincum (and
    # the rest of Roman Pannonia inside the bounding box) fall inside.
    "Pannonian Plain": [
        (44.8, 19.0),
        (44.8, 20.5),
        (44.5, 21.5),
        (47.0, 22.0),
        (47.0, 18.0),
    ],
    # Aegean Littoral — extended in Polygon-refinement Amendment B step 3:
    # western edge pushed from lon 22.5 E to lon 21.5 E, southern edge
    # pushed from lat 39.0 N down to lat 38.3 N (stopping just above the
    # Peloponnese polygon's northern edge so the two don't overlap),
    # absorbing the central-Greek inland strip between Albanian Highlands
    # and the Aegean coast that previously fell unassigned (Thessaly,
    # southern Macedonia, Boeotia, Attica). The Constantinople hinterland
    # and Black Sea coastal lobe at the east end are preserved verbatim
    # from the geographic foundation.
    "Aegean Littoral": [
        (42.5, 27.0),
        (42.0, 28.5),
        (40.5, 28.0),
        (40.0, 26.0),
        (38.3, 23.5),
        (38.3, 21.5),
        (40.5, 21.5),
        (41.0, 23.5),
        (42.0, 26.5),
    ],
    "Peloponnese": [
        (38.3, 21.5),
        (38.3, 23.5),
        (36.5, 23.5),
        (36.5, 21.5),
    ],
    "Albanian Highlands": [
        (42.5, 19.0),
        (42.5, 20.5),
        (40.0, 21.0),
        (39.5, 20.0),
        (41.5, 19.0),
    ],
    "Adriatic Coastal": [
        (45.5, 13.5),
        (45.5, 15.0),
        (43.5, 16.5),
        (42.5, 18.5),
        (42.5, 19.0),
        (43.0, 17.0),
        (44.5, 14.5),
    ],
    # Lower Danubian Frontier — extended in Polygon-refinement Amendment B
    # step 3: northern boundary pushed from lat 45.5 N up to lat 47.0 N
    # to absorb the strip of cells covering Wallachia / Transylvania /
    # eastern Hungary (the Curta archaeological zone north of the Danube
    # extends well into the modern Romanian plain). Southern boundary
    # unchanged at lat 44.0 N.
    "Lower Danubian Frontier": [
        (44.0, 22.0),
        (44.0, 28.5),
        (47.0, 28.5),
        (47.0, 22.0),
    ],
}

REGION_NAMES = (
    "Carpatho-Balkan Interior",
    "Pannonian Plain",
    "Aegean Littoral",
    "Peloponnese",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Lower Danubian Frontier",
)
# Label values that can appear as a cell's `region` field: the seven named
# regions plus "sea" (cell is masked out) and "unassigned" (cell is land but
# falls outside every region polygon). Both special labels are kept as
# explicit output values so that any leakage shows up in per-region
# accounting rather than being silently dropped.
REGION_LABELS = REGION_NAMES + ("sea", "unassigned")

def region_of(lat, lon):
    """Classify a coordinate. Returns one of REGION_NAMES, "sea", or
    "unassigned".

    Sea check runs first; only land coordinates are tested against the
    region polygons. The first polygon whose interior contains the point
    wins (polygons in REGION_POLYGONS should be disjoint by construction,
    but in the rare case of overlap the dict-iteration order pins the
    tie-break deterministically: it follows the order in which the keys
    were inserted into REGION_POLYGONS at module load).
    """
    if is_sea(lat, lon):
        return "sea"
    for name in REGION_POLYGONS:  # iteration order = insertion order in Py3.7+
        if point_in_polygon(lat, lon, REGION_POLYGONS[name]):
            return name
    return "unassigned"

# ---------------------------------------------------------------------------
# Precomputed lookups
# ---------------------------------------------------------------------------

def build_cell_table():
    """Return {(i, j) -> {"lat", "lon", "is_sea", "is_land", "region"}}
    for every cell in the GRID_SIZE_I x GRID_SIZE_J grid.

    Built once at simulation init; cheap (576 cells x 7 region polygons x
    a few vertices each = sub-millisecond).
    """
    table = {}
    for i in range(GRID_SIZE_I):
        for j in range(GRID_SIZE_J):
            lat, lon = cell_center(i, j)
            sea = is_sea(lat, lon)
            override = SEA_MASK_LAND_OVERRIDES.get((i, j))
            if override is not None:
                # Targeted manual fix (Amendment C): force this cell to
                # land and assign the documented region label, ignoring
                # the coarse sea polygons' overshoot.
                sea = False
                region = override
            elif sea:
                region = "sea"
            else:
                region = "unassigned"
                for name in REGION_POLYGONS:
                    if point_in_polygon(lat, lon, REGION_POLYGONS[name]):
                        region = name
                        break
            table[(i, j)] = {
                "lat": lat,
                "lon": lon,
                "is_sea": sea,
                "is_land": not sea,
                "region": region,
            }
    return table

def build_region_lookup():
    """Compact {(i, j) -> region_label} dispatcher table.

    Built once per simulation init; used by the per-region snapshot loop
    so per-year per-region accounting is O(agents), not O(agents x regions).
    """
    return {cell: info["region"] for cell, info in build_cell_table().items()}

def land_cells():
    """List of (i, j) for cells whose centre is land (is_sea == False)."""
    return [cell for cell, info in build_cell_table().items() if info["is_land"]]

def cells_in_region(region_name):
    """List of (i, j) for cells assigned to a given region label."""
    return [cell for cell, info in build_cell_table().items()
            if info["region"] == region_name]

# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def region_cell_counts():
    """Return {label: cell_count} for all REGION_LABELS, in REGION_LABELS order."""
    table = build_cell_table()
    counts = {label: 0 for label in REGION_LABELS}
    for info in table.values():
        counts[info["region"]] = counts.get(info["region"], 0) + 1
    return counts

if __name__ == "__main__":
    table = build_cell_table()
    counts = region_cell_counts()
    total = len(table)
    land_count = sum(1 for info in table.values() if info["is_land"])
    print(f"Grid: {GRID_SIZE_I} x {GRID_SIZE_J} = {total} cells; "
          f"land cells = {land_count}")
    print("Cell counts by region:")
    for label in REGION_LABELS:
        print(f"  {label:<28} {counts[label]:>4}")
