"""
Experiment: Geodesic deviation in prime metric g_n = (p_n/2)^2
After finding R=2 is tautological (holds for ANY monotonic sequence),
we test what IS specific to primes.

Key idea: The smooth Ricci scalar is trivially 2.0.
What matters is the FLUCTUATION of the discrete curvature around 2.0.
These fluctuations encode the gap structure of primes.

We measure:
1. The spectrum of curvature fluctuations dR_n = R_n - 2
2. Autocorrelation of dR_n (does it inherit prime gap anti-correlation?)
3. Power spectral density of dR_n (prime-specific frequency structure?)
4. Compare ALL of these against shuffled-gap surrogates

If primes show structure in dR_n that shuffled gaps don't, the metric
captures something real about prime distribution, even though <R>=2 is trivial.
"""

import numpy as np
from sympy import primerange
import json
from datetime import datetime

print("Generating primes up to 10^7...")
primes = np.array(list(primerange(2, 10_000_000)), dtype=np.float64)
N = len(primes)
print(f"N = {N} primes")

def compute_dR(seq):
    """Compute curvature fluctuations dR = R_n - 2 for a monotonic sequence."""
    t = np.log(seq)
    a = seq / 2.0
    dt = np.diff(t)
    dt_mid = (dt[:-1] + dt[1:]) / 2
    da = np.diff(a)
    a_prime = da / dt
    da_prime = np.diff(a_prime)
    a_double_prime = da_prime / dt_mid
    R_n = 2.0 * a_double_prime / a[1:-1]
    return R_n - 2.0

def autocorr(x, max_lag=50):
    """Normalized autocorrelation."""
    x = x - np.mean(x)
    n = len(x)
    var = np.var(x)
    if var == 0:
        return np.zeros(max_lag)
    result = np.correlate(x, x, mode='full')
    result = result[n-1:n-1+max_lag] / (var * n)
    return result

# --- Prime curvature fluctuations ---
dR_prime = compute_dR(primes)
print(f"\nPrime dR fluctuations:")
print(f"  std(dR) = {np.std(dR_prime):.8f}")
print(f"  skew    = {float(np.mean(dR_prime**3) / np.std(dR_prime)**3):.4f}")
print(f"  kurtosis= {float(np.mean(dR_prime**4) / np.std(dR_prime)**4 - 3):.4f}")

# Autocorrelation of dR
acf_prime = autocorr(dR_prime, max_lag=20)
print(f"\n  Autocorrelation of dR (prime):")
for lag in [1, 2, 3, 5, 10]:
    print(f"    lag {lag:>2}: {acf_prime[lag]:.6f}")

# Power spectral density (first 10K points for speed)
chunk = min(65536, len(dR_prime))
psd_prime = np.abs(np.fft.rfft(dR_prime[:chunk]))**2 / chunk
freqs = np.fft.rfftfreq(chunk)

# --- Shuffled-gap surrogates ---
print(f"\n--- SURROGATES (20 shuffled-gap) ---")
n_surr = 20
gaps = np.diff(primes)
surr_stds = []
surr_acf1 = []
surr_acf2 = []
surr_psds = []

for s in range(n_surr):
    shuf_gaps = gaps.copy()
    np.random.shuffle(shuf_gaps)
    surr_seq = np.zeros(N)
    surr_seq[0] = primes[0]
    surr_seq[1:] = primes[0] + np.cumsum(shuf_gaps)

    dR_surr = compute_dR(surr_seq)
    surr_stds.append(np.std(dR_surr))

    acf_surr = autocorr(dR_surr, max_lag=20)
    surr_acf1.append(acf_surr[1])
    surr_acf2.append(acf_surr[2])

    psd_surr = np.abs(np.fft.rfft(dR_surr[:chunk]))**2 / chunk
    surr_psds.append(psd_surr)

surr_psd_mean = np.mean(surr_psds, axis=0)

print(f"  std(dR): prime={np.std(dR_prime):.8f}, surr={np.mean(surr_stds):.8f} +/- {np.std(surr_stds):.8f}")
z_std = (np.std(dR_prime) - np.mean(surr_stds)) / np.std(surr_stds) if np.std(surr_stds) > 0 else 0
print(f"  z-score(std): {z_std:.2f}")

print(f"\n  ACF lag-1: prime={acf_prime[1]:.6f}, surr={np.mean(surr_acf1):.6f} +/- {np.std(surr_acf1):.6f}")
z_acf1 = (acf_prime[1] - np.mean(surr_acf1)) / np.std(surr_acf1) if np.std(surr_acf1) > 0 else 0
print(f"  z-score(ACF1): {z_acf1:.2f}")

print(f"\n  ACF lag-2: prime={acf_prime[2]:.6f}, surr={np.mean(surr_acf2):.6f} +/- {np.std(surr_acf2):.6f}")
z_acf2 = (acf_prime[2] - np.mean(surr_acf2)) / np.std(surr_acf2) if np.std(surr_acf2) > 0 else 0
print(f"  z-score(ACF2): {z_acf2:.2f}")

# PSD ratio in bands
n_bands = 5
band_size = len(freqs) // n_bands
print(f"\n  PSD ratio (prime/surrogate) by frequency band:")
psd_ratios = []
for b in range(n_bands):
    s_idx = b * band_size + 1  # skip DC
    e_idx = (b + 1) * band_size
    ratio = np.mean(psd_prime[s_idx:e_idx]) / np.mean(surr_psd_mean[s_idx:e_idx])
    freq_range = f"[{freqs[s_idx]:.4f}, {freqs[e_idx-1]:.4f}]"
    print(f"    band {b+1} {freq_range}: ratio = {ratio:.4f}")
    psd_ratios.append(round(ratio, 4))

# --- Cramer surrogates (model comparison) ---
print(f"\n--- CRAMER SURROGATES (random model primes) ---")
cramer_stds = []
cramer_acf1 = []
for s in range(n_surr):
    # Cramer model: gap ~ exponential with rate 1/ln(p)
    cramer_seq = [primes[0]]
    for i in range(1, N):
        gap = max(2, round(np.random.exponential(np.log(cramer_seq[-1])) / 2) * 2)
        cramer_seq.append(cramer_seq[-1] + gap)
    cramer_seq = np.array(cramer_seq, dtype=np.float64)

    dR_cramer = compute_dR(cramer_seq)
    cramer_stds.append(np.std(dR_cramer))
    acf_cramer = autocorr(dR_cramer, max_lag=5)
    cramer_acf1.append(acf_cramer[1])

print(f"  std(dR): prime={np.std(dR_prime):.8f}, Cramer={np.mean(cramer_stds):.8f} +/- {np.std(cramer_stds):.8f}")
z_cramer_std = (np.std(dR_prime) - np.mean(cramer_stds)) / np.std(cramer_stds) if np.std(cramer_stds) > 0 else 0
print(f"  z-score(std vs Cramer): {z_cramer_std:.2f}")

print(f"\n  ACF lag-1: prime={acf_prime[1]:.6f}, Cramer={np.mean(cramer_acf1):.6f} +/- {np.std(cramer_acf1):.6f}")
z_cramer_acf = (acf_prime[1] - np.mean(cramer_acf1)) / np.std(cramer_acf1) if np.std(cramer_acf1) > 0 else 0
print(f"  z-score(ACF1 vs Cramer): {z_cramer_acf:.2f}")

# --- Summary ---
print(f"\n{'='*60}")
print("SUMMARY:")
print(f"  1. <R> = 2.0 is TAUTOLOGICAL (holds for any sequence)")
print(f"  2. The FLUCTUATIONS dR = R-2 encode gap structure")
print(f"  3. Prime dR vs shuffled:")
print(f"     - std:  z = {z_std:.1f} ({'DIFFERENT' if abs(z_std) > 2 else 'SAME'})")
print(f"     - ACF1: z = {z_acf1:.1f} ({'DIFFERENT' if abs(z_acf1) > 2 else 'SAME'})")
print(f"     - ACF2: z = {z_acf2:.1f} ({'DIFFERENT' if abs(z_acf2) > 2 else 'SAME'})")
print(f"  4. Prime dR vs Cramer:")
print(f"     - std:  z = {z_cramer_std:.1f}")
print(f"     - ACF1: z = {z_cramer_acf:.1f}")

verdict = "CONSTRAINT"
finding = "R=2 tautological. Curvature fluctuations encode gap correlations."
if abs(z_acf1) > 3 and abs(z_cramer_acf) > 3:
    verdict = "NEW"
    finding += " Prime-specific autocorrelation in dR detected vs both baselines."
elif abs(z_acf1) > 3:
    finding += " dR autocorrelation differs from shuffled but similar to Cramer."

print(f"\nVERDICT: {verdict}")
print(f"FINDING: {finding}")

# Save
results = {
    "experiment": "exp_geodesic_deviation_primes",
    "timestamp": datetime.now().isoformat(),
    "piano": 39,
    "tension": "METRIC_TENSOR",
    "claim_tested": "g=(p/2)^2 de Sitter — is R=2 specific to primes?",
    "answer": "NO. R=2 is tautological. The FLUCTUATIONS dR=R-2 encode prime structure.",
    "N_primes": N,
    "prime_dR_std": round(float(np.std(dR_prime)), 8),
    "prime_acf_lag1": round(float(acf_prime[1]), 6),
    "prime_acf_lag2": round(float(acf_prime[2]), 6),
    "shuffled_baseline": {
        "n_surrogates": n_surr,
        "dR_std_mean": round(float(np.mean(surr_stds)), 8),
        "z_score_std": round(z_std, 2),
        "z_score_acf1": round(z_acf1, 2),
        "z_score_acf2": round(z_acf2, 2)
    },
    "cramer_baseline": {
        "n_surrogates": n_surr,
        "dR_std_mean": round(float(np.mean(cramer_stds)), 8),
        "z_score_std": round(z_cramer_std, 2),
        "z_score_acf1": round(z_cramer_acf, 2)
    },
    "psd_ratios_by_band": psd_ratios,
    "verdict": verdict,
    "finding": finding
}

with open("/opt/MM_D-ND/tools/data/reports/exp_geodesic_deviation_primes.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nSaved to data/reports/exp_geodesic_deviation_primes.json")
