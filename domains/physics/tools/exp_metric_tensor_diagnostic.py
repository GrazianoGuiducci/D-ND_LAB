#!/usr/bin/env python3
"""
METRIC_TENSOR diagnostic — long experiment
Piano 39, tensione METRIC_TENSOR (0.9)

Domanda: DOVE vive la struttura dei primi nel tensore metrico g=(p/2)^2?
- Curvatura scalare R => tautologica (z=-8.8, exp precedente)
- Rapporti DeltaGamma => z=+22.5, ma non testato direttamente

Esperimento:
1. Calcola i simboli di Christoffel Gamma^t_tt nella coordinata tau=ln(p)
2. Calcola DeltaGamma (variazione gap-to-gap della connessione)  
3. Calcola rapporti DeltaGamma_n/DeltaGamma_{n+1}
4. Confronta con Cramer surrogates e shuffled gaps
5. Misura il contenuto spettrale di DeltaGamma vs dR
6. Cerca la firma di phi nei rapporti
"""

import json
import numpy as np
from datetime import datetime
import sys

np.random.seed(42)

# ==== Generate primes via sieve ====
def sieve(limit):
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5)+1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.where(is_prime)[0]

print("Generating primes up to 10^7...")
primes = sieve(10_000_000)
N = len(primes)
print(f"N = {N} primes")

# ==== Coordinate ====
p = primes.astype(np.float64)
tau = np.log(p)  # de Sitter time coordinate
g = (p/2)**2     # metric tensor component

# ==== Gaps ====
gaps = np.diff(p)
log_gaps = np.diff(tau)  # gaps in tau coordinate

# ==== 1. Christoffel symbols ====
# For 1D metric g(tau), Gamma^tau_tautau = (1/2g) dg/dtau
# In discrete: dg/dtau ~ (g[n+1]-g[n])/(tau[n+1]-tau[n])
dg = np.diff(g)
dtau = np.diff(tau)
g_mid = (g[:-1] + g[1:]) / 2
Gamma = dg / (2 * g_mid * dtau)

print(f"Christoffel Gamma: mean={np.mean(Gamma):.6f}, std={np.std(Gamma):.6f}")

# ==== 2. DeltaGamma ====
DeltaGamma = np.diff(Gamma)
print(f"DeltaGamma: mean={np.mean(DeltaGamma):.6f}, std={np.std(DeltaGamma):.6f}")

# ==== 3. Rapporti DeltaGamma consecutivi ====
# Evita divisione per zero
mask = np.abs(DeltaGamma[:-1]) > 1e-20
DG_ratios = DeltaGamma[1:][mask] / DeltaGamma[:-1][mask]
# Clamp outliers per statistiche robuste
DG_ratios_clipped = np.clip(DG_ratios, -100, 100)
print(f"DeltaGamma ratios: mean={np.mean(DG_ratios_clipped):.6f}, median={np.median(DG_ratios_clipped):.6f}")

# ==== 4. Gap ratio <r> (Oganesyan-Huse) per confronto ====
r_ratios = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
r_mean_prime = np.mean(r_ratios)
print(f"Gap ratio <r>: {r_mean_prime:.6f}")

# ==== 5. Curvature fluctuations dR ====
# R = 2 for de Sitter; dR = R_discrete - 2
# R_discrete from second derivative of g in tau
d2g = np.diff(g, 2)
dtau2 = dtau[:-1] * dtau[1:]  # approximate
g_center = g[1:-1]
R_discrete = -d2g / (g_center * dtau2) + (dg[:-1]/(g_center*dtau[:-1]))**2
dR = R_discrete - 2.0

print(f"dR: mean={np.mean(dR):.6e}, std={np.std(dR):.6e}")

# ==== 6. Null baselines ====
n_surr = 30
results_surr = {
    'cramer': {'DG_std': [], 'DG_ratio_mean': [], 'DG_ratio_median': [], 'r_mean': [], 'dR_std': []},
    'shuffled': {'DG_std': [], 'DG_ratio_mean': [], 'DG_ratio_median': [], 'r_mean': [], 'dR_std': []}
}

print(f"Running {n_surr} surrogates each (Cramer + shuffled)...")

for i in range(n_surr):
    # Cramer surrogate: gaps ~ Exponential(ln(p))
    cramer_gaps = np.random.exponential(np.log(p[:len(gaps)]), size=len(gaps))
    cramer_gaps = np.maximum(cramer_gaps, 2)  # min gap = 2
    cramer_p = np.cumsum(np.concatenate([[p[0]], cramer_gaps]))[:N]
    cramer_tau = np.log(np.maximum(cramer_p, 2))
    cramer_g = (cramer_p/2)**2
    
    cdg = np.diff(cramer_g)
    cdtau = np.diff(cramer_tau)
    cdtau[cdtau == 0] = 1e-15
    cg_mid = (cramer_g[:-1] + cramer_g[1:]) / 2
    cGamma = cdg / (2 * cg_mid * cdtau)
    cDG = np.diff(cGamma)
    cmask = np.abs(cDG[:-1]) > 1e-20
    if np.sum(cmask) > 100:
        cDG_r = np.clip(cDG[1:][cmask] / cDG[:-1][cmask], -100, 100)
        results_surr['cramer']['DG_ratio_mean'].append(np.mean(cDG_r))
        results_surr['cramer']['DG_ratio_median'].append(np.median(cDG_r))
    results_surr['cramer']['DG_std'].append(np.std(cDG))
    
    cr = np.minimum(cramer_gaps[:-1], cramer_gaps[1:]) / np.maximum(cramer_gaps[:-1], cramer_gaps[1:])
    results_surr['cramer']['r_mean'].append(np.mean(cr))
    
    # dR for Cramer
    cd2g = np.diff(cramer_g[:N], 2)
    cdtau2 = cdtau[:N-2] * cdtau[1:N-1] if len(cdtau) >= N-1 else cdtau[:-1]*cdtau[1:]
    min_len = min(len(cd2g), len(cdtau2))
    cg_c = cramer_g[1:min_len+1]
    cR = -cd2g[:min_len] / (cg_c * cdtau2[:min_len]) + (cdg[:min_len]/(cg_c*cdtau[:min_len]))**2
    results_surr['cramer']['dR_std'].append(np.std(cR - 2.0))
    
    # Shuffled gaps
    shuf_gaps = np.random.permutation(gaps)
    shuf_p = np.cumsum(np.concatenate([[p[0]], shuf_gaps]))[:N]
    shuf_tau = np.log(np.maximum(shuf_p, 2))
    shuf_g = (shuf_p/2)**2
    
    sdg = np.diff(shuf_g)
    sdtau = np.diff(shuf_tau)
    sdtau[sdtau == 0] = 1e-15
    sg_mid = (shuf_g[:-1] + shuf_g[1:]) / 2
    sGamma = sdg / (2 * sg_mid * sdtau)
    sDG = np.diff(sGamma)
    smask = np.abs(sDG[:-1]) > 1e-20
    if np.sum(smask) > 100:
        sDG_r = np.clip(sDG[1:][smask] / sDG[:-1][smask], -100, 100)
        results_surr['shuffled']['DG_ratio_mean'].append(np.mean(sDG_r))
        results_surr['shuffled']['DG_ratio_median'].append(np.median(sDG_r))
    results_surr['shuffled']['DG_std'].append(np.std(sDG))
    
    sr = np.minimum(shuf_gaps[:-1], shuf_gaps[1:]) / np.maximum(shuf_gaps[:-1], shuf_gaps[1:])
    results_surr['shuffled']['r_mean'].append(np.mean(sr))
    
    sd2g = np.diff(shuf_g[:N], 2)
    sdtau2 = sdtau[:N-2] * sdtau[1:N-1] if len(sdtau) >= N-1 else sdtau[:-1]*sdtau[1:]
    min_len_s = min(len(sd2g), len(sdtau2))
    sg_c = shuf_g[1:min_len_s+1]
    sR = -sd2g[:min_len_s] / (sg_c * sdtau2[:min_len_s]) + (sdg[:min_len_s]/(sg_c*sdtau[:min_len_s]))**2
    results_surr['shuffled']['dR_std'].append(np.std(sR - 2.0))

print("Surrogates done.")

# ==== 7. Z-scores ====
def zscore(val, surr_list):
    arr = np.array(surr_list)
    return (val - np.mean(arr)) / (np.std(arr) + 1e-30)

z_DG_std_cramer = zscore(np.std(DeltaGamma), results_surr['cramer']['DG_std'])
z_DG_std_shuffled = zscore(np.std(DeltaGamma), results_surr['shuffled']['DG_std'])
z_r_cramer = zscore(r_mean_prime, results_surr['cramer']['r_mean'])
z_r_shuffled = zscore(r_mean_prime, results_surr['shuffled']['r_mean'])
z_dR_cramer = zscore(np.std(dR), results_surr['cramer']['dR_std'])
z_dR_shuffled = zscore(np.std(dR), results_surr['shuffled']['dR_std'])

if results_surr['cramer']['DG_ratio_median']:
    z_DGratio_cramer = zscore(np.median(DG_ratios_clipped), results_surr['cramer']['DG_ratio_median'])
    z_DGratio_shuffled = zscore(np.median(DG_ratios_clipped), results_surr['shuffled']['DG_ratio_median'])
else:
    z_DGratio_cramer = z_DGratio_shuffled = float('nan')

print(f"\n=== Z-SCORES ===")
print(f"DeltaGamma std:  z_cramer={z_DG_std_cramer:.2f}, z_shuffled={z_DG_std_shuffled:.2f}")
print(f"DeltaGamma ratio median: z_cramer={z_DGratio_cramer:.2f}, z_shuffled={z_DGratio_shuffled:.2f}")
print(f"Gap ratio <r>:   z_cramer={z_r_cramer:.2f}, z_shuffled={z_r_shuffled:.2f}")
print(f"dR std:          z_cramer={z_dR_cramer:.2f}, z_shuffled={z_dR_shuffled:.2f}")

# ==== 8. Windowed analysis (scale dependence) ====
n_windows = 20
window_size = 20000
windows_data = []

indices = np.linspace(0, N - window_size - 3, n_windows, dtype=int)

for idx in indices:
    w_p = p[idx:idx+window_size]
    w_tau = np.log(w_p)
    w_g = (w_p/2)**2
    w_gaps = np.diff(w_p)
    
    # DeltaGamma in window
    wdg = np.diff(w_g)
    wdtau = np.diff(w_tau)
    wg_mid = (w_g[:-1] + w_g[1:])/2
    wGamma = wdg / (2*wg_mid*wdtau)
    wDG = np.diff(wGamma)
    
    # DG ratios
    wmask = np.abs(wDG[:-1]) > 1e-20
    if np.sum(wmask) > 10:
        wDG_r = np.clip(wDG[1:][wmask] / wDG[:-1][wmask], -100, 100)
        wDG_med = float(np.median(wDG_r))
    else:
        wDG_med = float('nan')
    
    # gap ratio
    wr = np.minimum(w_gaps[:-1], w_gaps[1:]) / np.maximum(w_gaps[:-1], w_gaps[1:])
    
    # dR
    wd2g = np.diff(w_g, 2)
    wdtau2 = wdtau[:-1]*wdtau[1:]
    wg_c = w_g[1:-1]
    wR = -wd2g / (wg_c * wdtau2) + (wdg[:-1]/(wg_c*wdtau[:-1]))**2
    wdR = wR - 2.0
    
    windows_data.append({
        'p_center': float(np.median(w_p)),
        'ln_p': float(np.log(np.median(w_p))),
        'DG_std': float(np.std(wDG)),
        'DG_ratio_median': wDG_med,
        'gap_r_mean': float(np.mean(wr)),
        'dR_std': float(np.std(wdR)),
        'dR_acf1': float(np.corrcoef(wdR[:-1], wdR[1:])[0,1]) if len(wdR)>2 else float('nan')
    })

# ==== 9. Correlation DG_ratio vs gap_r across windows ====
dg_meds = [w['DG_ratio_median'] for w in windows_data]
gap_rs = [w['gap_r_mean'] for w in windows_data]
valid = [i for i in range(len(dg_meds)) if not np.isnan(dg_meds[i])]
if len(valid) > 5:
    corr_DGr_gapr = float(np.corrcoef([dg_meds[i] for i in valid], [gap_rs[i] for i in valid])[0,1])
else:
    corr_DGr_gapr = float('nan')

print(f"\nCorrelation(DG_ratio_median, gap_r_mean) across windows: {corr_DGr_gapr:.4f}")

# ==== 10. Spectral comparison: DeltaGamma vs dR ====
from numpy.fft import rfft

# Use central 100K chunk for clean FFT
chunk = 100000
start = N//2 - chunk//2
DG_chunk = DeltaGamma[start:start+chunk]
dR_chunk = dR[start:start+chunk]
min_chunk = min(len(DG_chunk), len(dR_chunk))
DG_chunk = DG_chunk[:min_chunk]
dR_chunk = dR_chunk[:min_chunk]

psd_DG = np.abs(rfft(DG_chunk - np.mean(DG_chunk)))**2
psd_dR = np.abs(rfft(dR_chunk - np.mean(dR_chunk)))**2

# Band power ratios (5 bands)
n_fft = min(len(psd_DG), len(psd_dR))
bands = np.array_split(np.arange(1, n_fft), 5)
band_ratio_DG_dR = []
for band in bands:
    pDG = np.mean(psd_DG[band])
    pdR = np.mean(psd_dR[band])
    band_ratio_DG_dR.append(float(pDG / (pdR + 1e-30)))

print(f"PSD ratio DG/dR by band: {[f'{x:.4f}' for x in band_ratio_DG_dR]}")

# ==== 11. Search for phi in DG ratios distribution ====
# Histogram of |DG_ratios| — look for peaks near phi, 1/phi
abs_DGr = np.abs(DG_ratios_clipped)
bins_phi = np.linspace(0, 3, 300)
hist, edges = np.histogram(abs_DGr, bins=bins_phi, density=True)
centers = (edges[:-1] + edges[1:]) / 2

# Density at phi and 1/phi vs neighbors
phi = (1 + np.sqrt(5)) / 2
idx_phi = np.argmin(np.abs(centers - phi))
idx_invphi = np.argmin(np.abs(centers - 1/phi))
idx_1 = np.argmin(np.abs(centers - 1.0))

# Local density +/- 5 bins
def local_density(h, idx, w=5):
    lo, hi = max(0, idx-w), min(len(h), idx+w+1)
    return float(np.mean(h[lo:hi]))

dens_phi = local_density(hist, idx_phi)
dens_invphi = local_density(hist, idx_invphi)
dens_1 = local_density(hist, idx_1)
dens_05 = local_density(hist, np.argmin(np.abs(centers - 0.5)))

print(f"\n|DG_ratio| density at phi={phi:.4f}: {dens_phi:.4f}")
print(f"|DG_ratio| density at 1/phi={1/phi:.4f}: {dens_invphi:.4f}")
print(f"|DG_ratio| density at 1.0: {dens_1:.4f}")
print(f"|DG_ratio| density at 0.5: {dens_05:.4f}")

# ==== 12. Scale dependence of DG signals ====
# Fit DG_std vs ln(p) across windows
lnp_w = np.array([w['ln_p'] for w in windows_data])
DG_std_w = np.array([w['DG_std'] for w in windows_data])
dR_std_w = np.array([w['dR_std'] for w in windows_data])

from numpy.polynomial import polynomial as P
if len(lnp_w) > 3:
    # log-log fit for DG_std
    log_DG = np.log(DG_std_w + 1e-30)
    coeff_DG = np.polyfit(lnp_w, log_DG, 1)
    # log-log fit for dR_std
    log_dR = np.log(dR_std_w + 1e-30)
    coeff_dR = np.polyfit(lnp_w, log_dR, 1)
    
    print(f"\nDG_std scaling: slope={coeff_DG[0]:.4f} (in log-log: DG_std ~ p^{coeff_DG[0]:.3f})")
    print(f"dR_std scaling: slope={coeff_dR[0]:.4f} (in log-log: dR_std ~ p^{coeff_dR[0]:.3f})")
else:
    coeff_DG = [0, 0]
    coeff_dR = [0, 0]

# ==== Build output ====
output = {
    "experiment": "exp_metric_tensor_diagnostic_long",
    "timestamp": datetime.now().isoformat(),
    "piano": 39,
    "tension": "METRIC_TENSOR",
    "intensity": 0.9,
    "claim_tested": "g=(p/2)^2 de Sitter: WHERE does prime structure live? Curvature R vs connection DeltaGamma",
    "N_primes": int(N),
    "prime_range": f"2 to {int(primes[-1])}",
    
    "christoffel": {
        "Gamma_mean": float(np.mean(Gamma)),
        "Gamma_std": float(np.std(Gamma)),
    },
    "delta_gamma": {
        "DG_mean": float(np.mean(DeltaGamma)),
        "DG_std": float(np.std(DeltaGamma)),
        "DG_ratio_mean": float(np.mean(DG_ratios_clipped)),
        "DG_ratio_median": float(np.median(DG_ratios_clipped)),
    },
    "curvature_fluctuations": {
        "dR_mean": float(np.mean(dR)),
        "dR_std": float(np.std(dR)),
    },
    "gap_ratio_r": float(r_mean_prime),
    
    "z_scores": {
        "DG_std_vs_cramer": round(z_DG_std_cramer, 2),
        "DG_std_vs_shuffled": round(z_DG_std_shuffled, 2),
        "DG_ratio_median_vs_cramer": round(z_DGratio_cramer, 2),
        "DG_ratio_median_vs_shuffled": round(z_DGratio_shuffled, 2),
        "gap_r_vs_cramer": round(z_r_cramer, 2),
        "gap_r_vs_shuffled": round(z_r_shuffled, 2),
        "dR_std_vs_cramer": round(z_dR_cramer, 2),
        "dR_std_vs_shuffled": round(z_dR_shuffled, 2),
    },
    
    "cross_window_correlation": {
        "DG_ratio_vs_gap_r": round(corr_DGr_gapr, 4),
    },
    
    "spectral_DG_over_dR_by_band": [round(x, 4) for x in band_ratio_DG_dR],
    
    "phi_search_DG_ratios": {
        "density_at_phi": round(dens_phi, 4),
        "density_at_inv_phi": round(dens_invphi, 4),
        "density_at_1": round(dens_1, 4),
        "density_at_0.5": round(dens_05, 4),
    },
    
    "scaling": {
        "DG_std_slope_lnp": round(coeff_DG[0], 4),
        "dR_std_slope_lnp": round(coeff_dR[0], 4),
        "note": "DG_std ~ exp(slope*ln(p)) = p^slope"
    },
    
    "windows": windows_data,
    
    "surrogates": {
        "n": n_surr,
        "cramer_DG_std_mean": float(np.mean(results_surr['cramer']['DG_std'])),
        "cramer_r_mean": float(np.mean(results_surr['cramer']['r_mean'])),
        "shuffled_DG_std_mean": float(np.mean(results_surr['shuffled']['DG_std'])),
        "shuffled_r_mean": float(np.mean(results_surr['shuffled']['r_mean'])),
    }
}

# Save JSON
json_path = '/opt/MM_D-ND/tools/data/reports/exp_metric_tensor_diag_long.json'
with open(json_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f"\nSaved: {json_path}")

# Print summary for report
print("\n=== SUMMARY ===")
print(f"Christoffel Gamma: mean={output['christoffel']['Gamma_mean']:.6f}")
print(f"DeltaGamma std: {output['delta_gamma']['DG_std']:.6e}")
print(f"DG ratio median: {output['delta_gamma']['DG_ratio_median']:.6f}")
print(f"dR std: {output['curvature_fluctuations']['dR_std']:.6e}")
print(f"<r> prime: {output['gap_ratio_r']:.6f}")
print(f"Z-scores DG: cramer={z_DG_std_cramer:.1f}, shuffled={z_DG_std_shuffled:.1f}")
print(f"Z-scores DG ratio: cramer={z_DGratio_cramer:.1f}, shuffled={z_DGratio_shuffled:.1f}")
print(f"Z-scores <r>: cramer={z_r_cramer:.1f}, shuffled={z_r_shuffled:.1f}")
print(f"Z-scores dR: cramer={z_dR_cramer:.1f}, shuffled={z_dR_shuffled:.1f}")
print(f"DG_ratio ~ gap_r correlation: {corr_DGr_gapr:.4f}")
print(f"DG_std scaling: p^{coeff_DG[0]:.3f}")
print(f"dR_std scaling: p^{coeff_dR[0]:.3f}")
