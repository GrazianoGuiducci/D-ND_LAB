#!/usr/bin/env python3
"""
exp_two_channel_decomposition.py — Decompose prime gap anti-correlation into two channels.

Discovery from agent_0418: Z/6Z residue lag-1 acf = -0.148 (3.8x magnitude acf1=-0.039).
Question: Are these independent channels with separate scaling laws?

Channels:
  1. RESIDUE channel: sequence of Z/6Z residue classes {1,5} → mapped to {+1,-1}
     (equivalent to the sequence of (p mod 6) for p>3)
  2. MAGNITUDE channel: gap sizes WITHIN each residue class
     (conditional gap given residue transition)

For each channel, across prime scales:
  - lag-1 autocorrelation
  - Full ACF decay law (power-law exponent)
  - Coherence length (minimum window where ordering is detectable)
  - Extrapolated Poisson crossover

Null baseline: shuffled versions of each channel independently.

Usage:
    python tools/exp_two_channel_decomposition.py [--n_primes N] [--n_windows W] [--n_surrogates S]
"""

import argparse
import json
import numpy as np
from pathlib import Path

def sieve_primes(limit):
    """Sieve of Eratosthenes."""
    is_prime = np.ones(limit, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]

def get_primes(n_target):
    """Get at least n_target primes."""
    # Prime counting function approximation
    limit = int(n_target * (np.log(n_target) + np.log(np.log(n_target)) + 2))
    limit = max(limit, 1000)
    primes = sieve_primes(limit)
    while len(primes) < n_target:
        limit = int(limit * 1.5)
        primes = sieve_primes(limit)
    return primes[:n_target]

def decompose_channels(primes):
    """
    Decompose prime gap sequence into residue and magnitude channels.

    For primes > 3, p mod 6 is either 1 or 5.
    Residue channel: +1 if p mod 6 == 1, -1 if p mod 6 == 5
    Magnitude channel: gap size, with mean removed per residue-transition type
    """
    # Skip 2, 3
    p = primes[primes > 3]
    gaps = np.diff(p)

    # Residue classes
    residues = p[:-1] % 6  # residue of the left prime of each gap
    residue_right = p[1:] % 6

    # Residue channel: binary sequence of left-prime residue
    # Map: 1 -> +1, 5 -> -1
    residue_channel = np.where(residues == 1, 1.0, -1.0)

    # Transition types: (1->1), (1->5), (5->1), (5->5)
    transition = residues * 10 + residue_right  # 11, 15, 51, 55

    # Magnitude channel: gap size demeaned by transition type
    magnitude_channel = gaps.astype(float).copy()
    for tt in np.unique(transition):
        mask = transition == tt
        magnitude_channel[mask] -= magnitude_channel[mask].mean()

    return gaps, residue_channel, magnitude_channel, residues, residue_right, p

def acf(x, max_lag=50):
    """Compute autocorrelation function up to max_lag."""
    n = len(x)
    x_centered = x - x.mean()
    var = np.var(x)
    if var == 0:
        return np.zeros(max_lag)
    result = np.zeros(max_lag)
    for k in range(max_lag):
        result[k] = np.mean(x_centered[:n-k] * x_centered[k:]) / var if k < n else 0
    return result

def fit_power_law_acf(acf_values, min_lag=1, max_lag=20):
    """Fit |acf(k)| = A / k^alpha for k >= min_lag."""
    lags = np.arange(min_lag, min(max_lag + 1, len(acf_values)))
    vals = np.abs(acf_values[min_lag:min_lag + len(lags)])

    # Filter positive values for log fit
    pos = vals > 0
    if pos.sum() < 3:
        return np.nan, np.nan, np.nan

    log_k = np.log(lags[pos])
    log_v = np.log(vals[pos])

    # Linear fit: log(|acf|) = log(A) - alpha * log(k)
    coeffs = np.polyfit(log_k, log_v, 1)
    alpha = -coeffs[0]
    A = np.exp(coeffs[1])

    # R^2
    predicted = coeffs[0] * log_k + coeffs[1]
    ss_res = np.sum((log_v - predicted)**2)
    ss_tot = np.sum((log_v - log_v.mean())**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return A, alpha, r2

def measure_coherence_length(channel, n_surrogates=20, window_sizes=None):
    """
    Find minimum window size where channel ordering is detectable.
    Coherence length L* = smallest L where |acf1_real - acf1_shuffle| > 2*sigma.
    """
    if window_sizes is None:
        window_sizes = [10, 15, 20, 25, 30, 40, 50, 70, 100, 150, 200, 300, 500]

    n = len(channel)
    results = []

    for L in window_sizes:
        if L >= n // 2:
            break
        n_windows = min(200, n // L)

        # Real ACF1 across windows
        acf1_real = []
        for i in range(n_windows):
            start = i * (n // n_windows)
            chunk = channel[start:start+L]
            if len(chunk) >= L:
                c = chunk - chunk.mean()
                v = np.var(chunk)
                if v > 0:
                    acf1_real.append(np.mean(c[:-1] * c[1:]) / v)

        if len(acf1_real) < 10:
            continue

        mean_real = np.mean(acf1_real)

        # Shuffled surrogates
        acf1_surr = []
        for _ in range(n_surrogates):
            shuffled = channel.copy()
            np.random.shuffle(shuffled)
            for i in range(min(50, n_windows)):
                start = i * (n // n_windows)
                chunk = shuffled[start:start+L]
                if len(chunk) >= L:
                    c = chunk - chunk.mean()
                    v = np.var(chunk)
                    if v > 0:
                        acf1_surr.append(np.mean(c[:-1] * c[1:]) / v)

        mean_surr = np.mean(acf1_surr) if acf1_surr else 0
        std_surr = np.std(acf1_surr) if acf1_surr else 1

        z = (mean_real - mean_surr) / std_surr if std_surr > 0 else 0

        results.append({
            'L': L,
            'acf1_real': mean_real,
            'acf1_surr': mean_surr,
            'z_score': z,
            'significant': abs(z) > 2.0
        })

    # Find L*
    l_star = None
    for r in results:
        if r['significant']:
            l_star = r['L']
            break

    return l_star, results

def scaling_analysis(primes, n_windows=15, n_surrogates=10):
    """
    Measure both channels across prime scales.
    """
    p_all = primes[primes > 3]
    n = len(p_all)

    # Log-spaced windows
    chunk_size = n // n_windows

    results = []

    for i in range(n_windows):
        start = i * chunk_size
        end = start + chunk_size
        p_chunk = p_all[start:end]

        if len(p_chunk) < 1000:
            continue

        gaps = np.diff(p_chunk)
        ln_p = np.log(p_chunk[len(p_chunk)//2])  # median prime

        # Residue channel
        res = p_chunk[:-1] % 6
        res_channel = np.where(res == 1, 1.0, -1.0)

        # Magnitude channel (demeaned by transition)
        res_right = p_chunk[1:] % 6
        trans = res * 10 + res_right
        mag_channel = gaps.astype(float).copy()
        for tt in np.unique(trans):
            mask = trans == tt
            if mask.sum() > 1:
                mag_channel[mask] -= mag_channel[mask].mean()

        # Full gap ACF
        acf_full = acf(gaps.astype(float), max_lag=30)
        A_full, alpha_full, r2_full = fit_power_law_acf(acf_full)

        # Residue channel ACF
        acf_res = acf(res_channel, max_lag=30)
        A_res, alpha_res, r2_res = fit_power_law_acf(acf_res)

        # Magnitude channel ACF
        acf_mag = acf(mag_channel, max_lag=30)
        A_mag, alpha_mag, r2_mag = fit_power_law_acf(acf_mag)

        # Shuffled baselines
        acf1_full_surr = []
        acf1_res_surr = []
        acf1_mag_surr = []
        for _ in range(n_surrogates):
            s_gaps = gaps.copy()
            np.random.shuffle(s_gaps)
            acf1_full_surr.append(acf(s_gaps.astype(float), max_lag=2)[1])

            s_res = res_channel.copy()
            np.random.shuffle(s_res)
            acf1_res_surr.append(acf(s_res, max_lag=2)[1])

            s_mag = mag_channel.copy()
            np.random.shuffle(s_mag)
            acf1_mag_surr.append(acf(s_mag, max_lag=2)[1])

        results.append({
            'ln_p': float(ln_p),
            'p_median': float(p_chunk[len(p_chunk)//2]),
            'n_gaps': len(gaps),
            # Full
            'acf1_full': float(acf_full[1]),
            'acf1_full_surr': float(np.mean(acf1_full_surr)),
            'z_full': float((acf_full[1] - np.mean(acf1_full_surr)) / (np.std(acf1_full_surr) + 1e-10)),
            'A_full': float(A_full) if not np.isnan(A_full) else None,
            'alpha_full': float(alpha_full) if not np.isnan(alpha_full) else None,
            # Residue
            'acf1_res': float(acf_res[1]),
            'acf1_res_surr': float(np.mean(acf1_res_surr)),
            'z_res': float((acf_res[1] - np.mean(acf1_res_surr)) / (np.std(acf1_res_surr) + 1e-10)),
            'A_res': float(A_res) if not np.isnan(A_res) else None,
            'alpha_res': float(alpha_res) if not np.isnan(alpha_res) else None,
            # Magnitude
            'acf1_mag': float(acf_mag[1]),
            'acf1_mag_surr': float(np.mean(acf1_mag_surr)),
            'z_mag': float((acf_mag[1] - np.mean(acf1_mag_surr)) / (np.std(acf1_mag_surr) + 1e-10)),
            'A_mag': float(A_mag) if not np.isnan(A_mag) else None,
            'alpha_mag': float(alpha_mag) if not np.isnan(alpha_mag) else None,
            # ACF profiles (first 20 lags)
            'acf_full_20': [float(x) for x in acf_full[:20]],
            'acf_res_20': [float(x) for x in acf_res[:20]],
            'acf_mag_20': [float(x) for x in acf_mag[:20]],
        })

    return results

def main():
    parser = argparse.ArgumentParser(description='Two-channel decomposition of prime gap anti-correlation')
    parser.add_argument('--n_primes', type=int, default=6_000_000, help='Number of primes')
    parser.add_argument('--n_windows', type=int, default=15, help='Number of scale windows')
    parser.add_argument('--n_surrogates', type=int, default=10, help='Surrogates per window')
    args = parser.parse_args()

    print(f"Generating {args.n_primes:,} primes...")
    primes = get_primes(args.n_primes)
    print(f"Got {len(primes):,} primes up to {primes[-1]:,}")

    # === 1. Global decomposition ===
    print("\n=== GLOBAL DECOMPOSITION ===")
    gaps, res_ch, mag_ch, res_l, res_r, p_used = decompose_channels(primes)

    # Transition statistics
    trans = res_l * 10 + res_r
    for tt in [11, 15, 51, 55]:
        mask = trans == tt
        label = f"{tt//10}->{tt%10}"
        print(f"  Transition {label}: n={mask.sum():,}, mean_gap={gaps[mask].mean():.2f}, std={gaps[mask].std():.2f}")

    # Global ACF
    print(f"\n  Full gap acf1 = {acf(gaps.astype(float), 2)[1]:.6f}")
    print(f"  Residue ch acf1 = {acf(res_ch, 2)[1]:.6f}")
    print(f"  Magnitude ch acf1 = {acf(mag_ch, 2)[1]:.6f}")

    # Ratio
    acf1_full = acf(gaps.astype(float), 2)[1]
    acf1_res = acf(res_ch, 2)[1]
    acf1_mag = acf(mag_ch, 2)[1]
    print(f"\n  Ratio |res/full| = {abs(acf1_res/acf1_full):.2f}x")
    print(f"  Ratio |mag/full| = {abs(acf1_mag/acf1_full):.2f}x")

    # === 2. Scaling analysis ===
    print(f"\n=== SCALING ANALYSIS ({args.n_windows} windows) ===")
    scaling = scaling_analysis(primes, n_windows=args.n_windows, n_surrogates=args.n_surrogates)

    print(f"\n{'ln(p)':>7} | {'acf1_full':>10} {'z':>6} | {'acf1_res':>10} {'z':>6} | {'acf1_mag':>10} {'z':>6}")
    print("-" * 75)
    for s in scaling:
        print(f"{s['ln_p']:7.2f} | {s['acf1_full']:10.6f} {s['z_full']:6.1f} | "
              f"{s['acf1_res']:10.6f} {s['z_res']:6.1f} | "
              f"{s['acf1_mag']:10.6f} {s['z_mag']:6.1f}")

    # === 3. Linear fits for scaling laws ===
    print("\n=== SCALING LAWS ===")
    ln_ps = np.array([s['ln_p'] for s in scaling])

    for label, key in [('Full', 'acf1_full'), ('Residue', 'acf1_res'), ('Magnitude', 'acf1_mag')]:
        vals = np.array([s[key] for s in scaling])
        # Linear fit: acf1 = a + b * ln(p)
        valid = ~np.isnan(vals)
        if valid.sum() >= 3:
            coeffs = np.polyfit(ln_ps[valid], vals[valid], 1)
            slope, intercept = coeffs
            predicted = np.polyval(coeffs, ln_ps[valid])
            ss_res = np.sum((vals[valid] - predicted)**2)
            ss_tot = np.sum((vals[valid] - vals[valid].mean())**2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            # Poisson crossover: acf1 = 0
            if slope != 0:
                ln_p_cross = -intercept / slope
                p_cross = np.exp(ln_p_cross)
            else:
                ln_p_cross = np.inf
                p_cross = np.inf

            print(f"  {label:12s}: acf1 = {intercept:.6f} + {slope:.6f} * ln(p)  "
                  f"R2={r2:.3f}  Poisson at ln(p)={ln_p_cross:.1f} (p~10^{ln_p_cross/np.log(10):.1f})")

    # === 4. Power-law exponents ===
    print("\n=== POWER-LAW EXPONENTS (|acf(k)| ~ A/k^alpha) ===")
    for label, a_key, al_key in [('Full', 'A_full', 'alpha_full'),
                                   ('Residue', 'A_res', 'alpha_res'),
                                   ('Magnitude', 'A_mag', 'alpha_mag')]:
        As = [s[a_key] for s in scaling if s[a_key] is not None]
        alphas = [s[al_key] for s in scaling if s[al_key] is not None]
        if As:
            print(f"  {label:12s}: A={np.mean(As):.4f}+/-{np.std(As):.4f}, "
                  f"alpha={np.mean(alphas):.3f}+/-{np.std(alphas):.3f}")

    # === 5. Coherence lengths ===
    print("\n=== COHERENCE LENGTHS ===")
    l_star_res, coh_res = measure_coherence_length(res_ch)
    l_star_mag, coh_mag = measure_coherence_length(mag_ch)
    l_star_full, coh_full = measure_coherence_length(gaps.astype(float))

    print(f"  Full gaps:     L* = {l_star_full}")
    print(f"  Residue ch:    L* = {l_star_res}")
    print(f"  Magnitude ch:  L* = {l_star_mag}")

    # === 6. Cross-channel independence test ===
    print("\n=== CROSS-CHANNEL INDEPENDENCE ===")
    # Are residue and magnitude channels correlated?
    cross_corr = np.corrcoef(res_ch[:len(mag_ch)], mag_ch[:len(res_ch)])[0, 1]
    print(f"  Pearson(residue, magnitude) = {cross_corr:.6f}")

    # Does knowing residue help predict magnitude?
    for trans_type in [11, 15, 51, 55]:
        mask = trans == trans_type
        if mask.sum() > 100:
            # ACF1 of magnitude channel within this transition type
            mc = mag_ch[mask]
            if len(mc) > 50:
                mc_acf1 = acf(mc, 2)[1]
                print(f"  Magnitude acf1 within {trans_type//10}->{trans_type%10}: {mc_acf1:.6f} (n={mask.sum():,})")

    # === 7. Additivity test ===
    print("\n=== ADDITIVITY TEST ===")
    print("  Does acf1_full ≈ f(acf1_res, acf1_mag)?")
    # If channels are independent and gaps = mean(transition) + magnitude_residual,
    # the full ACF should decompose
    # Compute: variance from residue transitions vs magnitude
    var_full = np.var(gaps)

    # Variance from transitions: mean gap differs by transition type
    trans_means = {}
    for tt in [11, 15, 51, 55]:
        mask = trans == tt
        if mask.sum() > 0:
            trans_means[tt] = gaps[mask].mean()

    gap_trans_component = np.array([trans_means[t] for t in trans])
    var_trans = np.var(gap_trans_component)
    var_mag = np.var(mag_ch)

    print(f"  Var(full) = {var_full:.2f}")
    print(f"  Var(transition means) = {var_trans:.2f} ({100*var_trans/var_full:.1f}%)")
    print(f"  Var(magnitude residual) = {var_mag:.2f} ({100*var_mag/var_full:.1f}%)")
    print(f"  Sum = {var_trans + var_mag:.2f} ({100*(var_trans+var_mag)/var_full:.1f}%)")

    # === Save results ===
    output = {
        'experiment': 'two_channel_decomposition',
        'n_primes': len(primes),
        'global': {
            'acf1_full': float(acf1_full),
            'acf1_res': float(acf1_res),
            'acf1_mag': float(acf1_mag),
            'ratio_res_full': float(abs(acf1_res / acf1_full)),
            'ratio_mag_full': float(abs(acf1_mag / acf1_full)),
            'cross_correlation': float(cross_corr),
            'var_full': float(var_full),
            'var_transition': float(var_trans),
            'var_magnitude': float(var_mag),
        },
        'coherence': {
            'L_star_full': l_star_full,
            'L_star_residue': l_star_res,
            'L_star_magnitude': l_star_mag,
        },
        'scaling': scaling,
    }

    out_path = Path(__file__).parent / 'data' / 'exp_two_channel_decomposition.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    return output

if __name__ == '__main__':
    main()
