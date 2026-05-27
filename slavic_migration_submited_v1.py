"""
Agent-Based Model for Linguistic Expansion (Slavic and Arabic Cases).
This model extends frameworks like Kandler (2009) by incorporating spatial
grids, reverse assimilation, and sensitivity analysis. Parameters are
justified from historical sources (e.g., birth rates from Russell 1987
~3.5-5%).
Validation: Matches Arabic ~60% dominance. Run with
python script.py --scenario slavic1 --substrate True --birth_vary 0.1 --plot True.
"""
import numpy as np
import random
import csv
import statistics  # For mean and SD
import argparse  # For flexible parameter input
import sys
import time
import matplotlib.pyplot as plt  # For plotting

# JLG geographic-extension (the geographic-foundation phase): coordinate-anchored grid and
# seven-region polygon classification. This replaces the abstract 50x50
# toroidal grid that the parent-submission frozen engine ran on. The new grid is
# 18 (north->south) x 32 (west->east), with the agent dict's "x" key
# carrying the row index i in [0, GRID_SIZE_I) and the "y" key carrying
# the column index j in [0, GRID_SIZE_J). Cell (i, j) maps to a fixed
# (lat, lon) cell-center via geography.cell_center; the per-cell region
# label is precomputed once into CELL_TABLE and re-used by every per-year
# accounting loop.
from geography import (
    GRID_SIZE_I,
    GRID_SIZE_J,
    REGION_NAMES,
    build_cell_table,
    cell_center,
)
from fortifications import (
    apply_fortification_anchoring,
    attribute_regions as jlg_attribute_fort_regions,
    fortifications_by_region,
    load_fortifications,
)

# Parse arguments for flexibility
parser = argparse.ArgumentParser()
parser.add_argument('--scenario', default='all',
                    help='Scenario: slavic1, slavic2, slavic3, arabic, or all to run and plot comparisons')
parser.add_argument('--num_runs', type=int, default=10,
                    help='Number of runs for averaging')
parser.add_argument('--substrate_config', default='none',
                    choices=('none', 'uniform', 'cbi_only'),
                    help='the substrate-configuration phase substrate placement configuration. '
                         '"none" (default): post-amendment no-substrate '
                         'baseline; substrate_fraction is ignored. '
                         '"uniform": substrate Slavs placed in all five '
                         'Balkan destination regions (Carpatho-Balkan '
                         'Interior, Aegean Littoral, Albanian Highlands, '
                         'Adriatic Coastal, Peloponnese), each at '
                         'substrate_fraction of the region\'s baseline '
                         'population. "cbi_only": substrate concentrated '
                         'in Carpatho-Balkan Interior only at '
                         'substrate_fraction; other Balkan destinations '
                         'retain 0%% initial Slavic. The two source '
                         'regions (Pannonian Plain, Lower Danubian '
                         'Frontier) retain their standard source-region '
                         'initial Slavic placement under all three '
                         'configurations.')
parser.add_argument('--birth_vary', type=float, default=0.0,
                    help='Variation factor for birth rate sensitivity (+/- fraction)')
parser.add_argument('--seed', type=int, default=42,
                    help='Random seed for reproducibility')
parser.add_argument('--plot', action='store_true',
                    help='Generate and save plot (figure1.png)')
parser.add_argument('--migration_override', type=int, default=None,
                    help='Override scenario migration_rate (e.g. 0 for the no-migration baseline)')
parser.add_argument('--no_plague', action='store_true',
                    help='Force PLAGUE_YEARS = [] for the engine-sanity baseline')
parser.add_argument('--inheritance_age_max', type=int, default=None,
                    help='Override INHERITANCE_AGE_MAX (mother-tongue cutoff). '
                         'Use 99 to effectively disable the cell-pool draw. '
                         'For the 22/25/28/30 sweep.')
parser.add_argument('--uniform_mortality', action='store_true',
                    help='Force the Slavic group to use the non-Slavic plague '
                         'mortality (i.e. zero plague differential). For the '
                         'scenario 3 counterfactual: how much of the Slavic '
                         'share comes from the differential vs from migration '
                         'and assimilation alone?')
parser.add_argument('--substrate_fraction', type=float, default=0.30,
                    help='Slavic substrate fraction within each substrate-'
                         'receiving region. Default 0.30; sweep candidates '
                         '0.00, 0.10, 0.20, 0.30, 0.40, 0.50. Has no effect '
                         'under --substrate_config none.')
parser.add_argument('--non_slavic_plague_mortality', type=float, default=None,
                    help='Override the per-scenario non_slavic_plague_mortality '
                         '(default 0.15 for slavic1/2 and arabic 0.12; 0.20 for '
                         'slavic3). For the plague-mortality sensitivity sweep '
                         '(0.10/0.12/0.15/0.20).')
# JLG geographic-extension (the fortification anchoring): fortification anchoring.
parser.add_argument('--fortification_anchor_fraction', type=float, default=0.30,
                    help='Share of each region\'s non-Slavic agents that are '
                         'anchored to the region\'s Justinian fortifications '
                         '(within-region redistribution; total agent count is '
                         'preserved). Default 0.30; sweep candidates 0.00, 0.20, '
                         '0.30, 0.40, 0.50. Setting to 0.00 disables anchoring '
                         'and recovers parent-submission-style uniform-in-region placement.')
parser.add_argument('--fortification_pop_band', default='mid',
                    choices=('low', 'mid', 'high'),
                    help='Which population estimate from the fortifications CSV '
                         'to use as the within-region weight: "low", "mid" '
                         '(canonical default), or "high".')
args = parser.parse_args()

random.seed(args.seed)  # Reproducibility

# Model Configuration
# Grid: see the JLG geographic-extension import block at the top of this file.
# The agent dict's "x" carries the row index in [0, GRID_SIZE_I); "y" carries
# the column index in [0, GRID_SIZE_J). These names are retained to keep the
# refactor diff focused; under the new grid they mean integer (i, j), not the
# old abstract toroidal (x, y).
INITIAL_POP = 5000  # Future: 10000 for agents=500 individuals
REPRO_AGE_MIN, REPRO_AGE_MAX = 15, 40
MAX_AGE = 60
INHERITANCE_AGE_MAX = 25  # Live: mother-tongue rule cutoff; sweep 22/25/28/30

# Precomputed cell table and derived lookups. Built once at import time so the
# per-region snapshot loop is O(agents) per year, not O(agents x regions).
CELL_TABLE = build_cell_table()
LAND_CELLS = [cell for cell, info in CELL_TABLE.items() if info["is_land"]]
LAND_CELLS_BY_REGION = {
    region: [cell for cell in LAND_CELLS if CELL_TABLE[cell]["region"] == region]
    for region in REGION_NAMES
}
JLG_REGION_LOOKUP = {cell: info["region"] for cell, info in CELL_TABLE.items()}
JLG_REGION_LOOKUP_LABELS_SET = set(JLG_REGION_LOOKUP.values())

# the per-region-output phase: per-region output schema.
# JLG_LANGS: ordered list of the language labels in GROUPS. Used as the column
#   order in results_{scen}_per_region.csv.
# JLG_BUCKET_LABELS: the eight per-region accounting buckets (seven named
#   regions plus "unassigned"). Sea cells host no agents and are excluded
#   from per-region accounting (the bucket would always read 0 / 0).
JLG_LANGS = ("slavic", "illyrian_thracian", "greek", "germanic", "avar", "other")
JLG_BUCKET_LABELS = REGION_NAMES + ("unassigned",)

# Cell-level toponym signature recording (the cell-level toponym signature).
# At each annual tick at or after this year, each land cell records its
# modal language. The signature at scenario end is the mode of those
# annual modals (cells with no non-empty ticks across the window get
# signature "empty"). Validation against observed-toponym density is
# deferred to the geographic-map phase.
TOPONYM_SIGNATURE_START_YEAR = 130

# Checkpoint years for per_region_summary.txt — match the the parent submission convention.
JLG_SLAVIC_CHECKPOINTS = (0, 25, 50, 100, 150, 200, 260)
JLG_ARABIC_CHECKPOINTS = (0, 25, 50, 100, 170)

# the substrate-configuration phase substrate-placement configurations.
# Both substrate-receiving sets are subsets of SLAVIC_DEST_REGIONS (the five
# Balkan destination regions). The two source regions (Pannonian Plain,
# Lower Danubian Frontier) are NEVER in the substrate-receiving set; they
# retain standard source-region initial Slavic placement under all three
# configurations. The substrate is ADDITIVE to that source-region placement
# (it places extra Slavic agents in destination regions; it does not
# displace the source-region Slavic placement).
SUBSTRATE_REGIONS_UNIFORM = (
    "Carpatho-Balkan Interior",
    "Aegean Littoral",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Peloponnese",
)
SUBSTRATE_REGIONS_CBI_ONLY = (
    "Carpatho-Balkan Interior",
)

def _compute_substrate_placement_plan(GROUPS_dict, substrate_regions, s):
    """Per-region per-group target counts under a substrate configuration.

    Step 1 — compute the baseline (what `none` would produce in expectation
    under group-eligibility random placement): each group's INITIAL_POP *
    initial_fraction agents distributed across its eligible regions
    proportionally to cell count. This is the expectation, not a sample;
    the actual `none` placement still uses random sampling per agent.

    Step 2 — for each substrate-receiving region (Section 3.1 of the design: the five
    Balkan destination regions for `uniform`, just CBI for `cbi_only`):
        - region_total stays at baseline_region_total
        - new Slavic count = s × region_total + baseline Slavic in region
            (baseline Slavic is 0 for destination regions, so this equals
             s × region_total in practice)
        - non-Slavic count = region_total - new Slavic count, distributed
          across non-Slavic groups in proportion to their baseline counts
          in that region.

    Source regions (Pannonian Plain, Lower Danubian Frontier) are never in
    substrate_regions; their baseline counts (including source-region
    initial Slavic placement) are passed through unchanged. The result is
    that substrate is ADDITIVE to source-region Slavic placement.

    Returns dict[(region_label, lang_label)] = int target count.
    """
    baseline = {(r, g): 0 for r in JLG_BUCKET_LABELS for g in JLG_LANGS}
    for group, gp in GROUPS_dict.items():
        num = int(round(INITIAL_POP * gp["initial_fraction"]))
        eligible = gp["regions"]
        cell_counts = [(r, len(LAND_CELLS_BY_REGION.get(r, []))) for r in eligible]
        total_cells = sum(c for _, c in cell_counts)
        if total_cells == 0:
            continue
        allocated = 0
        for r, c in cell_counts[:-1]:
            n = int(round(num * c / total_cells))
            baseline[(r, group)] = n
            allocated += n
        baseline[(cell_counts[-1][0], group)] = num - allocated

    plan = dict(baseline)

    for r in substrate_regions:
        region_total = sum(baseline[(r, g)] for g in JLG_LANGS)
        if region_total == 0:
            continue
        slavic_target = int(round(s * region_total))
        non_slavic_target = region_total - slavic_target
        non_slavic_baseline = region_total - baseline[(r, "slavic")]
        if non_slavic_baseline > 0:
            scale = non_slavic_target / non_slavic_baseline
            non_slavic_groups = [g for g in JLG_LANGS if g != "slavic"]
            running = 0
            for g in non_slavic_groups[:-1]:
                plan[(r, g)] = int(round(baseline[(r, g)] * scale))
                running += plan[(r, g)]
            plan[(r, non_slavic_groups[-1])] = non_slavic_target - running
            plan[(r, "slavic")] = slavic_target + baseline[(r, "slavic")]
        else:
            plan[(r, "slavic")] = slavic_target

    return plan
# Slavic migration semantics (Migration-target Amendment A).
# The conventional Slavic migration narrative has Slavs *starting* north of
# the Sava-Danube line and *moving* southward into the Balkan destination
# regions. We keep these two pools strictly separate:
#
#   SLAVIC_SOURCE_REGIONS  - regions where year-0 substrate-free Slavic
#       agents are initially placed. The Pannonian Plain + Lower Danubian
#       Frontier sit adjacent to the off-grid Slavic homeland and are
#       the canonical source / starting position.
#
#   SLAVIC_DEST_REGIONS    - regions where the year-by-year migration
#       loop deposits newly-arriving Slavic agents. These are the
#       Balkan destination regions proper (Carpatho-Balkan Interior,
#       Aegean Littoral, Albanian Highlands, Adriatic Coastal,
#       Peloponnese), matching the historical Sklaviniai zones.
#
# The pre-amendment engine targeted the *source* set with migration as
# well as with initial placement, which produced a 95 % / 88 % Slavic
# share in Pannonian / Danubian by year 260 and 0 % in every Balkan
# destination region - geographically backward. The amendment splits
# the two pools.
SLAVIC_SOURCE_REGIONS = ("Pannonian Plain", "Lower Danubian Frontier")
SLAVIC_DEST_REGIONS = ("Carpatho-Balkan Interior", "Aegean Littoral",
                       "Albanian Highlands", "Adriatic Coastal",
                       "Peloponnese")
SLAVIC_SOURCE_CELLS = [c for r in SLAVIC_SOURCE_REGIONS
                       for c in LAND_CELLS_BY_REGION.get(r, [])]
SLAVIC_DEST_CELLS = [c for r in SLAVIC_DEST_REGIONS
                     for c in LAND_CELLS_BY_REGION.get(r, [])]
SLAVIC_DEST_REGIONS_SET = set(SLAVIC_DEST_REGIONS)

# Fortifications: loaded once at module import. The per-region grouping is
# parameterised by --fortification_pop_band, so we keep the raw record list
# at module scope and build the per-region weighted grouping inside
# run_simulation once the args are visible.
JLG_FORTIFICATIONS = jlg_attribute_fort_regions(load_fortifications())

# --- Birth-rate calibration -------------------------------------------------
# The reproduction loop applies a group's birth_rate as a per-year probability
# PER reproductive-age female. The original numbers (0.04, 0.05, ...) were
# specified as if they were CRUDE birth rates (~3.5-5%); applied per-female
# they're ~6.6x too small, so populations collapse.
#
# FIX: specify each group's intended CRUDE birth rate (CBR, births per head per
# year) and convert to the per-female probability the loop needs. At
# equilibrium under flat mortality m=BASE_MORTALITY=0.02, the share of the
# population that is female AND aged REPRO_AGE_MIN..MAX is
#   REPRO_SHARE = 0.5 * sum_{a=15..40} 0.98^a / sum_{a=0..inf} 0.98^a ~= 0.151
# so per_female_rate = target_CBR / REPRO_SHARE.
#
# 0.151 is the EQUILIBRIUM share. Ages are initialised uniformly here, so
# early years run hotter and population rises before settling. Confirm
# REPRO_SHARE is right via the no-migration, no-plague baseline.
REPRO_SHARE = 0.151

def per_female_rate(crude_birth_rate):
    """Crude birth rate -> per-reproductive-female annual probability."""
    return crude_birth_rate / REPRO_SHARE

# Intended crude birth rates (births per head per year). Non-migrant groups sit
# at replacement (CBR ~ CDR ~ BASE_MORTALITY); the migrating group carries only
# a MODEST advantage. The original 2:1 ratio and the 0.04->0.05->0.06 ladder
# are dropped (a large built-in fertility advantage favours the migration
# hypothesis without warrant). Sweep CBR_SLAVIC in sensitivity, including the
# no-advantage case CBR_SLAVIC == CBR_NON_SLAVIC.
CBR_NON_SLAVIC = 0.020
CBR_SLAVIC_NEW = 0.011          # newly-settled migrants, first 50 yr
CBR_SLAVIC = {
    "slavic1": 0.021,
    "slavic2": 0.023,
    "slavic3": 0.025,
    "arabic":  0.022,
}

SCENARIOS = {  # Parameters with justifications
    "slavic1": {"migration_rate": 10, "slavic_assimilation_rate": 0.005,
                "reverse_assimilation_rate": 0.03,
                "slavic_birth_rate": per_female_rate(CBR_SLAVIC["slavic1"]),
                "slavic_birth_rate_new": per_female_rate(CBR_SLAVIC_NEW),
                "non_slavic_plague_mortality": 0.15, "years": 260,
                "start_year": 600,
                "source": "Low migration: Archaeology limits <2M (Curta 2001); birth ~4% medieval avg (Russell 1987)"},
    "slavic2": {"migration_rate": 30, "slavic_assimilation_rate": 0.01,
                "reverse_assimilation_rate": 0.02,
                "slavic_birth_rate": per_female_rate(CBR_SLAVIC["slavic2"]),
                "slavic_birth_rate_new": per_female_rate(CBR_SLAVIC_NEW),
                "non_slavic_plague_mortality": 0.15, "years": 260,
                "start_year": 600,
                "source": "Moderate: Assumes slight advantages; assimilation from Kandler (2010) neutral rates"},
    "slavic3": {"migration_rate": 50, "slavic_assimilation_rate": 0.02,
                "reverse_assimilation_rate": 0.015,
                "slavic_birth_rate": per_female_rate(CBR_SLAVIC["slavic3"]),
                "slavic_birth_rate_new": per_female_rate(CBR_SLAVIC_NEW),
                "non_slavic_plague_mortality": 0.20, "years": 260,
                "start_year": 600,
                "source": "Extreme: Tests implausibility; mortality ~Justinian plague 25-50% (Procopius)"},
    "arabic":  {"migration_rate": 10, "slavic_assimilation_rate": 0.02,
                "reverse_assimilation_rate": 0.0,
                "slavic_birth_rate": per_female_rate(CBR_SLAVIC["arabic"]),
                "slavic_birth_rate_new": per_female_rate(CBR_SLAVIC_NEW),
                "non_slavic_plague_mortality": 0.12, "years": 170,
                "start_year": 630,
                "source": "Kennedy (2007): ~1M migrants; assimilation via institutions"}
}

def run_simulation(params, substrate_config="none"):
    # Plague-mortality sweep override (batch 2: 0.10/0.12/0.15/0.20).
    # Applied here so that GROUPS picks it up at construction time and
    # the uniform_mortality variant below picks up the swept value too.
    # Mutates the params dict in place; callers using SCENARIOS[scen]
    # should be aware. (For the sweep workflow, each `python ... --scen X
    # --non_slavic_plague_mortality V` invocation is a fresh process, so
    # the mutation is contained to that invocation.)
    if args.non_slavic_plague_mortality is not None:
        params["non_slavic_plague_mortality"] = args.non_slavic_plague_mortality

    # Group region eligibility: the parent-submission frozen engine used the three coarse
    # labels "eastern" / "central" / "balkans". On the JLG coordinate-anchored
    # grid the source area ("eastern") sits outside the bounding box, so:
    #   - Slavic agents that the old engine placed in "eastern"/"central"
    #     (the source area) are now placed in the northern entry regions
    #     (Pannonian Plain + Lower Danubian Frontier), adjacent to the
    #     off-grid source.
    #   - Non-Slavic groups that the old engine placed in "balkans" are now
    #     placed in their historically-appropriate polygon region(s) inside
    #     the new grid. The mapping below is documented in
    #     CHANGES_jlg.md / .
    # The "other" group's region list collapses to "Carpatho-Balkan Interior"
    # as a defensible inland residual (the old "eastern" label has no direct
    # in-grid equivalent).
    GROUPS = {
        "slavic": {"birth_rate": params["slavic_birth_rate"],
                   "birth_rate_new": params["slavic_birth_rate_new"],
                   "plague_mortality": 0.04,
                   "initial_fraction": 0.1 if params["start_year"] != 630 else 0.05,
                   "regions": ["Pannonian Plain", "Lower Danubian Frontier"],
                   "christianized": False},
        "illyrian_thracian": {"birth_rate": per_female_rate(CBR_NON_SLAVIC),
                              "plague_mortality": params["non_slavic_plague_mortality"],
                              "initial_fraction": 0.3 if params["start_year"] != 630 else 0.0,
                              "regions": ["Carpatho-Balkan Interior",
                                          "Albanian Highlands",
                                          "Adriatic Coastal"],
                              "christianized": True},
        "greek": {"birth_rate": per_female_rate(CBR_NON_SLAVIC),
                  "plague_mortality": params["non_slavic_plague_mortality"],
                  "initial_fraction": 0.2 if params["start_year"] != 630 else 0.0,
                  "regions": ["Aegean Littoral", "Peloponnese"],
                  "christianized": True},
        "germanic": {"birth_rate": per_female_rate(CBR_NON_SLAVIC),
                     "plague_mortality": params["non_slavic_plague_mortality"],
                     "initial_fraction": 0.2 if params["start_year"] != 630 else 0.0,
                     "regions": ["Pannonian Plain", "Carpatho-Balkan Interior"],
                     "christianized": True},
        "avar": {"birth_rate": per_female_rate(CBR_NON_SLAVIC),
                 "plague_mortality": 0.06 if params["start_year"] != 630 else 0.0,
                 "initial_fraction": 0.1 if params["start_year"] != 630 else 0.0,
                 "regions": ["Pannonian Plain", "Lower Danubian Frontier",
                             "Carpatho-Balkan Interior"],
                 "christianized": False},
        "other": {"birth_rate": per_female_rate(CBR_NON_SLAVIC),
                  "plague_mortality": 0.08 if params["start_year"] != 630 else params["non_slavic_plague_mortality"],
                  "initial_fraction": 0.1 if params["start_year"] != 630 else 0.95,
                  "regions": ["Carpatho-Balkan Interior"],
                  "christianized": False}
    }

    # the substrate-configuration phase: substrate placement. The five Balkan destination regions
    # (CBI, Aegean Littoral, Albanian Highlands, Adriatic Coastal,
    # Peloponnese) may receive an initial substrate of Slavic agents at
    # substrate_fraction of the region's baseline population. The two
    # source regions (Pannonian Plain, Lower Danubian Frontier) are NEVER
    # in the substrate-receiving set; they retain their standard source-
    # region Slavic placement under all three configurations (per the
    # GROUPS["slavic"]["regions"] declaration above). Substrate is therefore
    # additive to source-region Slavic placement.
    #
    # Substrate applies only to Slavic scenarios (start_year != 630).
    # Arabic scenarios ignore substrate_config.
    use_substrate_quota = (substrate_config != "none"
                           and params["start_year"] != 630)
    substrate_fraction = args.substrate_fraction
    if use_substrate_quota:
        if substrate_config == "uniform":
            substrate_regions = SUBSTRATE_REGIONS_UNIFORM
        else:  # cbi_only
            substrate_regions = SUBSTRATE_REGIONS_CBI_ONLY
    else:
        substrate_regions = ()

    if args.uniform_mortality:
        GROUPS["slavic"]["plague_mortality"] = params["non_slavic_plague_mortality"]

    BASE_MORTALITY = 0.02  # Justification: Early medieval crude ~20-30/1000 (Russell 1987)
    PLAGUE_YEARS = [] if args.no_plague else (
        [0, 10, 25] if params["start_year"] != 630 else [0, 10]
    )
    migration_rate = (args.migration_override
                      if args.migration_override is not None
                      else params["migration_rate"])
    inheritance_age_max = (args.inheritance_age_max
                           if args.inheritance_age_max is not None
                           else INHERITANCE_AGE_MAX)

    # Region-of lookup: precomputed at module load (CELL_TABLE) and bound
    # here for the agent-placement / migration loops. The parent-submission engine's
    # inline coarse region_of(x, y) is removed; eligibility now goes through
    # the polygon classification fed by geography.build_cell_table.
    def region_of(i, j):
        return CELL_TABLE[(i, j)]["region"]

    # Pre-bind the per-group eligible-cell pools so we do one random pick
    # per agent placement, not a rejection-sampling loop. For each group,
    # the candidate pool is the union of its eligible regions' land cells.
    group_eligible_cells = {
        group: [cell
                for region in gp["regions"]
                for cell in LAND_CELLS_BY_REGION.get(region, [])]
        for group, gp in GROUPS.items()
    }
    # Arabic-scenario migration target: in the parent-submission engine, Arabic migration
    # could land anywhere on the abstract grid. On the JLG grid, "anywhere"
    # collapses to any land cell. (Arabic is calibration; not load-bearing.)
    arabic_migration_target_cells = LAND_CELLS

    # Per-region fortification weighting computed once for this run, using
    # the CLI-selected population band. Cached at the run_simulation level
    # so we don't rebuild it for every run inside the for-run loop.
    jlg_forts_by_region = fortifications_by_region(
        JLG_FORTIFICATIONS, pop_band=args.fortification_pop_band)

    all_props_runs = []  # List of lists: per run, proportions over years
    all_pops_runs = []   # List of lists: per run, total agents over years
    # the per-region-output phase per-region & cell-signature accumulators (one entry per run).
    # all_per_region_runs[run][year][bucket][lang] -> int count
    #   bucket in JLG_BUCKET_LABELS; lang in JLG_LANGS.
    # all_cell_modal_runs[run][year_idx] -> (year_offset, {(i, j): lang_or_empty})
    #   only recorded for years >= TOPONYM_SIGNATURE_START_YEAR. Cells with
    #   zero agents at a given tick get language string "empty".
    all_per_region_runs = []
    all_cell_modal_runs = []

    progress_every = max(1, params["years"] // 10)  # ~10 progress lines/run
    t_start = time.time()

    for run in range(args.num_runs):
        # Initialize grid/agents. Grid is now non-toroidal and rectangular:
        # GRID_SIZE_I rows (north->south) by GRID_SIZE_J columns (west->east).
        grid = [[[] for _ in range(GRID_SIZE_J)] for _ in range(GRID_SIZE_I)]
        agents = []
        agent_id = 0

        if not use_substrate_quota:
            # the substrate-configuration phase substrate_config "none" (and Arabic scenarios):
            # existing group-eligibility random placement, unchanged from
            # the post-amendment engine. Each agent's cell is drawn uniformly
            # at random from the group's eligible-region cells; per-region
            # counts therefore vary across runs.
            for group, gp in GROUPS.items():
                num = int(INITIAL_POP * gp["initial_fraction"])
                candidates = group_eligible_cells[group]
                if not candidates:
                    # No eligible cells for this group on this grid: skip
                    # cleanly. (Happens only if a group's regions list is
                    # empty under the current GROUPS dict; not currently.)
                    continue
                for _ in range(num):
                    idx = random.randint(0, len(candidates) - 1)
                    i, j = candidates[idx]
                    agents.append({"id": agent_id, "x": i, "y": j,
                                   "language": group,
                                   "age": min(MAX_AGE,
                                              int(random.expovariate(BASE_MORTALITY))),
                                   "sex": random.choice(["male", "female"])})
                    grid[i][j].append(agent_id)
                    agent_id += 1
        else:
            # the substrate-configuration phase substrate_config "uniform" or "cbi_only" on a
            # Slavic scenario: per-region per-group quota placement. The
            # quotas are deterministic; the cell choice within each region
            # is still random.
            placement_plan = _compute_substrate_placement_plan(
                GROUPS, substrate_regions, substrate_fraction)
            for group in GROUPS:  # canonical insertion order
                for region in JLG_BUCKET_LABELS:
                    n = placement_plan.get((region, group), 0)
                    if n <= 0:
                        continue
                    cells = LAND_CELLS_BY_REGION.get(region, [])
                    if not cells:
                        continue
                    for _ in range(n):
                        idx = random.randint(0, len(cells) - 1)
                        i, j = cells[idx]
                        agents.append({"id": agent_id, "x": i, "y": j,
                                       "language": group,
                                       "age": min(MAX_AGE,
                                                  int(random.expovariate(BASE_MORTALITY))),
                                       "sex": random.choice(["male", "female"])})
                        grid[i][j].append(agent_id)
                        agent_id += 1

        # JLG fortification anchoring. Operates only on the
        # initial agent placement; subsequent migration / reproduction /
        # assimilation are unaffected. Setting --fortification_anchor_fraction
        # 0.0 disables anchoring (uniform-in-region placement only).
        apply_fortification_anchoring(
            agents=agents,
            grid=grid,
            region_lookup=JLG_REGION_LOOKUP,
            forts_by_region=jlg_forts_by_region,
            anchor_fraction=args.fortification_anchor_fraction,
        )

        props = []
        pops = []
        # the per-region-output phase per-run accumulators.
        per_region_per_year = []   # list[year] -> {bucket: {lang: count}}
        cell_modal_per_year = []   # list[(year, {(i, j): lang_or_empty})] for years >= TOPONYM_SIGNATURE_START_YEAR
        for year in range(params["years"]):
            new_agents = []
            dead = []
            if year < 100:
                target_cells = (SLAVIC_DEST_CELLS
                                if params["start_year"] != 630
                                else arabic_migration_target_cells)
                if target_cells:
                    for _ in range(migration_rate):
                        idx = random.randint(0, len(target_cells) - 1)
                        i, j = target_cells[idx]
                        new_agents.append({"id": agent_id, "x": i, "y": j,
                                           "language": "slavic",
                                           "age": random.randint(15, 40),
                                           "sex": random.choice(["male", "female"])})
                        grid[i][j].append(agent_id)
                        agent_id += 1

            # Start-of-year snapshots: cell composition for the mother-tongue
            # rule, and agent_id -> language for the assimilation neighbour
            # scan further down. Both are built once per year from the
            # start-of-year population so the result is independent of agent
            # processing order. The dict snapshot also turns the previous
            # O(n^2) per-agent neighbour scan into O(n*k) where k is the
            # Moore-neighbourhood size (<= ~30).
            cell_langs = {}
            agent_id_to_lang = {}
            for ag in agents:
                cell_langs.setdefault((ag["x"], ag["y"]), []).append(ag["language"])
                agent_id_to_lang[ag["id"]] = ag["language"]

            for a in agents:
                a["age"] += 1
                mort = BASE_MORTALITY
                if year in PLAGUE_YEARS:
                    mort = GROUPS[a["language"]]["plague_mortality"]
                if random.random() < mort:
                    dead.append(a["id"])
                    grid[a["x"]][a["y"]].remove(a["id"])
                    continue
                if a["sex"] == "female" and REPRO_AGE_MIN <= a["age"] <= REPRO_AGE_MAX:
                    br = GROUPS[a["language"]]["birth_rate"]
                    # Newly-settled-Slavic birth-rate depression (first 50 yr
                    # of the Slavic horizon). The parent-submission engine checked
                    # `a["x"] >= GRID_SIZE // 2` (Slavic in the right half =
                    # the abstract-grid Balkan destination). After Amendment
                    # A separates source from destination, the check
                    # restores the original spirit: apply the new-settler
                    # rate to Slavic agents that find themselves in the
                    # Balkan destination regions (newly arrived migrants
                    # land there), not to the year-0 source-region Slavs.
                    if a["language"] == "slavic" and year < 50 \
                            and params["start_year"] != 630 \
                            and JLG_REGION_LOOKUP[(a["x"], a["y"])] in SLAVIC_DEST_REGIONS_SET:
                        br = GROUPS["slavic"]["birth_rate_new"]
                    if args.birth_vary > 0:
                        br *= random.uniform(1 - args.birth_vary, 1 + args.birth_vary)
                    if random.random() < br:
                        nx, ny = a["x"], a["y"]

                        # Mother-tongue transmission. Mother <= INHERITANCE_AGE_MAX
                        # at birth: child inherits her language. Older mother:
                        # child draws its language from the local same-cell
                        # distribution (community acquisition where no
                        # institution standardises transmission). If the cell
                        # holds fewer than 3 OTHER agents the local pool is too
                        # small to be meaningful, so the child falls back to
                        # the mother's language.
                        if a["age"] <= inheritance_age_max:
                            child_lang = a["language"]
                        else:
                            pool = list(cell_langs.get((a["x"], a["y"]), []))
                            if a["language"] in pool:
                                pool.remove(a["language"])
                            if len(pool) < 3:
                                child_lang = a["language"]
                            else:
                                child_lang = random.choice(pool)

                        new_agents.append({"id": agent_id, "x": nx, "y": ny,
                                           "language": child_lang, "age": 0,
                                           "sex": random.choice(["male", "female"])})
                        grid[nx][ny].append(agent_id)
                        agent_id += 1
                # Non-toroidal Moore-8 neighbourhood (the parent-submission engine wrapped
                # toroidally; on a geographic grid wrapping doesn't make
                # sense - lon 13 E doesn't wrap to lon 29 E). Out-of-bounds
                # and sea neighbours are skipped: agents in coastal cells
                # therefore see fewer neighbours than agents in deep inland
                # cells, which is the geographically realistic behaviour.
                neigh_ids = []
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        if di == 0 and dj == 0:
                            continue
                        ni = a["x"] + di
                        nj = a["y"] + dj
                        if 0 <= ni < GRID_SIZE_I and 0 <= nj < GRID_SIZE_J \
                                and CELL_TABLE[(ni, nj)]["is_land"]:
                            neigh_ids.extend(grid[ni][nj])
                neigh_langs = [agent_id_to_lang[i] for i in neigh_ids if i in agent_id_to_lang]
                if a["language"] == "slavic" and params["start_year"] != 630:
                    if neigh_langs:
                        christian_neighbors = sum(1 for l in neigh_langs if GROUPS[l]["christianized"])
                        if christian_neighbors / len(neigh_langs) > 0.5 and random.random() < params["reverse_assimilation_rate"]:
                            chlangs = [l for l in neigh_langs if GROUPS[l]["christianized"]]
                            if chlangs:
                                # Determinism fix: `set(chlangs)` iteration order
                                # depends on Python's hash randomisation
                                # (PYTHONHASHSEED), so when two Christianised
                                # neighbour-languages tied in count the
                                # `max(...)` tie-break was process-dependent.
                                # Sorting the set first pins the tie-break to
                                # alphabetical order — reproducible at any seed
                                # on any machine. See
                                # docs/run_logs/2026-05-15_determinism_fix.md.
                                a["language"] = max(sorted(set(chlangs)), key=chlangs.count)
                if a["language"] != "slavic":
                    if neigh_langs:
                        sN = sum(1 for l in neigh_langs if l == "slavic")
                        if sN / len(neigh_langs) > 0.5 and random.random() < params["slavic_assimilation_rate"]:
                            a["language"] = "slavic"
            agents = [a for a in agents if a["id"] not in dead] + new_agents
            s_count = sum(1 for a in agents if a["language"] == "slavic")
            props.append(s_count / len(agents) if agents else 0.0)
            pops.append(len(agents))

            # the per-region output schema: per-region snapshot.
            # End-of-year per-bucket per-language counts via the precomputed
            # JLG_REGION_LOOKUP. Passive observation only — does not call
            # random, does not touch agent state, so the slavic1 trajectory
            # is unchanged by adding this code.
            bucket_counts = {b: {lang: 0 for lang in JLG_LANGS}
                             for b in JLG_BUCKET_LABELS}
            for ag in agents:
                bucket = JLG_REGION_LOOKUP[(ag["x"], ag["y"])]
                if bucket == "sea":
                    # Defensive: agents on sea cells would indicate a placement
                    # bug; the override mechanism ensures this never fires
                    # under the current grid. Bucket-as-unassigned so the
                    # output stays rectangular.
                    bucket = "unassigned"
                bucket_counts[bucket][ag["language"]] += 1
            per_region_per_year.append(bucket_counts)

            # the cell-level toponym signature: cell-level toponym signature.
            # From TOPONYM_SIGNATURE_START_YEAR onwards, each LAND cell
            # records its modal language. Alphabetical tie-break for
            # determinism. Cells with zero agents record "empty".
            if year >= TOPONYM_SIGNATURE_START_YEAR:
                cell_modal = {}
                cell_buckets = {}
                for ag in agents:
                    cell_buckets.setdefault((ag["x"], ag["y"]), []).append(ag["language"])
                for cell in LAND_CELLS:
                    langs = cell_buckets.get(cell)
                    if not langs:
                        cell_modal[cell] = "empty"
                    else:
                        cell_modal[cell] = max(sorted(set(langs)),
                                               key=langs.count)
                cell_modal_per_year.append((year, cell_modal))

            if (year + 1) % progress_every == 0 or year + 1 == params["years"]:
                done_yr = run * params["years"] + year + 1
                total_yr = args.num_runs * params["years"]
                pct = 100.0 * done_yr / total_yr
                elapsed = time.time() - t_start
                eta = elapsed * (total_yr - done_yr) / done_yr if done_yr else 0.0
                print(f"PROGRESS run {run + 1}/{args.num_runs} year {year + 1}/{params['years']}"
                      f" pop={len(agents)} slav={props[-1]:.1%}"
                      f" overall {pct:5.1f}% elapsed={elapsed:6.1f}s eta={eta:6.1f}s",
                      file=sys.stdout, flush=True)

        all_props_runs.append(props)
        all_pops_runs.append(pops)
        all_per_region_runs.append(per_region_per_year)
        all_cell_modal_runs.append(cell_modal_per_year)

        # JLG diagnostic: per-region Slavic share at end of each run.
        # Lightweight tally over the final agents list (no extra RNG, no
        # state mutation); useful for Amendment A's migration-target
        # check and for any per-region eyeballing during development. The
        # structured per-region recording that Prompt 2 introduces will
        # subsume this, but this stays as a cheap end-of-run sanity print.
        _region_slavic = {r: 0 for r in JLG_REGION_LOOKUP_LABELS_SET}
        _region_total = {r: 0 for r in JLG_REGION_LOOKUP_LABELS_SET}
        for a in agents:
            reg = JLG_REGION_LOOKUP[(a["x"], a["y"])]
            _region_total[reg] += 1
            if a["language"] == "slavic":
                _region_slavic[reg] += 1
        print(f"DIAG run {run+1}/{args.num_runs} per-region Slavic share at year {params['years']}:",
              file=sys.stdout, flush=True)
        for reg in sorted(JLG_REGION_LOOKUP_LABELS_SET):
            tot = _region_total[reg]
            sla = _region_slavic[reg]
            sh = (sla / tot * 100.0) if tot > 0 else 0.0
            print(f"  {reg:<28} pop={tot:>5}  slav={sla:>4}  share={sh:>5.1f}%",
                  file=sys.stdout, flush=True)

    # Compute averages and SDs per year
    num_years = params["years"]
    avg_props = [statistics.mean([run_props[y] for run_props in all_props_runs]) for y in range(num_years)]
    sd_props = [statistics.stdev([run_props[y] for run_props in all_props_runs]) if args.num_runs > 1 else 0.0 for y in range(num_years)]
    avg_pops = [statistics.mean([run_pops[y] for run_pops in all_pops_runs]) for y in range(num_years)]
    min_pops = [min(run_pops[y] for run_pops in all_pops_runs) for y in range(num_years)]
    max_pops = [max(run_pops[y] for run_pops in all_pops_runs) for y in range(num_years)]

    return (avg_props, sd_props, params["start_year"], avg_pops, min_pops, max_pops,
            all_per_region_runs, all_cell_modal_runs)

# If scenario is 'all', run all and plot
if args.scenario == 'all':
    results = {}
    for scen in ['slavic1', 'slavic2', 'slavic3', 'arabic']:
        params = SCENARIOS[scen]
        results[scen] = run_simulation(params, args.substrate_config)
else:
    params = SCENARIOS[args.scenario]
    results = {args.scenario: run_simulation(params, args.substrate_config)}

# Population checkpoints printed in every results file so the run-log
# template can quote them. Range covers max scenario length (260 yr).
POP_CHECKPOINTS = [0, 25, 50, 100, 150, 200, 260]

# Output results for single or all
for scen, (avg_props, sd_props, start_year, avg_pops, min_pops, max_pops,
           all_per_region_runs, all_cell_modal_runs) in results.items():
    n_yr = len(avg_pops)

    # (a) results_{scen}_aggregate.txt - byte-identical to the pre-the per-region-output phase
    #     results_{scen}.txt format. The per-region observation code does not
    #     call random or mutate agent state, so the aggregate trajectory is
    #     unchanged from the post-Amendment engine. For a seed-42 10-run
    #     slavic1 with no substrate and no fortification anchoring this file
    #     reproduces the post-amendment canonical 11.61% +/- 2.05%.
    with open(f"results_{scen}_aggregate.txt", "w") as f:
        f.write(f"Scenario: {scen} | Runs: {args.num_runs} | Substrate: {args.substrate_config}"
                f" | Birth Vary: +/-{args.birth_vary*100}%"
                f" | migration_override: {args.migration_override}"
                f" | no_plague: {args.no_plague}"
                f" | uniform_mortality: {args.uniform_mortality}"
                f" | inheritance_age_max: {args.inheritance_age_max}"
                f" | substrate_fraction: {args.substrate_fraction}"
                f" | non_slavic_plague_mortality: {args.non_slavic_plague_mortality}"
                f" | seed: {args.seed}\n")
        f.write(f"Avg Final Proportion: {avg_props[-1]:.2%} (+/-{sd_props[-1]:.2%})\n")
        f.write("Population checkpoints (year_offset: mean [min..max]):\n")
        for c in POP_CHECKPOINTS:
            idx = c if c < n_yr else n_yr - 1
            f.write(f"  year {c:>3}: {avg_pops[idx]:>7.0f}  [{min_pops[idx]:>5}..{max_pops[idx]:>5}]\n")
        f.write("Slavic-share checkpoints (year_offset: mean +/- SD):\n")
        for c in POP_CHECKPOINTS:
            idx = c if c < n_yr else n_yr - 1
            f.write(f"  year {c:>3}: {avg_props[idx]*100:>5.2f}% +/- {sd_props[idx]*100:>4.2f}%\n")

    # (b) results_{scen}_per_region.csv - flat CSV, one row per region per
    #     year per run. Gitignored (regenerable from any seed-42 run).
    with open(f"results_{scen}_per_region.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "year", "run", "population",
                    "slavic_count", "slavic_share",
                    "illyrian_thracian_count", "greek_count",
                    "germanic_count", "avar_count", "other_count"])
        for run_idx, per_year in enumerate(all_per_region_runs):
            for year_idx, bucket_counts in enumerate(per_year):
                for bucket in JLG_BUCKET_LABELS:
                    counts = bucket_counts[bucket]
                    pop = sum(counts[lang] for lang in JLG_LANGS)
                    slavic = counts["slavic"]
                    share = slavic / pop if pop > 0 else 0.0
                    w.writerow([bucket, year_idx, run_idx, pop,
                                slavic, f"{share:.6f}",
                                counts["illyrian_thracian"], counts["greek"],
                                counts["germanic"], counts["avar"], counts["other"]])

    # (c) results_{scen}_per_region_summary.txt - tracked summary table.
    #     Per-bucket Slavic share at parent-submission-convention checkpoint years
    #     (mean +/- SD across runs) plus per-bucket population.
    checkpoints = (JLG_ARABIC_CHECKPOINTS if scen == "arabic"
                   else JLG_SLAVIC_CHECKPOINTS)
    with open(f"results_{scen}_per_region_summary.txt", "w") as f:
        f.write(f"Per-region summary | Scenario: {scen} | Runs: {args.num_runs}"
                f" | seed: {args.seed}"
                f" | substrate_config: {args.substrate_config}"
                f" | substrate_fraction: {args.substrate_fraction}"
                f" | non_slavic_plague_mortality: {args.non_slavic_plague_mortality}"
                f" | inheritance_age_max: {args.inheritance_age_max}"
                f" | uniform_mortality: {args.uniform_mortality}"
                f" | migration_override: {args.migration_override}"
                f" | no_plague: {args.no_plague}"
                f" | fortification_anchor_fraction: {args.fortification_anchor_fraction}"
                f" | fortification_pop_band: {args.fortification_pop_band}\n")
        f.write("\nPer-region Slavic share at checkpoint years (mean +/- SD across runs):\n\n")
        f.write(f"{'region':<28}")
        for c in checkpoints:
            f.write(f"  year {c:>3}        ")
        f.write("\n")
        for bucket in JLG_BUCKET_LABELS:
            f.write(f"{bucket:<28}")
            for c in checkpoints:
                idx = c if c < n_yr else n_yr - 1
                shares = []
                for per_year in all_per_region_runs:
                    counts = per_year[idx][bucket]
                    pop = sum(counts[lang] for lang in JLG_LANGS)
                    shares.append(counts["slavic"] / pop if pop > 0 else 0.0)
                mean_share = statistics.mean(shares) * 100
                sd_share = (statistics.stdev(shares) * 100
                            if len(shares) > 1 else 0.0)
                f.write(f"  {mean_share:>5.2f}+/-{sd_share:>5.2f}%")
            f.write("\n")
        f.write("\nPer-region population at checkpoint years (mean +/- SD across runs):\n\n")
        f.write(f"{'region':<28}")
        for c in checkpoints:
            f.write(f"  year {c:>3}            ")
        f.write("\n")
        for bucket in JLG_BUCKET_LABELS:
            f.write(f"{bucket:<28}")
            for c in checkpoints:
                idx = c if c < n_yr else n_yr - 1
                pops_here = []
                for per_year in all_per_region_runs:
                    counts = per_year[idx][bucket]
                    pops_here.append(sum(counts[lang] for lang in JLG_LANGS))
                mean_pop = statistics.mean(pops_here)
                sd_pop = (statistics.stdev(pops_here)
                          if len(pops_here) > 1 else 0.0)
                f.write(f"  {mean_pop:>7.1f}+/-{sd_pop:>7.1f}")
            f.write("\n")

    # (d) results_{scen}_cell_signatures.csv - per cell per run, the toponym
    #     signature is the mode of the cell's annual modal-language record
    #     across the recording window (years >= TOPONYM_SIGNATURE_START_YEAR).
    #     Empty ticks are excluded from the mode reduction; cells with no
    #     non-empty ticks across the window get signature "empty".
    #     Gitignored (regenerable from any seed-42 run); the geographic-map phase will
    #     validate aggregated signature distributions against observed
    #     toponym density per region.
    with open(f"results_{scen}_cell_signatures.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell_i", "cell_j", "lat", "lon", "region",
                    "signature_language", "run", "non_empty_ticks"])
        for run_idx, annual_modals in enumerate(all_cell_modal_runs):
            per_cell_record = {c: [] for c in LAND_CELLS}
            for _year_offset, cell_modal in annual_modals:
                for cell, lang in cell_modal.items():
                    if lang != "empty":
                        per_cell_record[cell].append(lang)
            for cell in LAND_CELLS:
                record = per_cell_record[cell]
                non_empty_ticks = len(record)
                if non_empty_ticks == 0:
                    signature = "empty"
                else:
                    signature = max(sorted(set(record)), key=record.count)
                info = CELL_TABLE[cell]
                w.writerow([cell[0], cell[1], f"{info['lat']:.4f}",
                            f"{info['lon']:.4f}", info["region"],
                            signature, run_idx, non_empty_ticks])

# Plot if requested
if args.plot or args.scenario == 'all':
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = {'slavic1': 'blue', 'slavic2': 'green', 'slavic3': 'red', 'arabic': 'purple'}
    for scen, (avg_props, sd_props, start_year, _avg_pops, _min_pops, _max_pops,
               _per_region, _cell_modal) in results.items():
        years = np.arange(start_year, start_year + len(avg_props))
        ax.plot(years, np.array(avg_props) * 100, label=scen.capitalize(), color=colors.get(scen, 'black'))
        ax.fill_between(years,
                        (np.array(avg_props) - np.array(sd_props)) * 100,
                        (np.array(avg_props) + np.array(sd_props)) * 100,
                        alpha=0.2, color=colors.get(scen, 'black'))

    ax.set_xlabel('Year')
    ax.set_ylabel('Linguistic Proportion (%)')
    ax.set_title('Time-series of Linguistic Proportions (Averages with Error Bars)')
    ax.legend()
    ax.grid(True)
    plt.savefig('figure1.png')
    plt.show()  # Or close if no display

# Alternative model: Simple Lotka-Volterra for comparison (from Kandler 2008 inspiration)
def lotka_volterra_comparison(N0_slavic=0.1, r_slavic=0.04, r_other=0.025, alpha=0.005, beta=0.03, t=260):
    """Equation-based alternative: dS/dt = r_s S (1 - S - alpha O), dO/dt = r_o O (1 - O - beta S)"""
    S, O = [N0_slavic], [1 - N0_slavic]
    for _ in range(t):
        dS = r_slavic * S[-1] * (1 - S[-1] - alpha * O[-1])
        dO = r_other * O[-1] * (1 - O[-1] - beta * S[-1])
        S.append(max(0, S[-1] + dS))
        O.append(max(0, O[-1] + dO))
    return S[-1] / (S[-1] + O[-1])

# Example call: Print comparison
lv_prop = lotka_volterra_comparison()
print(f"Lotka-Volterra Comparison Proportion: {lv_prop:.2%}")
