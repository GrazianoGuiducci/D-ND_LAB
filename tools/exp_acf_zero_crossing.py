#!/usr/bin/env python3
"""
exp_acf_zero_crossing.py — Measure the autocorrelation zero-crossing lag
of an ordered sequence across magnitude windows.

The zero-crossing is the first lag where ACF transitions from negative to positive.
Reports scaling behavior with a shuffle null baseline.

Usage:
    python3 tools/exp_acf_zero_crossing.py [--limit N] [--max-lag L] [--n-shuffle S]
"""
import numpy as np
import argparse


def sieve(n):
    is_prime = np.ones(n + 1, dtype=bool)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]


def autocorr(x, max_lag=80):
    x_c = x - x.mean()
    var = np.var(x)
    if var == 0:
        return np.zeros(max_lag)
    n = len(x)
    return np.array([np.mean(x_c[:n-lag] * x_c[lag:]) / var
                     for lag in range(1, max_lag + 1)])


def find_zero_crossing(acf):
    """First lag where ACF goes from <=0 to >0. Returns fractional lag."""
    for i in range(len(acf) - 1):
        if acf[i] <= 0 and acf[i + 1] > 0:
            denom = acf[i + 1] - acf[i]
            frac = -acf[i] / denom if denom != 0 else 0
            return (i + 1) + frac
    return None


def analyze_sequence(gaps, primes_start, n_windows=8, max_lag=80, n_shuffle=20):
    """Analyze zero-crossing scaling for a gap sequence with associated primes."""
    log_bounds = np.linspace(np.log10(primes_start.min()),
                             np.log10(primes_start.max()), n_windows + 1)
    boundaries = [int(10**x) for x in log_bounds]

    results = []
    for i in range(len(boundaries) - 1):
        lo, hi = boundaries[i], boundaries[i + 1]
        mask = (primes_start >= lo) & (primes_start < hi)
        window_gaps = gaps[mask]
        if len(window_gaps) < 300:
            continue

        acf_real = autocorr(window_gaps, max_lag)
        zc_real = find_zero_crossing(acf_real)

        # Shuffle baseline
        zc_shuffles = []
        for _ in range(n_shuffle):
            shuf = window_gaps.copy()
            np.random.shuffle(shuf)
            acf_shuf = autocorr(shuf, max_lag)
            zc_s = find_zero_crossing(acf_shuf)
            if zc_s is not None:
                zc_shuffles.append(zc_s)

        median_p = np.median(primes_start[mask])
        shuf_mean = np.mean(zc_shuffles) if zc_shuffles else None
        shuf_std = np.std(zc_shuffles) if len(zc_shuffles) > 3 else None

        results.append({
            'lo': lo, 'hi': hi, 'n': len(window_gaps),
            'median_p': median_p, 'zc_real': zc_real,
            'shuf_mean': shuf_mean, 'shuf_std': shuf_std,
            'acf_1': acf_real[0] if len(acf_real) > 0 else None,
        })

    return results


def fit_scaling(results):
    """Fit power-law and log-power scaling to zero-crossing data."""
    valid = [(r['median_p'], r['zc_real']) for r in results if r['zc_real'] is not None]
    if len(valid) < 3:
        return None

    p_arr = np.array([v[0] for v in valid])
    zc_arr = np.array([v[1] for v in valid])

    # H1: ZC ~ p^alpha
    log_p = np.log10(p_arr)
    log_zc = np.log10(zc_arr)
    slope1, _ = np.polyfit(log_p, log_zc, 1)
    r2_1 = np.corrcoef(log_p, log_zc)[0, 1]**2

    # H2: ZC ~ ln(p)^beta
    ln_p = np.log(p_arr)
    log_lnp = np.log(ln_p)
    log_zc_nat = np.log(zc_arr)
    slope2, _ = np.polyfit(log_lnp, log_zc_nat, 1)
    r2_2 = np.corrcoef(log_lnp, log_zc_nat)[0, 1]**2

    return {
        'power_law': {'alpha': slope1, 'r2': r2_1},
        'log_power': {'beta': slope2, 'r2': r2_2},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20_000_000)
    parser.add_argument('--max-lag', type=int, default=80)
    parser.add_argument('--n-shuffle', type=int, default=20)
    args = parser.parse_args()

    primes = sieve(args.limit)
    gaps = np.diff(primes)
    primes_start = primes[:-1]

    # Skip p < 1000 (too few gaps per window)
    mask_min = primes_start >= 1000
    results = analyze_sequence(gaps[mask_min], primes_start[mask_min],
                               max_lag=args.max_lag, n_shuffle=args.n_shuffle)

    print(f"{'Median p':<12} {'N':<8} {'ZC_real':<8} {'ZC_shuf':<12} {'z-score':<8} {'ACF(1)':<8}")
    print("-" * 60)
    for r in results:
        zc_str = f"{r['zc_real']:.2f}" if r['zc_real'] else ">max"
        shuf_str = f"{r['shuf_mean']:.1f}+/-{r['shuf_std']:.1f}" if r['shuf_std'] else "N/A"
        z = ((r['zc_real'] - r['shuf_mean']) / r['shuf_std']
             if r['zc_real'] and r['shuf_std'] and r['shuf_std'] > 0 else 0)
        print(f"{r['median_p']:<12.0f} {r['n']:<8} {zc_str:<8} {shuf_str:<12} {z:<8.1f} {r['acf_1']:<8.4f}")

    scaling = fit_scaling(results)
    if scaling:
        print(f"\nScaling: ZC ~ p^{scaling['power_law']['alpha']:.3f} (R2={scaling['power_law']['r2']:.3f})")
        print(f"         ZC ~ ln(p)^{scaling['log_power']['beta']:.2f} (R2={scaling['log_power']['r2']:.3f})")
