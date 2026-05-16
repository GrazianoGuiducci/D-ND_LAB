#!/usr/bin/env python3
"""
exp_observable_rank_audit.py - META audit for observable collinearity.

Recent runs found many Markov/crossover observables that react coherently under
partial shuffle. This script asks whether those observables carry independent
directions or mostly re-measure one latent boundary coordinate.

It measures retention curves from alpha-partial shuffles, then reports:
  - original-vs-full-shuffle z for each observable
  - PCA energy of the retention matrix across alpha
  - effective rank of that matrix
  - pairwise correlations between retention curves

The script measures data only. The report decides the structural claim.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from exp_3d_boundary_layers import get_primes, gue_gaps, partial_shuffle
from observables_registry import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    compute_canonical,
)


OBSERVABLES = OBSERVABLES_CANONICAL
OBS_NAMES = list(OBSERVABLES)


def measure(gaps):
    return compute_canonical(gaps)


def full_shuffle_baseline(gaps, n_trials, rng):
    vals = {name: [] for name in OBSERVABLES}
    for _ in range(n_trials):
        s = rng.permutation(gaps)
        row = measure(s)
        for name, value in row.items():
            vals[name].append(value)
    return {
        name: {
            "mean": float(np.mean(x)),
            "std": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
        }
        for name, x in vals.items()
    }


def retention_curves(gaps, alphas, n_trials, originals, baseline, rng):
    rows = []
    for alpha in alphas:
        vals = {name: [] for name in OBSERVABLES}
        for _ in range(n_trials):
            s = partial_shuffle(gaps, float(alpha), rng)
            row = measure(s)
            for name, value in row.items():
                vals[name].append(value)

        out = {"alpha": float(alpha)}
        for name in OBSERVABLES:
            mean = float(np.mean(vals[name]))
            denom = originals[name] - baseline[name]["mean"]
            retention = (mean - baseline[name]["mean"]) / denom if abs(denom) > 1e-12 else 0.0
            out[name] = {
                "mean": mean,
                "std": float(np.std(vals[name], ddof=1)) if len(vals[name]) > 1 else 0.0,
                "retention": float(retention),
            }
        rows.append(out)
    return rows


def pca_summary(rows):
    names = OBS_NAMES
    matrix = np.array([[row[name]["retention"] for name in names] for row in rows], dtype=float)
    matrix = matrix - np.mean(matrix, axis=0, keepdims=True)

    _, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    energy = singular * singular
    if np.sum(energy) <= 1e-15:
        explained = np.zeros_like(energy)
        effective_rank = 0.0
    else:
        explained = energy / np.sum(energy)
        positive = explained[explained > 1e-15]
        effective_rank = float(np.exp(-np.sum(positive * np.log(positive))))

    corr = np.corrcoef(matrix, rowvar=False)
    abs_corr = np.abs(corr)
    upper = abs_corr[np.triu_indices_from(abs_corr, k=1)]

    return {
        "observables": names,
        "singular_values": [float(x) for x in singular],
        "explained_variance": [float(x) for x in explained],
        "effective_rank": effective_rank,
        "pc1_loadings": {name: float(vt[0, i]) for i, name in enumerate(names)} if len(vt) else {},
        "mean_abs_pairwise_corr": float(np.mean(upper)) if len(upper) else 0.0,
        "min_abs_pairwise_corr": float(np.min(upper)) if len(upper) else 0.0,
        "max_abs_pairwise_corr": float(np.max(upper)) if len(upper) else 0.0,
    }


def analyze_sequence(name, gaps, alphas, n_trials, n_baseline, rng):
    originals = measure(gaps)
    baseline = full_shuffle_baseline(gaps, n_baseline, rng)
    rows = retention_curves(gaps, alphas, n_trials, originals, baseline, rng)

    z = {}
    stable_observables = []
    for obs_name in OBS_NAMES:
        std = baseline[obs_name]["std"]
        z[obs_name] = float((originals[obs_name] - baseline[obs_name]["mean"]) / std) if std > 1e-12 else 0.0
        if abs(z[obs_name]) >= 2.0:
            stable_observables.append(obs_name)

    return {
        "n_gaps": int(len(gaps)),
        "originals": originals,
        "full_shuffle_baseline": baseline,
        "original_vs_shuffle_z": z,
        "stable_observables_abs_z_ge_2": stable_observables,
        "weak_observable_count": int(len(OBS_NAMES) - len(stable_observables)),
        "retention_curves": rows,
        "pca": pca_summary(rows),
    }


def build_sequences(n_gaps, rng):
    primes = get_primes(n_gaps * 24)[: n_gaps + 1]
    prime_gaps = np.diff(primes).astype(float)

    gue = gue_gaps(160, max(8, n_gaps // 160 + 1), rng).astype(float)
    gue = gue[:n_gaps]

    poisson = rng.exponential(1.0, size=n_gaps).astype(float)
    prime_shuffle = rng.permutation(prime_gaps).astype(float)
    return {
        "primes": prime_gaps,
        "prime_shuffle": prime_shuffle,
        "gue": gue,
        "poisson": poisson,
    }


def run(n_gaps=30000, n_alpha=19, n_trials=24, n_baseline=72, seed=20260505, out="tools/data/observable_rank_audit.json"):
    rng = np.random.default_rng(seed)
    alphas = np.linspace(0.05, 0.95, n_alpha)
    sequences = build_sequences(n_gaps, rng)

    output = {
        "experiment": "observable_rank_audit",
        "question": "When do canonical observable retention curves break collinearity across domains?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "params": {
            "n_gaps": int(n_gaps),
            "n_alpha": int(n_alpha),
            "n_trials": int(n_trials),
            "n_baseline": int(n_baseline),
            "seed": int(seed),
        },
        "sequences": {},
    }

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"n_gaps={n_gaps}, n_alpha={n_alpha}, n_trials={n_trials}, n_baseline={n_baseline}, seed={seed}")
    print(f"{'sequence':<14} {'pc1':>8} {'eff_rank':>9} {'mean|corr|':>11} {'weak':>5}  z(SR,SR2,L1,L2,triple_var)")
    print("-" * 108)
    for seq_name, gaps in sequences.items():
        result = analyze_sequence(seq_name, gaps, alphas, n_trials, n_baseline, rng)
        output["sequences"][seq_name] = result
        pca = result["pca"]
        z = result["original_vs_shuffle_z"]
        z_text = ", ".join(f"{obs}={z[obs]:+.1f}" for obs in OBS_NAMES)
        pc1 = pca["explained_variance"][0] if pca["explained_variance"] else 0.0
        print(
            f"{seq_name:<14} {pc1:>8.3f} {pca['effective_rank']:>9.3f} "
            f"{pca['mean_abs_pairwise_corr']:>11.3f} {result['weak_observable_count']:>5}  {z_text}"
        )

    out_path = Path(out)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_gaps", type=int, default=30000)
    parser.add_argument("--n_alpha", type=int, default=19)
    parser.add_argument("--n_trials", type=int, default=24)
    parser.add_argument("--n_baseline", type=int, default=72)
    parser.add_argument("--seed", type=int, default=20260505)
    parser.add_argument("--out", default="tools/data/observable_rank_audit.json")
    args = parser.parse_args()
    run(
        n_gaps=args.n_gaps,
        n_alpha=args.n_alpha,
        n_trials=args.n_trials,
        n_baseline=args.n_baseline,
        seed=args.seed,
        out=args.out,
    )


if __name__ == "__main__":
    main()
