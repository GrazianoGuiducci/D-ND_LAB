#!/usr/bin/env python3
"""
exp_autocorrelation_excess.py — Measure excess autocorrelation beyond Markov-1 prediction.

For any ordered integer sequence, computes:
1. Empirical autocorrelation at lags 1..max_lag
2. Markov-1 predicted autocorrelation (from transition matrix eigenvalues)
3. Excess = empirical - Markov prediction
4. Null baseline: shuffled sequence (100 shuffles)
5. z-scores of excess vs shuffle

Reusable tool: works on prime gaps, Fibonacci ratios, any gap sequence.

Usage:
    python3 tools/exp_autocorrelation_excess.py [--N 2000000] [--max_lag 200] [--mod 6]
"""

import argparse
import numpy as np
from sympy import primerange
from collections import defaultdict


def get_prime_gaps(N):
    """Generate prime gaps up to N."""
    primes = list(primerange(7, N))
    gaps = [primes[i+1] - primes[i] for i in range(len(primes)-1)]
    return np.array(gaps, dtype=float)


def empirical_autocorrelation(x, max_lag):
    """Compute normalized autocorrelation at lags 1..max_lag."""
    n = len(x)
    x_centered = x - np.mean(x)
    var = np.var(x)
    if var == 0:
        return np.zeros(max_lag)
    acf = np.zeros(max_lag)
    for lag in range(1, max_lag + 1):
        acf[lag - 1] = np.mean(x_centered[:n-lag] * x_centered[lag:]) / var
    return acf


def markov_transition_matrix(gaps, mod):
    """Build Markov-1 transition matrix for gap residues mod m."""
    residues = gaps.astype(int) % mod
    states = sorted(set(residues))
    state_idx = {s: i for i, s in enumerate(states)}
    n_states = len(states)

    counts = np.zeros((n_states, n_states))
    for i in range(len(residues) - 1):
        r_from = state_idx[residues[i]]
        r_to = state_idx[residues[i + 1]]
        counts[r_from, r_to] += 1

    # Normalize rows
    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    T = counts / row_sums

    return T, states


def markov_predicted_autocorrelation(gaps, mod, max_lag):
    """
    Predict autocorrelation from Markov-1 chain.

    For a stationary Markov chain with transition matrix T,
    stationary distribution pi, and observable f(state),
    the autocorrelation at lag k is:
        rho(k) = sum_j c_j * lambda_j^k
    where lambda_j are eigenvalues of T and c_j are coefficients
    from the spectral decomposition projected onto f.
    """
    T, states = markov_transition_matrix(gaps, mod)
    n_states = len(states)

    # Stationary distribution
    eigenvalues_left, eigenvectors_left = np.linalg.eig(T.T)
    idx_stationary = np.argmin(np.abs(eigenvalues_left - 1.0))
    pi = np.abs(eigenvectors_left[:, idx_stationary])
    pi = pi / pi.sum()

    # Right eigenvectors of T
    eigenvalues, R = np.linalg.eig(T)
    # Left eigenvectors (rows of L = R^{-1})
    L = np.linalg.inv(R)

    # Observable: the gap value itself. We need the mean gap conditioned on state.
    residues = gaps.astype(int) % mod
    state_idx = {s: i for i, s in enumerate(states)}

    # Mean gap per state
    state_sums = defaultdict(float)
    state_counts = defaultdict(int)
    for i, g in enumerate(gaps):
        s = state_idx[residues[i]]
        state_sums[s] += g
        state_counts[s] += 1

    f_state = np.zeros(n_states)
    for s in range(n_states):
        if state_counts[s] > 0:
            f_state[s] = state_sums[s] / state_counts[s]

    # Center the observable
    f_mean = np.sum(pi * f_state)
    f_centered = f_state - f_mean
    f_var = np.sum(pi * f_centered**2)

    if f_var < 1e-12:
        return np.zeros(max_lag), eigenvalues

    # Spectral coefficients: c_j = (pi * f_centered . R_j) * (L_j . f_centered) / f_var
    # More precisely: rho(k) = sum_j lambda_j^k * (sum_i pi_i f_i R_{ij}) * (sum_i L_{ji} f_i) / f_var
    coeffs = np.zeros(n_states, dtype=complex)
    for j in range(n_states):
        a = np.sum(pi * f_centered * R[:, j])
        b = np.sum(L[j, :] * f_centered)
        coeffs[j] = a * b / f_var

    # Predicted autocorrelation
    acf_pred = np.zeros(max_lag)
    for lag in range(1, max_lag + 1):
        val = np.sum(coeffs * eigenvalues**lag)
        acf_pred[lag - 1] = val.real

    return acf_pred, eigenvalues


def run_experiment(N=2_000_000, max_lag=200, mod=6, n_shuffles=100):
    """Run the full experiment."""
    print(f"Generating prime gaps up to {N}...")
    gaps = get_prime_gaps(N)
    n_gaps = len(gaps)
    print(f"  {n_gaps} gaps generated.")

    # 1. Empirical autocorrelation
    print(f"Computing empirical autocorrelation (lags 1-{max_lag})...")
    acf_real = empirical_autocorrelation(gaps, max_lag)

    # 2. Markov-1 prediction
    print(f"Computing Markov-1 prediction (mod {mod})...")
    acf_markov, eigenvalues = markov_predicted_autocorrelation(gaps, mod, max_lag)

    print(f"  Transition matrix eigenvalues: {sorted(eigenvalues.real, reverse=True)}")

    # 3. Excess
    excess = acf_real - acf_markov

    # 4. Shuffle baseline for excess
    print(f"Computing shuffle baseline ({n_shuffles} shuffles)...")
    shuffle_excesses = np.zeros((n_shuffles, max_lag))
    for i in range(n_shuffles):
        shuffled = gaps.copy()
        np.random.shuffle(shuffled)
        acf_shuf = empirical_autocorrelation(shuffled, max_lag)
        # Markov prediction for shuffled is ~0 (no correlations)
        shuffle_excesses[i] = acf_shuf  # - 0

    shuffle_mean = shuffle_excesses.mean(axis=0)
    shuffle_std = shuffle_excesses.std(axis=0)
    shuffle_std[shuffle_std < 1e-12] = 1e-12

    # z-score of real excess vs shuffle
    z_excess = (excess - shuffle_mean) / shuffle_std

    # 5. Also compute z-score of raw autocorrelation vs shuffle
    z_raw = (acf_real - shuffle_mean) / shuffle_std

    return {
        'n_gaps': n_gaps,
        'acf_real': acf_real,
        'acf_markov': acf_markov,
        'excess': excess,
        'z_excess': z_excess,
        'z_raw': z_raw,
        'eigenvalues': eigenvalues,
        'shuffle_std': shuffle_std,
    }


def print_results(results, max_lag):
    """Print results table."""
    acf_real = results['acf_real']
    acf_markov = results['acf_markov']
    excess = results['excess']
    z_excess = results['z_excess']
    z_raw = results['z_raw']

    print("\n" + "="*90)
    print(f"AUTOCORRELATION LANDSCAPE — {results['n_gaps']} prime gaps")
    print("="*90)

    # Summary table at key lags
    key_lags = [1, 2, 3, 5, 10, 20, 30, 50, 75, 100, 150, 200]
    key_lags = [l for l in key_lags if l <= max_lag]

    print(f"\n{'Lag':>5} {'ACF_real':>12} {'ACF_markov':>12} {'Excess':>12} {'z(excess)':>12} {'z(raw)':>12}")
    print("-" * 75)
    for lag in key_lags:
        i = lag - 1
        print(f"{lag:>5d} {acf_real[i]:>12.6f} {acf_markov[i]:>12.6f} {excess[i]:>12.6f} {z_excess[i]:>12.2f} {z_raw[i]:>12.2f}")

    # Find sign crossover in raw ACF
    print("\n--- Sign crossover detection ---")
    sign_changes = []
    for i in range(1, len(acf_real)):
        if acf_real[i-1] * acf_real[i] < 0:
            sign_changes.append(i + 1)  # lag number
    if sign_changes:
        print(f"Raw ACF sign changes at lags: {sign_changes[:20]}")
    else:
        print("No sign changes detected in raw ACF.")

    # Find where excess becomes significant
    print("\n--- Significant excess detection (|z| > 3) ---")
    sig_lags = [i+1 for i in range(len(z_excess)) if abs(z_excess[i]) > 3]
    if sig_lags:
        print(f"Significant excess at lags: {sig_lags[:30]}")
        # Group into ranges
        if len(sig_lags) > 1:
            ranges = []
            start = sig_lags[0]
            end = sig_lags[0]
            for l in sig_lags[1:]:
                if l == end + 1:
                    end = l
                else:
                    ranges.append((start, end))
                    start = l
                    end = l
            ranges.append((start, end))
            print(f"Contiguous ranges: {ranges[:15]}")
    else:
        print("No significant excess at any lag.")

    # Markov dominance: fraction of ACF explained by Markov
    print("\n--- Markov explanation power ---")
    # Only at lags where raw ACF is significant
    sig_raw = [i for i in range(len(z_raw)) if abs(z_raw[i]) > 3]
    if sig_raw:
        markov_explains = sum(1 for i in sig_raw if abs(z_excess[i]) < 3)
        total_sig = len(sig_raw)
        print(f"Lags with significant raw ACF: {total_sig}")
        print(f"Of these, Markov-1 explains (excess |z|<3): {markov_explains} ({100*markov_explains/total_sig:.1f}%)")
        print(f"Markov-1 fails (excess |z|>3): {total_sig - markov_explains} ({100*(total_sig-markov_explains)/total_sig:.1f}%)")

    # Desert analysis
    print("\n--- Desert analysis ---")
    # Find the "desert": longest run where |z_raw| < 3
    in_desert = np.abs(z_raw) < 3
    desert_start = None
    longest_desert = (0, 0, 0)  # (start, end, length)
    for i in range(len(in_desert)):
        if in_desert[i] and desert_start is None:
            desert_start = i + 1
        elif not in_desert[i] and desert_start is not None:
            length = (i + 1) - desert_start
            if length > longest_desert[2]:
                longest_desert = (desert_start, i, length)
            desert_start = None
    if desert_start is not None:
        length = max_lag - desert_start + 1
        if length > longest_desert[2]:
            longest_desert = (desert_start, max_lag, length)

    if longest_desert[2] > 0:
        print(f"Longest desert (|z_raw|<3): lags {longest_desert[0]}-{longest_desert[1]} (length {longest_desert[2]})")

    # Excess at long range
    print("\n--- Long-range excess (lags 50-200) ---")
    long_range = range(49, min(200, max_lag))
    lr_excess = [excess[i] for i in long_range]
    lr_z = [z_excess[i] for i in long_range]
    print(f"Mean excess: {np.mean(lr_excess):.8f}")
    print(f"Mean |z(excess)|: {np.mean(np.abs(lr_z)):.2f}")
    print(f"Max |z(excess)|: {np.max(np.abs(lr_z)):.2f} at lag {long_range[0] + 1 + np.argmax(np.abs(lr_z))}")
    n_sig_lr = sum(1 for z in lr_z if abs(z) > 3)
    print(f"Significant (|z|>3): {n_sig_lr} of {len(lr_z)} lags ({100*n_sig_lr/len(lr_z):.1f}%)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Autocorrelation excess beyond Markov-1')
    parser.add_argument('--N', type=int, default=2_000_000, help='Prime upper bound')
    parser.add_argument('--max_lag', type=int, default=200, help='Max lag to compute')
    parser.add_argument('--mod', type=int, default=6, help='Modulus for Markov chain')
    parser.add_argument('--n_shuffles', type=int, default=100, help='Number of shuffles')
    args = parser.parse_args()

    results = run_experiment(N=args.N, max_lag=args.max_lag, mod=args.mod, n_shuffles=args.n_shuffles)
    print_results(results, args.max_lag)
