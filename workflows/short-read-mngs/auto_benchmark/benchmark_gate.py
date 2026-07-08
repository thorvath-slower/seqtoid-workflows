#!/usr/bin/env python3
"""
CZID-160: benchmark correctness gate.

Turns the short-read-mngs benchmark from an advisory run (a Jupyter notebook that
merely color-codes deviations and emits a `::warning::`) into a hard pass/fail
CI gate. It reads the per-sample JSON produced by harvest.py and enforces two
independent criteria:

  1. Deviation gate (default, used for the fast CI viral benchmark):
     each tracked metric (NT_aupr, NR_aupr) must be within `--tolerance`
     (relative, default 0.01 == 1 percent) of the pinned reference-library
     value for that sample. This is the CI equivalent of the notebook's
     `.short-read-mngs-benchmarks-deviation` sentinel, but it EXITS NON-ZERO
     instead of only warning.

  2. Absolute AUPR floor (opt-in, used for the full-index benchmark / release):
     when `--min-aupr` is supplied, each sample's NT_aupr and NR_aupr must be
     >= the floor (default beta-readiness bar is 0.98). The fast CI viral run
     uses a mini viral reference DB whose reference AUPRs are ~0.2-0.4, so the
     0.98 floor is NOT applied there -- only the full-index benchmark asserts it.

Exit status is 0 when every sample passes every applied criterion, 1 otherwise.
A human-readable table is printed to stdout and GitHub Actions error annotations
are emitted for each failure.

Usage:
  # CI viral gate: fail on any >1 percent deviation from the reference library
  benchmark_gate.py idseq_bench_3.default_viral.json idseq_bench_5.default_viral.json \\
      --ref-lib ref_libs/default_viral

  # full-index release gate: also require absolute AUPR >= 0.98
  benchmark_gate.py *.default_full.json --ref-lib ref_libs/default_full --min-aupr 0.98
"""

import os
import sys
import json
import math
import argparse
from pathlib import Path

# Metrics compared against the reference library. These are the correctness
# signals harvest.py records per sample.
TRACKED_METRICS = ("NT_aupr", "NR_aupr")


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _relative_deviation(observed, reference):
    """Relative deviation of observed from reference. NaN/non-float observed is
    treated as an infinite deviation so it always fails the gate."""
    if not isinstance(observed, (int, float)) or math.isnan(float(observed)):
        return math.inf
    if reference in (0, 0.0):
        # Avoid divide-by-zero: fall back to absolute difference.
        return abs(float(observed) - float(reference))
    return abs(float(observed) - float(reference)) / abs(float(reference))


def _annotate(msg):
    """Emit a GitHub Actions error annotation (no-op-friendly locally)."""
    print(f"::error ::{msg}")


def evaluate(harvest_paths, ref_lib_dir, tolerance, min_aupr):
    """Returns (rows, failures). rows is a list of dicts for reporting;
    failures is a list of human-readable failure strings."""
    rows = []
    failures = []

    for harvest_path in harvest_paths:
        harvested = _load(harvest_path)
        # harvest.py emits {sample_name: {..., NT_aupr, NR_aupr, ...}, ...}
        for sample, results in harvested.items():
            ref = None
            if ref_lib_dir is not None:
                ref_path = Path(ref_lib_dir) / f"{sample}.json"
                if ref_path.exists():
                    ref = _load(ref_path)
                else:
                    failures.append(
                        f"{sample}: no reference library entry at {ref_path}"
                    )
                    _annotate(f"{sample}: missing reference library file {ref_path}")

            for metric in TRACKED_METRICS:
                observed = results.get(metric)
                row = {
                    "sample": sample,
                    "metric": metric,
                    "observed": observed,
                    "reference": (ref or {}).get(metric) if ref else None,
                    "deviation": None,
                    "status": "OK",
                }

                # Absolute floor check (opt-in).
                if min_aupr is not None:
                    if not isinstance(observed, (int, float)) or math.isnan(
                        float(observed)
                    ) or float(observed) < min_aupr:
                        row["status"] = "FAIL(floor)"
                        failures.append(
                            f"{sample}.{metric}={observed} below AUPR floor {min_aupr}"
                        )
                        _annotate(
                            f"{sample} {metric}={observed} below AUPR floor {min_aupr}"
                        )

                # Deviation check (default).
                if ref is not None and metric in ref:
                    dev = _relative_deviation(observed, ref[metric])
                    row["deviation"] = dev
                    if dev > tolerance:
                        pretty = "inf" if math.isinf(dev) else f"{dev * 100:.3f}%"
                        row["status"] = "FAIL(deviation)"
                        failures.append(
                            f"{sample}.{metric}={observed} deviates {pretty} from "
                            f"reference {ref[metric]} (tolerance {tolerance * 100:.1f}%)"
                        )
                        _annotate(
                            f"{sample} {metric} deviates {pretty} from reference "
                            f"(tolerance {tolerance * 100:.1f}%)"
                        )

                rows.append(row)

    return rows, failures


def _print_table(rows):
    header = f"{'sample':<24} {'metric':<8} {'observed':>12} {'reference':>12} {'deviation':>12} status"
    print(header)
    print("-" * len(header))
    for r in rows:
        obs = "n/a" if r["observed"] is None else f"{r['observed']:.6f}"
        refv = "n/a" if r["reference"] is None else f"{r['reference']:.6f}"
        if r["deviation"] is None:
            devv = "n/a"
        elif math.isinf(r["deviation"]):
            devv = "inf"
        else:
            devv = f"{r['deviation'] * 100:.3f}%"
        print(f"{r['sample']:<24} {r['metric']:<8} {obs:>12} {refv:>12} {devv:>12} {r['status']}")


def main(argv):
    parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]),
        description="Gate a benchmark run on correctness thresholds (CZID-160).",
    )
    parser.add_argument(
        "harvest_json",
        metavar="HARVEST.json",
        nargs="+",
        help="per-sample benchmark JSON produced by harvest.py",
    )
    parser.add_argument(
        "--ref-lib",
        metavar="DIR",
        default=None,
        help="reference-library directory holding <sample>.json baselines "
        "(enables the deviation gate)",
    )
    parser.add_argument(
        "--tolerance",
        metavar="FRACTION",
        type=float,
        default=0.01,
        help="max allowed relative deviation from reference (default 0.01 == 1 percent)",
    )
    parser.add_argument(
        "--min-aupr",
        metavar="FLOOR",
        type=float,
        default=None,
        help="absolute NT/NR AUPR floor to enforce (e.g. 0.98 for the full-index "
        "release gate); omit to skip the floor check",
    )
    args = parser.parse_args(argv[1:])

    rows, failures = evaluate(
        args.harvest_json, args.ref_lib, args.tolerance, args.min_aupr
    )
    _print_table(rows)

    if failures:
        print(f"\nBENCHMARK GATE FAILED: {len(failures)} check(s) failed", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nBENCHMARK GATE PASSED: all tracked metrics within thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
