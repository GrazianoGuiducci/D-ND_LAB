#!/usr/bin/env python3
"""
exp_coherence_length.py — Coherence length of the dipolar ordering in prime gaps.

Question: at what subsequence length L does <r>_window significantly differ
from <r>_shuffle? This measures the scale below which primes look random and
above which the collective anti-correlation emerges.

Follows from agent_20260415: the dipole is distributed (99% of ordering is
non-local). The coherence length L* is where the ordering first becomes
detectable.

Usage:
    python tools/exp_coherence_length.py [--N_primes 6000000] [--n_surrogates 20]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def sieve_primes(limit):
    """Simple sieve of Eratosthenes."""
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]


def gap_ratio(gaps):
    """Compute <r> = mean of min(g_i, g_{i+1}) / max(g_i, g_{i+1})."""
    if len(gaps) < 2:
        return np.nan
    g1 = gaps[:-1]
    g2 = gaps[1:]
    mx = np.maximum(g1, g2)
    mask = mx > 0
    ratios = np.minimum(g1[mask], g2[mask]) / mx[mask]
    return np.mean(ratios)


def measure_coherence(gaps, window_lengths, n_windows=200, n_surrogates=20):
    """
    For each window length L:
    - Sample n_windows contiguous windows of length L from gaps
    - Compute <r> for each window
    - Compute <r> for shuffled version of same window
    - Return mean, std of <r>_prime and <r>_shuffle, plus z-score
    """
    results = []
    N = len(gaps)

    for L in window_lengths:
        if L >= N:
            continue

        r_prime_list = []
        r_shuf_lists = [[] for _ in range(n_surrogates)]

        # Sample random starting positions
        starts = np.random.randint(0, N - L, size=n_windows)
        for s in starts:
            window = gaps[s:s+L]
            r_prime_list.append(gap_ratio(window))

            for si in range(n_surrogates):
                shuf = window.copy()
                np.random.shuffle(shuf)
                r_shuf_lists[si].append(gap_ratio(shuf))

        r_prime_mean = np.mean(r_prime_list)
        r_prime_std = np.std(r_prime_list)

        # Pool all surrogate measurements
        all_shuf = [r for sl in r_shuf_lists for r in sl]
        r_shuf_mean = np.mean(all_shuf)
        r_shuf_std = np.std(all_shuf)

        # z-score: how far is the prime mean from the shuffle distribution?
        # Use standard error of the mean for the prime windows
        se_prime = r_prime_std / np.sqrt(n_windows)
        se_shuf = r_shuf_std / np.sqrt(len(all_shuf))
        se_combined = np.sqrt(se_prime**2 + se_shuf**2)
        z = (r_prime_mean - r_shuf_mean) / se_combined if se_combined > 0 else 0

        results.append({
            'L': int(L),
            'r_prime_mean': float(r_prime_mean),
            'r_prime_std': float(r_prime_std),
            'r_shuf_mean': float(r_shuf_mean),
            'r_shuf_std': float(r_shuf_std),
            'delta_r': float(r_prime_mean - r_shuf_mean),
            'z_score': float(z),
            'n_windows': int(n_windows),
            'n_surrogates': int(n_surrogates),
        })

    return results


def measure_coherence_by_scale(all_gaps, all_primes, window_lengths,
                               scale_windows=5, n_windows=150, n_surrogates=15):
    """
    Split gaps by prime scale (ln p), measure coherence length at each scale.
    Tests if L* grows with prime scale (POISSON_CONVERGENCE prediction).
    """
    N = len(all_gaps)
    ln_p = np.log(all_primes[1:N+1])  # ln(p) for each gap

    # Split into scale_windows equal bins by index
    chunk_size = N // scale_windows
    scale_results = []

    for sw in range(scale_windows):
        start_idx = sw * chunk_size
        end_idx = (sw + 1) * chunk_size if sw < scale_windows - 1 else N
        chunk_gaps = all_gaps[start_idx:end_idx]
        ln_p_mean = float(np.mean(ln_p[start_idx:end_idx]))

        # Only use window lengths that fit in the chunk
        valid_L = [L for L in window_lengths if L < len(chunk_gaps) // 2]

        results = measure_coherence(chunk_gaps, valid_L,
                                     n_windows=n_windows,
                                     n_surrogates=n_surrogates)

        # Find L* where |z| first exceeds 3 (significant)
        L_star = None
        for r in results:
            if abs(r['z_score']) > 3:
                L_star = r['L']
                break

        scale_results.append({
            'ln_p_mean': ln_p_mean,
            'L_star': L_star,
            'results': results,
        })

    return scale_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N_primes', type=int, default=6_000_000)
    parser.add_argument('--n_surrogates', type=int, default=20)
    args = parser.parse_args()

    np.random.seed(42)

    # Generate primes
    # Estimate sieve limit: p_n ~ n * ln(n) for large n
    est_limit = int(args.N_primes * (np.log(args.N_primes) + np.log(np.log(args.N_primes))) * 1.1)
    print(f"Sieving primes up to {est_limit:,}...")
    primes = sieve_primes(est_limit)
    primes = primes[:args.N_primes]
    print(f"Got {len(primes):,} primes, max = {primes[-1]:,}")

    gaps = np.diff(primes).astype(float)
    print(f"Got {len(gaps):,} gaps")

    # Window lengths: logarithmic from 10 to 100000
    window_lengths = np.unique(np.logspace(1, 5, 30).astype(int))
    print(f"\nWindow lengths: {window_lengths.tolist()}")

    # === Part 1: Global coherence length ===
    print("\n=== Part 1: Global coherence length ===")
    global_results = measure_coherence(gaps, window_lengths,
                                        n_windows=200,
                                        n_surrogates=args.n_surrogates)

    print(f"\n{'L':>8} | {'<r>_prime':>10} | {'<r>_shuf':>10} | {'delta_r':>10} | {'z':>8}")
    print("-" * 60)
    for r in global_results:
        print(f"{r['L']:>8} | {r['r_prime_mean']:>10.5f} | {r['r_shuf_mean']:>10.5f} | {r['delta_r']:>10.5f} | {r['z_score']:>8.1f}")

    # Find L* (first L where |z| > 3)
    L_star_global = None
    for r in global_results:
        if abs(r['z_score']) > 3:
            L_star_global = r['L']
            break
    print(f"\nL* (global, |z|>3): {L_star_global}")

    # === Part 2: Coherence length by scale ===
    print("\n=== Part 2: Coherence length by prime scale ===")
    scale_results = measure_coherence_by_scale(
        gaps, primes, window_lengths,
        scale_windows=5, n_windows=150, n_surrogates=15
    )

    print(f"\n{'ln(p)':>8} | {'L*':>8} | {'<r>_prime(L=1000)':>18} | {'delta_r(L=1000)':>16}")
    print("-" * 60)
    for sr in scale_results:
        # Find the result closest to L=1000
        r1k = None
        for r in sr['results']:
            if r['L'] >= 1000:
                r1k = r
                break
        r1k_str = f"{r1k['r_prime_mean']:.5f}" if r1k else "N/A"
        dr1k_str = f"{r1k['delta_r']:.5f}" if r1k else "N/A"
        lstar_str = str(sr['L_star']) if sr['L_star'] else ">max"
        print(f"{sr['ln_p_mean']:>8.2f} | {lstar_str:>8} | {r1k_str:>18} | {dr1k_str:>16}")

    # === Part 3: Delta_r scaling with L ===
    # If dipole is distributed, delta_r should grow as power law with L
    print("\n=== Part 3: Delta_r scaling with L ===")
    Ls = np.array([r['L'] for r in global_results if r['L'] >= 20])
    deltas = np.array([r['delta_r'] for r in global_results if r['L'] >= 20])

    # Fit log-log
    mask = np.abs(deltas) > 1e-10
    if np.sum(mask) > 3:
        log_L = np.log10(Ls[mask])
        log_delta = np.log10(np.abs(deltas[mask]))
        coeffs = np.polyfit(log_L, log_delta, 1)
        slope = coeffs[0]
        intercept = coeffs[1]
        predicted = np.polyval(coeffs, log_L)
        ss_res = np.sum((log_delta - predicted)**2)
        ss_tot = np.sum((log_delta - np.mean(log_delta))**2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        print(f"|delta_r| ~ L^{slope:.3f}, R^2 = {r_squared:.3f}")
        print(f"  At L=100: predicted |delta_r| = {10**(intercept + slope*2):.5f}")
        print(f"  At L=10000: predicted |delta_r| = {10**(intercept + slope*4):.5f}")
    else:
        slope = None
        r_squared = None
        print("Insufficient data for power-law fit")

    # Save results
    output = {
        'experiment': 'coherence_length',
        'date': '2026-04-16',
        'N_primes': int(len(primes)),
        'max_prime': int(primes[-1]),
        'n_surrogates': args.n_surrogates,
        'L_star_global': L_star_global,
        'delta_r_scaling': {
            'slope': float(slope) if slope is not None else None,
            'r_squared': float(r_squared) if r_squared is not None else None,
        },
        'global_results': global_results,
        'scale_results': [
            {
                'ln_p_mean': sr['ln_p_mean'],
                'L_star': sr['L_star'],
                'summary': [
                    {'L': r['L'], 'delta_r': r['delta_r'], 'z': r['z_score']}
                    for r in sr['results']
                ]
            }
            for sr in scale_results
        ]
    }

    out_path = Path(__file__).parent / 'data' / 'exp_coherence_length.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
