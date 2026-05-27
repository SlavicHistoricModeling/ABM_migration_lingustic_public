# Replication Instructions

This document walks through reproducing every reported number in the JLG paper from a clean clone of this replication package.

## 1. Environment setup

**Canonical execution environment:** Python 3.13.2 on x86-64 (Windows or Linux).

```bash
# Clone or download this replication package
git clone https://github.com/stoleskopje/ABM_migration_lingustic_public.git
cd ABM_migration_lingustic_public

# Create a fresh virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# Install dependencies (pinned to the versions that produced the canonical numbers)
pip install -r docs/requirements.txt
```

Cross-architecture caveat: floating-point determinism across different Python builds, CPU architectures, or library versions is not guaranteed. The canonical numbers were produced on the environment specified in `docs/requirements.txt`. If your numbers diverge from those reported below, check that you are running the pinned versions.

## 2. Smoke-test reproduction: the JLG-extension baseline

This is the fastest verification that the engine is intact. Run the slavic1 scenario at canonical-baseline settings:

```bash
python slavic_migration_submited_v1.py \
    --scenario slavic1 \
    --num_runs 10 \
    --seed 42 \
    --substrate_config none \
    --fortification_anchor_fraction 0.0
```

**Expected output** (the engine writes to `results_slavic1_aggregate.txt` in the working directory):

```
Avg Final Proportion: 11.61% (+/-2.05%)
```

If your output matches digit-exactly, the JLG-extension baseline has reproduced. The same baseline produces the engine-stability gate's `year 260 mean pop = 5202 (drift +4.0%)` checkpoint when run with the additional flags `--no_plague --migration_override 0`.

Wall-clock time on a modern laptop: approximately 10–15 minutes (10 runs × 260 simulated years × ~5000 agents).

## 3. Canonical cbi_only reproduction (paper's headline result)

```bash
python slavic_migration_submited_v1.py \
    --scenario slavic1 \
    --num_runs 10 \
    --seed 42 \
    --substrate_config cbi_only \
    --substrate_fraction 0.30 \
    --fortification_anchor_fraction 0.30
```

Note: the `reverse_assimilation_rate` value lives in the per-scenario `SCENARIOS` dict at lines 317-338 of `slavic_migration_submited_v1.py` (no CLI flag). The slavic1 engine default is `0.030`. To reproduce the parameter sweep's specific cells at non-default ra values, the sweep harness substitutes the rate in a per-cell engine copy via `re.sub` (see `scripts/run_jlg_sweep.py`).

**Expected output** at the slavic1 canonical (sf=0.30, ra=0.030, anchor=0.30):

```
results_slavic1_per_region_summary.txt:
  Carpatho-Balkan Interior  year 260   15.08% +/- 6.87%
  Lower Danubian Frontier   year 260   81.32% +/- 11.11%
  Aegean Littoral           year 260    0.08% +/- 0.16%
  Peloponnese               year 260    0.00% +/- 0.00%
  Albanian Highlands        year 260    0.25% +/- 0.53%
  Adriatic Coastal          year 260    0.00% +/- 0.00%
  Pannonian Plain           year 260   21.78% +/- 23.78%
```

(The pre-recorded canonical values are in `results/jlg_sweep/canonical/per_region_year260_canonical_ra030.csv` — slavic1 cbi_only rows.)

## 4. Reproducing the full 144-cell sweep (patient reader)

```bash
python scripts/run_jlg_sweep.py
```

Wall-clock time:

- **Pre-sweep gate + timing test:** ~12 minutes
- **Full sweep at 11 parallel workers:** projection was 2.5 hours but actual was 53.2 hours on the development machine (the timing test used the lightest config; slavic2 and slavic3 are ~3-5× slower per cell; Windows host slept twice overnight). A non-sleeping host with 11 modern cores should complete the sweep in 4-12 hours.

The sweep writes per-cell outputs into `results/jlg_sweep/{cell_id}/` and the consolidated `results/jlg_sweep/sweep_summary.csv`. CLI options:

- `--workers N` — parallelism (default `os.cpu_count() - 1`)
- `--dry-run` — list cells then exit
- `--skip-gate` — skip the pre-sweep engine-stability gate (debug only)
- `--skip-timing` — skip the pre-sweep timing test (debug only)
- `--force` — proceed even if projected wall exceeds 12 hours
- `--cell-filter SUBSTR` — run only cells whose `cell_id` contains the substring (debug only)

## 5. Reproducing the summary tables and figures

After the sweep (or using the pre-included `sweep_summary.csv` in `results/jlg_sweep/`):

```bash
# Generate the four sweep summary CSVs from sweep_summary.csv
python scripts/build_jlg_sweep_summaries.py

# Generate the three sweep figures (regional outcomes / CBI heatmap / coastal decay)
python scripts/build_jlg_sweep_figures.py

# Generate the four canonical tables at ra in {0.015, 0.030, 0.045} + CANONICAL_COMPARISON.md
python scripts/build_jlg_canonical_tables.py

# Generate the five JLG geographic-map figures + greyscale-check copies + captions
python figures/jlg_maps/make_jlg_maps.py
```

The figure scripts write to `figures/jlg_sweep/` and `figures/jlg_maps/` respectively. The pre-included PNGs in those folders are the canonical reference; regeneration should produce byte-similar (not necessarily byte-identical, due to matplotlib backend variation) outputs.

## 6. Test suite

```bash
pytest tests/ -v
```

Approximately 30 tests across four files:

- `tests/test_geography.py` — grid, point-in-polygon, sea mask, region classification, calibration baseline (14 tests)
- `tests/test_fortifications.py` — CSV loader, parser, region attribution, anchoring count-preservation (13 tests)
- `tests/test_regional_aggregate_equivalence.py` — per-region CSV sums match aggregate.txt at every checkpoint (3 tests)
- `tests/test_substrate_placement.py` — three substrate configurations behave as specified (several tests)

All tests must pass for the replication to be considered intact.

## 7. Known caveats (disclosure)

Cross-architecture reproduction is unverified at submission. The development machine was Windows 11 / x86-64 / Python 3.13.2. Linux x86-64 reproduction is expected to work but has not been formally tested by the author; readers who reproduce on Linux are warmly invited to report results.

The four documented limitations from the JLG paper:

- **Peloponnese under-resolution:** 4 grid cells, low statistical resolution; deferred technical debt (bounding-box extension to 36°N would change every parent-submission baseline number).
- **23 unassigned-cell fortifications:** ~13% of usable forts fall in inland gaps between region polygons; minor distortion of regional non-Slavic spatial distribution.
- **Constantinople absent from fortifications dataset:** the model's institutional anchor is conservative relative to the historical Byzantine urban network.
- **Adriatic Coastal heterogeneity:** observed toponym density averages inland (~25%) and urban-coastal (~5%) zones into a single midpoint (~15%).

These are documented in `docs/CHANGES_jlg.md` and acknowledged in the paper's discussion / limitations section.
