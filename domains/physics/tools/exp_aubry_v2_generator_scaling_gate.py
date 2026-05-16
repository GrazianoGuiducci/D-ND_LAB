#!/usr/bin/env python3
"""
V=2 generator scaling gate for the Aubry/Sturmian boundary.

The known Aubry-Andre self-dual point is V=2 for the continuous cosine
potential. This tool keeps V fixed there and asks whether binary Sturmian
generators, cosine generators, and null controls share the same finite-size
participation scaling.
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


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def sturmian_sequence(alpha: float, n: int, phase: float) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * alpha + phase)
    return np.diff(vals).astype(float)


def cosine_potential(alpha: float, n: int, phase: float) -> np.ndarray:
    idx = np.arange(n, dtype=float)
    return np.cos(2 * np.pi * (alpha * idx + phase))


def periodic_ab(n: int) -> np.ndarray:
    return (np.arange(n) % 2).astype(float)


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
    domain: str,
    diagonal: np.ndarray,
    n: int,
    phase: float | None,
    v_value: float,
    central_fraction: float,
    trial: int | None = None,
) -> dict[str, Any]:
    levels, vectors = np.linalg.eigh(hamiltonian(v_value * centered(diagonal)))
    row: dict[str, Any] = {
        "domain": domain,
        "N": n,
        "phase": phase,
        "V": v_value,
        "spacing_r": spacing_r(levels, central_fraction),
        **state_metrics(vectors, central_fraction),
    }
    if trial is not None:
        row["trial"] = trial
    return row


def finite(values: list[float | None]) -> np.ndarray:
    return np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(rows)}
    for key in ["spacing_r", "mean_ipr", "median_ipr", "mean_pr", "median_pr", "participation_entropy"]:
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


def median_by_n(rows: list[dict[str, Any]], domain: str, metric: str) -> dict[int, float]:
    out: dict[int, float] = {}
    ns = sorted({int(row["N"]) for row in rows if row["domain"] == domain})
    for n in ns:
        arr = finite([row.get(metric) for row in rows if row["domain"] == domain and int(row["N"]) == n])
        if len(arr):
            out[n] = float(np.median(arr))
    return out


def log_slope(values_by_n: dict[int, float]) -> dict[str, Any]:
    items = [(n, value) for n, value in sorted(values_by_n.items()) if value > 0]
    if len(items) < 2:
        return {"count": len(items), "slope": None, "intercept": None}
    x = np.log(np.array([n for n, _ in items], dtype=float))
    y = np.log(np.array([value for _, value in items], dtype=float))
    slope, intercept = np.polyfit(x, y, 1)
    return {
        "count": len(items),
        "slope": float(slope),
        "intercept": float(intercept),
        "values_by_n": {str(n): float(value) for n, value in items},
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    alphas = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }
    rows: list[dict[str, Any]] = []

    for n in ns:
        for phase in phases:
            for name, alpha in alphas.items():
                rows.append(
                    spectrum_row(
                        f"{name}_sturmian_binary",
                        sturmian_sequence(alpha, n, phase),
                        n,
                        phase,
                        args.v,
                        args.central_fraction,
                    )
                )
                rows.append(
                    spectrum_row(
                        f"{name}_cosine",
                        cosine_potential(alpha, n, phase),
                        n,
                        phase,
                        args.v,
                        args.central_fraction,
                    )
                )
            rows.append(spectrum_row("periodic_ab", periodic_ab(n), n, phase, args.v, args.central_fraction))
            phi_word = sturmian_sequence(1 / PHI, n, phase)
            for trial in range(args.random_trials):
                shuffled = np.array(phi_word, dtype=float)
                rng.shuffle(shuffled)
                rows.append(
                    spectrum_row(
                        "phi_binary_density_shuffle",
                        shuffled,
                        n,
                        phase,
                        args.v,
                        args.central_fraction,
                        trial,
                    )
                )
                rows.append(
                    spectrum_row(
                        "random_uniform",
                        rng.uniform(-1.0, 1.0, n),
                        n,
                        phase,
                        args.v,
                        args.central_fraction,
                        trial,
                    )
                )

    domains = sorted({row["domain"] for row in rows})
    summary_by_domain = {domain: aggregate([row for row in rows if row["domain"] == domain]) for domain in domains}
    scaling: dict[str, Any] = {}
    for domain in domains:
        scaling[domain] = {
            "mean_pr_tau": log_slope(median_by_n(rows, domain, "mean_pr")),
            "mean_ipr_tau": log_slope(median_by_n(rows, domain, "mean_ipr")),
            "spacing_r_by_n": median_by_n(rows, domain, "spacing_r"),
        }

    phi_tau = scaling["phi_sturmian_binary"]["mean_pr_tau"]["slope"]
    shuffle_tau = scaling["phi_binary_density_shuffle"]["mean_pr_tau"]["slope"]
    phi_cos_tau = scaling["phi_cosine"]["mean_pr_tau"]["slope"]
    silver_bin_tau = scaling["silver_sturmian_binary"]["mean_pr_tau"]["slope"]
    bronze_bin_tau = scaling["bronze_sturmian_binary"]["mean_pr_tau"]["slope"]
    classification = {
        "v2_baseline": args.v,
        "phi_binary_tau": phi_tau,
        "phi_cosine_tau": phi_cos_tau,
        "density_shuffle_tau": shuffle_tau,
        "silver_binary_tau": silver_bin_tau,
        "bronze_binary_tau": bronze_bin_tau,
        "phi_binary_separates_from_shuffle": (
            None
            if phi_tau is None or shuffle_tau is None
            else abs(float(phi_tau) - float(shuffle_tau)) >= args.min_tau_delta
        ),
        "phi_binary_separates_from_nonphi_binary": (
            None
            if phi_tau is None or silver_bin_tau is None or bronze_bin_tau is None
            else min(abs(float(phi_tau) - float(silver_bin_tau)), abs(float(phi_tau) - float(bronze_bin_tau)))
            >= args.min_tau_delta
        ),
        "cosine_class_tau_span": (
            max(scaling[f"{name}_cosine"]["mean_pr_tau"]["slope"] for name in alphas)
            - min(scaling[f"{name}_cosine"]["mean_pr_tau"]["slope"] for name in alphas)
        ),
    }

    return {
        "experiment": "aubry_v2_generator_scaling_gate",
        "parameters": vars(args),
        "observable_contract": {
            "claim": "at V=2 the boundary is a generator property only if binary Sturmian, cosine, and null controls carry different participation scaling",
            "observable": "finite-size log slope tau of mean participation ratio, plus spacing_r and IPR anchors",
            "operator": "tight-binding Hamiltonian with fixed V=2 onsite generators",
            "denominator": "N x phase x generator rows with density shuffle and random anchors",
            "non_possible": "claiming phi-specific boundary if the V=2 tau is shared by density shuffle or by non-phi Sturmian controls",
        },
        "rows_count": len(rows),
        "summary_by_domain": summary_by_domain,
        "scaling": scaling,
        "classification": classification,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/aubry_v2_generator_scaling_gate_20260515_1816.json")
    parser.add_argument("--seed", type=int, default=202605151816)
    parser.add_argument("--ns", default="89,144,233,377")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--v", type=float, default=2.0)
    parser.add_argument("--random-trials", type=int, default=4)
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--min-tau-delta", type=float, default=0.08)
    args = parser.parse_args()

    result = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["classification"], indent=2, sort_keys=True))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
