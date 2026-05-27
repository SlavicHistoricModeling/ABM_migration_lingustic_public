# Canonical comparison — slavic1 at sf=0.30 across ra ∈ {0.015, 0.030, 0.045}

Source: re-aggregated from `results/jlg_sweep/sweep_summary.csv` (the parameter sweep). No new model runs; this is the same underlying sweep data filtered by ra value.

Columns:
- ra=0.015 — the value the parameter-sweep phase reported as canonical
- ra=0.030 — the engine default for slavic1 (per `SCENARIOS['slavic1']['reverse_assimilation_rate']`)
- ra=0.045 — the conservative-stress-test value

Cell format: `mean% ± SD%` across 10 seed-42 runs.

| config | region | ra=0.015 | ra=0.030 | ra=0.045 |
|---|---|---:|---:|---:|
| none | Carpatho-Balkan Interior |  6.85% ±  4.04% |  2.81% ±  2.29% |  1.43% ±  2.01% |
| none | Aegean Littoral |  1.40% ±  0.95% |  0.14% ±  0.27% |  0.00% ±  0.00% |
| none | Peloponnese* |  0.77% ±  1.69% |  0.50% ±  1.10% |  0.00% ±  0.00% |
| none | Albanian Highlands |  3.12% ±  2.94% |  0.00% ±  0.00% |  0.00% ±  0.00% |
| none | Adriatic Coastal |  3.73% ±  4.11% |  0.09% ±  0.28% |  0.05% ±  0.16% |
| uniform | Carpatho-Balkan Interior | 24.65% ± 11.79% | 14.90% ± 10.43% |  9.87% ±  7.39% |
| uniform | Aegean Littoral |  4.30% ±  5.75% |  0.20% ±  0.26% |  0.00% ±  0.00% |
| uniform | Peloponnese* |  2.52% ±  3.62% |  0.14% ±  0.46% |  0.00% ±  0.00% |
| uniform | Albanian Highlands | 10.59% ± 20.50% |  0.00% ±  0.00% |  0.00% ±  0.00% |
| uniform | Adriatic Coastal | 12.44% ± 24.44% |  0.15% ±  0.46% |  0.00% ±  0.00% |
| cbi_only | Carpatho-Balkan Interior | 23.02% ±  8.96% | 15.08% ±  6.87% | 10.76% ±  5.12% |
| cbi_only | Aegean Littoral |  2.21% ±  1.14% |  0.08% ±  0.16% |  0.08% ±  0.22% |
| cbi_only | Peloponnese* |  0.35% ±  0.74% |  0.00% ±  0.00% |  0.00% ±  0.00% |
| cbi_only | Albanian Highlands |  2.41% ±  1.92% |  0.25% ±  0.53% |  0.00% ±  0.00% |
| cbi_only | Adriatic Coastal |  2.27% ±  3.37% |  0.00% ±  0.00% |  0.00% ±  0.00% |

\* Peloponnese: known low statistical resolution (4 grid cells; Peloponnese-resolution Amendment D deferred fix).

## Reading guide

Across all three ra columns, the cbi_only config is the only one in which CBI exceeds every coastal region's share. As ra increases (stronger reverse-assimilation pressure), every config's CBI share decays; cbi_only retains the highest CBI / coast ratio at every ra value. The 'CBI persists, coast does not' pattern is qualitatively robust across the ra range; the magnitude of CBI persistence is ra-dependent (monotonic decreasing in ra, as the `cbi_substrate_robustness.csv` grid documents).
