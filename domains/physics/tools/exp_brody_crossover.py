#!/usr/bin/env python3
"""
Experiment: Brody parameter crossover for primes vs Cramer surrogates.

Question: As prime scale grows, does the gap distribution follow a specific
crossover from GUE-like to Poisson-like? What is the functional form?

Method:
- Compute normalized prime gaps s = g_n / <g> in windows at different scales
- Fit the Brody distribution P(s) = (1+beta)*a*s^beta*exp(-a*s^(1+beta))
  where beta=0 is Poisson, beta=1 is GOE (Wigner)
- Also compute <r> gap ratio for cross-validation
- Compare to Cramer surrogates (exponential gaps) at each scale
- Fit beta(ln p) to find the crossover law

The Brody distribution is: P(s) = (1+beta)*alpha*s^beta*exp(-alpha*s^{1+beta})
with alpha = [Gamma((2+beta)/(1+beta))]^{1+beta} for unit mean.
"""

import numpy as np
from scipy.special import gamma as gamma_fn
from scipy.optimize import minimize_scalar
import json, time

def sieve_primes(limit):
    """Simple sieve of Eratosthenes."""
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]

def brody_loglik(beta, spacings):
    """Negative log-likelihood for Brody distribution.
    P(s) = (1+beta)*alpha*s^beta*exp(-alpha*s^{1+beta})
    alpha = [Gamma((beta+2)/(beta+1))]^{beta+1}
    """
    if beta < 0 or beta > 2:
        return 1e15
    bp1 = beta + 1.0
    alpha = gamma_fn((beta + 2) / bp1) ** bp1
    s = spacings
    s = s[s > 1e-12]  # avoid log(0)
    ll = np.log(bp1) + np.log(alpha) + beta * np.log(s) - alpha * s**bp1
    return -np.sum(ll)

def fit_brody(spacings):
    """Fit Brody beta to spacings via MLE."""
    res = minimize_scalar(lambda b: brody_loglik(b, spacings),
                          bounds=(0.001, 1.999), method='bounded')
    return res.x

def gap_ratio(gaps):
    """Mean gap ratio <r> = <min(g_i, g_{i+1})/max(g_i, g_{i+1})>."""
    r_vals = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r_vals)

def cramer_surrogate(densities, n_gaps):
    """Generate gaps from exponential distribution matching prime density."""
    return np.random.exponential(densities, size=n_gaps)

def main():
    t0 = time.time()
    LIMIT = 10**8
    N_WINDOWS = 30
    WINDOW_SIZE = 5000
    N_SURROGATES = 20

    print(f"Sieving primes up to {LIMIT}...")
    primes = sieve_primes(LIMIT)
    print(f"Found {len(primes)} primes in {time.time()-t0:.1f}s")

    gaps = np.diff(primes).astype(float)

    # Log-spaced window centers
    log_min = np.log(primes[WINDOW_SIZE])
    log_max = np.log(primes[-WINDOW_SIZE])
    log_centers = np.linspace(log_min, log_max, N_WINDOWS)

    results = []
    print(f"\n{'Window':>6} {'p_center':>12} {'ln(p)':>8} {'beta_p':>8} {'beta_C':>8} {'<r>_p':>8} {'<r>_C':>8} {'delta_b':>8}")
    print("-" * 80)

    for i, lc in enumerate(log_centers):
        pc = np.exp(lc)
        # Find window of WINDOW_SIZE primes centered near pc
        idx = np.searchsorted(primes, pc)
        lo = max(0, idx - WINDOW_SIZE // 2)
        hi = lo + WINDOW_SIZE
        if hi > len(primes):
            hi = len(primes)
            lo = hi - WINDOW_SIZE

        win_primes = primes[lo:hi]
        win_gaps = np.diff(win_primes).astype(float)
        mean_gap = np.mean(win_gaps)
        spacings = win_gaps / mean_gap  # normalized to unit mean

        # Fit Brody to primes
        beta_prime = fit_brody(spacings)
        r_prime = gap_ratio(win_gaps)

        # Cramer surrogates
        beta_cramer_list = []
        r_cramer_list = []
        for _ in range(N_SURROGATES):
            surr_gaps = np.random.exponential(mean_gap, size=len(win_gaps))
            surr_spacings = surr_gaps / np.mean(surr_gaps)
            beta_cramer_list.append(fit_brody(surr_spacings))
            r_cramer_list.append(gap_ratio(surr_gaps))

        beta_cramer = np.mean(beta_cramer_list)
        beta_cramer_std = np.std(beta_cramer_list)
        r_cramer = np.mean(r_cramer_list)
        r_cramer_std = np.std(r_cramer_list)

        delta_beta = beta_prime - beta_cramer
        z_beta = delta_beta / beta_cramer_std if beta_cramer_std > 0 else 0

        results.append({
            "window": i,
            "p_center": float(win_primes[WINDOW_SIZE//2]),
            "ln_p": float(np.log(win_primes[WINDOW_SIZE//2])),
            "beta_prime": float(beta_prime),
            "beta_cramer_mean": float(beta_cramer),
            "beta_cramer_std": float(beta_cramer_std),
            "delta_beta": float(delta_beta),
            "z_beta": float(z_beta),
            "r_prime": float(r_prime),
            "r_cramer_mean": float(r_cramer),
            "r_cramer_std": float(r_cramer_std),
            "mean_gap": float(mean_gap),
        })

        print(f"{i:>6} {win_primes[WINDOW_SIZE//2]:>12.0f} {np.log(win_primes[WINDOW_SIZE//2]):>8.2f} "
              f"{beta_prime:>8.4f} {beta_cramer:>8.4f} {r_prime:>8.4f} {r_cramer:>8.4f} {delta_beta:>+8.4f}")

    # Fit scaling law: beta_prime = a + b * ln(p)
    ln_ps = np.array([r["ln_p"] for r in results])
    betas = np.array([r["beta_prime"] for r in results])
    betas_cramer = np.array([r["beta_cramer_mean"] for r in results])
    deltas = np.array([r["delta_beta"] for r in results])
    z_scores = np.array([r["z_beta"] for r in results])

    from numpy.polynomial import polynomial as P
    # Linear fit beta_prime vs ln(p)
    coeffs = np.polyfit(ln_ps, betas, 1)
    slope_beta, intercept_beta = coeffs

    # Also fit delta_beta vs ln(p)
    coeffs_d = np.polyfit(ln_ps, deltas, 1)
    slope_delta, intercept_delta = coeffs_d

    # Pearson correlation
    from scipy.stats import pearsonr, spearmanr
    r_pearson, p_pearson = pearsonr(ln_ps, betas)
    r_spearman, p_spearman = spearmanr(ln_ps, betas)

    print(f"\n{'='*80}")
    print(f"BRODY CROSSOVER ANALYSIS")
    print(f"{'='*80}")
    print(f"beta_prime range: {betas.min():.4f} to {betas.max():.4f}")
    print(f"beta_cramer range: {betas_cramer.min():.4f} to {betas_cramer.max():.4f}")
    print(f"Poisson: beta=0, GOE: beta=1")
    print(f"\nScaling: beta_prime = {intercept_beta:.4f} + {slope_beta:.6f} * ln(p)")
    print(f"Pearson r(beta, ln p) = {r_pearson:.4f} (p = {p_pearson:.2e})")
    print(f"Spearman rho = {r_spearman:.4f} (p = {p_spearman:.2e})")
    print(f"\ndelta_beta = {intercept_delta:.4f} + {slope_delta:.6f} * ln(p)")
    print(f"z-score range: {z_scores.min():.1f} to {z_scores.max():.1f}")
    print(f"Mean z-score: {z_scores.mean():.1f}")
    print(f"\nAll delta_beta > 0? {np.all(deltas > 0)}")
    print(f"Sign changes: {np.sum(np.diff(np.sign(deltas)) != 0)}")

    # Key test: extrapolate where beta_prime would reach 0 (Poisson)
    if slope_beta < 0:
        ln_p_poisson = -intercept_beta / slope_beta
        print(f"\nExtrapolated Poisson (beta=0) at ln(p) = {ln_p_poisson:.1f} → p ~ 10^{ln_p_poisson/np.log(10):.0f}")
    else:
        print(f"\nbeta INCREASES with scale — primes move AWAY from Poisson")

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")

    # Save
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment": "brody_crossover",
        "tension_id": "BOUNDARY+METRIC_TENSOR",
        "parameters": {
            "limit": LIMIT,
            "n_windows": N_WINDOWS,
            "window_size": WINDOW_SIZE,
            "n_surrogates": N_SURROGATES,
        },
        "summary": {
            "beta_prime_min": float(betas.min()),
            "beta_prime_max": float(betas.max()),
            "beta_cramer_min": float(betas_cramer.min()),
            "beta_cramer_max": float(betas_cramer.max()),
            "slope_beta_vs_lnp": float(slope_beta),
            "intercept_beta": float(intercept_beta),
            "pearson_r": float(r_pearson),
            "pearson_p": float(p_pearson),
            "slope_delta_vs_lnp": float(slope_delta),
            "z_score_mean": float(z_scores.mean()),
            "z_score_min": float(z_scores.min()),
            "all_delta_positive": bool(np.all(deltas > 0)),
        },
        "windows": results,
    }

    outpath = "data/reports/exp_brody_crossover_20260405.json"
    with open(outpath, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {outpath}")

if __name__ == "__main__":
    main()
