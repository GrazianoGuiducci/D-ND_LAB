#!/usr/bin/env python3
"""
Experiment: Universal Crossover — One boundary or many?
=========================================================
Piano 39. Tensions: METRIC_TENSOR + BRODY_CROSSOVER + BOUNDARY + GAP_ANTICORR

Question: Are the three drifts (Brody beta, dR_acf1, gap_acf1) the SAME crossover?
  - beta(ln p) drifts from ~0.39 to ~0.27  (toward Poisson=0)
  - dR_acf1(ln p) drifts from ~-0.50 to ~-0.40  (toward Poisson=0?)
  - gap_acf1(ln p) drifts from ~-0.07 to ~-0.04  (toward Poisson=0)

If all three collapse onto one rescaled curve -> one universal boundary operator.
If they diverge -> independent structure at different levels.

Design:
  - 40 log-spaced windows on primes up to 10^7 (664K primes)
  - For each: beta, dR_acf1, gap_acf1, <r>
  - Rescale each to crossover parameter c in [0,1]: c=0 at GUE, c=1 at Poisson
  - Fit each c(ln p) and compare slopes
  - Pairwise residual correlation after removing ln(p) trend
  - Null: 15 Cramer surrogates (should be flat at Poisson)
"""

import numpy as np
import json
from datetime import datetime
from scipy import stats
from scipy.special import gamma as gamma_func

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
N_WINDOWS = 40
W_SIZE = 10000
N_SURR = 15

max_start = N_total - W_SIZE - 2
starts = np.unique(np.geomspace(100, max_start, N_WINDOWS).astype(int))
N_WINDOWS = len(starts)
print(f"  {N_WINDOWS} windows of {W_SIZE} primes each")

# === Brody beta estimation (MLE grid search) ===
def brody_beta(gaps):
    s = gaps / np.mean(gaps)
    s = s[s > 0]
    betas = np.linspace(0.01, 1.5, 150)
    log_likes = []
    for beta in betas:
        bp1 = beta + 1
        b = gamma_func((beta + 2) / bp1) ** bp1
        with np.errstate(divide='ignore', invalid='ignore'):
            ll = np.log(bp1) + np.log(b) + beta * np.mean(np.log(s)) - b * np.mean(s**bp1)
        log_likes.append(ll if np.isfinite(ll) else -1e10)
    return float(betas[np.argmax(log_likes)])

# === Observables per window ===
def window_observables(p_arr):
    gaps = np.diff(p_arr)

    # de Sitter Ricci
    t = np.log(p_arr)
    a = p_arr / 2.0
    dt = np.diff(t)
    da = np.diff(a)
    a_dot = da / dt
    dt2 = (dt[:-1] + dt[1:]) / 2.0
    a_ddot = np.diff(a_dot) / dt2
    a_mid = a[1:-1]
    R = -2.0 * a_ddot / a_mid
    dR = R - 2.0

    # dR autocorrelation lag-1
    dR_acf1 = float(np.corrcoef(dR[:-1], dR[1:])[0, 1]) if len(dR) > 10 else float('nan')

    # Gap autocorrelation lag-1
    g_c = gaps - np.mean(gaps)
    var_g = np.var(gaps)
    gap_acf1 = float(np.mean(g_c[:-1] * g_c[1:]) / var_g) if var_g > 0 else 0.0

    # Brody beta
    beta = brody_beta(gaps)

    # Gap ratio <r>
    r_vals = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    r_mean = float(np.mean(r_vals))

    # dR statistics
    dR_std = float(np.std(dR))
    dR_norm = dR_std / float(np.mean(a_mid))**2

    return {
        'p_center': float(np.median(p_arr)),
        'ln_p': float(np.log(np.median(p_arr))),
        'beta': beta,
        'dR_acf1': dR_acf1,
        'gap_acf1': gap_acf1,
        'r_mean': r_mean,
        'dR_std': dR_std,
        'dR_norm': dR_norm,
    }

# === Compute prime windows ===
print("\nComputing prime windows...")
prime_obs = []
for i, s in enumerate(starts):
    obs = window_observables(primes[s:s+W_SIZE])
    prime_obs.append(obs)
    if i % 10 == 0:
        print(f"  Win {i+1}/{N_WINDOWS}: ln(p)={obs['ln_p']:.2f}, beta={obs['beta']:.3f}, "
              f"dR_acf1={obs['dR_acf1']:.4f}, gap_acf1={obs['gap_acf1']:.4f}, <r>={obs['r_mean']:.4f}")

ln_p = np.array([o['ln_p'] for o in prime_obs])
beta_arr = np.array([o['beta'] for o in prime_obs])
dR_acf1_arr = np.array([o['dR_acf1'] for o in prime_obs])
gap_acf1_arr = np.array([o['gap_acf1'] for o in prime_obs])
r_arr = np.array([o['r_mean'] for o in prime_obs])

# === Reference values ===
# GUE: beta=1, dR_acf1~?, gap_acf1~?, <r>=0.5307 (4/pi - 1 ?)
# Poisson: beta=0, dR_acf1=0 (uncorrelated), gap_acf1=0, <r>=0.3863 (2ln2-1)
# We use empirical GUE reference where analytic is unknown
R_GUE = 0.5307  # 4/(pi+2) Wigner surmise
R_POISSON = 2*np.log(2) - 1  # = 0.3863

print(f"\n=== REFERENCE VALUES ===")
print(f"  <r> GUE = {R_GUE:.4f}, <r> Poisson = {R_POISSON:.4f}")
print(f"  beta GUE = 1.0, beta Poisson = 0.0")

# === Linear fits: observable(ln p) ===
print(f"\n=== LINEAR FITS vs ln(p) ===")
fits = {}
for name, arr in [('beta', beta_arr), ('dR_acf1', dR_acf1_arr),
                   ('gap_acf1', gap_acf1_arr), ('r_mean', r_arr)]:
    slope, intercept, r_val, p_val, se = stats.linregress(ln_p, arr)
    fits[name] = {'slope': slope, 'intercept': intercept, 'r2': r_val**2, 'p': p_val, 'se': se}
    print(f"  {name:10s} = {intercept:.6f} + {slope:.6f} * ln(p),  R²={r_val**2:.4f}, p={p_val:.2e}")

# === Crossover parameter c(ln p) ===
# Rescale each to c in [0,1] where 0=GUE-like, 1=Poisson-like
# For beta: c = 1 - beta (beta=1 is GUE, so c=0)
# For gap_acf1: c = 1 - |gap_acf1|/|gap_acf1_max| ... but simpler:
#   use normalized drift rate = slope / range
# Actually the cleanest: just compare the slopes normalized by their range
print(f"\n=== CROSSOVER RATES (normalized) ===")
# Compute how fast each observable moves toward Poisson per decade of ln(p)
# All should move toward Poisson (beta->0, dR_acf1->0, gap_acf1->0, r->0.386)

# Range of ln(p) in our data
ln_p_range = ln_p[-1] - ln_p[0]
print(f"  ln(p) range: {ln_p[0]:.2f} to {ln_p[-1]:.2f} (span={ln_p_range:.2f})")

# Fractional change per unit ln(p) toward Poisson
# beta: Poisson=0, so rate = -slope/mean(beta)
# gap_acf1: Poisson=0, rate = -slope/mean(gap_acf1) (gap_acf1 is negative, slope positive -> toward 0)
# dR_acf1: if Poisson = 0, rate = -slope/mean(dR_acf1)
# r_mean: Poisson = 0.386, rate = slope / (mean(r) - 0.386) ... toward lower r

rates = {}
rates['beta'] = -fits['beta']['slope'] / np.mean(beta_arr)
rates['dR_acf1'] = -fits['dR_acf1']['slope'] / abs(np.mean(dR_acf1_arr))
rates['gap_acf1'] = -fits['gap_acf1']['slope'] / abs(np.mean(gap_acf1_arr))
rates['r_mean'] = fits['r_mean']['slope'] / (np.mean(r_arr) - R_POISSON)  # negative if drifting toward Poisson

for name, rate in rates.items():
    print(f"  {name:10s}: fractional rate toward Poisson = {rate:.6f} per unit ln(p)")

# === Pairwise correlations (raw and partial) ===
print(f"\n=== PAIRWISE CORRELATIONS ===")
obs_dict = {'beta': beta_arr, 'dR_acf1': dR_acf1_arr, 'gap_acf1': gap_acf1_arr, 'r_mean': r_arr}
pairs = [('beta', 'dR_acf1'), ('beta', 'gap_acf1'), ('beta', 'r_mean'),
         ('dR_acf1', 'gap_acf1'), ('dR_acf1', 'r_mean'), ('gap_acf1', 'r_mean')]

corr_raw = {}
corr_partial = {}
for n1, n2 in pairs:
    a1, a2 = obs_dict[n1], obs_dict[n2]
    r_raw = float(np.corrcoef(a1, a2)[0, 1])
    # Partial: residualize on ln(p)
    res1 = a1 - np.polyval(np.polyfit(ln_p, a1, 1), ln_p)
    res2 = a2 - np.polyval(np.polyfit(ln_p, a2, 1), ln_p)
    r_part = float(np.corrcoef(res1, res2)[0, 1])
    corr_raw[f"{n1}__{n2}"] = r_raw
    corr_partial[f"{n1}__{n2}"] = r_part
    print(f"  {n1:10s} vs {n2:10s}: raw={r_raw:.4f}, partial|ln(p)={r_part:.4f}")

# === Key test: do residuals correlate? ===
# If partial correlations are high, observables share structure beyond the trivial scale trend
print(f"\n=== UNIVERSALITY TEST ===")
sig_partial = sum(1 for v in corr_partial.values() if abs(v) > 0.3)
print(f"  {sig_partial}/{len(corr_partial)} pairs have |partial_corr| > 0.3")
if sig_partial >= 4:
    print(f"  -> STRONG: observables share structure beyond scale (one crossover)")
elif sig_partial >= 2:
    print(f"  -> MODERATE: partial coupling between some observables")
else:
    print(f"  -> WEAK: each drifts independently (multiple crossovers)")

# === Null baseline: Cramer surrogates ===
print(f"\nComputing {N_SURR} Cramer surrogates...")
rng = np.random.default_rng(42)

null_fits = {k: {'slopes': [], 'intercepts': []} for k in ['beta', 'dR_acf1', 'gap_acf1', 'r_mean']}
null_partial = {k: [] for k in corr_partial.keys()}

for si in range(N_SURR):
    # Cramer model: gaps ~ Exp(ln(p))
    c_gaps = rng.exponential(np.log(primes[:N_total-1] + 1), size=N_total-1)
    c_gaps = np.maximum(c_gaps, 2)
    c_p = np.cumsum(np.concatenate([[primes[0]], c_gaps]))[:N_total]
    c_p = np.maximum(c_p, 2)

    s_obs = []
    for s in starts:
        if s + W_SIZE <= len(c_p):
            s_obs.append(window_observables(c_p[s:s+W_SIZE]))

    if len(s_obs) < N_WINDOWS - 3:
        continue

    s_lnp = np.array([o['ln_p'] for o in s_obs])
    s_data = {k: np.array([o[k] for o in s_obs]) for k in ['beta', 'dR_acf1', 'gap_acf1', 'r_mean']}

    for k in null_fits:
        sl, ic, _, _, _ = stats.linregress(s_lnp, s_data[k])
        null_fits[k]['slopes'].append(sl)
        null_fits[k]['intercepts'].append(ic)

    # Partial correlations
    for n1, n2 in pairs:
        key = f"{n1}__{n2}"
        res1 = s_data[n1] - np.polyval(np.polyfit(s_lnp, s_data[n1], 1), s_lnp)
        res2 = s_data[n2] - np.polyval(np.polyfit(s_lnp, s_data[n2], 1), s_lnp)
        null_partial[key].append(float(np.corrcoef(res1, res2)[0, 1]))

    if si % 5 == 0:
        print(f"  Surrogate {si+1}/{N_SURR}")

# === Z-scores vs Cramer ===
print(f"\n=== Z-SCORES vs CRAMER ===")
z_scores = {}
for k in ['beta', 'dR_acf1', 'gap_acf1', 'r_mean']:
    sl_arr = np.array(null_fits[k]['slopes'])
    if len(sl_arr) > 0 and np.std(sl_arr) > 1e-30:
        z_val = (fits[k]['slope'] - np.mean(sl_arr)) / np.std(sl_arr)
    else:
        z_val = float('nan')
    z_scores[f"{k}_slope"] = z_val
    print(f"  {k:10s} slope: prime={fits[k]['slope']:.6f}, cramer={np.mean(sl_arr):.6f}, z={z_val:.1f}")

print(f"\n=== Z-SCORES for PARTIAL CORRELATIONS ===")
z_partial = {}
for key in corr_partial:
    na = np.array(null_partial[key])
    if len(na) > 0 and np.std(na) > 1e-30:
        z_val = (corr_partial[key] - np.mean(na)) / np.std(na)
    else:
        z_val = float('nan')
    z_partial[key] = z_val
    print(f"  {key:25s}: prime={corr_partial[key]:.4f}, cramer={np.mean(na):.4f}, z={z_val:.1f}")

# === Extrapolation: when does beta reach 0 (Poisson)? ===
print(f"\n=== EXTRAPOLATION ===")
if fits['beta']['slope'] < 0:
    ln_p_poisson_beta = -fits['beta']['intercept'] / fits['beta']['slope']
    p_poisson_beta = np.exp(ln_p_poisson_beta)
    print(f"  beta -> 0 (Poisson) at ln(p)={ln_p_poisson_beta:.1f}, p~{p_poisson_beta:.2e}")
if fits['dR_acf1']['slope'] > 0:  # dR_acf1 is negative, drifting toward 0
    ln_p_poisson_dRacf1 = -fits['dR_acf1']['intercept'] / fits['dR_acf1']['slope']
    p_poisson_dRacf1 = np.exp(ln_p_poisson_dRacf1)
    print(f"  dR_acf1 -> 0 at ln(p)={ln_p_poisson_dRacf1:.1f}, p~{p_poisson_dRacf1:.2e}")
if fits['gap_acf1']['slope'] > 0:  # gap_acf1 is negative, drifting toward 0
    ln_p_poisson_gacf1 = -fits['gap_acf1']['intercept'] / fits['gap_acf1']['slope']
    p_poisson_gacf1 = np.exp(ln_p_poisson_gacf1)
    print(f"  gap_acf1 -> 0 at ln(p)={ln_p_poisson_gacf1:.1f}, p~{p_poisson_gacf1:.2e}")
if fits['r_mean']['slope'] < 0:
    ln_p_poisson_r = (R_POISSON - fits['r_mean']['intercept']) / fits['r_mean']['slope']
    p_poisson_r = np.exp(ln_p_poisson_r)
    print(f"  <r> -> {R_POISSON:.4f} (Poisson) at ln(p)={ln_p_poisson_r:.1f}, p~{p_poisson_r:.2e}")

# === Save results ===
report = {
    "experiment": "exp_crossover_universality",
    "timestamp": datetime.now().isoformat(),
    "piano": 39,
    "tensions": ["METRIC_TENSOR", "BRODY_CROSSOVER", "BOUNDARY", "GAP_ANTICORR"],
    "question": "Are beta, dR_acf1, gap_acf1 drifts the SAME universal crossover?",
    "N_primes": int(N_total),
    "N_windows": N_WINDOWS,
    "W_size": W_SIZE,
    "N_surrogates": N_SURR,
    "linear_fits": fits,
    "crossover_rates": rates,
    "correlations_raw": corr_raw,
    "correlations_partial": corr_partial,
    "z_scores_slopes": z_scores,
    "z_scores_partial": z_partial,
    "sig_partial_count": sig_partial,
    "windows": prime_obs,
}

out_path = "/opt/MM_D-ND/tools/data/reports/exp_crossover_universality.json"
with open(out_path, 'w') as f:
    json.dump(report, f, indent=2, default=str)
print(f"\nSaved: {out_path}")

# === VERDICT ===
print(f"\n{'='*60}")
print(f"VERDICT: Universal Crossover Test")
print(f"{'='*60}")

# Count how many slopes are significant vs Cramer
sig_slopes = sum(1 for v in z_scores.values() if abs(v) > 3)
print(f"  Slopes significant vs Cramer: {sig_slopes}/4")
print(f"  Partial correlations |r|>0.3: {sig_partial}/6")

if sig_partial >= 4 and sig_slopes >= 3:
    print(f"  -> ONE UNIVERSAL CROSSOVER: all observables drift together, correlated beyond scale")
    verdict = "UNIVERSAL"
elif sig_partial >= 2 or sig_slopes >= 2:
    print(f"  -> PARTIAL UNIVERSALITY: some observables coupled, others independent")
    verdict = "PARTIAL"
else:
    print(f"  -> INDEPENDENT DRIFTS: each observable has its own crossover")
    verdict = "INDEPENDENT"

report["verdict"] = verdict
with open(out_path, 'w') as f:
    json.dump(report, f, indent=2, default=str)
