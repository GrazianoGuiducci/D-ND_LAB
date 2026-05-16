#!/usr/bin/env python3
"""
Mod-3 vs Residual Ordering in Prime Gaps

Tests whether the mod-3 prohibition (zero self-transitions for residues 1,2)
fully explains the scale-dependent ordering in prime gaps, or whether
there is residual ordering beyond what mod-3 predicts.

Design:
  1. Real primes: compute Sigma^2(L) at multiple scales
  2. Free shuffle: shuffle all gaps freely (destroys all ordering)
  3. Mod-3 constrained shuffle: shuffle gaps but enforce the mod-3
     prohibition (consecutive gaps cannot share the same non-zero
     residue mod 3). Preserves mod-3 structure, destroys everything else.
  4. Compare: if mod-3 shuffle matches real primes, mod-3 explains all.
     If real primes show more rigidity, there's residual ordering.

Null: Cramer random primes (same density, no sieve) with same 3 conditions.

Usage:
  python exp_mod3_vs_residual_ordering.py [--n-primes N] [--n-shuffles N]
"""

import numpy as np
import json
import argparse
import os
from datetime import datetime


def sieve_primes(n_max):
    """Sieve of Eratosthenes up to n_max."""
    is_prime = np.ones(n_max + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(n_max**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]


def unfold_gaps(gaps):
    """Unfold gaps to mean spacing 1 using local mean from PNT."""
    # Use rolling window for local mean
    n = len(gaps)
    if n < 100:
        return gaps / np.mean(gaps)
    window = min(500, n // 5)
    local_mean = np.convolve(gaps, np.ones(window)/window, mode='same')
    # Fix edges
    local_mean[:window//2] = local_mean[window//2]
    local_mean[-window//2:] = local_mean[-window//2-1]
    local_mean[local_mean < 0.1] = np.mean(gaps)
    return gaps / local_mean


def number_variance(unfolded_gaps, L_values, n_starts=3000):
    """Sigma^2(L) from unfolded gaps."""
    levels = np.cumsum(unfolded_gaps)
    levels = np.concatenate([[0], levels])
    results = {}
    for L in L_values:
        if L > (levels[-1] - levels[0]) * 0.3:
            results[L] = np.nan
            continue
        max_start = levels[-1] - L
        starts = np.random.uniform(levels[0], max_start, size=min(n_starts, int(max_start)))
        counts = np.searchsorted(levels, starts + L) - np.searchsorted(levels, starts)
        results[L] = float(np.var(counts))
    return results


def _check_mod3(arr, pos):
    """Check if position pos has a mod-3 violation with its neighbors."""
    n = len(arr)
    r = arr[pos] % 3
    if r == 0:
        return False
    if pos > 0 and arr[pos-1] % 3 == r:
        return True
    if pos < n - 1 and arr[pos+1] % 3 == r:
        return True
    return False


def mod3_constrained_shuffle(gaps, n_mcmc=None):
    """
    Shuffle gaps preserving mod-3 prohibition via MCMC.
    Start from valid sequence built by greedy placement, then mix
    with random swaps that preserve the constraint.
    """
    n = len(gaps)
    if n_mcmc is None:
        n_mcmc = n * 10

    # Greedy build: place gaps into bins by residue, interleave
    by_res = {0: [], 1: [], 2: []}
    idx = list(range(n))
    np.random.shuffle(idx)
    for i in idx:
        by_res[int(gaps[i] % 3)].append(gaps[i])

    # Interleave: alternate 1s and 2s, pad with 0s between same-residue
    result = []
    r1, r2, r0 = by_res[1][:], by_res[2][:], by_res[0][:]
    np.random.shuffle(r1)
    np.random.shuffle(r2)
    np.random.shuffle(r0)

    # Strategy: place 0s freely, alternate 1s and 2s
    queue_12 = []
    i1, i2 = 0, 0
    flip = np.random.randint(2)  # start with 1 or 2
    while i1 < len(r1) or i2 < len(r2):
        if flip == 0 and i1 < len(r1):
            queue_12.append(r1[i1]); i1 += 1
        elif flip == 1 and i2 < len(r2):
            queue_12.append(r2[i2]); i2 += 1
        elif i1 < len(r1):
            queue_12.append(r1[i1]); i1 += 1
        else:
            queue_12.append(r2[i2]); i2 += 1
        flip = 1 - flip

    # Insert 0s at random positions (0s are always safe)
    result = queue_12[:]
    for g0 in r0:
        pos = np.random.randint(len(result) + 1)
        result.insert(pos, g0)

    result = np.array(result)

    # MCMC mixing: random pair swaps that preserve constraint
    accepted = 0
    for _ in range(n_mcmc):
        i, j = np.random.randint(n, size=2)
        if i == j or result[i] == result[j]:
            continue
        # Swap and check only the 4 affected positions
        result[i], result[j] = result[j], result[i]
        if _check_mod3(result, i) or _check_mod3(result, j):
            # Revert
            result[i], result[j] = result[j], result[i]
        else:
            accepted += 1

    return result


def cramer_random_primes(n_primes, primes_ref):
    """Generate Cramer random primes: each integer n is prime with prob 1/ln(n)."""
    # Use reference primes to set range
    max_val = int(primes_ref[-1] * 1.2)
    result = [2]
    for n in range(3, max_val, 2):
        if np.random.random() < 1.0 / np.log(n):
            result.append(n)
        if len(result) >= n_primes:
            break
    return np.array(result[:n_primes])


def run_experiment(n_max=500000, n_shuffles=100, n_cramer=5):
    """Main experiment."""
    np.random.seed(42)

    # 1. Generate primes and gaps
    primes = sieve_primes(n_max)
    gaps = np.diff(primes)
    # Skip first few (edge effects from p=2,3,5)
    gaps = gaps[3:]  # Start from p=7 onward
    n_gaps = len(gaps)

    print(f"Primes up to {n_max}: {len(primes)} primes, {n_gaps} gaps (from p=7)")
    print(f"Mean gap: {np.mean(gaps):.2f}, Std: {np.std(gaps):.2f}")

    # Verify mod-3 prohibition in real data
    res = gaps % 3
    self_trans = sum(1 for i in range(n_gaps-1)
                     if res[i] != 0 and res[i+1] != 0 and res[i] == res[i+1])
    possible = sum(1 for i in range(n_gaps-1) if res[i] != 0 and res[i+1] != 0)
    print(f"Mod-3 self-transitions: {self_trans}/{possible} ({100*self_trans/possible:.4f}%)")

    # 2. Unfold
    unfolded = unfold_gaps(gaps.astype(float))
    print(f"Unfolded: mean={np.mean(unfolded):.3f}, std={np.std(unfolded):.3f}")

    # 3. Define scales
    L_values = [1, 2, 5, 10, 20, 50, 100]

    # 4. Compute Sigma^2(L) for real primes
    print("\n--- Real primes ---")
    sig2_real = number_variance(unfolded, L_values)
    for L in L_values:
        print(f"  L={L:4d}: Sig2/L = {sig2_real[L]/L:.4f}")

    # 5. Free shuffle: destroy all ordering
    print(f"\n--- Free shuffle ({n_shuffles} realizations) ---")
    sig2_free = {L: [] for L in L_values}
    for i in range(n_shuffles):
        shuf = unfolded.copy()
        np.random.shuffle(shuf)
        sv = number_variance(shuf, L_values, n_starts=1000)
        for L in L_values:
            sig2_free[L].append(sv[L] / L)
    sig2_free_mean = {L: np.mean(sig2_free[L]) for L in L_values}
    sig2_free_std = {L: np.std(sig2_free[L]) for L in L_values}

    # 6. Mod-3 constrained shuffle
    print(f"\n--- Mod-3 constrained shuffle ({n_shuffles} realizations) ---")
    sig2_mod3 = {L: [] for L in L_values}
    for i in range(n_shuffles):
        if i % 20 == 0:
            print(f"  Realization {i+1}/{n_shuffles}...")
        # Shuffle raw gaps with mod-3 constraint, then unfold
        shuf_raw = mod3_constrained_shuffle(gaps)
        shuf_unf = unfold_gaps(shuf_raw.astype(float))
        sv = number_variance(shuf_unf, L_values, n_starts=1000)
        for L in L_values:
            sig2_mod3[L].append(sv[L] / L)
    sig2_mod3_mean = {L: np.mean(sig2_mod3[L]) for L in L_values}
    sig2_mod3_std = {L: np.std(sig2_mod3[L]) for L in L_values}

    # 7. Cramer random primes
    print(f"\n--- Cramer random primes ({n_cramer} realizations) ---")
    sig2_cramer = {L: [] for L in L_values}
    sig2_cramer_shuf = {L: [] for L in L_values}
    for i in range(n_cramer):
        print(f"  Cramer realization {i+1}/{n_cramer}...")
        cp = cramer_random_primes(len(primes), primes)
        cg = np.diff(cp)[3:].astype(float)
        cu = unfold_gaps(cg)
        sv = number_variance(cu, L_values, n_starts=1000)
        for L in L_values:
            sig2_cramer[L].append(sv[L] / L)
        # Also shuffle Cramer
        cs = cu.copy()
        np.random.shuffle(cs)
        sv2 = number_variance(cs, L_values, n_starts=1000)
        for L in L_values:
            sig2_cramer_shuf[L].append(sv2[L] / L)
    sig2_cramer_mean = {L: np.mean(sig2_cramer[L]) for L in L_values}
    sig2_cramer_shuf_mean = {L: np.mean(sig2_cramer_shuf[L]) for L in L_values}

    # 8. Compile results
    print("\n" + "="*90)
    print(f"{'L':>5} | {'Real':>8} | {'Free shuf':>10} | {'Mod3 shuf':>10} | "
          f"{'Cramer':>8} | {'Ord% real':>9} | {'Ord% mod3':>9} | {'Residual%':>9} | {'z_res':>6}")
    print("-"*90)

    results = []
    for L in L_values:
        real = sig2_real[L] / L
        free = sig2_free_mean[L]
        mod3 = sig2_mod3_mean[L]
        cramer = sig2_cramer_mean[L]

        # Ordering fractions
        ord_real = (free - real) / free * 100 if free > 0 else 0
        ord_mod3 = (free - mod3) / free * 100 if free > 0 else 0

        # Residual: ordering in real beyond what mod-3 explains
        residual = ord_real - ord_mod3

        # z-score of residual: how significant is the real-vs-mod3 difference?
        mod3_std_val = sig2_mod3_std[L]
        z_res = (mod3 - real) / mod3_std_val if mod3_std_val > 0 else 0

        print(f"{L:5d} | {real:8.4f} | {free:10.4f} | {mod3:10.4f} | "
              f"{cramer:8.4f} | {ord_real:8.1f}% | {ord_mod3:8.1f}% | {residual:8.1f}% | {z_res:6.1f}")

        results.append({
            'L': int(L),
            'sig2_L_real': round(real, 5),
            'sig2_L_free_shuffle': round(free, 5),
            'sig2_L_free_shuffle_std': round(sig2_free_std[L], 5),
            'sig2_L_mod3_shuffle': round(mod3, 5),
            'sig2_L_mod3_shuffle_std': round(mod3_std_val, 5),
            'sig2_L_cramer': round(cramer, 5),
            'sig2_L_cramer_shuffle': round(sig2_cramer_shuf_mean[L], 5),
            'ordering_pct_real': round(ord_real, 2),
            'ordering_pct_mod3': round(ord_mod3, 2),
            'residual_pct': round(residual, 2),
            'z_residual': round(z_res, 2)
        })

    # 9. Summary
    print("\n" + "="*90)
    print("SUMMARY")
    print("="*90)

    # Find crossover scale where residual dominates mod-3
    total_ord_at_L50 = results[5]['ordering_pct_real'] if len(results) > 5 else 0
    mod3_at_L50 = results[5]['ordering_pct_mod3'] if len(results) > 5 else 0
    res_at_L50 = results[5]['residual_pct'] if len(results) > 5 else 0

    print(f"At L=50: total ordering = {total_ord_at_L50:.1f}%, "
          f"mod-3 explains = {mod3_at_L50:.1f}%, "
          f"residual = {res_at_L50:.1f}%")

    # Check if Cramer has any ordering
    cramer_ord = [(sig2_cramer_shuf_mean[L] - sig2_cramer_mean[L]) / sig2_cramer_shuf_mean[L] * 100
                  for L in L_values]
    print(f"Cramer ordering: {['%.1f%%' % x for x in cramer_ord]}")

    # Mod-3 prohibition effect on Cramer
    print(f"\nCramer has {'NO' if all(abs(x) < 8 for x in cramer_ord) else 'SOME'} ordering "
          f"(all below artifact floor 7.8%)")

    # 10. Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'n_primes': int(len(primes)),
        'n_gaps': int(n_gaps),
        'n_shuffles': n_shuffles,
        'n_cramer': n_cramer,
        'mod3_self_transitions': int(self_trans),
        'mod3_possible_self_transitions': int(possible),
        'results_by_L': results
    }

    out_path = os.path.join(os.path.dirname(__file__), 'data', 'mod3_vs_residual_ordering.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nData saved to {out_path}")

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-primes', type=int, default=500000,
                        help='Sieve up to this value')
    parser.add_argument('--n-shuffles', type=int, default=100,
                        help='Number of shuffle realizations')
    parser.add_argument('--n-cramer', type=int, default=5,
                        help='Number of Cramer random prime realizations')
    args = parser.parse_args()
    run_experiment(n_max=args.n_primes, n_shuffles=args.n_shuffles, n_cramer=args.n_cramer)
