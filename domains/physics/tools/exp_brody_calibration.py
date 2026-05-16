#!/usr/bin/env python3
"""
exp_brody_calibration.py — META falsification: do our observables track real structure?

The Brody distribution P(s) ~ s^beta exp(-c s^(beta+1)) interpolates from
Poisson (beta=0) to Wigner-GUE (beta=1). Gaps are i.i.d. by construction —
no sequential correlation. This provides the calibration curve:
  - r-statistic should increase monotonically with beta
  - Sig2/L should decrease with beta (more repulsion = more rigidity)
  - Ordering fraction should be ~0 at all beta (no ordering in i.i.d.)

If ordering fraction != 0 for i.i.d. Brody -> shuffle test has artifact.
If r doesn't track beta -> classification unreliable.

Then overlay REAL domains on the calibration curve. Their deviation from the
Brody curve IS the non-trivial structure — the part from sequential ordering.

Usage:
    python tools/exp_brody_calibration.py [--n-gaps 10000] [--n-brody 11] [--n-shuffles 50]
"""

import argparse
import json
import numpy as np
from scipy.special import gamma as gamma_fn
from pathlib import Path


def brody_sample(beta, n, rng):
    """Sample n gaps from Brody distribution with parameter beta.
    CDF(s) = 1 - exp(-c s^(beta+1)), c = Gamma((beta+2)/(beta+1))^(beta+1).
    """
    c = gamma_fn((beta + 2) / (beta + 1)) ** (beta + 1)
    u = rng.random(n)
    u = np.clip(u, 1e-15, 1 - 1e-15)
    s = (-np.log(u) / c) ** (1.0 / (beta + 1))
    return s


def r_statistic(gaps):
    """Ratio of consecutive spacings."""
    ratios = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(ratios)


def number_variance(levels, L_values):
    """Sigma^2(L) = Var[N(x, x+L)] for unfolded levels."""
    results = {}
    n = len(levels)
    for L in L_values:
        n_windows = min(2000, max(500, n // 2))
        x_min, x_max = levels[0], levels[-1] - L
        if x_max <= x_min:
            results[L] = np.nan
            continue
        xs = np.linspace(x_min, x_max, n_windows)
        counts = np.array([np.searchsorted(levels, x + L) - np.searchsorted(levels, x) for x in xs])
        results[L] = np.var(counts)
    return results


def compute_observables(gaps, n_shuffles=50, rng=None):
    """Compute r, Sig2/L, and ordering fraction for a gap sequence."""
    if rng is None:
        rng = np.random.default_rng(42)

    r = r_statistic(gaps)
    levels = np.cumsum(gaps)
    L_values = [1, 2, 5, 10, 20, 50]

    sig2_real = number_variance(levels, L_values)

    sig2_shuf_all = {L: [] for L in L_values}
    r_shuf_all = []
    for _ in range(n_shuffles):
        shuf = gaps.copy()
        rng.shuffle(shuf)
        r_shuf_all.append(r_statistic(shuf))
        levels_shuf = np.cumsum(shuf)
        sig2_s = number_variance(levels_shuf, L_values)
        for L in L_values:
            sig2_shuf_all[L].append(sig2_s[L])

    sig2_shuf_mean = {L: np.mean(sig2_shuf_all[L]) for L in L_values}
    sig2_shuf_std = {L: np.std(sig2_shuf_all[L]) for L in L_values}

    ordering = {}
    z_scores = {}
    for L in L_values:
        if sig2_shuf_mean[L] > 0:
            ordering[L] = (sig2_shuf_mean[L] - sig2_real[L]) / sig2_shuf_mean[L]
        else:
            ordering[L] = 0.0
        if sig2_shuf_std[L] > 0:
            z_scores[L] = (sig2_real[L] - sig2_shuf_mean[L]) / sig2_shuf_std[L]
        else:
            z_scores[L] = 0.0

    return {
        'r': r,
        'r_shuf': np.mean(r_shuf_all),
        'sig2_over_L': {L: sig2_real[L] / L for L in L_values},
        'sig2_shuf_over_L': {L: sig2_shuf_mean[L] / L for L in L_values},
        'ordering_fraction': ordering,
        'z_scores': z_scores,
    }


def generate_primes(n_max=200000):
    sieve = np.ones(n_max, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def prime_gaps_unfolded(n_gaps):
    primes = generate_primes(n_gaps * 20)[:n_gaps + 1]
    gaps = np.diff(primes.astype(float))
    log_p = np.log(primes[:-1].astype(float))
    log_p[log_p < 1] = 1
    return gaps / log_p


def gue_gaps(n_gaps, rng):
    dim = min(n_gaps + 50, 500)
    A = rng.standard_normal((dim, dim)) + 1j * rng.standard_normal((dim, dim))
    H = (A + A.conj().T) / (2 * np.sqrt(2 * dim))
    eigs = np.sort(np.linalg.eigvalsh(H))
    gaps_raw = np.diff(eigs)
    local_density = np.sqrt(np.maximum(1 - eigs[:-1]**2, 0.01)) * dim * 2 / np.pi
    local_density = np.maximum(local_density, 0.01)
    unfolded = gaps_raw * local_density
    margin = len(unfolded) // 10
    unfolded = unfolded[margin:-margin]
    return unfolded[:n_gaps]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-gaps', type=int, default=10000)
    parser.add_argument('--n-brody', type=int, default=11)
    parser.add_argument('--n-shuffles', type=int, default=50)
    parser.add_argument('--seed', type=int, default=2026)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    # === Phase 1: Brody calibration curve ===
    betas = np.linspace(0, 1, args.n_brody)
    brody_results = []

    print("=== Phase 1: Brody Calibration Curve ===")
    print(f"{'beta':>6} {'r':>8} {'r_shuf':>8} {'Sig2/L@10':>10} {'Ord@10':>8} {'z@10':>8}")
    print("-" * 60)

    for beta in betas:
        gaps = brody_sample(beta, args.n_gaps, rng)
        obs = compute_observables(gaps, n_shuffles=args.n_shuffles, rng=rng)
        brody_results.append({
            'beta': float(beta),
            **{k: float(v) if isinstance(v, (float, np.floating)) else v for k, v in obs.items()}
        })
        print(f"{beta:6.2f} {obs['r']:8.4f} {obs['r_shuf']:8.4f} "
              f"{obs['sig2_over_L'][10]:10.4f} {obs['ordering_fraction'][10]:8.4f} "
              f"{obs['z_scores'][10]:8.2f}")

    # === Phase 2: Real domains ===
    print("\n=== Phase 2: Real Domains ===")
    print(f"{'Domain':>20} {'r':>8} {'r_shuf':>8} {'Sig2/L@10':>10} {'Ord@10':>8} {'z@10':>8} {'beta_eff':>8}")
    print("-" * 80)

    brody_r_values = [b['r'] for b in brody_results]
    brody_beta_values = [b['beta'] for b in brody_results]

    def r_to_beta(r_val):
        if r_val <= brody_r_values[0]:
            return 0.0
        if r_val >= brody_r_values[-1]:
            return 1.0
        for i in range(len(brody_r_values) - 1):
            if brody_r_values[i] <= r_val <= brody_r_values[i+1]:
                frac = (r_val - brody_r_values[i]) / (brody_r_values[i+1] - brody_r_values[i])
                return brody_beta_values[i] + frac * (brody_beta_values[i+1] - brody_beta_values[i])
        return 0.5

    def expected_sig2_at_beta(beta, L=10):
        sig2_values = [b['sig2_over_L'][10] for b in brody_results]
        if beta <= 0:
            return sig2_values[0]
        if beta >= 1:
            return sig2_values[-1]
        idx = beta * (len(sig2_values) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(sig2_values) - 1)
        frac = idx - lo
        return sig2_values[lo] + frac * (sig2_values[hi] - sig2_values[lo])

    real_domains = {}

    # Primes
    prime_gaps = prime_gaps_unfolded(args.n_gaps)
    obs_p = compute_observables(prime_gaps, n_shuffles=args.n_shuffles, rng=rng)
    beta_eff_p = r_to_beta(obs_p['r'])
    real_domains['primes'] = {**obs_p, 'beta_eff': beta_eff_p}
    print(f"{'primes':>20} {obs_p['r']:8.4f} {obs_p['r_shuf']:8.4f} "
          f"{obs_p['sig2_over_L'][10]:10.4f} {obs_p['ordering_fraction'][10]:8.4f} "
          f"{obs_p['z_scores'][10]:8.2f} {beta_eff_p:8.3f}")

    # GUE matrices
    gue_g = gue_gaps(min(args.n_gaps, 400), rng)
    obs_g = compute_observables(gue_g, n_shuffles=args.n_shuffles, rng=rng)
    beta_eff_g = r_to_beta(obs_g['r'])
    real_domains['gue_matrix'] = {**obs_g, 'beta_eff': beta_eff_g}
    print(f"{'gue_matrix':>20} {obs_g['r']:8.4f} {obs_g['r_shuf']:8.4f} "
          f"{obs_g['sig2_over_L'][10]:10.4f} {obs_g['ordering_fraction'][10]:8.4f} "
          f"{obs_g['z_scores'][10]:8.2f} {beta_eff_g:8.3f}")

    # Logistic map
    x = 0.1
    logistic_vals = []
    for _ in range(args.n_gaps + 1000):
        x = 3.9999 * x * (1 - x)
        logistic_vals.append(x)
    logistic_gaps = np.diff(np.sort(logistic_vals[-args.n_gaps - 1:]))
    logistic_gaps = logistic_gaps / np.mean(logistic_gaps)
    obs_l = compute_observables(logistic_gaps, n_shuffles=args.n_shuffles, rng=rng)
    beta_eff_l = r_to_beta(obs_l['r'])
    real_domains['logistic'] = {**obs_l, 'beta_eff': beta_eff_l}
    print(f"{'logistic':>20} {obs_l['r']:8.4f} {obs_l['r_shuf']:8.4f} "
          f"{obs_l['sig2_over_L'][10]:10.4f} {obs_l['ordering_fraction'][10]:8.4f} "
          f"{obs_l['z_scores'][10]:8.2f} {beta_eff_l:8.3f}")

    # Poisson
    poisson_gaps = rng.exponential(1.0, args.n_gaps)
    obs_po = compute_observables(poisson_gaps, n_shuffles=args.n_shuffles, rng=rng)
    beta_eff_po = r_to_beta(obs_po['r'])
    real_domains['poisson'] = {**obs_po, 'beta_eff': beta_eff_po}
    print(f"{'poisson':>20} {obs_po['r']:8.4f} {obs_po['r_shuf']:8.4f} "
          f"{obs_po['sig2_over_L'][10]:10.4f} {obs_po['ordering_fraction'][10]:8.4f} "
          f"{obs_po['z_scores'][10]:8.2f} {beta_eff_po:8.3f}")

    # Coupled oscillators
    n_osc = args.n_gaps + 1
    omega = 2 * np.sin(np.pi * np.arange(1, n_osc + 1) / (2 * (n_osc + 1)))
    osc_gaps = np.diff(omega)
    osc_gaps = osc_gaps[osc_gaps > 0]
    osc_gaps = osc_gaps / np.mean(osc_gaps)
    obs_osc = compute_observables(osc_gaps, n_shuffles=args.n_shuffles, rng=rng)
    beta_eff_osc = r_to_beta(obs_osc['r'])
    real_domains['coupled_osc'] = {**obs_osc, 'beta_eff': beta_eff_osc}
    print(f"{'coupled_osc':>20} {obs_osc['r']:8.4f} {obs_osc['r_shuf']:8.4f} "
          f"{obs_osc['sig2_over_L'][10]:10.4f} {obs_osc['ordering_fraction'][10]:8.4f} "
          f"{obs_osc['z_scores'][10]:8.2f} {beta_eff_osc:8.3f}")

    # === Phase 3: Deviation Analysis ===
    print("\n=== Phase 3: Deviation from Brody Curve ===")
    print("ON curve -> structure from gap distribution alone (i.i.d.).")
    print("BELOW curve -> sequential ordering ADDS rigidity.")
    print("ABOVE curve -> sequential ordering ADDS bunching.\n")

    print(f"{'Domain':>20} {'beta_eff':>8} {'Sig2/L@10':>10} {'Expected':>10} {'Delta':>10} {'Ord%':>8} {'Diagnosis':>35}")
    print("-" * 115)

    for name, obs in real_domains.items():
        beta_eff = obs['beta_eff']
        sig2_real = obs['sig2_over_L'][10]
        sig2_expected = expected_sig2_at_beta(beta_eff)
        delta = sig2_real - sig2_expected
        ord_pct = obs['ordering_fraction'][10] * 100

        if abs(obs['z_scores'][10]) < 2:
            diag = "ON curve (i.i.d.-like)"
        elif obs['z_scores'][10] < -2:
            diag = "BELOW curve (ordering adds rigidity)"
        else:
            diag = "ABOVE curve (ordering adds bunching)"

        print(f"{name:>20} {beta_eff:8.3f} {sig2_real:10.4f} {sig2_expected:10.4f} "
              f"{delta:10.4f} {ord_pct:8.1f}% {diag:>35}")

    # === Phase 4: Scale dependence of deviation ===
    print("\n=== Phase 4: Scale Dependence of Prime Ordering ===")
    print("How does the prime deviation from Brody curve change with L?\n")

    L_values = [1, 2, 5, 10, 20, 50]
    print(f"{'L':>5} {'Sig2/L real':>12} {'Sig2/L shuf':>12} {'Ord%':>8} {'z':>8}")
    print("-" * 50)
    for L in L_values:
        s_r = obs_p['sig2_over_L'][L]
        s_s = obs_p['sig2_shuf_over_L'][L]
        o = obs_p['ordering_fraction'][L] * 100
        z = obs_p['z_scores'][L]
        print(f"{L:5d} {s_r:12.4f} {s_s:12.4f} {o:8.1f}% {z:8.2f}")

    # === Phase 5: Brody ordering fraction audit ===
    print("\n=== Phase 5: Ordering Fraction Audit (Brody = i.i.d.) ===")
    print("If ordering fraction != 0 for Brody -> shuffle test has artifact.\n")

    max_ord = 0
    max_ord_beta = 0
    for br in brody_results:
        ord10 = br['ordering_fraction'][10]
        if abs(ord10) > abs(max_ord):
            max_ord = ord10
            max_ord_beta = br['beta']

    print(f"Max |ordering fraction| across Brody at L=10: {abs(max_ord):.4f} (beta={max_ord_beta:.2f})")
    if abs(max_ord) < 0.05:
        print("PASS: Ordering fraction < 5% for all Brody beta -> shuffle test is clean.")
        artifact_level = "clean"
    else:
        print(f"WARNING: Ordering fraction up to {abs(max_ord)*100:.1f}% for i.i.d. data.")
        artifact_level = "biased"

    # === Summary ===
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Check monotonicity of r vs beta
    r_monotonic = all(brody_results[i]['r'] <= brody_results[i+1]['r'] for i in range(len(brody_results)-1))
    print(f"\n1. r-statistic monotonic with beta: {'YES' if r_monotonic else 'NO'}")
    print(f"   r(beta=0) = {brody_results[0]['r']:.4f}, r(beta=1) = {brody_results[-1]['r']:.4f}")
    print(f"   Theory: Poisson r=0.386, GOE r=0.536")

    # Check Sig2/L monotonicity
    sig2_monotonic = all(brody_results[i]['sig2_over_L'][10] >= brody_results[i+1]['sig2_over_L'][10] for i in range(len(brody_results)-1))
    print(f"\n2. Sig2/L@10 monotonically decreasing with beta: {'YES' if sig2_monotonic else 'NO'}")
    print(f"   Sig2/L(beta=0) = {brody_results[0]['sig2_over_L'][10]:.4f}, Sig2/L(beta=1) = {brody_results[-1]['sig2_over_L'][10]:.4f}")

    print(f"\n3. Shuffle test artifact level: {artifact_level}")
    print(f"   Max ordering fraction for i.i.d. data: {abs(max_ord)*100:.1f}%")

    print(f"\n4. Primes: beta_eff = {beta_eff_p:.3f}, ordering fraction at L=10 = {obs_p['ordering_fraction'][10]*100:.1f}%")
    print(f"   Primes deviate from Brody curve: ordering adds {obs_p['ordering_fraction'][10]*100:.1f}% rigidity")
    print(f"   This {obs_p['ordering_fraction'][10]*100:.1f}% is ABOVE the {abs(max_ord)*100:.1f}% artifact floor -> {'REAL' if obs_p['ordering_fraction'][10] > abs(max_ord) + 0.05 else 'MARGINAL'}")

    # Save
    def sanitize(obj):
        if isinstance(obj, dict):
            return {str(k): sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (np.floating, float)):
            return round(float(obj), 6)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return [sanitize(x) for x in obj]
        if isinstance(obj, list):
            return [sanitize(x) for x in obj]
        return obj

    output = {
        'timestamp': '2026-04-27',
        'n_gaps': args.n_gaps,
        'n_shuffles': args.n_shuffles,
        'brody_curve': sanitize(brody_results),
        'real_domains': sanitize(real_domains),
        'max_brody_ordering_fraction': sanitize(max_ord),
        'r_monotonic': r_monotonic,
        'sig2_monotonic': sig2_monotonic,
        'artifact_level': artifact_level,
    }

    out_path = Path(__file__).parent / 'data' / 'brody_calibration_results.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
