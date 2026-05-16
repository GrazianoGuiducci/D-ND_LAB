#!/usr/bin/env python3
"""
Experiment: Does prime excess correlation over null models GROW with scale?

Tension: BOUNDARY (0.7)
Claim: <r>_primes > <r>_Cramer always, and the gap GROWS with n.

Null models:
  1. Cramer: random integers with probability 1/ln(n)
  2. Shuffled gaps: same gap distribution, random order (destroys correlations)

Metric: gap ratio <r> = min(g_i, g_{i+1}) / max(g_i, g_{i+1})
  - GUE (correlated): <r> ~ 0.5307
  - Poisson (uncorrelated): <r> ~ 0.3863

If primes are truly more correlated than Cramer at ALL scales and the
excess grows, that's structural content beyond density.
"""

import numpy as np
from sympy import primerange
import json
from datetime import datetime

def gap_ratio(gaps):
    """Compute mean gap ratio <r> for a sequence of gaps."""
    r_vals = []
    for i in range(len(gaps) - 1):
        g1, g2 = gaps[i], gaps[i+1]
        if max(g1, g2) > 0:
            r_vals.append(min(g1, g2) / max(g1, g2))
    return np.mean(r_vals) if r_vals else np.nan

def cramer_model(n_start, n_end, seed=None):
    """Generate Cramer random primes: each integer n in [n_start, n_end]
    is 'prime' with probability 1/ln(n)."""
    rng = np.random.default_rng(seed)
    # Sample integers, keep each with prob 1/ln(n)
    ns = np.arange(max(n_start, 3), n_end + 1)
    probs = 1.0 / np.log(ns)
    mask = rng.random(len(ns)) < probs
    return ns[mask]

def shuffled_gaps_model(gaps, seed=None):
    """Shuffle gaps to destroy sequential correlation, recompute <r>."""
    rng = np.random.default_rng(seed)
    shuffled = gaps.copy()
    rng.shuffle(shuffled)
    return gap_ratio(shuffled)

def run_experiment():
    print("=" * 70)
    print("BOUNDARY EXCESS GROWTH EXPERIMENT")
    print("Does <r>_primes - <r>_null GROW with scale?")
    print("=" * 70)

    # Generate primes up to 10^8
    LIMIT = 10**8
    print(f"\nGenerating primes up to {LIMIT:.0e}...")
    primes = np.array(list(primerange(2, LIMIT)), dtype=np.int64)
    print(f"Total primes: {len(primes):,}")

    # Define windows: logarithmically spaced by prime index
    n_windows = 25
    # Use windows of ~50K primes each, at different positions
    window_size = 50000
    positions = np.logspace(np.log10(1000), np.log10(len(primes) - window_size - 1), n_windows).astype(int)

    n_cramer_trials = 10  # Monte Carlo trials per window

    results = []

    print(f"\n{'Window':>8} {'p_start':>12} {'p_end':>12} {'<r>_prime':>10} "
          f"{'<r>_Cramer':>10} {'<r>_shuf':>10} {'excess_C':>10} {'excess_S':>10} {'z_C':>8}")
    print("-" * 100)

    for i, pos in enumerate(positions):
        p_window = primes[pos:pos + window_size]
        gaps = np.diff(p_window)

        # Prime gap ratio
        r_prime = gap_ratio(gaps)

        # Cramer null: generate multiple trials in same range
        r_cramer_list = []
        for trial in range(n_cramer_trials):
            cramer_primes = cramer_model(int(p_window[0]), int(p_window[-1]), seed=42 + trial + i * 100)
            if len(cramer_primes) > 100:
                cramer_gaps = np.diff(cramer_primes)
                r_cramer_list.append(gap_ratio(cramer_gaps))
        r_cramer_mean = np.mean(r_cramer_list) if r_cramer_list else np.nan
        r_cramer_std = np.std(r_cramer_list) if len(r_cramer_list) > 1 else np.nan

        # Shuffled gaps null
        r_shuf_list = []
        for trial in range(n_cramer_trials):
            r_shuf_list.append(shuffled_gaps_model(gaps, seed=42 + trial))
        r_shuf_mean = np.mean(r_shuf_list)
        r_shuf_std = np.std(r_shuf_list) if len(r_shuf_list) > 1 else np.nan

        # Excess and z-score vs Cramer
        excess_c = r_prime - r_cramer_mean
        excess_s = r_prime - r_shuf_mean
        z_c = excess_c / r_cramer_std if r_cramer_std > 0 else np.nan

        results.append({
            "window_idx": i,
            "prime_index_start": int(pos),
            "p_start": int(p_window[0]),
            "p_end": int(p_window[-1]),
            "r_prime": float(r_prime),
            "r_cramer_mean": float(r_cramer_mean),
            "r_cramer_std": float(r_cramer_std),
            "r_shuffled_mean": float(r_shuf_mean),
            "r_shuffled_std": float(r_shuf_std),
            "excess_cramer": float(excess_c),
            "excess_shuffled": float(excess_s),
            "z_cramer": float(z_c),
        })

        print(f"{i:>8} {int(p_window[0]):>12,} {int(p_window[-1]):>12,} "
              f"{r_prime:>10.6f} {r_cramer_mean:>10.6f} {r_shuf_mean:>10.6f} "
              f"{excess_c:>+10.6f} {excess_s:>+10.6f} {z_c:>8.2f}")

    # Summary analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    excesses_c = [r["excess_cramer"] for r in results]
    excesses_s = [r["excess_shuffled"] for r in results]
    z_scores = [r["z_cramer"] for r in results]
    scales = [np.log10(r["p_start"]) for r in results]

    # Linear regression: excess vs log10(p_start)
    from numpy.polynomial import polynomial as P
    coeffs_c = np.polyfit(scales, excesses_c, 1)
    coeffs_s = np.polyfit(scales, excesses_s, 1)
    coeffs_z = np.polyfit(scales, z_scores, 1)

    print(f"\nExcess over Cramer:")
    print(f"  Mean: {np.mean(excesses_c):+.6f}")
    print(f"  Range: [{min(excesses_c):+.6f}, {max(excesses_c):+.6f}]")
    print(f"  Slope (vs log10 p): {coeffs_c[0]:+.6f}  {'GROWING' if coeffs_c[0] > 0 else 'SHRINKING'}")
    print(f"  Sign-consistent: {sum(1 for e in excesses_c if e > 0)}/{len(excesses_c)}")

    print(f"\nExcess over Shuffled:")
    print(f"  Mean: {np.mean(excesses_s):+.6f}")
    print(f"  Range: [{min(excesses_s):+.6f}, {max(excesses_s):+.6f}]")
    print(f"  Slope (vs log10 p): {coeffs_s[0]:+.6f}  {'GROWING' if coeffs_s[0] > 0 else 'SHRINKING'}")
    print(f"  Sign-consistent: {sum(1 for e in excesses_s if e > 0)}/{len(excesses_s)}")

    print(f"\nZ-score (vs Cramer):")
    print(f"  Mean: {np.mean(z_scores):+.2f}")
    print(f"  Slope (vs log10 p): {coeffs_z[0]:+.4f}")
    print(f"  All significant (|z|>2): {sum(1 for z in z_scores if abs(z) > 2)}/{len(z_scores)}")

    # Key question: do primes approach GUE or Poisson at large scale?
    GUE_R = 0.5307
    POISSON_R = 0.3863
    r_large = results[-1]["r_prime"]
    r_small = results[0]["r_prime"]
    print(f"\n<r> at smallest scale (p~{results[0]['p_start']:,}): {r_small:.6f}")
    print(f"<r> at largest scale  (p~{results[-1]['p_start']:,}): {r_large:.6f}")
    print(f"GUE reference: {GUE_R}")
    print(f"Poisson reference: {POISSON_R}")
    print(f"Position: {'closer to GUE' if abs(r_large - GUE_R) < abs(r_large - POISSON_R) else 'closer to Poisson'}")

    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    all_positive = all(e > 0 for e in excesses_c)
    slope_positive = coeffs_c[0] > 0
    slope_significant = abs(coeffs_c[0]) > 0.001  # threshold

    if all_positive and slope_positive and slope_significant:
        verdict = "CONFIRMED: Excess is positive at all scales AND grows with scale"
    elif all_positive and not slope_positive:
        verdict = "PARTIAL: Excess is positive everywhere but does NOT grow (may shrink)"
    elif all_positive:
        verdict = "PARTIAL: Excess is positive everywhere but slope is negligible"
    else:
        verdict = "FALSIFIED: Excess is not consistently positive across scales"

    print(f"\n  {verdict}")
    print(f"  Slope excess_Cramer: {coeffs_c[0]:+.6f} per decade")
    print(f"  Slope excess_Shuffled: {coeffs_s[0]:+.6f} per decade")

    # Check META tension: are we testing tautologies?
    # The shuffled-gaps test is the key anti-tautology check:
    # if <r>_prime == <r>_shuffled, then the gap-ratio statistic
    # is just reflecting the gap distribution, not correlations.
    meta_tautology = abs(np.mean(excesses_s)) < 0.001
    print(f"\n  META check (anti-tautology):")
    print(f"    <r>_prime - <r>_shuffled mean = {np.mean(excesses_s):+.6f}")
    if meta_tautology:
        print(f"    WARNING: Gap ratio may be reflecting distribution, not correlation!")
    else:
        print(f"    OK: Gap ratio captures genuine sequential correlation in primes")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "boundary_excess_growth",
        "tension_id": "BOUNDARY",
        "parameters": {
            "limit": LIMIT,
            "n_windows": n_windows,
            "window_size": window_size,
            "n_cramer_trials": n_cramer_trials,
        },
        "results": results,
        "summary": {
            "excess_cramer_mean": float(np.mean(excesses_c)),
            "excess_cramer_slope": float(coeffs_c[0]),
            "excess_shuffled_mean": float(np.mean(excesses_s)),
            "excess_shuffled_slope": float(coeffs_s[0]),
            "z_cramer_mean": float(np.mean(z_scores)),
            "z_cramer_slope": float(coeffs_z[0]),
            "all_positive_cramer": bool(all_positive),
            "slope_growing": bool(slope_positive),
            "meta_tautology_risk": bool(meta_tautology),
        },
        "verdict": verdict,
    }

    out_path = "/opt/MM_D-ND/tools/data/reports/exp_boundary_growth_20260405_0914.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    return output

if __name__ == "__main__":
    run_experiment()
