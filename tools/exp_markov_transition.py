"""
exp_markov_transition.py — Markov transition matrix fingerprint for ordered sequences.

Given an ordered sequence of integers, classifies elements by residue (mod m),
builds the Markov transition matrix, and computes:
  - Determinant and eigenvalues
  - Structural zeros (forbidden transitions)
  - z-score vs shuffle baseline
  - Higher-order Markov test (KL divergence 2nd vs 1st order)

Reusable tool: works on primes, Fibonacci, or any integer sequence.

Usage:
  python3 tools/exp_markov_transition.py --domain primes --nmax 12000000 --mod 6
  python3 tools/exp_markov_transition.py --domain fibonacci --nmax 1000 --mod 6
"""

import argparse
import numpy as np
from sympy import primerange, fibonacci

def generate_sequence(domain, nmax):
    if domain == "primes":
        primes = list(primerange(2, nmax))
        gaps = [primes[i+1] - primes[i] for i in range(len(primes)-1)]
        # Filter p > 5 for clean F2
        gaps = [primes[i+1] - primes[i] for i in range(len(primes)-1) if primes[i] > 5]
        return np.array(gaps), "prime gaps (p>5)"
    elif domain == "fibonacci":
        fibs = [int(fibonacci(i)) for i in range(2, nmax)]
        gaps = [fibs[i+1] - fibs[i] for i in range(len(fibs)-1)]
        return np.array(gaps), "fibonacci differences"
    else:
        raise ValueError(f"Unknown domain: {domain}")

def build_transition_matrix(state_seq, n_states):
    counts = np.zeros((n_states, n_states))
    for i in range(len(state_seq) - 1):
        counts[state_seq[i], state_seq[i+1]] += 1
    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    T = counts / row_sums
    return T, counts

def analyze(sequence, mod, n_shuffle=200):
    residues = sequence % mod
    unique_res = sorted(set(np.unique(residues)))
    state_map = {r: i for i, r in enumerate(unique_res)}
    n_states = len(unique_res)
    states = np.array([state_map[r] for r in residues])

    print(f"\n  States (residues mod {mod}): {unique_res}")
    print(f"  N states: {n_states}, N transitions: {len(states)-1}")

    T_real, C_real = build_transition_matrix(states, n_states)
    det_real = np.linalg.det(T_real)
    eigvals = np.linalg.eigvals(T_real)

    print(f"\n  Transition matrix:")
    for i in range(n_states):
        row = " ".join(f"{T_real[i,j]:.4f}" for j in range(n_states))
        print(f"    {unique_res[i]} -> {row}")

    print(f"\n  det(T) = {det_real:.8f}")
    print(f"  eigenvalues = {sorted(eigvals.real, reverse=True)}")

    # Structural zeros
    zeros = [(unique_res[i], unique_res[j]) for i in range(n_states)
             for j in range(n_states) if C_real[i,j] == 0]
    if zeros:
        print(f"  Structural zeros: {zeros}")

    # Shuffle baseline
    dets_shuf = []
    for _ in range(n_shuffle):
        perm = np.random.permutation(states)
        T_s, _ = build_transition_matrix(perm, n_states)
        dets_shuf.append(np.linalg.det(T_s))
    dets_shuf = np.array(dets_shuf)
    z = (det_real - dets_shuf.mean()) / dets_shuf.std() if dets_shuf.std() > 0 else 0
    print(f"\n  Shuffle: det mean={dets_shuf.mean():.2e}, std={dets_shuf.std():.2e}")
    print(f"  z-score: {z:.2f}")

    # 2nd order Markov KL
    if n_states <= 10:
        bigram_counts = np.zeros((n_states*n_states, n_states))
        for i in range(len(states) - 2):
            bigram = states[i] * n_states + states[i+1]
            bigram_counts[bigram, states[i+2]] += 1
        kl_total, n_bi = 0, 0
        for bi in range(n_states*n_states):
            s2 = bi % n_states
            total = bigram_counts[bi].sum()
            if total < 10:
                continue
            p2 = bigram_counts[bi] / total
            p1 = T_real[s2]
            mask = (p2 > 0) & (p1 > 0)
            kl = np.sum(p2[mask] * np.log(p2[mask] / p1[mask]))
            kl_total += kl * total
            n_bi += total
        kl_avg = kl_total / n_bi if n_bi > 0 else 0
        print(f"\n  KL(2nd order vs 1st order): {kl_avg:.6f} nats")

    return det_real, eigvals, z

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="primes")
    parser.add_argument("--nmax", type=int, default=12000000)
    parser.add_argument("--mod", type=int, default=6)
    parser.add_argument("--shuffle", type=int, default=200)
    args = parser.parse_args()

    np.random.seed(42)
    print(f"Domain: {args.domain}, N_max: {args.nmax}, mod: {args.mod}")
    seq, desc = generate_sequence(args.domain, args.nmax)
    print(f"Sequence: {desc}, length: {len(seq)}")

    analyze(seq, args.mod, args.shuffle)

if __name__ == "__main__":
    main()
