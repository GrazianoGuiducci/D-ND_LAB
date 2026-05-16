#!/usr/bin/env python3
"""
Aubry-Andre cosine counter-gate for the BOUNDARY return.

This is the regression check opened by the binary Aubry/Fibonacci gate: remove
the binary Sturmian grammar and ask whether phi remains a privileged boundary
inside the canonical cosine potential. The null is explicit: all irrational
frequencies behave as the same Aubry-Andre class unless phi separates jointly
in spectral spacing and localization.
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


def localization_metrics(vectors: np.ndarray, central_fraction: float) -> dict[str, float]:
    n = vectors.shape[0]
    subset = vectors[:, central_slice(n, central_fraction)]
    probs = np.square(np.abs(subset))
    ipr = np.sum(probs * probs, axis=0)
    entropy_values = []
    for col in range(probs.shape[1]):
        p = probs[:, col]
        p = p[p > 1e-15]
        entropy_values.append(float(-np.sum(p * np.log(p)) / np.log(n)))
    return {
        "mean_ipr": float(np.mean(ipr)),
        "median_ipr": float(np.median(ipr)),
        "participation_entropy": float(np.mean(entropy_values)) if entropy_values else 0.0,
    }


def cosine_potential(beta: float, n: int, phase: float) -> np.ndarray:
    idx = np.arange(n, dtype=float)
    vals = np.cos(2 * np.pi * (beta * idx + phase))
    return vals - float(np.mean(vals))


def periodic_potential(n: int, phase: float) -> np.ndarray:
    idx = np.arange(n, dtype=float)
    vals = np.cos(np.pi * idx + 2 * np.pi * phase)
    return vals - float(np.mean(vals))


def random_potential(rng: np.random.Generator, n: int) -> np.ndarray:
    vals = rng.uniform(-1.0, 1.0, n)
    return vals - float(np.mean(vals))


def spectrum_row(
    domain: str,
    diagonal: np.ndarray,
    n: int,
    phase: float,
    v_value: float,
    central_fraction: float,
    trial: int | None = None,
) -> dict[str, Any]:
    levels, vectors = np.linalg.eigh(hamiltonian(v_value * diagonal))
    row: dict[str, Any] = {
        "domain": domain,
        "N": n,
        "phase": phase,
        "V": v_value,
        "spacing_r": spacing_r(levels, central_fraction),
        **localization_metrics(vectors, central_fraction),
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
    irrational_domains = {
        "phi_cosine": 1 / PHI,
        "silver_cosine": 1 / SILVER,
        "bronze_cosine": 1 / BRONZE,
    }

    rows: list[dict[str, Any]] = []
    for n in ns:
        for phase in phases:
            for v_value in v_values:
                for domain, beta in irrational_domains.items():
                    rows.append(
                        spectrum_row(
                            domain,
                            cosine_potential(beta, n, phase),
                            n,
                            phase,
                            float(v_value),
                            args.central_fraction,
                        )
                    )
                rows.append(
                    spectrum_row(
                        "periodic_cosine",
                        periodic_potential(n, phase),
                        n,
                        phase,
                        float(v_value),
                        args.central_fraction,
                    )
                )
                for trial in range(args.random_trials):
                    rows.append(
                        spectrum_row(
                            "random_onsite",
                            random_potential(rng, n),
                            n,
                            phase,
                            float(v_value),
                            args.central_fraction,
                            trial=trial,
                        )
                    )

    domains = sorted({row["domain"] for row in rows})
    summary_by_v: dict[str, dict[str, Any]] = {}
    for v_value in v_values:
        v_key = f"V={v_value:.6f}"
        summary_by_v[v_key] = {}
        for domain in domains:
            subset = [row for row in rows if row["domain"] == domain and abs(row["V"] - v_value) < 1e-12]
            summary_by_v[v_key][domain] = aggregate(subset)

    classification: dict[str, Any] = {"phi_joint_boundary_v": [], "phi_distinct_v": [], "by_v": {}}
    for v_value in v_values:
        v_key = f"V={v_value:.6f}"
        needed = {
            "phi_r": median_metric(summary_by_v, "phi_cosine", v_key, "spacing_r"),
            "periodic_r": median_metric(summary_by_v, "periodic_cosine", v_key, "spacing_r"),
            "random_r": median_metric(summary_by_v, "random_onsite", v_key, "spacing_r"),
            "phi_ipr": median_metric(summary_by_v, "phi_cosine", v_key, "mean_ipr"),
            "periodic_ipr": median_metric(summary_by_v, "periodic_cosine", v_key, "mean_ipr"),
            "random_ipr": median_metric(summary_by_v, "random_onsite", v_key, "mean_ipr"),
            "silver_r": median_metric(summary_by_v, "silver_cosine", v_key, "spacing_r"),
            "bronze_r": median_metric(summary_by_v, "bronze_cosine", v_key, "spacing_r"),
            "silver_ipr": median_metric(summary_by_v, "silver_cosine", v_key, "mean_ipr"),
            "bronze_ipr": median_metric(summary_by_v, "bronze_cosine", v_key, "mean_ipr"),
        }
        complete = all(value is not None for value in needed.values())
        r_between = bool(complete and between(needed["phi_r"], needed["periodic_r"], needed["random_r"]))
        ipr_between = bool(complete and between(needed["phi_ipr"], needed["periodic_ipr"], needed["random_ipr"]))
        separated_random = bool(
            complete
            and abs(needed["phi_r"] - needed["random_r"]) >= args.min_r_delta
            and abs(needed["phi_ipr"] - needed["random_ipr"]) >= args.min_ipr_delta
        )
        nearest_control_r = min(abs(needed["phi_r"] - needed["silver_r"]), abs(needed["phi_r"] - needed["bronze_r"])) if complete else None
        nearest_control_ipr = (
            min(abs(needed["phi_ipr"] - needed["silver_ipr"]), abs(needed["phi_ipr"] - needed["bronze_ipr"]))
            if complete
            else None
        )
        phi_distinct = bool(
            complete
            and nearest_control_r is not None
            and nearest_control_ipr is not None
            and nearest_control_r >= args.min_control_r_delta
            and nearest_control_ipr >= args.min_control_ipr_delta
        )
        joint = bool(r_between and ipr_between and separated_random and phi_distinct)
        classification["by_v"][v_key] = {
            **needed,
            "spacing_r_between": r_between,
            "mean_ipr_between": ipr_between,
            "separated_from_random": separated_random,
            "nearest_control_r_delta": nearest_control_r,
            "nearest_control_ipr_delta": nearest_control_ipr,
            "phi_distinct_from_irrational_controls": phi_distinct,
            "phi_joint_boundary": joint,
        }
        if joint:
            classification["phi_joint_boundary_v"].append(float(v_value))
        if phi_distinct:
            classification["phi_distinct_v"].append(float(v_value))

    return {
        "experiment": "aubry_cosine_boundary_counter_gate",
        "parameters": vars(args),
        "rows_count": len(rows),
        "summary_by_v": summary_by_v,
        "classification": classification,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/aubry_cosine_boundary_counter_gate.json")
    parser.add_argument("--seed", type=int, default=202605151758)
    parser.add_argument("--ns", default="89,144,233")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=3.0)
    parser.add_argument("--v-step", type=float, default=0.25)
    parser.add_argument("--random-trials", type=int, default=6)
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--min-r-delta", type=float, default=0.03)
    parser.add_argument("--min-ipr-delta", type=float, default=0.01)
    parser.add_argument("--min-control-r-delta", type=float, default=0.03)
    parser.add_argument("--min-control-ipr-delta", type=float, default=0.005)
    args = parser.parse_args()

    result = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["classification"], indent=2))


if __name__ == "__main__":
    main()
