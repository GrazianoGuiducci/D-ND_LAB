#!/usr/bin/env python3
"""
Modular Memory Spectrum of Prime Gaps

Question: The Markov memory result (2026-04-25) found 140x stronger memory in
mod-6 residues vs terciles. F2 says gaps are confined to {2,4} mod 6.
But WHY mod 6? Is it special (smallest non-trivial primorial 2*3=6),
or does memory grow with modular base (mod-30=2*3*5, mod-210=2*3*5*7)?

Method:
- For bases m = 2,3,4,5,6,10,12,15,30,42,210 compute gap residues mod m
- For each: Markov-1 conditional entropy H(X_t|X_{t-1}) real vs 200 shuffles
- Ordering fraction = (H_shuffle - H_real) / H_shuffle
- Also: count how many residue classes are actually OCCUPIED (confinement)
- Null: Cramer random primes (same density, no arithmetic structure)

The memory-vs-base profile discriminates:
  - Peak at 6 → structure is at primorial(2,3) level
  - Monotonic growth → structure deepens with primorial hierarchy
  - Cramer reproduces → density effect (tautology). Cramer differs → arithmetic.

Reusable: python exp_modular_memory_spectrum.py [--n-max 500000] [--n-cramer 10]
"""

import numpy as np
import json
import sys
from collections import Counter
from datetime import datetime


def sieve_primes(n_max):
    """Sieve of Eratosthenes."""
    is_prime = np.ones(n_max + 1, dtype=bool)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]


def cramer_random_primes(n_max, rng):
    """Cramer model: each odd n >= 3 included with prob 2/ln(n)."""
    result = [2]
    n_vals = np.arange(3, n_max, 2)
    probs = 2.0 / np.log(n_vals)
    probs = np.clip(probs, 0, 1)
    mask = rng.random(len(n_vals)) < probs
    result.extend(n_vals[mask].tolist())
    return np.array(result)


def conditional_entropy_order1(cats, n_classes):
    """Compute H(X_t | X_{t-1}) in bits."""
    n = len(cats)
    if n < 3:
        return float('nan')

    # Count transitions
    trans = np.zeros((n_classes, n_classes), dtype=int)
    for i in range(1, n):
        trans[cats[i-1], cats[i]] += 1

    row_sums = trans.sum(axis=1)
    total = row_sums.sum()

    H = 0.0
    for a in range(n_classes):
        if row_sums[a] == 0:
            continue
        for b in range(n_classes):
            if trans[a, b] == 0:
                continue
            p_joint = trans[a, b] / total
            p_cond = trans[a, b] / row_sums[a]
            H -= p_joint * np.log2(p_cond)
    return H


def modular_memory(gaps, base, n_shuffles=200):
    """Compute Markov-1 ordering fraction for gaps mod base.

    Returns dict with H_real, H_shuffle, ordering_pct, z_score,
    n_occupied (number of residue classes used), confinement_ratio.
    """
    residues = gaps.astype(int) % base
    n_classes = base

    # Count occupied classes
    occupied = len(set(residues))
    confinement = occupied / base

    # Real entropy
    H_real = conditional_entropy_order1(residues, n_classes)

    # Shuffle baseline
    H_shuffles = []
    for _ in range(n_shuffles):
        perm = np.random.permutation(residues)
        H_shuffles.append(conditional_entropy_order1(perm, n_classes))

    H_shuf_mean = np.mean(H_shuffles)
    H_shuf_std = np.std(H_shuffles)

    if H_shuf_mean > 0:
        ordering_pct = (H_shuf_mean - H_real) / H_shuf_mean * 100
    else:
        ordering_pct = 0.0

    z = (H_real - H_shuf_mean) / H_shuf_std if H_shuf_std > 0 else 0.0

    return {
        'base': base,
        'H_real': round(H_real, 5),
        'H_shuf_mean': round(H_shuf_mean, 5),
        'H_shuf_std': round(H_shuf_std, 5),
        'ordering_pct': round(ordering_pct, 2),
        'z_score': round(z, 1),
        'n_occupied': occupied,
        'n_possible': base,
        'confinement': round(confinement, 3),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-max', type=int, default=500000)
    parser.add_argument('--n-cramer', type=int, default=10)
    parser.add_argument('--n-shuffles', type=int, default=200)
    args = parser.parse_args()

    np.random.seed(42)
    rng = np.random.default_rng(42)

    print("=== Modular Memory Spectrum of Prime Gaps ===\n")

    # Generate primes
    print(f"Sieving primes up to {args.n_max:,}...")
    primes = sieve_primes(args.n_max)
    gaps = np.diff(primes).astype(float)
    print(f"  {len(primes):,} primes, {len(gaps):,} gaps\n")

    # Bases: primorials + intermediates
    # 2, 3, 6=2*3, 30=2*3*5, 210=2*3*5*7 (primorials)
    # 4, 5, 10, 12, 15, 42 (non-primorial controls)
    bases = [2, 3, 4, 5, 6, 10, 12, 15, 30, 42, 210]

    # === PRIMES ===
    print("--- Real primes ---")
    prime_results = []
    for b in bases:
        r = modular_memory(gaps, b, n_shuffles=args.n_shuffles)
        prime_results.append(r)
        print(f"  mod {b:>3}: ord={r['ordering_pct']:>7.2f}%  z={r['z_score']:>7.1f}  "
              f"occupied={r['n_occupied']}/{r['n_possible']}  "
              f"confine={r['confinement']:.3f}")

    # === CRAMER NULL ===
    print(f"\n--- Cramer null model ({args.n_cramer} realizations) ---")
    cramer_results_all = {b: [] for b in bases}

    for i in range(args.n_cramer):
        cp = cramer_random_primes(args.n_max, rng)
        cg = np.diff(cp).astype(float)
        for b in bases:
            r = modular_memory(cg, b, n_shuffles=50)  # fewer shuffles for null
            cramer_results_all[b].append(r)
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{args.n_cramer} done")

    cramer_summary = []
    for b in bases:
        ords = [r['ordering_pct'] for r in cramer_results_all[b]]
        occs = [r['n_occupied'] for r in cramer_results_all[b]]
        cramer_summary.append({
            'base': b,
            'ordering_pct_mean': round(np.mean(ords), 2),
            'ordering_pct_std': round(np.std(ords), 2),
            'n_occupied_mean': round(np.mean(occs), 1),
        })

    # === COMPARISON TABLE ===
    print("\n" + "=" * 110)
    print(f"{'Base':>5} {'Type':>10} | {'Prime ord%':>10} {'Prime z':>8} "
          f"{'Occ':>4}/{'':<4} | {'Cramer ord%':>14} "
          f"{'Delta':>8} {'Excess_z':>9}")
    print("-" * 110)

    is_primorial = {2: True, 6: True, 30: True, 210: True,
                    3: False, 4: False, 5: False, 10: False,
                    12: False, 15: False, 42: False}

    for pr, cs in zip(prime_results, cramer_summary):
        b = pr['base']
        btype = "PRIMORIAL" if is_primorial.get(b) else "other"
        delta = pr['ordering_pct'] - cs['ordering_pct_mean']
        excess_z = delta / cs['ordering_pct_std'] if cs['ordering_pct_std'] > 0 else 0

        print(f"{b:>5} {btype:>10} | {pr['ordering_pct']:>10.2f} {pr['z_score']:>8.1f} "
              f"{pr['n_occupied']:>4}/{pr['n_possible']:<4} | "
              f"{cs['ordering_pct_mean']:>6.2f}+/-{cs['ordering_pct_std']:<5.2f} "
              f"{delta:>+8.2f} {excess_z:>+9.1f}")

    print("=" * 110)

    # === KEY DIAGNOSTICS ===
    print("\n--- Diagnostics ---")

    # 1. Peak detection: where is ordering strongest?
    ord_vals = [r['ordering_pct'] for r in prime_results]
    peak_idx = np.argmax(ord_vals)
    print(f"1. Peak ordering: mod {bases[peak_idx]} at {ord_vals[peak_idx]:.2f}%")

    # 2. Primorial vs non-primorial
    primo_ords = [r['ordering_pct'] for r in prime_results if is_primorial.get(r['base'])]
    other_ords = [r['ordering_pct'] for r in prime_results if not is_primorial.get(r['base'])]
    print(f"2. Primorial avg: {np.mean(primo_ords):.2f}% vs Non-primorial avg: {np.mean(other_ords):.2f}%")

    # 3. Confinement: do primes use fewer residue classes than expected?
    print("3. Confinement (occupied/possible):")
    for pr, cs in zip(prime_results, cramer_summary):
        b = pr['base']
        # Euler totient gives expected occupied classes for gaps
        # But simpler: just compare prime vs Cramer occupancy
        print(f"   mod {b:>3}: primes={pr['n_occupied']}/{pr['n_possible']}  "
              f"Cramer={cs['n_occupied_mean']:.0f}/{pr['n_possible']}")

    # 4. Does ordering grow with base (for primorials)?
    primo_bases = [2, 6, 30, 210]
    primo_ord = [r['ordering_pct'] for r in prime_results if r['base'] in primo_bases]
    if len(primo_ord) >= 2:
        trend = "GROWING" if primo_ord[-1] > primo_ord[0] else "DECLINING"
        print(f"4. Primorial trend: {list(zip(primo_bases, primo_ord))} -> {trend}")

    # 5. Excess over Cramer: which bases show MOST arithmetic content?
    print("5. Excess over Cramer (prime - Cramer ordering):")
    excesses = []
    for pr, cs in zip(prime_results, cramer_summary):
        delta = pr['ordering_pct'] - cs['ordering_pct_mean']
        excesses.append((pr['base'], delta))
    excesses.sort(key=lambda x: -x[1])
    for b, d in excesses[:5]:
        tag = "PRIMORIAL" if is_primorial.get(b) else ""
        print(f"   mod {b:>3}: excess = {d:>+.2f}% {tag}")

    # === SAVE ===
    output = {
        'experiment': 'modular_memory_spectrum',
        'timestamp': datetime.now().isoformat(),
        'n_max': args.n_max,
        'n_primes': len(primes),
        'n_gaps': len(gaps),
        'n_cramer': args.n_cramer,
        'n_shuffles': args.n_shuffles,
        'bases': bases,
        'prime_results': prime_results,
        'cramer_summary': cramer_summary,
        'peak_base': int(bases[peak_idx]),
        'peak_ordering_pct': float(ord_vals[peak_idx]),
    }

    outpath = '/opt/MM_D-ND/tools/data/modular_memory_spectrum.json'
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved to {outpath}")

    return output


if __name__ == '__main__':
    main()
