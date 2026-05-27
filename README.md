# Demographic-Spatial Modeling of Slavic Linguistic Expansion in the Balkans, c. 600–860 CE
## Replication Package for the JLG Submission

**Date:** 2026
**Version:** v1.0.0
**License:** CC BY 4.0 (see [LICENSE](LICENSE))
**Repository:** <https://github.com/stoleskopje/ABM_migration_lingustic_public>
**Zenodo DOI:** *to be assigned at upload* (see [docs/MANUAL_ZENODO_UPLOAD.md](docs/MANUAL_ZENODO_UPLOAD.md))

### Related work

Companion submissions are in preparation on adjacent aspects of
the same research program, currently under review at separate
journals. These include: a demographic-modeling reassessment of the
conventional migration mechanism (under review at the Journal of
Artificial Societies and Social Simulation); a per-book frequency
analysis of group-mentions in Procopius of Caesarea's corpus (under
review at the Journal of Classical Antiquity); and a data-note
documentation of the Justinianic-era fortifications corpus (under
review at the Journal of Open Archaeology Data). Cross-references
with permanent identifiers will be added to this README after the
companion submissions reach decision; until then, readers seeking the companion works will find them via the published DOIs once decisions are reached.

---

## Overview

This replication package contains the empirical artifacts the JLG paper cites. The JLG paper extends a prior demographic-modeling submission (see *Related work* above) by adding (a) a coordinate-anchored 18×32 Balkan grid (38–47°N, 13–29°E, 0.5° cells); (b) a seven-region polygon classification (Carpatho-Balkan Interior, Pannonian Plain, Aegean Littoral, Peloponnese, Albanian Highlands, Adriatic Coastal, Lower Danubian Frontier) with proportional fortification anchoring from a 170-entry Justinianic-fortifications dataset; (c) per-region output tracking and a cell-level toponym signature; (d) three substrate placement configurations (`none`, `uniform`, `cbi_only`) controlled by a `--substrate_config` CLI flag; and (e) a 144-cell parameter sweep across scenarios × substrate configurations × substrate fractions × reverse-assimilation rates.

The headline empirical finding is that the `cbi_only` substrate configuration — substrate Slavic population placed only in the Carpatho-Balkan Interior region — produces a per-region year-260 Slavic-share spatial gradient that qualitatively resembles the observed Slavic toponymic gradient. At canonical parameters (`substrate_fraction = 0.30`, `revassim_rate = 0.030` for slavic1 = the engine default, `fortification_anchor_fraction = 0.30`, seed 42, 10 runs), the Carpatho-Balkan Interior reaches 15.1% ± 6.9% modeled Slavic share against an observed ~85% per Skok / Loma / Zaimov, and the four coastal destinations (Aegean, Peloponnese, Albanian, Adriatic) all stay below 0.3% modeled against observed values in the 10–25% range. The model captures the high-interior / low-coast direction of the observed gradient but under-predicts its magnitude at the canonical parameters; the `cbi_substrate_robustness.csv` grid shows the CBI modeled share can reach 83.9% at the upper substrate-fraction / lower reverse-assimilation corner of the swept parameter space.

The convergent argument the JLG paper develops combines this demographic-computational finding with five additional lines of evidence (assimilation-of-conquerors, prestige-koine ceiling, Cyrillo-Methodian decision, the historical-narrative companion analysis referenced under *Related work*, logistical feasibility per Heather 1996 / Ward-Perkins 2005). The convergent reading supports a substrate-continuity hypothesis concentrated in the Carpatho-Balkan zone.

---

## File manifest

### Engine and dependencies (deposit root)
- `slavic_migration_submited_v1.py` — the JLG-final engine module
- `geography.py` — coordinate-anchored grid, seven-region polygons, sea mask
- `fortifications.py` — Justinianic-fortifications loader and within-region anchoring
- `ODD_protocol.md` — ODD-protocol model description (from the parent-submission deposit, unchanged in the JLG extension)
- `LICENSE` — CC BY 4.0 license text
- `CITATION.cff` — Citation File Format metadata

### `data/`
- `Justinain_Fortifications_with_Population_Estimates_clean.csv` — 170 Justinianic fortifications with c. 600 CE population estimates (methodology documented in a separate data-note submission under review; see *Related work* above)
- `observed_toponym_density.csv` — observed Slavic toponym density per region, compiled from Skok 1971-1974, Loma 2002, Zaimov 1973, Vasmer 1941, Malingoudis 1981, Ylli 2000, Skok 1950, Muljačić 2000

### `scripts/`
- `run_jlg_sweep.py` — 144-cell parameter sweep harness (Python `ProcessPoolExecutor`)
- `check_engine_stability_gate.sh` — engine-stability gate (no-plague + no-migration baseline, ±10% population sustain)
- `build_jlg_sweep_summaries.py` — derives the three sweep-summary CSVs from `sweep_summary.csv`
- `build_jlg_sweep_figures.py` — derives the three sweep figures from `sweep_summary.csv`
- `build_jlg_canonical_tables.py` — derives side-by-side canonical tables at three reverse-assimilation rates

### `results/`
- `results_slavic1_aggregate.txt` — canonical slavic1 aggregate (cbi_only, sf=0.30 baseline)
- `results_slavic1_per_region_summary.txt` — corresponding per-region summary

### `results/jlg_sweep/`
- `sweep_summary.csv` — the 1,152-row sweep summary (144 cells × 8 region buckets); load-bearing replication input
- `aggregate_by_scenario.csv` — 12-row aggregate Slavic-share table per (scenario × substrate_config)
- `per_region_year260_canonical.csv` — 96-row per-region year-260 canonical table (sf=0.30, ra=0.015)
- `cbi_substrate_robustness.csv` — 20-row CBI substrate persistence grid (slavic1 cbi_only across the sf × ra parameter space)

### `results/jlg_sweep/canonical/` (side-by-side tables at three reverse-assimilation rates)
- `per_region_year260_canonical_ra015.csv` — 96-row canonical table at ra=0.015
- `per_region_year260_canonical_ra030.csv` — 96-row canonical table at ra=0.030 (engine default for slavic1; **the paper's recommended canonical**)
- `per_region_year260_canonical_ra045.csv` — 96-row canonical table at ra=0.045 (conservative stress test)
- `CANONICAL_COMPARISON.md` — slavic1 side-by-side comparison across the three ra values (paper Section 5 source table)

### `figures/` (top-level)
- `geographic_foundation.png` — the seven-region polygon classification with fortification overlay (paper Section 2)
- `regional_population_accounting.png` — per-region population trajectories (paper Appendix / verification figure)
- `make_geographic_foundation.py` — generator script
- `make_regional_population_accounting.py` — generator script

### `figures/jlg_sweep/`
- `regional_outcomes_canonical.png` — 4-panel bar chart of per-region year-260 Slavic share across the three substrate configurations (paper Section 5)
- `cbi_substrate_heatmap.png` — CBI year-260 Slavic share across the (sf × ra) parameter grid (paper Section 5 / supplementary)
- `coastal_substrate_decay.png` — coastal-region Slavic share under uniform configuration vs substrate_fraction (paper Section 5 / supplementary)

### `figures/jlg_maps/` (the five JLG geographic-map figures)
- `observed_toponym_density.png` — Figure JLG-1
- `modeled_cbi_only_year260.png` — Figure JLG-2
- `modeled_none_year260.png` — Figure JLG-3
- `observed_vs_modeled_comparison.png` — Figure JLG-4 (**paper headline visual**)
- `observed_minus_modeled_residuals.png` — Figure JLG-5
- `make_jlg_maps.py` — generator script
- `captions/figure_jlg_{1..5}_caption.txt` — 60–120 word paper-ready captions
- `_greyscale_check/*.png` — PIL L-mode greyscale copies for legibility-check (all PASS)

### `tests/`
- `test_geography.py` — grid, point-in-polygon, sea mask, region classification, calibration baseline (14 tests)
- `test_fortifications.py` — CSV loader, parser, region attribution, weight normalization, anchoring count-preservation (13 tests)
- `test_regional_aggregate_equivalence.py` — verifies the per-region CSV sums match the aggregate.txt at every engine checkpoint year (3 tests)
- `test_substrate_placement.py` — verifies the three substrate-configuration placements behave as specified (several tests)

### `docs/`
- `README.md` — this file (at deposit root, but conceptually a docs artifact)
- `REPLICATION.md` — step-by-step reproduction instructions
- `requirements.txt` — Python dependency pins
- `MANUAL_ZENODO_UPLOAD.md` — manual Zenodo upload instructions for the depositor
- `CHANGES_jlg.md` — per-commit changelog covering the full JLG-extension development history

---

## Reproducibility

See [`docs/REPLICATION.md`](docs/REPLICATION.md) for step-by-step instructions.

- Python 3.13.2 on x86-64 is the canonical execution environment.
- Seed 42, 10 runs per scenario, are the canonical settings for all reported numbers.
- Cross-architecture reproduction (different OS / CPU / Python build) is openly invited and disclosed as an outstanding caveat.

The canonical aggregate slavic1 number is `Avg Final Proportion: 11.61% (±2.05%)` under `--scenario slavic1 --num_runs 10 --seed 42 --substrate_config none --fortification_anchor_fraction 0.0`. If your environment reproduces this number digit-exactly the replication has verified the JLG-extension baseline.

---

## Authorship and citation

**Citation (preferred):**

> [author redacted for double-blind review] (2026). *Demographic-Spatial Modeling of Slavic Linguistic Expansion in the Balkans: Replication Package for the JLG Submission* (v1.0.0). Zenodo. [DOI to be assigned at upload]

The JLG paper itself is in preparation; readers seeking the paper text should consult the manuscript when available. The companion submissions referenced under *Related work* (above) provide additional supporting material on the demographic-modeling baseline, the historical-narrative frequency analysis, and the fortifications dataset methodology; permanent identifiers will be added here once those submissions reach decision.

---

## Known limitations

- **Peloponnese region** has 4 grid cells (low statistical resolution); marked with asterisk discipline throughout. Bounding-box extension to 36°N is deferred technical debt.
- **23 fortifications** remain in unassigned inland cells (~13% of usable forts); minor distortion of regional non-Slavic spatial distribution.
- **Constantinople** is not in the fortifications dataset; the model's institutional-anchor configuration is therefore conservative relative to the historical Byzantine urban network.
- **Adriatic Coastal observed toponym density** is heterogeneous between inland (~25%) and urban-coastal (~5%) zones; the midpoint value used in the map figures averages across this heterogeneity.

All four limitations are documented in [`docs/CHANGES_jlg.md`](docs/CHANGES_jlg.md) and will appear in the paper's discussion / limitations section.
