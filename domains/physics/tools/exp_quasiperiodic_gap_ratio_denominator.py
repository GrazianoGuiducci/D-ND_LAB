#!/usr/bin/env python3
"""
Stratified denominator audit for the quasiperiodic gap_ratio claim.

The old domandatore observable was:
  first spacing above threshold * mean / second spacing above threshold * mean
at one N, one phase, one threshold.

This tool keeps that observable but exposes its denominator:
N, Sturmian phase, threshold, metallic control, and a balanced random baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from numpy.linalg import eigvalsh


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)


def sturmian_sequence(theta: float, n: int, phase: float = 0.0) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(float)


def hamiltonian(seq: np.ndarray, v: float = 1.0) -> np.ndarray:
    n = len(seq)
    h = np.zeros((n, n), dtype=float)
    h[np.arange(n), np.arange(n)] = v * seq
    off = np.arange(n - 1)
    h[off, off + 1] = 1.0
    h[off + 1, off] = 1.0
    return h


def gap_observables(seq: np.ndarray, threshold: float) -> dict:
    eigs = np.sort(eigvalsh(hamiltonian(seq)))
    spacings = np.diff(eigs)
    mean_sp = float(np.mean(spacings))
    large = [(int(i), float(sp)) for i, sp in enumerate(spacings) if sp > threshold * mean_sp]
    if len(large) >= 2:
        first_two_ratio = large[0][1] / large[1][1]
    else:
        first_two_ratio = None

    top = sorted((float(sp) for sp in spacings), reverse=True)
    top2_ratio = top[0] / top[1] if len(top) >= 2 and top[1] > 0 else None
    return {
        "n_large": len(large),
        "first_two_ratio": first_two_ratio,
        "top2_ratio": top2_ratio,
    }


def finite(values: list[float | None]) -> np.ndarray:
    return np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)


def summarize(values: list[float | None]) -> dict:
    arr = finite(values)
    if len(arr) == 0:
        return {"count": 0}
    return {
        "count": int(len(arr)),
        "median": float(np.median(arr)),
        "q25": float(np.quantile(arr, 0.25)),
        "q75": float(np.quantile(arr, 0.75)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    domains = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }
    ns = [int(x) for x in args.ns.split(",")]
    phases = [float(x) for x in args.phases.split(",")]
    thresholds = [float(x) for x in args.thresholds.split(",")]

    rows = []
    for n in ns:
        for phase in phases:
            for threshold in thresholds:
                condition = {"N": n, "phase": phase, "threshold": threshold}
                matched = {}
                for name, theta in domains.items():
                    seq = sturmian_sequence(theta, n, phase)
                    obs = gap_observables(seq, threshold)
                    matched[name] = obs
                    rows.append({"domain": name, **condition, **obs})

                ones = int(np.sum(sturmian_sequence(1 / PHI, n, phase)))
                for trial in range(args.random_trials):
                    seq = np.array([1.0] * ones + [0.0] * (n - ones))
                    rng.shuffle(seq)
                    obs = gap_observables(seq, threshold)
                    rows.append({"domain": "balanced_random", "trial": trial, **condition, **obs})

                phi_v = matched["phi"]["first_two_ratio"]
                silver_v = matched["silver"]["first_two_ratio"]
                bronze_v = matched["bronze"]["first_two_ratio"]
                if phi_v is not None and silver_v is not None and bronze_v is not None:
                    rows.append({
                        "domain": "_matched_comparison",
                        **condition,
                        "phi_lt_silver": bool(phi_v < silver_v),
                        "phi_lt_bronze": bool(phi_v < bronze_v),
                        "phi_value": phi_v,
                        "silver_value": silver_v,
                        "bronze_value": bronze_v,
                    })

    by_domain = {}
    for domain in sorted({r["domain"] for r in rows if not r["domain"].startswith("_")}):
        subset = [r for r in rows if r["domain"] == domain]
        by_domain[domain] = {
            "first_two_ratio": summarize([r.get("first_two_ratio") for r in subset]),
            "top2_ratio": summarize([r.get("top2_ratio") for r in subset]),
            "large_gap_count": summarize([r.get("n_large") for r in subset]),
        }

    comparisons = [r for r in rows if r["domain"] == "_matched_comparison"]
    comparison_summary = {
        "count": len(comparisons),
        "phi_lt_silver": int(sum(r["phi_lt_silver"] for r in comparisons)),
        "phi_lt_bronze": int(sum(r["phi_lt_bronze"] for r in comparisons)),
        "phi_lt_both": int(sum(r["phi_lt_silver"] and r["phi_lt_bronze"] for r in comparisons)),
    }

    output = {
        "experiment": "quasiperiodic_gap_ratio_denominator",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "random_trials": args.random_trials,
            "seed": args.seed,
        },
        "summary": by_domain,
        "matched_comparison": comparison_summary,
        "rows": rows,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="233,377,500,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="1.75,2.0,2.25")
    parser.add_argument("--random-trials", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260508)
    parser.add_argument("--out", default="tools/data/quasiperiodic_gap_ratio_denominator_20260508_0330.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps({
        "summary": output["summary"],
        "matched_comparison": output["matched_comparison"],
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
