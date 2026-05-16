#!/usr/bin/env python3
"""
exp_two_layer_universality.py — Is the two-layer Markov memory structure universal?

Consecutio from piano 60g (agent_20260503_0330):
  Prime gap memory decomposes into two orthogonal layers:
    Layer 1 (pairs, Mk1): SR, L1
    Layer 2 (triples, Mk2): SR2, L2, cond_entropy, triple_var, num_var_10
  Question: Is this decomposition a property of ALL ordered sequences,
  or specific to primes?

Method:
  1. Generate 7 gap/spacing sequences: primes, GUE, Poisson, AR(1), logistic,
     periodic, Fibonacci gaps
  2. For each, build Markov-k surrogates (k=0,1,2,3)
  3. Compute 8 observables, measure z-scores vs each Mk level
  4. Classify which observables are "captured" by Mk1 (|z_Mk0|>>2, |z_Mk1|<2)
     vs Mk2 (|z_Mk1|>>2, |z_Mk2|<2) vs Mk3
  5. Compare layer assignments across sequences

Null hypothesis: If universal, all sequences assign SR,L1 to Layer1 and SR2,L2 to Layer2.
Alternative: Layer assignment is sequence-specific — the structure is diagnostic.

Usage:
    python tools/exp_two_layer_universality.py [--N 100000] [--n_surr 30]
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
    percentiles = np.linspace(0, 100, n_bins + 1)
    edges = np.percentile(gaps, percentiles)
    edges[0] = gaps.min() - 0.5
    edges[-1] = gaps.max() + 0.5
    binned = np.digitize(gaps, edges) - 1
    binned = np.clip(binned, 0, n_bins - 1)
    gap_pools = {}
    for b, g in zip(binned, gaps):
        gap_pools.setdefault(b, []).append(g)
    trans = {}
    for i in range(len(binned) - order):
        state = tuple(binned[i:i + order])
        nxt = binned[i + order]
        if state not in trans:
            trans[state] = Counter()
        trans[state][nxt] += 1
    trans_prob = {}
    for state, counts in trans.items():
        total = sum(counts.values())
        trans_prob[state] = {k: v / total for k, v in counts.items()}
    return binned, edges, gap_pools, trans_prob


def generate_markov_surrogate(gaps, order, n_bins=12, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    binned, edges, gap_pools, trans_prob = build_markov_chain(gaps, order, n_bins)
    n = len(gaps)
    result = np.zeros(n)
    start_idx = rng.integers(0, len(binned) - order)
    state = tuple(binned[start_idx:start_idx + order])
    for j in range(order):
        pool = gap_pools[state[j]]
        result[j] = pool[rng.integers(0, len(pool))]
    for i in range(order, n):
        if state in trans_prob:
            probs = trans_prob[state]
            bins_avail = list(probs.keys())
            p = np.array([probs[b] for b in bins_avail])
            nxt_bin = bins_avail[rng.choice(len(bins_avail), p=p)]
        else:
            nxt_bin = rng.integers(0, n_bins)
        pool = gap_pools.get(nxt_bin, gap_pools[list(gap_pools.keys())[0]])
        result[i] = pool[rng.integers(0, len(pool))]
        state = (*state[1:], nxt_bin)
    return result


# --- Observables ---
def spacing_ratio(gaps):
    s = gaps[:-1]
    s1 = gaps[1:]
    r = np.minimum(s, s1) / np.maximum(s, s1)
    return np.mean(r[np.isfinite(r)])

def lag_k_acf(gaps, k=1):
    g = gaps - np.mean(gaps)
    if np.var(gaps) == 0:
        return 0.0
    n = len(g)
    return np.sum(g[:n-k] * g[k:]) / np.sum(g**2)

def next_nearest_sr(gaps):
    """SR2: spacing ratio of next-nearest-neighbor gaps (skip one)."""
    if len(gaps) < 3:
        return 0.5
    s = gaps[:-2]
    s2 = gaps[2:]
    r = np.minimum(s, s2) / np.maximum(s, s2)
    return np.mean(r[np.isfinite(r)])

def cond_entropy_l2(gaps, n_bins=12):
    """Conditional entropy H(g_{n+2} | g_n, g_{n+1})."""
    if len(gaps) < 3:
        return 0.0
    percentiles = np.linspace(0, 100, n_bins + 1)
    edges = np.percentile(gaps, percentiles)
    edges[0] = gaps.min() - 0.5
    edges[-1] = gaps.max() + 0.5
    binned = np.digitize(gaps, edges) - 1
    binned = np.clip(binned, 0, n_bins - 1)
    joint = Counter()
    cond = Counter()
    for i in range(len(binned) - 2):
        state = (binned[i], binned[i+1])
        nxt = binned[i+2]
        joint[(state, nxt)] += 1
        cond[state] += 1
    h = 0.0
    for (state, nxt), cnt in joint.items():
        p = cnt / cond[state]
        if p > 0:
            h -= (cnt / (len(binned) - 2)) * np.log2(p)
    return h

def triple_var(gaps):
    """Variance of (g_n, g_{n+1}, g_{n+2}) triple sums."""
    if len(gaps) < 3:
        return 0.0
    t = gaps[:-2] + gaps[1:-1] + gaps[2:]
    return np.var(t)

def num_var_window(gaps, w=10):
    """Number variance in windows of size w."""
    if len(gaps) < w:
        return np.var(gaps)
    counts = np.array([np.sum(gaps[i:i+w]) for i in range(len(gaps) - w)])
    return np.var(counts)

def run_length_mean(gaps):
    """Mean run length (consecutive increases or decreases)."""
    diffs = np.diff(gaps)
    signs = np.sign(diffs)
    runs = []
    current = 1
    for i in range(1, len(signs)):
        if signs[i] == signs[i-1] and signs[i] != 0:
            current += 1
        else:
            runs.append(current)
            current = 1
    runs.append(current)
    return np.mean(runs)


OBSERVABLES = {
    'SR': spacing_ratio,
    'L1': lambda g: lag_k_acf(g, 1),
    'L2': lambda g: lag_k_acf(g, 2),
    'SR2': next_nearest_sr,
    'cond_entropy': cond_entropy_l2,
    'triple_var': triple_var,
    'num_var_10': num_var_window,
    'run_length': run_length_mean,
}


# --- Sequence generators ---
def gen_prime_gaps(N):
    primes = get_primes(int(N * 15))
    primes = primes[:N+1]
    return np.diff(primes).astype(float)

def gen_gue_spacings(N, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    dim = min(int(np.sqrt(2 * N)) + 50, 1500)
    H = rng.standard_normal((dim, dim))
    H = (H + H.T) / 2
    eigs = np.sort(np.linalg.eigvalsh(H))
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 0]
    # Unfold
    mean_s = np.mean(spacings)
    spacings = spacings / mean_s
    if len(spacings) > N:
        spacings = spacings[:N]
    return spacings

def gen_poisson_spacings(N, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return rng.exponential(1.0, N)

def gen_ar1_gaps(N, phi=0.5, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    x = np.zeros(N)
    x[0] = rng.standard_normal()
    for i in range(1, N):
        x[i] = phi * x[i-1] + rng.standard_normal()
    # Shift to positive
    x = x - x.min() + 1.0
    return x

def gen_logistic_gaps(N, r=3.95):
    x = np.zeros(N + 100)
    x[0] = 0.4
    for i in range(1, len(x)):
        x[i] = r * x[i-1] * (1 - x[i-1])
    x = x[100:]  # discard transient
    return x[:N] * 10 + 1  # scale to positive gaps

def gen_periodic_gaps(N):
    """Periodic 2,4,2,4,... mimicking Z/6Z prime gap structure."""
    return np.array([2.0 if i % 2 == 0 else 4.0 for i in range(N)])

def gen_fibonacci_gaps(N):
    """Gaps between Fibonacci numbers (use ratios to avoid overflow)."""
    # Use log-Fibonacci to avoid overflow, then take differences of logs
    # Actually: Fib gaps grow exponentially, use first 1000 only
    n_use = min(N, 1000)
    fibs = [1.0, 1.0]
    for _ in range(n_use):
        fibs.append(fibs[-1] + fibs[-2])
        if fibs[-1] > 1e300:
            break
    fibs = np.array(fibs, dtype=float)
    gaps = np.diff(fibs)
    return gaps[gaps > 0]


SEQUENCES = {
    'primes': gen_prime_gaps,
    'GUE': gen_gue_spacings,
    'Poisson': gen_poisson_spacings,
    'AR1': gen_ar1_gaps,
    'logistic': gen_logistic_gaps,
    'periodic_24': gen_periodic_gaps,
    'fibonacci': gen_fibonacci_gaps,
}


def classify_layer(z_mk0, z_mk1, z_mk2, threshold=2.0):
    """Classify which Markov order captures an observable.
    Layer 1: |z_Mk0| >> threshold, |z_Mk1| < threshold (captured by pairs)
    Layer 2: |z_Mk1| >> threshold, |z_Mk2| < threshold (captured by triples)
    Layer 0: |z_Mk0| < threshold (no memory)
    Layer 3+: |z_Mk2| >> threshold (needs higher order)
    """
    if abs(z_mk0) < threshold:
        return 0  # no memory
    if abs(z_mk1) < threshold:
        return 1  # pair memory
    if abs(z_mk2) < threshold:
        return 2  # triple memory
    return 3  # higher order


def run_experiment(N=100000, n_surr=30, seed=42):
    rng = np.random.default_rng(seed)
    results = {}

    for seq_name, gen_fn in SEQUENCES.items():
        print(f"\n=== {seq_name} ===")

        # Generate sequence
        if seq_name in ('GUE', 'Poisson', 'AR1'):
            gaps = gen_fn(N, rng=rng)
        elif seq_name == 'primes':
            gaps = gen_fn(N)
        else:
            gaps = gen_fn(N)

        gaps = np.asarray(gaps, dtype=float)
        if len(gaps) < 100:
            print(f"  Skipping {seq_name}: only {len(gaps)} gaps")
            continue

        # Real observables
        real_obs = {}
        for obs_name, obs_fn in OBSERVABLES.items():
            try:
                real_obs[obs_name] = float(obs_fn(gaps))
            except Exception:
                real_obs[obs_name] = float('nan')

        print(f"  N_gaps = {len(gaps)}")
        print(f"  Real: SR={real_obs['SR']:.4f}, L1={real_obs['L1']:.4f}, SR2={real_obs['SR2']:.4f}, L2={real_obs['L2']:.4f}")

        # Markov surrogates for k=0,1,2
        z_scores = {}
        for mk in [0, 1, 2]:
            surr_obs = {name: [] for name in OBSERVABLES}
            n_ok = 0
            for s in range(n_surr):
                try:
                    if mk == 0:
                        surr = rng.permutation(gaps)
                    else:
                        surr = generate_markov_surrogate(gaps, mk, rng=rng)
                    for obs_name, obs_fn in OBSERVABLES.items():
                        surr_obs[obs_name].append(obs_fn(surr))
                    n_ok += 1
                except Exception:
                    pass

            z_mk = {}
            for obs_name in OBSERVABLES:
                vals = np.array(surr_obs[obs_name])
                vals = vals[np.isfinite(vals)]
                if len(vals) > 2 and np.std(vals) > 0:
                    z = (real_obs[obs_name] - np.mean(vals)) / np.std(vals)
                    z_mk[obs_name] = round(float(z), 2)
                else:
                    z_mk[obs_name] = 0.0
            z_scores[f'Mk{mk}'] = z_mk
            print(f"  Mk{mk}: {n_ok}/{n_surr} ok | SR z={z_mk.get('SR',0):.1f}, L1 z={z_mk.get('L1',0):.1f}, SR2 z={z_mk.get('SR2',0):.1f}")

        # Classify layers
        layers = {}
        for obs_name in OBSERVABLES:
            z0 = z_scores['Mk0'].get(obs_name, 0)
            z1 = z_scores['Mk1'].get(obs_name, 0)
            z2 = z_scores['Mk2'].get(obs_name, 0)
            layers[obs_name] = classify_layer(z0, z1, z2)

        print(f"  Layers: {layers}")

        results[seq_name] = {
            'n_gaps': len(gaps),
            'real_obs': real_obs,
            'z_scores': z_scores,
            'layers': layers,
        }

    return results


def analyze_universality(results):
    """Check if layer assignments are the same across sequences."""
    print("\n\n=== UNIVERSALITY ANALYSIS ===\n")

    # Build layer matrix: sequence x observable
    obs_names = list(OBSERVABLES.keys())
    seq_names = [s for s in results if 'layers' in results[s]]

    print(f"{'Observable':<15}", end='')
    for s in seq_names:
        print(f"{s:<12}", end='')
    print("  Universal?")
    print("-" * (15 + 12 * len(seq_names) + 12))

    layer_vectors = {}
    for obs in obs_names:
        print(f"{obs:<15}", end='')
        vals = []
        for s in seq_names:
            layer = results[s]['layers'].get(obs, -1)
            print(f"L{layer:<11}", end='')
            vals.append(layer)
        # Check universality: all same layer?
        unique = set(vals)
        is_universal = len(unique) == 1
        print(f"  {'YES' if is_universal else 'NO'} ({unique})")
        layer_vectors[obs] = vals

    # Prime-specific layers: where primes differ from majority
    print("\n--- Prime-specific structure ---")
    if 'primes' in results:
        prime_layers = results['primes']['layers']
        for obs in obs_names:
            prime_l = prime_layers.get(obs, -1)
            others = [results[s]['layers'].get(obs, -1) for s in seq_names if s != 'primes']
            other_mode = max(set(others), key=others.count) if others else -1
            if prime_l != other_mode:
                print(f"  {obs}: primes=L{prime_l}, majority=L{other_mode}")

    return layer_vectors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=100000)
    parser.add_argument('--n_surr', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    results = run_experiment(N=args.N, n_surr=args.n_surr, seed=args.seed)
    layer_vectors = analyze_universality(results)

    # Save
    out_path = Path(__file__).parent / 'data' / 'two_layer_universality.json'
    save_data = {}
    for seq_name, data in results.items():
        save_data[seq_name] = {
            'n_gaps': data['n_gaps'],
            'real_obs': {k: round(v, 6) for k, v in data['real_obs'].items()},
            'z_scores': data['z_scores'],
            'layers': data['layers'],
        }
    with open(out_path, 'w') as f:
        json.dump(save_data, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
