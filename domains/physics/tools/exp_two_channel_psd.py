#!/usr/bin/env python3
"""
exp_two_channel_psd.py — Spectral decomposition of two anti-correlation channels.

Prediction from TWO_CHANNEL_DECOMPOSITION + Wiener-Khinchin:
  If residue and magnitude channels are independent,
  S_total(f) = S_res(f) + S_mag(f).

Tests:
  1. Additivity: does S_res + S_mag reconstruct S_full?
  2. Spectral slopes: do channels have different slopes (from different ACF alphas)?
  3. Low-f suppression: which channel carries the blue-noise dip (PSD_BLUE_NOISE)?
  4. Scale dependence: does the channel balance shift at larger primes?

Null baseline: shuffled channels (preserve distribution, destroy order).

Usage:
    python tools/exp_two_channel_psd.py [--n_primes N] [--nperseg S]
"""

import argparse
import numpy as np
from scipy.signal import welch
from pathlib import Path
import json


def sieve_primes(limit):
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def get_primes(n_target):
    limit = int(n_target * (np.log(n_target) + np.log(np.log(n_target)) + 2))
    limit = max(limit, 1000)
    primes = sieve_primes(limit)
    while len(primes) < n_target:
        limit = int(limit * 1.5)
        primes = sieve_primes(limit)
    return primes[:n_target]


def decompose_to_additive(primes):
    """
    Decompose gap sequence into additive components:
      gap_i = trans_mean(type_i) + magnitude_residual_i

    The transition-mean component encodes residue structure.
    The magnitude residual encodes within-class ordering.
    If independent: Var(gap) = Var(trans_mean) + Var(mag_resid),
                     S(gap) = S(trans_mean) + S(mag_resid).
    """
    p = primes[primes > 3]
    gaps = np.diff(p).astype(float)

    res_l = p[:-1] % 6
    res_r = p[1:] % 6
    trans = res_l * 10 + res_r

    # Transition-mean component (carries residue info)
    trans_component = np.zeros_like(gaps)
    for tt in np.unique(trans):
        mask = trans == tt
        trans_component[mask] = gaps[mask].mean()

    # Center the transition component around global mean
    global_mean = gaps.mean()
    trans_centered = trans_component - global_mean

    # Magnitude residual (gap minus its transition mean)
    mag_residual = gaps - trans_component

    # Centered full gaps
    gaps_centered = gaps - global_mean

    return gaps_centered, trans_centered, mag_residual, p


def compute_psd(signal, nperseg=4096, fs=1.0):
    """Welch PSD estimate."""
    f, psd = welch(signal, fs=fs, nperseg=min(nperseg, len(signal)//2),
                   noverlap=nperseg//2, detrend='constant')
    return f, psd


def spectral_slope(f, psd, f_min=0.01, f_max=0.45):
    """Fit log(S) = a + b*log(f) in [f_min, f_max]."""
    mask = (f >= f_min) & (f <= f_max) & (psd > 0)
    if mask.sum() < 5:
        return np.nan, np.nan, np.nan
    lf = np.log10(f[mask])
    lp = np.log10(psd[mask])
    coeffs = np.polyfit(lf, lp, 1)
    pred = np.polyval(coeffs, lf)
    ss_res = np.sum((lp - pred)**2)
    ss_tot = np.sum((lp - lp.mean())**2)
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
    return coeffs[0], coeffs[1], r2  # slope, intercept, R2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_primes', type=int, default=2_000_000)
    parser.add_argument('--nperseg', type=int, default=4096)
    parser.add_argument('--n_surrogates', type=int, default=20)
    args = parser.parse_args()

    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    print(f"Got {len(primes):,} primes up to {primes[-1]:,}")

    # === Decomposition ===
    gaps_c, trans_c, mag_r, p_used = decompose_to_additive(primes)
    n = len(gaps_c)

    print(f"\n=== VARIANCE PARTITION ===")
    v_gap = np.var(gaps_c)
    v_trans = np.var(trans_c)
    v_mag = np.var(mag_r)
    v_cross = 2 * np.mean(trans_c * mag_r)
    print(f"  Var(gap_centered) = {v_gap:.4f}")
    print(f"  Var(trans_centered) = {v_trans:.4f} ({100*v_trans/v_gap:.2f}%)")
    print(f"  Var(mag_residual) = {v_mag:.4f} ({100*v_mag/v_gap:.2f}%)")
    print(f"  2*Cov(trans, mag) = {v_cross:.6f} ({100*v_cross/v_gap:.3f}%)")
    print(f"  Sum = {v_trans + v_mag + v_cross:.4f} ({100*(v_trans+v_mag+v_cross)/v_gap:.2f}%)")

    # === PSD of each channel ===
    print(f"\n=== POWER SPECTRAL DENSITIES (nperseg={args.nperseg}) ===")
    f_full, psd_full = compute_psd(gaps_c, nperseg=args.nperseg)
    f_trans, psd_trans = compute_psd(trans_c, nperseg=args.nperseg)
    f_mag, psd_mag = compute_psd(mag_r, nperseg=args.nperseg)

    # Additivity test: S_full vs S_trans + S_mag
    psd_sum = psd_trans + psd_mag

    # Relative error at each frequency
    with np.errstate(divide='ignore', invalid='ignore'):
        rel_error = np.abs(psd_full - psd_sum) / psd_full
    valid = np.isfinite(rel_error) & (f_full > 0)

    mean_rel_err = np.mean(rel_error[valid])
    max_rel_err = np.max(rel_error[valid])

    # Correlation between S_full and S_sum
    corr_psd = np.corrcoef(psd_full[valid], psd_sum[valid])[0, 1]

    print(f"\n  ADDITIVITY TEST: S_full vs S_trans + S_mag")
    print(f"  Mean relative error: {mean_rel_err:.4f} ({100*mean_rel_err:.2f}%)")
    print(f"  Max relative error: {max_rel_err:.4f} ({100*max_rel_err:.2f}%)")
    print(f"  Pearson(S_full, S_sum): {corr_psd:.6f}")

    # === Spectral slopes ===
    print(f"\n=== SPECTRAL SLOPES (f in [0.01, 0.45]) ===")
    for label, f_arr, psd_arr in [('Full gaps', f_full, psd_full),
                                    ('Trans (residue)', f_trans, psd_trans),
                                    ('Magnitude', f_mag, psd_mag),
                                    ('Trans + Mag', f_full, psd_sum)]:
        slope, intercept, r2 = spectral_slope(f_arr, psd_arr)
        print(f"  {label:18s}: slope = {slope:+.4f}, R2 = {r2:.3f}")

    # === Low-frequency analysis ===
    print(f"\n=== LOW-FREQUENCY STRUCTURE ===")
    low_mask = (f_full > 0.005) & (f_full < 0.05)
    high_mask = (f_full > 0.3) & (f_full < 0.48)

    if low_mask.any() and high_mask.any():
        # Dip ratio: S(low)/S(high) for each channel
        for label, psd_arr in [('Full', psd_full), ('Trans', psd_trans),
                                ('Magnitude', psd_mag)]:
            dip = np.mean(psd_arr[low_mask]) / np.mean(psd_arr[high_mask])
            print(f"  {label:12s}: S(low)/S(high) = {dip:.4f}")

        # Fraction of total PSD from each channel at low and high f
        frac_trans_low = np.mean(psd_trans[low_mask]) / np.mean(psd_full[low_mask])
        frac_trans_high = np.mean(psd_trans[high_mask]) / np.mean(psd_full[high_mask])
        frac_mag_low = np.mean(psd_mag[low_mask]) / np.mean(psd_full[low_mask])
        frac_mag_high = np.mean(psd_mag[high_mask]) / np.mean(psd_full[high_mask])

        print(f"\n  Channel fractions:")
        print(f"  {'':12s}  {'low-f':>8}  {'high-f':>8}  {'shift':>8}")
        print(f"  {'Trans':12s}  {frac_trans_low:8.4f}  {frac_trans_high:8.4f}  {frac_trans_low-frac_trans_high:+8.4f}")
        print(f"  {'Magnitude':12s}  {frac_mag_low:8.4f}  {frac_mag_high:8.4f}  {frac_mag_low-frac_mag_high:+8.4f}")

    # === Shuffled null baselines ===
    print(f"\n=== NULL BASELINES ({args.n_surrogates} surrogates) ===")
    slope_full_surr = []
    slope_trans_surr = []
    slope_mag_surr = []
    dip_full_surr = []

    for i in range(args.n_surrogates):
        g_shuf = gaps_c.copy(); np.random.shuffle(g_shuf)
        _, ps_shuf = compute_psd(g_shuf, nperseg=args.nperseg)
        s, _, _ = spectral_slope(f_full, ps_shuf)
        slope_full_surr.append(s)
        if low_mask.any() and high_mask.any():
            dip_full_surr.append(np.mean(ps_shuf[low_mask]) / np.mean(ps_shuf[high_mask]))

        t_shuf = trans_c.copy(); np.random.shuffle(t_shuf)
        _, ps_t = compute_psd(t_shuf, nperseg=args.nperseg)
        s, _, _ = spectral_slope(f_trans, ps_t)
        slope_trans_surr.append(s)

        m_shuf = mag_r.copy(); np.random.shuffle(m_shuf)
        _, ps_m = compute_psd(m_shuf, nperseg=args.nperseg)
        s, _, _ = spectral_slope(f_mag, ps_m)
        slope_mag_surr.append(s)

    slope_full_real, _, _ = spectral_slope(f_full, psd_full)
    slope_trans_real, _, _ = spectral_slope(f_trans, psd_trans)
    slope_mag_real, _, _ = spectral_slope(f_mag, psd_mag)

    for label, real_val, surr_vals in [('Full', slope_full_real, slope_full_surr),
                                        ('Trans', slope_trans_real, slope_trans_surr),
                                        ('Magnitude', slope_mag_real, slope_mag_surr)]:
        surr_mean = np.nanmean(surr_vals)
        surr_std = np.nanstd(surr_vals)
        z = (real_val - surr_mean) / surr_std if surr_std > 0 else 0
        print(f"  {label:12s}: slope={real_val:+.4f}, shuffle={surr_mean:+.4f}+/-{surr_std:.4f}, z={z:.1f}")

    if dip_full_surr:
        dip_real = np.mean(psd_full[low_mask]) / np.mean(psd_full[high_mask])
        dip_surr_mean = np.mean(dip_full_surr)
        dip_surr_std = np.std(dip_full_surr)
        z_dip = (dip_real - dip_surr_mean) / dip_surr_std if dip_surr_std > 0 else 0
        print(f"\n  Low-f dip: real={dip_real:.4f}, shuffle={dip_surr_mean:.4f}+/-{dip_surr_std:.4f}, z={z_dip:.1f}")

    # === Scale dependence ===
    print(f"\n=== SCALE DEPENDENCE (3 bands) ===")
    third = n // 3
    bands = [
        ("Small primes", 0, third),
        ("Medium primes", third, 2*third),
        ("Large primes", 2*third, n),
    ]

    scale_results = []
    for label, s, e in bands:
        g_band = gaps_c[s:e]
        t_band = trans_c[s:e]
        m_band = mag_r[s:e]

        seg = min(args.nperseg, len(g_band)//4)
        if seg < 256:
            continue

        f_b, psd_g = compute_psd(g_band, nperseg=seg)
        _, psd_t = compute_psd(t_band, nperseg=seg)
        _, psd_m = compute_psd(m_band, nperseg=seg)

        sl_g, _, r2_g = spectral_slope(f_b, psd_g)
        sl_t, _, r2_t = spectral_slope(f_b, psd_t)
        sl_m, _, r2_m = spectral_slope(f_b, psd_m)

        # Fraction of total PSD from transition channel
        frac_t = np.mean(psd_t) / np.mean(psd_g) if np.mean(psd_g) > 0 else 0

        ln_p_mid = np.log(p_used[s + (e-s)//2]) if s + (e-s)//2 < len(p_used) else 0

        print(f"  {label:16s} (ln p={ln_p_mid:.1f}): "
              f"slope_full={sl_g:+.3f} slope_trans={sl_t:+.3f} slope_mag={sl_m:+.3f} "
              f"frac_trans={frac_t:.4f}")

        scale_results.append({
            'label': label,
            'ln_p': float(ln_p_mid),
            'slope_full': float(sl_g) if not np.isnan(sl_g) else None,
            'slope_trans': float(sl_t) if not np.isnan(sl_t) else None,
            'slope_mag': float(sl_m) if not np.isnan(sl_m) else None,
            'frac_trans': float(frac_t),
        })

    # === Save ===
    output = {
        'experiment': 'two_channel_psd',
        'n_primes': int(len(primes)),
        'nperseg': args.nperseg,
        'n_surrogates': args.n_surrogates,
        'variance_partition': {
            'var_gap': float(v_gap),
            'var_trans': float(v_trans),
            'var_mag': float(v_mag),
            'cov_cross': float(v_cross),
            'pct_trans': float(100*v_trans/v_gap),
            'pct_mag': float(100*v_mag/v_gap),
        },
        'additivity': {
            'mean_relative_error': float(mean_rel_err),
            'max_relative_error': float(max_rel_err),
            'pearson_S_full_vs_S_sum': float(corr_psd),
        },
        'spectral_slopes': {
            'full': float(slope_full_real),
            'trans': float(slope_trans_real),
            'mag': float(slope_mag_real),
        },
        'null_baselines': {
            'z_slope_full': float((slope_full_real - np.nanmean(slope_full_surr)) / (np.nanstd(slope_full_surr) + 1e-10)),
            'z_slope_trans': float((slope_trans_real - np.nanmean(slope_trans_surr)) / (np.nanstd(slope_trans_surr) + 1e-10)),
            'z_slope_mag': float((slope_mag_real - np.nanmean(slope_mag_surr)) / (np.nanstd(slope_mag_surr) + 1e-10)),
        },
        'scale_dependence': scale_results,
    }

    out_path = Path(__file__).parent / 'data' / 'exp_two_channel_psd.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
