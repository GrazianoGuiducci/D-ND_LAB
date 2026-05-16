#!/usr/bin/env python3
"""
exp_dipolar_angle_reference.py — Dipolar angle of GUE, Poisson, and primes

Measures the two order-sensitive observables (spacing_ratio, lag1_acf) for:
1. Pure GUE eigenvalue spacings (GOE/GUE unfolded)
2. Pure Poisson (exponential iid)
3. Cramer random primes (same density, no correlations)
4. Real primes

Computes the dipolar angle theta = atan2(delta_lag1, delta_spacing_ratio)
relative to shuffle baseline. This answers: is the prime angle (-150 deg)
unique or just a position on the GUE-Poisson continuum?

Usage:
    python tools/exp_dipolar_angle_reference.py [--N 100000] [--n_trials 50]
"""

import argparse
import numpy as np
from numpy.linalg import eigvalsh


def get_primes(n_max):
    """Sieve of Eratosthenes up to n_max."""
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def spacing_ratio(gaps):
    """Mean ratio of consecutive gaps: min(g_i, g_{i+1}) / max(g_i, g_{i+1})."""
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r[np.isfinite(r)])


def lag1_acf(gaps):
    """Lag-1 autocorrelation of gaps."""
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0:
        return 0.0
    c1 = np.mean(g[:-1] * g[1:])
    return c1 / c0


def compute_observables(gaps):
    """Return (spacing_ratio, lag1_acf) for a gap sequence."""
    return spacing_ratio(gaps), lag1_acf(gaps)


def shuffle_baseline(gaps, n_shuffle=200):
    """Shuffle gaps, compute mean observables."""
    sr_list, l1_list = [], []
    for _ in range(n_shuffle):
        sg = np.random.permutation(gaps)
        sr, l1 = compute_observables(sg)
        sr_list.append(sr)
        l1_list.append(l1)
    return np.mean(sr_list), np.mean(l1_list)


def dipolar_angle(gaps, n_shuffle=200):
    """
    Compute dipolar angle: direction of (delta_SR, delta_L1) relative to shuffle.
    Returns: theta (degrees), delta_SR, delta_L1, SR_real, L1_real, SR_shuf, L1_shuf
    """
    sr_real, l1_real = compute_observables(gaps)
    sr_shuf, l1_shuf = shuffle_baseline(gaps, n_shuffle)
    delta_sr = sr_real - sr_shuf
    delta_l1 = l1_real - l1_shuf
    theta = np.degrees(np.arctan2(delta_l1, delta_sr))
    return theta, delta_sr, delta_l1, sr_real, l1_real, sr_shuf, l1_shuf


def generate_gue_gaps(n_gaps, matrix_size=500):
    """Generate gaps from GUE eigenvalues (unfolded)."""
    all_gaps = []
    while len(all_gaps) < n_gaps:
        # GUE: complex Hermitian random matrix
        A = (np.random.randn(matrix_size, matrix_size) +
             1j * np.random.randn(matrix_size, matrix_size)) / np.sqrt(2 * matrix_size)
        H = (A + A.conj().T) / 2
        eigs = np.sort(eigvalsh(H))
        # Unfold: use local spacing
        spacings = np.diff(eigs)
        # Normalize by local mean (window)
        window = 20
        for i in range(window, len(spacings) - window):
            local_mean = np.mean(spacings[max(0, i-window):i+window])
            if local_mean > 0:
                all_gaps.append(spacings[i] / local_mean)
    return np.array(all_gaps[:n_gaps])


def generate_goe_gaps(n_gaps, matrix_size=500):
    """Generate gaps from GOE eigenvalues (unfolded)."""
    all_gaps = []
    while len(all_gaps) < n_gaps:
        A = np.random.randn(matrix_size, matrix_size) / np.sqrt(matrix_size)
        H = (A + A.T) / 2
        eigs = np.sort(eigvalsh(H))
        spacings = np.diff(eigs)
        window = 20
        for i in range(window, len(spacings) - window):
            local_mean = np.mean(spacings[max(0, i-window):i+window])
            if local_mean > 0:
                all_gaps.append(spacings[i] / local_mean)
    return np.array(all_gaps[:n_gaps])


def generate_poisson_gaps(n_gaps):
    """Generate iid exponential gaps (Poisson process)."""
    return np.random.exponential(1.0, n_gaps)


def generate_cramer_gaps(primes):
    """Generate Cramer random model: same local density as primes, no correlations."""
    gaps = np.diff(primes).astype(float)
    n = len(gaps)
    # For each prime p_n, generate gap from geometric with mean ~ ln(p_n)
    cramer_gaps = []
    for i in range(n):
        mean_gap = np.log(primes[i+1]) if primes[i+1] > 2 else 1.0
        g = np.random.exponential(mean_gap)
        cramer_gaps.append(max(1.0, round(g)))  # integer gaps >= 1
    return np.array(cramer_gaps)


def run_experiment(N=50000, n_trials=30):
    """Run the full experiment."""
    results = {}

    # 1. Real primes
    print(f"Computing primes up to ~{N*20}...")
    primes = get_primes(N * 20)
    # Use primes in the range [1e4, ...] to avoid small-prime effects
    mask = primes > 10000
    primes_filtered = primes[mask][:N]
    prime_gaps = np.diff(primes_filtered).astype(float)

    print(f"  Using {len(prime_gaps)} prime gaps (p > 10000)")
    theta_p, dsr_p, dl1_p, sr_p, l1_p, sr_ps, l1_ps = dipolar_angle(prime_gaps)
    results['primes'] = {
        'theta': theta_p, 'delta_SR': dsr_p, 'delta_L1': dl1_p,
        'SR': sr_p, 'L1': l1_p, 'SR_shuf': sr_ps, 'L1_shuf': l1_ps
    }
    print(f"  Primes: theta = {theta_p:.1f} deg, dSR = {dsr_p:.4f}, dL1 = {dl1_p:.4f}")

    # 2. GUE
    print(f"Generating GUE gaps (n_trials={n_trials})...")
    gue_thetas = []
    gue_data = []
    for t in range(n_trials):
        gue_gaps = generate_gue_gaps(len(prime_gaps))
        theta, dsr, dl1, sr, l1, srs, l1s = dipolar_angle(gue_gaps, n_shuffle=50)
        gue_thetas.append(theta)
        gue_data.append((theta, dsr, dl1, sr, l1))
        if (t+1) % 10 == 0:
            print(f"  GUE trial {t+1}/{n_trials}: theta = {theta:.1f}")
    gue_thetas = np.array(gue_thetas)
    results['GUE'] = {
        'theta_mean': np.mean(gue_thetas), 'theta_std': np.std(gue_thetas),
        'thetas': gue_thetas.tolist(),
        'SR_mean': np.mean([d[3] for d in gue_data]),
        'L1_mean': np.mean([d[4] for d in gue_data]),
    }
    print(f"  GUE: theta = {np.mean(gue_thetas):.1f} +/- {np.std(gue_thetas):.1f} deg")

    # 3. GOE
    print(f"Generating GOE gaps (n_trials={n_trials})...")
    goe_thetas = []
    goe_data = []
    for t in range(n_trials):
        goe_gaps = generate_goe_gaps(len(prime_gaps))
        theta, dsr, dl1, sr, l1, srs, l1s = dipolar_angle(goe_gaps, n_shuffle=50)
        goe_thetas.append(theta)
        goe_data.append((theta, dsr, dl1, sr, l1))
        if (t+1) % 10 == 0:
            print(f"  GOE trial {t+1}/{n_trials}: theta = {theta:.1f}")
    goe_thetas = np.array(goe_thetas)
    results['GOE'] = {
        'theta_mean': np.mean(goe_thetas), 'theta_std': np.std(goe_thetas),
        'thetas': goe_thetas.tolist(),
        'SR_mean': np.mean([d[3] for d in goe_data]),
        'L1_mean': np.mean([d[4] for d in goe_data]),
    }
    print(f"  GOE: theta = {np.mean(goe_thetas):.1f} +/- {np.std(goe_thetas):.1f} deg")

    # 4. Poisson
    print(f"Generating Poisson gaps (n_trials={n_trials})...")
    poi_thetas = []
    poi_data = []
    for t in range(n_trials):
        poi_gaps = generate_poisson_gaps(len(prime_gaps))
        theta, dsr, dl1, sr, l1, srs, l1s = dipolar_angle(poi_gaps, n_shuffle=50)
        poi_thetas.append(theta)
        poi_data.append((theta, dsr, dl1, sr, l1))
        if (t+1) % 10 == 0:
            print(f"  Poisson trial {t+1}/{n_trials}: theta = {theta:.1f}")
    poi_thetas = np.array(poi_thetas)
    results['Poisson'] = {
        'theta_mean': np.mean(poi_thetas), 'theta_std': np.std(poi_thetas),
        'thetas': poi_thetas.tolist(),
        'SR_mean': np.mean([d[3] for d in poi_data]),
        'L1_mean': np.mean([d[4] for d in poi_data]),
    }
    print(f"  Poisson: theta = {np.mean(poi_thetas):.1f} +/- {np.std(poi_thetas):.1f} deg")

    # 5. Cramer random primes
    print(f"Generating Cramer gaps (n_trials={n_trials})...")
    cramer_thetas = []
    cramer_data = []
    for t in range(n_trials):
        cramer_gaps = generate_cramer_gaps(primes_filtered)
        theta, dsr, dl1, sr, l1, srs, l1s = dipolar_angle(cramer_gaps, n_shuffle=50)
        cramer_thetas.append(theta)
        cramer_data.append((theta, dsr, dl1, sr, l1))
        if (t+1) % 10 == 0:
            print(f"  Cramer trial {t+1}/{n_trials}: theta = {theta:.1f}")
    cramer_thetas = np.array(cramer_thetas)
    results['Cramer'] = {
        'theta_mean': np.mean(cramer_thetas), 'theta_std': np.std(cramer_thetas),
        'thetas': cramer_thetas.tolist(),
        'SR_mean': np.mean([d[3] for d in cramer_data]),
        'L1_mean': np.mean([d[4] for d in cramer_data]),
    }
    print(f"  Cramer: theta = {np.mean(cramer_thetas):.1f} +/- {np.std(cramer_thetas):.1f} deg")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY — Dipolar Angle Reference Frame")
    print("="*70)
    print(f"{'Source':<12} {'theta (deg)':<18} {'SR_raw':<10} {'L1_raw':<10}")
    print("-"*50)
    print(f"{'Primes':<12} {results['primes']['theta']:>7.1f}{'':>11} {results['primes']['SR']:<10.4f} {results['primes']['L1']:<10.4f}")
    print(f"{'GUE':<12} {results['GUE']['theta_mean']:>7.1f} +/- {results['GUE']['theta_std']:>5.1f}  {results['GUE']['SR_mean']:<10.4f} {results['GUE']['L1_mean']:<10.4f}")
    print(f"{'GOE':<12} {results['GOE']['theta_mean']:>7.1f} +/- {results['GOE']['theta_std']:>5.1f}  {results['GOE']['SR_mean']:<10.4f} {results['GOE']['L1_mean']:<10.4f}")
    print(f"{'Poisson':<12} {results['Poisson']['theta_mean']:>7.1f} +/- {results['Poisson']['theta_std']:>5.1f}  {results['Poisson']['SR_mean']:<10.4f} {results['Poisson']['L1_mean']:<10.4f}")
    print(f"{'Cramer':<12} {results['Cramer']['theta_mean']:>7.1f} +/- {results['Cramer']['theta_std']:>5.1f}  {results['Cramer']['SR_mean']:<10.4f} {results['Cramer']['L1_mean']:<10.4f}")

    # Angular separation
    print("\nAngular separation from primes:")
    for name in ['GUE', 'GOE', 'Poisson', 'Cramer']:
        sep = results['primes']['theta'] - results[name]['theta_mean']
        # Normalize to [-180, 180]
        while sep > 180: sep -= 360
        while sep < -180: sep += 360
        z = abs(sep) / max(results[name]['theta_std'], 0.1)
        print(f"  {name:<12}: {sep:>7.1f} deg  (z = {z:.1f})")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=50000, help='Number of gaps')
    parser.add_argument('--n_trials', type=int, default=30, help='Trials per source')
    args = parser.parse_args()

    np.random.seed(42)
    results = run_experiment(N=args.N, n_trials=args.n_trials)
