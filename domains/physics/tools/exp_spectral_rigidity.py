#!/usr/bin/env python3
"""
Spectral Rigidity (Number Variance) Across All Domains

Tests META + BOUNDARY with an observable independent from the r-statistic:
  Sigma^2(L) = Var[N(x, x+L)]  (number of levels in window of size L)

Theory:
  GUE:     Sigma^2(L) ~ (2/pi^2) ln(L) + const   [log-log slope ~ 0]
  Poisson: Sigma^2(L) = L                         [log-log slope = 1]

The ratio Sigma^2(L)/L at L=10 discriminates:
  << 1 -> GUE (strong repulsion, rigid spectrum)
  ~  1 -> Poisson (no correlations)

Null: shuffle gaps (same marginal distribution, destroyed ordering).

Domains: primes, GUE matrices, coupled_osc, string_vib, percolation,
         logistic, brownian, pure Poisson.
"""

import numpy as np
import sys
import json
from collections import OrderedDict

sys.path.insert(0, '/opt/MM_D-ND/tools')
from dnd_autoricerca import genera_segnale


def gaps_from_domain(dominio):
    """Generate gaps from domain. Returns positive spacings."""
    signal, meta = genera_segnale(dominio)
    sig = np.array(signal, dtype=float)
    if dominio == 'numeri_primi':
        return sig[sig > 0]
    vals = np.sort(sig)
    g = np.diff(vals)
    return g[g > 0]


def generate_poisson_gaps(n=10000):
    return np.random.exponential(1.0, size=n)


def generate_gue_gaps(n=600):
    """GUE Hermitian matrix eigenvalue spacings, bulk only."""
    H = np.random.randn(n, n) + 1j * np.random.randn(n, n)
    H = (H + H.conj().T) / 2.0
    eigs = np.sort(np.linalg.eigvalsh(H))
    lo, hi = int(0.2 * n), int(0.8 * n)
    g = np.diff(eigs[lo:hi])
    return g[g > 0]


def number_variance(levels, L_values, n_starts=3000):
    """
    Sigma^2(L) from level positions (cumsum of unfolded gaps).
    levels must be sorted and have mean spacing ~1.
    """
    total = levels[-1] - levels[0]
    sigma2 = np.full(len(L_values), np.nan)

    for i, L in enumerate(L_values):
        if L >= total * 0.4:
            continue
        max_start = levels[-1] - L
        min_start = levels[0]
        starts = np.random.uniform(min_start, max_start, size=n_starts)
        counts = np.empty(n_starts)
        for j, a in enumerate(starts):
            counts[j] = np.searchsorted(levels, a + L, side='right') - \
                        np.searchsorted(levels, a, side='left')
        sigma2[i] = np.var(counts)
    return sigma2


def run():
    np.random.seed(137)

    L_values = np.array([1, 2, 3, 5, 8, 10, 15, 20, 30, 50], dtype=float)
    n_shuffle = 30

    domains = OrderedDict([
        ('primes',      {'gen': lambda: gaps_from_domain('numeri_primi'),      'type': 'dist-GUE'}),
        ('gue_matrix',  {'gen': lambda: generate_gue_gaps(600),               'type': 'dist-GUE'}),
        ('coupled_osc', {'gen': lambda: gaps_from_domain('coupled_oscillators'), 'type': 'ord-GUE'}),
        ('string_vib',  {'gen': lambda: gaps_from_domain('string_vibration'),  'type': 'ord-GUE'}),
        ('percolation', {'gen': lambda: gaps_from_domain('percolation'),       'type': 'ord-GUE'}),
        ('logistic',    {'gen': lambda: gaps_from_domain('logistica_biforcazione'), 'type': 'Poisson'}),
        ('brownian',    {'gen': lambda: gaps_from_domain('brownian_motion'),   'type': 'Poisson'}),
        ('poisson',     {'gen': lambda: generate_poisson_gaps(10000),          'type': 'Poisson'}),
    ])

    results = {}
    gue_theory = (2.0 / np.pi**2) * np.log(L_values) + 0.44

    for name, cfg in domains.items():
        print(f"\n=== {name} ({cfg['type']}) ===")
        try:
            gaps = cfg['gen']()
        except Exception as e:
            print(f"  ERROR: {e}")
            results[name] = {'error': str(e)}
            continue

        n = len(gaps)
        print(f"  N={n}, mean={np.mean(gaps):.4f}")
        if n < 80:
            print("  SKIP: too few")
            results[name] = {'error': 'too_few', 'n': n}
            continue

        # Unfold to mean spacing = 1
        unfolded = gaps / np.mean(gaps)
        levels = np.concatenate([[0], np.cumsum(unfolded)])

        sig2_real = number_variance(levels, L_values)

        # Shuffle baseline
        sig2_shuf_all = np.zeros((n_shuffle, len(L_values)))
        for s in range(n_shuffle):
            g_s = unfolded.copy()
            np.random.shuffle(g_s)
            lev_s = np.concatenate([[0], np.cumsum(g_s)])
            sig2_shuf_all[s] = number_variance(lev_s, L_values, n_starts=800)

        sig2_shuf_mean = np.nanmean(sig2_shuf_all, axis=0)
        sig2_shuf_std = np.nanstd(sig2_shuf_all, axis=0)

        # Key metrics at L=10
        idx10 = np.argmin(np.abs(L_values - 10))
        rig_real = sig2_real[idx10] / L_values[idx10] if not np.isnan(sig2_real[idx10]) else np.nan
        rig_shuf = sig2_shuf_mean[idx10] / L_values[idx10] if not np.isnan(sig2_shuf_mean[idx10]) else np.nan

        # z-score real vs shuffle at L=10
        if sig2_shuf_std[idx10] > 0:
            z10 = (sig2_real[idx10] - sig2_shuf_mean[idx10]) / sig2_shuf_std[idx10]
        else:
            z10 = 0.0

        # Log-log slope of Sigma^2 vs L in range [2, 30]
        mask = (L_values >= 2) & (L_values <= 30) & ~np.isnan(sig2_real) & (sig2_real > 0)
        if np.sum(mask) >= 3:
            slope, intercept = np.polyfit(np.log(L_values[mask]), np.log(sig2_real[mask]), 1)
        else:
            slope = np.nan

        mask_s = (L_values >= 2) & (L_values <= 30) & ~np.isnan(sig2_shuf_mean) & (sig2_shuf_mean > 0)
        if np.sum(mask_s) >= 3:
            slope_s, _ = np.polyfit(np.log(L_values[mask_s]), np.log(sig2_shuf_mean[mask_s]), 1)
        else:
            slope_s = np.nan

        print(f"  Sig2/L@10: real={rig_real:.4f}, shuf={rig_shuf:.4f}")
        print(f"  Slope (log-log): real={slope:.3f}, shuf={slope_s:.3f}  [GUE~0, Poisson=1]")
        print(f"  z(real vs shuf)@L=10: {z10:.1f}")

        results[name] = {
            'type': cfg['type'],
            'n': int(n),
            'sig2_real': [float(x) if not np.isnan(x) else None for x in sig2_real],
            'sig2_shuf_mean': [float(x) if not np.isnan(x) else None for x in sig2_shuf_mean],
            'sig2_gue_theory': gue_theory.tolist(),
            'rigidity_L10_real': float(rig_real) if not np.isnan(rig_real) else None,
            'rigidity_L10_shuf': float(rig_shuf) if not np.isnan(rig_shuf) else None,
            'z_vs_shuf_L10': float(z10),
            'slope_real': float(slope) if not np.isnan(slope) else None,
            'slope_shuf': float(slope_s) if not np.isnan(slope_s) else None,
        }

    # Summary table
    print("\n" + "=" * 95)
    print(f"{'Domain':<14} {'Type':<10} {'N':>6} {'Sig2/L@10':>10} {'Slope':>7} {'Shuf/L@10':>10} {'Shuf_Sl':>8} {'z':>7} {'Match?':>8}")
    print("-" * 95)
    for name, r in results.items():
        if 'error' in r:
            continue
        rig = r['rigidity_L10_real']
        sl = r['slope_real']
        rig_s = r['rigidity_L10_shuf']
        sl_s = r['slope_shuf']
        z = r['z_vs_shuf_L10']
        ty = r['type']

        # Does Sigma^2 agree with prior classification?
        if rig is not None and sl is not None:
            if ty in ('dist-GUE', 'ord-GUE'):
                match = "YES" if rig < 0.5 else "NO"
            else:
                match = "YES" if rig > 0.5 else "NO"
        else:
            match = "?"

        rig_f = f"{rig:.4f}" if rig is not None else "N/A"
        sl_f = f"{sl:.3f}" if sl is not None else "N/A"
        rig_sf = f"{rig_s:.4f}" if rig_s is not None else "N/A"
        sl_sf = f"{sl_s:.3f}" if sl_s is not None else "N/A"
        print(f"{name:<14} {ty:<10} {r['n']:>6} {rig_f:>10} {sl_f:>7} {rig_sf:>10} {sl_sf:>8} {z:>7.1f} {match:>8}")
    print("=" * 95)

    # Which domains have ordering-dependent rigidity?
    print("\n--- ORDERING EFFECT on spectral rigidity ---")
    for name, r in results.items():
        if 'error' in r or r['rigidity_L10_real'] is None:
            continue
        rig_r = r['rigidity_L10_real']
        rig_s = r['rigidity_L10_shuf']
        delta = rig_s - rig_r if rig_s is not None else 0
        pct = 100 * delta / rig_s if rig_s and rig_s > 0 else 0
        z = r['z_vs_shuf_L10']
        if abs(z) > 3:
            print(f"  {name}: shuffle changes Sig2/L by {delta:+.4f} ({pct:+.1f}%), z={z:.1f} -> ORDERING MATTERS")
        else:
            print(f"  {name}: shuffle effect {delta:+.4f} ({pct:+.1f}%), z={z:.1f} -> ordering negligible")

    return results


if __name__ == '__main__':
    results = run()

    out = '/opt/MM_D-ND/tools/data/spectral_rigidity_results.json'
    with open(out, 'w') as f:
        json.dump({
            'timestamp': '2026-04-26',
            'experiment': 'spectral_rigidity_cross_domain',
            'L_values': [1, 2, 3, 5, 8, 10, 15, 20, 30, 50],
            'results': results,
        }, f, indent=2)
    print(f"\nSaved to {out}")
