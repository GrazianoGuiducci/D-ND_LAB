#!/usr/bin/env python3
"""
exp_acf_z6z_mechanism.py — Is the Lag-6 ACF Crossover Arithmetic (Z/6Z) or Analytical (PNT Trend)?

Consecutio from agent_20260417_0803: "Crossover lag 6 ~ Z/6Z cycle?"

Three discriminating tests:
1. ACF of gap-mod-6 residue sequence — does Z/6Z impose period-6 structure?
2. Trend re-injection — does multiplying normalized gaps by synthetic ln(p) trend
   restore the crossover from 15 back to ~6?
3. Factorial surrogates — Z/6Z with/without trend, trend without Z/6Z,
   residue-preserving shuffle.

Usage:
    python tools/exp_acf_z6z_mechanism.py [--n_primes N] [--max_lag K] [--n_surrogates S]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def sieve_primes(n_max):
    """Sieve of Eratosthenes."""
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def get_primes(n_primes):
    """Get first n_primes primes."""
    import math
    if n_primes < 6:
        upper = 15
    else:
        upper = int(n_primes * (math.log(n_primes) + math.log(math.log(n_primes))) * 1.3) + 100
    primes = sieve_primes(upper)
    while len(primes) < n_primes:
        upper = int(upper * 1.5)
        primes = sieve_primes(upper)
    return primes[:n_primes]


def acf(x, max_lag):
    """Compute normalized autocorrelation at lags 1..max_lag."""
    n = len(x)
    xc = x - np.mean(x)
    var = np.var(x)
    if var < 1e-15:
        return np.zeros(max_lag)
    result = np.empty(max_lag)
    for k in range(1, max_lag + 1):
        result[k - 1] = np.mean(xc[:n - k] * xc[k:]) / var
    return result


def crossover_lag(acf_vals):
    """First lag (1-indexed) where ACF >= 0. Returns max_lag+1 if all negative."""
    for i, v in enumerate(acf_vals):
        if v >= 0:
            return i + 1
    return len(acf_vals) + 1


def n_negative(acf_vals):
    return int(np.sum(np.array(acf_vals) < 0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=500_000)
    parser.add_argument('--max_lag', type=int, default=50)
    parser.add_argument('--n_surrogates', type=int, default=20)
    args = parser.parse_args()

    np.random.seed(42)

    print(f"Generating {args.n_primes} primes...")
    primes = get_primes(args.n_primes)
    gaps = np.diff(primes).astype(float)
    n_gaps = len(gaps)
    ln_p = np.log(primes[:-1].astype(float))
    print(f"N gaps: {n_gaps}, p_max: {primes[-1]}, ln(p): {ln_p[0]:.1f} - {ln_p[-1]:.1f}")

    # Reference: raw and normalized ACF
    acf_raw = acf(gaps, args.max_lag)
    xover_raw = crossover_lag(acf_raw)
    nneg_raw = n_negative(acf_raw)

    norm_gaps = gaps / ln_p
    acf_norm = acf(norm_gaps, args.max_lag)
    xover_norm = crossover_lag(acf_norm)
    nneg_norm = n_negative(acf_norm)

    print(f"\nReference:")
    print(f"  Raw:        crossover={xover_raw}, n_neg={nneg_raw}/{args.max_lag}")
    print(f"  Normalized: crossover={xover_norm}, n_neg={nneg_norm}/{args.max_lag}")

    # ========================================================
    # TEST 1: ACF of gap-mod-6 residue sequence
    # ========================================================
    print(f"\n{'='*60}")
    print("TEST 1: ACF of gap-mod-6 residue sequence")
    print(f"{'='*60}")

    residues = gaps % 6  # values in {0, 2, 4}
    res_dist = {int(r): float(np.mean(residues == r)) for r in [0, 2, 4]}
    for r, frac in res_dist.items():
        print(f"  Fraction r={r}: {frac:.4f}")

    acf_res = acf(residues, args.max_lag)
    xover_res = crossover_lag(acf_res)
    nneg_res = n_negative(acf_res)
    print(f"  Crossover: {xover_res}")
    print(f"  N negative: {nneg_res}/{args.max_lag}")
    print(f"  First 12 lags: {' '.join(f'{v:+.5f}' for v in acf_res[:12])}")
    print(f"  Lags 6,12,18: {acf_res[5]:+.5f}, {acf_res[11]:+.5f}, {acf_res[17]:+.5f}")

    # Also check: ACF of normalized gap residues (g/ln(p) mod 1 residual?)
    # Not meaningful — stick with integer mod 6.

    # ========================================================
    # TEST 2: Trend re-injection scan
    # ========================================================
    print(f"\n{'='*60}")
    print("TEST 2: Trend re-injection into normalized gaps")
    print(f"{'='*60}")

    # Inject trend of varying strength: norm_gaps * ln(p)^strength
    # strength=0: normalized (crossover ~15)
    # strength=1: raw (crossover ~6)
    strengths = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5]
    strength_results = []
    for s in strengths:
        trended = norm_gaps * (ln_p ** s)
        a = acf(trended, args.max_lag)
        xo = crossover_lag(a)
        nn = n_negative(a)
        strength_results.append({'strength': s, 'crossover': xo, 'n_neg': nn})
        print(f"  ln(p)^{s:.1f}: crossover={xo:>3}, n_neg={nn}/{args.max_lag}")

    # ========================================================
    # TEST 3: Factorial surrogates
    # ========================================================
    print(f"\n{'='*60}")
    print(f"TEST 3: Factorial surrogates ({args.n_surrogates} each)")
    print(f"{'='*60}")

    ML = args.max_lag
    NS = args.n_surrogates

    # 3a: Residue-preserving shuffle
    # For each residue class, shuffle gap values within the class
    # Preserves: marginal per-class, Z/6Z residue sequence, overall distribution
    # Destroys: sequential magnitude ordering within class
    residue_int = residues.astype(int)
    xovers_rps, nnegs_rps = [], []
    for _ in range(NS):
        surr = gaps.copy()
        for r in [0, 2, 4]:
            mask = residue_int == r
            vals = surr[mask].copy()
            np.random.shuffle(vals)
            surr[mask] = vals
        a = acf(surr, ML)
        xovers_rps.append(crossover_lag(a))
        nnegs_rps.append(n_negative(a))
    print(f"  Residue-preserving shuffle:  xover={np.mean(xovers_rps):.1f}+/-{np.std(xovers_rps):.1f}, n_neg={np.mean(nnegs_rps):.1f}")

    # 3b: Full shuffle (baseline)
    xovers_fs, nnegs_fs = [], []
    for _ in range(NS):
        surr = gaps.copy()
        np.random.shuffle(surr)
        a = acf(surr, ML)
        xovers_fs.append(crossover_lag(a))
        nnegs_fs.append(n_negative(a))
    print(f"  Full shuffle:                xover={np.mean(xovers_fs):.1f}+/-{np.std(xovers_fs):.1f}, n_neg={np.mean(nnegs_fs):.1f}")

    # 3c: Cramer model (exponential gaps with mean ln(p), no Z/6Z, no structural corr)
    xovers_cramer, nnegs_cramer = [], []
    for _ in range(NS):
        surr = np.random.exponential(ln_p)
        a = acf(surr, ML)
        xovers_cramer.append(crossover_lag(a))
        nnegs_cramer.append(n_negative(a))
    print(f"  Cramer (exp, trend, no Z/6Z): xover={np.mean(xovers_cramer):.1f}+/-{np.std(xovers_cramer):.1f}, n_neg={np.mean(nnegs_cramer):.1f}")

    # 3d: Cramer + Z/6Z constraint (round to nearest ≡ r_n mod 6)
    xovers_cramer_z6, nnegs_cramer_z6 = [], []
    for _ in range(NS):
        raw_exp = np.random.exponential(ln_p)
        # Round to nearest value with same mod-6 residue as real gaps
        base = np.round(raw_exp / 6) * 6
        surr = base + residue_int
        surr = np.maximum(surr, 2)
        a = acf(surr, ML)
        xovers_cramer_z6.append(crossover_lag(a))
        nnegs_cramer_z6.append(n_negative(a))
    print(f"  Cramer + Z/6Z:               xover={np.mean(xovers_cramer_z6):.1f}+/-{np.std(xovers_cramer_z6):.1f}, n_neg={np.mean(nnegs_cramer_z6):.1f}")

    # 3e: Anti-correlated surrogates without trend (Gaussian AR(1) with acf1 matching primes)
    acf1_prime = float(acf_raw[0])
    xovers_ar, nnegs_ar = [], []
    for _ in range(NS):
        # AR(1) with phi = acf1_prime (negative)
        ar = np.empty(n_gaps)
        ar[0] = np.random.normal(0, 1)
        for i in range(1, n_gaps):
            ar[i] = acf1_prime * ar[i - 1] + np.random.normal(0, 1)
        a = acf(ar, ML)
        xovers_ar.append(crossover_lag(a))
        nnegs_ar.append(n_negative(a))
    print(f"  AR(1) phi={acf1_prime:.3f} (no trend): xover={np.mean(xovers_ar):.1f}+/-{np.std(xovers_ar):.1f}, n_neg={np.mean(nnegs_ar):.1f}")

    # 3f: AR(1) with same acf1 + PNT trend
    xovers_ar_trend, nnegs_ar_trend = [], []
    for _ in range(NS):
        ar = np.empty(n_gaps)
        ar[0] = np.random.normal(0, 1)
        for i in range(1, n_gaps):
            ar[i] = acf1_prime * ar[i - 1] + np.random.normal(0, 1)
        # Add trend to match prime gap mean
        surr = (ar - ar.min() + 1) * ln_p  # shift positive, add trend
        a = acf(surr, ML)
        xovers_ar_trend.append(crossover_lag(a))
        nnegs_ar_trend.append(n_negative(a))
    print(f"  AR(1) + trend:               xover={np.mean(xovers_ar_trend):.1f}+/-{np.std(xovers_ar_trend):.1f}, n_neg={np.mean(nnegs_ar_trend):.1f}")

    # ========================================================
    # SUMMARY TABLE
    # ========================================================
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    labels = [
        ("Real prime gaps (raw)", xover_raw, nneg_raw),
        ("Real prime gaps (normalized)", xover_norm, nneg_norm),
        ("Residue-preserving shuffle", np.mean(xovers_rps), np.mean(nnegs_rps)),
        ("Full shuffle", np.mean(xovers_fs), np.mean(nnegs_fs)),
        ("Cramer (trend, no Z/6Z)", np.mean(xovers_cramer), np.mean(nnegs_cramer)),
        ("Cramer + Z/6Z", np.mean(xovers_cramer_z6), np.mean(nnegs_cramer_z6)),
        ("AR(1) no trend", np.mean(xovers_ar), np.mean(nnegs_ar)),
        ("AR(1) + trend", np.mean(xovers_ar_trend), np.mean(nnegs_ar_trend)),
    ]
    print(f"{'Condition':<35} {'Crossover':>10} {'N_neg':>8}")
    print("-" * 55)
    for label, xo, nn in labels:
        print(f"{label:<35} {xo:>10.1f} {nn:>8.1f}/{ML}")

    # ========================================================
    # DIAGNOSTIC: What determines the crossover?
    # ========================================================
    print(f"\n{'='*60}")
    print("DIAGNOSTIC")
    print(f"{'='*60}")

    # Key comparisons:
    # 1. RPS vs raw: if RPS crossover ~ raw → Z/6Z sequence matters
    #    if RPS crossover ~ shuffle → Z/6Z sequence doesn't matter (only ordering within class does)
    rps_like_raw = abs(np.mean(xovers_rps) - xover_raw) < abs(np.mean(xovers_rps) - np.mean(xovers_fs))
    print(f"  Residue-preserving shuffle closer to raw ({xover_raw}) or shuffle ({np.mean(xovers_fs):.1f})?")
    print(f"    → {'RAW (Z/6Z sequence carries crossover info)' if rps_like_raw else 'SHUFFLE (Z/6Z sequence alone is not enough)'}")

    # 2. Cramer vs Cramer+Z/6Z: does adding Z/6Z change crossover?
    cramer_z6_diff = abs(np.mean(xovers_cramer_z6) - np.mean(xovers_cramer))
    print(f"  Cramer vs Cramer+Z/6Z crossover diff: {cramer_z6_diff:.1f}")
    print(f"    → {'Z/6Z changes crossover' if cramer_z6_diff > 1 else 'Z/6Z has no effect on crossover'}")

    # 3. AR(1) vs AR(1)+trend: does trend shift crossover?
    ar_trend_diff = np.mean(xovers_ar) - np.mean(xovers_ar_trend)
    print(f"  AR(1) crossover: {np.mean(xovers_ar):.1f} vs AR(1)+trend: {np.mean(xovers_ar_trend):.1f}")
    print(f"    → {'Trend shifts crossover earlier' if ar_trend_diff > 2 else 'Trend has minimal effect on AR crossover'}")

    # 4. Trend re-injection: what strength reproduces lag 6?
    for sr in strength_results:
        if sr['crossover'] <= xover_raw:
            crit_strength = sr['strength']
            break
    else:
        crit_strength = None
    if crit_strength is not None:
        print(f"  Trend strength to recover crossover {xover_raw}: ln(p)^{crit_strength:.1f}")
        print(f"    → Raw gaps have effective trend exponent ~{crit_strength:.1f}")

    # Overall verdict
    print(f"\n--- VERDICT ---")
    # The crossover at 6 is Z/6Z if: RPS ~ raw AND Cramer+Z/6Z ≠ Cramer
    # The crossover at 6 is trend if: strength scan shows smooth transition AND Cramer ~ low
    z6z_contributes = rps_like_raw or cramer_z6_diff > 1
    trend_determines = crit_strength is not None and 0.5 < crit_strength < 1.5

    if trend_determines and not z6z_contributes:
        verdict_text = "TREND_ONLY: The crossover lag is determined by PNT trend strength, not Z/6Z."
        verdict_code = "TREND_ONLY"
    elif z6z_contributes and not trend_determines:
        verdict_text = "Z6Z_MECHANISM: The Z/6Z arithmetic structure determines the crossover."
        verdict_code = "Z6Z_MECHANISM"
    elif z6z_contributes and trend_determines:
        verdict_text = "COMBINED: Both Z/6Z and PNT trend contribute to the crossover position."
        verdict_code = "COMBINED"
    else:
        verdict_text = "NEITHER: Crossover is determined by structural anti-correlation decay, not Z/6Z or trend alone."
        verdict_code = "STRUCTURAL"

    print(f"  {verdict_text}")

    # ========================================================
    # Save results
    # ========================================================
    results = {
        'experiment': 'acf_z6z_mechanism',
        'n_primes': args.n_primes,
        'n_gaps': n_gaps,
        'p_max': int(primes[-1]),
        'max_lag': args.max_lag,
        'n_surrogates': args.n_surrogates,
        'reference': {
            'raw': {'crossover': xover_raw, 'n_neg': nneg_raw,
                    'acf_first12': acf_raw[:12].tolist()},
            'normalized': {'crossover': xover_norm, 'n_neg': nneg_norm,
                          'acf_first12': acf_norm[:12].tolist()},
        },
        'test1_residue_acf': {
            'crossover': xover_res,
            'n_neg': nneg_res,
            'acf_first12': acf_res[:12].tolist(),
            'acf_at_6_12_18': [float(acf_res[5]), float(acf_res[11]), float(acf_res[17])],
            'residue_distribution': res_dist,
        },
        'test2_trend_injection': {
            'strength_scan': strength_results,
            'critical_strength': crit_strength,
        },
        'test3_surrogates': {
            'residue_preserving_shuffle': {
                'crossover_mean': float(np.mean(xovers_rps)),
                'crossover_std': float(np.std(xovers_rps)),
                'n_neg_mean': float(np.mean(nnegs_rps)),
                'all_xovers': xovers_rps,
            },
            'full_shuffle': {
                'crossover_mean': float(np.mean(xovers_fs)),
                'crossover_std': float(np.std(xovers_fs)),
                'n_neg_mean': float(np.mean(nnegs_fs)),
            },
            'cramer': {
                'crossover_mean': float(np.mean(xovers_cramer)),
                'crossover_std': float(np.std(xovers_cramer)),
                'n_neg_mean': float(np.mean(nnegs_cramer)),
            },
            'cramer_z6z': {
                'crossover_mean': float(np.mean(xovers_cramer_z6)),
                'crossover_std': float(np.std(xovers_cramer_z6)),
                'n_neg_mean': float(np.mean(nnegs_cramer_z6)),
            },
            'ar1_no_trend': {
                'crossover_mean': float(np.mean(xovers_ar)),
                'crossover_std': float(np.std(xovers_ar)),
                'n_neg_mean': float(np.mean(nnegs_ar)),
                'phi': float(acf1_prime),
            },
            'ar1_with_trend': {
                'crossover_mean': float(np.mean(xovers_ar_trend)),
                'crossover_std': float(np.std(xovers_ar_trend)),
                'n_neg_mean': float(np.mean(nnegs_ar_trend)),
            },
        },
        'verdict': verdict_code,
    }

    out_path = Path(__file__).parent / 'data' / 'exp_acf_z6z_mechanism.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
