#!/usr/bin/env python3
"""
exp_boundary_coherence.py — Multi-Observable Boundary Coherence

Question: Do different observables agree on WHERE primes sit between GUE and Poisson?
If yes → we're measuring one thing many ways (tautology risk).
If no → the disagreement reveals structure. Primes aren't "between" — they're something else.

Observables (all independent):
  1. Mean spacing ratio <r>        (Poisson ≈ 0.386, GUE ≈ 0.5307)
  2. Gap variance ratio Var/μ²     (Poisson = 1.0, GUE ≈ 0.178)
  3. Small-gap fraction P(s<0.3)   (Poisson ≈ 0.259, GUE ≈ 0.020)
  4. Brody parameter β             (Poisson = 0, GUE = 1)
  5. Lag-1 autocorrelation         (Poisson = 0, GUE ≈ -0.27)

Each observable is normalized to τ ∈ [0,1] where 0=Poisson, 1=GUE.
Coherence = all τ values cluster. Incoherence = they spread.

Null baseline: shuffled prime gaps (same distribution, destroyed ordering).
"""

import numpy as np
from scipy.optimize import minimize_scalar
from sympy import primerange
import json, os, sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ─── Reference values ───────────────────────────────────────────────────
# GUE values from random matrix theory (GOE for real symmetric, GUE for complex)
# Using GOE (β=1) since prime gaps are real-valued
REF = {
    "spacing_ratio":   {"poisson": 0.38629, "gue": 0.53590},  # 2ln2-1, 4-2√3
    "gap_var_ratio":   {"poisson": 1.0,     "gue": 0.178},
    "small_gap_frac":  {"poisson": 0.2592,  "gue": 0.020},    # P(s<0.3) for exp vs Wigner
    "brody_beta":      {"poisson": 0.0,     "gue": 1.0},
    "lag1_acf":        {"poisson": 0.0,     "gue": -0.271},
}


def normalize_gaps(gaps):
    """Normalize gaps to mean 1 (unfolding)."""
    mu = np.mean(gaps)
    if mu == 0:
        return gaps
    return gaps / mu


def spacing_ratio(gaps):
    """Mean consecutive spacing ratio min(s_i, s_{i+1}) / max(s_i, s_{i+1})."""
    ratios = []
    for i in range(len(gaps) - 1):
        a, b = gaps[i], gaps[i+1]
        if max(a, b) > 0:
            ratios.append(min(a, b) / max(a, b))
    return np.mean(ratios)


def gap_var_ratio(gaps):
    """Var(gaps) / mean(gaps)² — 1 for Poisson, <1 for correlated."""
    mu = np.mean(gaps)
    if mu == 0:
        return 0
    return np.var(gaps) / mu**2


def small_gap_fraction(gaps, threshold=0.3):
    """Fraction of normalized gaps below threshold."""
    s = normalize_gaps(gaps)
    return np.mean(s < threshold)


def brody_beta(gaps):
    """Fit Brody distribution P(s) = (1+β)·a·s^β·exp(-a·s^{1+β}) via MLE."""
    s = normalize_gaps(gaps)
    s = s[s > 0]

    def neg_log_lik(beta):
        bp1 = beta + 1.0
        # a = Γ((β+2)/(β+1))^(β+1)
        from scipy.special import gamma
        a = gamma((bp1 + 1) / bp1) ** bp1
        ll = np.log(bp1) + np.log(a) + beta * np.log(s) - a * s**bp1
        return -np.mean(ll)

    result = minimize_scalar(neg_log_lik, bounds=(0.001, 2.0), method='bounded')
    return result.x


def lag1_autocorrelation(gaps):
    """Lag-1 autocorrelation of the gap sequence."""
    s = normalize_gaps(gaps)
    n = len(s)
    mu = np.mean(s)
    var = np.var(s)
    if var == 0:
        return 0
    return np.mean((s[:-1] - mu) * (s[1:] - mu)) / var


def compute_all_observables(gaps):
    """Compute all 5 observables on a gap sequence."""
    return {
        "spacing_ratio": spacing_ratio(gaps),
        "gap_var_ratio": gap_var_ratio(gaps),
        "small_gap_frac": small_gap_fraction(gaps),
        "brody_beta": brody_beta(gaps),
        "lag1_acf": lag1_autocorrelation(gaps),
    }


def to_tau(obs_name, value):
    """Normalize observable to τ ∈ [0,1] where 0=Poisson, 1=GUE."""
    p = REF[obs_name]["poisson"]
    g = REF[obs_name]["gue"]
    if abs(g - p) < 1e-12:
        return 0.5
    return (value - p) / (g - p)


def generate_gue_spacings(n, n_matrices=50):
    """Generate GUE spacings from random Hermitian matrices."""
    all_spacings = []
    dim = max(10, n // n_matrices)
    for _ in range(n_matrices):
        # GUE: complex Hermitian with Gaussian entries
        H = np.random.randn(dim, dim) + 1j * np.random.randn(dim, dim)
        H = (H + H.conj().T) / 2.0
        eigs = np.sort(np.linalg.eigvalsh(H))
        spacings = np.diff(eigs)
        all_spacings.extend(spacings)
    all_spacings = np.array(all_spacings[:n])
    return all_spacings[all_spacings > 0]


def generate_poisson_spacings(n):
    """Generate Poisson spacings (exponential distribution)."""
    return np.random.exponential(1.0, n)


def get_prime_gaps(pmin, pmax):
    """Get prime gaps in range [pmin, pmax]."""
    primes = np.array(list(primerange(pmin, pmax)))
    return np.diff(primes).astype(float)


def run_experiment():
    np.random.seed(42)

    # ─── Prime gaps at multiple scales ──────────────────────────────────
    scales = [
        ("primes_1e4",   10**4,  5*10**4),
        ("primes_1e5",   10**5,  5*10**5),
        ("primes_1e6",   10**6,  3*10**6),
        ("primes_5e6",   5*10**6, 10**7),
    ]

    results = {}

    # ─── Pure references ────────────────────────────────────────────────
    print("Computing GUE reference...")
    gue_gaps = generate_gue_spacings(20000)
    gue_obs = compute_all_observables(gue_gaps)
    results["GUE_reference"] = {
        "raw": gue_obs,
        "tau": {k: to_tau(k, v) for k, v in gue_obs.items()},
    }

    print("Computing Poisson reference...")
    poi_gaps = generate_poisson_spacings(20000)
    poi_obs = compute_all_observables(poi_gaps)
    results["Poisson_reference"] = {
        "raw": poi_obs,
        "tau": {k: to_tau(k, v) for k, v in poi_obs.items()},
    }

    # ─── Primes at each scale ──────────────────────────────────────────
    for label, pmin, pmax in scales:
        print(f"Computing {label} ({pmin}-{pmax})...")
        gaps = get_prime_gaps(pmin, pmax)
        obs = compute_all_observables(gaps)
        tau = {k: to_tau(k, v) for k, v in obs.items()}

        # Shuffle control
        shuffled_gaps = gaps.copy()
        np.random.shuffle(shuffled_gaps)
        shuf_obs = compute_all_observables(shuffled_gaps)
        shuf_tau = {k: to_tau(k, v) for k, v in shuf_obs.items()}

        results[label] = {
            "n_gaps": len(gaps),
            "raw": obs,
            "tau": tau,
            "tau_mean": np.mean(list(tau.values())),
            "tau_std": np.std(list(tau.values())),
            "shuffle_raw": shuf_obs,
            "shuffle_tau": shuf_tau,
            "shuffle_tau_mean": np.mean(list(shuf_tau.values())),
            "shuffle_tau_std": np.std(list(shuf_tau.values())),
        }

    # ─── Coherence analysis ────────────────────────────────────────────
    print("\n" + "="*70)
    print("MULTI-OBSERVABLE BOUNDARY COHERENCE")
    print("="*70)

    print(f"\nReference anchors (τ should be ≈ 0 for Poisson, ≈ 1 for GUE):")
    print(f"  {'Observable':<20} {'Poisson τ':>10} {'GUE τ':>10}")
    for obs_name in REF:
        pt = results["Poisson_reference"]["tau"][obs_name]
        gt = results["GUE_reference"]["tau"][obs_name]
        print(f"  {obs_name:<20} {pt:>10.3f} {gt:>10.3f}")

    print(f"\nPrime gaps — τ values (0=Poisson, 1=GUE):")
    print(f"  {'Scale':<15} {'spacing_r':>10} {'var_ratio':>10} {'small_gap':>10} {'brody_β':>10} {'lag1_acf':>10} │ {'mean':>6} {'std':>6}")
    print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} ┼ {'-'*6} {'-'*6}")

    for label, _, _ in scales:
        r = results[label]
        t = r["tau"]
        vals = [t["spacing_ratio"], t["gap_var_ratio"], t["small_gap_frac"], t["brody_beta"], t["lag1_acf"]]
        print(f"  {label:<15} {vals[0]:>10.3f} {vals[1]:>10.3f} {vals[2]:>10.3f} {vals[3]:>10.3f} {vals[4]:>10.3f} │ {r['tau_mean']:>6.3f} {r['tau_std']:>6.3f}")

    print(f"\nShuffle control — τ values:")
    print(f"  {'Scale':<15} {'spacing_r':>10} {'var_ratio':>10} {'small_gap':>10} {'brody_β':>10} {'lag1_acf':>10} │ {'mean':>6} {'std':>6}")
    print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} ┼ {'-'*6} {'-'*6}")

    for label, _, _ in scales:
        r = results[label]
        t = r["shuffle_tau"]
        vals = [t["spacing_ratio"], t["gap_var_ratio"], t["small_gap_frac"], t["brody_beta"], t["lag1_acf"]]
        print(f"  {label:<15} {vals[0]:>10.3f} {vals[1]:>10.3f} {vals[2]:>10.3f} {vals[3]:>10.3f} {vals[4]:>10.3f} │ {r['shuffle_tau_mean']:>6.3f} {r['shuffle_tau_std']:>6.3f}")

    # ─── Key metrics ───────────────────────────────────────────────────
    # Coherence = std of τ across observables (low = coherent, high = incoherent)
    # Ordering signal = |τ_primes - τ_shuffle| averaged

    print(f"\n{'='*70}")
    print("COHERENCE ANALYSIS")
    print(f"{'='*70}")

    for label, _, _ in scales:
        r = results[label]
        tau_vals = np.array(list(r["tau"].values()))
        shuf_vals = np.array(list(r["shuffle_tau"].values()))

        coherence_prime = np.std(tau_vals)
        coherence_shuffle = np.std(shuf_vals)
        ordering_signal = np.mean(np.abs(tau_vals - shuf_vals))

        # Which observables are most order-sensitive?
        obs_names = list(r["tau"].keys())
        deltas = {k: r["tau"][k] - r["shuffle_tau"][k] for k in obs_names}

        print(f"\n  {label}:")
        print(f"    τ coherence (std): primes={coherence_prime:.4f}, shuffle={coherence_shuffle:.4f}")
        print(f"    Ordering signal (mean |Δτ|): {ordering_signal:.4f}")
        print(f"    Per-observable Δτ (prime - shuffle):")
        for k in obs_names:
            print(f"      {k:<20}: {deltas[k]:>+.4f}")

        results[label]["coherence_prime"] = coherence_prime
        results[label]["coherence_shuffle"] = coherence_shuffle
        results[label]["ordering_signal"] = ordering_signal
        results[label]["delta_tau"] = deltas

    # ─── Observable independence check ─────────────────────────────────
    # If observables are independent, they can disagree.
    # Compute pairwise correlations of τ values across scales.
    print(f"\n{'='*70}")
    print("OBSERVABLE CORRELATION ACROSS SCALES")
    print(f"{'='*70}")

    obs_names = list(REF.keys())
    tau_matrix = np.zeros((len(scales), len(obs_names)))
    for i, (label, _, _) in enumerate(scales):
        for j, obs in enumerate(obs_names):
            tau_matrix[i, j] = results[label]["tau"][obs]

    # Correlation between observables (columns)
    if tau_matrix.shape[0] > 2:
        corr = np.corrcoef(tau_matrix.T)
        print(f"\n  Correlation matrix (across {len(scales)} scales):")
        print(f"  {'':>20}", end="")
        for obs in obs_names:
            print(f"  {obs[:8]:>8}", end="")
        print()
        for i, obs in enumerate(obs_names):
            print(f"  {obs:<20}", end="")
            for j in range(len(obs_names)):
                print(f"  {corr[i,j]:>8.3f}", end="")
            print()
        results["obs_correlation"] = corr.tolist()

    # ─── Scale trend ───────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SCALE TRENDS — τ_mean drift")
    print(f"{'='*70}")
    for obs in obs_names:
        vals = [results[label]["tau"][obs] for label, _, _ in scales]
        trend = vals[-1] - vals[0]
        print(f"  {obs:<20}: {' → '.join(f'{v:.3f}' for v in vals)}  (Δ={trend:+.3f})")

    # Save results
    # Convert numpy types for JSON
    def make_serializable(obj):
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_serializable(x) for x in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    out_path = os.path.join(DATA_DIR, "boundary_coherence.json")
    with open(out_path, "w") as f:
        json.dump(make_serializable(results), f, indent=2)
    print(f"\nResults saved to {out_path}")

    return results


if __name__ == "__main__":
    run_experiment()
