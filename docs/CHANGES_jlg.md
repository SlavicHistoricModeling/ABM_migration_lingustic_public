# CHANGES — JLG geographic extension

This changelog documents the JLG-extension development on top of the parent-submission frozen engine (engine commit `37054ac`, the engine that produced the parent submission). Topics are grouped by the technical component they cover.

Throughout, the following hard constraints have held:

1. The five inherited implementation defects documented in `REPRODUCIBILITY.md` of the parent submission must not be reintroduced. The fixes for all five (per-female birth rate, mother-tongue inheritance, sorted-set tie-break, substrate normalisation, substrate destination) are preserved.
2. The engine-stability gate (`--no_plague --migration_override 0`, ±10 % population sustain over 260 yr) continues to pass.
3. The JLG-extension canonical aggregate slavic1 number (seed-42 10-run, `--substrate_config none --fortification_anchor_fraction 0.0`) remains digit-exactly reproducible at `Avg Final Proportion: 11.61% (+/-2.05%)`. The parent-submission-paper canonical number (`18.35% (+/-4.40%)` on the abstract 50×50 grid) remains reproducible from the parent-submission branch.

---

## 1. Geographic foundation

New module `geography.py`:

- Bounding box lat 38.0–47.0 N, lon 13.0–29.0 E; cell size 0.5° × 0.5°.
- Grid dimensions 18 (north→south) × 32 (west→east); 576 raw cells.
- Hand-coded coarse sea polygons (Adriatic, Ionian, Aegean, Marmara, Black) excluding marine cells from agent placement.
- Seven named-region polygons (Carpatho-Balkan Interior, Pannonian Plain, Aegean Littoral, Peloponnese, Albanian Highlands, Adriatic Coastal, Lower Danubian Frontier). Classification by ray-cast point-in-polygon on cell centres.
- `"unassigned"` preserved as an explicit bucket so any polygon-coverage leakage is visible in per-region accounting rather than silent.
- Precomputed `{(i, j) → region_label}` lookup via `build_region_lookup()` for O(agents) per-year per-region accounting.

Engine refactor (`slavic_migration_submited_v1.py`):

- Replaced the 50×50 abstract toroidal grid with the JLG coordinate-anchored grid. The agent dict's `"x"` / `"y"` keys now carry row index `i ∈ [0, 18)` and column index `j ∈ [0, 32)`.
- Replaced the inline `region_of(x, y)` with the geography module's polygon classification.
- GROUPS-dict region mappings updated to the new polygon region names: Slavic placed in Pannonian Plain + Lower Danubian Frontier; non-Slavic groups distributed across their historically-appropriate polygon regions.
- Migration target switched from "right half of abstract grid" to the SLAVIC_ENTRY_CELLS list.
- Moore-8 neighbourhood is now non-toroidal: out-of-bounds and sea neighbours are skipped.

### Polygon and migration-target refinements

Three issues surfaced during initial verification were addressed:

**Migration-target reorientation (Amendment A).** Diagnostic showed the migration loop was hitting the source set instead of the Balkan destination set. Engine fix: split `SLAVIC_ENTRY_CELLS` into two disjoint pools — `SLAVIC_SOURCE_CELLS` (Pannonian Plain + Lower Danubian Frontier) used only for year-0 initial placement, and `SLAVIC_DEST_CELLS` (Carpatho-Balkan Interior + Aegean Littoral + Albanian Highlands + Adriatic Coastal + Peloponnese) used only as the per-year migration deposit target.

**Polygon refinement (Amendment B).** `geography.py` polygon vertex lists extended: Pannonian Plain's southern edge pulled down to the Sava-Danube line; Lower Danubian Frontier's northern boundary pushed up to lat 47.0 N; Aegean Littoral's western edge pushed from lon 22.5 E to lon 21.5 E and southern edge from lat 39.0 N down to lat 38.3 N.

**Sea-mask land overrides (Amendment C).** 17 fortifications fell on cells the coarse sea polygons claimed are marine. Two override groups added (Lower Danube right bank near the delta, Chalkidiki peninsulas), absorbing the 17 fortifications into Lower Danubian Frontier and Aegean Littoral respectively.

**Peloponnese cell count (Amendment D — deferred).** Peloponnese has 4 cells, below the design target of ~15. Cause is structural: the polygon extends to lat 36.5 N but the bounding box's southern edge sits at lat 38.0 N. Extending the bounding box southward would change grid dimensions to 22 × 32 and shift every engine-stability baseline number. Deferred as known limitation; Peloponnese-region results carry asterisk discipline throughout.

### Fortification anchoring

New module `fortifications.py` and dataset `data/Justinain_Fortifications_with_Population_Estimates_clean.csv` (170 rows of Justinianic fortifications with c. 600 CE population estimates). After all polygon and override amendments: 147 fortifications usable for anchoring (of 170 total); 23 remain in unassigned inland gaps.

Engine flags added:

- `--fortification_anchor_fraction` (float, default 0.30). 0.0 disables anchoring (uniform-in-region placement).
- `--fortification_pop_band` (enum: `low` / `mid` / `high`, default `mid`).

Anchoring runs once at the end of each per-run initial placement, before the year-0 tick. It does not affect subsequent migration, reproduction, or assimilation rules.

---

## 2. Per-region outputs and cell-level toponym signature

The old single `results_{scen}.txt` write step is replaced by four files per scenario:

| filename | tracked? | content |
|---|---|---|
| `results_{scen}_aggregate.txt` | yes | Byte-identical content to the old `results_{scen}.txt` (scenario header, aggregate Slavic share, population and Slavic-share checkpoints) |
| `results_{scen}_per_region.csv` | **gitignored** | Flat CSV: `region, year, run, population, slavic_count, slavic_share, illyrian_thracian_count, greek_count, germanic_count, avar_count, other_count`. One row per (region bucket, year, run). For slavic1 at 10 runs × 260 years × 8 buckets = 20,800 rows. |
| `results_{scen}_per_region_summary.txt` | yes | Human-readable per-region Slavic share at engine checkpoint years |
| `results_{scen}_cell_signatures.csv` | **gitignored** | One row per land cell per run: `cell_i, cell_j, lat, lon, region, signature_language, run, non_empty_ticks`. Cell-level toponym signature: mode of the cell's annual modal-language record across the recording window (years ≥ 130, the midpoint of the 260-year horizon) |

A regression test (`tests/test_regional_aggregate_equivalence.py`) verifies that the aggregate Slavic share parsed from `results_slavic1_aggregate.txt` matches the sum-of-per-region-CSV value at every engine checkpoint year.

---

## 3. Substrate placement configurations

Three named substrate placement configurations introduced, selected via `--substrate_config` enum (default `none`):

- **`none`** — preserves the post-amendment no-substrate baseline. The five Balkan destination regions hold ~0 % Slavic at year 0. `--substrate_fraction` is ignored. This is the no-substrate null.
- **`uniform`** — substrate Slavs placed in all five Balkan destination regions. Within each, year-0 Slavic share = `substrate_fraction`. Non-Slavic fractions in each substrate-receiving region scale by `(1 − substrate_fraction)` to preserve regional agent count.
- **`cbi_only`** — substrate concentrated in Carpatho-Balkan Interior only. Within CBI, year-0 Slavic share = `substrate_fraction`; other four Balkan destinations retain 0 % initial Slavic.

In all three configurations, Pannonian Plain and Lower Danubian Frontier retain their standard source-region initial Slavic placement (substrate is additive, not displacing source).

The `none` path remains bit-identical to the post-amendment engine at seed 42; this is verified by the test suite. `cbi_only` is the operational form of the substrate-continuity hypothesis the JLG paper argues for; `uniform` is the alternative hypothesis that the substrate was distributed across all Balkan destinations.

---

## 4. Parameter sweep

`scripts/run_jlg_sweep.py` orchestrates a 144-cell Cartesian sweep:

| dimension | values | n |
|---|---|---:|
| scenario | slavic1, slavic2, slavic3, arabic | 4 |
| substrate_config | none, uniform, cbi_only | 3 |
| substrate_fraction (uniform / cbi_only only) | 0.10, 0.20, 0.30, 0.40 | 4 |
| reverse_assimilation_rate (slavic1 / slavic2 / slavic3 only) | 0.000, 0.005, 0.015, 0.030, 0.045 | 5 |

Cell counts: slavic1 + slavic2 + slavic3 each = 5 (none) + 20 (uniform) + 20 (cbi_only) = 45. arabic = 1 (none) + 4 (uniform) + 4 (cbi_only) = 9. **Total = 144 cells × 10 runs = 1,440 model runs.** seed = 42; fortification_anchor_fraction = 0.30 for every cell.

The engine has no CLI flag for `reverse_assimilation_rate` — the value lives in the per-scenario `SCENARIOS` dict in the engine module. The sweep substitutes the rate in a per-cell temporary copy of the engine via `re.sub` and runs the copy from a per-cell temporary working directory; the canonical engine file is never modified.

The sweep harness includes a pre-flight engine-stability gate and a pre-sweep timing-test wall-clock projection. Per-cell outputs are written to `results/jlg_sweep/{cell_id}/`; the consolidated `sweep_summary.csv` (1,152 rows = 144 cells × 8 region buckets) drives all downstream summary tables and figures.

### Sweep-derived summary tables

Three tables under `results/jlg_sweep/`:

- `aggregate_by_scenario.csv` — 12 rows, one per (scenario × substrate_config). Aggregate Slavic share = land-weighted mean across the eight buckets per cell, then mean / min / max across cells in the (scenario × config) slice.
- `per_region_year260_canonical.csv` — 96 rows. Per-region year-260 Slavic share at substrate_fraction = 0.30, revassim_rate = 0.015 for slavic1/2/3, revassim_rate = 0.000 for arabic.
- `cbi_substrate_robustness.csv` — 20 rows. The slavic1 cbi_only (sf × ra) grid that adjudicates "does the CBI substrate persist?" across the parameter space.

### Sweep-derived figures

Three figures under `figures/jlg_sweep/`:

- `regional_outcomes_canonical.png` — 4-panel bar chart, one panel per scenario, eight regions × three substrate_configs per panel.
- `cbi_substrate_heatmap.png` — heatmap of slavic1 cbi_only CBI year-260 Slavic share across the (sf × ra) parameter grid.
- `coastal_substrate_decay.png` — line chart of coastal-region year-260 Slavic share vs substrate_fraction under uniform configuration, with CBI as a comparison line.

### Canonical-RA resolution

The engine's per-scenario `reverse_assimilation_rate` defaults are slavic1 = 0.030, slavic2 = 0.020, slavic3 = 0.015, arabic = 0.000 (per the SCENARIOS dict in `slavic_migration_submited_v1.py`). The initial sweep-results write-up used ra = 0.015 as canonical, which matches slavic3's default but not slavic1's. For continuity with the parent submission, the slavic1 parent-submission-default ra = 0.030 was adopted as the paper canonical and three side-by-side tables were produced under `results/jlg_sweep/canonical/`:

- `per_region_year260_canonical_ra015.csv` (96 rows)
- `per_region_year260_canonical_ra030.csv` (96 rows; the recommended paper canonical)
- `per_region_year260_canonical_ra045.csv` (96 rows; conservative stress test)
- `CANONICAL_COMPARISON.md` (slavic1 side-by-side at ra ∈ {0.015, 0.030, 0.045}; 15 rows)

The "CBI persists, coast does not" pattern is qualitatively robust across the three ra values; the magnitude of CBI persistence is ra-dependent (slavic1 cbi_only at sf=0.30: 23.0 % at ra=0.015, 15.1 % at ra=0.030, 10.8 % at ra=0.045).

### Headline empirical finding

At slavic1 canonical parameters (sf = 0.30, ra = 0.030, fortification_anchor = 0.30), the cbi_only configuration is the only configuration that produces a per-region year-260 Slavic-share gradient resembling the observed Slavic toponymic gradient. CBI year-260 Slavic share = 15.08 % ± 6.87 %; all four coastal destinations (Aegean / Peloponnese / Albanian / Adriatic) ≤ 0.25 %. uniform slavic1 elevates coastal substrate (Aegean 0.2 %, Adriatic 0.2 % at ra = 0.030) and none slavic1 fails to reach observed CBI levels (2.81 % ± 2.29 % at ra = 0.030). slavic2 and slavic3 saturate too uniformly across regions to match the observed coast/interior contrast. arabic is invariant under substrate placement (engine forces ra = 0 for arabic).

---

## 5. Geographic map figures

New tracked CSV `data/observed_toponym_density.csv` compiles observed Slavic toponym density per region from the published toponymic literature (Skok 1971–1974, Loma 2002, Zaimov 1973, Vasmer 1941, Malingoudis 1981, Ylli 2000, Skok 1950, Muljačić 2000). Per-region midpoint values: CBI 0.85, Pannonian 0.70, Lower Danube 0.70, Albanian 0.25, Peloponnese 0.20, Adriatic 0.15, Aegean 0.10.

Five publication-quality choropleth maps under `figures/jlg_maps/` (cartopy PlateCarree projection over the JLG bounding box, viridis or RdBu_r colormap, 300 dpi, single-column 8.5 cm or two-column 17.4 cm width):

- `observed_toponym_density.png` — Figure JLG-1 (observed values)
- `modeled_cbi_only_year260.png` — Figure JLG-2 (modeled cbi_only canonical)
- `modeled_none_year260.png` — Figure JLG-3 (modeled none baseline)
- `observed_vs_modeled_comparison.png` — Figure JLG-4 (**paper headline visual**, two-panel side-by-side)
- `observed_minus_modeled_residuals.png` — Figure JLG-5 (RdBu_r diverging residual map)

Paper-ready captions under `figures/jlg_maps/captions/`; PIL L-mode greyscale-check copies under `figures/jlg_maps/_greyscale_check/` (all five pass).

The qualitative observation on Figure JLG-4: the cbi_only configuration matches the observed CBI-high / coast-low gradient in direction. The largest magnitude disagreement is CBI itself (observed 85 %, modeled 15 %, residual +69.9 pp — the model captures the geographic pattern but under-predicts the magnitude of interior substrate persistence at canonical parameters).

---

## 6. Known limitations carried into the paper

- **Peloponnese region** has 4 grid cells (low statistical resolution); marked with asterisk discipline throughout. Bounding-box extension to 36°N is deferred technical debt.
- **23 fortifications** remain in unassigned inland cells (~13 % of usable forts); minor distortion of regional non-Slavic spatial distribution.
- **Constantinople** is not in the fortifications dataset; the model's institutional-anchor configuration is therefore conservative relative to the historical Byzantine urban network.
- **Adriatic Coastal observed toponym density** is heterogeneous between inland (~25 %) and urban-coastal (~5 %) zones; the midpoint value used in the map figures averages across this heterogeneity.

These four limitations are documented in the paper's discussion / limitations section.
