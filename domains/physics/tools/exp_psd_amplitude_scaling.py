#!/usr/bin/env python3
"""
exp_psd_amplitude_scaling.py — PSD amplitude scaling across prime scales.

Cross-validates ACF_AMPLITUDE_SCALING via Wiener-Khinchin:
If acf(k) ~ -A(p)/k, then the PSD low-frequency suppression should track A(p).

Measures:
  - S(f) via Welch at multiple prime windows
  - Low-f dip ratio: S(f_low)/S(f_high) at each scale
  - Dip depth vs ln(p): does it decay linearly like A(ln p)?
  - Shuffled null baseline at each scale

Usage:
  python tools/exp_psd_amplitude_scaling.py [--n_primes N] [--n_windows W]
"""

import numpy as np
from scipy.signal import welch
from sympy import primerange
import json
import sys
import os

def get_args():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--n_primes', type=int, default=6_000_000)
    p.add_argument('--n_windows', type=int, default=10)
    p.add_argument('--window_size', type=int, default=100_000)
    p.add_argument('--n_surrogates', type=int, default=15)
    p.add_argument('--nperseg', type=int, default=2048)
    return p.parse_args()

def compute_psd_metrics(gaps, nperseg, f_low_max=0.02, f_high_min=0.3, f_high_max=0.48):
    """Compute PSD and extract low-f dip metrics."""
    g_norm = (gaps - np.mean(gaps)) / np.std(gaps)
    f, S = welch(g_norm, fs=1.0, nperseg=min(nperseg, len(g_norm)//2),
                 noverlap=nperseg//2, detrend='constant')

    low_mask = (f > 0) & (f <= f_low_max)
    high_mask = (f >= f_high_min) & (f <= f_high_max)

    if not np.any(low_mask) or not np.any(high_mask):
        return None

    S_low = np.mean(S[low_mask])
    S_high = np.mean(S[high_mask])
    dip_ratio = S_low / S_high  # <1 means suppression at low-f

    # Spectral slope (linear fit in log-log)
    pos = f > 0
    slope, intercept = np.polyfit(np.log10(f[pos]), np.log10(S[pos]), 1)

    return {
        'S_low': float(S_low),
        'S_high': float(S_high),
        'dip_ratio': float(dip_ratio),
        'spectral_slope': float(slope),
    }

def main():
    args = get_args()

    print(f"Generating primes up to ~{args.n_primes} primes...")
    # Estimate upper bound: p_n ~ n * ln(n) for large n
    import math
    upper = int(args.n_primes * (math.log(args.n_primes) + math.log(math.log(args.n_primes)) + 2))
    primes = np.array(list(primerange(2, upper)))[:args.n_primes]
    gaps = np.diff(primes).astype(float)
    print(f"Got {len(primes)} primes, {len(gaps)} gaps")

    # Log-spaced windows
    n_gaps = len(gaps)
    starts = np.linspace(0, n_gaps - args.window_size, args.n_windows, dtype=int)

    results = []

    for i, s in enumerate(starts):
        g = gaps[s:s+args.window_size]
        p_median = float(primes[s + args.window_size//2])
        ln_p = np.log(p_median)

        # Prime PSD
        m = compute_psd_metrics(g, args.nperseg)
        if m is None:
            continue

        # Shuffled surrogates
        dip_surr = []
        slope_surr = []
        for _ in range(args.n_surrogates):
            gs = np.random.permutation(g)
            ms = compute_psd_metrics(gs, args.nperseg)
            if ms:
                dip_surr.append(ms['dip_ratio'])
                slope_surr.append(ms['spectral_slope'])

        dip_surr = np.array(dip_surr)
        slope_surr = np.array(slope_surr)

        z_dip = (m['dip_ratio'] - np.mean(dip_surr)) / (np.std(dip_surr) + 1e-12)
        z_slope = (m['spectral_slope'] - np.mean(slope_surr)) / (np.std(slope_surr) + 1e-12)

        # ACF amplitude at this scale (for cross-check)
        acf1 = np.corrcoef(g[:-1], g[1:])[0, 1]

        row = {
            'window': i,
            'p_median': p_median,
            'ln_p': round(ln_p, 3),
            'dip_ratio': round(m['dip_ratio'], 4),
            'dip_surr_mean': round(float(np.mean(dip_surr)), 4),
            'z_dip': round(float(z_dip), 2),
            'spectral_slope': round(m['spectral_slope'], 4),
            'slope_surr_mean': round(float(np.mean(slope_surr)), 4),
            'z_slope': round(float(z_slope), 2),
            'acf1': round(float(acf1), 5),
        }
        results.append(row)
        print(f"  [{i+1}/{args.n_windows}] ln(p)={ln_p:.1f}  dip={m['dip_ratio']:.3f}  "
              f"z_dip={z_dip:.1f}  slope={m['spectral_slope']:.3f}  z_slope={z_slope:.1f}  "
              f"acf1={acf1:.4f}")

    # Fit dip_ratio vs ln(p)
    ln_ps = np.array([r['ln_p'] for r in results])
    dips = np.array([r['dip_ratio'] for r in results])
    slopes_psd = np.array([r['spectral_slope'] for r in results])
    acf1s = np.array([r['acf1'] for r in results])

    # Linear fits
    from scipy.stats import linregress

    fit_dip = linregress(ln_ps, dips)
    fit_slope = linregress(ln_ps, slopes_psd)
    fit_acf = linregress(ln_ps, np.abs(acf1s))

    print(f"\n=== SCALING LAWS ===")
    print(f"dip_ratio(ln p) = {fit_dip.intercept:.4f} + {fit_dip.slope:.6f}*ln(p)  "
          f"R2={fit_dip.rvalue**2:.3f}  p={fit_dip.pvalue:.2e}")
    print(f"spectral_slope(ln p) = {fit_slope.intercept:.4f} + {fit_slope.slope:.6f}*ln(p)  "
          f"R2={fit_slope.rvalue**2:.3f}  p={fit_slope.pvalue:.2e}")
    print(f"|acf1|(ln p) = {fit_acf.intercept:.4f} + {fit_acf.slope:.6f}*ln(p)  "
          f"R2={fit_acf.rvalue**2:.3f}  p={fit_acf.pvalue:.2e}")

    # Poisson crossover prediction from dip_ratio → 1.0 (no suppression)
    if fit_dip.slope > 0:
        ln_p_cross_dip = (1.0 - fit_dip.intercept) / fit_dip.slope
        p_cross_dip = np.exp(ln_p_cross_dip)
        print(f"\nPoisson crossover (dip→1.0): ln(p*)={ln_p_cross_dip:.1f}  "
              f"p*~10^{ln_p_cross_dip/np.log(10):.1f}")
    else:
        ln_p_cross_dip = None
        print(f"\nDip ratio DECREASING with scale — no Poisson crossover from PSD dip")

    # Poisson crossover from spectral_slope → 0
    if fit_slope.slope != 0:
        ln_p_cross_slope = -fit_slope.intercept / fit_slope.slope
        print(f"Poisson crossover (slope→0): ln(p*)={ln_p_cross_slope:.1f}  "
              f"p*~10^{ln_p_cross_slope/np.log(10):.1f}")

    # Cross-validation: does dip_ratio track |acf1|?
    corr_dip_acf = np.corrcoef(dips, np.abs(acf1s))[0, 1]
    print(f"\nCross-validation: corr(dip_ratio, |acf1|) = {corr_dip_acf:.3f}")

    # Save
    output = {
        'experiment': 'psd_amplitude_scaling',
        'n_primes': len(primes),
        'n_windows': args.n_windows,
        'window_size': args.window_size,
        'n_surrogates': args.n_surrogates,
        'nperseg': args.nperseg,
        'windows': results,
        'fits': {
            'dip_ratio': {
                'intercept': round(fit_dip.intercept, 5),
                'slope': round(fit_dip.slope, 7),
                'R2': round(fit_dip.rvalue**2, 4),
                'p_value': float(f'{fit_dip.pvalue:.3e}'),
            },
            'spectral_slope': {
                'intercept': round(fit_slope.intercept, 5),
                'slope': round(fit_slope.slope, 7),
                'R2': round(fit_slope.rvalue**2, 4),
                'p_value': float(f'{fit_slope.pvalue:.3e}'),
            },
            'abs_acf1': {
                'intercept': round(fit_acf.intercept, 5),
                'slope': round(fit_acf.slope, 7),
                'R2': round(fit_acf.rvalue**2, 4),
                'p_value': float(f'{fit_acf.pvalue:.3e}'),
            },
        },
        'cross_validation': {
            'corr_dip_acf1': round(float(corr_dip_acf), 4),
        },
        'poisson_crossover_ln_p': round(float(ln_p_cross_dip), 2) if ln_p_cross_dip else None,
    }

    outpath = os.path.join(os.path.dirname(__file__), 'data', 'exp_psd_amp_scaling.json')
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {outpath}")

if __name__ == '__main__':
    main()
