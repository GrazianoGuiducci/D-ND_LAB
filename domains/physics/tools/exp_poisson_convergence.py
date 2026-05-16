#!/usr/bin/env python3
"""
exp_poisson_convergence.py — Do beta, <r>_excess, and acf1 predict the same Poisson scale?

Three independent observables drift toward Poisson at large prime scale:
  - Brody beta -> 0
  - <r> excess over Cramer -> 0  (i.e. <r> -> <r>_Poisson ~ 0.386)
  - acf1 (gap autocorrelation) -> 0

Question: do all three extrapolate to Poisson at the SAME critical scale p*?
If yes: universal crossover. If no: multiple decorrelation scales.

Usage:
    python exp_poisson_convergence.py [--n_primes N] [--n_windows W] [--n_surrogates S]
"""

import argparse
import numpy as np
from scipy import stats
from sympy import primerange
import json
import sys


def get_primes(n_max):
    """Get primes up to n_max."""
    return np.array(list(primerange(2, n_max)), dtype=np.float64)


def gap_ratio_r(gaps):
    """Mean ratio of consecutive spacings: r_i = min(s_i, s_{i+1}) / max(s_i, s_{i+1})."""
    s = gaps.astype(np.float64)
    r_vals = np.minimum(s[:-1], s[1:]) / np.maximum(s[:-1], s[1:])
    return np.mean(r_vals)


def brody_beta(gaps, n_bins=50):
    """Estimate Brody parameter beta from gap distribution via MLE-like fit.
    P(s) = (beta+1)*b*s^beta * exp(-b*s^{beta+1}), with b = Gamma((beta+2)/(beta+1))^{beta+1}.
    We use a simple grid search over beta in [0, 1]."""
    s = gaps / np.mean(gaps)  # normalize to mean 1
    s = s[s > 0]

    best_beta = 0.0
    best_ll = -np.inf

    from scipy.special import gamma as gamma_fn

    for beta_try in np.linspace(0, 1.5, 300):
        bp1 = beta_try + 1
        b = gamma_fn((bp1 + 1) / bp1) ** bp1
        # log-likelihood
        ll = np.sum(np.log(bp1) + np.log(b) + beta_try * np.log(s) - b * s**bp1)
        if ll > best_ll:
            best_ll = ll
            best_beta = beta_try

    return best_beta


def acf1(gaps):
    """Lag-1 autocorrelation of gap sequence."""
    g = gaps - np.mean(gaps)
    c0 = np.sum(g**2)
    if c0 == 0:
        return 0.0
    c1 = np.sum(g[:-1] * g[1:])
    return c1 / c0


def cramer_random_primes(primes, n_surrogates=10):
    """Generate Cramer random model: gaps ~ Exponential(ln p_i), same density, independent."""
    results = []
    for _ in range(n_surrogates):
        # Use actual prime positions as anchors for local density
        gaps_random = np.array([np.random.exponential(np.log(p)) for p in primes[1:]])
        results.append(gaps_random)
    return results


def measure_window(primes_window):
    """Measure all three observables on a window of primes."""
    gaps = np.diff(primes_window)
    if len(gaps) < 20:
        return None

    r = gap_ratio_r(gaps)
    beta = brody_beta(gaps)
    a1 = acf1(gaps)
    median_p = np.median(primes_window)
    ln_p = np.log(median_p)

    return {
        'median_p': median_p,
        'ln_p': ln_p,
        'r': r,
        'beta': beta,
        'acf1': a1,
        'n_gaps': len(gaps),
    }


def measure_cramer_window(primes_window, n_surrogates=10):
    """Measure observables on Cramer surrogates for a window."""
    gaps_real = np.diff(primes_window)
    if len(gaps_real) < 20:
        return None

    r_vals, beta_vals, acf1_vals = [], [], []

    for _ in range(n_surrogates):
        # Cramer model: exponential gaps with scale = ln(p)
        log_ps = np.log(primes_window[1:])
        gaps_surr = np.array([np.random.exponential(lp) for lp in log_ps])
        gaps_surr = np.maximum(gaps_surr, 0.1)  # avoid zeros

        r_vals.append(gap_ratio_r(gaps_surr))
        beta_vals.append(brody_beta(gaps_surr))
        acf1_vals.append(acf1(gaps_surr))

    return {
        'r_cramer': np.mean(r_vals),
        'r_cramer_std': np.std(r_vals),
        'beta_cramer': np.mean(beta_vals),
        'beta_cramer_std': np.std(beta_vals),
        'acf1_cramer': np.mean(acf1_vals),
        'acf1_cramer_std': np.std(acf1_vals),
    }


def run_experiment(n_primes_target=6_000_000, n_windows=25, n_surrogates=10, window_size=50_000):
    """Main experiment: measure 3 observables at multiple scales."""

    # Estimate upper bound for sieve
    # p_n ~ n * ln(n) for large n
    import math
    upper = int(n_primes_target * (math.log(n_primes_target) + math.log(math.log(n_primes_target)) + 2))

    print(f"Sieving primes up to {upper:,} ...", flush=True)
    all_primes = get_primes(upper)
    print(f"Got {len(all_primes):,} primes. Using first {min(len(all_primes), n_primes_target):,}.", flush=True)
    all_primes = all_primes[:n_primes_target]

    # Create log-spaced windows
    min_idx = 1000  # skip very small primes
    max_idx = len(all_primes) - window_size
    if max_idx < min_idx + window_size:
        max_idx = len(all_primes) - 1
        window_size = min(window_size, max_idx - min_idx)

    window_starts = np.unique(np.logspace(
        np.log10(min_idx), np.log10(max_idx), n_windows
    ).astype(int))

    print(f"\nMeasuring {len(window_starts)} windows, {window_size} primes each, {n_surrogates} Cramer surrogates...\n")

    results = []

    for i, start in enumerate(window_starts):
        end = min(start + window_size, len(all_primes))
        window = all_primes[start:end]

        m = measure_window(window)
        if m is None:
            continue

        c = measure_cramer_window(window, n_surrogates)
        if c is None:
            continue

        # Excess over Cramer
        m['r_excess'] = m['r'] - c['r_cramer']
        m['beta_excess'] = m['beta'] - c['beta_cramer']
        m['acf1_excess'] = m['acf1'] - c['acf1_cramer']

        # z-scores
        m['r_z'] = m['r_excess'] / max(c['r_cramer_std'], 1e-10)
        m['beta_z'] = m['beta_excess'] / max(c['beta_cramer_std'], 1e-10)
        m['acf1_z'] = m['acf1_excess'] / max(c['acf1_cramer_std'], 1e-10)

        m.update(c)
        results.append(m)

        print(f"  [{i+1:2d}/{len(window_starts)}] ln(p)={m['ln_p']:.2f}  "
              f"beta={m['beta']:.4f}  <r>={m['r']:.4f}  acf1={m['acf1']:.4f}  "
              f"| excess: beta={m['beta_excess']:+.4f} <r>={m['r_excess']:+.4f} acf1={m['acf1_excess']:+.4f}",
              flush=True)

    return results


def fit_and_extrapolate(results):
    """Fit linear trends in ln(p) and extrapolate to Poisson."""
    ln_p = np.array([r['ln_p'] for r in results])

    # Poisson targets
    R_POISSON = 2 * np.log(2) - 1  # ~0.386 for ratio of consecutive spacings
    BETA_POISSON = 0.0
    ACF1_POISSON = 0.0

    fits = {}

    # 1. Beta vs ln(p)
    betas = np.array([r['beta'] for r in results])
    slope_b, intercept_b, r_val_b, p_val_b, se_b = stats.linregress(ln_p, betas)
    if slope_b < 0:
        ln_p_star_beta = (BETA_POISSON - intercept_b) / slope_b
    else:
        ln_p_star_beta = np.inf
    fits['beta'] = {
        'slope': slope_b, 'intercept': intercept_b, 'R2': r_val_b**2,
        'p_value': p_val_b, 'se': se_b,
        'ln_p_star': ln_p_star_beta,
        'p_star': np.exp(ln_p_star_beta) if np.isfinite(ln_p_star_beta) else np.inf,
        'target': BETA_POISSON,
        'values': betas.tolist(),
    }

    # 2. <r> vs ln(p)
    rs = np.array([r['r'] for r in results])
    slope_r, intercept_r, r_val_r, p_val_r, se_r = stats.linregress(ln_p, rs)
    if slope_r < 0:
        ln_p_star_r = (R_POISSON - intercept_r) / slope_r
    else:
        ln_p_star_r = np.inf
    fits['r'] = {
        'slope': slope_r, 'intercept': intercept_r, 'R2': r_val_r**2,
        'p_value': p_val_r, 'se': se_r,
        'ln_p_star': ln_p_star_r,
        'p_star': np.exp(ln_p_star_r) if np.isfinite(ln_p_star_r) else np.inf,
        'target': R_POISSON,
        'values': rs.tolist(),
    }

    # 3. acf1 vs ln(p)
    acf1s = np.array([r['acf1'] for r in results])
    slope_a, intercept_a, r_val_a, p_val_a, se_a = stats.linregress(ln_p, acf1s)
    if intercept_a < 0 and slope_a > 0:
        # acf1 is negative, drifting toward 0
        ln_p_star_acf1 = (ACF1_POISSON - intercept_a) / slope_a
    elif slope_a > 0:
        ln_p_star_acf1 = (ACF1_POISSON - intercept_a) / slope_a
    else:
        ln_p_star_acf1 = np.inf
    fits['acf1'] = {
        'slope': slope_a, 'intercept': intercept_a, 'R2': r_val_a**2,
        'p_value': p_val_a, 'se': se_a,
        'ln_p_star': ln_p_star_acf1,
        'p_star': np.exp(ln_p_star_acf1) if np.isfinite(ln_p_star_acf1) else np.inf,
        'target': ACF1_POISSON,
        'values': acf1s.tolist(),
    }

    fits['ln_p_range'] = [float(ln_p[0]), float(ln_p[-1])]
    fits['ln_p_values'] = ln_p.tolist()

    return fits


def print_summary(fits):
    """Print summary table."""
    print("\n" + "="*80)
    print("CONVERGENCE SUMMARY: Three roads to Poisson")
    print("="*80)

    for name, label, unit in [('beta', 'Brody beta', ''), ('r', '<r> ratio', ''), ('acf1', 'Gap acf1', '')]:
        f = fits[name]
        print(f"\n  {label}:")
        print(f"    Fit: {label} = {f['intercept']:.4f} + {f['slope']:.6f} * ln(p)")
        print(f"    R^2 = {f['R2']:.4f}, p = {f['p_value']:.2e}, SE(slope) = {f['se']:.6f}")
        print(f"    Target (Poisson): {f['target']:.4f}")
        if np.isfinite(f['ln_p_star']) and f['ln_p_star'] > 0:
            print(f"    Extrapolated Poisson at: ln(p*) = {f['ln_p_star']:.1f}  =>  p* ~ 10^{f['ln_p_star']/np.log(10):.1f}")
        else:
            print(f"    No convergence toward Poisson (slope wrong sign or flat)")

    # Compare scales
    print("\n" + "-"*80)
    print("CRITICAL COMPARISON:")
    scales = {}
    for name in ['beta', 'r', 'acf1']:
        lps = fits[name]['ln_p_star']
        if np.isfinite(lps) and lps > 0:
            scales[name] = lps
            print(f"  {name:8s}: ln(p*) = {lps:8.1f}  =>  p* ~ 10^{lps/np.log(10):.1f}")
        else:
            print(f"  {name:8s}: no convergence")

    if len(scales) >= 2:
        vals = list(scales.values())
        spread = max(vals) - min(vals)
        mean_val = np.mean(vals)
        print(f"\n  Spread in ln(p*): {spread:.1f} (ratio of scales: 10^{spread/np.log(10):.1f})")
        if spread < 5:
            print(f"  => CONSISTENT: all observables predict Poisson at similar scale")
        elif spread < 15:
            print(f"  => PARTIAL SEPARATION: observables separate by ~{spread/np.log(10):.0f} decades")
        else:
            print(f"  => STRONG SEPARATION: multiple decorrelation scales")

    print("="*80)


def main():
    parser = argparse.ArgumentParser(description='Poisson convergence: do beta, <r>, acf1 agree?')
    parser.add_argument('--n_primes', type=int, default=5_800_000, help='Number of primes')
    parser.add_argument('--n_windows', type=int, default=25, help='Number of scale windows')
    parser.add_argument('--n_surrogates', type=int, default=10, help='Cramer surrogates per window')
    parser.add_argument('--window_size', type=int, default=50_000, help='Primes per window')
    args = parser.parse_args()

    results = run_experiment(args.n_primes, args.n_windows, args.n_surrogates, args.window_size)
    fits = fit_and_extrapolate(results)

    print_summary(fits)

    # Save data
    output = {
        'experiment': 'poisson_convergence',
        'question': 'Do beta, <r>, and acf1 predict the same Poisson scale?',
        'params': vars(args),
        'fits': {},
        'windows': results,
    }
    # Make fits JSON-serializable
    for k, v in fits.items():
        if isinstance(v, dict):
            output['fits'][k] = {kk: (float(vv) if isinstance(vv, (np.floating, float)) else vv)
                                  for kk, vv in v.items()}
        else:
            output['fits'][k] = v

    with open('/opt/MM_D-ND/tools/data/exp_poisson_convergence.json', 'w') as f:
        json.dump(output, f, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else str(x))

    print(f"\nData saved to tools/data/exp_poisson_convergence.json")
    return fits


if __name__ == '__main__':
    main()
