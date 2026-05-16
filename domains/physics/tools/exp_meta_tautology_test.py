#!/usr/bin/env python3
"""META Tautology Discriminator — which observables measure real structure vs density artifacts?

Four observables x three synthetic controls. Each observable gets a verdict:
STRUCTURAL (distinguishes primes from all synthetics) or TAUTOLOGICAL (fails on at least one).

Observables:
  1. r-statistic (spacing ratio) — short-range repulsion
  2. Mod-3 ordering fraction — the algebraic memory channel
  3. Lag-1 autocorrelation — sequential gap correlation
  4. Two-channel delta-r — magnitude vs ordering decomposition

Controls:
  A. Shuffled gaps — same distribution, destroyed order
  B. Cramer model — PNT density, independent exponential gaps
  C. Hardy-Littlewood model — correct pair correlations, no higher-order structure
"""

import argparse
import json
import numpy as np
from sympy import primerange


def get_primes(n_max):
    return np.array(list(primerange(2, n_max + 1)), dtype=np.int64)


def r_statistic(gaps):
    """Mean spacing ratio min(s_i, s_{i+1}) / max(s_i, s_{i+1})."""
    s1 = gaps[:-1]
    s2 = gaps[1:]
    mn = np.minimum(s1, s2)
    mx = np.maximum(s1, s2)
    mask = mx > 0
    return np.mean(mn[mask] / mx[mask])


def mod3_ordering_fraction(gaps):
    """Fraction of consecutive gap pairs where mod-3 class is preserved."""
    classes = gaps % 3
    same = np.sum(classes[:-1] == classes[1:])
    return same / len(classes[:-1])


def lag1_autocorrelation(gaps):
    """Pearson autocorrelation at lag 1."""
    g = gaps.astype(np.float64)
    g = g - g.mean()
    if g.std() == 0:
        return 0.0
    return np.corrcoef(g[:-1], g[1:])[0, 1]


def two_channel_delta_r(gaps):
    """Decompose into magnitude and ordering channels, return delta-r for each."""
    g = gaps.astype(np.float64)
    median_g = np.median(g)
    binary = (g > median_g).astype(np.float64)  # ordering channel
    magnitude = np.abs(g - median_g)              # magnitude channel

    r_ord = r_statistic_from_signal(binary)
    r_mag = r_statistic_from_signal(magnitude)

    # Shuffle baseline
    rng = np.random.default_rng(42)
    r_ord_shuf = []
    r_mag_shuf = []
    for _ in range(20):
        idx = rng.permutation(len(gaps))
        b_s = binary[idx]
        m_s = magnitude[idx]
        r_ord_shuf.append(r_statistic_from_signal(b_s))
        r_mag_shuf.append(r_statistic_from_signal(m_s))

    dr_ord = (r_ord - np.mean(r_ord_shuf)) / (np.std(r_ord_shuf) + 1e-12)
    dr_mag = (r_mag - np.mean(r_mag_shuf)) / (np.std(r_mag_shuf) + 1e-12)
    return dr_ord, dr_mag


def r_statistic_from_signal(sig):
    """r-statistic on arbitrary positive signal (add offset if needed)."""
    s = sig - sig.min() + 1e-6
    s1 = s[:-1]
    s2 = s[1:]
    mn = np.minimum(s1, s2)
    mx = np.maximum(s1, s2)
    mask = mx > 0
    return np.mean(mn[mask] / mx[mask])


# === Synthetic generators ===

def shuffled_gaps(gaps, rng):
    """Same gap distribution, destroyed sequential order."""
    g = gaps.copy()
    rng.shuffle(g)
    return g


def cramer_random_gaps(n_gaps, mean_gap, rng):
    """Independent exponential gaps rounded to even (like PNT density)."""
    raw = rng.exponential(mean_gap, size=n_gaps)
    g = np.round(raw / 2) * 2
    g = np.maximum(g, 2).astype(np.int64)
    return g


def hardy_littlewood_gaps(gaps_real, rng):
    """Markov(1) model matching lag-1 autocorrelation of real primes.
    Preserves pair correlation structure but not higher-order."""
    g = gaps_real.astype(np.float64)
    mean_g = g.mean()
    std_g = g.std()
    rho = np.corrcoef(g[:-1], g[1:])[0, 1]

    # AR(1) process with correct mean, std, lag-1
    n = len(gaps_real)
    result = np.zeros(n)
    result[0] = mean_g
    noise_std = std_g * np.sqrt(1 - rho**2)
    for i in range(1, n):
        result[i] = mean_g + rho * (result[i-1] - mean_g) + rng.normal(0, noise_std)

    # Round to even, clip to >= 2
    result = np.round(result / 2) * 2
    result = np.maximum(result, 2).astype(np.int64)
    return result


def run(n_primes_max=600000, n_trials=20):
    """Run the META tautology test."""
    print(f"Generating primes up to {n_primes_max}...")
    primes = get_primes(n_primes_max)
    gaps = np.diff(primes)

    # Use a window in the middle to avoid small-prime effects
    N = min(len(gaps), 50000)
    start = len(gaps) // 4
    gaps_window = gaps[start:start + N]
    mean_gap = float(gaps_window.mean())

    print(f"Using {N} gaps starting at index {start} (mean gap = {mean_gap:.2f})")

    # Real primes observables
    print("\n=== REAL PRIMES ===")
    real_r = r_statistic(gaps_window)
    real_mod3 = mod3_ordering_fraction(gaps_window)
    real_lag1 = lag1_autocorrelation(gaps_window)
    real_dr_ord, real_dr_mag = two_channel_delta_r(gaps_window)
    print(f"  r-stat:     {real_r:.6f}")
    print(f"  mod3-frac:  {real_mod3:.6f}")
    print(f"  lag1-acf:   {real_lag1:.6f}")
    print(f"  dr-ord:     {real_dr_ord:.2f}σ")
    print(f"  dr-mag:     {real_dr_mag:.2f}σ")

    # Run synthetics
    rng = np.random.default_rng(2026)

    results = {
        'real': {
            'r_stat': real_r, 'mod3': real_mod3, 'lag1': real_lag1,
            'dr_ord': real_dr_ord, 'dr_mag': real_dr_mag
        }
    }

    for name, generator in [
        ('shuffled', lambda rng_: shuffled_gaps(gaps_window, rng_)),
        ('cramer', lambda rng_: cramer_random_gaps(N, mean_gap, rng_)),
        ('HL_markov', lambda rng_: hardy_littlewood_gaps(gaps_window, rng_)),
    ]:
        print(f"\n=== {name.upper()} (n_trials={n_trials}) ===")
        obs = {'r_stat': [], 'mod3': [], 'lag1': [], 'dr_ord': [], 'dr_mag': []}

        for t in range(n_trials):
            trial_rng = np.random.default_rng(rng.integers(0, 2**31))
            syn_gaps = generator(trial_rng)
            obs['r_stat'].append(r_statistic(syn_gaps))
            obs['mod3'].append(mod3_ordering_fraction(syn_gaps))
            obs['lag1'].append(lag1_autocorrelation(syn_gaps))
            dr_o, dr_m = two_channel_delta_r(syn_gaps)
            obs['dr_ord'].append(dr_o)
            obs['dr_mag'].append(dr_m)

        results[name] = {}
        for key in obs:
            arr = np.array(obs[key])
            results[name][key] = {
                'mean': float(np.mean(arr)),
                'std': float(np.std(arr)),
                'min': float(np.min(arr)),
                'max': float(np.max(arr))
            }
            print(f"  {key:12s}: {np.mean(arr):+.6f} ± {np.std(arr):.6f}")

    # === Discrimination verdict ===
    print("\n" + "=" * 60)
    print("DISCRIMINATION VERDICTS")
    print("=" * 60)

    verdicts = {}
    for obs_name in ['r_stat', 'mod3', 'lag1', 'dr_ord', 'dr_mag']:
        real_val = results['real'][obs_name]
        discriminates = {}
        for syn_name in ['shuffled', 'cramer', 'HL_markov']:
            syn = results[syn_name][obs_name]
            z = (real_val - syn['mean']) / (syn['std'] + 1e-12)
            discriminates[syn_name] = abs(z)
            label = "YES" if abs(z) > 3.0 else "no"
            print(f"  {obs_name:12s} vs {syn_name:12s}: z = {z:+8.2f}  [{label}]")

        all_pass = all(v > 3.0 for v in discriminates.values())
        verdict = "STRUCTURAL" if all_pass else "TAUTOLOGICAL"
        verdicts[obs_name] = {
            'verdict': verdict,
            'z_scores': {k: float(v) for k, v in discriminates.items()}
        }
        print(f"  → {obs_name}: {verdict}")
        print()

    # Save results
    output = {
        'n_gaps': N,
        'start_index': start,
        'mean_gap': mean_gap,
        'n_trials': n_trials,
        'real': results['real'],
        'synthetics': {k: results[k] for k in ['shuffled', 'cramer', 'HL_markov']},
        'verdicts': verdicts
    }
    out_path = 'tools/data/meta_tautology_test.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='META Tautology Discriminator')
    parser.add_argument('--n-primes', type=int, default=600000, help='Prime sieve limit')
    parser.add_argument('--n-trials', type=int, default=20, help='Synthetic trials per model')
    args = parser.parse_args()
    run(n_primes_max=args.n_primes, n_trials=args.n_trials)
