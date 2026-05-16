"""
Experiment: De Sitter Unification Test
=======================================
METRIC_TENSOR (0.9) + BRODY_CROSSOVER (0.85) + BOUNDARY (0.75) + GAP_ANTICORR (0.75)

Question: Are the geometric observable (curvature fluctuation dR) and statistical
observables (gap ratio <r>, lag-1 autocorrelation) measuring the SAME decorrelation?

If de Sitter is the right framework, all three should:
1. Be linear in t = ln(p)
2. Cross-correlate strongly across windows
3. Collapse onto a single scaling when normalized by a(t) = p/2

Null baseline: Cramer model + shuffled gaps (20 each).

Metric: cross-window Pearson correlation between observables.
Prediction: |corr(dR_std, <r>)| > 0.8 for primes, < 0.3 for null.
"""

import numpy as np
import json
from datetime import datetime

# --- Sieve of Eratosthenes for primes up to N ---
def sieve(limit):
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0].astype(np.float64)

print("Generating primes up to 10^8...")
primes = sieve(100_000_000)
N_total = len(primes)
print(f"  {N_total} primes generated.")

# --- Parameters ---
N_WINDOWS = 30
W_SIZE = 50000  # primes per window
N_SURROGATES = 20

# Log-spaced window starts
max_start = N_total - W_SIZE
starts = np.unique(np.geomspace(1000, max_start, N_WINDOWS).astype(int))
N_WINDOWS = len(starts)

def compute_observables(p_arr):
    """Compute observables for a window of primes."""
    g = np.diff(p_arr)
    n = len(g)

    # 1. Gap ratio <r> = mean(min(g_i, g_{i+1}) / max(g_i, g_{i+1}))
    r_vals = np.minimum(g[:-1], g[1:]) / np.maximum(g[:-1], g[1:])
    r_mean = np.mean(r_vals)

    # 2. Lag-1 autocorrelation of gaps
    g_centered = g - np.mean(g)
    var_g = np.var(g)
    if var_g > 0:
        acf1 = np.mean(g_centered[:-1] * g_centered[1:]) / var_g
    else:
        acf1 = 0.0

    # 3. Curvature fluctuation dR
    # t = ln(p), a = p/2, R = -2*a''/a in discrete form
    t = np.log(p_arr)
    a = p_arr / 2.0
    dt = np.diff(t)
    da = np.diff(a)
    a_dot = da / dt
    dt2 = (dt[:-1] + dt[1:]) / 2.0
    a_ddot = np.diff(a_dot) / dt2
    a_mid = a[1:-1]
    R = -2.0 * a_ddot / a_mid
    dR = R - 2.0  # fluctuation around de Sitter R=2
    dR_std = np.std(dR)
    dR_acf1 = np.corrcoef(dR[:-1], dR[1:])[0, 1] if len(dR) > 2 else 0.0

    # 4. Normalized curvature fluctuation: dR_std / a_mean^2 (dimensionless)
    a_mean = np.mean(a_mid)
    dR_norm = dR_std / a_mean**2

    p_center = np.median(p_arr)
    ln_p = np.log(p_center)

    return {
        'p_center': float(p_center),
        'ln_p': float(ln_p),
        'r_mean': float(r_mean),
        'acf1': float(acf1),
        'dR_std': float(dR_std),
        'dR_norm': float(dR_norm),
        'dR_acf1': float(dR_acf1),
    }

# --- Compute for primes ---
print(f"\nComputing observables across {N_WINDOWS} windows...")
prime_obs = []
for s in starts:
    window = primes[s:s+W_SIZE]
    obs = compute_observables(window)
    prime_obs.append(obs)

# Extract arrays
ln_p = np.array([o['ln_p'] for o in prime_obs])
r_arr = np.array([o['r_mean'] for o in prime_obs])
acf1_arr = np.array([o['acf1'] for o in prime_obs])
dR_std_arr = np.array([o['dR_std'] for o in prime_obs])
dR_norm_arr = np.array([o['dR_norm'] for o in prime_obs])

# Linear fits
from numpy.polynomial.polynomial import polyfit
r_fit = polyfit(ln_p, r_arr, 1)
acf1_fit = polyfit(ln_p, acf1_arr, 1)
dR_norm_fit = polyfit(ln_p, np.log(dR_norm_arr), 1)

# Cross-correlations
corr_r_acf1 = np.corrcoef(r_arr, acf1_arr)[0, 1]
corr_r_dR = np.corrcoef(r_arr, dR_std_arr)[0, 1]
corr_acf1_dR = np.corrcoef(acf1_arr, dR_std_arr)[0, 1]
corr_r_dRnorm = np.corrcoef(r_arr, dR_norm_arr)[0, 1]

print(f"\n=== PRIME OBSERVABLES ===")
print(f"  <r> range: {r_arr[0]:.4f} -> {r_arr[-1]:.4f}  slope={r_fit[1]:.6f}/ln(p)")
print(f"  acf1 range: {acf1_arr[0]:.4f} -> {acf1_arr[-1]:.4f}  slope={acf1_fit[1]:.6f}/ln(p)")
print(f"  dR_norm range: {dR_norm_arr[0]:.2e} -> {dR_norm_arr[-1]:.2e}")
print(f"\n=== CROSS-CORRELATIONS (primes) ===")
print(f"  corr(<r>, acf1)     = {corr_r_acf1:.4f}")
print(f"  corr(<r>, dR_std)   = {corr_r_dR:.4f}")
print(f"  corr(acf1, dR_std)  = {corr_acf1_dR:.4f}")
print(f"  corr(<r>, dR_norm)  = {corr_r_dRnorm:.4f}")

# --- Null baselines ---
print(f"\nComputing {N_SURROGATES} Cramer surrogates...")
rng = np.random.default_rng(42)
gaps_all = np.diff(primes)

null_corrs_cramer = {'r_acf1': [], 'r_dR': [], 'r_dRnorm': []}
null_corrs_shuffled = {'r_acf1': [], 'r_dR': [], 'r_dRnorm': []}

for i in range(N_SURROGATES):
    # Cramer model: gaps ~ exponential with local density 1/ln(p)
    cramer_gaps = np.zeros(N_total - 1)
    for s in starts[:1]:  # just check generation works
        pass
    # Generate Cramer primes: start from 2, gaps ~ Exp(ln(p))
    cramer_p = [2.0]
    for j in range(N_total - 1):
        local_mean = np.log(cramer_p[-1]) if cramer_p[-1] > 2 else 1.0
        gap = rng.exponential(local_mean)
        gap = max(gap, 1.0)  # minimum gap 1
        cramer_p.append(cramer_p[-1] + gap)
    cramer_p = np.array(cramer_p[:N_total])

    c_obs = []
    for s in starts:
        if s + W_SIZE <= len(cramer_p):
            c_obs.append(compute_observables(cramer_p[s:s+W_SIZE]))

    if len(c_obs) == N_WINDOWS:
        c_r = np.array([o['r_mean'] for o in c_obs])
        c_acf1 = np.array([o['acf1'] for o in c_obs])
        c_dR = np.array([o['dR_std'] for o in c_obs])
        c_dRn = np.array([o['dR_norm'] for o in c_obs])
        null_corrs_cramer['r_acf1'].append(np.corrcoef(c_r, c_acf1)[0, 1])
        null_corrs_cramer['r_dR'].append(np.corrcoef(c_r, c_dR)[0, 1])
        null_corrs_cramer['r_dRnorm'].append(np.corrcoef(c_r, c_dRn)[0, 1])

    if i % 5 == 0:
        print(f"  Cramer surrogate {i+1}/{N_SURROGATES}")

print(f"\nComputing {N_SURROGATES} shuffled surrogates...")
for i in range(N_SURROGATES):
    # Shuffled: same gaps, random order
    sh_gaps = rng.permutation(gaps_all)
    sh_p = np.cumsum(np.concatenate([[primes[0]], sh_gaps]))

    s_obs = []
    for s in starts:
        if s + W_SIZE <= len(sh_p):
            s_obs.append(compute_observables(sh_p[s:s+W_SIZE]))

    if len(s_obs) == N_WINDOWS:
        s_r = np.array([o['r_mean'] for o in s_obs])
        s_acf1 = np.array([o['acf1'] for o in s_obs])
        s_dR = np.array([o['dR_std'] for o in s_obs])
        s_dRn = np.array([o['dR_norm'] for o in s_obs])
        null_corrs_shuffled['r_acf1'].append(np.corrcoef(s_r, s_acf1)[0, 1])
        null_corrs_shuffled['r_dR'].append(np.corrcoef(s_r, s_dR)[0, 1])
        null_corrs_shuffled['r_dRnorm'].append(np.corrcoef(s_r, s_dRn)[0, 1])

    if i % 5 == 0:
        print(f"  Shuffled surrogate {i+1}/{N_SURROGATES}")

# --- Z-scores ---
def z_score(prime_val, null_vals):
    null_vals = np.array(null_vals)
    if len(null_vals) == 0 or np.std(null_vals) == 0:
        return float('nan')
    return (prime_val - np.mean(null_vals)) / np.std(null_vals)

z_cramer_r_dR = z_score(corr_r_dR, null_corrs_cramer['r_dR'])
z_shuffled_r_dR = z_score(corr_r_dR, null_corrs_shuffled['r_dR'])
z_cramer_r_acf1 = z_score(corr_r_acf1, null_corrs_cramer['r_acf1'])
z_shuffled_r_acf1 = z_score(corr_r_acf1, null_corrs_shuffled['r_acf1'])

print(f"\n=== NULL BASELINE: CRAMER ===")
print(f"  corr(<r>, dR_std): prime={corr_r_dR:.4f}  null={np.mean(null_corrs_cramer['r_dR']):.4f}+/-{np.std(null_corrs_cramer['r_dR']):.4f}  z={z_cramer_r_dR:.2f}")
print(f"  corr(<r>, acf1):   prime={corr_r_acf1:.4f}  null={np.mean(null_corrs_cramer['r_acf1']):.4f}+/-{np.std(null_corrs_cramer['r_acf1']):.4f}  z={z_cramer_r_acf1:.2f}")

print(f"\n=== NULL BASELINE: SHUFFLED ===")
print(f"  corr(<r>, dR_std): prime={corr_r_dR:.4f}  null={np.mean(null_corrs_shuffled['r_dR']):.4f}+/-{np.std(null_corrs_shuffled['r_dR']):.4f}  z={z_shuffled_r_dR:.2f}")
print(f"  corr(<r>, acf1):   prime={corr_r_acf1:.4f}  null={np.mean(null_corrs_shuffled['r_acf1']):.4f}+/-{np.std(null_corrs_shuffled['r_acf1']):.4f}  z={z_shuffled_r_acf1:.2f}")

# --- Unification test ---
# If de Sitter unifies, then <r>(t) and dR_norm(t) should be related by a monotonic function.
# Test: rank correlation (Spearman) between <r> and dR_norm
from scipy import stats
spearman_r_dR, sp_p = stats.spearmanr(r_arr, dR_norm_arr)
spearman_r_acf1, sp_p2 = stats.spearmanr(r_arr, acf1_arr)
spearman_acf1_dR, sp_p3 = stats.spearmanr(acf1_arr, dR_norm_arr)

print(f"\n=== SPEARMAN RANK CORRELATIONS (primes) ===")
print(f"  rho(<r>, dR_norm)  = {spearman_r_dR:.4f}  p={sp_p:.2e}")
print(f"  rho(<r>, acf1)     = {spearman_r_acf1:.4f}  p={sp_p2:.2e}")
print(f"  rho(acf1, dR_norm) = {spearman_acf1_dR:.4f}  p={sp_p3:.2e}")

# --- Does dR predict <r>? ---
# Fit: <r> = a + b * ln(dR_norm)
log_dRn = np.log(dR_norm_arr)
r_from_dR_fit = polyfit(log_dRn, r_arr, 1)
r_predicted = r_from_dR_fit[0] + r_from_dR_fit[1] * log_dRn
residual_std = np.std(r_arr - r_predicted)
r_total_std = np.std(r_arr)
R2 = 1 - (residual_std / r_total_std)**2

print(f"\n=== PREDICTIVE MODEL: <r> from dR_norm ===")
print(f"  <r> = {r_from_dR_fit[0]:.4f} + {r_from_dR_fit[1]:.6f} * ln(dR_norm)")
print(f"  R^2 = {R2:.4f}")
print(f"  residual_std = {residual_std:.6f} vs total_std = {r_total_std:.6f}")

# --- Save report ---
report = {
    "experiment": "exp_desitter_unification",
    "timestamp": datetime.now().isoformat(),
    "piano": 39,
    "tension": "METRIC_TENSOR + BRODY_CROSSOVER + BOUNDARY + GAP_ANTICORR",
    "claim_tested": "De Sitter metric unifies geometric (dR) and statistical (<r>, acf1) observables",
    "N_primes": int(N_total),
    "N_windows": int(N_WINDOWS),
    "W_size": W_SIZE,
    "prime_range": f"2 to {int(primes[-1])}",
    "observables_primes": {
        "r_slope_lnp": float(r_fit[1]),
        "r_intercept": float(r_fit[0]),
        "acf1_slope_lnp": float(acf1_fit[1]),
        "acf1_intercept": float(acf1_fit[0]),
        "r_range": [float(r_arr[0]), float(r_arr[-1])],
        "acf1_range": [float(acf1_arr[0]), float(acf1_arr[-1])],
        "dR_norm_range": [float(dR_norm_arr[0]), float(dR_norm_arr[-1])],
    },
    "cross_correlations_primes": {
        "pearson_r_acf1": float(corr_r_acf1),
        "pearson_r_dR_std": float(corr_r_dR),
        "pearson_acf1_dR_std": float(corr_acf1_dR),
        "pearson_r_dR_norm": float(corr_r_dRnorm),
        "spearman_r_dR_norm": float(spearman_r_dR),
        "spearman_r_acf1": float(spearman_r_acf1),
        "spearman_acf1_dR_norm": float(spearman_acf1_dR),
    },
    "null_cramer": {
        "n_surrogates": N_SURROGATES,
        "corr_r_dR_mean": float(np.mean(null_corrs_cramer['r_dR'])) if null_corrs_cramer['r_dR'] else None,
        "corr_r_dR_std": float(np.std(null_corrs_cramer['r_dR'])) if null_corrs_cramer['r_dR'] else None,
        "z_r_dR": float(z_cramer_r_dR),
        "z_r_acf1": float(z_cramer_r_acf1),
    },
    "null_shuffled": {
        "n_surrogates": N_SURROGATES,
        "corr_r_dR_mean": float(np.mean(null_corrs_shuffled['r_dR'])) if null_corrs_shuffled['r_dR'] else None,
        "corr_r_dR_std": float(np.std(null_corrs_shuffled['r_dR'])) if null_corrs_shuffled['r_dR'] else None,
        "z_r_dR": float(z_shuffled_r_dR),
        "z_r_acf1": float(z_shuffled_r_acf1),
    },
    "predictive_model": {
        "formula": "<r> = a + b * ln(dR_norm)",
        "a": float(r_from_dR_fit[0]),
        "b": float(r_from_dR_fit[1]),
        "R2": float(R2),
    },
    "windows": prime_obs,
}

out_path = "/opt/MM_D-ND/tools/data/reports/exp_desitter_unification.json"
with open(out_path, 'w') as f:
    json.dump(report, f, indent=2)
print(f"\nReport saved to {out_path}")

# --- Summary ---
print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
unified = abs(corr_r_dRnorm) > 0.8 and abs(corr_r_acf1) > 0.8
print(f"  Geometric-Statistical unification: {'YES' if unified else 'NO'}")
print(f"  corr(<r>, dR_norm) = {corr_r_dRnorm:.4f} {'> 0.8 STRONG' if abs(corr_r_dRnorm) > 0.8 else '< 0.8 WEAK'}")
print(f"  corr(<r>, acf1) = {corr_r_acf1:.4f} {'> 0.8 STRONG' if abs(corr_r_acf1) > 0.8 else '< 0.8 WEAK'}")
print(f"  <r> predictable from dR_norm: R^2={R2:.4f}")
if abs(z_cramer_r_dR) > 2:
    print(f"  SIGNIFICANT vs Cramer: z={z_cramer_r_dR:.2f}")
if abs(z_shuffled_r_dR) > 2:
    print(f"  SIGNIFICANT vs shuffled: z={z_shuffled_r_dR:.2f}")
