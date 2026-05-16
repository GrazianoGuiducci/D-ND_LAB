#!/usr/bin/env python3
"""
exp_brody_flow.py — Brody parameter flow along the prime sequence.

Measures how the Brody beta (interpolating Poisson beta=0 to GUE beta=1)
evolves as a function of position in the prime sequence. Sliding windows
of prime gaps, each fitted to the Brody distribution via MLE.

Also measures r-statistic (ratio of consecutive spacings) per window.

Controls:
- Shuffle: same gaps per window, order destroyed → β_shuffle(N)
- Cramer: density-matched random gaps → β_cramer(N)

Usage:
    python tools/exp_brody_flow.py [--n-max 2000000] [--window 5000] [--step 2000] [--n-shuffle 20]
"""

import argparse
import json
import sys
import numpy as np
from pathlib import Path


def sieve_primes(n_max):
    """Sieve of Eratosthenes, returns array of primes up to n_max."""
    is_prime = np.ones(n_max + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(n_max**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def brody_mle(spacings, beta_grid=np.linspace(0.01, 1.5, 300)):
    """MLE estimate of Brody parameter beta from unfolded spacings.

    Brody PDF: p(s) = (beta+1) * b * s^beta * exp(-b * s^(beta+1))
    where b = Gamma((beta+2)/(beta+1))^(beta+1)

    Returns beta_hat (MLE).
    """
    from scipy.special import gammaln
    s = spacings[spacings > 0]
    n = len(s)
    if n < 10:
        return np.nan

    log_s = np.log(s)
    best_ll = -np.inf
    best_beta = 0.5

    for beta in beta_grid:
        bp1 = beta + 1.0
        # b = Gamma((beta+2)/(beta+1))^(beta+1)
        log_b = bp1 * gammaln(1.0 + 1.0/bp1)
        # log-likelihood
        ll = n * np.log(bp1) + n * log_b + beta * np.sum(log_s) - np.exp(log_b) * np.sum(s**bp1)
        if ll > best_ll:
            best_ll = ll
            best_beta = beta

    return best_beta


def r_statistic(spacings):
    """Ratio of consecutive spacings: r = min(s_i, s_{i+1}) / max(s_i, s_{i+1})."""
    s = spacings
    if len(s) < 3:
        return np.nan
    ratios = np.minimum(s[:-1], s[1:]) / np.maximum(s[:-1], s[1:])
    # Exclude divisions by zero
    valid = np.isfinite(ratios)
    return np.mean(ratios[valid])


def unfold_spacings(gaps):
    """Unfold gaps to mean spacing 1 using local average (window of 50)."""
    from scipy.ndimage import uniform_filter1d
    g = gaps.astype(float)
    local_mean = uniform_filter1d(g, size=min(50, len(g)))
    local_mean[local_mean == 0] = 1.0
    return g / local_mean


def cramer_gaps(n_gaps, mean_gap):
    """Generate Cramer-model random gaps: exponential with same mean."""
    return np.random.exponential(mean_gap, size=n_gaps)


def run(n_max=2_000_000, window=5000, step=2000, n_shuffle=20):
    print(f"Sieving primes up to {n_max}...")
    primes = sieve_primes(n_max)
    gaps = np.diff(primes)
    n_gaps = len(gaps)
    print(f"Got {len(primes)} primes, {n_gaps} gaps")

    # Windows
    starts = list(range(0, n_gaps - window, step))
    if not starts:
        starts = [0]
        window = n_gaps

    results = {
        "n_max": n_max, "n_primes": len(primes), "n_gaps": n_gaps,
        "window": window, "step": step, "n_shuffle": n_shuffle,
        "n_windows": len(starts),
        "windows": []
    }

    print(f"Computing {len(starts)} windows of size {window}, step {step}...")

    for i, s0 in enumerate(starts):
        g = gaps[s0:s0 + window]
        p_center = primes[s0 + window // 2]
        mean_gap = float(np.mean(g))

        # Unfold
        uf = unfold_spacings(g)

        # Real measurements
        beta_real = brody_mle(uf)
        r_real = r_statistic(uf)

        # Shuffle control
        betas_shuf = []
        rs_shuf = []
        for _ in range(n_shuffle):
            g_shuf = g.copy()
            np.random.shuffle(g_shuf)
            uf_shuf = unfold_spacings(g_shuf)
            betas_shuf.append(brody_mle(uf_shuf))
            rs_shuf.append(r_statistic(uf_shuf))

        # Cramer control
        betas_cr = []
        rs_cr = []
        for _ in range(n_shuffle):
            g_cr = cramer_gaps(window, mean_gap)
            uf_cr = unfold_spacings(g_cr)
            betas_cr.append(brody_mle(uf_cr))
            rs_cr.append(r_statistic(uf_cr))

        w = {
            "idx": i,
            "start": int(s0),
            "p_center": int(p_center),
            "ln_p_center": float(np.log(p_center)),
            "mean_gap": mean_gap,
            "beta": float(beta_real),
            "r": float(r_real),
            "shuffle_beta_mean": float(np.mean(betas_shuf)),
            "shuffle_beta_std": float(np.std(betas_shuf)),
            "shuffle_r_mean": float(np.mean(rs_shuf)),
            "cramer_beta_mean": float(np.mean(betas_cr)),
            "cramer_beta_std": float(np.std(betas_cr)),
            "cramer_r_mean": float(np.mean(rs_cr)),
        }
        results["windows"].append(w)

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Window {i+1}/{len(starts)}: p~{p_center}, beta={beta_real:.4f}, "
                  f"shuf={np.mean(betas_shuf):.4f}, cramer={np.mean(betas_cr):.4f}")

    # Global summary
    betas = [w["beta"] for w in results["windows"]]
    rs = [w["r"] for w in results["windows"]]
    ln_ps = [w["ln_p_center"] for w in results["windows"]]

    # Linear regression: beta vs ln(p)
    if len(betas) > 2:
        coeffs = np.polyfit(ln_ps, betas, 1)
        results["beta_vs_lnp_slope"] = float(coeffs[0])
        results["beta_vs_lnp_intercept"] = float(coeffs[1])
        residuals = np.array(betas) - np.polyval(coeffs, ln_ps)
        results["beta_vs_lnp_r2"] = float(1 - np.var(residuals) / np.var(betas))

        coeffs_r = np.polyfit(ln_ps, rs, 1)
        results["r_vs_lnp_slope"] = float(coeffs_r[0])
        results["r_vs_lnp_r2"] = float(1 - np.var(np.array(rs) - np.polyval(coeffs_r, ln_ps)) / np.var(rs))

    results["beta_mean"] = float(np.mean(betas))
    results["beta_std"] = float(np.std(betas))
    results["beta_range"] = [float(np.min(betas)), float(np.max(betas))]
    results["r_mean"] = float(np.mean(rs))
    results["r_std"] = float(np.std(rs))

    # Is the slope significant vs shuffle?
    shuf_slopes = []
    for _ in range(n_shuffle):
        shuf_betas = [w["shuffle_beta_mean"] + np.random.normal(0, w["shuffle_beta_std"])
                      for w in results["windows"]]
        c = np.polyfit(ln_ps, shuf_betas, 1)
        shuf_slopes.append(c[0])
    results["shuffle_slope_mean"] = float(np.mean(shuf_slopes))
    results["shuffle_slope_std"] = float(np.std(shuf_slopes))
    if np.std(shuf_slopes) > 0:
        results["slope_z_vs_shuffle"] = float(
            (results["beta_vs_lnp_slope"] - np.mean(shuf_slopes)) / np.std(shuf_slopes)
        )

    return results


def main():
    parser = argparse.ArgumentParser(description="Brody parameter flow along prime sequence")
    parser.add_argument("--n-max", type=int, default=2_000_000)
    parser.add_argument("--window", type=int, default=5000)
    parser.add_argument("--step", type=int, default=2000)
    parser.add_argument("--n-shuffle", type=int, default=20)
    args = parser.parse_args()

    results = run(args.n_max, args.window, args.step, args.n_shuffle)

    out_path = Path(__file__).parent / "data" / "brody_flow.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")

    # Summary
    print(f"\n=== BRODY FLOW SUMMARY ===")
    print(f"beta mean: {results['beta_mean']:.4f} +/- {results['beta_std']:.4f}")
    print(f"beta range: [{results['beta_range'][0]:.4f}, {results['beta_range'][1]:.4f}]")
    print(f"r mean: {results['r_mean']:.4f} +/- {results['r_std']:.4f}")
    if "beta_vs_lnp_slope" in results:
        print(f"beta vs ln(p) slope: {results['beta_vs_lnp_slope']:.6f} (R²={results['beta_vs_lnp_r2']:.4f})")
        print(f"r vs ln(p) slope: {results['r_vs_lnp_slope']:.6f} (R²={results['r_vs_lnp_r2']:.4f})")
    if "slope_z_vs_shuffle" in results:
        print(f"Slope z-score vs shuffle: {results['slope_z_vs_shuffle']:.2f}")


if __name__ == "__main__":
    main()
