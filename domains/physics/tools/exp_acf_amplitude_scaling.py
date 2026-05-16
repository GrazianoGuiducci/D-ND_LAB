#!/usr/bin/env python3
"""
exp_acf_amplitude_scaling.py — Measure how the 1/k ACF amplitude A scales with prime size.

Connects: ACF_1K_LAW (A~0.037 overall) + POISSON_CONVERGENCE (p*~10^14) + BOUNDARY (drift)

Question: acf(k) = -A(p)/k. How does A(p) depend on p? If A → 0 logarithmically,
at what p* does the anti-correlation vanish (Poisson)?

Usage:
    python tools/exp_acf_amplitude_scaling.py [--n_primes N] [--n_windows W] [--max_lag L]
"""
import numpy as np
from sympy import primerange
import argparse
from scipy.optimize import curve_fit
from scipy.stats import linregress

def compute_acf(gaps, max_lag):
    """Autocorrelation of gaps at lags 1..max_lag, normalized by variance."""
    n = len(gaps)
    mean = np.mean(gaps)
    var = np.var(gaps)
    if var == 0:
        return np.zeros(max_lag)
    centered = gaps - mean
    acf = np.array([np.mean(centered[:n-k] * centered[k:]) / var for k in range(1, max_lag + 1)])
    return acf

def fit_1k_law(acf_values, lags):
    """Fit acf(k) = -A/k. Returns A, R2."""
    neg_acf = -acf_values  # should be positive if anti-correlated
    # fit A in: -acf(k) = A/k => neg_acf = A/k
    mask = lags > 0
    x = 1.0 / lags[mask]
    y = neg_acf[mask]
    # linear fit through origin: y = A * x
    A = np.sum(x * y) / np.sum(x * x)
    ss_res = np.sum((y - A * x) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    R2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return A, R2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=6_000_000)
    parser.add_argument('--n_windows', type=int, default=25)
    parser.add_argument('--max_lag', type=int, default=20)
    parser.add_argument('--window_size', type=int, default=50_000)
    parser.add_argument('--n_surrogates', type=int, default=10)
    args = parser.parse_args()

    print(f"Generating primes up to index ~{args.n_primes}...")
    # estimate upper bound
    import math
    upper = int(args.n_primes * (math.log(args.n_primes) + math.log(math.log(args.n_primes)) + 2))
    primes = np.array(list(primerange(2, upper)))[:args.n_primes]
    gaps = np.diff(primes).astype(float)
    print(f"Got {len(primes)} primes, {len(gaps)} gaps. Max prime: {primes[-1]:.3e}")

    # log-spaced windows
    n_gaps = len(gaps)
    starts = np.unique(np.logspace(0, np.log10(n_gaps - args.window_size), args.n_windows).astype(int))
    starts = starts[starts + args.window_size <= n_gaps]

    lags = np.arange(1, args.max_lag + 1, dtype=float)
    results = []

    print(f"\n{'Window':>6} {'p_center':>12} {'ln(p)':>8} {'A_prime':>10} {'R2':>8} {'A_shuf':>10} {'z_score':>8}")
    print("-" * 75)

    for i, s in enumerate(starts):
        window_gaps = gaps[s:s + args.window_size]
        window_primes = primes[s:s + args.window_size]
        p_center = np.median(window_primes)
        ln_p = np.log(p_center)

        # Prime ACF
        acf_prime = compute_acf(window_gaps, args.max_lag)
        A_prime, R2_prime = fit_1k_law(acf_prime, lags)

        # Surrogate ACFs (shuffled)
        A_surrogates = []
        for _ in range(args.n_surrogates):
            shuf = np.random.permutation(window_gaps)
            acf_shuf = compute_acf(shuf, args.max_lag)
            A_s, _ = fit_1k_law(acf_shuf, lags)
            A_surrogates.append(A_s)

        A_shuf_mean = np.mean(A_surrogates)
        A_shuf_std = np.std(A_surrogates) if np.std(A_surrogates) > 0 else 1e-10
        z = (A_prime - A_shuf_mean) / A_shuf_std

        results.append({
            'window': i,
            'start': s,
            'p_center': p_center,
            'ln_p': ln_p,
            'A_prime': A_prime,
            'R2': R2_prime,
            'A_shuf_mean': A_shuf_mean,
            'A_shuf_std': A_shuf_std,
            'z_score': z,
            'acf1': acf_prime[0],
        })

        print(f"{i:>6d} {p_center:>12.0f} {ln_p:>8.2f} {A_prime:>10.6f} {R2_prime:>8.4f} {A_shuf_mean:>10.6f} {z:>8.1f}")

    # Fit A(ln p) = a + b * ln(p)
    ln_ps = np.array([r['ln_p'] for r in results])
    As = np.array([r['A_prime'] for r in results])
    zs = np.array([r['z_score'] for r in results])

    slope, intercept, r_value, p_value, std_err = linregress(ln_ps, As)
    R2_fit = r_value ** 2

    print(f"\n{'='*75}")
    print(f"Linear fit: A(ln p) = {intercept:.6f} + {slope:.6f} * ln(p)")
    print(f"R² = {R2_fit:.4f}, p = {p_value:.2e}")
    print(f"Slope = {slope:.6f} ± {std_err:.6f}")

    # Predict crossover: A = 0 => ln(p*) = -intercept/slope
    if slope < 0:
        ln_p_star = -intercept / slope
        p_star = np.exp(ln_p_star)
        log10_p_star = ln_p_star / np.log(10)
        print(f"\nPoisson crossover (A=0): ln(p*) = {ln_p_star:.1f}, p* ~ 10^{log10_p_star:.1f}")
    else:
        print(f"\nSlope is non-negative ({slope:.6f}) — no Poisson crossover predicted")
        ln_p_star = None

    # Also fit power-law: A(p) = A0 * p^(-gamma)
    # => A(ln p) = ln(A0) - gamma * ln(p)  on log A vs ln(p)
    pos_mask = As > 0
    if np.sum(pos_mask) > 5:
        slope_log, intercept_log, r_log, p_log, se_log = linregress(ln_ps[pos_mask], np.log(As[pos_mask]))
        print(f"\nPower-law fit: A(p) = {np.exp(intercept_log):.4f} * p^({slope_log:.4f})")
        print(f"R² = {r_log**2:.4f}, p = {p_log:.2e}")

    # Consistency check: acf1 vs A (should be correlated since acf1 = -A)
    acf1s = np.array([r['acf1'] for r in results])
    corr_acf1_A = np.corrcoef(acf1s, As)[0, 1]
    print(f"\nConsistency: corr(acf1, A) = {corr_acf1_A:.4f} (expect ~ -1)")

    # Summary stats
    print(f"\nz-scores: min={np.min(zs):.1f}, max={np.max(zs):.1f}, mean={np.mean(zs):.1f}")
    print(f"All z > 2? {'YES' if np.all(zs > 2) else 'NO'} (count z>2: {np.sum(zs > 2)}/{len(zs)})")
    print(f"\nA range: {np.min(As):.6f} to {np.max(As):.6f}")
    print(f"A at smallest primes: {As[0]:.6f}")
    print(f"A at largest primes: {As[-1]:.6f}")
    print(f"Ratio: {As[-1]/As[0]:.4f}")

    return results, slope, intercept, R2_fit, ln_p_star

if __name__ == '__main__':
    main()
