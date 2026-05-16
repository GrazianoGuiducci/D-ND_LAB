#!/usr/bin/env python3
"""
Experiment: Does prime excess correlation grow with scale?

Claim (BOUNDARY): <r>_primes > <r>_Cramer always, and the gap GROWS with n.
Null hypothesis: the excess is constant or shrinks (density artifact).

Method:
- Generate primes up to 10^8 using sympy sieve
- Divide into 30 log-spaced windows
- In each window compute <r> = min(g_i, g_{i+1}) / max(g_i, g_{i+1})
  (gap ratio statistic, Atas et al 2013)
- Generate 20 Cramer surrogates per window (exponential gaps with same density)
- Compute delta_r = <r>_primes - mean(<r>_Cramer) per window
- Fit delta_r vs log(p_center) to see if slope > 0
"""

import numpy as np
from sympy import sieve
import json, time

t0 = time.time()

# Generate primes up to 10^8
N_MAX = 10**8
print(f"Generating primes up to {N_MAX}...")
sieve._reset()
sieve.extend(N_MAX)
primes = np.array(list(sieve._list))
print(f"  {len(primes)} primes generated in {time.time()-t0:.1f}s")

# Gap ratio statistic
def gap_ratio(gaps):
    """Compute <r> for a sequence of gaps."""
    r = []
    for i in range(len(gaps)-1):
        g1, g2 = gaps[i], gaps[i+1]
        if g1 > 0 and g2 > 0:
            r.append(min(g1, g2) / max(g1, g2))
    return np.mean(r) if r else np.nan

# Cramer surrogate: exponential gaps with same mean gap
def cramer_surrogate_r(mean_gap, n_gaps, n_surrogates=20):
    """Generate Cramer surrogates and return mean <r>."""
    rs = []
    for _ in range(n_surrogates):
        gaps = np.random.exponential(mean_gap, n_gaps)
        gaps = np.maximum(gaps, 1)  # gaps >= 1
        rs.append(gap_ratio(gaps))
    return np.mean(rs), np.std(rs)

# 30 log-spaced windows
n_windows = 30
window_size = 5000  # primes per window
indices = np.logspace(np.log10(1000), np.log10(len(primes) - window_size - 1), n_windows).astype(int)

results = []
print(f"\nComputing <r> in {n_windows} windows of {window_size} primes each...")
print(f"{'Window':>6} {'p_center':>12} {'<r>_prime':>10} {'<r>_Cramer':>10} {'delta_r':>10} {'z-score':>8}")
print("-" * 65)

for i, idx in enumerate(indices):
    p_window = primes[idx:idx+window_size]
    gaps = np.diff(p_window)

    r_prime = gap_ratio(gaps)
    mean_gap = np.mean(gaps)
    p_center = np.median(p_window)

    r_cramer_mean, r_cramer_std = cramer_surrogate_r(mean_gap, len(gaps))

    delta_r = r_prime - r_cramer_mean
    z = delta_r / r_cramer_std if r_cramer_std > 0 else 0

    results.append({
        'window': i,
        'p_center': float(p_center),
        'log_p': float(np.log(p_center)),
        'r_prime': float(r_prime),
        'r_cramer': float(r_cramer_mean),
        'r_cramer_std': float(r_cramer_std),
        'delta_r': float(delta_r),
        'z_score': float(z),
        'mean_gap': float(mean_gap),
        'n_gaps': int(len(gaps))
    })

    print(f"{i:>6} {p_center:>12.0f} {r_prime:>10.6f} {r_cramer_mean:>10.6f} {delta_r:>10.6f} {z:>8.2f}")

# Fit: delta_r vs log(p_center)
log_p = np.array([r['log_p'] for r in results])
delta_r_arr = np.array([r['delta_r'] for r in results])
z_arr = np.array([r['z_score'] for r in results])

# Linear regression
from numpy.polynomial import polynomial as P
coeffs = np.polyfit(log_p, delta_r_arr, 1)
slope, intercept = coeffs

# Also fit z-score vs log(p)
coeffs_z = np.polyfit(log_p, z_arr, 1)
slope_z, intercept_z = coeffs_z

print(f"\n{'='*65}")
print(f"RESULTS:")
print(f"  delta_r vs log(p): slope = {slope:.6f}, intercept = {intercept:.6f}")
print(f"  z-score vs log(p): slope = {slope_z:.4f}, intercept = {intercept_z:.4f}")
print(f"  Mean delta_r: {np.mean(delta_r_arr):.6f}")
print(f"  Mean z-score: {np.mean(z_arr):.2f}")
print(f"  Min/Max delta_r: {np.min(delta_r_arr):.6f} / {np.max(delta_r_arr):.6f}")

# Is the excess growing?
if slope > 0 and np.mean(z_arr) > 2:
    verdict = "CONFIRMED: excess correlation GROWS with scale (slope > 0, z > 2)"
elif np.mean(z_arr) > 2:
    verdict = "PARTIAL: excess is real (z > 2) but NOT growing (slope <= 0)"
elif slope > 0:
    verdict = "WEAK: trend positive but not significant (z < 2)"
else:
    verdict = "FALSIFIED: no growing excess correlation"

print(f"\n  VERDICT: {verdict}")

# Additional: check GUE vs Poisson classification
# GUE: <r> ~ 0.5307, Poisson: <r> ~ 0.3863
r_GUE = 0.5307
r_Poisson = 0.3863

print(f"\n  Reference: GUE <r> = {r_GUE}, Poisson <r> = {r_Poisson}")
print(f"  First window <r> = {results[0]['r_prime']:.4f} (small primes)")
print(f"  Last window <r> = {results[-1]['r_prime']:.4f} (large primes)")

# Does <r> move toward Poisson at large scale?
if results[-1]['r_prime'] < results[0]['r_prime']:
    print(f"  <r> DECREASES with scale: moving toward Poisson")
else:
    print(f"  <r> INCREASES with scale: moving toward/staying GUE")

# Correlation coefficient
from scipy.stats import pearsonr, spearmanr
r_pearson, p_pearson = pearsonr(log_p, delta_r_arr)
r_spearman, p_spearman = spearmanr(log_p, delta_r_arr)
print(f"\n  Pearson r = {r_pearson:.4f}, p = {p_pearson:.4e}")
print(f"  Spearman rho = {r_spearman:.4f}, p = {p_spearman:.4e}")

elapsed = time.time() - t0
print(f"\n  Total time: {elapsed:.1f}s")

# Save results
output = {
    'experiment': 'excess_scaling',
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'n_primes': len(primes),
    'n_windows': n_windows,
    'window_size': window_size,
    'slope_delta_r': float(slope),
    'slope_z': float(slope_z),
    'mean_delta_r': float(np.mean(delta_r_arr)),
    'mean_z': float(np.mean(z_arr)),
    'pearson_r': float(r_pearson),
    'pearson_p': float(p_pearson),
    'spearman_rho': float(r_spearman),
    'spearman_p': float(p_spearman),
    'verdict': verdict,
    'windows': results
}

with open('data/reports/exp_excess_scaling_20260405.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n  Results saved to data/reports/exp_excess_scaling_20260405.json")
