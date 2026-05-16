#!/usr/bin/env python3
"""
exp_psd_prime_gaps.py — Power Spectral Density of Prime Gaps

Tests the prediction from ACF_1K_LAW: if acf(k) ~ -A/k, then by
Wiener-Khinchin, S(f) = sigma^2 + 2A * ln|2 sin(pi f)|.

This is "anti-1/f" noise: PSD dips at low f (long-range anti-correlation),
opposite of pink noise.

Usage:
    python tools/exp_psd_prime_gaps.py [--n_primes N] [--n_shuffles K]
"""

import argparse
import json
import numpy as np
from sympy import primerange


def compute_psd(gaps, method="welch", nperseg=None):
    """Compute PSD via Welch method for robustness."""
    from scipy.signal import welch
    if nperseg is None:
        nperseg = min(len(gaps) // 4, 8192)
    # Normalize gaps to zero mean
    g = gaps - np.mean(gaps)
    freqs, psd = welch(g, fs=1.0, nperseg=nperseg, noverlap=nperseg // 2)
    return freqs, psd


def theoretical_psd(freqs, A, sigma2):
    """
    Predicted PSD from acf(k) = -A/k:
    S(f) = sigma^2 + 2A * ln|2 sin(pi f)|

    Valid for 0 < f < 0.5 (excluding f=0).
    """
    f = np.asarray(freqs, dtype=float)
    mask = (f > 0) & (f < 0.5)
    S = np.full_like(f, np.nan)
    S[mask] = sigma2 + 2 * A * np.log(np.abs(2 * np.sin(np.pi * f[mask])))
    return S


def run_experiment(n_primes=500_000, n_shuffles=20, nperseg=4096):
    """Run the PSD experiment."""
    print(f"Generating primes up to cover {n_primes} primes...")
    # Estimate upper bound: p_n ~ n * ln(n) for large n
    import math
    upper = int(n_primes * (math.log(n_primes) + math.log(math.log(n_primes)) + 3))
    primes = np.array(list(primerange(2, upper)))[:n_primes]
    actual_n = len(primes)
    print(f"Got {actual_n} primes, largest = {primes[-1]}")

    gaps = np.diff(primes).astype(float)
    sigma2 = np.var(gaps)
    mean_gap = np.mean(gaps)
    print(f"Mean gap = {mean_gap:.3f}, Var = {sigma2:.3f}")

    # Measure A from autocorrelation directly
    g_centered = gaps - mean_gap
    n = len(g_centered)
    acf_lags = []
    for k in range(1, 21):
        c = np.mean(g_centered[:-k] * g_centered[k:]) / sigma2
        acf_lags.append((k, c))

    # Fit A from acf(k) = -A/k
    ks = np.array([x[0] for x in acf_lags])
    acfs = np.array([x[1] for x in acf_lags])
    # acf(k) = -A/k => acf(k)*k = -A
    A_estimates = -acfs * ks
    A_measured = np.median(A_estimates)
    print(f"Measured A = {A_measured:.4f} (from acf(k)*k median)")

    # Compute PSD of prime gaps
    freqs, psd_prime = compute_psd(gaps, nperseg=nperseg)

    # Theoretical prediction
    psd_theory = theoretical_psd(freqs, A_measured, sigma2)

    # Null baseline: shuffled gaps (destroys correlations => white noise)
    psd_shuffles = []
    for i in range(n_shuffles):
        shuffled = gaps.copy()
        np.random.shuffle(shuffled)
        _, psd_s = compute_psd(shuffled, nperseg=nperseg)
        psd_shuffles.append(psd_s)
    psd_shuffle_mean = np.mean(psd_shuffles, axis=0)
    psd_shuffle_std = np.std(psd_shuffles, axis=0)

    # Analysis: compare prime PSD with theory and shuffle
    valid = (freqs > 0.01) & (freqs < 0.49)

    # 1. Residual between measured and theoretical
    residual = psd_prime[valid] - psd_theory[valid]
    rel_residual = residual / psd_prime[valid]
    mean_rel_residual = np.mean(np.abs(rel_residual))

    # 2. z-score of prime PSD vs shuffle at low frequencies
    low_f = (freqs > 0.005) & (freqs < 0.05)
    if np.any(low_f) and np.any(psd_shuffle_std[low_f] > 0):
        z_low = (psd_prime[low_f] - psd_shuffle_mean[low_f]) / psd_shuffle_std[low_f]
        z_low_mean = np.mean(z_low)
    else:
        z_low_mean = np.nan

    # 3. z-score at high frequencies
    high_f = (freqs > 0.3) & (freqs < 0.49)
    if np.any(high_f) and np.any(psd_shuffle_std[high_f] > 0):
        z_high = (psd_prime[high_f] - psd_shuffle_mean[high_f]) / psd_shuffle_std[high_f]
        z_high_mean = np.mean(z_high)
    else:
        z_high_mean = np.nan

    # 4. Spectral slope: fit log(S) vs log(f) at low f
    low_region = (freqs > 0.005) & (freqs < 0.1)
    if np.sum(low_region) > 5:
        log_f = np.log10(freqs[low_region])
        log_s = np.log10(psd_prime[low_region])
        coeffs = np.polyfit(log_f, log_s, 1)
        spectral_slope = coeffs[0]
    else:
        spectral_slope = np.nan

    # 5. Compare with ln|2sin(pi f)| shape: correlation
    valid2 = (freqs > 0.02) & (freqs < 0.48)
    theory_shape = np.log(np.abs(2 * np.sin(np.pi * freqs[valid2])))
    r_corr = np.corrcoef(psd_prime[valid2], theory_shape)[0, 1]

    # 6. Ratio PSD(f=0.01) / PSD(f=0.5) — measures the "dip"
    idx_low = np.argmin(np.abs(freqs - 0.01))
    idx_high = np.argmin(np.abs(freqs - 0.48))
    dip_ratio = psd_prime[idx_low] / psd_prime[idx_high]
    dip_ratio_shuffle = psd_shuffle_mean[idx_low] / psd_shuffle_mean[idx_high]

    results = {
        "n_primes": actual_n,
        "n_gaps": len(gaps),
        "mean_gap": float(mean_gap),
        "var_gap": float(sigma2),
        "A_measured": float(A_measured),
        "nperseg": nperseg,
        "n_shuffles": n_shuffles,
        "mean_abs_rel_residual": float(mean_rel_residual),
        "z_low_freq_vs_shuffle": float(z_low_mean),
        "z_high_freq_vs_shuffle": float(z_high_mean),
        "spectral_slope_low_f": float(spectral_slope),
        "correlation_with_theory_shape": float(r_corr),
        "dip_ratio_prime": float(dip_ratio),
        "dip_ratio_shuffle": float(dip_ratio_shuffle),
        "acf_lags": [(int(k), float(a)) for k, a in acf_lags],
    }

    # Print summary
    print("\n=== RESULTS ===")
    print(f"A (measured from acf): {A_measured:.4f}")
    print(f"Mean |relative residual| (measured vs theory): {mean_rel_residual:.3f}")
    print(f"Correlation with ln|2sin(pi f)| shape: {r_corr:.4f}")
    print(f"Spectral slope at low f (log-log): {spectral_slope:.3f}")
    print(f"  (white noise = 0, pink noise = -1, blue noise = +1)")
    print(f"z-score vs shuffle at LOW freq (0.005-0.05): {z_low_mean:.2f}")
    print(f"z-score vs shuffle at HIGH freq (0.3-0.49): {z_high_mean:.2f}")
    print(f"Dip ratio S(0.01)/S(0.48): prime={dip_ratio:.3f}, shuffle={dip_ratio_shuffle:.3f}")
    print(f"\nACF lags 1-5:")
    for k, a in acf_lags[:5]:
        print(f"  lag {k}: acf = {a:.5f}, acf*k = {-a*k:.5f}")

    # Verdict
    print("\n=== VERDICT ===")
    if r_corr > 0.9:
        print("STRONG MATCH: PSD follows the ln|2sin(pi f)| prediction from 1/k law.")
        verdict = "CONFIRMED"
    elif r_corr > 0.7:
        print("PARTIAL MATCH: PSD has the right shape but deviations exist.")
        verdict = "PARTIAL"
    else:
        print("MISMATCH: PSD does not follow the 1/k prediction.")
        verdict = "FALSIFIED"

    if dip_ratio < 0.8 and dip_ratio_shuffle > 0.9:
        print(f"LOW-FREQ DIP confirmed: prime dip={dip_ratio:.3f} vs shuffle={dip_ratio_shuffle:.3f}")
        results["low_freq_dip_confirmed"] = True
    else:
        results["low_freq_dip_confirmed"] = False

    results["verdict"] = verdict
    return results, freqs, psd_prime, psd_theory, psd_shuffle_mean, psd_shuffle_std


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_primes", type=int, default=500_000)
    parser.add_argument("--n_shuffles", type=int, default=20)
    parser.add_argument("--nperseg", type=int, default=4096)
    args = parser.parse_args()

    results, freqs, psd_prime, psd_theory, psd_shuf_mean, psd_shuf_std = run_experiment(
        n_primes=args.n_primes,
        n_shuffles=args.n_shuffles,
        nperseg=args.nperseg,
    )

    # Save results
    out_path = "tools/data/psd_prime_gaps_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")
