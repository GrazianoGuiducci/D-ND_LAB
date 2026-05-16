#!/usr/bin/env python3
"""
Binary grammar surrogate gate for the Aubry/Fibonacci boundary return.

This isolates the residue left by the cosine counter-gate: keep the same
tight-binding denominator as the binary Sturmian test, then replace the phi
word with surrogates that preserve density, short memory, or Fourier amplitude.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


PHI = (1 + np.sqrt(5)) / 2


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
    row: dict[str, Any] = {
        "domain": domain,
        "N": n,
        "phase": phase,
        "V": v_value,
        "ones": int(np.sum(seq)),
        "spacing_r": spacing_r(levels, central_fraction),
        **localization_metrics(vectors, central_fraction),
    }
    if trial is not None:
        row["trial"] = trial
    return row


def balanced_shuffle(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.array(seq, dtype=float)
    rng.shuffle(out)
    return out


def block_shuffle(seq: np.ndarray, rng: np.random.Generator, block_size: int) -> np.ndarray:
    blocks = [np.array(seq[i : i + block_size], dtype=float) for i in range(0, len(seq), block_size)]
    order = np.arange(len(blocks))
    rng.shuffle(order)
    return np.concatenate([blocks[i] for i in order])[: len(seq)]


def markov_surrogate(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    seq_int = np.asarray(seq, dtype=int)
    counts = np.ones((2, 2), dtype=float)
    for a, b in zip(seq_int[:-1], seq_int[1:]):
        counts[a, b] += 1.0
    probs = counts / counts.sum(axis=1, keepdims=True)
    out = np.empty(len(seq_int), dtype=float)
    out[0] = seq_int[0]
    for i in range(1, len(seq_int)):
        prev = int(out[i - 1])
        out[i] = 1.0 if rng.random() < probs[prev, 1] else 0.0
    target_ones = int(np.sum(seq_int))
    current_ones = int(np.sum(out))
    if current_ones != target_ones:
        want = 1.0 if current_ones < target_ones else 0.0
        have = 1.0 - want
        idx = np.where(out == have)[0]
        rng.shuffle(idx)
        out[idx[: abs(target_ones - current_ones)]] = want
    return out


def iaaft_binary_surrogate(seq: np.ndarray, rng: np.random.Generator, iterations: int) -> np.ndarray:
    reference = np.asarray(seq, dtype=float)
    target_amp = np.abs(np.fft.rfft(reference - np.mean(reference)))
    sorted_values = np.sort(reference)
    current = balanced_shuffle(reference, rng)
    for _ in range(iterations):
        spectrum = np.fft.rfft(current - np.mean(current))
        phases = np.exp(1j * np.angle(spectrum))
        adjusted = np.fft.irfft(target_amp * phases, n=len(reference))
        ranks = np.argsort(np.argsort(adjusted))
        current = sorted_values[ranks]
    return current.astype(float)


def autocorr(seq: np.ndarray, max_lag: int) -> np.ndarray:
    x = np.asarray(seq, dtype=float) - float(np.mean(seq))
    denom = float(np.dot(x, x))
    if denom <= 1e-15:
        return np.zeros(max_lag, dtype=float)
    return np.array([float(np.dot(x[:-lag], x[lag:]) / denom) for lag in range(1, max_lag + 1)])


def psd_profile(seq: np.ndarray) -> np.ndarray:
    x = np.asarray(seq, dtype=float) - float(np.mean(seq))
    psd = np.abs(np.fft.rfft(x)) ** 2
    total = float(np.sum(psd))
    return psd / total if total > 1e-15 else psd


def profile_metrics(reference: np.ndarray, candidate: np.ndarray, max_lag: int) -> dict[str, float]:
    return {
        "hamming_ratio": float(np.mean(reference != candidate)),
        "acf_l1": float(np.mean(np.abs(autocorr(reference, max_lag) - autocorr(candidate, max_lag)))),
        "psd_l1": float(np.mean(np.abs(psd_profile(reference) - psd_profile(candidate)))),
    }


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


def make_surrogates(
    seq: np.ndarray,
    rng: np.random.Generator,
    random_trials: int,
    block_size: int,
    iaaft_iterations: int,
) -> list[tuple[str, np.ndarray, int]]:
    out: list[tuple[str, np.ndarray, int]] = []
    for trial in range(random_trials):
        out.append(("density_shuffle", balanced_shuffle(seq, rng), trial))
        out.append(("markov_short_memory", markov_surrogate(seq, rng), trial))
        out.append((f"block_shuffle_{block_size}", block_shuffle(seq, rng, block_size), trial))
        out.append(("iaaft_binary_psd", iaaft_binary_surrogate(seq, rng, iaaft_iterations), trial))
    return out


def classify_domain(
    summary_by_v: dict[str, Any],
    domain: str,
    v_key: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    needed = {
        "domain_r": median_metric(summary_by_v, domain, v_key, "spacing_r"),
        "periodic_r": median_metric(summary_by_v, "periodic_ab", v_key, "spacing_r"),
        "random_r": median_metric(summary_by_v, "balanced_random_phi_density", v_key, "spacing_r"),
        "domain_ipr": median_metric(summary_by_v, domain, v_key, "mean_ipr"),
        "periodic_ipr": median_metric(summary_by_v, "periodic_ab", v_key, "mean_ipr"),
        "random_ipr": median_metric(summary_by_v, "balanced_random_phi_density", v_key, "mean_ipr"),
    }
    complete = all(value is not None for value in needed.values())
    r_between = bool(complete and between(needed["domain_r"], needed["periodic_r"], needed["random_r"]))
    ipr_between = bool(complete and between(needed["domain_ipr"], needed["periodic_ipr"], needed["random_ipr"]))
    separated_random = bool(
        complete
        and abs(needed["domain_r"] - needed["random_r"]) >= args.min_r_delta
        and abs(needed["domain_ipr"] - needed["random_ipr"]) >= args.min_ipr_delta
    )
    return {
        **needed,
        "spacing_r_between": r_between,
        "mean_ipr_between": ipr_between,
        "separated_from_random": separated_random,
        "joint_boundary": bool(r_between and ipr_between and separated_random),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    v_values = np.arange(args.v_min, args.v_max + args.v_step / 2, args.v_step)
    rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []

    for n in ns:
        for phase in phases:
            phi_seq = sturmian_sequence(1 / PHI, n, phase)
            periodic = periodic_sequence(n)
            for v_value in v_values:
                rows.append(spectrum_row("phi_sturmian", phi_seq, n, phase, float(v_value), args.central_fraction))
                rows.append(spectrum_row("periodic_ab", periodic, n, phase, float(v_value), args.central_fraction))
                for trial, (_, surrogate, _) in enumerate(
                    [("density_shuffle", balanced_shuffle(phi_seq, rng), 0) for _ in range(args.random_trials)]
                ):
                    rows.append(
                        spectrum_row(
                            "balanced_random_phi_density",
                            surrogate,
                            n,
                            phase,
                            float(v_value),
                            args.central_fraction,
                            trial=trial,
                        )
                    )
                for domain, surrogate, trial in make_surrogates(
                    phi_seq,
                    rng,
                    args.surrogate_trials,
                    args.block_size,
                    args.iaaft_iterations,
                ):
                    rows.append(spectrum_row(domain, surrogate, n, phase, float(v_value), args.central_fraction, trial=trial))
                    if abs(v_value - args.v_min) < 1e-12:
                        profiles.append(
                            {
                                "domain": domain,
                                "N": n,
                                "phase": phase,
                                "trial": trial,
                                **profile_metrics(phi_seq, surrogate, args.max_lag),
                            }
                        )

    domains = sorted({row["domain"] for row in rows})
    summary_by_v: dict[str, dict[str, Any]] = {}
    for v_value in v_values:
        v_key = f"V={v_value:.6f}"
        summary_by_v[v_key] = {}
        for domain in domains:
            subset = [row for row in rows if row["domain"] == domain and abs(row["V"] - v_value) < 1e-12]
            summary_by_v[v_key][domain] = aggregate(subset)

    domain_classes = [d for d in domains if d not in {"periodic_ab", "balanced_random_phi_density"}]
    classification: dict[str, Any] = {"joint_boundary_v_by_domain": {}, "by_v": {}}
    for domain in domain_classes:
        classification["joint_boundary_v_by_domain"][domain] = []

    for v_value in v_values:
        v_key = f"V={v_value:.6f}"
        classification["by_v"][v_key] = {}
        for domain in domain_classes:
            row = classify_domain(summary_by_v, domain, v_key, args)
            classification["by_v"][v_key][domain] = row
            if row["joint_boundary"]:
                classification["joint_boundary_v_by_domain"][domain].append(float(v_value))

    profile_summary: dict[str, Any] = {}
    for domain in sorted({row["domain"] for row in profiles}):
        subset = [row for row in profiles if row["domain"] == domain]
        profile_summary[domain] = {}
        for key in ["hamming_ratio", "acf_l1", "psd_l1"]:
            values = np.array([row[key] for row in subset], dtype=float)
            profile_summary[domain][key] = {
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
            }

    return {
        "experiment": "aubry_binary_grammar_surrogate_gate",
        "parameters": vars(args),
        "observable_contract": {
            "claim": "the binary phi boundary is grammar-complete only if it fails under density, short-memory, and PSD-preserving surrogates",
            "observable": "joint spacing_r and mean_ipr boundary window plus surrogate profile distances",
            "operator": "binary tight-binding Hamiltonian with phi word ablations",
            "denominator": "N x phase x V x surrogate class rows, with periodic and balanced random anchors",
            "non_possible": "calling the 17:45 window phi-specific if a weaker surrogate retains the same joint window",
        },
        "rows_count": len(rows),
        "summary_by_v": summary_by_v,
        "classification": classification,
        "profile_summary": profile_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/aubry_binary_grammar_surrogate_gate.json")
    parser.add_argument("--seed", type=int, default=202605151807)
    parser.add_argument("--ns", default="89,144,233")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=1.5)
    parser.add_argument("--v-step", type=float, default=0.25)
    parser.add_argument("--random-trials", type=int, default=6)
    parser.add_argument("--surrogate-trials", type=int, default=4)
    parser.add_argument("--block-size", type=int, default=8)
    parser.add_argument("--iaaft-iterations", type=int, default=80)
    parser.add_argument("--max-lag", type=int, default=8)
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--min-r-delta", type=float, default=0.025)
    parser.add_argument("--min-ipr-delta", type=float, default=0.0025)
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "classification": output["classification"]["joint_boundary_v_by_domain"],
                "profile_summary": output["profile_summary"],
                "rows_count": output["rows_count"],
                "out": str(out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
