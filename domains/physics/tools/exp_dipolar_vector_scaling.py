#!/usr/bin/env python3
"""
exp_dipolar_vector_scaling.py — Dipolar vector of order-sensitive observables across scales.

Two observables are order-sensitive in prime gaps (survive shuffle test):
  - spacing_ratio: mean(min(g_i, g_{i+1}) / max(g_i, g_{i+1}))
  - lag1_acf: autocorrelation at lag 1

For each scale (window of N primes starting at offset), compute:
  - Real value of each observable
  - Shuffle baseline (mean, std over K shuffles)
  - Deviation: Delta = (real - shuffle_mean) / shuffle_std  (z-score)

The "dipolar vector" is (Delta_spacing, Delta_lag1).
Track angle theta = atan2(Delta_lag1, Delta_spacing) across scales.

Question: does theta rotate (internal dynamics) or stay constant (pure decay/invariant)?
"""

import numpy as np
from sympy import primerange
import json, sys, os

def get_primes_in_range(lo, hi):
    """Get primes in [lo, hi)."""
    return np.array(list(primerange(lo, hi)), dtype=np.int64)

def spacing_ratio(gaps):
    """Mean of min/max for consecutive gaps."""
    if len(gaps) < 2:
        return np.nan
    g1 = gaps[:-1].astype(float)
    g2 = gaps[1:].astype(float)
    mn = np.minimum(g1, g2)
    mx = np.maximum(g1, g2)
    # Avoid division by zero
    valid = mx > 0
    return np.mean(mn[valid] / mx[valid])

def lag1_acf(gaps):
    """Lag-1 autocorrelation of gap sequence."""
    if len(gaps) < 3:
        return np.nan
    g = gaps.astype(float)
    mu = g.mean()
    var = g.var()
    if var == 0:
        return np.nan
    return np.mean((g[:-1] - mu) * (g[1:] - mu)) / var

def compute_observables(gaps):
    """Return (spacing_ratio, lag1_acf) for a gap sequence."""
    return spacing_ratio(gaps), lag1_acf(gaps)

def shuffle_baseline(gaps, n_shuffles=200):
    """Compute shuffle mean and std for both observables."""
    sr_vals = []
    l1_vals = []
    for _ in range(n_shuffles):
        shuffled = gaps.copy()
        np.random.shuffle(shuffled)
        sr, l1 = compute_observables(shuffled)
        sr_vals.append(sr)
        l1_vals.append(l1)
    sr_arr = np.array(sr_vals)
    l1_arr = np.array(l1_vals)
    return {
        'sr_mean': np.mean(sr_arr), 'sr_std': np.std(sr_arr),
        'l1_mean': np.mean(l1_arr), 'l1_std': np.std(l1_arr),
    }

def analyze_scale(primes, label=""):
    """Full analysis for one scale window."""
    gaps = np.diff(primes)
    sr_real, l1_real = compute_observables(gaps)
    baseline = shuffle_baseline(gaps, n_shuffles=200)

    # Z-scores (the dipolar vector components)
    z_sr = (sr_real - baseline['sr_mean']) / baseline['sr_std'] if baseline['sr_std'] > 0 else 0
    z_l1 = (l1_real - baseline['l1_mean']) / baseline['l1_std'] if baseline['l1_std'] > 0 else 0

    # Angle and magnitude
    theta = np.degrees(np.arctan2(z_l1, z_sr))
    magnitude = np.sqrt(z_sr**2 + z_l1**2)

    return {
        'label': label,
        'n_primes': len(primes),
        'n_gaps': len(gaps),
        'sr_real': round(sr_real, 6),
        'l1_real': round(l1_real, 6),
        'sr_shuffle_mean': round(baseline['sr_mean'], 6),
        'sr_shuffle_std': round(baseline['sr_std'], 6),
        'l1_shuffle_mean': round(baseline['l1_mean'], 6),
        'l1_shuffle_std': round(baseline['l1_std'], 6),
        'z_sr': round(z_sr, 2),
        'z_l1': round(z_l1, 2),
        'theta_deg': round(theta, 2),
        'magnitude': round(magnitude, 2),
    }

def main():
    np.random.seed(42)

    # Scales: windows of primes at different positions
    # Use starting offsets to probe different scales
    scales = [
        ('1e4', 2, 10_000),
        ('3e4', 2, 30_000),
        ('1e5', 2, 100_000),
        ('3e5', 2, 300_000),
        ('1e6', 2, 1_000_000),
        ('3e6', 2, 3_000_000),
    ]

    # Also test at HIGH offset (primes near 1e8) to check if the pattern holds far from origin
    # Use a fixed window size at different offsets
    window_scales = [
        ('win_1e4', 2, 10_000),
        ('win_1e5', 50_000, 150_000),
        ('win_1e6', 500_000, 1_500_000),
        ('win_high', 2_000_000, 3_000_000),
    ]

    results = []

    print("=" * 80)
    print("DIPOLAR VECTOR SCALING — spacing_ratio + lag1_acf across scales")
    print("=" * 80)

    # Part 1: Growing window from origin
    print("\n--- Part 1: Growing window [2, N] ---")
    print(f"{'Scale':<10} {'N_primes':<10} {'z_SR':<8} {'z_L1':<8} {'theta':<8} {'|V|':<8} {'SR_real':<10} {'L1_real':<10}")
    print("-" * 80)

    for label, lo, hi in scales:
        primes = get_primes_in_range(lo, hi)
        r = analyze_scale(primes, label)
        results.append(r)
        print(f"{label:<10} {r['n_primes']:<10} {r['z_sr']:<8} {r['z_l1']:<8} {r['theta_deg']:<8} {r['magnitude']:<8} {r['sr_real']:<10} {r['l1_real']:<10}")

    # Part 2: Fixed-size windows at different offsets
    print("\n--- Part 2: Fixed-size windows (50K primes) at different offsets ---")

    offsets = [
        ('off_0', 2, 50_000),        # first 50K primes
        ('off_500K', 500_000, 550_000),
        ('off_1M', 1_000_000, 1_050_000),
        ('off_2M', 2_000_000, 2_050_000),
    ]

    print(f"{'Label':<10} {'Start_p':<12} {'z_SR':<8} {'z_L1':<8} {'theta':<8} {'|V|':<8}")
    print("-" * 60)

    offset_results = []
    for label, lo_idx, hi_idx in offsets:
        # Get enough primes, then slice by index
        # For efficiency, get primes up to a reasonable bound
        # p_n ~ n * ln(n) for large n
        import math
        upper_bound = int(hi_idx * (math.log(hi_idx) + math.log(math.log(hi_idx + 10)) + 3))
        all_p = get_primes_in_range(2, upper_bound)
        if len(all_p) < hi_idx:
            upper_bound = int(upper_bound * 1.5)
            all_p = get_primes_in_range(2, upper_bound)
        primes = all_p[lo_idx:hi_idx] if lo_idx > 0 else all_p[:hi_idx]

        r = analyze_scale(primes, label)
        offset_results.append(r)
        start_prime = primes[0] if len(primes) > 0 else 0
        print(f"{label:<10} {start_prime:<12} {r['z_sr']:<8} {r['z_l1']:<8} {r['theta_deg']:<8} {r['magnitude']:<8}")

    results.extend(offset_results)

    # Part 3: Cramer random model baseline
    print("\n--- Part 3: Cramer random model (same density, no correlations) ---")
    print("Generating Cramer pseudo-primes at 3 scales...")

    cramer_results = []
    for n_target, label in [(10000, 'cramer_1e4'), (100000, 'cramer_1e5'), (1000000, 'cramer_1e6')]:
        # Cramer: each integer n is "prime" with probability 1/ln(n)
        cramer_primes = [2]
        n = 3
        while len(cramer_primes) < n_target:
            if np.random.random() < 1.0 / np.log(n):
                cramer_primes.append(n)
            n += 1
        cramer_primes = np.array(cramer_primes)
        r = analyze_scale(cramer_primes, label)
        cramer_results.append(r)
        print(f"  {label}: z_SR={r['z_sr']}, z_L1={r['z_l1']}, theta={r['theta_deg']}, |V|={r['magnitude']}")

    results.extend(cramer_results)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    growing = [r for r in results if r['label'].startswith(('1e', '3e'))]
    thetas = [r['theta_deg'] for r in growing]
    magnitudes = [r['magnitude'] for r in growing]

    if len(thetas) >= 2:
        theta_std = np.std(thetas)
        theta_range = max(thetas) - min(thetas)
        mag_ratio = magnitudes[-1] / magnitudes[0] if magnitudes[0] != 0 else float('inf')

        print(f"Growing window theta range: {theta_range:.1f} deg (std={theta_std:.1f})")
        print(f"Growing window magnitude ratio (last/first): {mag_ratio:.2f}")
        print(f"Thetas: {[r['theta_deg'] for r in growing]}")
        print(f"Magnitudes: {[r['magnitude'] for r in growing]}")

        if theta_range < 15:
            print("=> CONSTANT ANGLE — pure decay or invariant dipole")
        elif theta_range < 45:
            print("=> MODERATE ROTATION — dipole has weak internal dynamics")
        else:
            print("=> STRONG ROTATION — dipole has significant internal dynamics")

    # Save results
    output = {
        'experiment': 'dipolar_vector_scaling',
        'question': 'Does the dipolar vector (z_SR, z_L1) rotate with scale or only decay?',
        'n_shuffles': 200,
        'seed': 42,
        'results': results,
        'summary': {
            'growing_thetas': thetas,
            'growing_magnitudes': magnitudes,
            'theta_std': round(float(np.std(thetas)), 2) if thetas else None,
            'theta_range': round(float(max(thetas) - min(thetas)), 2) if thetas else None,
        }
    }

    outpath = os.path.join(os.path.dirname(__file__), 'data', 'dipolar_vector_scaling.json')
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {outpath}")

if __name__ == '__main__':
    main()
