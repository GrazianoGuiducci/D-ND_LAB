#!/usr/bin/env python3
"""
exp_selective_layer_decoupling.py — Can selective perturbations decouple the two Markov layers?

Consecutio from BOUNDARY (piano 60h): The two Markov layers (pairs->SR,L1; triples->SR2,L2)
are coupled at the uniform-shuffle boundary (same critical alpha=0.334). But Mk1 surrogates
capture Layer 1 while destroying Layer 2. Contradiction?

Hypothesis: The coupling is an artifact of UNIFORM shuffle symmetry — not structural coupling.
Uniform shuffle attacks all correlations at the same rate. Selective perturbation should decouple.

Method:
  For 3 perturbation types x 15 alpha levels x 30 surrogates:
  1. UNIFORM: replace position i with random draw from distribution, prob=alpha
  2. Mk1-SELECTIVE: replace position i with Mk1 surrogate value, prob=alpha
     (preserves pair statistics at alpha=1, destroys triple+)
  3. Mk2-SELECTIVE: replace position i with Mk2 surrogate value, prob=alpha
     (preserves triple statistics at alpha=1)

  Measure 6 observables at each alpha, compute z-scores vs original.
  Find critical alpha_c where each observable crosses |z|=2.

Prediction if independent:
  - Uniform: both layers break at same alpha_c (already known)
  - Mk1-selective: Layer 1 never breaks, Layer 2 breaks at some alpha_c
  - Mk2-selective: neither layer breaks
Prediction if coupled:
  - All perturbation types break both layers together

Usage:
    python tools/exp_selective_layer_decoupling.py [--N 100000] [--n_surr 30]
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


def gen_prime_gaps(N):
    primes = get_primes(int(N * 15))[:N + 1]
    return np.diff(primes).astype(float)


def gen_gue_spacings(N, rng):
    dim = min(int(np.sqrt(2 * N)) + 50, 1500)
    H = rng.standard_normal((dim, dim))
    H = (H + H.T) / 2
    eigs = np.sort(np.linalg.eigvalsh(H))
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 0]
    spacings = spacings / np.mean(spacings)
    return spacings[:N] if len(spacings) > N else spacings


def gen_poisson_spacings(N, rng):
    return rng.exponential(1.0, N)


# --- Markov surrogate generation ---
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


def partial_perturbation(original, surrogate, alpha, rng):
    """Position-wise interpolation: replace original[i] with surrogate[i] with probability alpha."""
    n = len(original)
    mask = rng.random(n) < alpha
    result = original.copy()
    result[mask] = surrogate[mask]
    return result


# --- Observables ---
def spacing_ratio(gaps):
    s, s1 = gaps[:-1], gaps[1:]
    r = np.minimum(s, s1) / np.maximum(s, s1)
    return np.mean(r[np.isfinite(r)])


def lag_k_acf(gaps, k=1):
    g = gaps - np.mean(gaps)
    v = np.sum(g ** 2)
    if v < 1e-12:
        return 0.0
    n = len(g)
    return np.sum(g[:n - k] * g[k:]) / v


def next_nearest_sr(gaps):
    if len(gaps) < 3:
        return 0.5
    s, s2 = gaps[:-2], gaps[2:]
    r = np.minimum(s, s2) / np.maximum(s, s2)
    return np.mean(r[np.isfinite(r)])


def cond_entropy_l2(gaps, n_bins=12):
    if len(gaps) < 3:
        return 0.0
    pct = np.linspace(0, 100, n_bins + 1)
    edges = np.percentile(gaps, pct)
    edges[0] = gaps.min() - 0.5
    edges[-1] = gaps.max() + 0.5
    binned = np.clip(np.digitize(gaps, edges) - 1, 0, n_bins - 1)
    joint = Counter()
    cond = Counter()
    for i in range(len(binned) - 2):
        state = (binned[i], binned[i + 1])
        nxt = binned[i + 2]
        joint[(state, nxt)] += 1
        cond[state] += 1
    h = 0.0
    total = len(binned) - 2
    for (state, nxt), cnt in joint.items():
        p = cnt / cond[state]
        if p > 0:
            h -= (cnt / total) * np.log2(p)
    return h


def triple_var(gaps):
    if len(gaps) < 3:
        return 0.0
    t = gaps[:-2] + gaps[1:-1] + gaps[2:]
    return np.var(t)


OBSERVABLES = {
    'SR': spacing_ratio,
    'L1': lambda g: lag_k_acf(g, 1),
    'SR2': next_nearest_sr,
    'L2': lambda g: lag_k_acf(g, 2),
    'cond_entropy': cond_entropy_l2,
    'triple_var': triple_var,
}

LAYER1_OBS = ['SR', 'L1']
LAYER2_OBS = ['SR2', 'L2', 'cond_entropy', 'triple_var']


def measure_all(gaps):
    return {name: fn(gaps) for name, fn in OBSERVABLES.items()}


def find_critical_alpha(alpha_vals, z_vals, threshold=2.0):
    """Find alpha where |z| first exceeds threshold (linear interpolation)."""
    for i in range(len(alpha_vals)):
        if abs(z_vals[i]) >= threshold:
            if i == 0:
                return alpha_vals[0]
            z_prev, z_curr = abs(z_vals[i - 1]), abs(z_vals[i])
            a_prev, a_curr = alpha_vals[i - 1], alpha_vals[i]
            if z_curr - z_prev > 0:
                frac = (threshold - z_prev) / (z_curr - z_prev)
                return a_prev + frac * (a_curr - a_prev)
            return a_curr
    return float('inf')  # never crosses


def run_sweep(gaps, perturbation_type, alpha_vals, n_surr, rng):
    """Sweep alpha for one perturbation type. Returns z-scores per observable per alpha."""
    real_obs = measure_all(gaps)
    results = {name: [] for name in OBSERVABLES}

    for alpha in alpha_vals:
        surr_obs = {name: [] for name in OBSERVABLES}
        for _ in range(n_surr):
            if perturbation_type == 'uniform':
                shuffled = rng.permutation(gaps)
                perturbed = partial_perturbation(gaps, shuffled, alpha, rng)
            elif perturbation_type == 'Mk1':
                mk1_surr = generate_markov_surrogate(gaps, 1, rng=rng)
                perturbed = partial_perturbation(gaps, mk1_surr, alpha, rng)
            elif perturbation_type == 'Mk2':
                mk2_surr = generate_markov_surrogate(gaps, 2, rng=rng)
                perturbed = partial_perturbation(gaps, mk2_surr, alpha, rng)
            else:
                raise ValueError(f"Unknown perturbation: {perturbation_type}")

            obs = measure_all(perturbed)
            for name in OBSERVABLES:
                surr_obs[name].append(obs[name])

        for name in OBSERVABLES:
            vals = np.array(surr_obs[name])
            vals = vals[np.isfinite(vals)]
            if len(vals) > 2 and np.std(vals) > 1e-12:
                z = (real_obs[name] - np.mean(vals)) / np.std(vals)
            else:
                z = 0.0
            results[name].append(round(float(z), 2))

    return results, real_obs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=100000)
    parser.add_argument('--n_surr', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    alpha_vals = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    perturbation_types = ['uniform', 'Mk1', 'Mk2']

    sequences = {
        'primes': gen_prime_gaps(args.N),
        'GUE': gen_gue_spacings(args.N, rng),
        'Poisson': gen_poisson_spacings(args.N, rng),
    }

    all_results = {}

    for seq_name, gaps in sequences.items():
        print(f"\n{'='*60}")
        print(f"  {seq_name} (N={len(gaps)})")
        print(f"{'='*60}")

        seq_results = {}
        for ptype in perturbation_types:
            print(f"\n--- {ptype} perturbation ---")
            z_curves, real_obs = run_sweep(gaps, ptype, alpha_vals, args.n_surr, rng)

            # Find critical alpha for each observable
            critical = {}
            for name in OBSERVABLES:
                ac = find_critical_alpha(alpha_vals, z_curves[name])
                critical[name] = round(ac, 3) if ac < float('inf') else None
                layer = 'L1' if name in LAYER1_OBS else 'L2'
                tag = f"alpha_c={ac:.3f}" if ac < float('inf') else "NEVER_BREAKS"
                print(f"  {name:>14} ({layer}): {tag}")

            seq_results[ptype] = {
                'z_curves': z_curves,
                'critical_alpha': critical,
                'real_obs': {k: round(v, 6) for k, v in real_obs.items()},
            }

        # Summary for this sequence
        print(f"\n--- SUMMARY: {seq_name} ---")
        print(f"{'Observable':<14} {'Layer':<6} {'uniform':>10} {'Mk1':>10} {'Mk2':>10}")
        print("-" * 55)
        for name in OBSERVABLES:
            layer = 'L1' if name in LAYER1_OBS else 'L2'
            vals = []
            for pt in perturbation_types:
                ac = seq_results[pt]['critical_alpha'][name]
                vals.append(f"{ac:.3f}" if ac is not None else "NEVER")
            print(f"{name:<14} {layer:<6} {vals[0]:>10} {vals[1]:>10} {vals[2]:>10}")

        all_results[seq_name] = seq_results

    # Cross-sequence analysis
    print(f"\n\n{'='*60}")
    print(f"  CROSS-SEQUENCE DECOUPLING ANALYSIS")
    print(f"{'='*60}")

    for seq_name, seq_results in all_results.items():
        print(f"\n--- {seq_name} ---")
        for ptype in perturbation_types:
            l1_crits = [seq_results[ptype]['critical_alpha'][o]
                        for o in LAYER1_OBS
                        if seq_results[ptype]['critical_alpha'][o] is not None]
            l2_crits = [seq_results[ptype]['critical_alpha'][o]
                        for o in LAYER2_OBS
                        if seq_results[ptype]['critical_alpha'][o] is not None]

            l1_mean = np.mean(l1_crits) if l1_crits else float('inf')
            l2_mean = np.mean(l2_crits) if l2_crits else float('inf')
            delta = abs(l1_mean - l2_mean) if l1_mean < float('inf') and l2_mean < float('inf') else float('inf')

            l1_str = f"{l1_mean:.3f}" if l1_mean < float('inf') else "NEVER"
            l2_str = f"{l2_mean:.3f}" if l2_mean < float('inf') else "NEVER"
            delta_str = f"{delta:.3f}" if delta < float('inf') else "DECOUPLED"

            coupled = "COUPLED" if delta < 0.1 and l1_mean < float('inf') else "DECOUPLED"
            print(f"  {ptype:<10}: L1_mean={l1_str:>6}, L2_mean={l2_str:>6}, delta={delta_str:>10} -> {coupled}")

    # Save
    out_path = Path(__file__).parent / 'data' / 'selective_layer_decoupling.json'
    save_data = {}
    for seq_name, seq_results in all_results.items():
        save_data[seq_name] = {}
        for ptype, data in seq_results.items():
            save_data[seq_name][ptype] = {
                'alpha_vals': alpha_vals,
                'z_curves': data['z_curves'],
                'critical_alpha': data['critical_alpha'],
                'real_obs': data['real_obs'],
            }

    with open(out_path, 'w') as f:
        json.dump(save_data, f, indent=2)
    print(f"\nSaved to {out_path}")

    return all_results


if __name__ == '__main__':
    main()
