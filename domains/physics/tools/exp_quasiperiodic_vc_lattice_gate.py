#!/usr/bin/env python3
"""
Quasiperiodic V_c lattice gate.

The Domandatore scale probe tried to fit V_c(N) with a power law. For phi the
fit did not converge and the measured values repeated on a small grid. This
tool treats that failure as the signal: it measures whether V_c lives on a
small boundary lattice across Fibonacci sizes, phases, and controls.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.linalg import eigvalsh_tridiagonal


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)


def sturmian_sequence(theta: float, n: int, phase: float = 0.0) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(float)


def r_statistic_from_diag(diagonal: np.ndarray) -> float:
    offdiag = np.ones(len(diagonal) - 1, dtype=float)
    eigs = eigvalsh_tridiagonal(diagonal, offdiag, check_finite=False)
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 1e-12]
    if len(spacings) < 2:
        return 0.5
    left = spacings[:-1]
    right = spacings[1:]
    return float(np.mean(np.minimum(left, right) / np.maximum(left, right)))


def find_vc(seq: np.ndarray, v_values: np.ndarray, threshold: float) -> dict:
    curve = []
    for v in v_values:
        r_value = r_statistic_from_diag(v * seq)
        curve.append((float(v), r_value))
        if r_value < threshold:
            return {
                "vc": float(v),
                "r_at_vc": r_value,
                "crossed": True,
                "curve_head": curve[:5],
            }
    return {
        "vc": None,
        "r_at_vc": None,
        "crossed": False,
        "curve_head": curve[:5],
    }


def summarize(values: list[float | None], grid_step: float) -> dict:
    finite = [float(v) for v in values if v is not None and np.isfinite(v)]
    if not finite:
        return {"count": 0}
    rounded = [round(v / grid_step) * grid_step for v in finite]
    counts: dict[str, int] = {}
    for value in rounded:
        key = f"{value:.6f}"
        counts[key] = counts.get(key, 0) + 1
    total = len(rounded)
    return {
        "count": total,
        "none_count": len(values) - total,
        "distinct_vc": len(counts),
        "repeat_rate": float(1 - (len(counts) / total)),
        "mode_count": int(max(counts.values())),
        "mode_rate": float(max(counts.values()) / total),
        "median": float(np.median(finite)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "rounded_counts": dict(sorted(counts.items())),
    }


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    v_values = np.arange(args.v_min, args.v_max + (args.v_step / 2), args.v_step)
    domains = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }

    rows = []
    for n in ns:
        for phase in phases:
            phi_seq = sturmian_sequence(1 / PHI, n, phase)
            ones = int(np.sum(phi_seq))

            for domain, theta in domains.items():
                seq = sturmian_sequence(theta, n, phase)
                result = find_vc(seq, v_values, args.threshold)
                rows.append({
                    "domain": domain,
                    "N": n,
                    "phase": phase,
                    "ones": int(np.sum(seq)),
                    **result,
                })

            for trial in range(args.random_trials):
                seq = np.array([1.0] * ones + [0.0] * (n - ones), dtype=float)
                rng.shuffle(seq)
                result = find_vc(seq, v_values, args.threshold)
                rows.append({
                    "domain": "balanced_random_phi_density",
                    "trial": trial,
                    "N": n,
                    "phase": phase,
                    "ones": ones,
                    **result,
                })

    summary = {}
    for domain in sorted({row["domain"] for row in rows}):
        subset = [row for row in rows if row["domain"] == domain]
        summary[domain] = summarize([row["vc"] for row in subset], args.v_step)

    summary_by_domain_phase = {}
    grouped: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["domain"], row["phase"])].append(row)
    for (domain, phase), subset in sorted(grouped.items()):
        summary_by_domain_phase[f"{domain}|phase={phase}"] = summarize(
            [row["vc"] for row in subset], args.v_step
        )

    phi_main = [
        row["vc"]
        for row in rows
        if row["domain"] == "phi" and abs(row["phase"]) < 1e-12
    ]
    original_phi = [1.017, 0.672, 1.017, 0.672, 0.931]

    return {
        "experiment": "quasiperiodic_vc_lattice_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "v_min": args.v_min,
            "v_max": args.v_max,
            "v_step": args.v_step,
            "threshold": args.threshold,
            "random_trials": args.random_trials,
            "seed": args.seed,
        },
        "source_domandatore_phi_values": original_phi,
        "phi_phase0_values": phi_main,
        "summary": summary,
        "summary_by_domain_phase": summary_by_domain_phase,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="89,144,233,377,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=3.0)
    parser.add_argument("--v-step", type=float, default=0.025)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--random-trials", type=int, default=4)
    parser.add_argument("--seed", type=int, default=202605082140)
    parser.add_argument("--out", default="tools/data/quasiperiodic_vc_lattice_gate_20260508_2140.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        "summary": output["summary"],
        "phi_phase0_values": output["phi_phase0_values"],
        "out": str(out),
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
