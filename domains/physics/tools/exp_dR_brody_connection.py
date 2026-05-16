#!/usr/bin/env python3
"""
Experiment: dR-Brody Connection + dR_acf1 Universality
=======================================================
Piano 39. Tensions: METRIC_TENSOR (0.9) + BRODY_CROSSOVER (0.85)

Question 1: Does de Sitter curvature fluctuation dR predict Brody beta?
  If yes -> geometric and statistical observables are unified under de Sitter.
  If no  -> de Sitter is a convenient coordinate, not a physical framework.

Question 2: Is dR_acf1 ~ -0.527 prime-specific or tautological?
  Previous exp found dR_acf1 locked at -0.527 +/- 0.005 across 20 windows.
  If Cramer surrogates show the same -> tautological (artifact of g=(p/2)^2 mapping).
  If Cramer surrogates differ -> prime-specific structure.

Null baseline: 20 Cramer surrogates + 20 shuffled.
Metric: Pearson/Spearman correlation between dR_std and Brody beta across windows.
Prediction: |corr(dR, beta)| > 0.7 for primes if de Sitter unifies.
"""

import numpy as np
import json
from datetime import datetime
from scipy import stats

np.random.seed(42)

# === Sieve ===
def sieve(limit):
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0].astype(np.float64)

print("Generating primes up to 10^7...")
primes = sieve(10_000_000)
N_total = len(primes)
print(f"  {N_total} primes")

# === Parameters ===
N_WINDOWS = 25
W_SIZE = 15000
N_SURR = 20

# Log-spaced window starts
max_start = N_total - W_SIZE - 2
starts = np.unique(np.geomspace(100, max_start, N_WINDOWS).astype(int))
N_WINDOWS = len(starts)
print(f"  {N_WINDOWS} windows of {W_SIZE} primes each")

# === Brody beta estimation ===
def brody_beta(gaps, n_iter=50):
    """Estimate Brody parameter beta from gap spacings.
    Brody distribution: P(s) = (beta+1)*b*s^beta * exp(-b*s^(beta+1))
    where b = Gamma((beta+2)/(beta+1))^(beta+1).
    beta=0 -> Poisson, beta=1 -> Wigner (GOE).
    We use MLE via grid search over beta in [0,1].
    """
    # Normalize spacings to mean 1
    s = gaps / np.mean(gaps)
    s = s[s > 0]

    # Grid search for beta
    betas = np.linspace(0.01, 1.5, 150)
    log_likes = []
    from scipy.special import gamma as gamma_func

    for beta in betas:
        bp1 = beta + 1
        b = gamma_func((beta + 2) / bp1) ** bp1
        # log P(s) = log(bp1) + log(b) + beta*log(s) - b*s^bp1
        with np.errstate(divide='ignore', invalid='ignore'):
            log_s = np.log(s)
            ll = np.log(bp1) + np.log(b) + beta * np.mean(log_s) - b * np.mean(s**bp1)
        if np.isfinite(ll):
            log_likes.append(ll)
        else:
            log_likes.append(-1e10)

    log_likes = np.array(log_likes)
    best_idx = np.argmax(log_likes)
    return float(betas[best_idx])

# === Compute observables per window ===
def window_observables(p_arr):
    """Compute dR statistics and Brody beta for a window."""
    gaps = np.diff(p_arr)

    # de Sitter coordinates
    t = np.log(p_arr)
    a = p_arr / 2.0
    dt = np.diff(t)
    da = np.diff(a)

    # Ricci scalar fluctuation
    a_dot = da / dt
    dt2 = (dt[:-1] + dt[1:]) / 2.0
    a_ddot = np.diff(a_dot) / dt2
    a_mid = a[1:-1]
    R = -2.0 * a_ddot / a_mid
    dR = R - 2.0

    dR_std = float(np.std(dR))
    dR_mean = float(np.mean(dR))

    # dR autocorrelation lag-1
    if len(dR) > 10:
        dR_acf1 = float(np.corrcoef(dR[:-1], dR[1:])[0, 1])
    else:
        dR_acf1 = float('nan')

    # Normalized dR
    a_mean = float(np.mean(a_mid))
    dR_norm = dR_std / a_mean**2

    # Brody beta
    beta = brody_beta(gaps)

    # Gap ratio <r>
    r_vals = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    r_mean = float(np.mean(r_vals))

    # Lag-1 gap autocorrelation
    g_c = gaps - np.mean(gaps)
    var_g = np.var(gaps)
    acf1_gap = float(np.mean(g_c[:-1] * g_c[1:]) / var_g) if var_g > 0 else 0.0

    return {
        'p_center': float(np.median(p_arr)),
        'ln_p': float(np.log(np.median(p_arr))),
        'dR_std': dR_std,
        'dR_mean': dR_mean,
        'dR_norm': dR_norm,
        'dR_acf1': dR_acf1,
        'brody_beta': beta,
        'r_mean': r_mean,
        'acf1_gap': acf1_gap,
    }

# === Prime windows ===
print("\nComputing prime windows...")
prime_obs = []
for i, s in enumerate(starts):
    obs = window_observables(primes[s:s+W_SIZE])
    prime_obs.append(obs)
    if i % 5 == 0:
        print(f"  Window {i+1}/{N_WINDOWS}: ln(p)={obs['ln_p']:.2f}, beta={obs['brody_beta']:.4f}, dR_acf1={obs['dR_acf1']:.4f}")

# Extract arrays
ln_p = np.array([o['ln_p'] for o in prime_obs])
beta_arr = np.array([o['brody_beta'] for o in prime_obs])
dR_std_arr = np.array([o['dR_std'] for o in prime_obs])
dR_norm_arr = np.array([o['dR_norm'] for o in prime_obs])
dR_acf1_arr = np.array([o['dR_acf1'] for o in prime_obs])
r_arr = np.array([o['r_mean'] for o in prime_obs])
acf1_gap_arr = np.array([o['acf1_gap'] for o in prime_obs])

# === Cross-correlations for primes ===
corr_beta_dRnorm = float(np.corrcoef(beta_arr, dR_norm_arr)[0, 1])
corr_beta_dRstd = float(np.corrcoef(beta_arr, dR_std_arr)[0, 1])
corr_beta_r = float(np.corrcoef(beta_arr, r_arr)[0, 1])
corr_beta_lnp = float(np.corrcoef(beta_arr, ln_p)[0, 1])
corr_dRnorm_lnp = float(np.corrcoef(dR_norm_arr, ln_p)[0, 1])
corr_r_dRnorm = float(np.corrcoef(r_arr, dR_norm_arr)[0, 1])

# Spearman
sp_beta_dRnorm, sp_p1 = stats.spearmanr(beta_arr, dR_norm_arr)
sp_beta_r, sp_p2 = stats.spearmanr(beta_arr, r_arr)

# dR_acf1 statistics
dR_acf1_mean = float(np.mean(dR_acf1_arr))
dR_acf1_std = float(np.std(dR_acf1_arr))

print(f"\n=== PRIME CORRELATIONS ===")
print(f"  corr(beta, dR_norm) = {corr_beta_dRnorm:.4f}  (Spearman: {sp_beta_dRnorm:.4f}, p={sp_p1:.2e})")
print(f"  corr(beta, dR_std)  = {corr_beta_dRstd:.4f}")
print(f"  corr(beta, <r>)     = {corr_beta_r:.4f}  (Spearman: {sp_beta_r:.4f})")
print(f"  corr(beta, ln_p)    = {corr_beta_lnp:.4f}")
print(f"  corr(<r>, dR_norm)  = {corr_r_dRnorm:.4f}")
print(f"\n  dR_acf1: mean={dR_acf1_mean:.6f}, std={dR_acf1_std:.6f}")
print(f"  dR_acf1 range: [{np.min(dR_acf1_arr):.4f}, {np.max(dR_acf1_arr):.4f}]")

# Linear fit: beta vs ln(p)
beta_fit = np.polyfit(ln_p, beta_arr, 1)
print(f"  beta = {beta_fit[1]:.4f} + {beta_fit[0]:.6f} * ln(p)")

# === Null baselines ===
print(f"\nComputing {N_SURR} surrogates each...")
rng = np.random.default_rng(42)
gaps_all = np.diff(primes)

null_data = {
    'cramer': {'corr_beta_dRnorm': [], 'corr_beta_r': [], 'dR_acf1_mean': [], 'beta_slope': []},
    'shuffled': {'corr_beta_dRnorm': [], 'corr_beta_r': [], 'dR_acf1_mean': [], 'beta_slope': []},
}

for surr_type in ['cramer', 'shuffled']:
    for si in range(N_SURR):
        if surr_type == 'cramer':
            # Cramer: gaps ~ Exp(ln(p))
            c_gaps = rng.exponential(np.log(primes[:N_total-1] + 1), size=N_total-1)
            c_gaps = np.maximum(c_gaps, 2)
            c_p = np.cumsum(np.concatenate([[primes[0]], c_gaps]))[:N_total]
        else:
            # Shuffled: same gaps, random order
            sh_gaps = rng.permutation(gaps_all)
            c_p = np.cumsum(np.concatenate([[primes[0]], sh_gaps]))[:N_total]

        c_p = np.maximum(c_p, 2)  # avoid log(0)

        s_obs = []
        for s in starts:
            if s + W_SIZE <= len(c_p):
                s_obs.append(window_observables(c_p[s:s+W_SIZE]))

        if len(s_obs) >= N_WINDOWS - 2:
            s_beta = np.array([o['brody_beta'] for o in s_obs])
            s_dRn = np.array([o['dR_norm'] for o in s_obs])
            s_r = np.array([o['r_mean'] for o in s_obs])
            s_acf1 = np.array([o['dR_acf1'] for o in s_obs])
            s_lnp = np.array([o['ln_p'] for o in s_obs])

            null_data[surr_type]['corr_beta_dRnorm'].append(float(np.corrcoef(s_beta, s_dRn)[0, 1]))
            null_data[surr_type]['corr_beta_r'].append(float(np.corrcoef(s_beta, s_r)[0, 1]))
            null_data[surr_type]['dR_acf1_mean'].append(float(np.mean(s_acf1)))
            s_bfit = np.polyfit(s_lnp, s_beta, 1)
            null_data[surr_type]['beta_slope'].append(float(s_bfit[0]))

        if si % 5 == 0:
            print(f"  {surr_type} {si+1}/{N_SURR}")

# === Z-scores ===
def z(val, arr):
    a = np.array(arr)
    if len(a) == 0 or np.std(a) < 1e-30:
        return float('nan')
    return float((val - np.mean(a)) / np.std(a))

print(f"\n=== Z-SCORES ===")

z_beta_dRnorm_cramer = z(corr_beta_dRnorm, null_data['cramer']['corr_beta_dRnorm'])
z_beta_dRnorm_shuffled = z(corr_beta_dRnorm, null_data['shuffled']['corr_beta_dRnorm'])
z_beta_r_cramer = z(corr_beta_r, null_data['cramer']['corr_beta_r'])
z_dR_acf1_cramer = z(dR_acf1_mean, null_data['cramer']['dR_acf1_mean'])
z_dR_acf1_shuffled = z(dR_acf1_mean, null_data['shuffled']['dR_acf1_mean'])
z_beta_slope_cramer = z(beta_fit[0], null_data['cramer']['beta_slope'])

print(f"  corr(beta, dR_norm):  z_cramer={z_beta_dRnorm_cramer:.2f}, z_shuffled={z_beta_dRnorm_shuffled:.2f}")
print(f"  corr(beta, <r>):      z_cramer={z_beta_r_cramer:.2f}")
print(f"  dR_acf1 mean:         z_cramer={z_dR_acf1_cramer:.2f}, z_shuffled={z_dR_acf1_shuffled:.2f}")
print(f"  beta slope:           z_cramer={z_beta_slope_cramer:.2f}")

# Cramer dR_acf1 details
if null_data['cramer']['dR_acf1_mean']:
    c_acf1 = np.array(null_data['cramer']['dR_acf1_mean'])
    print(f"\n  Cramer dR_acf1: {np.mean(c_acf1):.6f} +/- {np.std(c_acf1):.6f}")
    print(f"  Prime  dR_acf1: {dR_acf1_mean:.6f} +/- {dR_acf1_std:.6f}")
if null_data['shuffled']['dR_acf1_mean']:
    s_acf1 = np.array(null_data['shuffled']['dR_acf1_mean'])
    print(f"  Shuffled dR_acf1: {np.mean(s_acf1):.6f} +/- {np.std(s_acf1):.6f}")

# === Question 2 diagnostic: is -0.527 = -1/2 within error? ===
# t-test: dR_acf1 vs -0.5
t_stat, t_p = stats.ttest_1samp(dR_acf1_arr, -0.5)
print(f"\n=== dR_acf1 vs -1/2 (de Sitter H=1/2) ===")
print(f"  t-test: t={t_stat:.3f}, p={t_p:.2e}")
print(f"  mean - (-0.5) = {dR_acf1_mean - (-0.5):.6f}")

# === Partial correlation: beta ~ dR_norm | ln(p) ===
# Residualize both on ln(p)
beta_res = beta_arr - np.polyval(np.polyfit(ln_p, beta_arr, 1), ln_p)
dRn_res = dR_norm_arr - np.polyval(np.polyfit(ln_p, dR_norm_arr, 1), ln_p)
partial_corr = float(np.corrcoef(beta_res, dRn_res)[0, 1])
print(f"\n=== PARTIAL CORRELATION beta ~ dR_norm | ln(p) ===")
print(f"  partial_corr = {partial_corr:.4f}")
print(f"  (This removes the trivial trend with scale)")

# === Save ===
report = {
    "experiment": "exp_dR_brody_connection",
    "timestamp": datetime.now().isoformat(),
    "piano": 39,
    "tensions": ["METRIC_TENSOR", "BRODY_CROSSOVER"],
    "questions": [
        "Does dR predict Brody beta?",
        "Is dR_acf1 ~ -0.527 prime-specific or tautological?"
    ],
    "N_primes": int(N_total),
    "N_windows": N_WINDOWS,
    "W_size": W_SIZE,
    "N_surrogates": N_SURR,
    "prime_results": {
        "beta_fit": {"intercept": float(beta_fit[1]), "slope": float(beta_fit[0])},
        "correlations": {
            "pearson_beta_dRnorm": corr_beta_dRnorm,
            "pearson_beta_dRstd": corr_beta_dRstd,
            "pearson_beta_r": corr_beta_r,
            "pearson_beta_lnp": corr_beta_lnp,
            "pearson_r_dRnorm": corr_r_dRnorm,
            "spearman_beta_dRnorm": float(sp_beta_dRnorm),
            "spearman_beta_r": float(sp_beta_r),
            "partial_beta_dRnorm_given_lnp": partial_corr,
        },
        "dR_acf1": {
            "mean": dR_acf1_mean,
            "std": dR_acf1_std,
            "min": float(np.min(dR_acf1_arr)),
            "max": float(np.max(dR_acf1_arr)),
            "t_test_vs_minus_half": {"t": float(t_stat), "p": float(t_p)},
        },
    },
    "z_scores": {
        "corr_beta_dRnorm_vs_cramer": z_beta_dRnorm_cramer,
        "corr_beta_dRnorm_vs_shuffled": z_beta_dRnorm_shuffled,
        "corr_beta_r_vs_cramer": z_beta_r_cramer,
        "dR_acf1_vs_cramer": z_dR_acf1_cramer,
        "dR_acf1_vs_shuffled": z_dR_acf1_shuffled,
        "beta_slope_vs_cramer": z_beta_slope_cramer,
    },
    "null_baselines": {
        "cramer": {
            "dR_acf1_mean": float(np.mean(null_data['cramer']['dR_acf1_mean'])) if null_data['cramer']['dR_acf1_mean'] else None,
            "dR_acf1_std": float(np.std(null_data['cramer']['dR_acf1_mean'])) if null_data['cramer']['dR_acf1_mean'] else None,
            "corr_beta_dRnorm_mean": float(np.mean(null_data['cramer']['corr_beta_dRnorm'])) if null_data['cramer']['corr_beta_dRnorm'] else None,
        },
        "shuffled": {
            "dR_acf1_mean": float(np.mean(null_data['shuffled']['dR_acf1_mean'])) if null_data['shuffled']['dR_acf1_mean'] else None,
            "dR_acf1_std": float(np.std(null_data['shuffled']['dR_acf1_mean'])) if null_data['shuffled']['dR_acf1_mean'] else None,
            "corr_beta_dRnorm_mean": float(np.mean(null_data['shuffled']['corr_beta_dRnorm'])) if null_data['shuffled']['corr_beta_dRnorm'] else None,
        },
    },
    "windows": prime_obs,
}

out_path = "/opt/MM_D-ND/tools/data/reports/exp_dR_brody_connection.json"
with open(out_path, 'w') as f:
    json.dump(report, f, indent=2)
print(f"\nSaved: {out_path}")

# === VERDICT ===
print(f"\n{'='*60}")
print(f"VERDICT")
print(f"{'='*60}")

# Q1: dR predicts beta?
if abs(partial_corr) > 0.3:
    print(f"  Q1: dR and beta are correlated BEYOND scale trend (partial_r={partial_corr:.3f})")
    print(f"      -> De Sitter geometry carries information about level repulsion")
else:
    print(f"  Q1: dR-beta correlation is TRIVIAL (both trend with scale, partial_r={partial_corr:.3f})")
    print(f"      -> De Sitter is a coordinate choice, not a physical framework")

# Q2: dR_acf1 universality
if abs(z_dR_acf1_cramer) < 2 and abs(z_dR_acf1_shuffled) < 2:
    print(f"  Q2: dR_acf1={dR_acf1_mean:.4f} is TAUTOLOGICAL (Cramer shows same)")
    print(f"      -> Artifact of g=(p/2)^2 mapping, not prime structure")
elif abs(z_dR_acf1_cramer) > 2:
    print(f"  Q2: dR_acf1={dR_acf1_mean:.4f} is PRIME-SPECIFIC (z_cramer={z_dR_acf1_cramer:.1f})")
    if t_p < 0.01:
        print(f"      -> Significantly different from -1/2 (p={t_p:.2e})")
    else:
        print(f"      -> Compatible with -1/2 = de Sitter H")
