#!/usr/bin/env python3
"""
exp_two_channel_boundary.py — Two-Channel Boundary Separation

Question: Do the residue and magnitude channels of prime gaps lose their
structure at the same scale, or at different scales?

Consecutio from:
  - Mod-3 prohibition (agent_20260425): algebraic memory in ordering channel
  - Brody calibration (agent_20260427): 7.8% artifact floor, r is faithful
  - Spectral rigidity (agent_20260428): scale-dependent two-channel structure

Method:
  Fix window size W (number of consecutive gaps). Slide start index across
  the prime number line. In each window measure:
    1. Raw gap r-statistic (overall structure level)
    2. Residue channel: lag-1 autocorrelation of Z/6Z binary sequence
    3. Magnitude channel: lag-1 autocorrelation of demeaned gaps
    4. Mod-3 self-transition fraction (algebraic memory marker)

  Null: shuffle gaps within each window, recompute all four.
  The shuffle preserves marginal distribution but destroys sequential memory.

  If the channels have different scale-decay profiles, the boundary between
  GUE-like and Poisson-like regimes is channel-specific.

Usage:
    python tools/exp_two_channel_boundary.py [--n_primes N] [--window W] [--n_surrogates S]
"""

import argparse
import numpy as np
import json
from pathlib import Path


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


def r_statistic(gaps):
    """Consecutive gap ratio <min/max>."""
    if len(gaps) < 2:
        return np.nan
    g = gaps.astype(float)
    r = np.minimum(g[:-1], g[1:]) / np.maximum(g[:-1], g[1:])
    return np.nanmean(r[np.isfinite(r)])


def lag1_acf(x):
    """Lag-1 autocorrelation."""
    if len(x) < 3:
        return np.nan
    x = x - np.mean(x)
    v = np.var(x)
    if v < 1e-15:
        return np.nan
    return np.mean(x[:-1] * x[1:]) / v


def mod3_self_fraction(residues_6):
    """Fraction of consecutive primes where (p mod 3) repeats.
    For primes > 3, p mod 6 in {1,5}. Map to mod 3: 1->1, 5->2.
    Self-transition = same mod-3 class in a row."""
    m3 = np.where(residues_6 == 1, 1, 2)
    if len(m3) < 2:
        return np.nan
    self_trans = np.sum(m3[:-1] == m3[1:])
    return self_trans / (len(m3) - 1)


def analyze_window(primes_window):
    """Analyze a window of primes, return all four observables."""
    p = primes_window[primes_window > 3]
    if len(p) < 100:
        return None

    gaps = np.diff(p).astype(float)
    residues = p[:-1] % 6
    residue_right = p[1:] % 6

    # Residue channel: binary +1/-1
    res_channel = np.where(residues == 1, 1.0, -1.0)

    # Magnitude channel: gap demeaned by transition type
    transition = residues * 10 + residue_right
    mag_channel = gaps.copy()
    for tt in np.unique(transition):
        mask = transition == tt
        mag_channel[mask] -= mag_channel[mask].mean()

    return {
        'r_stat': r_statistic(gaps),
        'acf1_residue': lag1_acf(res_channel),
        'acf1_magnitude': lag1_acf(mag_channel),
        'mod3_self': mod3_self_fraction(residues),
        'mean_prime': np.mean(p).item(),
        'mean_gap': np.mean(gaps).item(),
        'n_gaps': len(gaps),
    }


def analyze_shuffled(primes_window, rng):
    """Shuffle gaps, reconstruct primes, analyze."""
    p = primes_window[primes_window > 3]
    if len(p) < 100:
        return None
    gaps = np.diff(p).astype(float)
    shuffled_gaps = rng.permutation(gaps)
    # Reconstruct primes from shuffled gaps (preserves distribution, destroys order)
    fake_primes = np.concatenate([[p[0]], p[0] + np.cumsum(shuffled_gaps)])
    fake_primes = fake_primes.astype(int)
    # Residues of fake primes (not constrained to {1,5} mod 6!)
    residues = fake_primes[:-1] % 6
    residue_right = fake_primes[1:] % 6

    res_channel = np.where(residues == 1, 1.0,
                  np.where(residues == 5, -1.0, 0.0))
    transition = residues * 10 + residue_right
    mag_channel = shuffled_gaps.copy()
    for tt in np.unique(transition):
        mask = transition == tt
        if mask.sum() > 1:
            mag_channel[mask] -= mag_channel[mask].mean()

    return {
        'r_stat': r_statistic(shuffled_gaps),
        'acf1_residue': lag1_acf(res_channel),
        'acf1_magnitude': lag1_acf(mag_channel),
        'mod3_self': mod3_self_fraction(residues),
    }


def run(n_primes=500000, window=5000, n_surrogates=20):
    """Main experiment."""
    print(f"Sieving {n_primes} primes...")
    primes = get_primes(n_primes)
    print(f"Got {len(primes)} primes up to {primes[-1]}")

    # Define window start indices - logarithmically spaced
    max_start = len(primes) - window - 10
    n_windows = 30
    starts = np.unique(np.logspace(0, np.log10(max_start), n_windows).astype(int))
    starts = starts[starts < max_start]

    rng = np.random.default_rng(42)

    results = []
    print(f"Analyzing {len(starts)} windows of size {window}...")
    for i, s in enumerate(starts):
        pw = primes[s:s+window]
        obs = analyze_window(pw)
        if obs is None:
            continue

        # Surrogates
        shuf_r = []
        shuf_acf_res = []
        shuf_acf_mag = []
        shuf_mod3 = []
        for _ in range(n_surrogates):
            sh = analyze_shuffled(pw, rng)
            if sh is None:
                continue
            shuf_r.append(sh['r_stat'])
            shuf_acf_res.append(sh['acf1_residue'])
            shuf_acf_mag.append(sh['acf1_magnitude'])
            shuf_mod3.append(sh['mod3_self'])

        obs['shuffle_r_mean'] = np.nanmean(shuf_r)
        obs['shuffle_r_std'] = np.nanstd(shuf_r)
        obs['shuffle_acf_res_mean'] = np.nanmean(shuf_acf_res)
        obs['shuffle_acf_res_std'] = np.nanstd(shuf_acf_res)
        obs['shuffle_acf_mag_mean'] = np.nanmean(shuf_acf_mag)
        obs['shuffle_acf_mag_std'] = np.nanstd(shuf_acf_mag)
        obs['shuffle_mod3_mean'] = np.nanmean(shuf_mod3)
        obs['shuffle_mod3_std'] = np.nanstd(shuf_mod3)

        # Z-scores (signal relative to null)
        def zscore(val, mu, sig):
            if sig < 1e-15:
                return 0.0
            return (val - mu) / sig

        obs['z_r'] = zscore(obs['r_stat'], obs['shuffle_r_mean'], obs['shuffle_r_std'])
        obs['z_acf_res'] = zscore(obs['acf1_residue'], obs['shuffle_acf_res_mean'], obs['shuffle_acf_res_std'])
        obs['z_acf_mag'] = zscore(obs['acf1_magnitude'], obs['shuffle_acf_mag_mean'], obs['shuffle_acf_mag_std'])
        obs['z_mod3'] = zscore(obs['mod3_self'], obs['shuffle_mod3_mean'], obs['shuffle_mod3_std'])

        results.append(obs)

        if (i + 1) % 5 == 0 or i == 0:
            print(f"  Window {i+1}/{len(starts)}: start_idx={s}, "
                  f"<p>={obs['mean_prime']:.0f}, "
                  f"r={obs['r_stat']:.4f}, "
                  f"acf_res={obs['acf1_residue']:.4f}, "
                  f"acf_mag={obs['acf1_magnitude']:.4f}, "
                  f"mod3_self={obs['mod3_self']:.4f}")

    return results


def print_table(results):
    """Print results table."""
    print("\n" + "="*120)
    print(f"{'<p>':>12} {'r':>7} {'r_shuf':>7} {'z_r':>7} | "
          f"{'acf_res':>8} {'shuf':>8} {'z_res':>7} | "
          f"{'acf_mag':>8} {'shuf':>8} {'z_mag':>7} | "
          f"{'mod3':>6} {'shuf':>6} {'z_mod3':>7}")
    print("-"*120)
    for r in results:
        print(f"{r['mean_prime']:>12.0f} "
              f"{r['r_stat']:>7.4f} {r['shuffle_r_mean']:>7.4f} {r['z_r']:>7.1f} | "
              f"{r['acf1_residue']:>8.4f} {r['shuffle_acf_res_mean']:>8.4f} {r['z_acf_res']:>7.1f} | "
              f"{r['acf1_magnitude']:>8.4f} {r['shuffle_acf_mag_mean']:>8.4f} {r['z_acf_mag']:>7.1f} | "
              f"{r['mod3_self']:>6.4f} {r['shuffle_mod3_mean']:>6.4f} {r['z_mod3']:>7.1f}")


def compute_summary(results):
    """Extract key findings from results."""
    # Check if z-scores decay with scale
    mean_primes = [r['mean_prime'] for r in results]
    z_r = [r['z_r'] for r in results]
    z_res = [r['z_acf_res'] for r in results]
    z_mag = [r['z_acf_mag'] for r in results]
    z_mod3 = [r['z_mod3'] for r in results]

    # Split into first half / second half
    mid = len(results) // 2
    summary = {
        'n_windows': len(results),
        'prime_range': [results[0]['mean_prime'], results[-1]['mean_prime']],
        'z_r_early': np.mean(z_r[:mid]),
        'z_r_late': np.mean(z_r[mid:]),
        'z_acf_res_early': np.mean(z_res[:mid]),
        'z_acf_res_late': np.mean(z_res[mid:]),
        'z_acf_mag_early': np.mean(z_mag[:mid]),
        'z_acf_mag_late': np.mean(z_mag[mid:]),
        'z_mod3_early': np.mean(z_mod3[:mid]),
        'z_mod3_late': np.mean(z_mod3[mid:]),
        'r_stat_range': [results[0]['r_stat'], results[-1]['r_stat']],
        'acf_res_range': [results[0]['acf1_residue'], results[-1]['acf1_residue']],
        'acf_mag_range': [results[0]['acf1_magnitude'], results[-1]['acf1_magnitude']],
        'mod3_self_range': [results[0]['mod3_self'], results[-1]['mod3_self']],
    }

    # Correlation of z-scores with log(mean_prime) — decay rate
    log_p = np.log(mean_primes)
    for name, z_arr in [('r', z_r), ('acf_res', z_res), ('acf_mag', z_mag), ('mod3', z_mod3)]:
        valid = np.isfinite(z_arr) & np.isfinite(log_p)
        if np.sum(valid) > 3:
            corr = np.corrcoef(np.array(log_p)[valid], np.array(z_arr)[valid])[0, 1]
            summary[f'decay_corr_{name}'] = corr
        else:
            summary[f'decay_corr_{name}'] = np.nan

    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=500000)
    parser.add_argument('--window', type=int, default=5000)
    parser.add_argument('--n_surrogates', type=int, default=20)
    args = parser.parse_args()

    results = run(args.n_primes, args.window, args.n_surrogates)
    print_table(results)
    summary = compute_summary(results)

    print("\n=== SUMMARY ===")
    print(f"Prime range: {summary['prime_range'][0]:.0f} to {summary['prime_range'][1]:.0f}")
    print(f"\nZ-scores (early vs late halves of prime range):")
    print(f"  r-statistic:     {summary['z_r_early']:>7.1f} → {summary['z_r_late']:>7.1f}")
    print(f"  Residue ACF-1:   {summary['z_acf_res_early']:>7.1f} → {summary['z_acf_res_late']:>7.1f}")
    print(f"  Magnitude ACF-1: {summary['z_acf_mag_early']:>7.1f} → {summary['z_acf_mag_late']:>7.1f}")
    print(f"  Mod-3 self-frac: {summary['z_mod3_early']:>7.1f} → {summary['z_mod3_late']:>7.1f}")
    print(f"\nDecay correlation with ln(p):")
    print(f"  r-statistic:     {summary['decay_corr_r']:>7.3f}")
    print(f"  Residue ACF-1:   {summary['decay_corr_acf_res']:>7.3f}")
    print(f"  Magnitude ACF-1: {summary['decay_corr_acf_mag']:>7.3f}")
    print(f"  Mod-3 self-frac: {summary['decay_corr_mod3']:>7.3f}")

    # Save
    out_path = Path('tools/data/two_channel_boundary.json')
    out = {
        'experiment': 'two_channel_boundary',
        'question': 'Do residue and magnitude channels lose structure at the same scale?',
        'n_primes': args.n_primes,
        'window': args.window,
        'n_surrogates': args.n_surrogates,
        'summary': {k: (v if not isinstance(v, float) or np.isfinite(v) else None)
                    for k, v in summary.items()},
        'windows': [{k: (v if not isinstance(v, float) or np.isfinite(v) else None)
                     for k, v in r.items()} for r in results],
    }
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved to {out_path}")
