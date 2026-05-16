#!/usr/bin/env python3
"""
exp_two_channel_cross_domain.py — Two-Channel Decomposition Across Domains

Question: Is the scale-invariant algebraic channel unique to primes (C1)?

The last 3 runs established that primes have TWO channels:
  1. Algebraic (mod-6 residue / mod-3 prohibition): scale-invariant, z=26-44 sigma
  2. Statistical (magnitude): decays slowly toward Poisson

C1 claims primes are the only dynamic domain under M among 7 tested.
This experiment tests whether OTHER gap sequences also show a scale-invariant
algebraic channel, or whether that property is unique to primes.

Domains:
  - Primes: reference (known two-channel)
  - GUE eigenvalues: random matrix, strong statistical correlation, no arithmetic
  - Cramer random primes: same density as primes, no sieve correlations

For each domain, at multiple scales, we measure:
  - r-statistic (combined channel)
  - Binary channel ACF (mod-6 for primes, above/below-median for others)
  - Magnitude channel ACF (gap minus conditional mean)
  - Z-scores vs shuffle
  - Whether z-scores decay with scale or stay constant

If GUE shows only decaying channels → C1 supported (algebraic invariance is prime-specific)
If GUE shows a scale-invariant channel → C1 needs refinement

Usage:
    python tools/exp_two_channel_cross_domain.py [--n_primes N] [--gue_size N] [--n_windows N]
"""

import argparse
import numpy as np
import json
from pathlib import Path
from datetime import datetime


def sieve_primes(limit):
    """Sieve of Eratosthenes."""
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def get_primes(n_target):
    """Get at least n_target primes."""
    limit = int(n_target * (np.log(n_target) + np.log(np.log(n_target)) + 2))
    limit = max(limit, 1000)
    primes = sieve_primes(limit)
    while len(primes) < n_target:
        limit = int(limit * 1.5)
        primes = sieve_primes(limit)
    return primes[:n_target]


def gue_eigenvalues(n_matrices, matrix_size):
    """Generate unfolded spacings from GUE random matrices."""
    all_spacings = []
    for _ in range(n_matrices):
        # GUE: H = (A + A^*) / (2 * sqrt(2N)), A is complex Gaussian
        A = (np.random.randn(matrix_size, matrix_size)
             + 1j * np.random.randn(matrix_size, matrix_size)) / np.sqrt(2)
        H = (A + A.conj().T) / (2 * np.sqrt(2 * matrix_size))
        evals = np.sort(np.linalg.eigvalsh(H))
        # Unfold using semicircle law: rho(x) = (2/pi) * sqrt(1 - x^2) for |x| < 1
        # Use only the bulk (avoid edges)
        bulk = evals[matrix_size // 5: 4 * matrix_size // 5]
        spacings = np.diff(bulk)
        # Local unfolding
        if len(spacings) > 50:
            window = min(50, len(spacings) // 5)
            local_mean = np.convolve(spacings, np.ones(window)/window, mode='same')
            local_mean[local_mean < 1e-15] = np.mean(spacings)
            spacings = spacings / local_mean
        all_spacings.extend(spacings.tolist())
    return np.array(all_spacings)


def cramer_random_primes(n_primes):
    """Cramer model: each odd n is 'prime' with probability 2/ln(n)."""
    result = [2, 3]
    n = 5
    while len(result) < n_primes:
        if np.random.random() < 2.0 / np.log(n):
            result.append(n)
        n += 2
    return np.array(result[:n_primes])


def r_statistic(gaps):
    """Mean consecutive gap ratio min/max."""
    if len(gaps) < 2:
        return np.nan
    g = gaps.astype(float)
    mask = g[1:] > 0
    r = np.minimum(g[:-1][mask], g[1:][mask]) / np.maximum(g[:-1][mask], g[1:][mask])
    return np.nanmean(r) if len(r) > 0 else np.nan


def lag1_acf(x):
    """Lag-1 autocorrelation."""
    if len(x) < 3:
        return np.nan
    x = x - np.mean(x)
    v = np.var(x)
    if v < 1e-15:
        return np.nan
    return np.mean(x[:-1] * x[1:]) / v


def decompose_primes(primes_window):
    """Decompose prime gaps into algebraic (mod-6) and magnitude channels."""
    p = primes_window[primes_window > 3]
    if len(p) < 100:
        return None, None, None
    gaps = np.diff(p).astype(float)
    residues = p[:-1] % 6

    # Algebraic channel: mod-6 residue as binary +1/-1
    binary = np.where(residues == 1, 1.0, -1.0)

    # Magnitude channel: gap demeaned by transition type
    residues_right = p[1:] % 6
    transition = residues * 10 + residues_right
    mag = gaps.copy()
    for tt in np.unique(transition):
        mask = transition == tt
        if mask.sum() > 1:
            mag[mask] -= mag[mask].mean()

    return gaps, binary, mag


def decompose_generic(gaps):
    """Decompose any gap sequence into binary (above/below median) and magnitude."""
    if len(gaps) < 100:
        return None, None, None
    gaps = gaps.astype(float)
    gaps = gaps[gaps > 0]
    if len(gaps) < 100:
        return None, None, None

    median = np.median(gaps)
    # Binary channel: +1 if above median, -1 if below
    binary = np.where(gaps > median, 1.0, -1.0)

    # Magnitude channel: gap demeaned by binary class
    mag = gaps.copy()
    for b_val in [1.0, -1.0]:
        mask = binary == b_val
        if mask.sum() > 1:
            mag[mask] -= mag[mask].mean()

    return gaps, binary, mag


def analyze_at_scale(gaps, binary, mag, n_surrogates=30, rng=None):
    """Analyze one window: real observables + shuffle null."""
    if rng is None:
        rng = np.random.default_rng()

    real = {
        'r': r_statistic(gaps),
        'acf_binary': lag1_acf(binary),
        'acf_mag': lag1_acf(mag),
    }

    # Shuffle null: permute gaps, recompute binary and magnitude
    shuf_r, shuf_bin, shuf_mag = [], [], []
    for _ in range(n_surrogates):
        sg = rng.permutation(gaps)
        median = np.median(sg)
        sb = np.where(sg > median, 1.0, -1.0)
        sm = sg.copy()
        for b_val in [1.0, -1.0]:
            mask = sb == b_val
            if mask.sum() > 1:
                sm[mask] -= sm[mask].mean()
        shuf_r.append(r_statistic(sg))
        shuf_bin.append(lag1_acf(sb))
        shuf_mag.append(lag1_acf(sm))

    def z(val, arr):
        arr = np.array(arr)
        arr = arr[np.isfinite(arr)]
        if len(arr) < 3:
            return 0.0
        s = np.std(arr)
        if s < 1e-15:
            return 0.0
        return (val - np.mean(arr)) / s

    real['z_r'] = z(real['r'], shuf_r)
    real['z_binary'] = z(real['acf_binary'], shuf_bin)
    real['z_mag'] = z(real['acf_mag'], shuf_mag)
    real['shuf_r_mean'] = float(np.nanmean(shuf_r))
    real['shuf_bin_mean'] = float(np.nanmean(shuf_bin))
    real['shuf_mag_mean'] = float(np.nanmean(shuf_mag))

    return real


def analyze_at_scale_primes(primes_window, n_surrogates=30, rng=None):
    """Like analyze_at_scale but using prime-specific mod-6 decomposition."""
    if rng is None:
        rng = np.random.default_rng()

    gaps, binary, mag = decompose_primes(primes_window)
    if gaps is None:
        return None

    real = {
        'r': r_statistic(gaps),
        'acf_binary': lag1_acf(binary),
        'acf_mag': lag1_acf(mag),
    }

    # Shuffle: permute gaps, reconstruct fake primes, decompose
    p = primes_window[primes_window > 3]
    shuf_r, shuf_bin, shuf_mag = [], [], []
    for _ in range(n_surrogates):
        sg = rng.permutation(gaps)
        # Binary from shuffle: above/below median (mod-6 is destroyed)
        median = np.median(sg)
        sb = np.where(sg > median, 1.0, -1.0)
        sm = sg.copy()
        for b_val in [1.0, -1.0]:
            mask = sb == b_val
            if mask.sum() > 1:
                sm[mask] -= sm[mask].mean()
        shuf_r.append(r_statistic(sg))
        shuf_bin.append(lag1_acf(sb))
        shuf_mag.append(lag1_acf(sm))

    def z(val, arr):
        arr = np.array(arr)
        arr = arr[np.isfinite(arr)]
        if len(arr) < 3:
            return 0.0
        s = np.std(arr)
        if s < 1e-15:
            return 0.0
        return (val - np.mean(arr)) / s

    real['z_r'] = z(real['r'], shuf_r)
    real['z_binary'] = z(real['acf_binary'], shuf_bin)
    real['z_mag'] = z(real['acf_mag'], shuf_mag)
    real['shuf_r_mean'] = float(np.nanmean(shuf_r))
    real['shuf_bin_mean'] = float(np.nanmean(shuf_bin))
    real['shuf_mag_mean'] = float(np.nanmean(shuf_mag))

    # Also measure mod-3 self-transition
    residues = p[:-1] % 6
    m3 = np.where(residues == 1, 1, 2)
    real['mod3_self'] = float(np.mean(m3[:-1] == m3[1:]))

    return real


def run(n_primes=200000, gue_matrices=50, gue_size=800, n_windows=8, window=5000, n_surrogates=20):
    """Main experiment."""
    rng = np.random.default_rng(42)
    results = {}

    # === PRIMES ===
    print("=== PRIMES ===")
    primes = get_primes(n_primes)
    print(f"Got {len(primes)} primes up to {primes[-1]}")

    max_start = len(primes) - window - 10
    starts = np.unique(np.logspace(1, np.log10(max_start), n_windows).astype(int))
    starts = starts[starts < max_start]

    prime_results = []
    for s in starts:
        pw = primes[s:s + window]
        obs = analyze_at_scale_primes(pw, n_surrogates, rng)
        if obs:
            obs['start_idx'] = int(s)
            obs['mean_value'] = float(np.mean(pw))
            prime_results.append(obs)
            print(f"  idx={s:>6d} <p>={obs['mean_value']:>10.0f} "
                  f"r={obs['r']:.4f} acf_bin={obs['acf_binary']:.4f} acf_mag={obs['acf_mag']:.4f} "
                  f"| z_r={obs['z_r']:>6.1f} z_bin={obs['z_binary']:>6.1f} z_mag={obs['z_mag']:>6.1f} "
                  f"mod3_self={obs['mod3_self']:.4f}")

    results['primes'] = prime_results

    # === GUE EIGENVALUES ===
    print(f"\n=== GUE EIGENVALUES ({gue_matrices} matrices of size {gue_size}) ===")
    gue_spacings = gue_eigenvalues(gue_matrices, gue_size)
    print(f"Got {len(gue_spacings)} GUE spacings, mean={np.mean(gue_spacings):.3f}")

    # Analyze at different scales (positions along the concatenated sequence)
    gue_max_start = len(gue_spacings) - window - 10
    gue_starts = np.unique(np.logspace(1, np.log10(max(gue_max_start, 100)), n_windows).astype(int))
    gue_starts = gue_starts[gue_starts < gue_max_start]

    gue_results = []
    for s in gue_starts:
        gw = gue_spacings[s:s + window]
        gaps, binary, mag = decompose_generic(gw)
        if gaps is None:
            continue
        obs = analyze_at_scale(gaps, binary, mag, n_surrogates, rng)
        obs['start_idx'] = int(s)
        obs['mean_value'] = float(s)  # position in concatenated sequence
        gue_results.append(obs)
        print(f"  idx={s:>6d} "
              f"r={obs['r']:.4f} acf_bin={obs['acf_binary']:.4f} acf_mag={obs['acf_mag']:.4f} "
              f"| z_r={obs['z_r']:>6.1f} z_bin={obs['z_binary']:>6.1f} z_mag={obs['z_mag']:>6.1f}")

    results['gue'] = gue_results

    # === CRAMER RANDOM PRIMES ===
    print(f"\n=== CRAMER RANDOM PRIMES ===")
    cramer = cramer_random_primes(n_primes)
    cramer_gaps = np.diff(cramer).astype(float)
    print(f"Got {len(cramer)} Cramer primes, mean gap={np.mean(cramer_gaps):.2f}")

    cramer_max_start = len(cramer_gaps) - window - 10
    cramer_starts = np.unique(np.logspace(1, np.log10(max(cramer_max_start, 100)), n_windows).astype(int))
    cramer_starts = cramer_starts[cramer_starts < cramer_max_start]

    cramer_results = []
    for s in cramer_starts:
        cw = cramer_gaps[s:s + window]
        gaps, binary, mag = decompose_generic(cw)
        if gaps is None:
            continue
        obs = analyze_at_scale(gaps, binary, mag, n_surrogates, rng)
        obs['start_idx'] = int(s)
        obs['mean_value'] = float(cramer[s])
        cramer_results.append(obs)
        print(f"  idx={s:>6d} <n>={obs['mean_value']:>10.0f} "
              f"r={obs['r']:.4f} acf_bin={obs['acf_binary']:.4f} acf_mag={obs['acf_mag']:.4f} "
              f"| z_r={obs['z_r']:>6.1f} z_bin={obs['z_binary']:>6.1f} z_mag={obs['z_mag']:>6.1f}")

    results['cramer'] = cramer_results

    return results


def compute_summary(results):
    """Extract scale-dependence of z-scores for each domain."""
    summary = {}
    for domain, data in results.items():
        if not data:
            continue
        z_r = [d['z_r'] for d in data]
        z_bin = [d['z_binary'] for d in data]
        z_mag = [d['z_mag'] for d in data]
        positions = [d['start_idx'] for d in data]

        # Correlation of z-scores with position (proxy for scale)
        log_pos = np.log(np.array(positions) + 1)

        def corr(x, y):
            x, y = np.array(x), np.array(y)
            valid = np.isfinite(x) & np.isfinite(y)
            if valid.sum() < 3:
                return float('nan')
            return float(np.corrcoef(x[valid], y[valid])[0, 1])

        summary[domain] = {
            'n_windows': len(data),
            'z_r_mean': float(np.nanmean(z_r)),
            'z_r_std': float(np.nanstd(z_r)),
            'z_binary_mean': float(np.nanmean(z_bin)),
            'z_binary_std': float(np.nanstd(z_bin)),
            'z_mag_mean': float(np.nanmean(z_mag)),
            'z_mag_std': float(np.nanstd(z_mag)),
            'decay_corr_r': corr(log_pos, z_r),
            'decay_corr_binary': corr(log_pos, z_bin),
            'decay_corr_mag': corr(log_pos, z_mag),
            'z_r_range': [float(np.nanmin(z_r)), float(np.nanmax(z_r))],
            'z_binary_range': [float(np.nanmin(z_bin)), float(np.nanmax(z_bin))],
            'z_mag_range': [float(np.nanmin(z_mag)), float(np.nanmax(z_mag))],
        }

    return summary


def print_comparison(summary):
    """Print comparison table."""
    print("\n" + "=" * 100)
    print("CROSS-DOMAIN COMPARISON: Two-Channel Scale Invariance")
    print("=" * 100)
    print(f"{'Domain':>12} | {'<z_r>':>7} {'<z_bin>':>8} {'<z_mag>':>8} | "
          f"{'corr_r':>7} {'corr_bin':>8} {'corr_mag':>8} | "
          f"{'bin_range':>16} {'mag_range':>16}")
    print("-" * 100)
    for domain, s in summary.items():
        print(f"{domain:>12} | "
              f"{s['z_r_mean']:>7.1f} {s['z_binary_mean']:>8.1f} {s['z_mag_mean']:>8.1f} | "
              f"{s['decay_corr_r']:>7.3f} {s['decay_corr_binary']:>8.3f} {s['decay_corr_mag']:>8.3f} | "
              f"[{s['z_binary_range'][0]:>5.1f},{s['z_binary_range'][1]:>5.1f}] "
              f"[{s['z_mag_range'][0]:>5.1f},{s['z_mag_range'][1]:>5.1f}]")

    print("\n--- Interpretation Guide ---")
    print("z > 3: signal significant vs shuffle")
    print("corr ~ 0: scale-invariant (z does NOT decay with position)")
    print("corr < -0.5: decaying (z weakens at larger scale)")
    print("corr > 0.5: strengthening (unusual)")
    print("\nC1 test: primes should show scale-invariant binary channel (corr_bin ~ 0, high z_bin)")
    print("         GUE/Cramer should show decaying or absent binary channel")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=200000)
    parser.add_argument('--gue_matrices', type=int, default=50)
    parser.add_argument('--gue_size', type=int, default=800)
    parser.add_argument('--n_windows', type=int, default=8)
    parser.add_argument('--window', type=int, default=5000)
    parser.add_argument('--n_surrogates', type=int, default=20)
    args = parser.parse_args()

    results = run(args.n_primes, args.gue_matrices, args.gue_size,
                  args.n_windows, args.window, args.n_surrogates)
    summary = compute_summary(results)
    print_comparison(summary)

    # Save
    out = {
        'experiment': 'two_channel_cross_domain',
        'timestamp': datetime.now().isoformat(),
        'question': 'Is the scale-invariant algebraic channel unique to primes?',
        'params': {
            'n_primes': args.n_primes,
            'gue_matrices': args.gue_matrices,
            'gue_size': args.gue_size,
            'n_windows': args.n_windows,
            'window': args.window,
            'n_surrogates': args.n_surrogates,
        },
        'summary': summary,
        'raw': {k: v for k, v in results.items()},
    }
    out_path = Path('tools/data/two_channel_cross_domain.json')
    out_path.write_text(json.dumps(out, indent=2, default=lambda x: None if not np.isfinite(x) else x))
    print(f"\nSaved to {out_path}")
