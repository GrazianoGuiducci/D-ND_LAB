#!/usr/bin/env python3
"""
exp_perturbation_rank_size_curve.py

Reusable META audit for perturbation dimensionality.

The 2026-05-06 06:25 cycle restricted the claim "GUE has a second
perturbation axis" to sample size, generator, and observable definitions.
This tool measures the size curve directly, using the canonical observable
registry and explicit original-vs-shuffle denominator diagnostics.

The report owns interpretation. This script only measures:
- effective rank and PC2 across scale-selective perturbation profiles;
- original-vs-shuffle z-score per observable;
- whether apparent rank co-occurs with weak retention denominators.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from observables_registry import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    compute_canonical,
)


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
PERT_NAMES = ["adjacent_swap", "block_shuffle", "large_gap_only", "uniform"]


def prime_gaps(n_gaps: int) -> np.ndarray:
    """Return the first n_gaps prime gaps using a compact numpy sieve."""
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


def gue_spacings(matrix_size: int, min_spacings: int, rng: np.random.Generator) -> np.ndarray:
    """Generate unfolded GUE spacings by concatenating independent matrices."""
    parts = []
    edge = max(2, matrix_size // 10)
    while sum(len(x) for x in parts) < min_spacings:
        real = rng.standard_normal((matrix_size, matrix_size))
        imag = rng.standard_normal((matrix_size, matrix_size))
        h = real + 1j * imag
        h = (h + h.conj().T) / (2.0 * np.sqrt(matrix_size))
        eigs = np.sort(np.linalg.eigvalsh(h).real)
        bulk = eigs[edge:-edge]
        gaps = np.diff(bulk)
        mean = float(np.mean(gaps))
        if mean > 1e-15:
            parts.append(gaps / mean)
    return np.concatenate(parts)[:min_spacings].astype(float)


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


def pca_summary(vectors: list[list[float]], labels: list[str]) -> dict:
    matrix = np.array(vectors, dtype=float)
    matrix = matrix - np.mean(matrix, axis=0, keepdims=True)
    if min(matrix.shape) == 0 or np.max(np.abs(matrix)) <= 1e-15:
        return {
            "explained_variance": [],
            "effective_rank": 0.0,
            "centroid_cosine": {},
            "pc2": 0.0,
        }
    _, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    energy = singular * singular
    if float(np.sum(energy)) <= 1e-15:
        explained = np.zeros_like(energy)
        effective_rank = 0.0
    else:
        explained = energy / np.sum(energy)
        pos = explained[explained > 1e-15]
        effective_rank = float(np.exp(-np.sum(pos * np.log(pos))))

    centroids = {}
    for name in PERT_NAMES:
        vals = np.array([v for v, label in zip(vectors, labels) if label == name], dtype=float)
        if len(vals):
            centroids[name] = np.mean(vals, axis=0)

    cosine = {}
    for i, a_name in enumerate(PERT_NAMES):
        for b_name in PERT_NAMES[i + 1 :]:
            if a_name not in centroids or b_name not in centroids:
                continue
            a = centroids[a_name]
            b = centroids[b_name]
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            cosine[f"{a_name}_vs_{b_name}"] = float(np.dot(a, b) / denom) if denom > 1e-15 else 0.0

    return {
        "explained_variance": [float(x) for x in explained],
        "effective_rank": effective_rank,
        "centroid_cosine": cosine,
        "pc2": float(explained[1]) if len(explained) > 1 else 0.0,
    }


def analyze_sequence(
    gaps: np.ndarray,
    alphas: list[float],
    n_trials: int,
    n_baseline: int,
    z_min: float,
    rng: np.random.Generator,
) -> dict:
    original = compute_canonical(gaps)
    baseline_vals = {obs: [] for obs in OBS_NAMES}
    for _ in range(n_baseline):
        obs = compute_canonical(rng.permutation(gaps))
        for name in OBS_NAMES:
            baseline_vals[name].append(obs[name])

    baseline = {}
    z = {}
    denom = {}
    for name in OBS_NAMES:
        vals = np.array(baseline_vals[name], dtype=float)
        mean = float(np.mean(vals))
        std = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        baseline[name] = {"mean": mean, "std": std}
        denom[name] = float(original[name] - mean)
        z[name] = float(denom[name] / std) if std > 1e-15 else 0.0

    stable_obs = [name for name in OBS_NAMES if abs(z[name]) >= z_min]
    all_vectors = []
    screened_vectors = []
    labels = []
    profiles = []

    for pert_name in PERT_NAMES:
        for alpha in alphas:
            trial_vals = {obs: [] for obs in OBS_NAMES}
            for _ in range(n_trials):
                perturbed = PERTURB[pert_name](gaps, alpha, rng)
                obs = compute_canonical(perturbed)
                for name in OBS_NAMES:
                    trial_vals[name].append(obs[name])
            means = {name: float(np.mean(trial_vals[name])) for name in OBS_NAMES}
            retention = {}
            for name in OBS_NAMES:
                retention[name] = (
                    float((means[name] - baseline[name]["mean"]) / denom[name])
                    if abs(denom[name]) > 1e-12
                    else 0.0
                )
            all_vector = [retention[name] for name in OBS_NAMES]
            screened_vector = [retention[name] for name in stable_obs]
            all_vectors.append(all_vector)
            if len(stable_obs) >= 2:
                screened_vectors.append(screened_vector)
            labels.append(pert_name)
            profiles.append(
                {
                    "perturbation": pert_name,
                    "alpha": float(alpha),
                    "retention": retention,
                    "retention_vector": all_vector,
                }
            )

    all_pca = pca_summary(all_vectors, labels)
    screened_pca = pca_summary(screened_vectors, labels) if len(stable_obs) >= 2 else None

    return {
        "n_gaps": int(len(gaps)),
        "original": original,
        "full_shuffle_baseline": baseline,
        "denominator": denom,
        "original_vs_shuffle_z": z,
        "stable_observables": stable_obs,
        "weak_observable_count": int(len(OBS_NAMES) - len(stable_obs)),
        "profiles": profiles,
        "pca_all_observables": all_pca,
        "pca_stable_observables": screened_pca,
    }


def summarize_replicates(items: list[dict]) -> dict:
    def arr(path: tuple[str, ...]) -> np.ndarray:
        vals = []
        for item in items:
            x = item
            for key in path:
                if x is None:
                    break
                x = x.get(key)
            if isinstance(x, (int, float)):
                vals.append(float(x))
        return np.array(vals, dtype=float)

    rank = arr(("pca_all_observables", "effective_rank"))
    pc2 = arr(("pca_all_observables", "pc2"))
    weak = np.array([item["weak_observable_count"] for item in items], dtype=float)
    stable_rank = arr(("pca_stable_observables", "effective_rank"))
    cos = arr(("pca_all_observables", "centroid_cosine", "adjacent_swap_vs_large_gap_only"))

    out = {
        "n_replicates": len(items),
        "rank_mean": float(np.mean(rank)) if len(rank) else 0.0,
        "rank_std": float(np.std(rank, ddof=1)) if len(rank) > 1 else 0.0,
        "pc2_mean": float(np.mean(pc2)) if len(pc2) else 0.0,
        "pc2_std": float(np.std(pc2, ddof=1)) if len(pc2) > 1 else 0.0,
        "weak_observable_count_mean": float(np.mean(weak)) if len(weak) else 0.0,
        "stable_rank_mean": float(np.mean(stable_rank)) if len(stable_rank) else None,
        "stable_rank_std": float(np.std(stable_rank, ddof=1)) if len(stable_rank) > 1 else 0.0,
        "adjacent_vs_large_cosine_mean": float(np.mean(cos)) if len(cos) else 0.0,
        "adjacent_vs_large_cosine_std": float(np.std(cos, ddof=1)) if len(cos) > 1 else 0.0,
    }
    if len(rank) > 1 and np.std(weak) > 1e-15 and np.std(rank) > 1e-15:
        out["rank_vs_weak_count_corr"] = float(np.corrcoef(rank, weak)[0, 1])
    else:
        out["rank_vs_weak_count_corr"] = 0.0
    return out


def build_prime_windows(max_n: int, n_reps: int) -> list[np.ndarray]:
    total = max_n * n_reps + max_n
    gaps = prime_gaps(total)
    max_start = len(gaps) - max_n
    starts = np.linspace(0, max_start, n_reps, dtype=int)
    return [gaps[start : start + max_n].astype(float) for start in starts]


def run(args: argparse.Namespace) -> dict:
    root_rng = np.random.default_rng(args.seed)
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    max_n = max(sizes)
    alphas = [float(x) for x in np.linspace(args.alpha_min, args.alpha_max, args.n_alpha)]

    output = {
        "experiment": "perturbation_rank_size_curve",
        "question": "Does perturbation effective-rank stabilize with sample size under canonical observables?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "perturbations": PERT_NAMES,
        "params": vars(args),
        "alphas": alphas,
        "domains": {},
        "summary": {},
    }

    prime_windows = build_prime_windows(max_n, args.n_replicates)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"{'domain':<22} {'N':>6} {'rank':>7} {'PC2':>7} {'weak':>5} {'stable_rank':>11}")

    domain_builders = {
        "primes_windows": lambda rep_rng, rep_i: prime_windows[rep_i],
        "prime_shuffle_control": lambda rep_rng, rep_i: rep_rng.permutation(prime_windows[rep_i]),
        "poisson": lambda rep_rng, rep_i: rep_rng.exponential(1.0, size=max_n),
        "gue": lambda rep_rng, rep_i: gue_spacings(args.gue_matrix_size, max_n, rep_rng),
    }

    for domain_name, builder in domain_builders.items():
        output["domains"][domain_name] = {}
        output["summary"][domain_name] = {}
        bases = []
        for rep_i in range(args.n_replicates):
            rep_rng = np.random.default_rng(root_rng.integers(0, 2**63 - 1))
            bases.append(builder(rep_rng, rep_i))

        for n in sizes:
            rows = []
            for rep_i, base in enumerate(bases):
                rep_rng = np.random.default_rng(root_rng.integers(0, 2**63 - 1))
                res = analyze_sequence(
                    base[:n],
                    alphas=alphas,
                    n_trials=args.n_trials,
                    n_baseline=args.n_baseline,
                    z_min=args.z_min,
                    rng=rep_rng,
                )
                res["replicate"] = rep_i
                rows.append(res)
            summary = summarize_replicates(rows)
            output["domains"][domain_name][str(n)] = rows
            output["summary"][domain_name][str(n)] = summary
            stable_rank = summary["stable_rank_mean"]
            stable_text = f"{stable_rank:>11.3f}" if stable_rank is not None else f"{'NA':>11}"
            print(
                f"{domain_name:<22} {n:>6} {summary['rank_mean']:>7.3f} "
                f"{summary['pc2_mean']:>7.3f} {summary['weak_observable_count_mean']:>5.2f} "
                f"{stable_text}"
            )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="128,256,512,1024,2048")
    parser.add_argument("--n-replicates", type=int, default=8)
    parser.add_argument("--gue-matrix-size", type=int, default=180)
    parser.add_argument("--n-alpha", type=int, default=5)
    parser.add_argument("--alpha-min", type=float, default=0.1)
    parser.add_argument("--alpha-max", type=float, default=0.9)
    parser.add_argument("--n-trials", type=int, default=8)
    parser.add_argument("--n-baseline", type=int, default=16)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=20260506)
    parser.add_argument("--out", default="tools/data/perturbation_rank_size_curve.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
