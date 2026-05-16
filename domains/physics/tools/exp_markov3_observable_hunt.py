#!/usr/bin/env python3
"""
exp_markov3_observable_hunt.py — Find the observable that renders Markov-3 memory visible.

Consecutio from piano 60 (agent_20260502_0330):
  "The Markov-3 residual (z=6203) doesn't live in the (SR, L1) plane.
   Which observable renders it visible?"

Method:
  1. Compute prime gaps, build Markov-k surrogates (k=0,1,2,3)
  2. For 10+ observables, compute z-score: real vs Markov-k null
  3. The "visibility" of Markov-3 is where |z_vs_Mk1| >> 2 but |z_vs_Mk3| ~ 0
     (Markov-1 misses it, Markov-3 captures it)

Usage:
    python tools/exp_markov3_observable_hunt.py [--N 200000] [--n_surr 50]
"""

import argparse
import json
import numpy as np
from pathlib import Path
from collections import Counter


def get_primes(n_max):
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def build_markov_chain(gaps, order, n_bins=12):
    """Build Markov-k transition model from gap sequence using equal-count bins."""
    percentiles = np.linspace(0, 100, n_bins + 1)
    edges = np.percentile(gaps, percentiles)
    edges[0] = gaps.min() - 0.5
    edges[-1] = gaps.max() + 0.5
    binned = np.digitize(gaps, edges) - 1
    binned = np.clip(binned, 0, n_bins - 1)

    # Build gap pools per bin
    gap_pools = {}
    for b, g in zip(binned, gaps):
        gap_pools.setdefault(b, []).append(g)

    # Build transition counts
    trans = {}
    for i in range(len(binned) - order):
        state = tuple(binned[i:i + order])
        nxt = binned[i + order]
        if state not in trans:
            trans[state] = Counter()
        trans[state][nxt] += 1

    # Convert to probabilities
    trans_prob = {}
    for state, counts in trans.items():
        total = sum(counts.values())
        trans_prob[state] = {k: v / total for k, v in counts.items()}

    return binned, edges, gap_pools, trans_prob


def generate_markov_surrogate(gaps, order, n_bins=12, rng=None):
    """Generate a surrogate sequence from a Markov-k model of the gaps."""
    if rng is None:
        rng = np.random.default_rng()

    binned, edges, gap_pools, trans_prob = build_markov_chain(gaps, order, n_bins)
    n = len(gaps)
    result = np.zeros(n)

    # Seed with random starting state from data
    start_idx = rng.integers(0, len(binned) - order)
    state = tuple(binned[start_idx:start_idx + order])
    for j in range(order):
        pool = gap_pools[state[j]]
        result[j] = pool[rng.integers(len(pool))]

    for i in range(order, n):
        if state in trans_prob:
            bins_list = list(trans_prob[state].keys())
            probs = np.array([trans_prob[state][b] for b in bins_list])
            chosen_bin = bins_list[rng.choice(len(bins_list), p=probs)]
        else:
            # Fallback: uniform from all bins
            chosen_bin = rng.integers(n_bins)
        pool = gap_pools.get(chosen_bin, gap_pools[list(gap_pools.keys())[0]])
        result[i] = pool[rng.integers(len(pool))]
        state = tuple(list(state[1:]) + [chosen_bin])

    return result


# --- Observables ---

def obs_spacing_ratio(gaps):
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r[np.isfinite(r)])

def obs_lag1_acf(gaps):
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0: return 0.0
    return np.mean(g[:-1] * g[1:]) / c0

def obs_lag2_acf(gaps):
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0: return 0.0
    return np.mean(g[:-2] * g[2:]) / c0

def obs_lag3_acf(gaps):
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0: return 0.0
    return np.mean(g[:-3] * g[3:]) / c0

def obs_triple_corr(gaps):
    """Three-body correlation: <g_n * g_{n+1} * g_{n+2}> / <g>^3"""
    mu = np.mean(gaps)
    if mu == 0: return 0.0
    return np.mean(gaps[:-2] * gaps[1:-1] * gaps[2:]) / mu**3

def obs_triple_variance(gaps):
    """Variance of consecutive triple sums: var(g_n + g_{n+1} + g_{n+2})"""
    triples = gaps[:-2] + gaps[1:-1] + gaps[2:]
    return np.var(triples) / np.var(gaps)

def obs_lag2_spacing_ratio(gaps):
    """Next-nearest-neighbor spacing ratio: min(g_n, g_{n+2})/max(g_n, g_{n+2})"""
    r = np.minimum(gaps[:-2], gaps[2:]) / np.maximum(gaps[:-2], gaps[2:])
    return np.mean(r[np.isfinite(r)])

def obs_conditional_entropy_lag2(gaps, n_bins=12):
    """H(g_{n+2} | g_n, g_{n+1}) — conditional entropy at lag 2"""
    percentiles = np.linspace(0, 100, n_bins + 1)
    edges = np.percentile(gaps, percentiles)
    edges[0] = gaps.min() - 0.5
    edges[-1] = gaps.max() + 0.5
    binned = np.digitize(gaps, edges) - 1
    binned = np.clip(binned, 0, n_bins - 1)

    # Count triples
    triple_counts = Counter()
    pair_counts = Counter()
    for i in range(len(binned) - 2):
        triple_counts[(binned[i], binned[i+1], binned[i+2])] += 1
        pair_counts[(binned[i], binned[i+1])] += 1

    # H(X3 | X1, X2) = H(X1,X2,X3) - H(X1,X2)
    n_total = sum(triple_counts.values())
    h_triple = 0.0
    for c in triple_counts.values():
        p = c / n_total
        if p > 0:
            h_triple -= p * np.log2(p)

    n_pair = sum(pair_counts.values())
    h_pair = 0.0
    for c in pair_counts.values():
        p = c / n_pair
        if p > 0:
            h_pair -= p * np.log2(p)

    return h_triple - h_pair

def obs_gap_run_length(gaps):
    """Mean run length of same-sign deviations from local mean (window=50)."""
    w = 50
    if len(gaps) < w + 10:
        return 0.0
    local_mean = np.convolve(gaps, np.ones(w)/w, mode='valid')
    dev_sign = np.sign(gaps[w//2:w//2+len(local_mean)] - local_mean)
    runs = []
    current = 1
    for i in range(1, len(dev_sign)):
        if dev_sign[i] == dev_sign[i-1]:
            current += 1
        else:
            runs.append(current)
            current = 1
    runs.append(current)
    return np.mean(runs)

def obs_number_variance(gaps, L=10):
    """Sigma^2(L): variance of number of primes in windows of L consecutive gaps."""
    cumsum = np.cumsum(gaps)
    # Count gaps in windows of total length ~ L * mean_gap
    n_windows = len(gaps) - L
    if n_windows < 100:
        return 0.0
    counts = np.array([L] * n_windows)  # fixed L gaps per window
    sums = cumsum[L:] - np.concatenate([[0], cumsum[:n_windows-1]])
    # Number variance = var of sum of L consecutive gaps / mean^2
    return np.var(sums[:n_windows]) / np.mean(gaps)**2


OBSERVABLES = {
    'SR': obs_spacing_ratio,
    'L1': obs_lag1_acf,
    'L2': obs_lag2_acf,
    'L3': obs_lag3_acf,
    'triple_corr': obs_triple_corr,
    'triple_var': obs_triple_variance,
    'SR2': obs_lag2_spacing_ratio,
    'cond_entropy_L2': obs_conditional_entropy_lag2,
    'run_length': obs_gap_run_length,
    'num_var_10': obs_number_variance,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=200000,
                        help='Number of primes')
    parser.add_argument('--n_surr', type=int, default=50,
                        help='Surrogates per Markov order')
    parser.add_argument('--n_bins', type=int, default=12,
                        help='Bins for Markov model')
    args = parser.parse_args()

    print(f"Generating {args.N} primes...")
    # Estimate sieve limit
    import math
    limit = int(args.N * (math.log(args.N) + math.log(math.log(args.N)) + 2))
    primes = get_primes(limit)[:args.N]
    gaps = np.diff(primes).astype(float)
    print(f"Got {len(gaps)} gaps, mean={np.mean(gaps):.2f}")

    # Compute real observables
    real_obs = {}
    for name, fn in OBSERVABLES.items():
        real_obs[name] = fn(gaps)
        print(f"  Real {name} = {real_obs[name]:.6f}")

    # For each Markov order, generate surrogates and compute observables
    rng = np.random.default_rng(42)
    orders = [0, 1, 2, 3]
    results = {}

    for k in orders:
        print(f"\nMarkov-{k}: generating {args.n_surr} surrogates...")
        surr_obs = {name: [] for name in OBSERVABLES}

        for trial in range(args.n_surr):
            if k == 0:
                # Markov-0 = iid shuffle (preserves distribution, destroys all ordering)
                surr = rng.permutation(gaps)
            else:
                surr = generate_markov_surrogate(gaps, k, args.n_bins, rng)

            for name, fn in OBSERVABLES.items():
                surr_obs[name].append(fn(surr))

        # Compute z-scores
        results[f'Mk{k}'] = {}
        for name in OBSERVABLES:
            vals = np.array(surr_obs[name])
            mu = np.mean(vals)
            std = np.std(vals)
            if std < 1e-15:
                z = 0.0
            else:
                z = (real_obs[name] - mu) / std
            results[f'Mk{k}'][name] = {
                'real': float(real_obs[name]),
                'surr_mean': float(mu),
                'surr_std': float(std),
                'z': float(z),
            }
            print(f"  {name}: real={real_obs[name]:.6f}, surr={mu:.6f}+/-{std:.6f}, z={z:.1f}")

    # Summary: find observables where |z_Mk1| >> 2 and |z_Mk3| ~ 0
    print("\n" + "="*80)
    print("SUMMARY: Observables that reveal Markov-3 memory")
    print("="*80)
    print(f"{'Observable':<20} {'z(Mk0)':<10} {'z(Mk1)':<10} {'z(Mk2)':<10} {'z(Mk3)':<10} {'|Mk1-Mk3|':<12} {'VISIBLE?'}")
    print("-"*80)

    visibility = {}
    for name in OBSERVABLES:
        z0 = results['Mk0'][name]['z']
        z1 = results['Mk1'][name]['z']
        z2 = results['Mk2'][name]['z']
        z3 = results['Mk3'][name]['z']
        drop = abs(z1) - abs(z3)
        # Visible = Mk1 can't explain it (|z|>2) but Mk3 can (|z|<2)
        visible = "YES" if abs(z1) > 3 and abs(z3) < 2 else ""
        if abs(z1) > 3 and abs(z3) < abs(z1) * 0.3:
            visible = visible or "PARTIAL"
        print(f"{name:<20} {z0:<10.1f} {z1:<10.1f} {z2:<10.1f} {z3:<10.1f} {drop:<12.1f} {visible}")
        visibility[name] = {
            'z_Mk0': round(z0, 2),
            'z_Mk1': round(z1, 2),
            'z_Mk2': round(z2, 2),
            'z_Mk3': round(z3, 2),
            'drop_Mk1_to_Mk3': round(drop, 2),
            'visible': bool(visible),
        }

    # Save
    output = {
        'experiment': 'markov3_observable_hunt',
        'date': '2026-05-03',
        'N_primes': args.N,
        'n_gaps': len(gaps),
        'n_surrogates': args.n_surr,
        'n_bins': args.n_bins,
        'real_observables': {k: round(v, 6) for k, v in real_obs.items()},
        'z_scores': {mk: {obs: round(results[mk][obs]['z'], 2) for obs in OBSERVABLES} for mk in results},
        'visibility_summary': visibility,
    }

    out_path = Path('tools/data/markov3_observable_hunt.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
