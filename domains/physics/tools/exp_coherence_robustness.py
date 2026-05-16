#!/usr/bin/env python3
"""
exp_coherence_robustness.py — Robustness check on COHERENCE_LENGTH (L*=35, delta_r=-0.014).

Segue agent_20260416_0330 (COHERENCE_LENGTH). Obiettivo: stimare confidence intervals
e varianza su L* e delta_r rispetto a scelte metodologiche:
  - seeds diversi (stochasticità sampling/shuffle)
  - n_windows diversi (quante finestre per stima)
  - strategia di windowing (contiguous random, stride, overlap)
  - numero di shuffle per surrogate

Se L*=35 e delta_r=-0.014 sopravvivono al bootstrap con CI stretti, il claim regge.
Se i CI si allargano o L* drifta, il valore era artefatto di singola scelta.

Null baseline: ogni variante comparata con lo shuffle corrispondente.

Usage:
    python tools/exp_coherence_robustness.py [--N_primes 6000000] [--n_seeds 20] [--n_boot 500]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def sieve_primes(limit):
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]


def gap_ratio(gaps):
    if len(gaps) < 2:
        return np.nan
    g1 = gaps[:-1]
    g2 = gaps[1:]
    mx = np.maximum(g1, g2)
    mask = mx > 0
    if mask.sum() == 0:
        return np.nan
    ratios = np.minimum(g1[mask], g2[mask]) / mx[mask]
    return float(np.mean(ratios))


def sample_windows(gaps, L, n_windows, strategy, rng):
    """
    strategy:
      - 'random': posizioni iniziali uniformi casuali
      - 'stride': posizioni equispaziate (stride = N/n_windows)
      - 'overlap': posizioni molto dense, stride = L/4
    """
    N = len(gaps)
    if L >= N:
        return []

    if strategy == 'random':
        starts = rng.integers(0, N - L, size=n_windows)
    elif strategy == 'stride':
        stride = max(1, (N - L) // n_windows)
        starts = np.arange(0, N - L, stride)[:n_windows]
    elif strategy == 'overlap':
        stride = max(1, L // 4)
        starts = np.arange(0, N - L, stride)[:n_windows]
    else:
        raise ValueError(f"strategy {strategy} unknown")

    return [gaps[s:s+L] for s in starts]


def measure_delta_r(gaps, L, n_windows, n_surrogates, strategy, rng):
    """
    Returns (delta_r, z_score) for one specific (L, strategy, seed) configuration.
    """
    windows = sample_windows(gaps, L, n_windows, strategy, rng)
    if not windows:
        return np.nan, np.nan

    r_prime = np.array([gap_ratio(w) for w in windows])
    r_prime = r_prime[~np.isnan(r_prime)]

    r_shuf_all = []
    for w in windows:
        for _ in range(n_surrogates):
            shuf = w.copy()
            rng.shuffle(shuf)
            r = gap_ratio(shuf)
            if not np.isnan(r):
                r_shuf_all.append(r)
    r_shuf_all = np.array(r_shuf_all)

    if len(r_prime) == 0 or len(r_shuf_all) == 0:
        return np.nan, np.nan

    mu_p, mu_s = r_prime.mean(), r_shuf_all.mean()
    se_p = r_prime.std() / np.sqrt(len(r_prime)) if len(r_prime) > 1 else 0
    se_s = r_shuf_all.std() / np.sqrt(len(r_shuf_all)) if len(r_shuf_all) > 1 else 0
    se = np.sqrt(se_p**2 + se_s**2)
    z = (mu_p - mu_s) / se if se > 0 else 0.0
    return float(mu_p - mu_s), float(z)


def estimate_L_star(gaps, L_grid, n_windows, n_surrogates, strategy, rng, z_threshold=3.0):
    """First L where |z| > z_threshold."""
    for L in L_grid:
        _, z = measure_delta_r(gaps, L, n_windows, n_surrogates, strategy, rng)
        if not np.isnan(z) and abs(z) > z_threshold:
            return int(L)
    return None


def bootstrap_L_star(gaps, L_grid, n_windows, n_surrogates, n_boot, strategy, master_seed):
    """
    Bootstrap L* re-running the estimation with different seeds.
    Returns distribution of L* values.
    """
    L_stars = []
    for i in range(n_boot):
        rng = np.random.default_rng(master_seed + i)
        L_star = estimate_L_star(gaps, L_grid, n_windows, n_surrogates, strategy, rng)
        if L_star is not None:
            L_stars.append(L_star)
    return np.array(L_stars)


def variance_over_n_windows(gaps, L_fixed, n_windows_list, n_surrogates, rng_seed):
    """How does delta_r at fixed L vary with n_windows?"""
    results = []
    for nw in n_windows_list:
        rng = np.random.default_rng(rng_seed)
        dr, z = measure_delta_r(gaps, L_fixed, nw, n_surrogates, 'random', rng)
        results.append({'n_windows': int(nw), 'delta_r': dr, 'z': z})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N_primes', type=int, default=6_000_000)
    parser.add_argument('--n_seeds', type=int, default=20, help='bootstrap replicates')
    parser.add_argument('--n_boot', type=int, default=500, help='bootstrap L* resamples')
    parser.add_argument('--n_surrogates', type=int, default=20)
    parser.add_argument('--L_fixed', type=int, default=1000, help='L for intensivity check')
    args = parser.parse_args()

    # Generate primes
    est_limit = int(args.N_primes * (np.log(args.N_primes) + np.log(np.log(args.N_primes))) * 1.1)
    print(f"Sieving primes up to {est_limit:,}...")
    primes = sieve_primes(est_limit)[:args.N_primes]
    gaps = np.diff(primes).astype(float)
    print(f"Got {len(primes):,} primes, {len(gaps):,} gaps, max = {primes[-1]:,}")

    # L grid: logarithmic 10 → 100K
    L_grid = np.unique(np.logspace(1, 5, 30).astype(int))

    # === Part 1: bootstrap L* (random windowing) ===
    print(f"\n=== Part 1: bootstrap L* (n_boot={args.n_boot}, strategy=random) ===")
    L_stars = bootstrap_L_star(
        gaps, L_grid,
        n_windows=200, n_surrogates=args.n_surrogates,
        n_boot=args.n_boot, strategy='random', master_seed=42
    )
    if len(L_stars) > 0:
        median = int(np.median(L_stars))
        lo, hi = np.percentile(L_stars, [2.5, 97.5])
        print(f"L* median = {median}, 95% CI = [{int(lo)}, {int(hi)}]")
        print(f"mean = {L_stars.mean():.1f}, std = {L_stars.std():.2f}")
        print(f"mode = {int(np.bincount(L_stars).argmax())}")
    else:
        print("No L* found in any bootstrap replicate.")

    # === Part 2: varianza su n_windows ===
    print(f"\n=== Part 2: variance vs n_windows (L={args.L_fixed}) ===")
    n_windows_list = [50, 100, 200, 500, 1000]
    nw_results = variance_over_n_windows(gaps, args.L_fixed, n_windows_list,
                                         args.n_surrogates, rng_seed=42)
    print(f"{'n_windows':>10} | {'delta_r':>10} | {'z':>8}")
    for r in nw_results:
        print(f"{r['n_windows']:>10} | {r['delta_r']:>10.5f} | {r['z']:>8.1f}")

    # === Part 3: varianza su strategie di windowing ===
    print(f"\n=== Part 3: variance across windowing strategies (L={args.L_fixed}) ===")
    strategies = ['random', 'stride', 'overlap']
    strat_results = []
    for strat in strategies:
        dr_list, z_list = [], []
        for seed in range(args.n_seeds):
            rng = np.random.default_rng(42 + seed)
            dr, z = measure_delta_r(gaps, args.L_fixed, 200, args.n_surrogates, strat, rng)
            if not np.isnan(dr):
                dr_list.append(dr)
                z_list.append(z)
        if dr_list:
            entry = {
                'strategy': strat,
                'delta_r_mean': float(np.mean(dr_list)),
                'delta_r_std': float(np.std(dr_list)),
                'z_mean': float(np.mean(z_list)),
                'z_std': float(np.std(z_list)),
                'n_seeds': len(dr_list),
            }
            strat_results.append(entry)
            print(f"{strat:>8}: delta_r = {entry['delta_r_mean']:.5f} +/- {entry['delta_r_std']:.5f}, "
                  f"z = {entry['z_mean']:.1f} +/- {entry['z_std']:.1f}")

    # === Part 4: delta_r intensivity across L ===
    # Key claim of COHERENCE_LENGTH: delta_r ~ constant across L (intensive, not extensive).
    # Bootstrap across seeds at multiple L to get CI on delta_r for each L.
    print(f"\n=== Part 4: delta_r intensivity (L = 35, 100, 1000, 10000, 100000) ===")
    L_test = [35, 100, 1000, 10000, 100000]
    L_test = [L for L in L_test if L < len(gaps)]
    intensivity = []
    for L in L_test:
        dr_list = []
        for seed in range(args.n_seeds):
            rng = np.random.default_rng(42 + seed)
            dr, _ = measure_delta_r(gaps, L, 200, args.n_surrogates, 'random', rng)
            if not np.isnan(dr):
                dr_list.append(dr)
        if dr_list:
            lo, hi = np.percentile(dr_list, [2.5, 97.5])
            entry = {
                'L': int(L),
                'delta_r_mean': float(np.mean(dr_list)),
                'delta_r_std': float(np.std(dr_list)),
                'ci_95': [float(lo), float(hi)],
                'n_seeds': len(dr_list),
            }
            intensivity.append(entry)
            print(f"L={L:>7}: delta_r = {entry['delta_r_mean']:.5f} "
                  f"[{entry['ci_95'][0]:.5f}, {entry['ci_95'][1]:.5f}] (n={entry['n_seeds']})")

    # Test intensivity: do CIs overlap across L?
    # If yes → intensive confirmed. If no → scaling exists.
    if len(intensivity) >= 2:
        dr_means = [r['delta_r_mean'] for r in intensivity]
        spread = max(dr_means) - min(dr_means)
        typical_std = np.mean([r['delta_r_std'] for r in intensivity])
        overlap_ratio = spread / typical_std if typical_std > 0 else np.inf
        print(f"\nSpread of delta_r across L: {spread:.5f}")
        print(f"Typical std within each L: {typical_std:.5f}")
        print(f"Spread / std: {overlap_ratio:.2f} (< 2 = intensive, > 2 = scaling)")

    # === Save ===
    output = {
        'experiment': 'coherence_robustness',
        'date': '2026-04-17',
        'N_primes': int(len(primes)),
        'max_prime': int(primes[-1]),
        'args': vars(args),
        'bootstrap_L_star': {
            'n_boot': args.n_boot,
            'values': L_stars.tolist(),
            'median': int(np.median(L_stars)) if len(L_stars) > 0 else None,
            'ci_95': [float(np.percentile(L_stars, 2.5)), float(np.percentile(L_stars, 97.5))] if len(L_stars) > 0 else None,
            'mean': float(L_stars.mean()) if len(L_stars) > 0 else None,
            'std': float(L_stars.std()) if len(L_stars) > 0 else None,
        },
        'variance_over_n_windows': nw_results,
        'variance_over_strategies': strat_results,
        'intensivity_check': intensivity,
    }

    out_path = Path(__file__).parent / 'data' / 'exp_coherence_robustness.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
