#!/usr/bin/env python3
"""
exp_magnitude_psd_from_acf.py — Wiener-Khinchin self-consistency of magnitude channel

Question: Does the measured magnitude ACF (acf(k) ~ -A/k^alpha) predict the
measured PSD slope (+0.074) via Wiener-Khinchin? At what lag depth K* does the
ACF-predicted PSD converge to the directly-measured PSD?

If K*=1 → pair correlations (lag-1 only) suffice for the spectrum.
If K*>>1 → the 1/k decay law carries essential spectral content.
If convergence fails → there's spectral structure beyond the power-law ACF.

Design:
  1. Get primes, decompose into magnitude channel
  2. Measure magnitude ACF for lags 1..K_max
  3. Wiener-Khinchin: S_K(f) = 1 + 2*sum_{k=1}^{K} acf_norm(k)*cos(2*pi*f*k)
  4. Vary K, measure predicted slope at each K
  5. Compare with directly-measured Welch PSD slope
  6. Analytical 1/k model: S(f) = sigma^2 + 2A*ln|2*sin(pi*f)|
  7. Null: shuffled magnitude channel

Usage:
  python tools/exp_magnitude_psd_from_acf.py [--n_primes N] [--nperseg S] [--k_max K]
"""

import argparse
import numpy as np
from scipy.signal import welch
from scipy.stats import linregress
import json
import time


def sieve_primes(limit):
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def get_primes(n_target):
    limit = int(n_target * (np.log(n_target) + np.log(np.log(n_target)) + 2))
    limit = max(limit, 1000)
    primes = sieve_primes(limit)
    while len(primes) < n_target:
        limit = int(limit * 1.5)
        primes = sieve_primes(limit)
    return primes[:n_target]


def decompose_magnitude(primes):
    """Extract magnitude channel: gap minus its transition-class mean."""
    p = primes[primes > 3]
    gaps = np.diff(p).astype(float)
    res_l = p[:-1] % 6
    res_r = p[1:] % 6
    trans = res_l * 10 + res_r
    trans_component = np.zeros_like(gaps)
    for tt in np.unique(trans):
        mask = trans == tt
        trans_component[mask] = gaps[mask].mean()
    mag_residual = gaps - trans_component
    return mag_residual, gaps


def measure_acf(signal, k_max):
    """Measure empirical ACF for lags 1..k_max (normalized)."""
    n = len(signal)
    mean = signal.mean()
    var = signal.var()
    centered = signal - mean
    acf = np.zeros(k_max)
    for k in range(1, k_max + 1):
        acf[k-1] = np.dot(centered[:n-k], centered[k:]) / ((n - k) * var)
    return acf


def wiener_khinchin_psd(acf_values, freqs):
    """
    Reconstruct PSD from ACF via Wiener-Khinchin:
    S(f) = 1 + 2 * sum_{k=1}^{K} acf(k) * cos(2*pi*f*k)
    (Normalized so that S represents ratio to white noise baseline.)
    """
    K = len(acf_values)
    k_arr = np.arange(1, K + 1)
    S = np.ones_like(freqs)
    for i, f in enumerate(freqs):
        S[i] += 2.0 * np.sum(acf_values * np.cos(2 * np.pi * f * k_arr))
    return S


def analytical_1k_psd(A, freqs):
    """
    Analytical PSD for acf(k) = -A/k (negative 1/k correlation).
    S(f) = 1 + 2*(-A)*sum_{k=1}^{inf} cos(2*pi*f*k)/k
         = 1 + 2*A*ln|2*sin(pi*f)|
    (using the Fourier series -sum cos(kx)/k = ln|2sin(x/2)|)
    """
    sf = np.sin(np.pi * freqs)
    sf = np.maximum(sf, 1e-15)
    return 1.0 + 2.0 * A * np.log(2.0 * sf)


def measure_slope(freqs, psd, f_min=0.02, f_max=0.45):
    """Log-log slope of PSD in frequency range."""
    mask = (freqs >= f_min) & (freqs <= f_max)
    if mask.sum() < 5:
        return np.nan, np.nan, np.nan
    lf = np.log10(freqs[mask])
    lp = np.log10(psd[mask])
    res = linregress(lf, lp)
    return res.slope, res.stderr, res.rvalue**2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=2_000_000)
    parser.add_argument('--nperseg', type=int, default=4096)
    parser.add_argument('--k_max', type=int, default=200)
    parser.add_argument('--n_shuffle', type=int, default=15)
    args = parser.parse_args()

    t0 = time.time()
    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    print(f"  Range: {primes[0]} to {primes[-1]:,} ({time.time()-t0:.1f}s)")

    # Decompose
    mag, gaps = decompose_magnitude(primes)
    print(f"  Magnitude channel: {len(mag):,} gaps, var={mag.var():.4f}, mean={mag.mean():.6f}")

    # 1. Direct Welch PSD of magnitude channel
    print("\n--- Direct Welch PSD ---")
    f_welch, psd_welch = welch(mag, fs=1.0, nperseg=args.nperseg, detrend='constant')
    mask_nz = f_welch > 0
    f_welch = f_welch[mask_nz]
    psd_welch = psd_welch[mask_nz]
    slope_direct, se_direct, r2_direct = measure_slope(f_welch, psd_welch)
    print(f"  Direct PSD slope: {slope_direct:.4f} +/- {se_direct:.4f} (R2={r2_direct:.4f})")

    # 2. Measure empirical ACF
    print(f"\n--- Empirical ACF (K_max={args.k_max}) ---")
    acf = measure_acf(mag, args.k_max)
    print(f"  acf(1)={acf[0]:.6f}, acf(2)={acf[1]:.6f}, acf(5)={acf[4]:.6f}")
    n_neg = np.sum(acf < 0)
    print(f"  Negative lags: {n_neg}/{args.k_max}")

    # Fit 1/k model to ACF
    lags = np.arange(1, args.k_max + 1)
    neg_mask = acf < 0
    if neg_mask.sum() > 5:
        log_lag = np.log10(lags[neg_mask])
        log_acf = np.log10(np.abs(acf[neg_mask]))
        res_acf = linregress(log_lag, log_acf)
        A_fit = 10**res_acf.intercept
        alpha_fit = -res_acf.slope
        print(f"  ACF power-law fit: |acf(k)| ~ {A_fit:.4f}/k^{alpha_fit:.3f} (R2={res_acf.rvalue**2:.4f})")
    else:
        A_fit = np.abs(acf[0])
        alpha_fit = 1.0
        print(f"  Too few negative lags for fit, using A={A_fit:.4f}, alpha=1.0")

    # 3. Wiener-Khinchin reconstruction at varying K
    print(f"\n--- WK Reconstruction: slope convergence ---")
    freqs_wk = np.linspace(0.001, 0.499, 2000)
    K_values = [1, 2, 3, 5, 10, 20, 50, 100, 150, 200]
    K_values = [k for k in K_values if k <= args.k_max]

    results_wk = []
    print(f"  {'K':>5s}  {'slope':>8s}  {'R2':>6s}  {'slope_err':>10s}")
    for K in K_values:
        psd_wk = wiener_khinchin_psd(acf[:K], freqs_wk)
        psd_wk = np.maximum(psd_wk, 1e-15)
        sl, se, r2 = measure_slope(freqs_wk, psd_wk)
        delta = sl - slope_direct
        results_wk.append({'K': K, 'slope': sl, 'R2': r2, 'delta': delta})
        print(f"  {K:>5d}  {sl:>+8.4f}  {r2:>6.4f}  {delta:>+10.4f}")

    # Find K* where WK slope converges to direct slope (within 10%)
    k_star = None
    for r in results_wk:
        if abs(r['delta']) < abs(slope_direct) * 0.10:
            k_star = r['K']
            break
    if k_star:
        print(f"\n  K* = {k_star} (WK slope within 10% of direct PSD slope)")
    else:
        print(f"\n  K* > {args.k_max}: WK slope has NOT converged to direct PSD slope")

    # 4. Analytical 1/k model
    print(f"\n--- Analytical 1/k model ---")
    psd_1k = analytical_1k_psd(A_fit, freqs_wk)
    psd_1k = np.maximum(psd_1k, 1e-15)
    sl_1k, se_1k, r2_1k = measure_slope(freqs_wk, psd_1k)
    print(f"  Analytical 1/k PSD slope: {sl_1k:+.4f} (R2={r2_1k:.4f})")
    print(f"  Delta vs direct: {sl_1k - slope_direct:+.4f}")

    # Compare shapes: correlation between WK(K_max) and direct Welch PSD
    # Interpolate WK onto Welch frequencies
    psd_wk_full = wiener_khinchin_psd(acf, freqs_wk)
    psd_wk_full = np.maximum(psd_wk_full, 1e-15)

    # 5. Null baseline: shuffled magnitude
    print(f"\n--- Null baseline: shuffled magnitude ({args.n_shuffle} surrogates) ---")
    shuffle_slopes = []
    rng = np.random.default_rng(42)
    for i in range(args.n_shuffle):
        mag_shuf = rng.permutation(mag)
        f_s, psd_s = welch(mag_shuf, fs=1.0, nperseg=args.nperseg, detrend='constant')
        mask_s = f_s > 0
        sl_s, _, _ = measure_slope(f_s[mask_s], psd_s[mask_s])
        shuffle_slopes.append(sl_s)
    shuffle_slopes = np.array(shuffle_slopes)
    z_direct = (slope_direct - shuffle_slopes.mean()) / shuffle_slopes.std()
    print(f"  Shuffle slope: {shuffle_slopes.mean():.4f} +/- {shuffle_slopes.std():.4f}")
    print(f"  Direct slope z-score vs shuffle: {z_direct:.1f}")

    # 6. Decompose the ACF contribution by lag range
    print(f"\n--- ACF contribution by lag range ---")
    ranges = [(1, 1), (2, 5), (6, 20), (21, 50), (51, 100), (101, 200)]
    ranges = [(a, min(b, args.k_max)) for a, b in ranges if a <= args.k_max]
    print(f"  {'Range':>10s}  {'sum_acf':>10s}  {'frac_total':>10s}  {'slope_incr':>10s}")
    total_sum = np.sum(acf)
    prev_slope = 0.0
    for a, b in ranges:
        sum_range = np.sum(acf[a-1:b])
        frac = sum_range / total_sum if total_sum != 0 else 0
        # Incremental: PSD with lags up to b
        psd_b = wiener_khinchin_psd(acf[:b], freqs_wk)
        psd_b = np.maximum(psd_b, 1e-15)
        sl_b, _, _ = measure_slope(freqs_wk, psd_b)
        incr = sl_b - prev_slope
        prev_slope = sl_b
        print(f"  {a:>4d}-{b:<4d}  {sum_range:>+10.6f}  {frac:>10.3f}  {incr:>+10.4f}")

    # 7. Scale dependence: split primes into windows
    print(f"\n--- Scale dependence: magnitude PSD slope in windows ---")
    n_windows = 5
    chunk = len(mag) // n_windows
    print(f"  {'Window':>8s}  {'ln_p':>6s}  {'slope_direct':>12s}  {'acf1':>8s}  {'slope_WK50':>10s}")
    for w in range(n_windows):
        start = w * chunk
        end = (w + 1) * chunk
        mag_w = mag[start:end]
        p_mid = primes[primes > 3][start + chunk // 2]
        ln_p = np.log(float(p_mid))
        f_w, psd_w = welch(mag_w, fs=1.0, nperseg=min(args.nperseg, chunk // 2), detrend='constant')
        mask_w = f_w > 0
        sl_w, _, _ = measure_slope(f_w[mask_w], psd_w[mask_w])
        acf_w = measure_acf(mag_w, 50)
        psd_wk50 = wiener_khinchin_psd(acf_w, freqs_wk)
        psd_wk50 = np.maximum(psd_wk50, 1e-15)
        sl_wk50, _, _ = measure_slope(freqs_wk, psd_wk50)
        print(f"  {w+1:>8d}  {ln_p:>6.1f}  {sl_w:>+12.4f}  {acf_w[0]:>+8.5f}  {sl_wk50:>+10.4f}")

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Direct Welch PSD slope (magnitude): {slope_direct:+.4f}")
    print(f"WK-reconstructed slope (K={args.k_max}):    {results_wk[-1]['slope']:+.4f}")
    print(f"Analytical 1/k model slope:          {sl_1k:+.4f}")
    print(f"Shuffle baseline slope:              {shuffle_slopes.mean():+.4f}")
    print(f"K* (10% convergence):                {k_star if k_star else f'>{args.k_max}'}")
    print(f"ACF fit: |acf(k)| ~ {A_fit:.4f}/k^{alpha_fit:.3f}")
    wk_delta = results_wk[-1]['slope'] - slope_direct
    frac_captured = results_wk[-1]['slope'] / slope_direct * 100 if slope_direct != 0 else 0
    print(f"WK captures {frac_captured:.1f}% of direct PSD slope")
    if abs(wk_delta) < abs(slope_direct) * 0.15:
        print(f"VERDICT: WK SELF-CONSISTENT — ACF fully predicts PSD slope")
    else:
        print(f"VERDICT: WK DISCREPANCY — ACF does NOT fully predict PSD slope")
        print(f"  Gap: {wk_delta:+.4f} ({abs(wk_delta/slope_direct)*100:.0f}% of direct slope)")
    print(f"\nTotal time: {time.time()-t0:.1f}s")

    # Save results
    output = {
        'n_primes': args.n_primes,
        'slope_direct': slope_direct,
        'slope_wk_full': results_wk[-1]['slope'],
        'slope_analytical_1k': sl_1k,
        'slope_shuffle': float(shuffle_slopes.mean()),
        'k_star': k_star,
        'acf_A': float(A_fit),
        'acf_alpha': float(alpha_fit),
        'acf1_mag': float(acf[0]),
        'wk_convergence': results_wk,
        'z_vs_shuffle': float(z_direct),
        'frac_captured_pct': frac_captured
    }
    out_path = 'tools/data/magnitude_psd_from_acf.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
