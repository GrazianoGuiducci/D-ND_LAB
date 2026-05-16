#!/usr/bin/env python3
"""
exp_markov_dipolar_decomposition.py — Is the prime dipolar angle a pair-statistics consequence?

The prime ordering signal has dL1/dSR = 2.28 at angle -111 deg.
GUE has dL1/dSR = 8.37 at angle -97 deg.

Question: does the ratio 2.28 follow from gap-pair correlations alone
(Lemke Oliver-Soundararajan territory), or does it require higher-order memory?

Method:
  1. Compute empirical transition matrix P(g_{n+1} | g_n) from real prime gaps
  2. Generate Markov-1 surrogate with that matrix (same pair stats, no higher memory)
  3. Generate Markov-0 surrogate (iid from marginal distribution)
  4. Compute dipolar angle for each: Markov-1, Markov-0, real primes
  5. Compare dL1/dSR across all three

If Markov-1 reproduces -111 deg and 2.28 → the ratio is pair-statistics
If not → higher-order correlations shape the dipolar direction

Usage:
    python tools/exp_markov_dipolar_decomposition.py [--N 100000] [--n_trials 30]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def get_primes(n_max):
    """Sieve of Eratosthenes."""
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def spacing_ratio(gaps):
    """Mean ratio min/max of consecutive gaps."""
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r[np.isfinite(r)])


def lag1_acf(gaps):
    """Lag-1 autocorrelation."""
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0:
        return 0.0
    return np.mean(g[:-1] * g[1:]) / c0


def shuffle_baseline(gaps, n_shuffle=200):
    """Shuffle mean of (SR, L1)."""
    sr_list, l1_list = [], []
    for _ in range(n_shuffle):
        sg = np.random.permutation(gaps)
        sr_list.append(spacing_ratio(sg))
        l1_list.append(lag1_acf(sg))
    return np.mean(sr_list), np.mean(l1_list), np.std(sr_list), np.std(l1_list)


def dipolar_vector(gaps, n_shuffle=200):
    """Compute dipolar angle and ratio relative to shuffle."""
    sr_real = spacing_ratio(gaps)
    l1_real = lag1_acf(gaps)
    sr_shuf, l1_shuf, sr_std, l1_std = shuffle_baseline(gaps, n_shuffle)
    dsr = sr_real - sr_shuf
    dl1 = l1_real - l1_shuf
    theta = np.degrees(np.arctan2(dl1, dsr))
    mag = np.sqrt(dsr**2 + dl1**2)
    ratio = abs(dl1 / dsr) if abs(dsr) > 1e-10 else float('inf')
    z_sr = dsr / sr_std if sr_std > 0 else 0
    z_l1 = dl1 / l1_std if l1_std > 0 else 0
    return {
        'theta': theta, 'magnitude': mag, 'dL1_over_dSR': ratio,
        'delta_SR': dsr, 'delta_L1': dl1,
        'SR_real': sr_real, 'L1_real': l1_real,
        'SR_shuf': sr_shuf, 'L1_shuf': l1_shuf,
        'z_SR': z_sr, 'z_L1': z_l1
    }


def build_transition_matrix(gaps, n_bins=None):
    """Build empirical transition matrix from gap sequence.

    Bins gaps into categories to get stable transition probabilities.
    Returns: (transition_matrix, bin_edges, stationary_dist)
    """
    if n_bins is None:
        # Use even gaps only (primes > 2 have even gaps)
        # Bin: 2, 4, 6, 8, 10, 12, 14+
        edges = [0, 3, 5, 7, 9, 11, 13, 1000]
        n_bins = len(edges) - 1
    else:
        # Quantile-based binning
        percentiles = np.linspace(0, 100, n_bins + 1)
        edges = np.unique(np.percentile(gaps, percentiles))
        edges[0] = 0
        edges[-1] = gaps.max() + 1
        n_bins = len(edges) - 1

    # Digitize gaps into bins
    bin_idx = np.digitize(gaps, edges) - 1
    bin_idx = np.clip(bin_idx, 0, n_bins - 1)

    # Build transition counts
    T = np.zeros((n_bins, n_bins), dtype=float)
    for i in range(len(bin_idx) - 1):
        T[bin_idx[i], bin_idx[i+1]] += 1

    # Normalize rows
    row_sums = T.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    T_norm = T / row_sums

    # Stationary distribution (empirical marginal)
    marginal = np.bincount(bin_idx, minlength=n_bins).astype(float)
    marginal /= marginal.sum()

    # Bin centers (representative gap values for each bin)
    centers = np.zeros(n_bins)
    for b in range(n_bins):
        mask = bin_idx == b
        if mask.any():
            centers[b] = np.mean(gaps[mask])
        else:
            centers[b] = (edges[b] + edges[b+1]) / 2

    return T_norm, edges, marginal, centers, bin_idx


def generate_markov1(T, marginal, centers, n_gaps, rng):
    """Generate a Markov-1 chain from transition matrix T.

    Uses bin centers as gap values, with small jitter within bin.
    """
    n_bins = len(marginal)
    gaps = np.zeros(n_gaps)

    # Start from stationary distribution
    state = rng.choice(n_bins, p=marginal)
    for i in range(n_gaps):
        gaps[i] = centers[state]
        # Transition
        state = rng.choice(n_bins, p=T[state])

    return gaps


def generate_markov0(marginal, centers, n_gaps, rng):
    """Generate iid from marginal distribution (Markov-0, no pair memory)."""
    states = rng.choice(len(marginal), size=n_gaps, p=marginal)
    return centers[states]


def run_experiment(N=100000, n_trials=30, n_shuffle=100):
    """Main experiment."""
    print("=" * 70)
    print("MARKOV DIPOLAR DECOMPOSITION")
    print("Is dL1/dSR = 2.28 a pair-statistics consequence?")
    print("=" * 70)

    # Generate primes
    print(f"\nGenerating primes (N={N} gaps, p > 10000)...")
    primes = get_primes(N * 25)
    mask = primes > 10000
    primes_f = primes[mask][:N + 1]
    real_gaps = np.diff(primes_f).astype(float)
    print(f"  Got {len(real_gaps)} prime gaps, range [{primes_f[0]}, {primes_f[-1]}]")

    # Build transition matrix
    print("\nBuilding transition matrix from real gaps...")
    T, edges, marginal, centers, bin_idx = build_transition_matrix(real_gaps)
    n_bins = len(marginal)
    print(f"  {n_bins} bins, edges: {[int(e) for e in edges]}")
    print(f"  Bin centers: {[f'{c:.1f}' for c in centers]}")
    print(f"  Marginal: {[f'{m:.3f}' for m in marginal]}")

    # Show transition matrix
    print("\n  Transition matrix (rows = from, cols = to):")
    for i in range(n_bins):
        row = " ".join(f"{T[i,j]:.3f}" for j in range(n_bins))
        print(f"    bin {i} (g~{centers[i]:.0f}): [{row}]")

    # Check: is T different from marginal repeated? (i.e., is there pair memory?)
    marginal_row = marginal[np.newaxis, :].repeat(n_bins, axis=0)
    pair_memory = np.sqrt(np.mean((T - marginal_row)**2))
    print(f"\n  Pair memory (RMSE T vs marginal): {pair_memory:.4f}")
    if pair_memory < 0.005:
        print("  WARNING: transition matrix ~ marginal. Markov-1 ≈ Markov-0.")

    # === Real primes ===
    print("\n--- REAL PRIMES ---")
    real_dv = dipolar_vector(real_gaps, n_shuffle=n_shuffle)
    print(f"  theta = {real_dv['theta']:.1f} deg, |d| = {real_dv['magnitude']:.4f}")
    print(f"  dL1/dSR = {real_dv['dL1_over_dSR']:.3f}")
    print(f"  delta_SR = {real_dv['delta_SR']:.4f}, delta_L1 = {real_dv['delta_L1']:.4f}")
    print(f"  z_SR = {real_dv['z_SR']:.1f}, z_L1 = {real_dv['z_L1']:.1f}")

    # === Markov-1 surrogates ===
    print(f"\n--- MARKOV-1 SURROGATES ({n_trials} trials) ---")
    m1_results = []
    for t in range(n_trials):
        rng = np.random.default_rng(1000 + t)
        m1_gaps = generate_markov1(T, marginal, centers, len(real_gaps), rng)
        dv = dipolar_vector(m1_gaps, n_shuffle=n_shuffle)
        m1_results.append(dv)
        if (t + 1) % 10 == 0:
            print(f"  Trial {t+1}: theta = {dv['theta']:.1f}, dL1/dSR = {dv['dL1_over_dSR']:.3f}")

    m1_thetas = np.array([r['theta'] for r in m1_results])
    m1_ratios = np.array([r['dL1_over_dSR'] for r in m1_results])
    m1_mags = np.array([r['magnitude'] for r in m1_results])
    print(f"\n  Markov-1: theta = {np.mean(m1_thetas):.1f} +/- {np.std(m1_thetas):.1f} deg")
    print(f"  Markov-1: dL1/dSR = {np.mean(m1_ratios):.3f} +/- {np.std(m1_ratios):.3f}")
    print(f"  Markov-1: |d| = {np.mean(m1_mags):.4f} +/- {np.std(m1_mags):.4f}")

    # === Markov-0 surrogates (iid from marginal) ===
    print(f"\n--- MARKOV-0 SURROGATES ({n_trials} trials) ---")
    m0_results = []
    for t in range(n_trials):
        rng = np.random.default_rng(2000 + t)
        m0_gaps = generate_markov0(marginal, centers, len(real_gaps), rng)
        dv = dipolar_vector(m0_gaps, n_shuffle=n_shuffle)
        m0_results.append(dv)
        if (t + 1) % 10 == 0:
            print(f"  Trial {t+1}: theta = {dv['theta']:.1f}, dL1/dSR = {dv['dL1_over_dSR']:.3f}")

    m0_thetas = np.array([r['theta'] for r in m0_results])
    m0_ratios = np.array([r['dL1_over_dSR'] for r in m0_results])
    m0_mags = np.array([r['magnitude'] for r in m0_results])
    print(f"\n  Markov-0: theta = {np.mean(m0_thetas):.1f} +/- {np.std(m0_thetas):.1f} deg")
    print(f"  Markov-0: dL1/dSR = {np.mean(m0_ratios):.3f} +/- {np.std(m0_ratios):.3f}")
    print(f"  Markov-0: |d| = {np.mean(m0_mags):.4f} +/- {np.std(m0_mags):.4f}")

    # === Scale dependence ===
    print("\n--- SCALE DEPENDENCE ---")
    scales = [
        (10000, 50000),
        (50000, 200000),
        (200000, 1000000),
        (1000000, 5000000),
    ]
    scale_results = []
    for lo, hi in scales:
        p_mask = (primes > lo) & (primes < hi)
        p_scale = primes[p_mask]
        if len(p_scale) < 100:
            continue
        g_scale = np.diff(p_scale).astype(float)

        # Real
        real_s = dipolar_vector(g_scale, n_shuffle=n_shuffle)

        # Build scale-specific transition matrix
        T_s, _, marg_s, cent_s, _ = build_transition_matrix(g_scale)

        # Markov-1 at this scale (5 trials for speed)
        m1_thetas_s = []
        m1_ratios_s = []
        for t in range(5):
            rng = np.random.default_rng(3000 + t)
            m1_g = generate_markov1(T_s, marg_s, cent_s, len(g_scale), rng)
            dv_s = dipolar_vector(m1_g, n_shuffle=50)
            m1_thetas_s.append(dv_s['theta'])
            m1_ratios_s.append(dv_s['dL1_over_dSR'])

        row = {
            'scale': f"{lo:.0e}-{hi:.0e}",
            'N_gaps': len(g_scale),
            'real_theta': real_s['theta'],
            'real_ratio': real_s['dL1_over_dSR'],
            'real_mag': real_s['magnitude'],
            'm1_theta': np.mean(m1_thetas_s),
            'm1_theta_std': np.std(m1_thetas_s),
            'm1_ratio': np.mean(m1_ratios_s),
            'm1_ratio_std': np.std(m1_ratios_s),
            'delta_theta': real_s['theta'] - np.mean(m1_thetas_s),
        }
        scale_results.append(row)
        print(f"  {row['scale']} ({row['N_gaps']} gaps):")
        print(f"    Real:    theta={row['real_theta']:.1f}, dL1/dSR={row['real_ratio']:.3f}")
        print(f"    Markov1: theta={row['m1_theta']:.1f}+/-{row['m1_theta_std']:.1f}, "
              f"dL1/dSR={row['m1_ratio']:.3f}+/-{row['m1_ratio_std']:.3f}")
        print(f"    Delta theta = {row['delta_theta']:.1f} deg")

    # === Summary ===
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Source':<14} {'theta (deg)':<20} {'dL1/dSR':<16} {'|d|':<12}")
    print("-" * 62)
    print(f"{'Real primes':<14} {real_dv['theta']:>7.1f}{'':>13} "
          f"{real_dv['dL1_over_dSR']:<16.3f} {real_dv['magnitude']:<12.4f}")
    print(f"{'Markov-1':<14} {np.mean(m1_thetas):>7.1f} +/- {np.std(m1_thetas):>5.1f}  "
          f"{np.mean(m1_ratios):<6.3f} +/- {np.std(m1_ratios):<6.3f} "
          f"{np.mean(m1_mags):<12.4f}")
    print(f"{'Markov-0':<14} {np.mean(m0_thetas):>7.1f} +/- {np.std(m0_thetas):>5.1f}  "
          f"{np.mean(m0_ratios):<6.3f} +/- {np.std(m0_ratios):<6.3f} "
          f"{np.mean(m0_mags):<12.4f}")

    theta_gap = real_dv['theta'] - np.mean(m1_thetas)
    while theta_gap > 180: theta_gap -= 360
    while theta_gap < -180: theta_gap += 360
    z_theta = abs(theta_gap) / max(np.std(m1_thetas), 0.1)

    ratio_gap = real_dv['dL1_over_dSR'] - np.mean(m1_ratios)
    z_ratio = abs(ratio_gap) / max(np.std(m1_ratios), 0.001)

    print(f"\n  Angle gap (real - Markov1): {theta_gap:.1f} deg (z = {z_theta:.1f})")
    print(f"  Ratio gap (real - Markov1): {ratio_gap:.3f} (z = {z_ratio:.1f})")

    if z_theta < 2:
        print("\n  RESULT: Markov-1 REPRODUCES the prime dipolar angle.")
        print("  The ratio 2.28 is a pair-statistics consequence.")
    else:
        print(f"\n  RESULT: Markov-1 does NOT reproduce the prime angle (z={z_theta:.1f}).")
        print("  Higher-order correlations shape the dipolar direction.")

    # Save results
    output = {
        'real': {k: float(v) for k, v in real_dv.items()},
        'markov1': {
            'theta_mean': float(np.mean(m1_thetas)),
            'theta_std': float(np.std(m1_thetas)),
            'ratio_mean': float(np.mean(m1_ratios)),
            'ratio_std': float(np.std(m1_ratios)),
            'mag_mean': float(np.mean(m1_mags)),
        },
        'markov0': {
            'theta_mean': float(np.mean(m0_thetas)),
            'theta_std': float(np.std(m0_thetas)),
            'ratio_mean': float(np.mean(m0_ratios)),
            'ratio_std': float(np.std(m0_ratios)),
            'mag_mean': float(np.mean(m0_mags)),
        },
        'pair_memory_rmse': float(pair_memory),
        'z_theta': float(z_theta),
        'z_ratio': float(z_ratio),
        'scales': scale_results,
        'n_gaps': len(real_gaps),
        'n_trials': n_trials,
        'transition_matrix': T.tolist(),
        'bin_centers': centers.tolist(),
        'marginal': marginal.tolist(),
    }

    out_path = Path(__file__).parent / "data" / "markov_dipolar_decomposition.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=100000)
    parser.add_argument('--n_trials', type=int, default=30)
    parser.add_argument('--n_shuffle', type=int, default=100)
    args = parser.parse_args()

    np.random.seed(42)
    run_experiment(N=args.N, n_trials=args.n_trials, n_shuffle=args.n_shuffle)
