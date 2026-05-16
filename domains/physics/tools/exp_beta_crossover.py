#!/usr/bin/env python3
"""
exp_beta_crossover.py — Beta-ensemble crossover vs prime niche.

The spectral landscape is 2D: (<r>, acf1). Primes sit at (~0.45, ~-0.07).
Question: Does the standard beta-ensemble (Dyson beta 0->inf) trace a curve
that passes through the prime niche, or do primes lie OFF the universal curve?

Method: Dumitriu-Edelman tridiagonal model gives exact beta-Hermite ensemble
for any beta > 0. Sweep beta from 0.01 to 10, measure (<r>, acf1) at each.
Plot the curve and mark where primes fall.

If primes are ON the curve: they're just beta~0.3 or similar.
If primes are OFF: the gap autocorrelation (acf1) is an independent degree
of freedom not captured by Dyson beta. The 2D landscape is real.

Usage:
    python exp_beta_crossover.py [--N 2000] [--betas 30] [--surrogates 10]
"""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import gamma as gamma_fn
import json, os, sys
from datetime import datetime

N_DEFAULT = 2000   # matrix size (= number of spacings)
N_BETAS = 30       # number of beta values to sweep
N_SURROGATES = 10  # shuffled surrogates per point


# --- Observables (same as exp_spectral_2d.py) ---

def ratio_statistic(spacings):
    s = spacings[spacings > 0]
    if len(s) < 3:
        return np.nan
    r = np.minimum(s[:-1], s[1:]) / np.maximum(s[:-1], s[1:])
    return np.mean(r)

def gap_acf1(spacings):
    s = spacings - np.mean(spacings)
    if np.var(spacings) < 1e-15:
        return np.nan
    c0 = np.mean(s ** 2)
    c1 = np.mean(s[:-1] * s[1:])
    return c1 / c0 if c0 > 0 else np.nan

def gap_acf2(spacings):
    """Lag-2 autocorrelation."""
    s = spacings - np.mean(spacings)
    if np.var(spacings) < 1e-15:
        return np.nan
    c0 = np.mean(s ** 2)
    c2 = np.mean(s[:-2] * s[2:])
    return c2 / c0 if c0 > 0 else np.nan

def number_variance(spacings, L=2.0):
    """Number variance Sigma^2(L): variance of count in window of length L."""
    cumsum = np.cumsum(spacings)
    total = cumsum[-1]
    n_windows = min(2000, len(spacings) // 2)
    starts = np.random.uniform(0, total - L, n_windows)
    counts = []
    for s in starts:
        n = np.searchsorted(cumsum, s + L) - np.searchsorted(cumsum, s)
        counts.append(n)
    counts = np.array(counts)
    return float(np.var(counts))


# --- Dumitriu-Edelman tridiagonal beta-ensemble ---

def beta_ensemble_spacings(N, beta):
    """
    Generate eigenvalue spacings from the beta-Hermite ensemble
    using the Dumitriu-Edelman tridiagonal model (2002).

    H_ij tridiagonal with:
      diagonal: N(0, 2) / sqrt(2)
      off-diagonal: chi_{(N-i)*beta} / sqrt(2)  (i = 1..N-1)

    This gives the EXACT joint density proportional to
    prod|x_i - x_j|^beta * exp(-beta/4 * sum x_i^2).
    """
    # Diagonal: standard normal
    diag = np.random.randn(N)

    # Off-diagonal: chi_{k*beta} for k = N-1, N-2, ..., 1
    off_diag = np.zeros(N - 1)
    for i in range(N - 1):
        k = N - 1 - i  # k goes from N-1 down to 1
        df = k * beta   # degrees of freedom for chi distribution
        # chi_df = sqrt(chi2_df) where chi2_df ~ Gamma(df/2, 2)
        off_diag[i] = np.sqrt(np.random.gamma(df / 2, 2.0))

    # Construct tridiagonal matrix and diagonalize
    from scipy.linalg import eigvalsh_tridiagonal
    eigs = eigvalsh_tridiagonal(diag, off_diag)

    # Sort and compute spacings
    eigs = np.sort(eigs)
    spacings = np.diff(eigs)

    # Unfold: divide by local mean density
    w = max(10, N // 50)
    kernel = np.ones(w) / w
    local_mean = np.convolve(spacings, kernel, mode='same')
    local_mean[local_mean < 1e-15] = 1e-15
    s = spacings / local_mean

    # Trim edges (unfolding artifacts)
    trim = N // 20
    return s[trim:-trim]


# --- Prime gaps ---

def gen_primes_multiscale(scales=None):
    """Generate prime gap statistics at multiple scales."""
    if scales is None:
        scales = [5000, 20000, 50000]

    # Sieve enough primes
    max_n = max(scales) + 1000
    limit = int(max_n * 20 * np.log(max(max_n * 20, 100)))
    limit = max(limit, 2000000)
    sieve = np.ones(limit, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    primes = np.where(sieve)[0].astype(float)

    results = []
    for n in scales:
        if n + 1 > len(primes):
            continue
        p = primes[:n + 1]
        gaps = np.diff(p)
        # Unfold
        w = min(50, len(gaps) // 5)
        kernel = np.ones(w) / w
        local_mean = np.convolve(gaps, kernel, mode='same')
        local_mean[local_mean < 0.1] = 1.0
        spacings = gaps / local_mean

        r = ratio_statistic(spacings)
        acf = gap_acf1(spacings)
        acf2_val = gap_acf2(spacings)

        # Shuffled null for z-score
        r_s, acf_s = [], []
        for _ in range(N_SURROGATES):
            sh = spacings.copy()
            np.random.shuffle(sh)
            r_s.append(ratio_statistic(sh))
            acf_s.append(gap_acf1(sh))

        z_acf = (acf - np.mean(acf_s)) / max(np.std(acf_s), 1e-10)

        results.append({
            "n": n,
            "p_max": float(p[-1]),
            "r": float(r),
            "acf1": float(acf),
            "acf2": float(acf2_val),
            "z_acf1": float(z_acf),
        })
    return results


# --- Main experiment ---

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--N", type=int, default=N_DEFAULT,
                        help="Matrix size for beta-ensemble")
    parser.add_argument("--betas", type=int, default=N_BETAS,
                        help="Number of beta values to sweep")
    parser.add_argument("--surrogates", type=int, default=N_SURROGATES)
    args = parser.parse_args()

    N = args.N
    n_betas = args.betas
    NS = args.surrogates

    print(f"=== Beta-Ensemble Crossover vs Prime Niche ===")
    print(f"Matrix N={N}, beta sweep: {n_betas} values, surrogates={NS}\n")

    # Sweep beta from near-Poisson (0.01) to beyond-GUE (10)
    betas = np.concatenate([
        np.linspace(0.05, 0.5, n_betas // 3),      # fine resolution near Poisson
        np.linspace(0.6, 2.0, n_betas // 3),         # through GOE-GUE
        np.linspace(2.5, 8.0, n_betas - 2*(n_betas//3)),  # beyond GUE
    ])

    print(f"{'beta':>6} {'<r>':>7} {'acf1':>8} {'acf2':>8} {'Sig2(2)':>8}")
    print("-" * 45)

    beta_results = []
    for beta in betas:
        try:
            spacings = beta_ensemble_spacings(N, beta)
            spacings = spacings[np.isfinite(spacings) & (spacings > 0)]

            r = ratio_statistic(spacings)
            acf = gap_acf1(spacings)
            acf2_val = gap_acf2(spacings)
            nvar = number_variance(spacings, L=2.0)

            # Shuffled null
            acf_shuf = []
            for _ in range(NS):
                sh = spacings.copy()
                np.random.shuffle(sh)
                acf_shuf.append(gap_acf1(sh))
            z_acf = (acf - np.mean(acf_shuf)) / max(np.std(acf_shuf), 1e-10)

            res = {
                "beta": float(beta),
                "n_spacings": int(len(spacings)),
                "r": float(r),
                "acf1": float(acf),
                "acf2": float(acf2_val),
                "nvar_2": float(nvar),
                "z_acf1": float(z_acf),
            }
            beta_results.append(res)
            print(f"{beta:6.3f} {r:7.4f} {acf:8.4f} {acf2_val:8.4f} {nvar:8.4f}")

        except Exception as e:
            print(f"{beta:6.3f} ERROR: {e}")

    # --- Primes at multiple scales ---
    print(f"\n=== Prime Gaps (multi-scale) ===")
    print(f"{'n_primes':>10} {'p_max':>12} {'<r>':>7} {'acf1':>8} {'acf2':>8} {'z_acf1':>8}")
    print("-" * 60)

    prime_results = gen_primes_multiscale([5000, 20000, 50000, 100000])
    for pr in prime_results:
        print(f"{pr['n']:10d} {pr['p_max']:12.0f} {pr['r']:7.4f} {pr['acf1']:8.4f} "
              f"{pr['acf2']:8.4f} {pr['z_acf1']:8.1f}")

    # --- Analysis: does the beta-curve pass through primes? ---
    print(f"\n=== Analysis: Beta-curve vs Primes ===")

    if not beta_results or not prime_results:
        print("Insufficient data for analysis.")
        return

    # Use the largest prime scale as reference
    prime_ref = prime_results[-1]
    pr_r = prime_ref["r"]
    pr_acf1 = prime_ref["acf1"]

    print(f"Prime reference (n={prime_ref['n']}): <r>={pr_r:.4f}, acf1={pr_acf1:.4f}")

    # Find closest beta-ensemble point to primes in (<r>, acf1) plane
    min_dist = float('inf')
    closest = None
    for br in beta_results:
        dr = br["r"] - pr_r
        da = br["acf1"] - pr_acf1
        d = np.sqrt(dr**2 + da**2)
        if d < min_dist:
            min_dist = d
            closest = br

    if closest:
        print(f"Closest beta-ensemble: beta={closest['beta']:.3f}, "
              f"<r>={closest['r']:.4f}, acf1={closest['acf1']:.4f}, "
              f"distance={min_dist:.4f}")

    # Find beta that matches <r> of primes
    best_r_match = None
    best_r_diff = float('inf')
    for br in beta_results:
        diff = abs(br["r"] - pr_r)
        if diff < best_r_diff:
            best_r_diff = diff
            best_r_match = br

    if best_r_match:
        acf1_at_matched_r = best_r_match["acf1"]
        acf1_gap = pr_acf1 - acf1_at_matched_r
        print(f"\nBeta matching primes' <r>: beta={best_r_match['beta']:.3f}")
        print(f"  beta-ensemble at this beta: <r>={best_r_match['r']:.4f}, acf1={acf1_at_matched_r:.4f}")
        print(f"  primes:                     <r>={pr_r:.4f}, acf1={pr_acf1:.4f}")
        print(f"  acf1 gap: {acf1_gap:+.4f}")

        if abs(acf1_gap) > 0.03:
            print(f"\n  --> PRIMES ARE OFF THE BETA CURVE.")
            print(f"  At matched <r>, the beta-ensemble has acf1={acf1_at_matched_r:.4f}")
            print(f"  but primes have acf1={pr_acf1:.4f}.")
            print(f"  The gap autocorrelation is NOT determined by <r> alone.")
            print(f"  Primes need TWO parameters: repulsion strength + ordering strength.")
        else:
            print(f"\n  --> Primes are ON or near the beta curve.")
            print(f"  The beta-ensemble at beta={best_r_match['beta']:.3f} reproduces both")
            print(f"  <r> and acf1 of primes. The 2D landscape collapses to 1D for primes.")

    # The beta-ensemble curve: extract <r>(beta) and acf1(beta)
    print(f"\n=== Beta-ensemble curve: acf1 vs <r> ===")
    print(f"{'beta':>6} {'<r>':>7} {'acf1':>8} | note")
    print("-" * 50)
    for br in beta_results:
        note = ""
        if abs(br["r"] - pr_r) < 0.01:
            note = " <-- matches prime <r>"
        if abs(br["r"] - 0.386) < 0.01:
            note = " <-- Poisson"
        if abs(br["r"] - 0.536) < 0.01:
            note = " <-- GOE"
        if abs(br["r"] - 0.603) < 0.01:
            note = " <-- GUE"
        print(f"{br['beta']:6.3f} {br['r']:7.4f} {br['acf1']:8.4f} |{note}")

    # --- Perpendicular distance: how far are primes from the curve? ---
    if len(beta_results) >= 3:
        curve_r = np.array([br["r"] for br in beta_results])
        curve_acf1 = np.array([br["acf1"] for br in beta_results])

        # Find perpendicular distance from prime point to the piecewise-linear curve
        min_perp = float('inf')
        for i in range(len(curve_r) - 1):
            # Segment from point i to point i+1
            ax, ay = curve_r[i], curve_acf1[i]
            bx, by = curve_r[i+1], curve_acf1[i+1]
            # Project prime point onto segment
            dx, dy = bx - ax, by - ay
            seg_len2 = dx*dx + dy*dy
            if seg_len2 < 1e-20:
                continue
            t = max(0, min(1, ((pr_r - ax)*dx + (pr_acf1 - ay)*dy) / seg_len2))
            proj_x = ax + t * dx
            proj_y = ay + t * dy
            d = np.sqrt((pr_r - proj_x)**2 + (pr_acf1 - proj_y)**2)
            if d < min_perp:
                min_perp = d

        print(f"\nPerpendicular distance from primes to beta-curve: {min_perp:.4f}")

        # Compare with typical scatter
        # Estimate scatter by computing distances between consecutive points
        scatter = []
        for br in beta_results:
            # Distance from this point to a smoothed version
            pass

        # Simple: compare with the <r> range of the curve
        r_range = max(curve_r) - min(curve_r)
        relative_dist = min_perp / r_range
        print(f"Relative distance (vs <r> range): {relative_dist:.3f}")

        if relative_dist > 0.05:
            print(f"  --> Primes are SIGNIFICANTLY off the universal curve.")
        else:
            print(f"  --> Primes are within noise of the universal curve.")

    # --- Save ---
    outpath = os.path.join(os.path.dirname(__file__), "data", "exp_beta_crossover.json")
    with open(outpath, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "N_matrix": N,
            "n_betas": n_betas,
            "surrogates": NS,
            "beta_curve": beta_results,
            "primes": prime_results,
            "analysis": {
                "prime_ref_n": prime_ref["n"],
                "prime_r": pr_r,
                "prime_acf1": pr_acf1,
                "closest_beta": closest["beta"] if closest else None,
                "closest_distance": float(min_dist),
                "r_matched_beta": best_r_match["beta"] if best_r_match else None,
                "acf1_at_matched_r": float(acf1_at_matched_r) if best_r_match else None,
                "acf1_gap": float(acf1_gap) if best_r_match else None,
            },
        }, f, indent=2)
    print(f"\nSaved: {outpath}")


if __name__ == "__main__":
    main()
