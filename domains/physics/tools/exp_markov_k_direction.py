#!/usr/bin/env python3
"""
exp_markov_k_direction.py — Direction of Markov-k memory in the dipolar plane.

Consecutio from piano 60 (agent_20260501_0330):
  "The 3-deg residual is Markov-2+ memory. Markov-3 has z=6203.
   Does the Markov-3 component have a preferred direction in (SR, L1)?"

Answer: NO. With proper binning (equal-count), Markov-1 already captures the
full dipolar angle within noise (z=1.4). The massive Markov-3 signal (z=6203)
is orthogonal to the (SR, L1) plane — it exists but doesn't shape the dipolar
direction. The "3 deg residual" of the previous experiment was inflated by
coarse fixed-edge binning (the 14+ catch-all bin).

Method:
  1. Build Markov-k surrogates for k=0,1,2,3 from real prime gaps
  2. Use equal-count (percentile) bins — NOT fixed edges
  3. Per-source shuffle baseline (each surrogate vs its own permutation)
  4. Sample from gap pools (actual values), not bin centers
  5. Compare dipolar angles across Markov orders

Usage:
    python tools/exp_markov_k_direction.py [--N 100000] [--n_trials 20] [--n_bins 14]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def get_primes(n_max):
    """Sieve of Eratosthenes."""
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def spacing_ratio(gaps):
    """Mean ratio min/max of consecutive gaps."""
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r[np.isfinite(r)])


def lag1_acf(gaps):
    """Lag-1 autocorrelation."""
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0:
        return 0.0
    return np.mean(g[:-1] * g[1:]) / c0


def shuffle_baseline(gaps, n_shuffle=100):
    """Shuffle mean of (SR, L1) — per-source baseline."""
    rng = np.random.default_rng(9999)
    sr_list, l1_list = [], []
    for _ in range(n_shuffle):
        sg = rng.permutation(gaps)
        sr_list.append(spacing_ratio(sg))
        l1_list.append(lag1_acf(sg))
    return np.mean(sr_list), np.mean(l1_list), np.std(sr_list), np.std(l1_list)


def dipolar_vector(gaps, n_shuffle=100):
    """Compute dipolar vector relative to own shuffle baseline."""
    sr_real = spacing_ratio(gaps)
    l1_real = lag1_acf(gaps)
    sr_shuf, l1_shuf, sr_std, l1_std = shuffle_baseline(gaps, n_shuffle)
    dsr = sr_real - sr_shuf
    dl1 = l1_real - l1_shuf
    theta = np.degrees(np.arctan2(dl1, dsr))
    mag = np.sqrt(dsr**2 + dl1**2)
    ratio = abs(dl1 / dsr) if abs(dsr) > 1e-10 else float('inf')
    return {
        'theta': theta, 'magnitude': mag, 'dL1_over_dSR': ratio,
        'delta_SR': dsr, 'delta_L1': dl1,
    }


def make_bins(gaps, n_bins=14):
    """Equal-count (percentile) binning with gap pools for realistic sampling."""
    percentiles = np.linspace(0, 100, n_bins + 1)
    edges = list(np.unique(np.percentile(gaps, percentiles)))
    edges[0] = 0
    edges[-1] = gaps.max() + 1
    nb = len(edges) - 1
    bi = np.clip(np.digitize(gaps, edges) - 1, 0, nb - 1)
    pools = {}
    for b in range(nb):
        m = bi == b
        pools[b] = gaps[m].copy() if m.any() else np.array([np.mean(edges[b:b+2])])
    marg = np.bincount(bi, minlength=nb).astype(float)
    marg /= marg.sum()
    return bi, pools, marg, nb, edges


def build_markov_k(bi, nb, k):
    """Build Markov-k transition dict from binned sequence."""
    counts = {}
    for i in range(k, len(bi)):
        ctx = tuple(bi[i-k:i])
        if ctx not in counts:
            counts[ctx] = np.zeros(nb, dtype=int)
        counts[ctx][bi[i]] += 1
    result = {}
    sparse = 0
    for ctx, cnt in counts.items():
        if cnt.sum() >= 5:
            result[ctx] = cnt / cnt.sum()
        else:
            sparse += 1
    return result, sparse, len(counts)


def gen_markov_k(trans_by_order, pools, n_gaps, k_max, marg, rng):
    """Generate Markov-k surrogate with fallback and gap-pool sampling."""
    nb = len(marg)
    gaps = np.zeros(n_gaps)
    states = list(rng.choice(nb, size=k_max, p=marg))
    for i in range(k_max):
        p = pools[states[i]]
        gaps[i] = p[rng.integers(len(p))]
    for i in range(k_max, n_gaps):
        chosen = False
        for k in range(k_max, 0, -1):
            ctx = tuple(states[-k:])
            t = trans_by_order.get(k, {})
            if ctx in t:
                state = rng.choice(nb, p=t[ctx])
                chosen = True
                break
        if not chosen:
            state = rng.choice(nb, p=marg)
        p = pools[state]
        gaps[i] = p[rng.integers(len(p))]
        states.append(state)
    return gaps


def run_experiment(N=100000, n_trials=20, n_bins=14, n_shuffle=100):
    """Main experiment."""
    print("=" * 70)
    print("MARKOV-k DIRECTIONAL DECOMPOSITION (equal-count bins)")
    print("Does higher-order memory point GUE-ward in the (SR, L1) plane?")
    print("=" * 70)

    primes = get_primes(max(N * 25, 5_000_000))
    p = primes[primes > 10000][:N + 1]
    gaps = np.diff(p).astype(float)
    print(f"\n{len(gaps)} prime gaps, range [{p[0]}, {p[-1]}]")

    real = dipolar_vector(gaps, n_shuffle)
    print(f"Real primes: theta={real['theta']:.1f}, |d|={real['magnitude']:.4f}, "
          f"dL1/dSR={real['dL1_over_dSR']:.3f}")

    bi, pools, marg, nb, edges = make_bins(gaps, n_bins)
    print(f"{nb} bins (equal-count)")

    all_trans = {}
    for k in [1, 2, 3]:
        t, sp, tot = build_markov_k(bi, nb, k)
        all_trans[k] = t
        print(f"  Markov-{k}: {tot} contexts, {sp} sparse, {tot-sp} usable")

    GUE_THETA = -97.0
    results = {}

    for k_max in [0, 1, 2, 3]:
        thetas, mags, ratios = [], [], []
        for trial in range(n_trials):
            rng = np.random.default_rng(1000 * k_max + trial)
            if k_max == 0:
                states = rng.choice(nb, size=len(gaps), p=marg)
                sg = np.array([pools[s][rng.integers(len(pools[s]))] for s in states])
            else:
                tf = {k: all_trans[k] for k in range(1, k_max + 1)}
                sg = gen_markov_k(tf, pools, len(gaps), k_max, marg, rng)
            d = dipolar_vector(sg, 50)
            thetas.append(d['theta'])
            mags.append(d['magnitude'])
            ratios.append(d['dL1_over_dSR'])

        tm, ts = np.mean(thetas), np.std(thetas)
        delta = real['theta'] - tm
        while delta > 180: delta -= 360
        while delta < -180: delta += 360
        z = abs(delta) / max(ts, 0.1)
        results[k_max] = {
            'theta_mean': float(tm), 'theta_std': float(ts),
            'mag_mean': float(np.mean(mags)),
            'ratio_mean': float(np.mean(ratios)), 'ratio_std': float(np.std(ratios)),
            'residual_deg': float(delta), 'z': float(z),
        }
        print(f"\nMarkov-{k_max}: theta={tm:.1f}+/-{ts:.1f}, |d|={np.mean(mags):.4f}, "
              f"ratio={np.mean(ratios):.3f}, residual={delta:+.1f} deg (z={z:.1f})")

    # Scale check
    print(f"\n--- SCALE CHECK ---")
    scale_results = []
    for lo, hi in [(10000, 100000), (100000, 1000000), (1000000, 5000000)]:
        pm = (primes > lo) & (primes < hi)
        ps = primes[pm]
        if len(ps) < 200:
            continue
        gs = np.diff(ps).astype(float)
        real_s = dipolar_vector(gs, 80)
        bi_s, pools_s, marg_s, nb_s, _ = make_bins(gs, min(n_bins, max(5, len(gs) // 500)))

        for k_test in [1, 3]:
            trans_s = {}
            for k in range(1, k_test + 1):
                t, _, _ = build_markov_k(bi_s, nb_s, k)
                trans_s[k] = t
            ts_list = []
            for trial in range(10):
                rng = np.random.default_rng(5000 + trial)
                sg = gen_markov_k(trans_s, pools_s, len(gs), k_test, marg_s, rng)
                d = dipolar_vector(sg, 40)
                ts_list.append(d['theta'])
            m, s = np.mean(ts_list), np.std(ts_list)
            dt = real_s['theta'] - m
            zs = abs(dt) / max(s, 0.1)
            scale_results.append({
                'scale': f"{lo:.0e}-{hi:.0e}", 'N': len(gs),
                'real': float(real_s['theta']), f'M{k_test}': float(m),
                f'M{k_test}_std': float(s), 'residual': float(dt), 'z': float(zs)
            })
            print(f"  {lo:.0e}-{hi:.0e} ({len(gs)}): real={real_s['theta']:.1f}, "
                  f"M{k_test}={m:.1f}+/-{s:.1f}, res={dt:+.1f} (z={zs:.1f})")

    output = {
        'method': f'{nb} equal-count bins, per-source shuffle baseline, gap-pool sampling',
        'real': {k: float(v) for k, v in real.items()},
        'results_by_k': {str(k): v for k, v in results.items()},
        'n_gaps': len(gaps), 'n_trials': n_trials, 'n_bins': nb,
        'GUE_ref_theta': GUE_THETA,
        'scale_check': scale_results,
    }
    out_path = Path(__file__).parent / "data" / "markov_k_direction.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=100000)
    parser.add_argument('--n_trials', type=int, default=20)
    parser.add_argument('--n_bins', type=int, default=14)
    parser.add_argument('--n_shuffle', type=int, default=100)
    args = parser.parse_args()
    run_experiment(N=args.N, n_trials=args.n_trials, n_bins=args.n_bins,
                   n_shuffle=args.n_shuffle)
