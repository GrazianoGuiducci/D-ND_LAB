#!/usr/bin/env python3
"""
exp_acf_range_universality.py — ACF decay structure across domains.

Tests:
  1. Does the 1/k ACF law persist beyond lag 20 (up to 200)?
  2. Is alpha=1 prime-specific or generic?
  3. Does alpha drift across prime scales?
  4. Where does the 1/k law break — at L*=35?

Domains: primes, GUE, GOE, Poisson, primes_shuffled.
Null: shuffled gaps (order destroyed, marginals preserved).

Reusable: --n_primes, --max_lag_prime, --max_lag_other, --n_surrogates.
"""

import argparse
import json
import sys
import numpy as np
from sympy import primerange


def get_primes(n):
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
    """ACF at lags 1..max_lag, normalized."""
    n = len(gaps)
    mean = np.mean(gaps)
    var = np.var(gaps)
    if var < 1e-15:
        return np.zeros(max_lag)
    centered = gaps - mean
    acf = np.empty(max_lag)
    for k in range(1, max_lag + 1):
        acf[k - 1] = np.mean(centered[:-k] * centered[k:]) / var
    return acf


def fit_power_law(lags, acf):
    """Fit |acf(k)| = A * k^(-alpha) on negative ACF values.
    Returns (A, alpha, R2) or None."""
    mask = acf < 0
    if np.sum(mask) < 3:
        return None
    k = lags[mask].astype(float)
    y = np.abs(acf[mask])
    lk, ly = np.log(k), np.log(y)
    c = np.polyfit(lk, ly, 1)
    alpha = -c[0]
    A = np.exp(c[1])
    pred = c[1] + c[0] * lk
    ss_res = np.sum((ly - pred) ** 2)
    ss_tot = np.sum((ly - np.mean(ly)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return A, alpha, r2


def generate_rmt_spacings(N, n_mat, ensemble='GUE'):
    """Unfolded spacings from random matrix ensemble."""
    spacings = []
    sz = max(50, N // n_mat + 10)
    for _ in range(n_mat):
        if ensemble == 'GUE':
            Re = np.random.randn(sz, sz)
            Im = np.random.randn(sz, sz)
            H = (Re + Re.T) / 2 + 1j * (Im - Im.T) / 2
        else:  # GOE
            A = np.random.randn(sz, sz)
            H = (A + A.T) / 2
        eigs = np.sort(np.linalg.eigvalsh(H))
        s = np.diff(eigs)
        s = s / np.mean(s)
        spacings.extend(s)
        if len(spacings) >= N:
            break
    return np.array(spacings[:N])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_primes", type=int, default=1_000_000)
    parser.add_argument("--max_lag_prime", type=int, default=200)
    parser.add_argument("--max_lag_other", type=int, default=50)
    parser.add_argument("--n_surrogates", type=int, default=15)
    args = parser.parse_args()

    np.random.seed(42)

    # --- Generate primes ---
    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    gaps = np.diff(primes).astype(float)
    N = len(gaps)
    print(f"Got {N:,} gaps. p_max = {primes[-1]:,}")

    # ============================================================
    # PART A: Prime ACF extended to lag 200
    # ============================================================
    print(f"\n=== PART A: Prime ACF extended (lags 1-{args.max_lag_prime}) ===")
    acf_prime_full = compute_acf(gaps, args.max_lag_prime)
    lags_full = np.arange(1, args.max_lag_prime + 1)

    noise = 2.0 / np.sqrt(N)
    sig_mask = np.abs(acf_prime_full) > noise
    sig_lags = np.where(sig_mask)[0]
    max_sig_lag = int(sig_lags[-1] + 1) if len(sig_lags) > 0 else 0

    print(f"  Noise level (2/sqrt(N)): {noise:.7f}")
    print(f"  Last significant lag: {max_sig_lag}")
    if max_sig_lag >= 35:
        print(f"  acf at L*=35: {acf_prime_full[34]:.7f} (z={acf_prime_full[34]/noise:.1f})")

    # Power-law fits over different lag ranges
    fit_ranges = {}
    for end in [20, 35, 50, 100, 150, 200]:
        if end > args.max_lag_prime:
            break
        lags_seg = lags_full[:end]
        acf_seg = acf_prime_full[:end]
        fit = fit_power_law(lags_seg, acf_seg)
        if fit:
            A, alpha, r2 = fit
            fit_ranges[f'1-{end}'] = {'A': A, 'alpha': alpha, 'r2': r2}
            print(f"  Lags 1-{end:3d}: A={A:.5f}, alpha={alpha:.3f}, R2={r2:.4f}")

    # Segmented fits: 1-35 vs 36-200 (test breakpoint at L*)
    if args.max_lag_prime >= 100:
        fit_lo = fit_power_law(lags_full[:35], acf_prime_full[:35])
        fit_hi = fit_power_law(lags_full[35:150], acf_prime_full[35:150])
        if fit_lo and fit_hi:
            print(f"\n  Segmented fit (breakpoint at L*=35):")
            print(f"    Lags  1-35:  alpha={fit_lo[1]:.3f}, R2={fit_lo[2]:.4f}")
            print(f"    Lags 36-150: alpha={fit_hi[1]:.3f}, R2={fit_hi[2]:.4f}")
            fit_ranges['seg_1_35'] = {'A': fit_lo[0], 'alpha': fit_lo[1], 'r2': fit_lo[2]}
            fit_ranges['seg_36_150'] = {'A': fit_hi[0], 'alpha': fit_hi[1], 'r2': fit_hi[2]}

    # Shuffled surrogate extended ACF
    print("\n  Shuffled surrogates (extended):")
    shuf_acfs = []
    for i in range(args.n_surrogates):
        sg = gaps.copy()
        np.random.shuffle(sg)
        sa = compute_acf(sg, min(50, args.max_lag_prime))
        shuf_acfs.append(sa)
    shuf_acf_mean = np.mean(shuf_acfs, axis=0)
    shuf_acf_std = np.std(shuf_acfs, axis=0)
    print(f"  Shuffle acf1: {shuf_acf_mean[0]:.7f} +/- {shuf_acf_std[0]:.7f}")
    print(f"  Shuffle max|acf|: {np.max(np.abs(shuf_acf_mean)):.7f}")

    # ============================================================
    # PART B: Cross-domain comparison
    # ============================================================
    print(f"\n=== PART B: Cross-domain ACF (lags 1-{args.max_lag_other}) ===")

    N_rmt = 10_000
    n_mat_rmt = 30

    print("Generating GUE spacings...")
    gue_gaps = generate_rmt_spacings(N_rmt, n_mat_rmt, 'GUE')
    print("Generating GOE spacings...")
    goe_gaps = generate_rmt_spacings(N_rmt, n_mat_rmt, 'GOE')

    poisson_gaps = np.random.exponential(1.0, 100_000)

    shuffled_gaps = gaps[:100_000].copy()
    np.random.shuffle(shuffled_gaps)

    domains = {
        'primes': gaps[:100_000],
        'primes_shuffled': shuffled_gaps,
        'GUE': gue_gaps,
        'GOE': goe_gaps,
        'Poisson': poisson_gaps,
    }

    lags_other = np.arange(1, args.max_lag_other + 1)

    header = f"{'Domain':<20} {'N':>8} {'acf1':>10} {'acf2':>10} {'|S|':>8} {'lag1/S':>7} {'alpha':>7} {'R2':>6} {'range':>6}"
    print(f"\n{header}")
    print("-" * len(header))

    cross_results = {}
    for name, g in domains.items():
        acf = compute_acf(g, args.max_lag_other)

        S = np.sum(np.abs(acf))
        lag1_frac = np.abs(acf[0]) / S if S > 0 else 0

        nl = 2.0 / np.sqrt(len(g))
        sig = np.where(np.abs(acf) > nl)[0]
        rng = int(sig[-1] + 1) if len(sig) > 0 else 0

        fit = fit_power_law(lags_other, acf)
        if fit:
            A, alpha, r2 = fit
        else:
            A, alpha, r2 = None, None, None

        # Count negative lags
        n_neg = int(np.sum(acf < 0))
        n_pos = int(np.sum(acf > 0))

        cross_results[name] = {
            'N': int(len(g)),
            'acf1': float(acf[0]),
            'acf2': float(acf[1]),
            'S_50': float(S),
            'lag1_frac': float(lag1_frac),
            'alpha': float(alpha) if alpha is not None else None,
            'r2': float(r2) if r2 is not None else None,
            'range': rng,
            'n_negative_lags': n_neg,
            'n_positive_lags': n_pos,
            'acf_values': [float(x) for x in acf],
        }

        a_str = f"{alpha:.3f}" if alpha is not None else "  N/A"
        r_str = f"{r2:.3f}" if r2 is not None else " N/A"
        print(f"{name:<20} {len(g):>8,} {acf[0]:>+10.6f} {acf[1]:>+10.6f} {S:>8.4f} {lag1_frac:>7.3f} {a_str:>7} {r_str:>6} {rng:>6}")

    # ============================================================
    # PART C: Alpha stability across 5 prime scales
    # ============================================================
    print(f"\n=== PART C: Alpha stability across prime scales ===")

    window_size = min(100_000, N // 6)
    n_scale = 5
    starts = np.linspace(0, N - window_size, n_scale).astype(int)

    print(f"\n{'idx':>4} {'ln(p)':>8} {'alpha':>8} {'A':>10} {'R2':>6} | {'alpha_s':>8} {'z_alpha':>8}")
    print("-" * 68)

    scale_results = []
    for start in starts:
        wg = gaps[start:start + window_size]
        p_center = primes[start + window_size // 2]
        ln_p = np.log(float(p_center))

        acf_w = compute_acf(wg, 50)
        fit_w = fit_power_law(np.arange(1, 51), acf_w)

        shuf_alphas = []
        for _ in range(args.n_surrogates):
            sw = wg.copy()
            np.random.shuffle(sw)
            acf_s = compute_acf(sw, 50)
            fit_s = fit_power_law(np.arange(1, 51), acf_s)
            if fit_s:
                shuf_alphas.append(fit_s[1])

        if fit_w:
            A_w, alpha_w, r2_w = fit_w
            alpha_s_mean = np.mean(shuf_alphas) if shuf_alphas else 0
            alpha_s_std = np.std(shuf_alphas) if shuf_alphas else 1
            z_alpha = (alpha_w - alpha_s_mean) / alpha_s_std if alpha_s_std > 0 else 0

            scale_results.append({
                'start': int(start),
                'ln_p': float(ln_p),
                'alpha': float(alpha_w),
                'A': float(A_w),
                'r2': float(r2_w),
                'alpha_shuf_mean': float(alpha_s_mean),
                'alpha_shuf_std': float(alpha_s_std),
                'z_alpha': float(z_alpha),
            })

            print(f"{start:>4d} {ln_p:>8.2f} {alpha_w:>8.3f} {A_w:>10.5f} {r2_w:>6.3f} | {alpha_s_mean:>8.3f} {z_alpha:>+8.1f}")

    # Trend analysis
    if len(scale_results) >= 3:
        ln_ps = np.array([r['ln_p'] for r in scale_results])
        alphas = np.array([r['alpha'] for r in scale_results])
        c = np.polyfit(ln_ps, alphas, 1)
        drift = c[0] * (ln_ps[-1] - ln_ps[0])
        scatter = np.std(alphas)

        print(f"\n  Alpha trend:")
        print(f"    mean = {np.mean(alphas):.4f} +/- {scatter:.4f}")
        print(f"    slope = {c[0]:.5f} per unit ln(p)")
        print(f"    total drift = {drift:.4f} over ln(p) range {ln_ps[0]:.1f}-{ln_ps[-1]:.1f}")
        print(f"    drift/scatter = {abs(drift)/scatter:.2f}" if scatter > 0 else "")
        stable = abs(drift) < scatter
        print(f"    => alpha is {'STABLE' if stable else 'DRIFTS'}")

        # A trend
        As = np.array([r['A'] for r in scale_results])
        c_A = np.polyfit(ln_ps, As, 1)
        print(f"\n  Amplitude trend:")
        print(f"    A mean = {np.mean(As):.5f} +/- {np.std(As):.5f}")
        print(f"    A slope = {c_A[0]:.6f} per unit ln(p)")
        if c_A[0] < 0:
            ln_p_zero = -c_A[1] / c_A[0]
            print(f"    A -> 0 at ln(p) = {ln_p_zero:.1f}  =>  p* = {np.exp(ln_p_zero):.2e}")

    # ============================================================
    # Save
    # ============================================================
    output = {
        'experiment': 'acf_range_universality',
        'date': '2026-04-17T03:30',
        'piano': 39,
        'params': vars(args),
        'prime_acf_extended': {
            'max_lag': args.max_lag_prime,
            'last_significant_lag': max_sig_lag,
            'acf_at_35': float(acf_prime_full[34]) if args.max_lag_prime >= 35 else None,
            'noise_level': float(noise),
            'fit_ranges': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in fit_ranges.items()},
            'acf_values': [float(x) for x in acf_prime_full],
        },
        'cross_domain': cross_results,
        'scale_stability': scale_results,
    }

    outpath = 'tools/data/exp_acf_range_universality.json'
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {outpath}")


if __name__ == '__main__':
    main()
