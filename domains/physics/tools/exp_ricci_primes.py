"""
Experiment: Discrete Ricci scalar from prime metric g_n = (p_n/2)^2
Claim under test: METRIC_TENSOR — de Sitter 1+1D predicts constant Ricci scalar.

In 1+1D de Sitter with a(t) = e^{Ht}, ds^2 = -dt^2 + a(t)^2 dx^2:
  Ricci scalar R = 2 * (a''/a) = 2H^2 (constant)

We define:
  t_n = ln(p_n)          (conformal time)
  a_n = p_n / 2          (scale factor, from g_n = a_n^2)

Discrete Ricci scalar:
  R_n = 2 * (a''_n / a_n)  where a''_n is the second finite difference

If de Sitter holds, R_n should be approximately constant.
Null baseline: shuffled gaps (destroys correlations, preserves distribution).
"""

import numpy as np
from sympy import primerange
import json
from datetime import datetime

# Generate primes
print("Generating primes up to 10^7...")
primes = np.array(list(primerange(2, 10_000_000)), dtype=np.float64)
N = len(primes)
print(f"N = {N} primes")

# Define metric quantities
t = np.log(primes)          # conformal time
a = primes / 2.0            # scale factor

# Discrete derivatives via finite differences
# dt between consecutive primes
dt = np.diff(t)              # t_{n+1} - t_n
dt_mid = (dt[:-1] + dt[1:]) / 2  # averaged spacing for second derivative

# First derivative: a' = da/dt
da = np.diff(a)
a_prime = da / dt            # da/dt at midpoints

# Second derivative: a'' = d(a')/dt
da_prime = np.diff(a_prime)
a_double_prime = da_prime / dt_mid

# Ricci scalar at interior points (aligned with a[1:-1])
a_interior = a[1:-1]
R_n = 2.0 * a_double_prime / a_interior

print(f"\nRicci scalar R_n statistics (full range):")
print(f"  mean   = {np.mean(R_n):.6f}")
print(f"  median = {np.median(R_n):.6f}")
print(f"  std    = {np.std(R_n):.6f}")
print(f"  CV     = {np.std(R_n)/abs(np.mean(R_n)):.4f}")

# --- Scale analysis: R_n in windows ---
n_windows = 20
window_size = len(R_n) // n_windows

print(f"\n{'Window':>8} {'p_center':>12} {'ln(p)':>8} {'<R>':>12} {'std(R)':>12} {'CV':>8}")
print("-" * 70)

window_results = []
for i in range(n_windows):
    start = i * window_size
    end = (i + 1) * window_size
    R_window = R_n[start:end]
    p_center = primes[1 + start + window_size // 2]
    lnp = np.log(p_center)
    mean_R = np.mean(R_window)
    std_R = np.std(R_window)
    cv = std_R / abs(mean_R) if abs(mean_R) > 1e-12 else float('inf')
    print(f"  {i+1:>5} {p_center:>12.0f} {lnp:>8.3f} {mean_R:>12.6f} {std_R:>12.6f} {cv:>8.4f}")
    window_results.append({
        "window": i + 1,
        "p_center": float(p_center),
        "ln_p": round(lnp, 3),
        "mean_R": round(float(mean_R), 8),
        "std_R": round(float(std_R), 8),
        "CV": round(cv, 4)
    })

# Extract means for trend analysis
means = np.array([w["mean_R"] for w in window_results])
lnps = np.array([w["ln_p"] for w in window_results])

# Linear fit: R vs ln(p)
coeffs = np.polyfit(lnps, means, 1)
slope, intercept = coeffs
residuals = means - np.polyval(coeffs, lnps)
ss_res = np.sum(residuals**2)
ss_tot = np.sum((means - np.mean(means))**2)
R2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

print(f"\nLinear fit <R> = {slope:.6f} * ln(p) + {intercept:.6f}")
print(f"  R^2 = {R2:.4f}")
print(f"  slope = {slope:.6f}")

# de Sitter prediction: if a(t) = e^{Ht}, then R = 2H^2
# From a = p/2, t = ln(p): a = e^t / 2, so a'/a = 1, a''/a = ?
# Actually: a = p/2, t = ln(p), da/dt = (da/dp)(dp/dt) = (1/2)(p) = p/2 = a
# So a'/a = 1 → H_eff = 1
# a'' = da'/dt = d(a)/dt = a → a''/a = 1
# R_deSitter = 2 * 1 = 2
print(f"\nde Sitter prediction (H=1): R = 2.0")
print(f"Observed global <R> = {np.mean(R_n):.6f}")
print(f"Ratio observed/predicted = {np.mean(R_n) / 2.0:.6f}")

# --- Null baseline: shuffled gaps ---
print("\n--- NULL BASELINE: shuffled gaps ---")
n_surrogates = 20
surrogate_means = []
surrogate_slopes = []

gaps = np.diff(primes)
for s in range(n_surrogates):
    shuffled_gaps = gaps.copy()
    np.random.shuffle(shuffled_gaps)
    surr_primes = np.zeros(N)
    surr_primes[0] = primes[0]
    surr_primes[1:] = primes[0] + np.cumsum(shuffled_gaps)

    surr_t = np.log(surr_primes)
    surr_a = surr_primes / 2.0
    surr_dt = np.diff(surr_t)
    surr_dt_mid = (surr_dt[:-1] + surr_dt[1:]) / 2
    surr_da = np.diff(surr_a)
    surr_a_prime = surr_da / surr_dt
    surr_da_prime = np.diff(surr_a_prime)
    surr_a_double_prime = surr_da_prime / surr_dt_mid
    surr_R = 2.0 * surr_a_double_prime / surr_a[1:-1]

    surrogate_means.append(np.mean(surr_R))

    # Windowed slope
    surr_window_means = []
    for i in range(n_windows):
        start = i * window_size
        end = (i + 1) * window_size
        surr_window_means.append(np.mean(surr_R[start:end]))
    surr_coeffs = np.polyfit(lnps, surr_window_means, 1)
    surrogate_slopes.append(surr_coeffs[0])

surr_mean_avg = np.mean(surrogate_means)
surr_mean_std = np.std(surrogate_means)
surr_slope_avg = np.mean(surrogate_slopes)
surr_slope_std = np.std(surrogate_slopes)

z_mean = (np.mean(R_n) - surr_mean_avg) / surr_mean_std if surr_mean_std > 0 else 0
z_slope = (slope - surr_slope_avg) / surr_slope_std if surr_slope_std > 0 else 0

print(f"Surrogate <R>: {surr_mean_avg:.6f} +/- {surr_mean_std:.6f}")
print(f"Prime <R>:     {np.mean(R_n):.6f}")
print(f"z-score (mean): {z_mean:.2f}")
print(f"\nSurrogate slope: {surr_slope_avg:.8f} +/- {surr_slope_std:.8f}")
print(f"Prime slope:     {slope:.8f}")
print(f"z-score (slope): {z_slope:.2f}")

# --- Verdict ---
is_constant = abs(slope) < 3 * surr_slope_std and R2 < 0.5
deviates_from_2 = abs(np.mean(R_n) - 2.0) / abs(np.mean(R_n)) > 0.1

print(f"\n{'='*60}")
print(f"VERDICT:")
if is_constant and not deviates_from_2:
    verdict = "CONFIRMED"
    print(f"  R_n is approximately constant and close to 2.0")
    print(f"  de Sitter 1+1D prediction CONFIRMED")
elif is_constant:
    verdict = "PARTIAL"
    print(f"  R_n is approximately constant but NOT close to 2.0")
    print(f"  Constant curvature but NOT de Sitter with H=1")
elif not deviates_from_2:
    verdict = "PARTIAL"
    print(f"  R_n averages ~2.0 but varies systematically with scale")
    print(f"  de Sitter H=1 as average but NOT constant")
else:
    verdict = "FALSIFIED"
    print(f"  R_n neither constant nor close to 2.0")
    print(f"  de Sitter 1+1D prediction FALSIFIED")

# Save results
results = {
    "experiment": "exp_ricci_primes",
    "timestamp": datetime.now().isoformat(),
    "piano": 39,
    "tension": "METRIC_TENSOR",
    "claim": "g_n=(p_n/2)^2 is de Sitter 1+1D => constant Ricci scalar R=2",
    "N_primes": N,
    "global_mean_R": round(float(np.mean(R_n)), 8),
    "global_std_R": round(float(np.std(R_n)), 8),
    "global_CV": round(float(np.std(R_n)/abs(np.mean(R_n))), 4),
    "slope_vs_lnp": round(float(slope), 8),
    "intercept": round(float(intercept), 6),
    "R2_linear": round(R2, 4),
    "deSitter_prediction": 2.0,
    "ratio_observed_predicted": round(float(np.mean(R_n)/2.0), 6),
    "null_baseline": {
        "n_surrogates": n_surrogates,
        "surrogate_mean_R": round(surr_mean_avg, 8),
        "surrogate_std": round(surr_mean_std, 8),
        "z_score_mean": round(z_mean, 2),
        "z_score_slope": round(z_slope, 2)
    },
    "windows": window_results,
    "verdict": verdict
}

with open("/opt/MM_D-ND/tools/data/reports/exp_ricci_primes.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to data/reports/exp_ricci_primes.json")
