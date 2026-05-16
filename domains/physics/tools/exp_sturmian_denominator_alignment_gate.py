#!/usr/bin/env python3
"""
Denominator-aligned Sturmian gate for the Aubry/Sturmian boundary.

The previous V=2 gate showed that phi, silver and bronze binary Sturmian
generators stay in the same finite-size corridor. This tool asks whether that
corridor survives when each irrational is measured on its own convergent
denominators, instead of on shared Fibonacci-sized boxes.
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


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def continued_fraction_denominators(alpha: float, max_n: int) -> list[int]:
    x = float(alpha)
    p_prev, p = 0, 1
    q_prev, q = 1, 0
    denominators: list[int] = []
    for _ in range(64):
        a = int(np.floor(x))
        p_prev, p = p, a * p + p_prev
        q_prev, q = q, a * q + q_prev
        if q > 1:
            denominators.append(q)
        if q > max_n:
            break
        frac = x - a
        if abs(frac) < 1e-14:
            break
        x = 1.0 / frac
    return denominators


def sturmian_sequence(alpha: float, n: int, phase: float) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * alpha + phase)
    return np.diff(vals).astype(float)


def centered(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return values - float(np.mean(values))


def hamiltonian(diagonal: np.ndarray) -> np.ndarray:
    n = len(diagonal)
    matrix = np.diag(diagonal.astype(float))
    off = np.ones(n - 1, dtype=float)
    matrix += np.diag(off, 1) + np.diag(off, -1)
    return matrix


def central_slice(n: int, central_fraction: float) -> slice:
    keep = max(8, min(n, int(round(n * central_fraction))))
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


def state_metrics(vectors: np.ndarray, central_fraction: float) -> dict[str, float]:
    n = vectors.shape[0]
    subset = vectors[:, central_slice(n, central_fraction)]
    probs = np.square(np.abs(subset))
    ipr = np.sum(probs * probs, axis=0)
    pr = 1.0 / ipr
    entropy_values = []
    for col in range(probs.shape[1]):
        p = probs[:, col]
        p = p[p > 1e-15]
        entropy_values.append(float(-np.sum(p * np.log(p)) / np.log(n)))
    return {
        "mean_ipr": float(np.mean(ipr)),
        "median_ipr": float(np.median(ipr)),
        "mean_pr": float(np.mean(pr)),
        "median_pr": float(np.median(pr)),
        "participation_entropy": float(np.mean(entropy_values)) if entropy_values else 0.0,
    }


def spectrum_row(
    family: str,
    alpha: float,
    n: int,
    denominator_rank: int,
    phase: float,
    v_value: float,
    central_fraction: float,
) -> dict[str, Any]:
    diagonal = sturmian_sequence(alpha, n, phase)
    levels, vectors = np.linalg.eigh(hamiltonian(v_value * centered(diagonal)))
    return {
        "family": family,
        "domain": f"{family}_sturmian_binary",
        "N": n,
        "denominator_rank": denominator_rank,
        "phase": phase,
        "V": v_value,
        "density": float(np.mean(diagonal)),
        "spacing_r": spacing_r(levels, central_fraction),
        **state_metrics(vectors, central_fraction),
    }


def finite(values: list[float | None]) -> np.ndarray:
    return np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)


def median_metric(rows: list[dict[str, Any]], family: str, n: int, metric: str) -> float | None:
    arr = finite([row.get(metric) for row in rows if row["family"] == family and int(row["N"]) == n])
    if len(arr) == 0:
        return None
    return float(np.median(arr))


def aggregate_family(rows: list[dict[str, Any]], family: str) -> dict[str, Any]:
    family_rows = [row for row in rows if row["family"] == family]
    out: dict[str, Any] = {"count": len(family_rows)}
    for key in ["spacing_r", "mean_ipr", "median_ipr", "mean_pr", "median_pr", "participation_entropy", "density"]:
        arr = finite([row.get(key) for row in family_rows])
        out[key] = {
            "count": int(len(arr)),
            "median": float(np.median(arr)) if len(arr) else None,
            "mean": float(np.mean(arr)) if len(arr) else None,
            "min": float(np.min(arr)) if len(arr) else None,
            "max": float(np.max(arr)) if len(arr) else None,
        }
    return out


def log_slope_by_family(rows: list[dict[str, Any]], family: str, metric: str) -> dict[str, Any]:
    ns = sorted({int(row["N"]) for row in rows if row["family"] == family})
    pairs = []
    for n in ns:
        value = median_metric(rows, family, n, metric)
        if value is not None and value > 0:
            pairs.append((n, value))
    if len(pairs) < 2:
        return {"count": len(pairs), "slope": None, "values_by_n": {str(n): v for n, v in pairs}}
    x = np.log(np.array([n for n, _ in pairs], dtype=float))
    y = np.log(np.array([value for _, value in pairs], dtype=float))
    slope, intercept = np.polyfit(x, y, 1)
    return {
        "count": len(pairs),
        "slope": float(slope),
        "intercept": float(intercept),
        "values_by_n": {str(n): float(value) for n, value in pairs},
    }


def phase_spread(rows: list[dict[str, Any]], family: str, metric: str) -> dict[str, float]:
    spreads: dict[str, float] = {}
    ns = sorted({int(row["N"]) for row in rows if row["family"] == family})
    for n in ns:
        arr = finite([row.get(metric) for row in rows if row["family"] == family and int(row["N"]) == n])
        if len(arr):
            spreads[str(n)] = float(np.max(arr) - np.min(arr))
    return spreads


def classify(summary: dict[str, Any], min_tau_delta: float, max_phase_spread: float) -> dict[str, Any]:
    phi_tau = summary["families"]["phi"]["mean_pr_tau"]["slope"]
    silver_tau = summary["families"]["silver"]["mean_pr_tau"]["slope"]
    bronze_tau = summary["families"]["bronze"]["mean_pr_tau"]["slope"]
    nonphi = [v for v in [silver_tau, bronze_tau] if v is not None]
    if phi_tau is None or len(nonphi) != 2:
        return {"verdict": "blank", "reason": "missing_tau"}
    nearest_delta = min(abs(phi_tau - value) for value in nonphi)
    mean_phase_spread = summary["families"]["phi"]["mean_pr_phase_spread_mean"]
    return {
        "verdict": "phi_specific" if nearest_delta >= min_tau_delta else "sturmian_corridor",
        "phi_tau": phi_tau,
        "silver_tau": silver_tau,
        "bronze_tau": bronze_tau,
        "nearest_nonphi_tau_delta": float(nearest_delta),
        "min_tau_delta": min_tau_delta,
        "phi_phase_stable": bool(mean_phase_spread <= max_phase_spread),
        "phi_mean_pr_phase_spread_mean": mean_phase_spread,
        "max_phase_spread": max_phase_spread,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    phases = parse_csv_floats(args.phases)
    alphas = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }
    denominators = {
        name: [q for q in continued_fraction_denominators(alpha, args.max_n) if args.min_n <= q <= args.max_n]
        for name, alpha in alphas.items()
    }
    min_count = min(len(values) for values in denominators.values())
    selected = {name: values[:min_count] for name, values in denominators.items()}

    rows: list[dict[str, Any]] = []
    for family, alpha in alphas.items():
        for rank, n in enumerate(selected[family]):
            for phase in phases:
                rows.append(spectrum_row(family, alpha, n, rank, phase, args.v, args.central_fraction))

    families: dict[str, Any] = {}
    for family in alphas:
        aggregate = aggregate_family(rows, family)
        mean_pr_tau = log_slope_by_family(rows, family, "mean_pr")
        entropy_tau = log_slope_by_family(rows, family, "participation_entropy")
        spreads = phase_spread(rows, family, "mean_pr")
        aggregate["mean_pr_tau"] = mean_pr_tau
        aggregate["participation_entropy_tau"] = entropy_tau
        aggregate["mean_pr_phase_spread_by_n"] = spreads
        aggregate["mean_pr_phase_spread_mean"] = float(np.mean(list(spreads.values()))) if spreads else None
        families[family] = aggregate

    summary = {
        "families": families,
        "classification": {},
        "denominators": {name: [int(v) for v in values] for name, values in selected.items()},
    }
    summary["classification"] = classify(summary, args.min_tau_delta, args.max_phase_spread)

    return {
        "metadata": {
            "experiment": "sturmian_denominator_alignment_gate",
            "V": args.v,
            "min_n": args.min_n,
            "max_n": args.max_n,
            "phases": phases,
            "central_fraction": args.central_fraction,
            "min_tau_delta": args.min_tau_delta,
            "max_phase_spread": args.max_phase_spread,
        },
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("tools/data/sturmian_denominator_alignment_gate.json"))
    parser.add_argument("--min-n", type=int, default=50)
    parser.add_argument("--max-n", type=int, default=500)
    parser.add_argument("--v", type=float, default=2.0)
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--central-fraction", type=float, default=0.5)
    parser.add_argument("--min-tau-delta", type=float, default=0.08)
    parser.add_argument("--max-phase-spread", type=float, default=12.0)
    args = parser.parse_args()

    result = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    classification = result["summary"]["classification"]
    print(json.dumps(classification, indent=2, sort_keys=True))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
