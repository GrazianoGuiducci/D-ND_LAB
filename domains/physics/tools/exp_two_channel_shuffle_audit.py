#!/usr/bin/env python3
"""
exp_two_channel_shuffle_audit.py — META tautology audit on two-channel decomposition.

Question: Does the two-channel structure (spectral independence, different PSD slopes,
Markov closure of residue, pair-dominance of magnitude) survive shuffling?
If yes → tautology (structure in values, not order).
If no → genuine (structure in ordering).

Usage:
    python tools/exp_two_channel_shuffle_audit.py [--N 100000] [--n_shuffle 50]
"""

import argparse
import json
import numpy as np
from sympy import primerange
from scipy import signal


def get_prime_gaps(N):
    """Get first N prime gaps."""
    primes = list(primerange(2, int(N * np.log(N) * 1.3) + 1000))[:N + 1]
    gaps = np.diff(primes).astype(float)
    return gaps, np.array(primes[:len(gaps)])


def decompose_two_channel(gaps):
    """Decompose gaps into magnitude and residue channels."""
    magnitude = gaps  # gaps are already positive
    residue = gaps % 6  # on Z/6Z: {0, 2, 4} for gaps (mostly {2, 4} for p>3)
    return magnitude, residue


def psd_slope(x, nperseg=256):
    """Compute PSD slope via Welch method."""
    x_centered = x - np.mean(x)
    if np.std(x_centered) < 1e-12:
        return 0.0, np.array([]), np.array([])
    f, pxx = signal.welch(x_centered, nperseg=min(nperseg, len(x) // 4),
                          noverlap=min(nperseg, len(x) // 4) // 2)
    mask = f > 0
    f, pxx = f[mask], pxx[mask]
    pxx = np.maximum(pxx, 1e-30)
    log_f, log_p = np.log10(f), np.log10(pxx)
    slope, _ = np.polyfit(log_f, log_p, 1)
    return slope, f, pxx


def cross_correlation_lag0(a, b):
    """Pearson correlation between two channels."""
    a_c = a - np.mean(a)
    b_c = b - np.mean(b)
    denom = np.std(a_c) * np.std(b_c)
    if denom < 1e-12:
        return 0.0
    return np.corrcoef(a_c, b_c)[0, 1]


def acf(x, max_lag=10):
    """Normalized autocorrelation function."""
    x_c = x - np.mean(x)
    var = np.var(x_c)
    if var < 1e-12:
        return np.zeros(max_lag)
    result = np.correlate(x_c, x_c, mode='full')
    mid = len(result) // 2
    return result[mid:mid + max_lag] / (var * len(x_c))


def markov_transition_matrix(residue_seq, order=3):
    """Estimate Markov transition matrix of given order on residue states."""
    states = sorted(set(residue_seq))
    state_map = {s: i for i, s in enumerate(states)}
    n_states = len(states)

    # For order-k Markov, count transitions from k-grams to next state
    counts = {}
    for i in range(order, len(residue_seq)):
        key = tuple(residue_seq[i - order:i])
        nxt = residue_seq[i]
        if key not in counts:
            counts[key] = np.zeros(n_states)
        counts[key][state_map[nxt]] += 1

    # Predict the sequence using the Markov model
    predictions = []
    actuals = []
    for i in range(order, len(residue_seq)):
        key = tuple(residue_seq[i - order:i])
        if key in counts:
            total = counts[key].sum()
            if total > 0:
                probs = counts[key] / total
                predictions.append(probs)
                actuals.append(state_map[residue_seq[i]])

    if not predictions:
        return 0.0

    # Log-likelihood ratio vs uniform
    n_s = n_states
    ll_markov = 0.0
    ll_uniform = 0.0
    for prob, actual in zip(predictions, actuals):
        p_m = max(prob[actual], 1e-10)
        ll_markov += np.log(p_m)
        ll_uniform += np.log(1.0 / n_s)

    # Return bits per symbol advantage
    bits_advantage = (ll_markov - ll_uniform) / (len(predictions) * np.log(2))
    return bits_advantage


def psd_convergence_depth(x, max_lag=20):
    """Find K* — number of ACF lags needed to capture 95% of PSD slope."""
    full_slope, _, _ = psd_slope(x)
    if abs(full_slope) < 1e-6:
        return 1, 1.0

    acf_vals = acf(x, max_lag=max_lag + 1)

    # Cumulative contribution of each lag
    cumulative = 0.0
    for k in range(1, max_lag + 1):
        # Each lag contributes proportionally to ACF(k)
        cumulative += abs(acf_vals[k]) if k < len(acf_vals) else 0

    total = cumulative
    if total < 1e-12:
        return 1, 1.0

    running = 0.0
    for k in range(1, max_lag + 1):
        running += abs(acf_vals[k]) if k < len(acf_vals) else 0
        if running / total >= 0.95:
            return k, running / total

    return max_lag, running / total if total > 0 else 0.0


def measure_properties(gaps, label=""):
    """Measure all two-channel properties."""
    mag, res = decompose_two_channel(gaps)

    # 1. PSD slopes
    slope_mag, _, _ = psd_slope(mag)
    slope_res, _, _ = psd_slope(res)

    # 2. Cross-correlation
    xcorr = cross_correlation_lag0(mag, res)

    # 3. ACF lag-1 of total gaps
    acf_vals = acf(gaps, max_lag=5)
    lag1 = acf_vals[1] if len(acf_vals) > 1 else 0.0

    # 4. Residue Markov advantage (bits/symbol over uniform)
    res_int = res.astype(int).tolist()
    markov_bits = markov_transition_matrix(res_int, order=3)

    # 5. Magnitude convergence depth K*
    k_star, k_capture = psd_convergence_depth(mag, max_lag=10)

    # 6. Slope ratio (residue/magnitude)
    slope_ratio = slope_res / slope_mag if abs(slope_mag) > 1e-6 else float('inf')

    return {
        'label': label,
        'slope_mag': round(slope_mag, 4),
        'slope_res': round(slope_res, 4),
        'slope_ratio': round(slope_ratio, 3),
        'xcorr': round(xcorr, 4),
        'lag1_total': round(lag1, 4),
        'markov3_bits': round(markov_bits, 4),
        'k_star': k_star,
        'k_capture': round(k_capture, 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=100000, help='Number of primes')
    parser.add_argument('--n_shuffle', type=int, default=50, help='Number of shuffle trials')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    print(f"=== Two-Channel Shuffle Audit (META tautology test) ===")
    print(f"N={args.N} primes, {args.n_shuffle} shuffle trials\n")

    # Real primes
    gaps, primes = get_prime_gaps(args.N)
    real = measure_properties(gaps, "REAL_PRIMES")

    print(f"--- REAL PRIMES ---")
    for k, v in real.items():
        if k != 'label':
            print(f"  {k}: {v}")

    # Shuffle trials
    shuffle_results = []
    for i in range(args.n_shuffle):
        shuffled = gaps.copy()
        rng.shuffle(shuffled)
        r = measure_properties(shuffled, f"shuffle_{i}")
        shuffle_results.append(r)

    # Aggregate shuffle statistics
    keys = ['slope_mag', 'slope_res', 'slope_ratio', 'xcorr', 'lag1_total',
            'markov3_bits', 'k_star', 'k_capture']

    print(f"\n--- SHUFFLE DISTRIBUTION (n={args.n_shuffle}) ---")
    print(f"{'property':>15} | {'real':>9} | {'shuf_mean':>9} | {'shuf_std':>9} | {'z-score':>9} | {'survives?':>9}")
    print("-" * 75)

    verdicts = {}
    for k in keys:
        vals = [r[k] for r in shuffle_results]
        mean_s = np.mean(vals)
        std_s = np.std(vals)
        real_v = real[k]
        z = (real_v - mean_s) / std_s if std_s > 1e-12 else 0.0
        survives = abs(z) < 2.0  # within 2 sigma of shuffle → tautology
        verdicts[k] = {
            'real': float(real_v),
            'shuffle_mean': round(float(mean_s), 4),
            'shuffle_std': round(float(std_s), 4),
            'z_score': round(float(z), 2),
            'survives_shuffle': bool(survives),
            'verdict': 'TAUTOLOGY' if survives else 'GENUINE'
        }
        tag = "TAUTOLOGY" if survives else "GENUINE"
        print(f"{k:>15} | {real_v:>9} | {mean_s:>9.4f} | {std_s:>9.4f} | {z:>9.2f} | {tag:>9}")

    # Summary
    tautologies = [k for k, v in verdicts.items() if v['verdict'] == 'TAUTOLOGY']
    genuine = [k for k, v in verdicts.items() if v['verdict'] == 'GENUINE']

    print(f"\n=== SUMMARY ===")
    print(f"TAUTOLOGIES (survive shuffle, |z|<2): {tautologies}")
    print(f"GENUINE (break under shuffle, |z|>=2): {genuine}")
    print(f"\nTautology ratio: {len(tautologies)}/{len(verdicts)} = {len(tautologies)/len(verdicts):.0%}")

    # Save results
    output = {
        'experiment': 'two_channel_shuffle_audit',
        'N': args.N,
        'n_shuffle': args.n_shuffle,
        'real_properties': real,
        'verdicts': verdicts,
        'tautologies': tautologies,
        'genuine': genuine,
        'tautology_ratio': len(tautologies) / len(verdicts),
    }

    out_path = 'tools/data/two_channel_shuffle_audit.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")

    return output


if __name__ == '__main__':
    main()
