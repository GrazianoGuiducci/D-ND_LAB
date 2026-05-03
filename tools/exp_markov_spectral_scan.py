"""
exp_markov_spectral_scan.py — Spectral landscape of Markov transition matrices across moduli.

For an ordered integer sequence, builds the Markov transition matrix of residues
mod m for a range of moduli m, and extracts:
  - lambda_2(m): subdominant eigenvalue (real part, sorted by magnitude)
  - spectral_gap(m): 1 - |lambda_2|
  - det(m): determinant
  - n_states(m): number of active residue classes
  - z-score of det vs shuffle

Reusable tool: works on any integer sequence (primes, fibonacci, etc).

Usage:
  python3 tools/exp_markov_spectral_scan.py --domain primes --nmax 2000000 --mods 2-60
  python3 tools/exp_markov_spectral_scan.py --domain primes --nmax 2000000 --mods 4,6,8,10,12,30
"""

import argparse
import numpy as np
from sympy import primerange

def generate_gaps(domain, nmax):
    if domain == "primes":
        primes = list(primerange(7, nmax))  # p > 5 for clean F2
        gaps = np.array([primes[i+1] - primes[i] for i in range(len(primes)-1)])
        return gaps, f"prime gaps (p>5, up to {nmax})"
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

def spectral_analysis(sequence, mod, n_shuffle=100):
    residues = sequence % mod
    unique_res = sorted(set(residues))
    state_map = {r: i for i, r in enumerate(unique_res)}
    n_states = len(unique_res)
    states = np.array([state_map[r] for r in residues])

    T_real, C_real = build_transition_matrix(states, n_states)
    det_real = np.linalg.det(T_real)
    eigvals = np.linalg.eigvals(T_real)

    # Sort by magnitude, descending
    idx = np.argsort(-np.abs(eigvals))
    eigvals_sorted = eigvals[idx]

    # lambda_2 is the second eigenvalue by magnitude
    lambda_2 = eigvals_sorted[1].real if len(eigvals_sorted) > 1 else 0.0
    spectral_gap = 1 - abs(lambda_2)

    # Stationary distribution (left eigenvector of eigenvalue 1)
    eigvals_left, eigvecs_left = np.linalg.eig(T_real.T)
    idx1 = np.argmin(np.abs(eigvals_left - 1.0))
    pi = np.abs(eigvecs_left[:, idx1].real)
    pi = pi / pi.sum()

    # Structural zeros
    n_zeros = np.sum(C_real == 0)

    # Shuffle baseline for det
    dets_shuf = []
    l2_shuf = []
    for _ in range(n_shuffle):
        perm = np.random.permutation(states)
        T_s, _ = build_transition_matrix(perm, n_states)
        dets_shuf.append(np.linalg.det(T_s))
        ev_s = np.linalg.eigvals(T_s)
        idx_s = np.argsort(-np.abs(ev_s))
        l2_shuf.append(ev_s[idx_s[1]].real if len(ev_s) > 1 else 0.0)

    dets_shuf = np.array(dets_shuf)
    l2_shuf = np.array(l2_shuf)

    z_det = (det_real - dets_shuf.mean()) / dets_shuf.std() if dets_shuf.std() > 0 else 0
    z_l2 = (lambda_2 - l2_shuf.mean()) / l2_shuf.std() if l2_shuf.std() > 0 else 0

    return {
        'mod': mod,
        'n_states': n_states,
        'det': det_real,
        'lambda_2': lambda_2,
        'spectral_gap': spectral_gap,
        'eigvals': eigvals_sorted,
        'stationary': dict(zip(unique_res, pi)),
        'n_zeros': n_zeros,
        'z_det': z_det,
        'z_l2': z_l2,
        'l2_shuf_mean': l2_shuf.mean(),
        'l2_shuf_std': l2_shuf.std(),
    }

def parse_mods(mods_str):
    mods = []
    for part in mods_str.split(','):
        if '-' in part:
            a, b = part.split('-')
            mods.extend(range(int(a), int(b)+1))
        else:
            mods.append(int(part))
    return sorted(set(m for m in mods if m >= 2))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="primes")
    parser.add_argument("--nmax", type=int, default=2000000)
    parser.add_argument("--mods", default="2-60")
    parser.add_argument("--shuffle", type=int, default=100)
    args = parser.parse_args()

    np.random.seed(42)
    mods = parse_mods(args.mods)
    seq, desc = generate_gaps(args.domain, args.nmax)
    print(f"Domain: {desc}, length: {len(seq)}")
    print(f"Scanning moduli: {mods[0]}-{mods[-1]} ({len(mods)} values)")
    print()

    results = []
    print(f"{'mod':>4} {'n_st':>4} {'det':>10} {'lambda_2':>10} {'gap':>8} {'z_det':>8} {'z_l2':>8} {'l2_shuf':>10}")
    print("-" * 80)

    for m in mods:
        r = spectral_analysis(seq, m, args.shuffle)
        results.append(r)
        print(f"{r['mod']:4d} {r['n_states']:4d} {r['det']:10.6f} {r['lambda_2']:10.6f} "
              f"{r['spectral_gap']:8.4f} {r['z_det']:8.1f} {r['z_l2']:8.1f} {r['l2_shuf_mean']:10.6f}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    l2_vals = [r['lambda_2'] for r in results]
    z_l2_vals = [r['z_l2'] for r in results]
    gaps = [r['spectral_gap'] for r in results]

    print(f"\nlambda_2 range: [{min(l2_vals):.6f}, {max(l2_vals):.6f}]")
    print(f"lambda_2 mean:  {np.mean(l2_vals):.6f}")
    print(f"lambda_2 std:   {np.std(l2_vals):.6f}")
    print(f"\nspectral_gap range: [{min(gaps):.4f}, {max(gaps):.4f}]")
    print(f"\nz_l2 range: [{min(z_l2_vals):.1f}, {max(z_l2_vals):.1f}]")
    print(f"z_l2 > 3 (significant): {sum(abs(z) > 3 for z in z_l2_vals)}/{len(z_l2_vals)}")

    # Check: does lambda_2 cluster near -1/phi?
    phi = (1 + np.sqrt(5)) / 2
    inv_phi = -1/phi
    dists = [abs(l2 - inv_phi) for l2 in l2_vals]
    print(f"\n-1/phi = {inv_phi:.6f}")
    print(f"Distance to -1/phi: min={min(dists):.6f}, mean={np.mean(dists):.6f}, max={max(dists):.6f}")

    # Even vs odd moduli
    even_l2 = [r['lambda_2'] for r in results if r['mod'] % 2 == 0]
    odd_l2 = [r['lambda_2'] for r in results if r['mod'] % 2 == 1]
    if even_l2 and odd_l2:
        print(f"\nEven moduli lambda_2 mean: {np.mean(even_l2):.6f}")
        print(f"Odd moduli lambda_2 mean:  {np.mean(odd_l2):.6f}")

    # Multiples of 6 vs rest
    m6_l2 = [r['lambda_2'] for r in results if r['mod'] % 6 == 0]
    rest_l2 = [r['lambda_2'] for r in results if r['mod'] % 6 != 0]
    if m6_l2 and rest_l2:
        print(f"\nMultiples of 6 lambda_2 mean: {np.mean(m6_l2):.6f}")
        print(f"Non-multiples lambda_2 mean:  {np.mean(rest_l2):.6f}")

if __name__ == "__main__":
    main()
