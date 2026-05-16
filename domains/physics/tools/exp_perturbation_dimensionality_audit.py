#!/usr/bin/env python3
"""
exp_perturbation_dimensionality_audit.py

Robustness audit for the scale-selective perturbation result.

The 2026-05-06 03:30 run found that GUE spacing sequences expose a second
perturbation axis under scale-selective probes, while prime gaps remain close
to one axis. That run used a short GUE sequence. This tool repeats the same
kind of measurement across independent replicates and explicit sample-size
controls.

It measures only observables and null baselines. The report owns the claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


OBS_NAMES = ["SR", "L1", "L2", "SR2", "triple_var"]
PERT_NAMES = ["adjacent_swap", "block_shuffle", "large_gap_only", "uniform"]
OBSERVABLE_SET = "rank_audit"


def prime_gaps(n_gaps: int) -> np.ndarray:
    limit = max(100, int(n_gaps * (np.log(n_gaps + 10) + np.log(np.log(n_gaps + 10)) + 5)))
    while True:
        sieve = np.ones(limit + 1, dtype=bool)
        sieve[:2] = False
        for p in range(2, int(limit**0.5) + 1):
            if sieve[p]:
                sieve[p * p : limit + 1 : p] = False
        primes = np.flatnonzero(sieve)
        if len(primes) >= n_gaps + 1:
            return np.diff(primes[: n_gaps + 1]).astype(float)
        limit *= 2


def gue_spacings(matrix_size: int, n_matrices: int, rng: np.random.Generator) -> np.ndarray:
    parts = []
    edge = max(2, matrix_size // 10)
    for _ in range(n_matrices):
        real = rng.standard_normal((matrix_size, matrix_size))
        imag = rng.standard_normal((matrix_size, matrix_size))
        h = real + 1j * imag
        h = (h + h.conj().T) / (2.0 * np.sqrt(matrix_size))
        eigs = np.sort(np.linalg.eigvalsh(h).real)
        bulk = eigs[edge:-edge]
        gaps = np.diff(bulk)
        mean = np.mean(gaps)
        if mean > 1e-15:
            parts.append(gaps / mean)
    return np.concatenate(parts).astype(float)


def spacing_ratio(gaps: np.ndarray, lag: int) -> float:
    a = gaps[:-lag]
    b = gaps[lag:]
    denom = np.maximum(a, b)
    valid = denom > 1e-15
    if not np.any(valid):
        return 0.0
    return float(np.mean(np.minimum(a[valid], b[valid]) / denom[valid]))


def lag_acf(gaps: np.ndarray, lag: int) -> float:
    g = gaps - np.mean(gaps)
    c0 = np.dot(g, g)
    if c0 <= 1e-15 or len(gaps) <= lag:
        return 0.0
    return float(np.dot(g[:-lag], g[lag:]) / c0)


def triple_var(gaps: np.ndarray) -> float:
    if len(gaps) < 3:
        return 0.0
    triples = gaps[:-2] + gaps[1:-1] + gaps[2:]
    v = np.var(gaps)
    if v <= 1e-15:
        return 0.0
    return float(np.var(triples) / v)


def spectral_rigidity(gaps: np.ndarray, L: int) -> float:
    cumulative = np.cumsum(gaps)
    if cumulative[-1] <= 1e-15:
        return 0.0
    cumulative = cumulative / cumulative[-1] * len(cumulative)
    n = np.arange(1, len(cumulative) + 1, dtype=float)
    window = int(min(L * len(gaps) / cumulative[-1], len(gaps) // 2))
    if window < 5:
        return 0.0
    step = max(1, window // 2)
    residuals = []
    for start in range(0, len(gaps) - window, step):
        seg_n = n[start : start + window]
        seg_c = cumulative[start : start + window]
        coeffs = np.polyfit(seg_n, seg_c, 1)
        fitted = np.polyval(coeffs, seg_n)
        residuals.append(np.mean((seg_c - fitted) ** 2))
    return float(np.mean(residuals)) if residuals else 0.0


def triple_product_var(gaps: np.ndarray) -> float:
    if len(gaps) < 3:
        return 0.0
    triples = gaps[:-2] * gaps[1:-1] * gaps[2:]
    return float(np.var(triples))


def measure(gaps: np.ndarray) -> dict[str, float]:
    if OBSERVABLE_SET == "scale_0330":
        return {
            "SR": spectral_rigidity(gaps, 10),
            "L1": lag_acf(gaps, 1),
            "L2": lag_acf(gaps, 2),
            "SR2": spectral_rigidity(gaps, 20),
            "triple_var": triple_product_var(gaps),
        }
    return {
        "SR": spacing_ratio(gaps, 1),
        "L1": lag_acf(gaps, 1),
        "L2": lag_acf(gaps, 2),
        "SR2": spacing_ratio(gaps, 2),
        "triple_var": triple_var(gaps),
    }


def perturb_adjacent_swap(gaps: np.ndarray, alpha: float, rng: np.random.Generator) -> np.ndarray:
    out = gaps.copy()
    idx = np.arange(0, len(out) - 1, 2)
    chosen = idx[rng.random(len(idx)) < alpha]
    tmp = out[chosen].copy()
    out[chosen] = out[chosen + 1]
    out[chosen + 1] = tmp
    return out


def perturb_block_shuffle(gaps: np.ndarray, alpha: float, rng: np.random.Generator, block_size: int = 64) -> np.ndarray:
    out = gaps.copy()
    n_blocks = len(out) // block_size
    if n_blocks <= 0:
        return rng.permutation(out) if alpha > 0 else out
    k = int(round(alpha * n_blocks))
    if k <= 0:
        return out
    for block in rng.choice(n_blocks, size=min(k, n_blocks), replace=False):
        start = block * block_size
        end = min(start + block_size, len(out))
        rng.shuffle(out[start:end])
    return out


def perturb_large_gap_only(gaps: np.ndarray, alpha: float, rng: np.random.Generator) -> np.ndarray:
    out = gaps.copy()
    idx = np.flatnonzero(out > np.median(out))
    k = int(round(alpha * len(idx)))
    if k < 2:
        return out
    chosen = rng.choice(idx, size=min(k, len(idx)), replace=False)
    vals = out[chosen].copy()
    rng.shuffle(vals)
    out[chosen] = vals
    return out


def perturb_uniform(gaps: np.ndarray, alpha: float, rng: np.random.Generator) -> np.ndarray:
    out = gaps.copy()
    k = int(round(alpha * len(out)))
    if k < 2:
        return out
    chosen = rng.choice(len(out), size=min(k, len(out)), replace=False)
    vals = out[chosen].copy()
    rng.shuffle(vals)
    out[chosen] = vals
    return out


PERTURB = {
    "adjacent_swap": perturb_adjacent_swap,
    "block_shuffle": perturb_block_shuffle,
    "large_gap_only": perturb_large_gap_only,
    "uniform": perturb_uniform,
}


def pca_summary(rows: list[dict]) -> dict:
    matrix = np.array([row["retention_vector"] for row in rows], dtype=float)
    matrix = matrix - np.mean(matrix, axis=0, keepdims=True)
    _, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    energy = singular * singular
    if np.sum(energy) <= 1e-15:
        explained = np.zeros_like(energy)
        eff_rank = 0.0
    else:
        explained = energy / np.sum(energy)
        pos = explained[explained > 1e-15]
        eff_rank = float(np.exp(-np.sum(pos * np.log(pos))))

    centroids = {}
    for name in PERT_NAMES:
        vals = np.array([row["retention_vector"] for row in rows if row["perturbation"] == name])
        centroids[name] = np.mean(vals, axis=0)

    cosine = {}
    for i, a_name in enumerate(PERT_NAMES):
        for b_name in PERT_NAMES[i + 1 :]:
            a = centroids[a_name]
            b = centroids[b_name]
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            cosine[f"{a_name}_vs_{b_name}"] = float(np.dot(a, b) / denom) if denom > 1e-15 else 0.0

    return {
        "explained_variance": [float(x) for x in explained],
        "effective_rank": eff_rank,
        "pc1_loadings": {name: float(vt[0, i]) for i, name in enumerate(OBS_NAMES)} if len(vt) else {},
        "pc2_loadings": {name: float(vt[1, i]) for i, name in enumerate(OBS_NAMES)} if len(vt) > 1 else {},
        "centroid_cosine": cosine,
    }


def analyze(name: str, gaps: np.ndarray, alphas: list[float], n_trials: int, n_baseline: int, rng: np.random.Generator) -> dict:
    original = measure(gaps)
    baseline_vals = {obs: [] for obs in OBS_NAMES}
    for _ in range(n_baseline):
        row = measure(rng.permutation(gaps))
        for obs in OBS_NAMES:
            baseline_vals[obs].append(row[obs])
    baseline = {
        obs: {
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
        }
        for obs, vals in baseline_vals.items()
    }

    rows = []
    for pert_name in PERT_NAMES:
        for alpha in alphas:
            vals = {obs: [] for obs in OBS_NAMES}
            for _ in range(n_trials):
                row = measure(PERTURB[pert_name](gaps, alpha, rng))
                for obs in OBS_NAMES:
                    vals[obs].append(row[obs])
            means = {obs: float(np.mean(vals[obs])) for obs in OBS_NAMES}
            retention = {}
            for obs in OBS_NAMES:
                denom = original[obs] - baseline[obs]["mean"]
                retention[obs] = float((means[obs] - baseline[obs]["mean"]) / denom) if abs(denom) > 1e-12 else 0.0
            rows.append(
                {
                    "perturbation": pert_name,
                    "alpha": float(alpha),
                    "mean": means,
                    "retention": retention,
                    "retention_vector": [retention[obs] for obs in OBS_NAMES],
                }
            )

    z = {}
    for obs in OBS_NAMES:
        std = baseline[obs]["std"]
        z[obs] = float((original[obs] - baseline[obs]["mean"]) / std) if std > 1e-12 else 0.0

    return {
        "name": name,
        "n_gaps": int(len(gaps)),
        "original": original,
        "full_shuffle_baseline": baseline,
        "original_vs_shuffle_z": z,
        "profiles": rows,
        "pca": pca_summary(rows),
    }


def replicate_summary(results: list[dict]) -> dict:
    ranks = np.array([r["pca"]["effective_rank"] for r in results], dtype=float)
    pc2 = np.array([r["pca"]["explained_variance"][1] if len(r["pca"]["explained_variance"]) > 1 else 0.0 for r in results])
    cos = np.array([
        r["pca"]["centroid_cosine"].get("adjacent_swap_vs_large_gap_only", 0.0)
        for r in results
    ])
    return {
        "n_replicates": len(results),
        "effective_rank_mean": float(np.mean(ranks)),
        "effective_rank_std": float(np.std(ranks, ddof=1)) if len(ranks) > 1 else 0.0,
        "effective_rank_min": float(np.min(ranks)),
        "effective_rank_max": float(np.max(ranks)),
        "pc2_mean": float(np.mean(pc2)),
        "pc2_std": float(np.std(pc2, ddof=1)) if len(pc2) > 1 else 0.0,
        "adjacent_vs_large_cosine_mean": float(np.mean(cos)),
        "adjacent_vs_large_cosine_std": float(np.std(cos, ddof=1)) if len(cos) > 1 else 0.0,
    }


def run(args: argparse.Namespace) -> dict:
    root_rng = np.random.default_rng(args.seed)
    alphas = [float(x) for x in np.linspace(args.alpha_min, args.alpha_max, args.n_alpha)]

    prime = prime_gaps(args.n_prime_gaps)
    fixed_domains = {
        "primes": prime,
        "prime_shuffle_control": root_rng.permutation(prime),
        "poisson": root_rng.exponential(1.0, size=args.n_prime_gaps),
    }

    output = {
        "experiment": "perturbation_dimensionality_audit",
        "question": "Is the GUE second perturbation axis stable across independent ensembles and sample-size controls?",
        "params": vars(args),
        "alphas": alphas,
        "observables": OBS_NAMES,
        "perturbations": PERT_NAMES,
        "fixed_domains": {},
        "gue_replicates": [],
        "gue_summary": {},
        "gue_short_replicates": [],
        "gue_short_summary": {},
    }

    print("fixed domains")
    print(f"{'domain':<22} {'N':>7} {'rank':>7} {'PC2':>7} {'cos(adj,large)':>15}")
    for name, gaps in fixed_domains.items():
        rng = np.random.default_rng(root_rng.integers(0, 2**63 - 1))
        res = analyze(name, gaps.astype(float), alphas, args.n_trials, args.n_baseline, rng)
        output["fixed_domains"][name] = res
        pc2 = res["pca"]["explained_variance"][1]
        cos = res["pca"]["centroid_cosine"]["adjacent_swap_vs_large_gap_only"]
        print(f"{name:<22} {len(gaps):>7} {res['pca']['effective_rank']:>7.3f} {pc2:>7.3f} {cos:>15.3f}")

    print("\nGUE independent replicates")
    for i in range(args.n_gue_replicates):
        rng = np.random.default_rng(root_rng.integers(0, 2**63 - 1))
        gaps = gue_spacings(args.gue_matrix_size, args.gue_matrices, rng)
        res = analyze(f"gue_rep_{i}", gaps, alphas, args.n_trials, args.n_baseline, rng)
        output["gue_replicates"].append(res)
        pc2 = res["pca"]["explained_variance"][1]
        cos = res["pca"]["centroid_cosine"]["adjacent_swap_vs_large_gap_only"]
        print(f"gue_rep_{i:<14} {len(gaps):>7} {res['pca']['effective_rank']:>7.3f} {pc2:>7.3f} {cos:>15.3f}")

    for i in range(args.n_gue_replicates):
        rng = np.random.default_rng(root_rng.integers(0, 2**63 - 1))
        gaps = gue_spacings(args.gue_short_matrix_size, 1, rng)
        res = analyze(f"gue_short_rep_{i}", gaps, alphas, args.n_trials, args.n_baseline, rng)
        output["gue_short_replicates"].append(res)

    output["gue_summary"] = replicate_summary(output["gue_replicates"])
    output["gue_short_summary"] = replicate_summary(output["gue_short_replicates"])

    print("\nsummary")
    for label, summary in [("gue", output["gue_summary"]), ("gue_short", output["gue_short_summary"])]:
        print(
            f"{label:<10} rank={summary['effective_rank_mean']:.3f}+/-{summary['effective_rank_std']:.3f} "
            f"PC2={summary['pc2_mean']:.3f}+/-{summary['pc2_std']:.3f} "
            f"cos={summary['adjacent_vs_large_cosine_mean']:.3f}+/-{summary['adjacent_vs_large_cosine_std']:.3f}"
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)
    print(f"\nsaved {out_path}")
    return output


def main() -> None:
    global OBSERVABLE_SET
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-prime-gaps", type=int, default=12000)
    parser.add_argument("--gue-matrix-size", type=int, default=180)
    parser.add_argument("--gue-matrices", type=int, default=16)
    parser.add_argument("--gue-short-matrix-size", type=int, default=42)
    parser.add_argument("--n-gue-replicates", type=int, default=6)
    parser.add_argument("--n-alpha", type=int, default=5)
    parser.add_argument("--alpha-min", type=float, default=0.1)
    parser.add_argument("--alpha-max", type=float, default=0.9)
    parser.add_argument("--n-trials", type=int, default=10)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260506)
    parser.add_argument("--observable-set", choices=["rank_audit", "scale_0330"], default="rank_audit")
    parser.add_argument("--out", default="tools/data/perturbation_dimensionality_audit.json")
    args = parser.parse_args()
    OBSERVABLE_SET = args.observable_set
    run(args)


if __name__ == "__main__":
    main()
