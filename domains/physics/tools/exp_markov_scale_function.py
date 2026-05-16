#!/usr/bin/env python3
"""
exp_markov_scale_function.py — Scale dependence of Markov-3 ordering information in prime gaps.

Question: The Markov-3 mutual information (z=6203 globally) — does it decay with prime scale?
If so, does the decay track the GUE→Poisson boundary?

Method:
  - Generate primes up to 10^7 (~620K primes)
  - Divide into non-overlapping windows of W primes each
  - In each window, measure:
    1. Markov-3 conditional entropy of residue channel (gap mod 6 → {1,5} mapped to {0,1})
    2. Same after shuffling gaps within the window (null baseline)
    3. The ordering fraction: (H_shuffle - H_real) / H_shuffle
    4. Lag-1 ACF of gaps
    5. Brody parameter β (GUE/Poisson indicator)
  - Plot ordering fraction vs window center (log scale)

Null baseline: 50 shuffles per window.
"""

import numpy as np
import json
from collections import Counter
from pathlib import Path

def sieve_primes(limit):
    """Sieve of Eratosthenes."""
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]

def markov3_entropy(seq):
    """Conditional entropy H(X_t | X_{t-1}, X_{t-2}, X_{t-3}) for binary sequence."""
    if len(seq) < 4:
        return 1.0  # max entropy if too short
    # Count transitions from each 3-gram context
    contexts = Counter()
    transitions = Counter()
    for i in range(len(seq) - 3):
        ctx = (seq[i], seq[i+1], seq[i+2])
        nxt = seq[i+3]
        contexts[ctx] += 1
        transitions[(ctx, nxt)] += 1

    # Conditional entropy
    H = 0.0
    N = sum(contexts.values())
    for ctx, count in contexts.items():
        for symbol in [0, 1]:
            t_count = transitions.get((ctx, symbol), 0)
            if t_count > 0:
                p = t_count / count
                H -= (count / N) * p * np.log2(p)
    return H

def brody_beta(spacings):
    """Estimate Brody parameter β from gap spacings.
    β=0 → Poisson, β=1 → GUE (Wigner).
    Uses MLE on P(s) = (β+1)*b*s^β * exp(-b*s^{β+1}).
    """
    s = spacings / np.mean(spacings)  # normalize to mean 1
    s = s[s > 0]
    if len(s) < 10:
        return 0.5

    # Grid search for β
    best_beta = 0.0
    best_ll = -np.inf
    for beta_try in np.linspace(0.01, 1.5, 150):
        bp1 = beta_try + 1
        # b = Gamma((bp1+1)/bp1)^bp1 for mean=1 normalization
        from scipy.special import gammaln
        log_b = bp1 * gammaln((bp1 + 1) / bp1)
        b = np.exp(log_b)
        log_p = np.log(bp1) + log_b + beta_try * np.log(s) - b * s**bp1
        ll = np.sum(log_p)
        if ll > best_ll:
            best_ll = ll
            best_beta = beta_try
    return best_beta

def analyze_window(gaps, n_shuffles=50):
    """Analyze a single window of gaps."""
    # Residue channel: gap mod 6 mapped to binary
    residues = gaps % 6
    # In Z/6Z, prime gaps > 2 are always ≡ 0, 2, or 4 mod 6
    # But gap mod 6 for large primes: gaps are even, so mod 6 ∈ {0, 2, 4}
    # The two-channel uses mod-6 residue class of the prime itself
    # Actually: primes > 3 are 1 or 5 mod 6. Let me use the prime residues.
    # But we only have gaps here. The residue channel from the two-channel
    # decomposition maps gap → gap mod 6. Gaps between primes >3 are even,
    # so gap mod 6 ∈ {0, 2, 4}. That's 3 symbols, not 2.
    #
    # From exp_two_channel_shuffle_audit.py, the decomposition is:
    # magnitude = gap values, residue = gap mod 6
    # For Markov-3, we use the residue mod 6 sequence directly (3 symbols: 0,2,4)

    res_seq = tuple(int(r) for r in residues)

    # Markov-3 entropy on residue channel (3-symbol)
    H_real = markov3_entropy_general(res_seq, alphabet=[0, 2, 4])

    # Shuffle baseline
    H_shuffles = []
    for _ in range(n_shuffles):
        shuf = list(gaps.copy())
        np.random.shuffle(shuf)
        res_shuf = tuple(int(g % 6) for g in shuf)
        H_shuffles.append(markov3_entropy_general(res_shuf, alphabet=[0, 2, 4]))

    H_shuf_mean = np.mean(H_shuffles)
    H_shuf_std = np.std(H_shuffles)

    # Ordering fraction: how much entropy the ordering reduces
    if H_shuf_mean > 0:
        ordering_frac = (H_shuf_mean - H_real) / H_shuf_mean
    else:
        ordering_frac = 0.0

    # z-score
    z = (H_real - H_shuf_mean) / H_shuf_std if H_shuf_std > 0 else 0.0

    # Lag-1 ACF
    g = gaps.astype(float)
    g_centered = g - g.mean()
    var = np.var(g)
    if var > 0:
        lag1 = np.mean(g_centered[:-1] * g_centered[1:]) / var
    else:
        lag1 = 0.0

    # Brody parameter
    spacings = gaps.astype(float)
    beta = brody_beta(spacings)

    return {
        'H_real': float(H_real),
        'H_shuffle_mean': float(H_shuf_mean),
        'H_shuffle_std': float(H_shuf_std),
        'ordering_frac': float(ordering_frac),
        'z_score': float(z),
        'lag1_acf': float(lag1),
        'brody_beta': float(beta),
        'mean_gap': float(np.mean(gaps)),
    }

def markov3_entropy_general(seq, alphabet):
    """Conditional entropy H(X_t | X_{t-1}, X_{t-2}, X_{t-3}) for general alphabet."""
    if len(seq) < 4:
        return np.log2(len(alphabet))

    contexts = Counter()
    transitions = Counter()
    for i in range(len(seq) - 3):
        ctx = (seq[i], seq[i+1], seq[i+2])
        nxt = seq[i+3]
        contexts[ctx] += 1
        transitions[(ctx, nxt)] += 1

    H = 0.0
    N = sum(contexts.values())
    if N == 0:
        return np.log2(len(alphabet))
    for ctx, count in contexts.items():
        for symbol in alphabet:
            t_count = transitions.get((ctx, symbol), 0)
            if t_count > 0:
                p = t_count / count
                H -= (count / N) * p * np.log2(p)
    return H


def main():
    print("=== Markov-3 Scale Function: Ordering Information vs Prime Scale ===\n")

    # Generate primes
    LIMIT = 10_000_000
    print(f"Sieving primes up to {LIMIT:,}...")
    primes = sieve_primes(LIMIT)
    gaps = np.diff(primes)
    print(f"  {len(primes):,} primes, {len(gaps):,} gaps\n")

    # Window sizes to test
    W = 5000  # primes per window
    n_windows = len(gaps) // W
    print(f"Window size: {W} gaps, {n_windows} windows\n")

    results = []
    print(f"{'Window':>6} {'Center p':>12} {'ln(p)':>7} {'H_real':>7} {'H_shuf':>7} "
          f"{'Ord%':>6} {'z':>8} {'lag1':>7} {'beta':>5} {'<gap>':>7}")
    print("-" * 90)

    for i in range(n_windows):
        start = i * W
        end = start + W
        window_gaps = gaps[start:end]
        window_center_prime = primes[start + W // 2]

        res = analyze_window(window_gaps, n_shuffles=30)
        res['window_idx'] = i
        res['center_prime'] = int(window_center_prime)
        res['ln_center'] = float(np.log(window_center_prime))
        results.append(res)

        print(f"{i:>6} {window_center_prime:>12,} {res['ln_center']:>7.2f} "
              f"{res['H_real']:>7.4f} {res['H_shuffle_mean']:>7.4f} "
              f"{res['ordering_frac']*100:>5.1f}% {res['z_score']:>8.1f} "
              f"{res['lag1_acf']:>7.4f} {res['brody_beta']:>5.2f} {res['mean_gap']:>7.2f}")

    # Summary statistics
    print("\n=== Scale Function Analysis ===\n")

    ln_centers = [r['ln_center'] for r in results]
    ord_fracs = [r['ordering_frac'] for r in results]
    betas = [r['brody_beta'] for r in results]
    lag1s = [r['lag1_acf'] for r in results]
    z_scores = [r['z_score'] for r in results]

    # Linear regression: ordering_frac vs ln(p)
    ln_c = np.array(ln_centers)
    of = np.array(ord_fracs)
    slope_of, intercept_of = np.polyfit(ln_c, of, 1)
    resid = of - (slope_of * ln_c + intercept_of)
    r2_of = 1 - np.sum(resid**2) / np.sum((of - np.mean(of))**2)

    print(f"Ordering fraction vs ln(p):")
    print(f"  slope = {slope_of:.6f} per unit ln(p)")
    print(f"  intercept = {intercept_of:.4f}")
    print(f"  R² = {r2_of:.4f}")
    print(f"  First window: {ord_fracs[0]*100:.1f}%")
    print(f"  Last window:  {ord_fracs[-1]*100:.1f}%")

    # Linear regression: brody_beta vs ln(p)
    bt = np.array(betas)
    slope_bt, intercept_bt = np.polyfit(ln_c, bt, 1)
    resid_bt = bt - (slope_bt * ln_c + intercept_bt)
    r2_bt = 1 - np.sum(resid_bt**2) / np.sum((bt - np.mean(bt))**2)

    print(f"\nBrody β vs ln(p):")
    print(f"  slope = {slope_bt:.6f} per unit ln(p)")
    print(f"  intercept = {intercept_bt:.4f}")
    print(f"  R² = {r2_bt:.4f}")
    print(f"  First window: β = {betas[0]:.3f}")
    print(f"  Last window:  β = {betas[-1]:.3f}")

    # Correlation between ordering_frac and brody_beta
    corr_ob = np.corrcoef(of, bt)[0, 1]
    print(f"\nCorrelation(ordering_frac, brody_β) = {corr_ob:.4f}")

    # Correlation between ordering_frac and lag1
    l1 = np.array(lag1s)
    corr_ol = np.corrcoef(of, l1)[0, 1]
    print(f"Correlation(ordering_frac, lag1_ACF) = {corr_ol:.4f}")

    # Does ordering fraction converge?
    # Test: is the last 1/3 flat?
    n3 = len(ord_fracs) // 3
    last_third = ord_fracs[-n3:]
    slope_last, _ = np.polyfit(range(n3), last_third, 1)
    print(f"\nLast third slope (convergence test): {slope_last:.8f} per window")
    print(f"  Mean ordering in last third: {np.mean(last_third)*100:.2f}%")

    # z-score trend
    z_arr = np.array(z_scores)
    slope_z, _ = np.polyfit(ln_c, z_arr, 1)
    print(f"\nz-score vs ln(p): slope = {slope_z:.2f} per unit ln(p)")
    print(f"  z-score range: [{z_arr.min():.1f}, {z_arr.max():.1f}]")
    print(f"  ALL windows genuine (|z| > 2): {np.all(np.abs(z_arr) > 2)}")

    # Save results
    output = {
        'experiment': 'markov_scale_function',
        'description': 'Markov-3 ordering information as function of prime scale',
        'params': {'W': W, 'n_shuffles': 30, 'prime_limit': LIMIT},
        'n_windows': n_windows,
        'summary': {
            'ordering_frac_vs_lnp': {
                'slope': slope_of,
                'intercept': intercept_of,
                'R2': r2_of,
                'first_pct': ord_fracs[0] * 100,
                'last_pct': ord_fracs[-1] * 100,
            },
            'brody_vs_lnp': {
                'slope': slope_bt,
                'intercept': intercept_bt,
                'R2': r2_bt,
                'first': betas[0],
                'last': betas[-1],
            },
            'correlations': {
                'ordering_brody': corr_ob,
                'ordering_lag1': corr_ol,
            },
            'z_score_range': [float(z_arr.min()), float(z_arr.max())],
            'all_genuine': bool(np.all(np.abs(z_arr) > 2)),
        },
        'windows': results,
    }

    out_path = Path(__file__).parent / 'data' / 'markov_scale_function.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
