#!/usr/bin/env python3
"""
Aubry/Fibonacci boundary phase transport gate.

Projects the live BOUNDARY direction into a 1D tight-binding model with binary
quasiperiodic potentials. The test is deliberately joint: a boundary return is
accepted only when the phi stack is between periodic order and balanced random
disorder for both spectral spacing and eigenstate localization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)


def sturmian_sequence(theta: float, n: int, phase: float) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(float)


def periodic_sequence(n: int) -> np.ndarray:
    return (np.arange(n) % 2).astype(float)


def hamiltonian(diagonal: np.ndarray) -> np.ndarray:
    n = len(diagonal)
    matrix = np.diag(diagonal.astype(float))
    off = np.ones(n - 1, dtype=float)
    matrix += np.diag(off, 1) + np.diag(off, -1)
    return matrix


def central_slice(n: int, central_fraction: float) -> slice:
    keep = max(8, int(round(n * central_fraction)))
    keep = min(n, keep)
    start = (n - keep) // 2
    return slice(start, start + keep)


def spacing_r(levels: np.ndarray, central_fraction: float) -> float | None:
    levels = np.sort(np.asarray(levels, dtype=float))
    central = levels[central_slice(len(levels), central_fraction)]
    gaps = np.diff(central)
    gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
    if len(gaps) < 2:
        return None
    left = gaps[:-1]
    right = gaps[1:]
    return float(np.mean(np.minimum(left, right) / np.maximum(left, right)))


def localization_metrics(vectors: np.ndarray, central_fraction: float) -> dict[str, float]:
    n = vectors.shape[0]
    subset = vectors[:, central_slice(n, central_fraction)]
    probs = np.square(np.abs(subset))
    ipr = np.sum(probs * probs, axis=0)
    entropy = []
    for col in range(probs.shape[1]):
        p = probs[:, col]
        p = p[p > 1e-15]
        entropy.append(float(-np.sum(p * np.log(p)) / np.log(n)))
    return {
        "mean_ipr": float(np.mean(ipr)),
        "median_ipr": float(np.median(ipr)),
        "participation_entropy": float(np.mean(entropy)) if entropy else 0.0,
    }


def spectrum_row(
    domain: str,
    seq: np.ndarray,
    n: int,
    phase: float,
    v_value: float,
    central_fraction: float,
    trial: int | None = None,
) -> dict[str, Any]:
    centered = seq - float(np.mean(seq))
    levels, vectors = np.linalg.eigh(hamiltonian(v_value * centered))
    metrics = localization_metrics(vectors, central_fraction)
    row: dict[str, Any] = {
        "domain": domain,
        "N": n,
        "phase": phase,
        "V": v_value,
        "ones": int(np.sum(seq)),
        "spacing_r": spacing_r(levels, central_fraction),
        **metrics,
    }
    if trial is not None:
        row["trial"] = trial
    return row


def finite(values: list[float | None]) -> np.ndarray:
    return np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(rows)}
    for key in ["spacing_r", "mean_ipr", "median_ipr", "participation_entropy"]:
        arr = finite([row.get(key) for row in rows])
        if len(arr) == 0:
            out[key] = {"count": 0}
        else:
            out[key] = {
                "count": int(len(arr)),
                "median": float(np.median(arr)),
                "mean": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
            }
    return out


def median_metric(summary: dict[str, Any], domain: str, v_key: str, metric: str) -> float | None:
    value = summary.get(v_key, {}).get(domain, {}).get(metric, {})
    if not isinstance(value, dict):
        return None
    median = value.get("median")
    return float(median) if median is not None else None


def between(value: float, left: float, right: float) -> bool:
    return min(left, right) <= value <= max(left, right)


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    v_values = np.arange(args.v_min, args.v_max + args.v_step / 2, args.v_step)
    domains = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }

    rows: list[dict[str, Any]] = []
    for n in ns:
        for phase in phases:
            phi_seq = sturmian_sequence(1 / PHI, n, phase)
            ones = int(np.sum(phi_seq))
            for v_value in v_values:
                for domain, theta in domains.items():
                    seq = sturmian_sequence(theta, n, phase)
                    rows.append(spectrum_row(domain, seq, n, phase, float(v_value), args.central_fraction))

                periodic = periodic_sequence(n)
                rows.append(spectrum_row("periodic_ab", periodic, n, phase, float(v_value), args.central_fraction))

                for trial in range(args.random_trials):
                    seq = np.array([1.0] * ones + [0.0] * (n - ones), dtype=float)
                    rng.shuffle(seq)
                    rows.append(
                        spectrum_row(
                            "balanced_random_phi_density",
                            seq,
                            n,
                            phase,
                            float(v_value),
                            args.central_fraction,
                            trial=trial,
                        )
                    )

    summary_by_v: dict[str, dict[str, Any]] = {}
    for v_value in v_values:
        v_key = f"V={v_value:.6f}"
        summary_by_v[v_key] = {}
        for domain in sorted({row["domain"] for row in rows}):
            subset = [row for row in rows if row["domain"] == domain and abs(row["V"] - v_value) < 1e-12]
            summary_by_v[v_key][domain] = aggregate(subset)

    classification: dict[str, Any] = {"joint_boundary_v": [], "by_v": {}}
    for v_value in v_values:
        v_key = f"V={v_value:.6f}"
        needed = {
            "phi_r": median_metric(summary_by_v, "phi", v_key, "spacing_r"),
            "periodic_r": median_metric(summary_by_v, "periodic_ab", v_key, "spacing_r"),
            "random_r": median_metric(summary_by_v, "balanced_random_phi_density", v_key, "spacing_r"),
            "phi_ipr": median_metric(summary_by_v, "phi", v_key, "mean_ipr"),
            "periodic_ipr": median_metric(summary_by_v, "periodic_ab", v_key, "mean_ipr"),
            "random_ipr": median_metric(summary_by_v, "balanced_random_phi_density", v_key, "mean_ipr"),
            "phi_entropy": median_metric(summary_by_v, "phi", v_key, "participation_entropy"),
            "periodic_entropy": median_metric(summary_by_v, "periodic_ab", v_key, "participation_entropy"),
            "random_entropy": median_metric(summary_by_v, "balanced_random_phi_density", v_key, "participation_entropy"),
        }
        complete = all(value is not None for value in needed.values())
        r_between = bool(complete and between(needed["phi_r"], needed["periodic_r"], needed["random_r"]))
        ipr_between = bool(complete and between(needed["phi_ipr"], needed["periodic_ipr"], needed["random_ipr"]))
        entropy_between = bool(complete and between(needed["phi_entropy"], needed["periodic_entropy"], needed["random_entropy"]))
        separated_random = bool(
            complete
            and abs(needed["phi_r"] - needed["random_r"]) >= args.min_r_delta
            and abs(needed["phi_ipr"] - needed["random_ipr"]) >= args.min_ipr_delta
        )
        joint = bool(r_between and ipr_between and separated_random)
        classification["by_v"][v_key] = {
            **needed,
            "spacing_r_between": r_between,
            "mean_ipr_between": ipr_between,
            "participation_entropy_between": entropy_between,
            "separated_from_random": separated_random,
            "joint_boundary": joint,
        }
        if joint:
            classification["joint_boundary_v"].append(float(v_value))

    return {
        "experiment": "aubry_boundary_phase_transport_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "v_min": args.v_min,
            "v_max": args.v_max,
            "v_step": args.v_step,
            "central_fraction": args.central_fraction,
            "random_trials": args.random_trials,
            "seed": args.seed,
            "min_r_delta": args.min_r_delta,
            "min_ipr_delta": args.min_ipr_delta,
        },
        "observable_contract": {
            "claim": "phi is a physical boundary state between periodic order and balanced random disorder only if spectral spacing and localization agree",
            "observable": "spacing_r plus mean_ipr / participation_entropy on tight-binding spectra",
            "operator": "binary quasiperiodic tight-binding Hamiltonian with phase row denominator",
            "denominator": "N x phase x V x generator rows with balanced random controls",
            "non_possible": "single-observable boundary, phase-aggregated critical value, or phi outside the periodic-random interval",
        },
        "classification": classification,
        "summary_by_v": summary_by_v,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="89,144,233")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=2.5)
    parser.add_argument("--v-step", type=float, default=0.25)
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--random-trials", type=int, default=6)
    parser.add_argument("--seed", type=int, default=202605151745)
    parser.add_argument("--min-r-delta", type=float, default=0.025)
    parser.add_argument("--min-ipr-delta", type=float, default=0.0025)
    parser.add_argument("--out", default="tools/data/aubry_boundary_phase_transport_gate_20260515_1745.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        "classification": output["classification"],
        "out": str(out),
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
