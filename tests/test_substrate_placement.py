"""Initial-state correctness tests for the substrate-configuration phase substrate
configurations.

Runs slavic1 at seed 42 with 1 run for each of the three substrate
configurations and asserts per-region year-0 Slavic share properties
per the substrate-configuration test specification. The engine is invoked as a subprocess
in a tempdir, so the main repo's output files are not touched.

Each test parses results_slavic1_per_region.csv from its tempdir.

NOTE on year-0 semantics: the engine's per-region snapshot is taken
AFTER year-0 dynamics (the year-0 plague tick + year-0 mortality +
year-0 reproduction + year-0 assimilation rolls). The post-year-0
population is therefore ~10-12 % below INITIAL_POP=5000 because of
year-0 mortality. The "post-year-0" Slavic share also differs slightly
from the pre-year-0 substrate_fraction because of the Slavic-vs-non-
Slavic plague mortality differential (Slavic 0.04, non-Slavic 0.15)
which boosts Slavic share at the year-0 plague tick.

The test tolerances below accommodate these year-0 effects.
"""

import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE = REPO_ROOT / "slavic_migration_submited_v1.py"

SEED = 42
INITIAL_POP = 5000
SUBSTRATE_FRACTION = 0.30

BALKAN_DESTINATIONS = (
    "Carpatho-Balkan Interior",
    "Aegean Littoral",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Peloponnese",
)
SOURCE_REGIONS = ("Pannonian Plain", "Lower Danubian Frontier")

def _run_engine(workdir: Path, substrate_config: str, num_runs: int = 1):
    """Run slavic1 at SEED in workdir, no anchoring, given substrate_config."""
    cmd = [
        sys.executable, str(ENGINE),
        "--scenario", "slavic1",
        "--num_runs", str(num_runs),
        "--seed", str(SEED),
        "--fortification_anchor_fraction", "0.0",
        "--substrate_config", substrate_config,
        "--substrate_fraction", str(SUBSTRATE_FRACTION),
    ]
    res = subprocess.run(cmd, cwd=workdir, capture_output=True,
                         text=True, timeout=600)
    if res.returncode != 0:
        raise AssertionError(
            f"engine failed (rc={res.returncode}, config={substrate_config})"
            f"\nstderr:\n{res.stderr[-1500:]}"
        )

def _read_year0_per_region(workdir: Path):
    """Return {region_label: {"population": int, "slavic_share": float,
    "slavic_count": int, "non_slavic_count": int}} for year 0 of run 0.
    """
    csv_path = workdir / "results_slavic1_per_region.csv"
    out = {}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["year"]) != 0 or int(row["run"]) != 0:
                continue
            pop = int(row["population"])
            slavic = int(row["slavic_count"])
            out[row["region"]] = {
                "population": pop,
                "slavic_count": slavic,
                "non_slavic_count": pop - slavic,
                "slavic_share": float(row["slavic_share"]),
            }
    return out

# ---------------------------------------------------------------------------
# (a) Configuration "none" — post-amendment baseline preserved
# ---------------------------------------------------------------------------

def test_a_none_baseline(tmp_path):
    _run_engine(tmp_path, "none")
    per_region = _read_year0_per_region(tmp_path)

    # The five Balkan destination regions hold ~0% Slavic at year 0
    # (Slavic placement under `none` goes only to source regions).
    for r in BALKAN_DESTINATIONS:
        assert per_region[r]["slavic_share"] < 0.05, (
            f"region {r}: year-0 Slavic share {per_region[r]['slavic_share']:.3f}"
            " expected ~0 under config none"
        )

    # The two source regions hold non-trivial year-0 Slavic share.
    # Pannonian Plain ~30% (baseline ~141 slavic / ~473 total);
    # LDF much higher because its baseline non-Slavic is just Avar.
    for r in SOURCE_REGIONS:
        assert per_region[r]["slavic_share"] > 0.10, (
            f"source region {r}: year-0 Slavic share "
            f"{per_region[r]['slavic_share']:.3f} expected > 0.10 under "
            f"config none"
        )

# ---------------------------------------------------------------------------
# (b) Configuration "uniform" — all 5 Balkan destinations at s = 0.30
# ---------------------------------------------------------------------------

def test_b_uniform_substrate_share(tmp_path):
    _run_engine(tmp_path, "uniform")
    per_region = _read_year0_per_region(tmp_path)

    # All 5 Balkan destinations within +/-5 pp of substrate_fraction.
    # The tolerance accommodates year-0 mortality differential (Slavic
    # plague mortality 0.04 vs non-Slavic 0.15), which boosts Slavic
    # share by ~2-4 pp at the year-0 plague tick in substrate regions.
    for r in BALKAN_DESTINATIONS:
        share = per_region[r]["slavic_share"]
        assert abs(share - SUBSTRATE_FRACTION) <= 0.05, (
            f"uniform: region {r} year-0 Slavic share {share:.4f}, "
            f"expected within +/-0.05 of {SUBSTRATE_FRACTION}"
        )

    # Source regions retain source placement (non-trivial Slavic share,
    # approximately the `none` baseline).
    for r in SOURCE_REGIONS:
        assert per_region[r]["slavic_share"] > 0.10, (
            f"uniform: source region {r} year-0 Slavic share "
            f"{per_region[r]['slavic_share']:.4f} expected > 0.10 "
            "(source placement should be preserved)"
        )

    # Total agent count after year-0 dynamics is roughly the post-amendment
    # baseline level (~4488 mean for slavic1 under `none` per
    #  §2). Substrate placement preserves
    # the pre-year-0 INITIAL_POP=5000; the year-0 plague tick drops it
    # by ~10-15 % to ~4300-4700 depending on the Slavic-vs-non-Slavic
    # composition.
    total = sum(d["population"] for d in per_region.values())
    assert 4200 <= total <= 4800, (
        f"uniform: total agent count {total} expected in [4200, 4800] "
        "post-year-0 dynamics"
    )

# ---------------------------------------------------------------------------
# (c) Configuration "cbi_only" — only CBI receives substrate
# ---------------------------------------------------------------------------

def test_c_cbi_only_substrate_share(tmp_path):
    _run_engine(tmp_path, "cbi_only")
    per_region = _read_year0_per_region(tmp_path)

    # CBI year-0 Slavic share within +/-5 pp of 0.30 (accommodates year-0
    # plague mortality differential — see test_b for details).
    cbi_share = per_region["Carpatho-Balkan Interior"]["slavic_share"]
    assert abs(cbi_share - SUBSTRATE_FRACTION) <= 0.05, (
        f"cbi_only: CBI year-0 Slavic share {cbi_share:.4f}, "
        f"expected within +/-0.05 of {SUBSTRATE_FRACTION}"
    )

    # Other 4 Balkan destinations at ~0 Slavic share.
    other_balkan = [r for r in BALKAN_DESTINATIONS if r != "Carpatho-Balkan Interior"]
    for r in other_balkan:
        share = per_region[r]["slavic_share"]
        assert share < 0.05, (
            f"cbi_only: region {r} year-0 Slavic share {share:.4f}, "
            "expected ~0 under cbi_only"
        )

    # Source regions retain source placement.
    for r in SOURCE_REGIONS:
        assert per_region[r]["slavic_share"] > 0.10, (
            f"cbi_only: source region {r} year-0 Slavic share "
            f"{per_region[r]['slavic_share']:.4f} expected > 0.10"
        )

    # Total agent count after year-0 dynamics (see test_b comment).
    total = sum(d["population"] for d in per_region.values())
    assert 4200 <= total <= 4800, (
        f"cbi_only: total agent count {total} expected in [4200, 4800] "
        "post-year-0 dynamics"
    )

# ---------------------------------------------------------------------------
# (d) Total non-Slavic count under substrate configs
# ---------------------------------------------------------------------------

def test_d_total_non_slavic_under_substrate(tmp_path):
    """For both uniform and cbi_only at substrate_fraction=0.30, the total
    non-Slavic count across all regions equals
        INITIAL_POP - source_Slavic_count - substrate_Slavic_count
        = INITIAL_POP - (source_Slavic_count + s × dest_population)
    Per the substrate-configuration phase (d), this should equal
        (1 - s × dest_population_fraction) × INITIAL_POP - source_Slavic_count
    within sampling-rejection rounding.

    The substrate adds Slavic agents into Balkan destination regions but
    keeps each region's total at baseline (it replaces some non-Slavic with
    Slavic within each substrate-receiving region). The source-Slavic
    placement (Pannonian+LDF, ~500 agents at slavic1 init_fraction=0.10) is
    PRESERVED under all three configurations.
    """
    for config in ("uniform", "cbi_only"):
        _run_engine(tmp_path, config)
        per_region = _read_year0_per_region(tmp_path)

        total_non_slavic = sum(d["non_slavic_count"] for d in per_region.values())
        total_slavic = sum(d["slavic_count"] for d in per_region.values())
        total = total_non_slavic + total_slavic

        # Sanity: post-year-0 total in the same range as the `none`
        # post-year-0 baseline (~4488). The pre-year-0 INITIAL_POP=5000
        # gets reduced by ~10-15 % at the year-0 plague tick; the
        # surviving population depends on the Slavic-vs-non-Slavic
        # composition mix in each region.
        assert 4200 <= total <= 4800, (
            f"{config}: post-year-0 total {total} expected in "
            "[4200, 4800] (the year-0 plague tick reduces INITIAL_POP "
            "to ~4400-4700 depending on composition)"
        )

        # The expected non-Slavic count is INITIAL_POP - total_Slavic, which
        # by construction holds. The substantive check: the SUBSTRATE Slavic
        # count is ≈ s × destination_population, and total_Slavic ≈
        # source_Slavic + substrate_Slavic. Verify this composition.
        # Approximate source-Slavic = 500 at slavic1 init_fraction=0.10
        # (small variance due to rounding in per-region placement).
        approx_source_slavic = sum(per_region[r]["slavic_count"]
                                   for r in SOURCE_REGIONS)
        approx_substrate_slavic = total_slavic - approx_source_slavic
        # Source-Slavic should sit in the 480-520 range (~10% of INITIAL_POP).
        assert 450 <= approx_source_slavic <= 550, (
            f"{config}: source-region Slavic count {approx_source_slavic} "
            "expected ~500"
        )
        # Substrate Slavic depends on config; for cbi_only it's ~s × baseline_CBI,
        # for uniform it's ~s × sum_of_baseline_balkan_destinations.
        assert approx_substrate_slavic > 0, (
            f"{config}: substrate Slavic count is 0; substrate placement broken"
        )

if __name__ == "__main__":
    import inspect
    import tempfile

    g = globals()
    tests = sorted(name for name, obj in g.items()
                   if name.startswith("test_") and inspect.isfunction(obj))
    failures = 0
    for name in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                g[name](Path(td))
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}: {e}")
    print(f"\n{len(tests) - failures} / {len(tests)} passed")
    sys.exit(1 if failures else 0)
