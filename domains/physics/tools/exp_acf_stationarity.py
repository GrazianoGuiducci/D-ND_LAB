#!/usr/bin/env python3
"""
exp_acf_stationarity.py — ACF structure: raw vs PNT-normalized gaps

Tests whether the sign flip at lag ~7 in prime gap ACF is structural
or an artifact of non-stationarity (density drift).

The claim ACF_1K_LAW says acf(k) ~ -0.037/k with ALL 20 lags negative.
But exp_acf_range_universality (2026-04-17) shows only 6 negative lags
on the raw sequence. Lags 7+ are positive.

Hypothesis: the positive ACF at lags 7+ is the PNT density drift
(illusory duality, det=+1). PNT-normalization should recover the
all-negative pattern (dipolar duality, det=-1).

Metrics:
  1. Crossover lag: first lag where ACF becomes positive (raw vs normalized)
  2. Number of negative lags in first 50 (raw vs normalized)
  3. Power-law fit alpha, R2 on negative lags (raw vs normalized)
  4. Same analysis in 5 scale windows (stability check)
  5. Null baseline: shuffled (raw and normalized should both give ACF~0)

Usage:
    python tools/exp_acf_stationarity.py [--n_primes N] [--max_lag L]
"""

import argparse
import json
import numpy as np


def sieve_primes(limit):
    """Sieve of Eratosthenes, returns numpy array."""
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def get_primes(n):
    """Get at least n primes via sieve."""
    import math
    upper = int(n * (math.log(n) + math.log(math.log(n)) + 3))
    primes = sieve_primes(upper)
    while len(primes) < n:
        upper = int(upper * 1.5)
        primes = sieve_primes(upper)
    return primes[:n]


def compute_acf(gaps, max_lag):
    """ACF at lags 1..max_lag, normalized by variance."""
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
    Returns (A, alpha, R2, n_points) or None."""
    mask = acf < 0
    n_neg = int(np.sum(mask))
    if n_neg < 3:
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
    return A, alpha, r2, n_neg


def analyze_acf(gaps, max_lag, label=""):
    """Full ACF analysis. Returns dict of metrics."""
    acf = compute_acf(gaps, max_lag)
    lags = np.arange(1, max_lag + 1)

    n_neg = int(np.sum(acf < 0))
    n_pos = int(np.sum(acf > 0))

    # Crossover lag: first lag where ACF > 0
    pos_idx = np.where(acf > 0)[0]
    crossover = int(pos_idx[0] + 1) if len(pos_idx) > 0 else max_lag + 1

    # Significance
    noise = 2.0 / np.sqrt(len(gaps))
    sig_neg = int(np.sum(acf < -noise))
    sig_pos = int(np.sum(acf > noise))

    # Power-law fit
    fit = fit_power_law(lags, acf)
    if fit:
        A, alpha, r2, n_fit = fit
    else:
        A, alpha, r2, n_fit = None, None, None, 0

    return {
        'n_negative': n_neg,
        'n_positive': n_pos,
        'crossover_lag': crossover,
        'sig_negative': sig_neg,
        'sig_positive': sig_pos,
        'noise_level': float(noise),
        'alpha': float(alpha) if alpha is not None else None,
        'A': float(A) if A is not None else None,
        'r2': float(r2) if r2 is not None else None,
        'n_fit_points': n_fit,
        'acf_first_10': [float(x) for x in acf[:10]],
        'acf_values': [float(x) for x in acf],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_primes", type=int, default=500_000)
    parser.add_argument("--max_lag", type=int, default=50)
    parser.add_argument("--n_shuffles", type=int, default=15)
    args = parser.parse_args()

    np.random.seed(42)
    max_lag = args.max_lag

    # Generate primes
    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    N = len(primes)
    print(f"Got {N:,} primes, p_max = {primes[-1]:,}")

    gaps_raw = np.diff(primes).astype(float)
    N_gaps = len(gaps_raw)

    # PNT normalization: g_i / ln(p_i)
    ln_p = np.log(primes[:-1].astype(float))
    gaps_norm = gaps_raw / ln_p
    print(f"Mean raw gap = {np.mean(gaps_raw):.3f}, mean normalized = {np.mean(gaps_norm):.4f}")
    print(f"Var raw = {np.var(gaps_raw):.3f}, var normalized = {np.var(gaps_norm):.4f}")

    # ============================================================
    # PART 1: Full-sequence ACF (raw vs normalized)
    # ============================================================
    print(f"\n{'='*60}")
    print("PART 1: Full-sequence ACF (raw vs PNT-normalized)")
    print(f"{'='*60}")

    res_raw = analyze_acf(gaps_raw, max_lag, "raw")
    res_norm = analyze_acf(gaps_norm, max_lag, "normalized")

    print(f"\n{'Metric':<25} {'Raw':>12} {'Normalized':>12}")
    print("-" * 50)
    print(f"{'Negative lags':<25} {res_raw['n_negative']:>12} {res_norm['n_negative']:>12}")
    print(f"{'Positive lags':<25} {res_raw['n_positive']:>12} {res_norm['n_positive']:>12}")
    print(f"{'Crossover lag':<25} {res_raw['crossover_lag']:>12} {res_norm['crossover_lag']:>12}")
    print(f"{'Sig negative':<25} {res_raw['sig_negative']:>12} {res_norm['sig_negative']:>12}")
    print(f"{'Sig positive':<25} {res_raw['sig_positive']:>12} {res_norm['sig_positive']:>12}")

    a_raw = f"{res_raw['alpha']:.3f}" if res_raw['alpha'] else "N/A"
    a_norm = f"{res_norm['alpha']:.3f}" if res_norm['alpha'] else "N/A"
    r_raw = f"{res_raw['r2']:.3f}" if res_raw['r2'] else "N/A"
    r_norm = f"{res_norm['r2']:.3f}" if res_norm['r2'] else "N/A"
    print(f"{'Alpha (power law)':<25} {a_raw:>12} {a_norm:>12}")
    print(f"{'R2':<25} {r_raw:>12} {r_norm:>12}")

    print(f"\nFirst 10 ACF values:")
    print(f"  {'Lag':<5} {'Raw':>12} {'Normalized':>12}")
    for i in range(10):
        print(f"  {i+1:<5} {res_raw['acf_first_10'][i]:>+12.6f} {res_norm['acf_first_10'][i]:>+12.6f}")

    # ============================================================
    # PART 2: Shuffled null baseline
    # ============================================================
    print(f"\n{'='*60}")
    print(f"PART 2: Shuffled baseline ({args.n_shuffles} surrogates)")
    print(f"{'='*60}")

    shuf_crossovers_raw = []
    shuf_crossovers_norm = []
    shuf_n_neg_raw = []
    shuf_n_neg_norm = []

    for i in range(args.n_shuffles):
        idx = np.random.permutation(N_gaps)
        sg_raw = gaps_raw[idx]
        sg_norm = gaps_norm[idx]

        acf_sr = compute_acf(sg_raw, max_lag)
        acf_sn = compute_acf(sg_norm, max_lag)

        pos_r = np.where(acf_sr > 0)[0]
        pos_n = np.where(acf_sn > 0)[0]
        shuf_crossovers_raw.append(int(pos_r[0] + 1) if len(pos_r) > 0 else max_lag + 1)
        shuf_crossovers_norm.append(int(pos_n[0] + 1) if len(pos_n) > 0 else max_lag + 1)
        shuf_n_neg_raw.append(int(np.sum(acf_sr < 0)))
        shuf_n_neg_norm.append(int(np.sum(acf_sn < 0)))

    print(f"  Shuffle crossover (raw):  median={np.median(shuf_crossovers_raw):.0f}, mean={np.mean(shuf_crossovers_raw):.1f}")
    print(f"  Shuffle crossover (norm): median={np.median(shuf_crossovers_norm):.0f}, mean={np.mean(shuf_crossovers_norm):.1f}")
    print(f"  Shuffle n_neg (raw):  mean={np.mean(shuf_n_neg_raw):.1f}/{max_lag}")
    print(f"  Shuffle n_neg (norm): mean={np.mean(shuf_n_neg_norm):.1f}/{max_lag}")

    z_crossover_raw = (res_raw['crossover_lag'] - np.mean(shuf_crossovers_raw)) / (np.std(shuf_crossovers_raw) + 1e-10)
    z_crossover_norm = (res_norm['crossover_lag'] - np.mean(shuf_crossovers_norm)) / (np.std(shuf_crossovers_norm) + 1e-10)
    z_nneg_raw = (res_raw['n_negative'] - np.mean(shuf_n_neg_raw)) / (np.std(shuf_n_neg_raw) + 1e-10)
    z_nneg_norm = (res_norm['n_negative'] - np.mean(shuf_n_neg_norm)) / (np.std(shuf_n_neg_norm) + 1e-10)

    print(f"  z-score crossover (raw): {z_crossover_raw:+.1f}")
    print(f"  z-score crossover (norm): {z_crossover_norm:+.1f}")
    print(f"  z-score n_neg (raw): {z_nneg_raw:+.1f}")
    print(f"  z-score n_neg (norm): {z_nneg_norm:+.1f}")

    # ============================================================
    # PART 3: Scale windows — stability
    # ============================================================
    print(f"\n{'='*60}")
    print("PART 3: ACF across 5 scale windows (100K gaps each)")
    print(f"{'='*60}")

    window_size = min(100_000, N_gaps // 6)
    n_windows = 5
    starts = np.linspace(0, N_gaps - window_size, n_windows).astype(int)

    print(f"\n{'Win':>3} {'ln(p)':>7} | {'X_raw':>5} {'Neg_r':>5} {'alpha_r':>8} {'R2_r':>6} | {'X_nrm':>5} {'Neg_n':>5} {'alpha_n':>8} {'R2_n':>6}")
    print("-" * 80)

    window_results = []
    for i, start in enumerate(starts):
        end = start + window_size
        wg_raw = gaps_raw[start:end]
        wg_norm = gaps_norm[start:end]
        p_center = primes[start + window_size // 2]
        ln_pc = float(np.log(float(p_center)))

        wr = analyze_acf(wg_raw, max_lag, f"win{i}_raw")
        wn = analyze_acf(wg_norm, max_lag, f"win{i}_norm")

        ar = f"{wr['alpha']:.3f}" if wr['alpha'] else "  N/A"
        rr = f"{wr['r2']:.3f}" if wr['r2'] else " N/A"
        an = f"{wn['alpha']:.3f}" if wn['alpha'] else "  N/A"
        rn = f"{wn['r2']:.3f}" if wn['r2'] else " N/A"

        print(f"{i:>3} {ln_pc:>7.2f} | {wr['crossover_lag']:>5} {wr['n_negative']:>5} {ar:>8} {rr:>6} | {wn['crossover_lag']:>5} {wn['n_negative']:>5} {an:>8} {rn:>6}")

        window_results.append({
            'window': i,
            'start': int(start),
            'ln_p': ln_pc,
            'raw': {k: v for k, v in wr.items() if k != 'acf_values'},
            'normalized': {k: v for k, v in wn.items() if k != 'acf_values'},
        })

    # ============================================================
    # PART 4: The dipolar/illusory decomposition
    # ============================================================
    print(f"\n{'='*60}")
    print("PART 4: Dipolar vs illusory decomposition")
    print(f"{'='*60}")

    # The ACF of raw gaps = ACF of (trend + local) = ACF(trend) + ACF(local) + cross
    # If we define trend = ln(p) and local = gap/ln(p) - 1, then:
    # raw_gap = ln(p) * (1 + local)
    # The positive ACF at long lags should come from the trend.
    # Let's measure it directly.

    acf_raw_full = np.array(res_raw['acf_values'])
    acf_norm_full = np.array(res_norm['acf_values'])
    acf_diff = acf_raw_full - acf_norm_full  # the "trend" contribution

    # Where does the dipolar (negative) component dominate?
    dipolar_lags = np.sum(acf_norm_full < 0)
    illusory_lags = np.sum(acf_diff > 0)

    print(f"  ACF(raw) = ACF(structural) + ACF(trend-induced)")
    print(f"  Structural (normalized) negative lags: {dipolar_lags}/{max_lag}")
    print(f"  Trend-induced positive contribution: at {illusory_lags}/{max_lag} lags")

    # At what lag does the trend contribution overtake the structural?
    for k in range(max_lag):
        if acf_norm_full[k] < 0 and acf_raw_full[k] > 0:
            print(f"  Trend overtakes structure at lag {k+1}: raw={acf_raw_full[k]:+.6f}, norm={acf_norm_full[k]:+.6f}")
            break

    # Sum of ACF (total correlation)
    sum_raw = float(np.sum(acf_raw_full))
    sum_norm = float(np.sum(acf_norm_full))
    sum_neg_raw = float(np.sum(acf_raw_full[acf_raw_full < 0]))
    sum_neg_norm = float(np.sum(acf_norm_full[acf_norm_full < 0]))

    print(f"\n  Total ACF sum (raw): {sum_raw:+.4f}")
    print(f"  Total ACF sum (norm): {sum_norm:+.4f}")
    print(f"  Negative-only sum (raw): {sum_neg_raw:+.4f}")
    print(f"  Negative-only sum (norm): {sum_neg_norm:+.4f}")

    # ============================================================
    # VERDICT
    # ============================================================
    print(f"\n{'='*60}")
    print("VERDICT")
    print(f"{'='*60}")

    norm_recovers = res_norm['n_negative'] > res_raw['n_negative'] * 2
    norm_all_neg = res_norm['n_negative'] >= max_lag - 5  # allow a few
    crossover_shifts = res_norm['crossover_lag'] > res_raw['crossover_lag'] * 2

    if norm_all_neg:
        print(f"  CONFIRMED: PNT-normalization recovers all-negative ACF ({res_norm['n_negative']}/{max_lag} negative)")
        print(f"  The positive ACF at lags 7+ in raw data is a NON-STATIONARITY ARTIFACT.")
        print(f"  ACF_1K_LAW holds on the normalized (stationary) gaps.")
        verdict = "CONFIRMED_NONSTATIONARITY"
    elif norm_recovers:
        print(f"  PARTIAL: Normalization increases negative lags ({res_raw['n_negative']}->{res_norm['n_negative']}) but not all.")
        print(f"  Non-stationarity explains PART of the sign flip, but structural positive ACF remains.")
        verdict = "PARTIAL"
    else:
        print(f"  FALSIFIED: Normalization does NOT recover negative lags ({res_raw['n_negative']}->{res_norm['n_negative']})")
        print(f"  The positive ACF at lags 7+ is STRUCTURAL, not an artifact.")
        verdict = "STRUCTURAL_POSITIVE"

    print(f"\n  Raw crossover: lag {res_raw['crossover_lag']}")
    print(f"  Normalized crossover: lag {res_norm['crossover_lag']}")
    print(f"  Normalization shifts crossover by factor {res_norm['crossover_lag']/max(res_raw['crossover_lag'],1):.1f}x")

    # ============================================================
    # Save results
    # ============================================================
    output = {
        'experiment': 'acf_stationarity',
        'date': '2026-04-17T08:03',
        'piano': 39,
        'n_primes': int(N),
        'n_gaps': int(N_gaps),
        'max_lag': max_lag,
        'n_shuffles': args.n_shuffles,
        'full_sequence': {
            'raw': {k: v for k, v in res_raw.items() if k != 'acf_values'},
            'normalized': {k: v for k, v in res_norm.items() if k != 'acf_values'},
        },
        'shuffle_baseline': {
            'crossover_raw_mean': float(np.mean(shuf_crossovers_raw)),
            'crossover_norm_mean': float(np.mean(shuf_crossovers_norm)),
            'n_neg_raw_mean': float(np.mean(shuf_n_neg_raw)),
            'n_neg_norm_mean': float(np.mean(shuf_n_neg_norm)),
            'z_crossover_raw': float(z_crossover_raw),
            'z_crossover_norm': float(z_crossover_norm),
            'z_n_neg_raw': float(z_nneg_raw),
            'z_n_neg_norm': float(z_nneg_norm),
        },
        'windows': window_results,
        'decomposition': {
            'dipolar_lags': int(dipolar_lags),
            'sum_acf_raw': sum_raw,
            'sum_acf_norm': sum_norm,
            'sum_neg_raw': sum_neg_raw,
            'sum_neg_norm': sum_neg_norm,
        },
        'verdict': verdict,
        'acf_raw': [float(x) for x in res_raw['acf_values']],
        'acf_norm': [float(x) for x in res_norm['acf_values']],
    }

    outpath = 'tools/data/exp_acf_stationarity.json'
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {outpath}")


if __name__ == '__main__':
    main()
