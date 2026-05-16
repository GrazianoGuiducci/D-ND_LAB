#!/usr/bin/env python3
"""
Experiment: GUE/Poisson boundary in prime gaps vs Cramér null model.

Question: Is the transition from GUE-like to Poisson-like statistics in prime gaps
a structural feature of primes, or does it appear in any sequence with decreasing density?

Method:
1. Compute consecutive gap ratios <r> = min(g_i, g_{i+1}) / max(g_i, g_{i+1})
   for primes in sliding windows at different scales.
   - GUE (GOE in 1D): <r> ≈ 0.5307
   - Poisson: <r> ≈ 0.3863
2. Generate Cramér random primes: each integer n is "prime" with probability 1/ln(n).
3. Compare the <r> profile across scales for real primes vs Cramér model.
4. If both show the same transition → the boundary is trivial (density effect).
   If primes differ → the boundary carries structural information.

Null baseline: 20 Cramér realizations, report mean ± std.
"""

import numpy as np
from sympy import primerange
import json
from datetime import datetime

def gap_ratios(gaps):
    """Compute consecutive gap ratios min/max for a sequence of gaps."""
    if len(gaps) < 2:
        return np.array([])
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return r

def primes_in_window(start, end, primes_array):
    """Get primes in [start, end)."""
    idx_start = np.searchsorted(primes_array, start, side='left')
    idx_end = np.searchsorted(primes_array, end, side='left')
    return primes_array[idx_start:idx_end]

def cramer_random_primes(N_max, rng):
    """Generate Cramér random 'primes': each n>=2 is included with prob 1/ln(n)."""
    # For efficiency, work in blocks
    result = [2]
    n_vals = np.arange(3, N_max, 2)  # odd numbers only (like primes > 2)
    probs = 2.0 / np.log(n_vals)  # factor 2 because we only test odds
    probs = np.clip(probs, 0, 1)
    mask = rng.random(len(n_vals)) < probs
    result.extend(n_vals[mask].tolist())
    return np.array(result)

def analyze_windows(primes_array, windows):
    """Compute <r> for primes in each window."""
    results = []
    for (start, end) in windows:
        p = primes_in_window(start, end, primes_array)
        if len(p) < 50:
            results.append(np.nan)
            continue
        gaps = np.diff(p).astype(float)
        r = gap_ratios(gaps)
        results.append(np.mean(r))
    return np.array(results)

def main():
    print("=== GUE/Poisson Boundary: Primes vs Cramér Null Model ===\n")

    # Generate primes up to 10^7
    N_MAX = 10_000_000
    print(f"Generating primes up to {N_MAX:,}...")
    primes = np.array(list(primerange(2, N_MAX)))
    print(f"  Found {len(primes):,} primes\n")

    # Define windows: logarithmically spaced
    # Each window has ~2000 consecutive primes for statistical stability
    n_windows = 20
    window_centers = np.logspace(np.log10(1000), np.log10(N_MAX - 100000), n_windows).astype(int)
    window_half = 50000  # ±50K around center
    windows = [(max(2, c - window_half), c + window_half) for c in window_centers]

    # Analyze real primes
    print("Analyzing real primes across scales...")
    r_primes = analyze_windows(primes, windows)

    # Cramér null model: 20 realizations
    N_CRAMER = 20
    print(f"Generating {N_CRAMER} Cramér random prime sets...")
    rng = np.random.default_rng(42)
    r_cramer_all = []
    for i in range(N_CRAMER):
        cp = cramer_random_primes(N_MAX, rng)
        r_c = analyze_windows(cp, windows)
        r_cramer_all.append(r_c)
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{N_CRAMER} done")

    r_cramer_all = np.array(r_cramer_all)
    r_cramer_mean = np.nanmean(r_cramer_all, axis=0)
    r_cramer_std = np.nanstd(r_cramer_all, axis=0)

    # Reference values
    r_gue = 0.5307  # GOE (real symmetric) in 1D
    r_poisson = 0.3863

    # Print results
    print("\n" + "="*80)
    print(f"{'Window center':>15} | {'<r> primes':>10} | {'<r> Cramér':>12} | {'Δ':>8} | {'σ_Cramér':>8} | {'z-score':>8}")
    print("-"*80)

    z_scores = []
    for i, (start, end) in enumerate(windows):
        center = (start + end) // 2
        rp = r_primes[i]
        rc = r_cramer_mean[i]
        rs = r_cramer_std[i]
        delta = rp - rc
        z = delta / rs if rs > 0 else 0
        z_scores.append(z)
        print(f"{center:>15,} | {rp:>10.4f} | {rc:>10.4f}±{rs:.3f} | {delta:>+8.4f} | {rs:>8.4f} | {z:>+8.2f}")

    print("="*80)
    print(f"\nReference: <r>_GUE = {r_gue:.4f}, <r>_Poisson = {r_poisson:.4f}")

    # Summary statistics
    z_scores = np.array(z_scores)
    valid = ~np.isnan(z_scores)
    print(f"\nz-score summary (primes - Cramér) / σ_Cramér:")
    print(f"  mean z = {np.nanmean(z_scores):.3f}")
    print(f"  max |z| = {np.max(np.abs(z_scores[valid])):.3f}")
    print(f"  windows with |z| > 2: {np.sum(np.abs(z_scores[valid]) > 2)}/{np.sum(valid)}")

    # Key diagnostic: does <r> trend differ?
    print("\n--- Diagnostic: trend analysis ---")
    # Fit linear trend to <r> vs log(center)
    centers = np.array([(s+e)//2 for s,e in windows])
    log_centers = np.log10(centers)

    valid_p = ~np.isnan(r_primes)
    if np.sum(valid_p) > 3:
        coeff_p = np.polyfit(log_centers[valid_p], r_primes[valid_p], 1)
        coeff_c = np.polyfit(log_centers[valid_p], r_cramer_mean[valid_p], 1)
        print(f"  Primes: <r> = {coeff_p[0]:+.4f} * log10(n) + {coeff_p[1]:.4f}")
        print(f"  Cramér: <r> = {coeff_c[0]:+.4f} * log10(n) + {coeff_c[1]:.4f}")
        print(f"  Slope difference: {coeff_p[0] - coeff_c[0]:+.4f}")

        if abs(coeff_p[0] - coeff_c[0]) < 0.005:
            print("  → Slopes nearly identical: transition is a DENSITY EFFECT")
            structural = False
        else:
            print("  → Slopes differ: primes have STRUCTURAL content beyond density")
            structural = True
    else:
        print("  Not enough valid windows for trend analysis")
        structural = None

    # Where are primes relative to GUE/Poisson?
    print("\n--- Classification ---")
    for i, (start, end) in enumerate(windows):
        center = (start + end) // 2
        rp = r_primes[i]
        if np.isnan(rp):
            continue
        dist_gue = abs(rp - r_gue)
        dist_poi = abs(rp - r_poisson)
        label = "GUE" if dist_gue < dist_poi else "POISSON"
        margin = abs(dist_gue - dist_poi)
        if margin < 0.02:
            label = "BOUNDARY"
        print(f"  n~{center:>10,}: <r>={rp:.4f}  → {label}")

    # Save results
    result = {
        "experiment": "boundary_gue_poisson_cramer",
        "timestamp": datetime.now().isoformat(),
        "N_MAX": N_MAX,
        "n_primes": len(primes),
        "n_cramer_realizations": N_CRAMER,
        "reference": {"r_gue": r_gue, "r_poisson": r_poisson},
        "windows": [{"center": int((s+e)//2), "r_primes": float(r_primes[i]),
                      "r_cramer_mean": float(r_cramer_mean[i]),
                      "r_cramer_std": float(r_cramer_std[i]),
                      "z_score": float(z_scores[i]) if not np.isnan(z_scores[i]) else None}
                     for i, (s, e) in enumerate(windows)],
        "structural": structural,
        "z_mean": float(np.nanmean(z_scores)),
        "z_max_abs": float(np.max(np.abs(z_scores[valid]))),
        "slope_primes": float(coeff_p[0]) if np.sum(valid_p) > 3 else None,
        "slope_cramer": float(coeff_c[0]) if np.sum(valid_p) > 3 else None,
    }

    outpath = "/opt/MM_D-ND/tools/data/reports/exp_boundary_20260405_0825.json"
    with open(outpath, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to {outpath}")

    return result

if __name__ == "__main__":
    main()
