"""
exp_dipole_classifier.py — Classifica le proprieta di una sequenza ordinata
in dipoli REALI (det=-1, distrutti dallo shuffle) vs ILLUSORI (det=+1, preservati).

Strumento riusabile: funziona su qualsiasi sequenza ordinata di interi.
Uso: python exp_dipole_classifier.py [--N 1000000] [--n_shuffle 200]
"""

import numpy as np
from sympy import primerange
import argparse
from collections import Counter

def generate_prime_gaps(N):
    """Genera la sequenza di gap tra primi fino a N."""
    primes = list(primerange(2, N))
    gaps = np.diff(primes).astype(float)
    return gaps, primes

def autocorrelation(x, lag):
    """Autocorrelazione normalizzata a lag dato."""
    n = len(x)
    if lag >= n:
        return 0.0
    xm = x - np.mean(x)
    c0 = np.sum(xm**2)
    if c0 == 0:
        return 0.0
    cl = np.sum(xm[:n-lag] * xm[lag:])
    return cl / c0

def r_statistic(x):
    """Rapporto tra spacing consecutivi (media di min/max)."""
    n = len(x)
    ratios = np.minimum(x[:n-1], x[1:]) / np.maximum(x[:n-1], x[1:])
    # Evita divisione per zero
    valid = np.isfinite(ratios)
    return np.mean(ratios[valid])

def run_lengths(x):
    """Statistiche sulle run (sequenze monotone crescenti/decrescenti)."""
    diffs = np.diff(x)
    signs = np.sign(diffs)
    # Rimuovi zeri (gap uguali) — tratta come continuazione
    signs[signs == 0] = 1
    # Conta cambio di segno
    changes = np.sum(signs[:-1] != signs[1:])
    n_runs = changes + 1
    # Run medio
    mean_run = len(signs) / n_runs if n_runs > 0 else len(signs)
    return n_runs, mean_run

def turning_points_fraction(x):
    """Frazione di turning points (minimi/massimi locali)."""
    n = len(x)
    if n < 3:
        return 0.0
    tp = 0
    for i in range(1, n-1):
        if (x[i] > x[i-1] and x[i] > x[i+1]) or (x[i] < x[i-1] and x[i] < x[i+1]):
            tp += 1
    return tp / (n - 2)

def psd_slope(x, f_range=(0.01, 0.1)):
    """Slope del PSD nel range di frequenze dato (log-log)."""
    n = len(x)
    xm = x - np.mean(x)
    ft = np.fft.rfft(xm)
    psd = np.abs(ft)**2 / n
    freqs = np.fft.rfftfreq(n)
    # Seleziona range
    mask = (freqs >= f_range[0]) & (freqs <= f_range[1])
    if np.sum(mask) < 5:
        return 0.0, 0.0
    log_f = np.log10(freqs[mask])
    log_p = np.log10(psd[mask] + 1e-30)
    # Fit lineare
    coeffs = np.polyfit(log_f, log_p, 1)
    return coeffs[0], coeffs[1]  # slope, intercept

def mutual_info_binned(x, y, n_bins=20):
    """Mutual information stimata via binning."""
    # Bin entrambe le variabili
    x_bins = np.digitize(x, np.linspace(np.min(x), np.max(x)+1e-10, n_bins+1))
    y_bins = np.digitize(y, np.linspace(np.min(y), np.max(y)+1e-10, n_bins+1))
    n = len(x)
    # Joint probability
    joint = Counter(zip(x_bins, y_bins))
    px = Counter(x_bins)
    py = Counter(y_bins)
    mi = 0.0
    for (xi, yi), nxy in joint.items():
        pxy = nxy / n
        pxi = px[xi] / n
        pyi = py[yi] / n
        if pxy > 0 and pxi > 0 and pyi > 0:
            mi += pxy * np.log2(pxy / (pxi * pyi))
    return mi

def compute_all_statistics(gaps):
    """Calcola tutte le statistiche sulla sequenza di gap."""
    stats = {}

    # Autocorrelazioni
    for lag in [1, 2, 3, 5, 10, 50]:
        stats[f'autocorr_lag{lag}'] = autocorrelation(gaps, lag)

    # r-statistic
    stats['r_statistic'] = r_statistic(gaps)

    # Run statistics
    n_runs, mean_run = run_lengths(gaps)
    stats['n_runs'] = n_runs
    stats['mean_run_length'] = mean_run

    # Turning points
    stats['turning_points_frac'] = turning_points_fraction(gaps)

    # PSD slope
    slope, _ = psd_slope(gaps)
    stats['psd_slope'] = slope

    # Mutual information gap(n) vs gap(n+1)
    stats['MI_lag1'] = mutual_info_binned(gaps[:-1], gaps[1:])

    # Mutual information gap(n) vs gap(n+2)
    stats['MI_lag2'] = mutual_info_binned(gaps[:-2], gaps[2:])

    # Varianza dei rapporti consecutivi
    ratios = gaps[1:] / np.maximum(gaps[:-1], 1e-10)
    stats['ratio_variance'] = np.var(ratios[np.isfinite(ratios)])

    # Gap pair asymmetry: P(g_{n+1} > g_n) - 0.5
    stats['pair_asymmetry'] = np.mean(gaps[1:] > gaps[:-1]) - 0.5

    # Third-order: P(g_{n+2} > g_{n+1} > g_n)
    mono_up = np.mean((gaps[2:] > gaps[1:-1]) & (gaps[1:-1] > gaps[:-2]))
    stats['monotone_triple_frac'] = mono_up

    return stats

def classify_dipoles(real_stats, shuffle_stats_list, alpha=3.0):
    """
    Classifica ogni statistica come det=-1 (reale) o det=+1 (illusoria).

    det=-1: lo shuffle distrugge il valore (|z| > alpha)
    det=+1: lo shuffle preserva il valore (|z| <= alpha)
    """
    results = {}
    for key in real_stats:
        real_val = real_stats[key]
        shuf_vals = [s[key] for s in shuffle_stats_list]
        shuf_mean = np.mean(shuf_vals)
        shuf_std = np.std(shuf_vals)
        if shuf_std < 1e-15:
            z = 0.0
        else:
            z = (real_val - shuf_mean) / shuf_std

        det = -1 if abs(z) > alpha else 1
        results[key] = {
            'real': real_val,
            'shuffle_mean': shuf_mean,
            'shuffle_std': shuf_std,
            'z_score': z,
            'det': det,
            'label': 'REALE (det=-1)' if det == -1 else 'ILLUSORIO (det=+1)'
        }
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=2_000_000, help='Primi fino a N')
    parser.add_argument('--n_shuffle', type=int, default=200, help='Numero di shuffle')
    args = parser.parse_args()

    print(f"Generating primes up to {args.N}...")
    gaps, primes = generate_prime_gaps(args.N)
    print(f"  {len(primes)} primes, {len(gaps)} gaps")
    print(f"  Mean gap: {np.mean(gaps):.3f}, Std: {np.std(gaps):.3f}")

    print("\nComputing statistics on real sequence...")
    real_stats = compute_all_statistics(gaps)

    print(f"Running {args.n_shuffle} shuffles...")
    rng = np.random.default_rng(42)
    shuffle_stats = []
    for i in range(args.n_shuffle):
        shuffled = gaps.copy()
        rng.shuffle(shuffled)
        shuffle_stats.append(compute_all_statistics(shuffled))
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{args.n_shuffle} done")

    print("\nClassifying dipoles...")
    results = classify_dipoles(real_stats, shuffle_stats)

    # Print results
    print("\n" + "="*90)
    print(f"{'Statistic':<25} {'Real':>12} {'Shuf mean':>12} {'Shuf std':>10} {'z-score':>10} {'Class':>20}")
    print("="*90)

    det_minus = []
    det_plus = []
    for key in sorted(results.keys()):
        r = results[key]
        print(f"{key:<25} {r['real']:>12.6f} {r['shuffle_mean']:>12.6f} {r['shuffle_std']:>10.6f} {r['z_score']:>10.2f} {r['label']:>20}")
        if r['det'] == -1:
            det_minus.append(key)
        else:
            det_plus.append(key)

    print("\n" + "="*90)
    print(f"\ndet=-1 (REALI — ordine distrutto dallo shuffle): {len(det_minus)}")
    for k in det_minus:
        print(f"  - {k} (z={results[k]['z_score']:.1f})")

    print(f"\ndet=+1 (ILLUSORI — preservati dallo shuffle): {len(det_plus)}")
    for k in det_plus:
        print(f"  - {k} (z={results[k]['z_score']:.1f})")

    return results, real_stats, gaps

if __name__ == '__main__':
    results, real_stats, gaps = main()
