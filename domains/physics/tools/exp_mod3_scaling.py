#!/usr/bin/env python3
"""
exp_mod3_scaling.py — Scaling of mod-3 ordering memory along the prime sequence.

Question: Does mod-3 gap memory weaken with position like Brody beta does,
or is it a separate (non-Markovian) channel?

Measures in sliding windows:
  1. Mod-3 self-transition probability (gaps mod 3: 0,1,2 -> next gap mod 3)
  2. Markov(1) vs Markov(2) mutual information (is the memory deeper than lag-1?)
  3. Z-scores vs shuffle baseline per window

Compare scaling law with Brody flow: beta(p) = 0.64 - 0.030*ln(p).
If mod-3 z-score decays similarly -> same channel.
If mod-3 z-score is flat -> separate, non-Markovian channel.

Usage: python exp_mod3_scaling.py [--n-max N] [--window W] [--step S] [--n-shuffle K]
"""

import argparse
import json
import numpy as np
from pathlib import Path
from sympy import primerange
from collections import Counter


def get_primes_and_gaps(n_max):
    primes = np.array(list(primerange(2, n_max + 1)))
    gaps = np.diff(primes)
    return primes, gaps


def mod3_transition_matrix(gaps_mod3):
    """3x3 transition matrix from gap_n mod 3 to gap_{n+1} mod 3."""
    T = np.zeros((3, 3), dtype=float)
    for i in range(len(gaps_mod3) - 1):
        T[gaps_mod3[i], gaps_mod3[i + 1]] += 1
    # normalize rows
    row_sums = T.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    T_norm = T / row_sums
    return T, T_norm


def mod3_self_transition_rate(gaps_mod3):
    """Fraction of consecutive gaps with same non-zero mod-3 residue."""
    count = 0
    total = 0
    for i in range(len(gaps_mod3) - 1):
        r1 = gaps_mod3[i]
        r2 = gaps_mod3[i + 1]
        if r1 != 0 and r2 != 0:
            total += 1
            if r1 == r2:
                count += 1
    return count / total if total > 0 else 0.0, count, total


def markov_order_test(gaps_mod3, max_order=3):
    """Compare Markov(k) vs Markov(k-1) using log-likelihood ratio.
    Returns dict of {order: (LLR, df, p_value)}."""
    from scipy.stats import chi2
    results = {}
    seq = gaps_mod3
    n_states = 3

    for order in range(1, max_order + 1):
        # Count (order+1)-grams and order-grams
        higher = Counter()
        lower = Counter()
        for i in range(len(seq) - order):
            context = tuple(seq[i:i + order])
            next_val = seq[i + order]
            higher[(context, next_val)] += 1
            lower[context] += 1

        # log-likelihood ratio: 2 * sum n(context,next) * log(p_higher / p_lower)
        # p_higher = n(context,next) / n(context)
        # p_lower = n(shorter_context,next) / n(shorter_context)
        if order == 1:
            # Compare Markov(1) vs Markov(0) = iid
            marginal = Counter()
            for (ctx, nxt), c in higher.items():
                marginal[nxt] += c
            total = sum(marginal.values())
            p_marginal = {k: v / total for k, v in marginal.items()}

            llr = 0.0
            for (ctx, nxt), c in higher.items():
                p_h = c / lower[ctx] if lower[ctx] > 0 else 1e-10
                p_l = p_marginal.get(nxt, 1e-10)
                if p_h > 0 and p_l > 0:
                    llr += c * np.log(p_h / p_l)
            llr *= 2
            df = (n_states - 1) * n_states  # 3 contexts * 2 free params each = 6
        else:
            # Compare Markov(order) vs Markov(order-1)
            # Need shorter context counts
            shorter_higher = Counter()
            shorter_lower = Counter()
            for i in range(len(seq) - order):
                short_ctx = tuple(seq[i + 1:i + order])
                nxt = seq[i + order]
                shorter_higher[(short_ctx, nxt)] += 1
                shorter_lower[short_ctx] += 1

            llr = 0.0
            for (ctx, nxt), c in higher.items():
                p_h = c / lower[ctx] if lower[ctx] > 0 else 1e-10
                short_ctx = ctx[1:]
                p_l = shorter_higher.get((short_ctx, nxt), 1) / shorter_lower.get(short_ctx, 1)
                if p_h > 0 and p_l > 0:
                    llr += c * np.log(p_h / p_l)
            llr *= 2
            df = (n_states ** order - n_states ** (order - 1)) * (n_states - 1)

        p_val = 1 - chi2.cdf(llr, df) if df > 0 else 1.0
        results[order] = {"llr": float(llr), "df": int(df), "p_value": float(p_val)}

    return results


def run_experiment(n_max=2_000_000, window=5000, step=2000, n_shuffle=20):
    primes, gaps = get_primes_and_gaps(n_max)
    n_gaps = len(gaps)
    print(f"Primes up to {n_max}: {len(primes)} primes, {n_gaps} gaps")

    gaps_mod3 = (gaps % 3).astype(int)

    results = []
    n_windows = (n_gaps - window) // step + 1

    for w in range(n_windows):
        start = w * step
        end = start + window
        if end > n_gaps:
            break

        win_gaps = gaps[start:end]
        win_mod3 = gaps_mod3[start:end]
        p_center = int(primes[start + window // 2])

        # Real mod-3 self-transition
        self_rate, self_count, self_total = mod3_self_transition_rate(win_mod3)

        # Real transition matrix
        T_raw, T_norm = mod3_transition_matrix(win_mod3)

        # Markov order test on real data
        markov = markov_order_test(win_mod3, max_order=3)

        # Shuffle baseline
        shuffle_self_rates = []
        shuffle_markov1_llr = []
        for _ in range(n_shuffle):
            shuf = win_mod3.copy()
            np.random.shuffle(shuf)
            sr, _, _ = mod3_self_transition_rate(shuf)
            shuffle_self_rates.append(sr)
            m = markov_order_test(shuf, max_order=1)
            shuffle_markov1_llr.append(m[1]["llr"])

        shuffle_self_mean = np.mean(shuffle_self_rates)
        shuffle_self_std = np.std(shuffle_self_rates, ddof=1)
        z_self = (self_rate - shuffle_self_mean) / shuffle_self_std if shuffle_self_std > 0 else 0.0

        shuffle_m1_mean = np.mean(shuffle_markov1_llr)
        shuffle_m1_std = np.std(shuffle_markov1_llr, ddof=1)
        z_markov1 = (markov[1]["llr"] - shuffle_m1_mean) / shuffle_m1_std if shuffle_m1_std > 0 else 0.0

        row = {
            "p_center": p_center,
            "ln_p": float(np.log(p_center)),
            "self_transition_rate": round(float(self_rate), 5),
            "shuffle_self_mean": round(float(shuffle_self_mean), 5),
            "shuffle_self_std": round(float(shuffle_self_std), 5),
            "z_self_transition": round(float(z_self), 2),
            "markov1_llr": round(float(markov[1]["llr"]), 1),
            "markov1_p": float(markov[1]["p_value"]),
            "markov2_llr": round(float(markov[2]["llr"]), 1),
            "markov2_p": float(markov[2]["p_value"]),
            "markov3_llr": round(float(markov[3]["llr"]), 1),
            "markov3_p": float(markov[3]["p_value"]),
            "z_markov1_vs_shuffle": round(float(z_markov1), 2),
            "transition_matrix": T_norm.round(4).tolist(),
        }
        results.append(row)
        if w % 10 == 0:
            print(f"  Window {w}/{n_windows}: p_center={p_center}, z_self={z_self:.1f}, "
                  f"M1_llr={markov[1]['llr']:.0f}, M2_llr={markov[2]['llr']:.0f}")

    # Global scaling fit: z_self vs ln(p)
    ln_ps = np.array([r["ln_p"] for r in results])
    z_selfs = np.array([r["z_self_transition"] for r in results])
    m1_llrs = np.array([r["markov1_llr"] for r in results])
    m2_llrs = np.array([r["markov2_llr"] for r in results])

    # Linear fits
    from numpy.polynomial.polynomial import polyfit
    coef_z = polyfit(ln_ps, z_selfs, 1)  # [intercept, slope]
    ss_res = np.sum((z_selfs - (coef_z[0] + coef_z[1] * ln_ps)) ** 2)
    ss_tot = np.sum((z_selfs - np.mean(z_selfs)) ** 2)
    r2_z = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    coef_m1 = polyfit(ln_ps, m1_llrs, 1)
    ss_res_m1 = np.sum((m1_llrs - (coef_m1[0] + coef_m1[1] * ln_ps)) ** 2)
    ss_tot_m1 = np.sum((m1_llrs - np.mean(m1_llrs)) ** 2)
    r2_m1 = 1 - ss_res_m1 / ss_tot_m1 if ss_tot_m1 > 0 else 0

    coef_m2 = polyfit(ln_ps, m2_llrs, 1)
    ss_res_m2 = np.sum((m2_llrs - (coef_m2[0] + coef_m2[1] * ln_ps)) ** 2)
    ss_tot_m2 = np.sum((m2_llrs - np.mean(m2_llrs)) ** 2)
    r2_m2 = 1 - ss_res_m2 / ss_tot_m2 if ss_tot_m2 > 0 else 0

    # Markov depth ratio: M2/M1 per window
    m2_m1_ratios = [r["markov2_llr"] / r["markov1_llr"] if r["markov1_llr"] > 0 else 0
                    for r in results]

    summary = {
        "n_primes": int(len(primes)),
        "n_windows": len(results),
        "z_self_scaling": {
            "slope": round(float(coef_z[1]), 4),
            "intercept": round(float(coef_z[0]), 2),
            "r_squared": round(float(r2_z), 4),
            "mean_z": round(float(np.mean(z_selfs)), 2),
            "std_z": round(float(np.std(z_selfs)), 2),
        },
        "markov1_scaling": {
            "slope": round(float(coef_m1[1]), 2),
            "intercept": round(float(coef_m1[0]), 1),
            "r_squared": round(float(r2_m1), 4),
            "mean_llr": round(float(np.mean(m1_llrs)), 1),
        },
        "markov2_scaling": {
            "slope": round(float(coef_m2[1]), 2),
            "intercept": round(float(coef_m2[0]), 1),
            "r_squared": round(float(r2_m2), 4),
            "mean_llr": round(float(np.mean(m2_llrs)), 1),
        },
        "markov_depth_ratio_m2_m1": {
            "mean": round(float(np.mean(m2_m1_ratios)), 4),
            "std": round(float(np.std(m2_m1_ratios)), 4),
        },
        "windows": results,
    }

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"z_self_transition: slope = {coef_z[1]:.4f} per ln(p), R^2 = {r2_z:.4f}")
    print(f"  mean z = {np.mean(z_selfs):.2f}, range [{np.min(z_selfs):.1f}, {np.max(z_selfs):.1f}]")
    print(f"Markov(1) LLR: slope = {coef_m1[1]:.2f} per ln(p), R^2 = {r2_m1:.4f}")
    print(f"  mean LLR = {np.mean(m1_llrs):.1f}")
    print(f"Markov(2) LLR: slope = {coef_m2[1]:.2f} per ln(p), R^2 = {r2_m2:.4f}")
    print(f"  mean LLR = {np.mean(m2_llrs):.1f}")
    print(f"Markov depth M2/M1 ratio: {np.mean(m2_m1_ratios):.4f} +/- {np.std(m2_m1_ratios):.4f}")

    # Compare with Brody flow
    brody_slope = -0.030  # per ln(p)
    print(f"\n=== COMPARISON WITH BRODY FLOW ===")
    print(f"Brody beta slope: {brody_slope} per ln(p)")
    print(f"z_self slope:     {coef_z[1]:.4f} per ln(p)")
    if abs(coef_z[1]) < 0.5 and r2_z < 0.3:
        print("=> MOD-3 SIGNAL IS FLAT — different channel from Brody beta")
    else:
        print("=> MOD-3 SIGNAL SCALES — possibly same channel as Brody beta")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-max", type=int, default=2_000_000)
    parser.add_argument("--window", type=int, default=5000)
    parser.add_argument("--step", type=int, default=2000)
    parser.add_argument("--n-shuffle", type=int, default=20)
    args = parser.parse_args()

    summary = run_experiment(args.n_max, args.window, args.step, args.n_shuffle)

    out_path = Path(__file__).parent / "data" / "mod3_scaling.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {out_path}")
