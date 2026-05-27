#!/usr/bin/env bash
# Engine-stability gate for the jlg-geographic-extension branch family.
#
# Re-runs the no-plague / no-migration baseline (parent-submission REPRODUCIBILITY.md §4
# Defect 1 verification) on the coordinate-anchored JLG grid, with
# fortification anchoring disabled (--fortification_anchor_fraction 0.0).
# The year-260 mean population must sit within +/-10 % of the initial
# 5000 agents.
#
# Usage:
#   bash scripts/check_engine_stability_gate.sh
#
# Writes results_slavic1.txt next to the engine; the script parses the
# final population checkpoint line and exits non-zero if drift exceeds
# the +/-10 % band.
set -euo pipefail

cd "$(dirname "$0")/.."

python slavic_migration_submited_v1.py \
    --scenario slavic1 \
    --num_runs 10 \
    --seed 42 \
    --no_plague \
    --migration_override 0 \
    --fortification_anchor_fraction 0.0

python - <<'PY'
import re, sys
text = open("results_slavic1_aggregate.txt").read()
m = re.search(r"year 260:\s+(\d+)", text)
if not m:
    print("could not find 'year 260:' checkpoint in results_slavic1.txt",
          file=sys.stderr)
    sys.exit(2)
pop = int(m.group(1))
drift_pct = 100.0 * (pop - 5000) / 5000
print(f"engine-stability gate: year 260 mean pop = {pop} "
      f"(drift {drift_pct:+.1f}%)")
if abs(drift_pct) > 10.0:
    print(f"FAIL: drift {drift_pct:+.1f}% outside +/-10 %% band",
          file=sys.stderr)
    sys.exit(1)
print("PASS")
PY
