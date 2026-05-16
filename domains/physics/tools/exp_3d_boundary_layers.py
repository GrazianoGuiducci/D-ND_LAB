#!/usr/bin/env python3
"""
exp_3d_boundary_layers.py — Does the boundary have 3D structure?

Consecutio from piano 60 runs:
  - Layer 1 (pairs, Mk1) → SR, L1 (the dipolar plane)
  - Layer 2 (triples, Mk2) → SR2, triple_var (depth)
  - The crossover (partial shuffle) shows a phase transition in (SR, L1)
  - META question: does Layer 2 transition at the SAME critical alpha?

If same α_c → the boundary is 2D (Layer 2 follows Layer 1 = partial tautology)
If different α_c → the boundary has genuine 3D depth (two independent transitions)

Tests on: primes, GUE, Poisson baseline.

Usage:
    python tools/exp_3d_boundary_layers.py [--N 50000] [--n_alpha 20] [--n_trials 30]
"""

import argparse
import json
import numpy as np
from scipy import stats
from pathlib import Path


def get_primes(n_max):
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def gue_gaps(N_mat, n_matrices, rng):
    """Generate GUE eigenvalue gaps."""
    all_gaps = []
    for _ in range(n_matrices):
        H = rng.standard_normal((N_mat, N_mat)) + 1j * rng.standard_normal((N_mat, N_mat))
        H = (H + H.conj().T) / 2
        evals = np.sort(np.linalg.eigvalsh(H))
        gaps = np.diff(evals)
        gaps = gaps[gaps > 0]
        all_gaps.extend(gaps.tolist())
    return np.array(all_gaps)


def partial_shuffle(seq, alpha, rng):
    s = seq.copy()
    n = len(s)
    k = int(alpha * n)
    if k < 2:
        return s
    idx = rng.choice(n, size=k, replace=False)
    vals = s[idx].copy()
    rng.shuffle(vals)
    s[idx] = vals
    return s


# --- Layer 1 observables (pair statistics) ---
def obs_spacing_ratio(gaps):
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r[np.isfinite(r)])

def obs_lag1_acf(gaps):
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0: return 0.0
    return np.mean(g[:-1] * g[1:]) / c0

# --- Layer 2 observables (triple statistics) ---
def obs_sr2(gaps):
    """Next-nearest-neighbor spacing ratio: min(g_n, g_{n+2})/max(g_n, g_{n+2})"""
    r = np.minimum(gaps[:-2], gaps[2:]) / np.maximum(gaps[:-2], gaps[2:])
    return np.mean(r[np.isfinite(r)])

def obs_triple_var(gaps):
    """Variance of consecutive triple sums, normalized."""
    triples = gaps[:-2] + gaps[1:-1] + gaps[2:]
    v = np.var(gaps)
    if v == 0: return 0.0
    return np.var(triples) / v


def run_crossover(gaps, alphas, n_trials, rng, label=""):
    """Compute all 4 observables at each alpha level."""
    obs_fns = {
        'SR': obs_spacing_ratio,
        'L1': obs_lag1_acf,
        'SR2': obs_sr2,
        'triple_var': obs_triple_var,
    }

    # Full shuffle baseline (alpha=1.0)
    baselines = {name: [] for name in obs_fns}
    for _ in range(n_trials * 3):
        shuffled = partial_shuffle(gaps, 1.0, rng)
        for name, fn in obs_fns.items():
            baselines[name].append(fn(shuffled))
    baseline_mean = {name: np.mean(vals) for name, vals in baselines.items()}
    baseline_std = {name: np.std(vals) for name, vals in baselines.items()}

    # Original values (alpha=0)
    originals = {name: fn(gaps) for name, fn in obs_fns.items()}

    results = []
    for alpha in alphas:
        trial_vals = {name: [] for name in obs_fns}
        for _ in range(n_trials):
            s = partial_shuffle(gaps, alpha, rng)
            for name, fn in obs_fns.items():
                trial_vals[name].append(fn(s))

        row = {'alpha': float(alpha)}
        for name in obs_fns:
            mean_val = np.mean(trial_vals[name])
            std_val = np.std(trial_vals[name])
            # Fraction of original signal retained
            orig_delta = originals[name] - baseline_mean[name]
            curr_delta = mean_val - baseline_mean[name]
            if abs(orig_delta) > 1e-12:
                retention = curr_delta / orig_delta
            else:
                retention = 0.0
            row[f'{name}_mean'] = float(mean_val)
            row[f'{name}_std'] = float(std_val)
            row[f'{name}_retention'] = float(retention)
        results.append(row)

    return results, originals, baseline_mean, baseline_std


def find_critical_alpha(results, obs_name, threshold=0.5):
    """Find alpha where retention drops below threshold (signal half-life)."""
    for r in results:
        if r[f'{obs_name}_retention'] < threshold:
            return r['alpha']
    return 1.0  # never crossed


def find_zero_crossing(results, obs_name):
    """Find alpha where retention crosses zero (sign flip)."""
    for i in range(1, len(results)):
        r0 = results[i-1][f'{obs_name}_retention']
        r1 = results[i][f'{obs_name}_retention']
        if r0 * r1 < 0:
            # Linear interpolation
            a0 = results[i-1]['alpha']
            a1 = results[i]['alpha']
            alpha_zero = a0 + (a1 - a0) * abs(r0) / (abs(r0) + abs(r1))
            return alpha_zero
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=50000, help='Number of primes')
    parser.add_argument('--n_alpha', type=int, default=20, help='Number of alpha steps')
    parser.add_argument('--n_trials', type=int, default=30, help='Trials per alpha')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    alphas = np.linspace(0.05, 0.95, args.n_alpha)

    print(f"=== 3D Boundary Layer Experiment ===")
    print(f"N_primes={args.N}, n_alpha={args.n_alpha}, n_trials={args.n_trials}")

    # --- Primes ---
    print("\n--- PRIMES ---")
    primes = get_primes(args.N * 20)[:args.N]
    prime_gaps = np.diff(primes).astype(float)
    prime_results, prime_orig, prime_bl_mean, prime_bl_std = run_crossover(
        prime_gaps, alphas, args.n_trials, rng, "Primes"
    )

    # --- GUE ---
    print("\n--- GUE ---")
    n_mat = 200
    n_matrices = max(5, args.N // n_mat)
    gue_g = gue_gaps(n_mat, n_matrices, rng)
    if len(gue_g) > args.N:
        gue_g = gue_g[:args.N]
    gue_results, gue_orig, gue_bl_mean, gue_bl_std = run_crossover(
        gue_g, alphas, args.n_trials, rng, "GUE"
    )

    # --- Poisson (exponential gaps, iid) ---
    print("\n--- POISSON ---")
    poisson_gaps = rng.exponential(1.0, size=args.N)
    pois_results, pois_orig, pois_bl_mean, pois_bl_std = run_crossover(
        poisson_gaps, alphas, args.n_trials, rng, "Poisson"
    )

    # --- Analysis ---
    obs_names = ['SR', 'L1', 'SR2', 'triple_var']
    layer_map = {'SR': 'L1_pair', 'L1': 'L1_pair', 'SR2': 'L2_triple', 'triple_var': 'L2_triple'}

    output = {
        'experiment': '3D Boundary Layers',
        'question': 'Do Layer 1 (pairs) and Layer 2 (triples) transition at the same critical alpha?',
        'params': {'N': args.N, 'n_alpha': args.n_alpha, 'n_trials': args.n_trials, 'seed': args.seed},
        'sequences': {}
    }

    for name, results, originals, bl_mean, bl_std in [
        ('primes', prime_results, prime_orig, prime_bl_mean, prime_bl_std),
        ('gue', gue_results, gue_orig, gue_bl_mean, gue_bl_std),
        ('poisson', pois_results, pois_orig, pois_bl_mean, pois_bl_std),
    ]:
        seq_data = {
            'originals': {k: float(v) for k, v in originals.items()},
            'baseline_mean': {k: float(v) for k, v in bl_mean.items()},
            'baseline_std': {k: float(v) for k, v in bl_std.items()},
            'critical_alpha_50': {},
            'zero_crossing': {},
            'retention_curve': results,
        }
        print(f"\n=== {name.upper()} ===")
        print(f"{'Observable':>12} {'Layer':>10} {'Original':>10} {'Baseline':>10} {'α_crit(50%)':>12} {'α_zero':>8}")
        for obs in obs_names:
            ac = find_critical_alpha(results, obs)
            az = find_zero_crossing(results, obs)
            seq_data['critical_alpha_50'][obs] = float(ac)
            seq_data['zero_crossing'][obs] = float(az) if az else None
            print(f"{obs:>12} {layer_map[obs]:>10} {originals[obs]:>10.5f} {bl_mean[obs]:>10.5f} {ac:>12.3f} {str(az and f'{az:.3f}') or 'none':>8}")

        # Layer separation: difference in critical alpha between layers
        l1_crit = np.mean([seq_data['critical_alpha_50'][o] for o in ['SR', 'L1']])
        l2_crit = np.mean([seq_data['critical_alpha_50'][o] for o in ['SR2', 'triple_var']])
        delta_crit = l2_crit - l1_crit
        seq_data['layer_separation'] = {
            'L1_mean_crit': float(l1_crit),
            'L2_mean_crit': float(l2_crit),
            'delta': float(delta_crit),
        }
        print(f"\n  Layer 1 mean α_crit: {l1_crit:.3f}")
        print(f"  Layer 2 mean α_crit: {l2_crit:.3f}")
        print(f"  Δα (L2 - L1): {delta_crit:+.3f}")
        if abs(delta_crit) > 0.05:
            print(f"  → SEPARATION: Layer 2 transitions {'later' if delta_crit > 0 else 'earlier'} than Layer 1")
        else:
            print(f"  → COINCIDENT: Layers transition together (|Δα| < 0.05)")

        output['sequences'][name] = seq_data

    # Summary
    prime_sep = output['sequences']['primes']['layer_separation']['delta']
    gue_sep = output['sequences']['gue']['layer_separation']['delta']
    pois_sep = output['sequences']['poisson']['layer_separation']['delta']

    print(f"\n=== SUMMARY ===")
    print(f"Layer separation Δα: Primes={prime_sep:+.3f}, GUE={gue_sep:+.3f}, Poisson={pois_sep:+.3f}")

    output['summary'] = {
        'prime_layer_separation': float(prime_sep),
        'gue_layer_separation': float(gue_sep),
        'poisson_layer_separation': float(pois_sep),
    }

    # Save
    out_path = Path(__file__).parent / 'data' / '3d_boundary_layers.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
