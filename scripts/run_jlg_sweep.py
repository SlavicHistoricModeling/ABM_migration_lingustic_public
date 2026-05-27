"""
the parameter-sweep phase — Regional sweep across substrate x parameter space.

Cartesian product:
  scenarios        : slavic1, slavic2, slavic3, arabic
  substrate_config : none, uniform, cbi_only
  substrate_fraction (uniform/cbi_only only) : 0.10, 0.20, 0.30, 0.40
  revassim_rate (slavic1/2/3 only)           : 0.000, 0.005, 0.015, 0.030, 0.045

Cell tally:
  slavic1/2/3  : none x 1sf x 5ra  +  uniform x 4sf x 5ra  +  cbi_only x 4sf x 5ra = 45
  arabic       : none x 1sf x 1ra  +  uniform x 4sf x 1ra  +  cbi_only x 4sf x 1ra =  9
  total cells  : 3*45 + 9 = 144
  total runs   : 144 * 10 = 1440

The engine has no CLI flag for reverse_assimilation_rate (it lives in the
SCENARIOS dict). Following the pattern of
scripts/run_substrate_revassim_sweep.sh we sed-patch a per-cell COPY of
the engine and run the copy from a per-cell temp working directory. The
canonical engine file is never modified.

Year-260 vs final year: column names retain the year_260_* form per
the parameter-sweep phase spec. For arabic the engine only runs 170 years, so the
"year_260" column actually carries year-169 (the engine's final tick);
this is documented here and in the verification report.

Usage (from the deposit root):
  python scripts/run_jlg_sweep.py            # full sweep, default workers
  python scripts/run_jlg_sweep.py --workers 4
  python scripts/run_jlg_sweep.py --dry-run  # list cells, do not run
  python scripts/run_jlg_sweep.py --skip-gate --skip-timing  # debug shortcuts
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
ENGINE_FILE = ENGINE_DIR / "slavic_migration_submited_v1.py"
GEOGRAPHY_FILE = ENGINE_DIR / "geography.py"
FORTIFICATIONS_FILE = ENGINE_DIR / "fortifications.py"
FORTIFICATIONS_CSV = (
    ENGINE_DIR / "data" / "Justinain_Fortifications_with_Population_Estimates_clean.csv"
)
RESULTS_ROOT = ENGINE_DIR / "results" / "jlg_sweep"
SWEEP_LOG = RESULTS_ROOT / "sweep_log.txt"
SWEEP_SUMMARY_CSV = RESULTS_ROOT / "sweep_summary.csv"

# ---------------------------------------------------------------------------
# Sweep dimensions (edit here for future re-sweeps).
# ---------------------------------------------------------------------------
SCENARIOS = ("slavic1", "slavic2", "slavic3", "arabic")
SUBSTRATE_CONFIGS = ("none", "uniform", "cbi_only")
SUBSTRATE_FRACTIONS = (0.10, 0.20, 0.30, 0.40)
REVASSIM_RATES_SLAVIC = (0.000, 0.005, 0.015, 0.030, 0.045)
REVASSIM_RATES_ARABIC = (0.000,)
NONE_SUBSTRATE_FRACTION = 0.30  # placeholder, ignored by engine when config==none

SEED = 42
NUM_RUNS = 10
FORTIFICATION_ANCHOR_FRACTION = 0.30  # canonical default; matches engine default

CANONICAL_SUBSTRATE_FRACTION = 0.30
CANONICAL_REVASSIM_RATE_SLAVIC = 0.015
CANONICAL_REVASSIM_RATE_ARABIC = 0.000

REGION_BUCKETS = (
    "Carpatho-Balkan Interior",
    "Pannonian Plain",
    "Aegean Littoral",
    "Peloponnese",
    "Albanian Highlands",
    "Adriatic Coastal",
    "Lower Danubian Frontier",
    "unassigned",
)

# Engine year-count per scenario (matches SCENARIOS dict in the engine).
SCENARIO_YEARS = {
    "slavic1": 260,
    "slavic2": 260,
    "slavic3": 260,
    "arabic": 170,
}

def cell_id(scenario: str, substrate_config: str,
            substrate_fraction: float, revassim_rate: float) -> str:
    return (f"{scenario}__{substrate_config}"
            f"__sf{int(round(substrate_fraction * 100)):03d}"
            f"__ra{int(round(revassim_rate * 1000)):03d}")

def build_cells():
    cells = []
    for scen in SCENARIOS:
        ra_list = REVASSIM_RATES_ARABIC if scen == "arabic" else REVASSIM_RATES_SLAVIC
        for sub_cfg in SUBSTRATE_CONFIGS:
            sf_list = (NONE_SUBSTRATE_FRACTION,) if sub_cfg == "none" else SUBSTRATE_FRACTIONS
            for sf in sf_list:
                for ra in ra_list:
                    cells.append({
                        "scenario": scen,
                        "substrate_config": sub_cfg,
                        "substrate_fraction": sf,
                        "revassim_rate": ra,
                        "cell_id": cell_id(scen, sub_cfg, sf, ra),
                    })
    return cells

# ---------------------------------------------------------------------------
# Per-cell execution (runs in a worker process; must be picklable, so we
# keep it as a module-level function and do all I/O via the filesystem).
# ---------------------------------------------------------------------------
def patch_engine_text(engine_src: str, revassim_rate: float) -> str:
    """Substitute the per-scenario reverse_assimilation_rate constants."""
    return re.sub(
        r'("reverse_assimilation_rate"\s*:\s*)[0-9.]+',
        lambda m: f"{m.group(1)}{revassim_rate}",
        engine_src,
    )

def _format_dt(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run_one_cell(cell: dict, env_overrides: dict | None = None,
                 capture_stdout: bool = False) -> dict:
    """Run one sweep cell in an isolated temp working directory.

    Returns a result dict {cell_id, status, wallclock_s, output_dir, error?}.
    """
    t0 = time.time()
    cid = cell["cell_id"]
    output_dir = RESULTS_ROOT / cid
    output_dir.mkdir(parents=True, exist_ok=True)

    engine_src = ENGINE_FILE.read_text(encoding="utf-8")
    patched_src = patch_engine_text(engine_src, cell["revassim_rate"])

    with tempfile.TemporaryDirectory(prefix=f"jlg_sweep_{cid}_") as td:
        td_path = Path(td)
        engine_copy = td_path / "engine.py"
        engine_copy.write_text(patched_src, encoding="utf-8")
        shutil.copy2(GEOGRAPHY_FILE, td_path / "geography.py")
        shutil.copy2(FORTIFICATIONS_FILE, td_path / "fortifications.py")
        (td_path / "data").mkdir()
        shutil.copy2(FORTIFICATIONS_CSV, td_path / "data" / FORTIFICATIONS_CSV.name)

        cmd = [
            sys.executable, str(engine_copy),
            "--scenario", cell["scenario"],
            "--num_runs", str(NUM_RUNS),
            "--seed", str(SEED),
            "--substrate_config", cell["substrate_config"],
            "--substrate_fraction", f"{cell['substrate_fraction']:.2f}",
            "--fortification_anchor_fraction", f"{FORTIFICATION_ANCHOR_FRACTION:.2f}",
        ]
        env = dict(os.environ)
        env["MPLBACKEND"] = "Agg"  # headless matplotlib
        if env_overrides:
            env.update(env_overrides)

        try:
            proc = subprocess.run(
                cmd,
                cwd=td_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            return {
                "cell_id": cid,
                "status": "exception",
                "error": f"{type(exc).__name__}: {exc}",
                "wallclock_s": time.time() - t0,
                "output_dir": str(output_dir),
            }

        if proc.returncode != 0:
            (output_dir / "_stderr.txt").write_text(proc.stderr, encoding="utf-8")
            (output_dir / "_stdout.txt").write_text(proc.stdout, encoding="utf-8")
            return {
                "cell_id": cid,
                "status": "engine_nonzero_exit",
                "error": f"exit code {proc.returncode}; see _stderr.txt",
                "wallclock_s": time.time() - t0,
                "output_dir": str(output_dir),
            }

        scen = cell["scenario"]
        wanted = [
            f"results_{scen}_aggregate.txt",
            f"results_{scen}_per_region.csv",
            f"results_{scen}_per_region_summary.txt",
            f"results_{scen}_cell_signatures.csv",
        ]
        captured = []
        for fn in wanted:
            src = td_path / fn
            if src.exists():
                shutil.copy2(src, output_dir / fn)
                captured.append(fn)

        if capture_stdout:
            (output_dir / "_stdout.txt").write_text(proc.stdout, encoding="utf-8")

    return {
        "cell_id": cid,
        "status": "ok",
        "wallclock_s": time.time() - t0,
        "output_dir": str(output_dir),
        "captured_files": captured,
    }

# ---------------------------------------------------------------------------
# Engine-stability gate (Python re-implementation of the bash script, kept
# here so the sweep is self-contained and works on Windows without bash).
# ---------------------------------------------------------------------------
def run_engine_stability_gate(log) -> tuple[bool, str]:
    log(f"engine-stability gate: starting at {_format_dt(time.time())}")
    with tempfile.TemporaryDirectory(prefix="jlg_sweep_gate_") as td:
        td_path = Path(td)
        shutil.copy2(ENGINE_FILE, td_path / "engine.py")
        shutil.copy2(GEOGRAPHY_FILE, td_path / "geography.py")
        shutil.copy2(FORTIFICATIONS_FILE, td_path / "fortifications.py")
        (td_path / "data").mkdir()
        shutil.copy2(FORTIFICATIONS_CSV, td_path / "data" / FORTIFICATIONS_CSV.name)
        cmd = [
            sys.executable, str(td_path / "engine.py"),
            "--scenario", "slavic1",
            "--num_runs", "10",
            "--seed", "42",
            "--no_plague",
            "--migration_override", "0",
            "--fortification_anchor_fraction", "0.0",
        ]
        env = dict(os.environ)
        env["MPLBACKEND"] = "Agg"
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=td_path, env=env,
                              capture_output=True, text=True, check=False)
        gate_wallclock = time.time() - t0
        if proc.returncode != 0:
            log(f"engine-stability gate: FAIL (exit {proc.returncode})")
            return False, proc.stderr or proc.stdout
        agg = (td_path / "results_slavic1_aggregate.txt").read_text(encoding="utf-8")
        m = re.search(r"year 260:\s+(\d+)", agg)
        if not m:
            log("engine-stability gate: FAIL (could not find 'year 260:' checkpoint)")
            return False, "missing year 260 checkpoint"
        pop = int(m.group(1))
        drift_pct = 100.0 * (pop - 5000) / 5000
        passed = abs(drift_pct) <= 10.0
        msg = (f"engine-stability gate: year 260 mean pop = {pop} "
               f"(drift {drift_pct:+.1f}%), wall = {gate_wallclock:.1f}s, "
               f"verdict = {'PASS' if passed else 'FAIL'}")
        log(msg)
        return passed, msg

# ---------------------------------------------------------------------------
# Pre-sweep timing test (single slavic1 run, no substrate, no anchoring).
# ---------------------------------------------------------------------------
def run_timing_test(log) -> float:
    log(f"timing test: starting at {_format_dt(time.time())}")
    with tempfile.TemporaryDirectory(prefix="jlg_sweep_timing_") as td:
        td_path = Path(td)
        shutil.copy2(ENGINE_FILE, td_path / "engine.py")
        shutil.copy2(GEOGRAPHY_FILE, td_path / "geography.py")
        shutil.copy2(FORTIFICATIONS_FILE, td_path / "fortifications.py")
        (td_path / "data").mkdir()
        shutil.copy2(FORTIFICATIONS_CSV, td_path / "data" / FORTIFICATIONS_CSV.name)
        cmd = [
            sys.executable, str(td_path / "engine.py"),
            "--scenario", "slavic1",
            "--num_runs", "1",
            "--seed", "42",
            "--substrate_config", "none",
            "--fortification_anchor_fraction", "0.0",
        ]
        env = dict(os.environ)
        env["MPLBACKEND"] = "Agg"
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=td_path, env=env,
                              capture_output=True, text=True, check=False)
        wall = time.time() - t0
        if proc.returncode != 0:
            log("timing test: FAIL")
            log(proc.stderr[-2000:])
            raise RuntimeError("timing test engine returned non-zero")
        log(f"timing test: single slavic1 run wall = {wall:.1f}s "
            f"(seed 42, num_runs 1, substrate none, anchor 0.0)")
        return wall

# ---------------------------------------------------------------------------
# Summary CSV (one row per cell x region tuple).
# ---------------------------------------------------------------------------
def _collect_cell_summary(cell: dict) -> list[dict]:
    cid = cell["cell_id"]
    scen = cell["scenario"]
    per_region_csv = RESULTS_ROOT / cid / f"results_{scen}_per_region.csv"
    if not per_region_csv.exists():
        return []
    final_year = SCENARIO_YEARS[scen] - 1
    by_region: dict[str, list[tuple[int, float]]] = {b: [] for b in REGION_BUCKETS}
    with per_region_csv.open("r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            if int(row["year"]) != final_year:
                continue
            bucket = row["region"]
            if bucket not in by_region:
                continue
            by_region[bucket].append((int(row["population"]), float(row["slavic_share"])))
    rows = []
    for bucket in REGION_BUCKETS:
        observations = by_region[bucket]
        pops = [p for p, _ in observations]
        shares = [s for _, s in observations]
        n = len(observations)
        mean_share = statistics.mean(shares) if n else 0.0
        sd_share = statistics.stdev(shares) if n > 1 else 0.0
        mean_pop = statistics.mean(pops) if n else 0.0
        rows.append({
            "scenario": scen,
            "substrate_config": cell["substrate_config"],
            "substrate_fraction": f"{cell['substrate_fraction']:.2f}",
            "revassim_rate": f"{cell['revassim_rate']:.3f}",
            "region": bucket,
            "year_260_slavic_share_mean": f"{mean_share:.6f}",
            "year_260_slavic_share_sd": f"{sd_share:.6f}",
            "year_260_pop_mean": f"{mean_pop:.2f}",
            "run_count": n,
        })
    return rows

def write_sweep_summary(cells: list[dict]) -> None:
    fieldnames = [
        "scenario", "substrate_config", "substrate_fraction", "revassim_rate",
        "region", "year_260_slavic_share_mean", "year_260_slavic_share_sd",
        "year_260_pop_mean", "run_count",
    ]
    with SWEEP_SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for cell in cells:
            for row in _collect_cell_summary(cell):
                w.writerow(row)

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def make_logger(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    def log(msg: str):
        line = f"[{_format_dt(time.time())}] {msg}"
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()
    return log, fh

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--dry-run", action="store_true",
                    help="List cells then exit.")
    ap.add_argument("--skip-gate", action="store_true",
                    help="Skip engine-stability gate (debug only).")
    ap.add_argument("--skip-timing", action="store_true",
                    help="Skip pre-sweep timing test (debug only).")
    ap.add_argument("--force", action="store_true",
                    help="Run even if projected wall > 12 h.")
    ap.add_argument("--cell-filter", default=None,
                    help="Substring filter on cell_id (debug; runs only matching cells).")
    args = ap.parse_args()

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    log, fh = make_logger(SWEEP_LOG)
    try:
        log("=" * 72)
        log(f"sweep run starting; workers={args.workers}")
        log(f"engine: {ENGINE_FILE}")
        log(f"results root: {RESULTS_ROOT}")

        cells = build_cells()
        if args.cell_filter:
            cells = [c for c in cells if args.cell_filter in c["cell_id"]]
        log(f"sweep cells: {len(cells)} (target = 144 for full sweep)")
        if args.dry_run:
            for c in cells:
                log(f"  cell: {c['cell_id']}")
            return 0

        if not args.skip_gate:
            ok, msg = run_engine_stability_gate(log)
            if not ok:
                log(f"engine-stability gate FAILED — aborting sweep. {msg}")
                return 2

        if not args.skip_timing:
            single_run_wall = run_timing_test(log)
            est_cell_wall = single_run_wall * NUM_RUNS
            est_total_serial = est_cell_wall * len(cells)
            est_total_parallel = est_total_serial / args.workers
            est_hr = est_total_parallel / 3600.0
            log(f"projected wall (serial)   = {est_total_serial/3600.0:.2f} h")
            log(f"projected wall (parallel) = {est_total_parallel/3600.0:.2f} h "
                f"at workers={args.workers}")
            if est_hr > 12.0 and not args.force:
                log(f"projected wall > 12 h ({est_hr:.2f} h); aborting per the 12-hour wall-clock threshold. "
                    f"Re-run with --force to proceed.")
                return 3
        else:
            log("timing test skipped (--skip-timing)")

        # ------------------------------------------------------------------
        # Run sweep
        # ------------------------------------------------------------------
        sweep_t0 = time.time()
        log(f"launching {len(cells)} cells across {args.workers} workers")
        results: list[dict] = []
        completed_count = 0

        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            future_to_cell = {ex.submit(run_one_cell, c): c for c in cells}
            for fut in as_completed(future_to_cell):
                c = future_to_cell[fut]
                try:
                    r = fut.result()
                except Exception as exc:
                    r = {
                        "cell_id": c["cell_id"],
                        "status": "future_exception",
                        "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
                        "wallclock_s": 0.0,
                        "output_dir": str(RESULTS_ROOT / c["cell_id"]),
                    }
                results.append(r)
                completed_count += 1
                elapsed = time.time() - sweep_t0
                log(f"  [{completed_count:>3}/{len(cells)}] "
                    f"{r['status']:<22} {r['cell_id']:<55} "
                    f"wall={r['wallclock_s']:.1f}s   "
                    f"sweep_elapsed={elapsed:.0f}s")
                if r["status"] != "ok":
                    log(f"      ERROR: {r.get('error', '?')}")

        sweep_wall = time.time() - sweep_t0
        ok_n = sum(1 for r in results if r["status"] == "ok")
        log(f"sweep complete: {ok_n}/{len(cells)} cells ok; "
            f"wall = {sweep_wall:.1f}s ({sweep_wall/3600.0:.2f} h)")

        # ------------------------------------------------------------------
        # Aggregate sweep_summary.csv
        # ------------------------------------------------------------------
        log("building sweep_summary.csv")
        write_sweep_summary(cells)
        log(f"wrote {SWEEP_SUMMARY_CSV} "
            f"({SWEEP_SUMMARY_CSV.stat().st_size} bytes)")
        log("sweep run finished.")
        return 0 if ok_n == len(cells) else 1
    finally:
        fh.close()

if __name__ == "__main__":
    sys.exit(main())
