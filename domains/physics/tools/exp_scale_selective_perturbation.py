#!/usr/bin/env python3
"""
exp_scale_selective_perturbation.py — Scale-Selective Perturbation Audit

Consecutio from observable_rank_audit: under uniform partial shuffle, all
observables (SR, L1, L2, SR2, triple_var) collapse to 1 latent coordinate
(PC1 ~99%). Is this because the boundary is genuinely 1D, or because uniform
shuffle destroys all correlations along the same axis?

This experiment applies FOUR structurally different perturbations:
  1. Adjacent-swap: swap only neighboring pairs (destroys lag-1, preserves long-range)
  2. Block-shuffle: shuffle within blocks of size B (preserves inter-block, destroys intra-block)
  3. Large-gap-only: shuffle only the positions of above-median gaps (preserves small-gap ordering)
  4. Uniform partial: the baseline from previous runs (for comparison)

For each perturbation at multiple intensities, measure SR/L1/L2/SR2/triple_var,
compute PCA across perturbation types, and check if the rank is > 1.

If different perturbation types produce different observable profiles -> the boundary
is multi-dimensional and uniform shuffle was collapsing it.
If all perturbation types produce the same profile -> the boundary is 1D in observable space.

Usage:
    python tools/exp_scale_selective_perturbation.py [--N 30000] [--seed 20260506]
"""

import argparse
import json
import numpy as np
from pathlib import Path
from sympy import nextprime


def generate_primes(N):
    """Generate first N prime gaps."""
    gaps = []
    p = 2
    for _ in range(N + 1):
        p_next = nextprime(p)
        gaps.append(p_next - p)
        p = p_next
        if len(gaps) >= N:
            break
    return np.array(gaps, dtype=float)


def generate_gue(N, rng):
    """Generate N GUE gaps (eigenvalue spacings of random Hermitian matrix)."""
    dim = int(np.sqrt(2 * N)) + 10
    H = rng.standard_normal((dim, dim)) + 1j * rng.standard_normal((dim, dim))
    H = (H + H.conj().T) / 2
    evals = np.sort(np.linalg.eigvalsh(H))
    spacings = np.diff(evals)
    spacings = spacings[spacings > 0]
    # Unfold: normalize by local mean
    from scipy.ndimage import uniform_filter1d
    local_mean = uniform_filter1d(spacings.astype(float), size=max(50, len(spacings)//20))
    local_mean[local_mean < 1e-12] = 1e-12
    unfolded = spacings / local_mean
    if len(unfolded) >= N:
        return unfolded[:N]
    return unfolded


def generate_poisson(N, rng):
    """Generate N Poisson (iid exponential) gaps."""
    return rng.exponential(1.0, size=N)


# ---------- Observables ----------

def spectral_rigidity(gaps, L=10):
    """Delta_3(L) spectral rigidity."""
    cumulative = np.cumsum(gaps)
    cumulative = cumulative / cumulative[-1] * len(cumulative)
    n = np.arange(1, len(cumulative) + 1, dtype=float)
    window = int(min(L * len(gaps) / cumulative[-1], len(gaps) // 2))
    if window < 5:
        return 0.0
    residuals = []
    for start in range(0, len(gaps) - window, max(1, window // 2)):
        seg_n = n[start:start+window]
        seg_c = cumulative[start:start+window]
        coeffs = np.polyfit(seg_n, seg_c, 1)
        fitted = np.polyval(coeffs, seg_n)
        residuals.append(np.mean((seg_c - fitted)**2))
    return float(np.mean(residuals))


def lag1_autocorr(gaps):
    """Lag-1 autocorrelation."""
    g = gaps - np.mean(gaps)
    c0 = np.dot(g, g)
    if c0 < 1e-15:
        return 0.0
    return float(np.dot(g[:-1], g[1:]) / c0)


def lag2_autocorr(gaps):
    """Lag-2 autocorrelation."""
    g = gaps - np.mean(gaps)
    c0 = np.dot(g, g)
    if c0 < 1e-15:
        return 0.0
    return float(np.dot(g[:-2], g[2:]) / c0)


def sr2(gaps, L=20):
    """Spectral rigidity at larger L."""
    return spectral_rigidity(gaps, L=L)


def triple_variance(gaps):
    """Variance of triple products g_n * g_{n+1} * g_{n+2}."""
    triples = gaps[:-2] * gaps[1:-1] * gaps[2:]
    return float(np.var(triples))


def compute_observables(gaps):
    """Compute all 5 observables."""
    return {
        'SR': spectral_rigidity(gaps),
        'L1': lag1_autocorr(gaps),
        'L2': lag2_autocorr(gaps),
        'SR2': sr2(gaps),
        'triple_var': triple_variance(gaps),
    }


# ---------- Perturbation types ----------

def perturb_adjacent_swap(gaps, alpha, rng):
    """Swap adjacent pairs with probability alpha. Destroys lag-1, preserves long-range."""
    g = gaps.copy()
    n = len(g)
    for i in range(0, n - 1, 2):
        if rng.random() < alpha:
            g[i], g[i+1] = g[i+1], g[i]
    return g


def perturb_block_shuffle(gaps, alpha, rng, block_size=50):
    """Shuffle within blocks of size B. Alpha controls fraction of blocks shuffled."""
    g = gaps.copy()
    n = len(g)
    n_blocks = n // block_size
    blocks_to_shuffle = rng.choice(n_blocks, size=max(1, int(alpha * n_blocks)), replace=False)
    for b in blocks_to_shuffle:
        start = b * block_size
        end = min(start + block_size, n)
        rng.shuffle(g[start:end])
    return g


def perturb_large_gap_only(gaps, alpha, rng):
    """Shuffle only above-median gap positions. Alpha controls fraction shuffled."""
    g = gaps.copy()
    median_val = np.median(g)
    large_idx = np.where(g > median_val)[0]
    n_shuffle = max(2, int(alpha * len(large_idx)))
    chosen = rng.choice(large_idx, size=min(n_shuffle, len(large_idx)), replace=False)
    vals = g[chosen].copy()
    rng.shuffle(vals)
    g[chosen] = vals
    return g


def perturb_uniform(gaps, alpha, rng):
    """Standard uniform partial shuffle. Baseline from previous runs."""
    g = gaps.copy()
    n = len(g)
    n_swap = max(1, int(alpha * n / 2))
    for _ in range(n_swap):
        i, j = rng.integers(0, n, size=2)
        g[i], g[j] = g[j], g[i]
    return g


PERTURBATION_TYPES = {
    'adjacent_swap': perturb_adjacent_swap,
    'block_shuffle': perturb_block_shuffle,
    'large_gap_only': perturb_large_gap_only,
    'uniform': perturb_uniform,
}


# ---------- Main experiment ----------

def run_experiment(N=30000, seed=20260506, n_trials=16):
    rng = np.random.default_rng(seed)
    alphas = [0.1, 0.3, 0.5, 0.7, 0.9]
    obs_names = ['SR', 'L1', 'L2', 'SR2', 'triple_var']

    results = {}

    for domain_name, gen_func in [('primes', lambda: generate_primes(N)),
                                   ('GUE', lambda: generate_gue(N, rng))]:
        gaps = gen_func()
        actual_n = len(gaps)
        print(f"\n=== {domain_name} (N={actual_n}) ===")

        original_obs = compute_observables(gaps)
        print(f"Original: {original_obs}")

        # Full shuffle baseline (z-score reference)
        full_shuffle_obs = {k: [] for k in obs_names}
        for _ in range(48):
            g_shuf = gaps.copy()
            rng.shuffle(g_shuf)
            obs = compute_observables(g_shuf)
            for k in obs_names:
                full_shuffle_obs[k].append(obs[k])
        full_mean = {k: np.mean(v) for k, v in full_shuffle_obs.items()}
        full_std = {k: np.std(v) for k, v in full_shuffle_obs.items()}

        # For each perturbation type, collect observable retention curves
        # retention = (obs_perturbed - obs_shuffle) / (obs_original - obs_shuffle)
        domain_result = {
            'original': original_obs,
            'full_shuffle_mean': full_mean,
            'full_shuffle_std': full_std,
            'perturbations': {},
        }

        # Collect: for each (perturbation_type, alpha) -> mean observable vector
        # Then do PCA across perturbation types
        all_profiles = []  # list of (pert_type, alpha, obs_vector)

        for pert_name, pert_func in PERTURBATION_TYPES.items():
            pert_result = {}
            for alpha in alphas:
                trial_obs = {k: [] for k in obs_names}
                for t in range(n_trials):
                    g_pert = pert_func(gaps, alpha, rng)
                    obs = compute_observables(g_pert)
                    for k in obs_names:
                        trial_obs[k].append(obs[k])

                mean_obs = {k: float(np.mean(v)) for k, v in trial_obs.items()}

                # Compute retention: how much of the original signal survives
                retention = {}
                for k in obs_names:
                    denom = original_obs[k] - full_mean[k]
                    if abs(denom) < 1e-15:
                        retention[k] = 0.0
                    else:
                        retention[k] = (mean_obs[k] - full_mean[k]) / denom

                pert_result[f'alpha_{alpha}'] = {
                    'mean': mean_obs,
                    'retention': retention,
                }

                obs_vec = [retention[k] for k in obs_names]
                all_profiles.append((pert_name, alpha, obs_vec))

            domain_result['perturbations'][pert_name] = pert_result

        # PCA across all (perturbation_type, alpha) profiles
        profile_matrix = np.array([p[2] for p in all_profiles])
        # Center
        profile_mean = profile_matrix.mean(axis=0)
        profile_centered = profile_matrix - profile_mean
        U, S, Vt = np.linalg.svd(profile_centered, full_matrices=False)
        total_var = np.sum(S**2)
        explained = (S**2 / total_var) if total_var > 1e-15 else S * 0

        # Effective rank (entropy-based)
        p_norm = explained[explained > 1e-12]
        p_norm = p_norm / p_norm.sum()
        eff_rank = float(np.exp(-np.sum(p_norm * np.log(p_norm))))

        # Angle between perturbation-type centroids
        centroids = {}
        for pert_name in PERTURBATION_TYPES:
            vecs = [p[2] for p in all_profiles if p[0] == pert_name]
            centroids[pert_name] = np.mean(vecs, axis=0)

        # Pairwise cosine similarity between centroids
        cos_sim = {}
        pert_names_list = list(PERTURBATION_TYPES.keys())
        for i in range(len(pert_names_list)):
            for j in range(i+1, len(pert_names_list)):
                a = centroids[pert_names_list[i]]
                b = centroids[pert_names_list[j]]
                na, nb = np.linalg.norm(a), np.linalg.norm(b)
                if na > 1e-12 and nb > 1e-12:
                    cs = float(np.dot(a, b) / (na * nb))
                else:
                    cs = 0.0
                cos_sim[f'{pert_names_list[i]}_vs_{pert_names_list[j]}'] = cs

        domain_result['pca'] = {
            'singular_values': S.tolist(),
            'explained_variance': explained.tolist(),
            'effective_rank': eff_rank,
            'PC1_loadings': Vt[0].tolist() if len(Vt) > 0 else [],
            'PC2_loadings': Vt[1].tolist() if len(Vt) > 1 else [],
        }
        domain_result['centroid_cosine_similarity'] = cos_sim

        print(f"PCA explained: {explained[:3]}")
        print(f"Effective rank: {eff_rank:.3f}")
        print(f"Centroid cosine similarities: {cos_sim}")

        # Print retention table per perturbation type at alpha=0.5
        print(f"\nRetention at alpha=0.5:")
        print(f"{'Perturbation':<20} {'SR':>8} {'L1':>8} {'L2':>8} {'SR2':>8} {'triple':>8}")
        for pert_name in PERTURBATION_TYPES:
            ret = domain_result['perturbations'][pert_name]['alpha_0.5']['retention']
            print(f"{pert_name:<20} {ret['SR']:>8.3f} {ret['L1']:>8.3f} {ret['L2']:>8.3f} {ret['SR2']:>8.3f} {ret['triple_var']:>8.3f}")

        results[domain_name] = domain_result

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=30000)
    parser.add_argument('--seed', type=int, default=20260506)
    parser.add_argument('--trials', type=int, default=16)
    args = parser.parse_args()

    results = run_experiment(N=args.N, seed=args.seed, n_trials=args.trials)

    outpath = Path('tools/data/scale_selective_perturbation.json')
    with open(outpath, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {outpath}")
