#!/usr/bin/env python3
"""
exp_modular_algebra_depth.py — Modular Algebraic Memory Across Prime Moduli

Question: Does the algebraic ordering memory (found at mod-3) extend to mod-5, mod-7, mod-11, mod-13?
What is the Markov depth ratio M2/M1 for each modulus?

Method:
- Compute gap sequence g_n = p_{n+1} - p_n for first N primes
- For each modulus q in {3, 5, 7, 11, 13}:
  - Compute residues r_n = g_n mod q
  - Build order-1 and order-2 Markov transition matrices
  - Measure self-transition rates for each non-zero residue class
  - Compare with shuffle baseline (50 shuffles)
  - Compute M2/M1 = (info gained by order-2) / (info gained by order-1)
- Null baseline: shuffle gap ordering, preserve distribution

Output: tools/data/modular_algebra_depth.json
"""

import json
import numpy as np
from collections import Counter
from pathlib import Path
from sympy import primerange

def get_gaps(N=200000):
    """Get first N prime gaps."""
    primes = list(primerange(2, N * 20))[:N+1]
    return np.array([primes[i+1] - primes[i] for i in range(len(primes)-1)])

def markov_order1(residues, q):
    """Build order-1 transition matrix and compute entropy."""
    states = list(range(q))
    n_states = q
    counts = np.zeros((n_states, n_states))
    for i in range(len(residues) - 1):
        counts[residues[i], residues[i+1]] += 1
    # Normalize rows
    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    P = counts / row_sums
    # Stationary distribution from counts
    pi = counts.sum(axis=1)
    pi = pi / pi.sum()
    # Entropy rate H1 = -sum_i pi_i sum_j P_ij log P_ij
    H1 = 0
    for i in range(n_states):
        if pi[i] > 0:
            for j in range(n_states):
                if P[i, j] > 0:
                    H1 -= pi[i] * P[i, j] * np.log2(P[i, j])
    return P, pi, H1, counts

def markov_order2(residues, q):
    """Build order-2 transition matrix and compute entropy."""
    n_states = q
    # States are (i, j) pairs
    counts = np.zeros((n_states, n_states, n_states))
    for i in range(len(residues) - 2):
        counts[residues[i], residues[i+1], residues[i+2]] += 1
    # Entropy rate H2 = -sum_{i,j} pi_{ij} sum_k P_{ij->k} log P_{ij->k}
    # pi_{ij} = frequency of pair (i,j)
    pair_counts = counts.sum(axis=2)  # shape (q, q)
    total_pairs = pair_counts.sum()
    if total_pairs == 0:
        return 0, counts
    pi_pair = pair_counts / total_pairs
    H2 = 0
    for i in range(n_states):
        for j in range(n_states):
            if pair_counts[i, j] > 0:
                row = counts[i, j, :]
                row_sum = row.sum()
                if row_sum > 0:
                    probs = row / row_sum
                    for k in range(n_states):
                        if probs[k] > 0:
                            H2 -= pi_pair[i, j] * probs[k] * np.log2(probs[k])
    return H2, counts

def self_transition_rates(P, q):
    """Extract self-transition rates P(i->i) for each residue class."""
    return {i: float(P[i, i]) for i in range(q)}

def run_experiment():
    print("Generating prime gaps...")
    gaps = get_gaps(200000)
    N = len(gaps)
    print(f"  {N} gaps generated")

    moduli = [3, 5, 7, 11, 13]
    n_shuffles = 50
    results = {}

    for q in moduli:
        print(f"\n=== Modulus q = {q} ===")
        residues = gaps % q

        # Order-1 Markov
        P1, pi, H1, counts1 = markov_order1(residues, q)
        self_rates = self_transition_rates(P1, q)

        # Order-2 Markov
        H2, counts2 = markov_order2(residues, q)

        # Marginal entropy (order 0)
        H0 = 0
        for p_val in pi:
            if p_val > 0:
                H0 -= p_val * np.log2(p_val)

        # Information gains
        I1 = H0 - H1  # info from order-1 structure
        I2 = H1 - H2  # additional info from order-2
        M2_M1 = I2 / I1 if I1 > 0 else float('nan')

        print(f"  H0 (marginal) = {H0:.4f} bits")
        print(f"  H1 (order-1)  = {H1:.4f} bits")
        print(f"  H2 (order-2)  = {H2:.4f} bits")
        print(f"  I1 = H0-H1    = {I1:.4f} bits")
        print(f"  I2 = H1-H2    = {I2:.4f} bits")
        print(f"  M2/M1         = {M2_M1:.4f}")

        # Self-transition for non-zero residues
        nonzero_self = {k: v for k, v in self_rates.items() if k != 0}
        print(f"  Self-transitions (non-zero): {nonzero_self}")

        # Shuffle baseline
        shuffle_H1 = []
        shuffle_H2 = []
        shuffle_self = {i: [] for i in range(q)}
        for s in range(n_shuffles):
            shuf_gaps = np.random.permutation(gaps)
            shuf_res = shuf_gaps % q
            P1s, _, H1s, _ = markov_order1(shuf_res, q)
            H2s, _ = markov_order2(shuf_res, q)
            shuffle_H1.append(H1s)
            shuffle_H2.append(H2s)
            for i in range(q):
                shuffle_self[i].append(P1s[i, i])

        # Z-scores for self-transitions
        z_self = {}
        for i in range(q):
            sh_mean = np.mean(shuffle_self[i])
            sh_std = np.std(shuffle_self[i])
            if sh_std > 0:
                z = (self_rates[i] - sh_mean) / sh_std
            else:
                z = 0.0
            z_self[i] = {
                'real': self_rates[i],
                'shuffle_mean': sh_mean,
                'shuffle_std': sh_std,
                'z_score': z
            }

        # Z-score for I1, I2
        shuffle_I1 = [H0 - h1 for h1 in shuffle_H1]
        shuffle_I2 = [h1 - h2 for h1, h2 in zip(shuffle_H1, shuffle_H2)]

        z_I1 = (I1 - np.mean(shuffle_I1)) / np.std(shuffle_I1) if np.std(shuffle_I1) > 0 else 0
        z_I2 = (I2 - np.mean(shuffle_I2)) / np.std(shuffle_I2) if np.std(shuffle_I2) > 0 else 0

        # Expected self-transition under uniform (1/q for each)
        uniform_self = 1.0 / q

        # Count actual transitions that are "exact zero" or near-zero
        # For non-zero classes: is self_rate exactly 0?
        exact_zeros = {k: v == 0.0 for k, v in nonzero_self.items()}

        results[str(q)] = {
            'N_gaps': int(N),
            'H0_bits': round(H0, 5),
            'H1_bits': round(H1, 5),
            'H2_bits': round(H2, 5),
            'I1_bits': round(I1, 5),
            'I2_bits': round(I2, 5),
            'M2_M1': round(M2_M1, 5),
            'z_I1': round(float(z_I1), 2),
            'z_I2': round(float(z_I2), 2),
            'self_transitions': {str(k): round(v, 5) for k, v in self_rates.items()},
            'z_self_transitions': {str(k): {kk: round(vv, 4) if isinstance(vv, float) else vv
                                            for kk, vv in v.items()}
                                  for k, v in z_self.items()},
            'nonzero_exact_zeros': exact_zeros,
            'uniform_self_rate': round(uniform_self, 5),
            'stationary_dist': {str(k): round(float(v), 5) for k, v in enumerate(pi)}
        }

        print(f"  z(I1) = {z_I1:.1f}, z(I2) = {z_I2:.1f}")
        nz_z = {k: v['z_score'] for k, v in z_self.items() if k != 0}
        print(f"  z(self) non-zero: {nz_z}")

    # Summary table
    print("\n\n=== SUMMARY ===")
    print(f"{'q':>4} {'H0':>8} {'H1':>8} {'H2':>8} {'I1':>8} {'I2':>8} {'M2/M1':>8} {'z(I1)':>8} {'z(I2)':>8}")
    for q in moduli:
        r = results[str(q)]
        print(f"{q:4d} {r['H0_bits']:8.4f} {r['H1_bits']:8.4f} {r['H2_bits']:8.4f} "
              f"{r['I1_bits']:8.4f} {r['I2_bits']:8.4f} {r['M2_M1']:8.4f} "
              f"{r['z_I1']:8.1f} {r['z_I2']:8.1f}")

    # Save
    out_path = Path(__file__).parent / 'data' / 'modular_algebra_depth.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")

    return results

if __name__ == '__main__':
    run_experiment()
