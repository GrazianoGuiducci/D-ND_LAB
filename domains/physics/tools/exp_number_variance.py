#!/usr/bin/env python3
"""
Experiment: Number variance Sigma^2(L) for primes at multiple scales.
Tests whether the GUE->Poisson drift (seen in gap ratio) is confirmed
by an independent RMT statistic.

GUE: Sigma^2(L) ~ (2/pi^2) * ln(L) + const  (logarithmic)
Poisson: Sigma^2(L) = L  (linear)

If primes drift toward Poisson at large scale, the number variance
should become more linear (steeper) at larger primes.
"""

import numpy as np
from sympy import primerange
import json
from datetime import datetime

# Parameters
SCALES = [
    (1_000, 50_000),       # small primes
    (100_000, 150_000),    # medium
    (1_000_000, 1_050_000),  # large
    (10_000_000, 10_050_000),  # very large
    (50_000_000, 50_050_000),  # huge
]
L_VALUES = np.array([2, 5, 10, 20, 50, 100, 200])
N_SHUFFLES = 20

def unfolded_primes(primes):
    """Unfold primes using smooth part of counting function: n(p) ~ p/ln(p)."""
    p = np.array(primes, dtype=float)
    unfolded = p / np.log(p)
    # Normalize to unit mean spacing
    spacings = np.diff(unfolded)
    mean_s = np.mean(spacings)
    unfolded = unfolded / mean_s
    return unfolded

def number_variance(unfolded, L_values):
    """Compute Sigma^2(L) = Var(N(x, x+L)) over x."""
    results = []
    for L in L_values:
        counts = []
        # Sample random starting points
        x_min, x_max = unfolded[0], unfolded[-1]
        starts = np.linspace(x_min, x_max - L, min(5000, int((x_max - x_min) / L)))
        for x0 in starts:
            n = np.sum((unfolded >= x0) & (unfolded < x0 + L))
            counts.append(n)
        counts = np.array(counts)
        results.append(np.var(counts))
    return np.array(results)

def number_variance_poisson(L_values):
    """Poisson prediction: Sigma^2 = L."""
    return L_values.astype(float)

def number_variance_gue(L_values):
    """GUE prediction: Sigma^2 ~ (2/pi^2) * ln(L) + 0.44 (approximate)."""
    return (2.0 / np.pi**2) * np.log(L_values) + 0.44

print("=" * 70)
print("NUMBER VARIANCE Σ²(L) — PRIMES AT MULTIPLE SCALES")
print("=" * 70)

all_results = {}

for (p_start, p_end) in SCALES:
    label = f"p~{p_start:.0e}"
    print(f"\n--- Scale: primes in [{p_start:,}, {p_end:,}] ---")

    primes = list(primerange(p_start, p_end))
    n_primes = len(primes)
    print(f"  N primes: {n_primes}")

    # Unfold
    uf = unfolded_primes(primes)

    # Number variance for primes
    sv_primes = number_variance(uf, L_VALUES)

    # Shuffled baseline (destroy correlations -> Poisson-like)
    sv_shuffled_list = []
    for _ in range(N_SHUFFLES):
        spacings = np.diff(uf)
        np.random.shuffle(spacings)
        uf_shuf = np.concatenate([[uf[0]], uf[0] + np.cumsum(spacings)])
        sv_shuf = number_variance(uf_shuf, L_VALUES)
        sv_shuffled_list.append(sv_shuf)
    sv_shuffled = np.mean(sv_shuffled_list, axis=0)

    # Theoretical
    sv_gue = number_variance_gue(L_VALUES)
    sv_poisson = number_variance_poisson(L_VALUES)

    # Fit log slope: Sigma^2 = a * ln(L) + b
    log_L = np.log(L_VALUES)
    coeffs_prime = np.polyfit(log_L, sv_primes, 1)
    coeffs_shuf = np.polyfit(log_L, sv_shuffled, 1)
    coeffs_gue = np.polyfit(log_L, sv_gue, 1)

    # Fit linear slope: Sigma^2 = c * L + d
    lin_coeffs_prime = np.polyfit(L_VALUES, sv_primes, 1)
    lin_coeffs_shuf = np.polyfit(L_VALUES, sv_shuffled, 1)

    # R² for log fit vs linear fit
    ss_tot = np.sum((sv_primes - np.mean(sv_primes))**2)

    log_pred = np.polyval(coeffs_prime, log_L)
    ss_res_log = np.sum((sv_primes - log_pred)**2)
    r2_log = 1 - ss_res_log / ss_tot if ss_tot > 0 else 0

    lin_pred = np.polyval(lin_coeffs_prime, L_VALUES)
    ss_res_lin = np.sum((sv_primes - lin_pred)**2)
    r2_lin = 1 - ss_res_lin / ss_tot if ss_tot > 0 else 0

    print(f"  Log-fit slope (primes):   {coeffs_prime[0]:.4f}  (GUE={2/np.pi**2:.4f})")
    print(f"  Log-fit slope (shuffled): {coeffs_shuf[0]:.4f}")
    print(f"  Linear slope (primes):    {lin_coeffs_prime[0]:.6f}")
    print(f"  Linear slope (shuffled):  {lin_coeffs_shuf[0]:.6f}")
    print(f"  R² log-fit: {r2_log:.4f}  |  R² lin-fit: {r2_lin:.4f}")
    print(f"  Better fit: {'LOG (GUE-like)' if r2_log > r2_lin else 'LINEAR (Poisson-like)'}")

    print(f"\n  L    | Σ²_prime  | Σ²_shuf  | Σ²_GUE  | Σ²_Poisson")
    print(f"  {'─'*55}")
    for i, L in enumerate(L_VALUES):
        print(f"  {L:4d} | {sv_primes[i]:8.4f} | {sv_shuffled[i]:8.4f} | {sv_gue[i]:7.4f} | {sv_poisson[i]:8.1f}")

    all_results[label] = {
        "n_primes": n_primes,
        "p_start": p_start,
        "log_slope_prime": float(coeffs_prime[0]),
        "log_slope_shuffled": float(coeffs_shuf[0]),
        "lin_slope_prime": float(lin_coeffs_prime[0]),
        "lin_slope_shuffled": float(lin_coeffs_shuf[0]),
        "r2_log": float(r2_log),
        "r2_lin": float(r2_lin),
        "better_fit": "log" if r2_log > r2_lin else "linear",
    }

# Summary
print("\n" + "=" * 70)
print("SUMMARY: How does the fit evolve with scale?")
print("=" * 70)
print(f"{'Scale':<12} | {'log_slope':>10} | {'R²_log':>7} | {'R²_lin':>7} | {'Better':>10}")
print("-" * 60)
for label, r in all_results.items():
    print(f"{label:<12} | {r['log_slope_prime']:>10.4f} | {r['r2_log']:>7.4f} | {r['r2_lin']:>7.4f} | {r['better_fit']:>10}")

# Key metric: does log_slope increase with scale? (would mean moving away from GUE)
scales = [r["p_start"] for r in all_results.values()]
log_slopes = [r["log_slope_prime"] for r in all_results.values()]
if len(scales) > 2:
    ln_scales = np.log(scales)
    trend = np.polyfit(ln_scales, log_slopes, 1)
    print(f"\nTrend of log_slope vs ln(p_start): slope={trend[0]:.6f}")
    print(f"  GUE value: {2/np.pi**2:.4f}")
    print(f"  If trend > 0: number variance grows faster at large scale -> MORE Poisson")
    print(f"  If trend ~ 0: stable -> GUE character preserved")

# Save
output = {
    "experiment": "number_variance_multi_scale",
    "timestamp": datetime.now().isoformat(),
    "claim_under_test": "BOUNDARY: GUE->Poisson drift in primes",
    "method": "Number variance Sigma^2(L) at 5 scales, compared with GUE and Poisson predictions",
    "L_values": L_VALUES.tolist(),
    "results": all_results,
    "gue_log_slope": float(2/np.pi**2),
}
with open("/opt/MM_D-ND/tools/data/reports/exp_number_variance_test.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nData saved to data/reports/exp_number_variance_test.json")
