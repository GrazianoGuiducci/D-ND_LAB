#!/usr/bin/env python3
"""
Exact local-window matrix for the finite Rosenzweig-Porter boundary crest.

The historical unfolding audit forces local windows to odd widths.  This
wrapper preserves even widths so windows 9/10/11/12 are distinct experimental
coordinates, then reuses the row-aligned two-reader/null machinery.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

import exp_rp_unfolding_sensitivity_audit as base


def exact_local_unfold_gaps(gaps: np.ndarray, window: int) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
    if len(gaps) == 0:
        return gaps
    width = max(2, min(int(window), len(gaps)))
    unfolded = np.empty_like(gaps)
    left = width // 2
    for idx in range(len(gaps)):
        start = idx - left
        end = start + width
        if start < 0:
            start = 0
            end = width
        if end > len(gaps):
            end = len(gaps)
            start = max(0, end - width)
        local_mean = float(np.mean(gaps[start:end]))
        if local_mean <= 1e-12:
            local_mean = float(np.mean(gaps))
        unfolded[idx] = gaps[idx] / local_mean
    return unfolded


def parse_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def run(args: argparse.Namespace) -> dict[str, Any]:
    original_unfolder = base.local_unfold_gaps
    base.local_unfold_gaps = exact_local_unfold_gaps
    try:
        windows = parse_ints(args.local_windows)
        sizes = parse_ints(args.sizes)
        lambdas = parse_floats(args.lambdas)
        window_outputs = []
        matrix_rows = []
        for window in windows:
            out_path = Path(args.out).with_name(Path(args.out).stem + f"_w{window}.json")
            base_args = SimpleNamespace(
                out=str(out_path),
                sizes=args.sizes,
                reps=args.reps,
                lambdas=args.lambdas,
                seeds=args.seeds,
                k_values=args.k_values,
                label_null_trials=args.label_null_trials,
                position_offsets=args.position_offsets,
                central_fraction=args.central_fraction,
                grid_size=args.grid_size,
                poisson_pole_max=args.poisson_pole_max,
                gue_pole_min=args.gue_pole_min,
                min_observed_rate=args.min_observed_rate,
                min_lift=args.min_lift,
                alpha=args.alpha,
                unfolding_modes="local_window",
                local_window=window,
            )
            result = base.run(base_args)
            window_outputs.append(
                {
                    "local_window": window,
                    "path": str(out_path),
                    "summary": result["summary"],
                }
            )
            for lam in lambdas:
                name = f"RP_lambda_{lam:.3f}"
                pass_sizes = []
                cell_rows = []
                for entry in result["by_size_mode"]:
                    row = next(item for item in entry["rows"] if item["domain_window"] == name)
                    if row["threshold_pass"]:
                        pass_sizes.append(entry["n"])
                    cell_rows.append(
                        {
                            "n": entry["n"],
                            "observed_successes": row["observed_successes"],
                            "observed_total": row["observed_total"],
                            "label_shuffle_successes": row["label_shuffle_successes"],
                            "label_shuffle_total": row["label_shuffle_total"],
                            "position_shift_successes": row["position_shift_successes"],
                            "position_shift_total": row["position_shift_total"],
                            "max_null_p": max(
                                row["label_shuffle_binomial_tail_p"],
                                row["position_shift_binomial_tail_p"],
                            ),
                            "min_lift_against_nulls": row["min_lift_against_nulls"],
                            "threshold_pass": row["threshold_pass"],
                            "classical_audit_state": row["classical_audit_state"],
                        }
                    )
                matrix_rows.append(
                    {
                        "local_window": window,
                        "lambda": round(lam, 6),
                        "domain_window": name,
                        "pass_sizes": pass_sizes,
                        "pass_cells": len(pass_sizes),
                        "total_cells": len(sizes),
                        "cells": cell_rows,
                    }
                )

        crest = f"RP_lambda_{args.crest_lambda:.3f}"
        crest_rows = [row for row in matrix_rows if row["domain_window"] == crest]
        output = {
            "experiment": "rp_exact_local_window_matrix",
            "question": "Does RP_lambda_0.060 survive exact local windows 9/10/11/12 at sizes beyond 192?",
            "observables_registry": base.OBSERVABLES_REGISTRY_VERSION,
            "observables_used": base.FEATURE_NAMES
            + [
                "observed_successes",
                "label_shuffle_successes",
                "position_shift_successes",
                "Wilson intervals",
                "binomial-tail p-values",
                "min_lift_against_nulls",
                "threshold_pass",
                "exact_local_window",
            ],
            "parameters": {
                "sizes": sizes,
                "reps": args.reps,
                "lambdas": lambdas,
                "crest_lambda": args.crest_lambda,
                "seeds": parse_ints(args.seeds),
                "k_values": parse_ints(args.k_values),
                "label_null_trials": args.label_null_trials,
                "position_offsets": parse_ints(args.position_offsets),
                "local_windows": windows,
                "unfolding_patch": "exact even windows preserved; no odd-width coercion",
            },
            "threshold_preregistered": {
                "min_observed_rate": args.min_observed_rate,
                "min_lift_against_each_null": args.min_lift,
                "alpha_each_null": args.alpha,
                "classical_clause": "classical_intermediate required for two-reader threshold pass",
                "persistence_clause": "crest survives only if it passes every declared size and exact local window",
            },
            "observable_contract": {
                "claim": "RP_lambda_0.060 is a finite-size persistence crest only if it beats both row-aligned nulls at every exact local window 9/10/11/12 and size beyond 192",
                "observable": "thresholded two-reader raw-count pass by lambda, exact local_window and size",
                "operator": "exact-width local unfolding matrix with label-shuffle and position-shift nulls",
                "generator": "H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE",
                "denominator": "sentinel lambda grid x sizes x windows; observed denominator seeds*k; null denominators observed*trials or observed*offsets",
                "non_possible": "single-lambda boundary if any declared exact window or size fails threshold",
                "not_tested": "N to infinity, windows beyond 12, alternate unfolding kernels, experimental spectra, Anderson 3D",
            },
            "summary": {
                "crest_domain_window": crest,
                "crest_pass_cells": sum(row["pass_cells"] for row in crest_rows),
                "crest_total_cells": sum(row["total_cells"] for row in crest_rows),
                "crest_all_cells_pass": all(
                    cell["threshold_pass"] for row in crest_rows for cell in row["cells"]
                ),
                "window_outputs": window_outputs,
            },
            "matrix_rows": matrix_rows,
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(output["summary"], indent=2, sort_keys=True))
        return output
    finally:
        base.local_unfold_gaps = original_unfolder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/rp_exact_local_window_matrix_20260516_1019.json")
    parser.add_argument("--sizes", default="224,256")
    parser.add_argument("--reps", type=int, default=8)
    parser.add_argument("--lambdas", default="0.03,0.045,0.06,0.075,0.82")
    parser.add_argument("--crest-lambda", type=float, default=0.06)
    parser.add_argument("--local-windows", default="9,10,11,12")
    parser.add_argument("--seeds", default="202605161019,202605161020,202605161021,202605161022")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--label-null-trials", type=int, default=64)
    parser.add_argument("--position-offsets", default="1,2,3,4")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--poisson-pole-max", type=float, default=0.03)
    parser.add_argument("--gue-pole-min", type=float, default=0.82)
    parser.add_argument("--min-observed-rate", type=float, default=0.75)
    parser.add_argument("--min-lift", type=float, default=0.10)
    parser.add_argument("--alpha", type=float, default=0.05)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
