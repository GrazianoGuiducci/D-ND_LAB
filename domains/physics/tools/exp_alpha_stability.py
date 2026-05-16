#!/usr/bin/env python3
"""
exp_alpha_stability.py — Test whether the power-law exponent alpha in
acf(k) ~ -A * k^(-alpha) remains stable at 1.00 across prime scales,
or drifts during the Poisson crossover.

Reusable: accepts --n_primes, --n_windows, --n_surrogates, --max_lag.

Null baseline: shuffled gaps within each window.
"""

import argparse
import numpy as np
from scipy.optimize import curve_fit
from sympy import primerange


def get_primes(n):
    """Get first n primes."""
    # Estimate upper bound using prime counting function approximation
    if n < 10:
        upper = 30
    else:
        upper = int(n * (np.log(n) + np.log(np.log(n)) + 2))
    primes = list(primerange(2, upper))
    while len(primes) < n:
        upper = int(upper * 1.5)
        primes = list(primerange(2, upper))
    return np.array(primes[:n])


def compute_acf(gaps, max_lag):
    """Compute normalized autocorrelation for lags 1..max_lag."""
    n = len(gaps)
    mean = np.mean(gaps)
    var = np.var(gaps)
    if var == 0:
        return np.zeros(max_lag)
    acf = np.zeros(max_lag)
    centered = gaps - mean
    for k in range(1, max_lag + 1):
        acf[k - 1] = np.mean(centered[:-k] * centered[k:]) / var
    return acf


def fit_power_law(lags, acf_values):
    """Fit acf(k) = -A * k^(-alpha) to negative ACF values.
    Returns (A, alpha, R2) or None if fit fails."""
    # Use only negative values (the anti-correlation signal)
    mask = acf_values < 0
    if np.sum(mask) < 3:
        return None

    k = lags[mask]
    y = -acf_values[mask]  # Make positive for fitting

    # Fit in log-log space: log(y) = log(A) - alpha * log(k)
    log_k = np.log(k)
    log_y = np.log(y)

    # Linear regression
    coeffs = np.polyfit(log_k, log_y, 1)
    alpha = -coeffs[0]
    A = np.exp(coeffs[1])

    # R^2
    predicted = coeffs[1] + coeffs[0] * log_k
    ss_res = np.sum((log_y - predicted) ** 2)
    ss_tot = np.sum((log_y - np.mean(log_y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return A, alpha, r2


def main():
    parser = argparse.ArgumentParser(description="Alpha exponent stability across prime scales")
    parser.add_argument("--n_primes", type=int, default=6_000_000, help="Total primes to use")
    parser.add_argument("--n_windows", type=int, default=12, help="Number of log-spaced windows")
    parser.add_argument("--window_size", type=int, default=100_000, help="Gaps per window")
    parser.add_argument("--max_lag", type=int, default=50, help="Max ACF lag")
    parser.add_argument("--n_surrogates", type=int, default=10, help="Shuffled surrogates per window")
    args = parser.parse_args()

    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    gaps = np.diff(primes).astype(float)
    n_gaps = len(gaps)
    print(f"Got {n_gaps:,} gaps. p_max = {primes[-1]:,}")

    # Log-spaced window starts
    max_start = n_gaps - args.window_size
    if max_start < args.window_size:
        print("ERROR: not enough primes for requested windows")
        return

    starts = np.unique(np.logspace(
        np.log10(1000),
        np.log10(max_start),
        args.n_windows
    ).astype(int))

    lags = np.arange(1, args.max_lag + 1)

    print(f"\n{'Window':>8} {'p_center':>14} {'ln(p)':>8} {'A':>8} {'alpha':>8} {'R2':>8} | {'A_shuf':>8} {'alpha_shuf':>8}")
    print("-" * 95)

    results = []

    for start in starts:
        window_gaps = gaps[start:start + args.window_size]
        p_center = primes[start + args.window_size // 2]
        ln_p = np.log(float(p_center))

        # Compute ACF
        acf = compute_acf(window_gaps, args.max_lag)

        # Fit power law
        fit = fit_power_law(lags, acf)
        if fit is None:
            continue
        A, alpha, r2 = fit

        # Shuffled surrogates
        A_shuf_list = []
        alpha_shuf_list = []
        for _ in range(args.n_surrogates):
            shuf = window_gaps.copy()
            np.random.shuffle(shuf)
            acf_shuf = compute_acf(shuf, args.max_lag)
            fit_shuf = fit_power_law(lags, acf_shuf)
            if fit_shuf is not None:
                A_shuf_list.append(fit_shuf[0])
                alpha_shuf_list.append(fit_shuf[1])

        A_shuf_mean = np.mean(A_shuf_list) if A_shuf_list else 0
        alpha_shuf_mean = np.mean(alpha_shuf_list) if alpha_shuf_list else 0

        row = {
            'start': start,
            'p_center': int(p_center),
            'ln_p': ln_p,
            'A': A,
            'alpha': alpha,
            'r2': r2,
            'A_shuf': A_shuf_mean,
            'alpha_shuf': alpha_shuf_mean,
        }
        results.append(row)

        print(f"{start:>8d} {int(p_center):>14,} {ln_p:>8.2f} {A:>8.4f} {alpha:>8.3f} {r2:>8.3f} | {A_shuf_mean:>8.4f} {alpha_shuf_mean:>8.3f}")

    if len(results) < 3:
        print("\nNot enough valid windows for trend analysis.")
        return

    # Trend analysis: alpha vs ln(p)
    ln_ps = np.array([r['ln_p'] for r in results])
    alphas = np.array([r['alpha'] for r in results])
    As = np.array([r['A'] for r in results])
    r2s = np.array([r['r2'] for r in results])

    # Linear fit: alpha(ln p) = a + b * ln(p)
    coeffs_alpha = np.polyfit(ln_ps, alphas, 1)
    pred_alpha = np.polyval(coeffs_alpha, ln_ps)
    ss_res = np.sum((alphas - pred_alpha) ** 2)
    ss_tot = np.sum((alphas - np.mean(alphas)) ** 2)
    r2_alpha_fit = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    # Linear fit: A(ln p) = a + b * ln(p)
    coeffs_A = np.polyfit(ln_ps, As, 1)
    pred_A = np.polyval(coeffs_A, ln_ps)
    ss_res_A = np.sum((As - pred_A) ** 2)
    ss_tot_A = np.sum((As - np.mean(As)) ** 2)
    r2_A_fit = 1 - ss_res_A / ss_tot_A if ss_tot_A > 0 else 0

    print(f"\n=== TREND ANALYSIS ===")
    print(f"alpha mean = {np.mean(alphas):.4f} +/- {np.std(alphas):.4f}")
    print(f"alpha range = [{np.min(alphas):.4f}, {np.max(alphas):.4f}]")
    print(f"alpha(ln p) = {coeffs_alpha[1]:.4f} + {coeffs_alpha[0]:.6f} * ln(p)")
    print(f"  slope = {coeffs_alpha[0]:.6f}, R2 = {r2_alpha_fit:.4f}")
    print(f"  alpha drift per decade of p: {coeffs_alpha[0] * np.log(10):.4f}")
    print()
    print(f"A mean = {np.mean(As):.5f} +/- {np.std(As):.5f}")
    print(f"A(ln p) = {coeffs_A[1]:.5f} + {coeffs_A[0]:.7f} * ln(p)")
    print(f"  slope = {coeffs_A[0]:.7f}, R2 = {r2_A_fit:.4f}")
    print(f"  A -> 0 at ln(p) = {-coeffs_A[1] / coeffs_A[0]:.1f} => p* = {np.exp(-coeffs_A[1] / coeffs_A[0]):.2e}")
    print()
    print(f"R2 of power-law fits: mean = {np.mean(r2s):.4f}, min = {np.min(r2s):.4f}")

    # Is alpha stable? Compare drift to measurement noise
    alpha_std = np.std(alphas)
    total_drift = abs(coeffs_alpha[0]) * (ln_ps[-1] - ln_ps[0])
    print(f"\nStability test:")
    print(f"  Total alpha drift across data = {total_drift:.4f}")
    print(f"  Alpha scatter (std) = {alpha_std:.4f}")
    print(f"  Drift / scatter ratio = {total_drift / alpha_std:.2f}" if alpha_std > 0 else "  Scatter = 0")

    if total_drift < alpha_std:
        print(f"  => alpha is STABLE (drift < scatter): the exponent stays at ~{np.mean(alphas):.2f}")
        print(f"     Structure type preserved during amplitude decay.")
    else:
        print(f"  => alpha DRIFTS significantly (drift > scatter)")
        direction = "increases" if coeffs_alpha[0] > 0 else "decreases"
        print(f"     Exponent {direction} with scale: structure type changes.")


if __name__ == "__main__":
    main()
