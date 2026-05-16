#!/usr/bin/env python3
"""
exp_two_channel_universality.py — Is the two-channel decomposition unique to primes?

Consecutio from agent_0419_0330 (TWO_CHANNEL_DECOMPOSITION):
  "Test decomposition on other Z/mZ-structured sequences.
   If the decomposition is generic for any anti-correlated sequence
   with residue structure, it constrains C1 (primes unique under M)."

Question: The prime gap 1/k anti-correlation decomposes into a residue channel
(Z/6Z class alternation, acf1=-0.122, alpha=1.30) and a magnitude channel
(gap size within class, acf1=-0.030, alpha=0.95). The same-class magnitude
acf1 is 2.1x stronger than cross-class. Is this structure:
  (a) algebraic — any Z/6Z-structured sequence shows it, OR
  (b) number-theoretic — only primes show it?

Method: Construct 3 synthetic models with Z/6Z structure, measure same metrics.

Models:
  PRIMES:   Real prime gaps (baseline)
  MARKOV:   Z/6Z Markov chain (same transition probs as primes),
            gap sizes drawn i.i.d. from empirical distribution per transition type
  CLASS_SHUFFLE: Keep real gap sizes in order, randomize Z/6Z class assignments
  MAG_SHUFFLE:   Keep real Z/6Z class sequence, shuffle gap sizes within each
                 transition type

Key discriminator: the same-class magnitude asymmetry (2.1x in primes).
  - MARKOV has Z/6Z + correct marginals but no ordering → tests algebraic origin
  - CLASS_SHUFFLE has real magnitudes but random classes → tests class contribution
  - MAG_SHUFFLE has real classes but random magnitudes → tests magnitude contribution

Usage:
    python tools/exp_two_channel_universality.py [--n_primes N] [--n_trials T]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def sieve_primes(limit):
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def get_primes(n_target):
    limit = int(n_target * (np.log(n_target) + np.log(np.log(n_target)) + 2))
    limit = max(limit, 1000)
    primes = sieve_primes(limit)
    while len(primes) < n_target:
        limit = int(limit * 1.5)
        primes = sieve_primes(limit)
    return primes[:n_target]


def acf(x, max_lag=50):
    n = len(x)
    x_c = x - x.mean()
    v = np.var(x)
    if v == 0:
        return np.zeros(max_lag)
    return np.array([np.mean(x_c[:n-k] * x_c[k:]) / v if k < n else 0.0
                     for k in range(max_lag)])


def fit_power_law(acf_vals, min_lag=1, max_lag=20):
    lags = np.arange(min_lag, min(max_lag + 1, len(acf_vals)))
    vals = np.abs(acf_vals[min_lag:min_lag + len(lags)])
    pos = vals > 0
    if pos.sum() < 3:
        return np.nan, np.nan, np.nan
    log_k = np.log(lags[pos])
    log_v = np.log(vals[pos])
    c = np.polyfit(log_k, log_v, 1)
    pred = c[0] * log_k + c[1]
    ss_r = np.sum((log_v - pred)**2)
    ss_t = np.sum((log_v - log_v.mean())**2)
    return np.exp(c[1]), -c[0], (1 - ss_r/ss_t) if ss_t > 0 else 0.0


def decompose(gaps, classes_left, classes_right):
    """Given gaps and Z/6Z classes, decompose into residue + magnitude channels."""
    res_ch = np.where(classes_left == 1, 1.0, -1.0)
    trans = classes_left * 10 + classes_right
    mag_ch = gaps.astype(float).copy()
    for tt in np.unique(trans):
        mask = trans == tt
        if mask.sum() > 1:
            mag_ch[mask] -= mag_ch[mask].mean()
    return res_ch, mag_ch, trans


def measure_channels(gaps, classes_left, classes_right, label=""):
    """Measure all channel metrics for a gap sequence with class labels."""
    res_ch, mag_ch, trans = decompose(gaps, classes_left, classes_right)

    # Global ACFs
    acf_full = acf(gaps.astype(float), 30)
    acf_res = acf(res_ch, 30)
    acf_mag = acf(mag_ch, 30)

    # Power-law fits
    A_full, alpha_full, r2_full = fit_power_law(acf_full)
    A_res, alpha_res, r2_res = fit_power_law(acf_res)
    A_mag, alpha_mag, r2_mag = fit_power_law(acf_mag)

    # Same-class vs cross-class magnitude acf1
    same_acf1s = []
    cross_acf1s = []
    for tt in np.unique(trans):
        mask = trans == tt
        mc = mag_ch[mask]
        if len(mc) > 100:
            a1 = acf(mc, 2)[1]
            is_same = (tt // 10) == (tt % 10)
            if is_same:
                same_acf1s.append(a1)
            else:
                cross_acf1s.append(a1)

    same_mean = np.mean(same_acf1s) if same_acf1s else 0.0
    cross_mean = np.mean(cross_acf1s) if cross_acf1s else 0.0
    asymmetry = abs(same_mean / cross_mean) if cross_mean != 0 else np.inf

    # Transition statistics
    trans_stats = {}
    for tt in [11, 15, 51, 55]:
        mask = trans == tt
        if mask.sum() > 0:
            trans_stats[str(tt)] = {
                'count': int(mask.sum()),
                'mean_gap': float(gaps[mask].mean()),
                'std_gap': float(gaps[mask].std()),
            }

    return {
        'label': label,
        'n_gaps': len(gaps),
        'acf1_full': float(acf_full[1]),
        'acf1_res': float(acf_res[1]),
        'acf1_mag': float(acf_mag[1]),
        'alpha_full': float(alpha_full) if not np.isnan(alpha_full) else None,
        'alpha_res': float(alpha_res) if not np.isnan(alpha_res) else None,
        'alpha_mag': float(alpha_mag) if not np.isnan(alpha_mag) else None,
        'A_res': float(A_res) if not np.isnan(A_res) else None,
        'A_mag': float(A_mag) if not np.isnan(A_mag) else None,
        'same_class_acf1': float(same_mean),
        'cross_class_acf1': float(cross_mean),
        'asymmetry_ratio': float(asymmetry) if not np.isinf(asymmetry) else None,
        'transition_stats': trans_stats,
        'acf_full_10': [float(x) for x in acf_full[:10]],
        'acf_res_10': [float(x) for x in acf_res[:10]],
        'acf_mag_10': [float(x) for x in acf_mag[:10]],
    }


def generate_markov(gaps_real, classes_left_real, classes_right_real, n_gaps):
    """
    Z/6Z Markov chain with same transition probs as primes.
    Gap sizes drawn i.i.d. from empirical distribution per transition type.
    No sequential memory in magnitudes.
    """
    trans_real = classes_left_real * 10 + classes_right_real
    # Transition probabilities
    trans_probs = {}
    for cl in [1, 5]:
        counts = {}
        mask_l = classes_left_real == cl
        for cr in [1, 5]:
            mask = mask_l & (classes_right_real == cr)
            counts[cr] = mask.sum()
        total = sum(counts.values())
        trans_probs[cl] = {cr: c / total for cr, c in counts.items()}

    # Gap distributions per transition type
    gap_pools = {}
    for tt in [11, 15, 51, 55]:
        mask = trans_real == tt
        gap_pools[tt] = gaps_real[mask]

    # Generate Markov chain
    classes = np.zeros(n_gaps + 1, dtype=int)
    classes[0] = np.random.choice([1, 5])
    gaps = np.zeros(n_gaps, dtype=float)

    for i in range(n_gaps):
        cl = classes[i]
        p1 = trans_probs[cl][1]
        cr = 1 if np.random.random() < p1 else 5
        classes[i + 1] = cr
        tt = cl * 10 + cr
        gaps[i] = np.random.choice(gap_pools[tt])

    return gaps, classes[:-1], classes[1:]


def generate_class_shuffle(gaps_real, classes_left_real, classes_right_real):
    """Keep gap magnitudes in real order, randomize class assignments."""
    n = len(gaps_real)
    # Random class sequence with same frequency
    freq_1 = (classes_left_real == 1).mean()
    classes = np.where(np.random.random(n + 1) < freq_1, 1, 5)
    return gaps_real.copy(), classes[:-1], classes[1:]


def generate_mag_shuffle(gaps_real, classes_left_real, classes_right_real):
    """Keep real class sequence, shuffle gap sizes within each transition type."""
    trans = classes_left_real * 10 + classes_right_real
    gaps = gaps_real.copy()
    for tt in np.unique(trans):
        mask = trans == tt
        idx = np.where(mask)[0]
        gaps[idx] = np.random.permutation(gaps[idx])
    return gaps, classes_left_real.copy(), classes_right_real.copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=2_000_000)
    parser.add_argument('--n_trials', type=int, default=20)
    args = parser.parse_args()

    np.random.seed(42)

    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    p = primes[primes > 3]
    gaps = np.diff(p)
    cl = p[:-1] % 6
    cr = p[1:] % 6
    print(f"Got {len(gaps):,} gaps up to p={p[-1]:,}")

    # === PRIMES baseline ===
    print("\n=== PRIMES (baseline) ===")
    prime_result = measure_channels(gaps, cl, cr, "PRIMES")
    print(f"  acf1: full={prime_result['acf1_full']:.6f}  res={prime_result['acf1_res']:.6f}  mag={prime_result['acf1_mag']:.6f}")
    print(f"  alpha: res={prime_result['alpha_res']:.3f}  mag={prime_result['alpha_mag']:.3f}")
    print(f"  Same-class mag acf1: {prime_result['same_class_acf1']:.6f}")
    print(f"  Cross-class mag acf1: {prime_result['cross_class_acf1']:.6f}")
    print(f"  Asymmetry ratio: {prime_result['asymmetry_ratio']:.2f}x")

    # === SYNTHETIC MODELS (averaged over trials) ===
    models = {
        'MARKOV': generate_markov,
        'CLASS_SHUFFLE': generate_class_shuffle,
        'MAG_SHUFFLE': generate_mag_shuffle,
    }

    all_results = {'PRIMES': prime_result}

    for model_name, generator in models.items():
        print(f"\n=== {model_name} ({args.n_trials} trials) ===")
        trial_results = []

        for t in range(args.n_trials):
            if model_name == 'MARKOV':
                g, c_l, c_r = generator(gaps, cl, cr, len(gaps))
            else:
                g, c_l, c_r = generator(gaps, cl, cr)
            trial_results.append(measure_channels(g, c_l, c_r, f"{model_name}_{t}"))

        # Average over trials
        avg = {}
        keys = ['acf1_full', 'acf1_res', 'acf1_mag', 'alpha_res', 'alpha_mag',
                'same_class_acf1', 'cross_class_acf1', 'asymmetry_ratio',
                'A_res', 'A_mag']
        for k in keys:
            vals = [r[k] for r in trial_results if r[k] is not None]
            if vals:
                avg[k] = float(np.mean(vals))
                avg[f'{k}_std'] = float(np.std(vals))

        print(f"  acf1: full={avg.get('acf1_full',0):.6f}  res={avg.get('acf1_res',0):.6f}  mag={avg.get('acf1_mag',0):.6f}")
        print(f"  alpha: res={avg.get('alpha_res',0):.3f}+/-{avg.get('alpha_res_std',0):.3f}  mag={avg.get('alpha_mag',0):.3f}+/-{avg.get('alpha_mag_std',0):.3f}")
        print(f"  Same-class mag acf1: {avg.get('same_class_acf1',0):.6f} +/- {avg.get('same_class_acf1_std',0):.6f}")
        print(f"  Cross-class mag acf1: {avg.get('cross_class_acf1',0):.6f} +/- {avg.get('cross_class_acf1_std',0):.6f}")
        print(f"  Asymmetry ratio: {avg.get('asymmetry_ratio',0):.2f}x +/- {avg.get('asymmetry_ratio_std',0):.2f}")

        # Z-score vs primes for key metrics
        for metric in ['same_class_acf1', 'asymmetry_ratio', 'acf1_res']:
            if f'{metric}_std' in avg and avg[f'{metric}_std'] > 0 and prime_result[metric] is not None:
                z = (prime_result[metric] - avg[metric]) / avg[f'{metric}_std']
                print(f"  z({metric} vs primes) = {z:.1f}")

        all_results[model_name] = {
            'mean': avg,
            'n_trials': args.n_trials,
            'individual': [{'label': r['label'],
                           'acf1_full': r['acf1_full'],
                           'acf1_res': r['acf1_res'],
                           'acf1_mag': r['acf1_mag'],
                           'same_class_acf1': r['same_class_acf1'],
                           'cross_class_acf1': r['cross_class_acf1'],
                           'asymmetry_ratio': r['asymmetry_ratio']}
                          for r in trial_results]
        }

    # === SUMMARY TABLE ===
    print("\n" + "=" * 90)
    print(f"{'Model':>16} | {'acf1_res':>10} | {'acf1_mag':>10} | {'alpha_res':>10} | {'same_cl':>10} | {'cross_cl':>10} | {'asym':>6}")
    print("-" * 90)
    # Primes
    p = prime_result
    print(f"{'PRIMES':>16} | {p['acf1_res']:10.6f} | {p['acf1_mag']:10.6f} | {p['alpha_res']:10.3f} | {p['same_class_acf1']:10.6f} | {p['cross_class_acf1']:10.6f} | {p['asymmetry_ratio']:6.2f}x")
    for model_name in ['MARKOV', 'CLASS_SHUFFLE', 'MAG_SHUFFLE']:
        m = all_results[model_name]['mean']
        print(f"{model_name:>16} | {m.get('acf1_res',0):10.6f} | {m.get('acf1_mag',0):10.6f} | {m.get('alpha_res',0):10.3f} | {m.get('same_class_acf1',0):10.6f} | {m.get('cross_class_acf1',0):10.6f} | {m.get('asymmetry_ratio',0):6.2f}x")

    # === SAVE ===
    out_path = Path(__file__).parent / 'data' / 'exp_two_channel_universality.json'
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
