"""
exp_boundary_shuffle_audit.py — Is the GUE/Poisson classification tautological?

Question: Does the r-statistic (nearest-neighbor spacing ratio) of each domain
depend on sequential correlations between gaps, or only on the gap distribution?

Method:
  For each domain, compute:
    1. r_original = mean(min(g_i, g_{i+1}) / max(g_i, g_{i+1})) on actual gap sequence
    2. r_shuffled = same, on 2000 random permutations of the gap sequence
    3. z = (r_original - mean(r_shuffled)) / std(r_shuffled)

  If |z| > 3: classification depends on ordering (non-trivial)
  If |z| < 3: classification is a property of the distribution alone (tautological)

Domains: primes, zeta zeros, random matrix (GUE), Fibonacci spectrum,
         logistic map, Poisson, coupled oscillators, percolation,
         Ising 2D, cellular automata, Brownian motion, reaction-diffusion,
         pendulum.

Author: AI-Lab D-ND
Date: 2026-04-24
"""

import numpy as np
from scipy import linalg
import json
import sys
from pathlib import Path
from datetime import datetime

PHI = (1 + np.sqrt(5)) / 2
N_SHUFFLE = 2000
rng = np.random.default_rng(42)


def r_statistic(gaps):
    """Mean ratio of consecutive gap pairs: min/max."""
    if len(gaps) < 2:
        return np.nan
    ratios = []
    for i in range(len(gaps) - 1):
        a, b = gaps[i], gaps[i + 1]
        if max(a, b) > 0:
            ratios.append(min(a, b) / max(a, b))
    return np.mean(ratios) if ratios else np.nan


def shuffle_test(gaps, n_shuffle=N_SHUFFLE):
    """Shuffle gap sequence, recompute r each time. Return z-score."""
    r_orig = r_statistic(gaps)
    r_shuf = []
    for _ in range(n_shuffle):
        perm = rng.permutation(gaps)
        r_shuf.append(r_statistic(perm))
    r_shuf = np.array(r_shuf)
    mu, sigma = np.mean(r_shuf), np.std(r_shuf)
    z = (r_orig - mu) / sigma if sigma > 1e-12 else 0.0
    return {
        'r_original': float(r_orig),
        'r_shuffled_mean': float(mu),
        'r_shuffled_std': float(sigma),
        'z_score': float(z),
        'n_shuffle': n_shuffle,
    }


# === Domain generators ===

def gen_primes(n=100000):
    """Sieve of Eratosthenes, return gaps."""
    limit = int(n * np.log(n) * 1.3) + 100
    sieve = np.ones(limit, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    primes = np.where(sieve)[0][:n]
    return np.diff(primes).astype(float)


def gen_gue_eigenvalues(size=2000, n_matrices=50):
    """GUE random matrices — eigenvalue spacings."""
    all_spacings = []
    for _ in range(n_matrices):
        H = rng.standard_normal((size, size)) + 1j * rng.standard_normal((size, size))
        H = (H + H.conj().T) / 2
        eigs = np.sort(linalg.eigvalsh(H))
        # Unfold: local mean spacing = 1
        spacings = np.diff(eigs)
        mid = len(spacings) // 4
        core = spacings[mid:-mid]  # central half to avoid edge effects
        if len(core) > 10:
            core = core / np.mean(core)
            all_spacings.extend(core.tolist())
    return np.array(all_spacings)


def gen_poisson(n=100000):
    """Poisson process — exponential spacings."""
    return rng.exponential(1.0, size=n)


def gen_logistic(n=100000, r_param=3.99):
    """Logistic map in chaotic regime — gaps between sorted iterates."""
    x = np.empty(n + 1000)
    x[0] = 0.1
    for i in range(1, len(x)):
        x[i] = r_param * x[i-1] * (1 - x[i-1])
    x = x[1000:]  # discard transient
    x_sorted = np.sort(x)
    return np.diff(x_sorted)


def gen_fibonacci_spectrum(size=610):
    """Fibonacci tight-binding model, V=1 (critical point)."""
    n = size
    pot = np.array([1.0 if int((k + 1) / PHI) - int(k / PHI) else 0.0 for k in range(n)])
    H = np.diag(pot)
    for i in range(n - 1):
        H[i, i+1] = H[i+1, i] = 1.0
    eigs = np.sort(linalg.eigvalsh(H))
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 1e-12]
    return spacings / np.mean(spacings)


def gen_ising_2d(L=64, T=2.269, steps=50000):
    """2D Ising model near T_c — energy gaps between consecutive states."""
    grid = rng.choice([-1, 1], size=(L, L))
    energies = []
    for step in range(steps + 5000):
        i, j = rng.integers(0, L, size=2)
        s = grid[i, j]
        nn = (grid[(i+1) % L, j] + grid[(i-1) % L, j] +
              grid[i, (j+1) % L] + grid[i, (j-1) % L])
        dE = 2 * s * nn
        if dE <= 0 or rng.random() < np.exp(-dE / T):
            grid[i, j] = -s
        if step >= 5000 and step % 5 == 0:
            E = 0
            for ii in range(L):
                for jj in range(L):
                    E -= grid[ii, jj] * (grid[(ii+1) % L, jj] + grid[ii, (jj+1) % L])
            energies.append(E)
    energies = np.array(energies, dtype=float)
    e_sorted = np.sort(np.unique(energies))
    gaps = np.diff(e_sorted).astype(float)
    gaps = gaps[gaps > 0]
    return gaps / np.mean(gaps) if len(gaps) > 10 else gaps


def gen_percolation(L=200, p=0.5927, n_samples=200):
    """Site percolation near p_c — cluster size gaps."""
    from scipy.ndimage import label as ndlabel
    all_sizes = []
    for _ in range(n_samples):
        grid = (rng.random((L, L)) < p).astype(int)
        labeled, n_clusters = ndlabel(grid)
        if n_clusters > 0:
            sizes = np.bincount(labeled.ravel())[1:]  # skip background
            all_sizes.extend(sizes.tolist())
    sizes_sorted = np.sort(all_sizes).astype(float)
    gaps = np.diff(sizes_sorted)
    gaps = gaps[gaps > 0]
    return gaps / np.mean(gaps) if len(gaps) > 10 else gaps


def gen_brownian(n=100000):
    """Brownian motion — gaps between level crossings."""
    walk = np.cumsum(rng.standard_normal(n))
    crossings = np.where(np.diff(np.sign(walk)))[0]
    if len(crossings) < 10:
        return np.array([1.0])
    return np.diff(crossings).astype(float)


def gen_coupled_oscillators(n=200):
    """Coupled harmonic oscillators — eigenfrequency spacings."""
    K = np.zeros((n, n))
    for i in range(n):
        k1 = 1.0 + 0.5 * np.sin(2 * np.pi * i * PHI)
        K[i, i] = 2 * k1
        if i > 0:
            K[i, i-1] = K[i-1, i] = -k1
    eigs = np.sort(linalg.eigvalsh(K))
    eigs = eigs[eigs > 1e-10]
    freqs = np.sqrt(eigs)
    spacings = np.diff(freqs)
    spacings = spacings[spacings > 1e-12]
    return spacings / np.mean(spacings)


def gen_reaction_diffusion(L=100, steps=5000):
    """1D reaction-diffusion (Gray-Scott) — pattern wavelength gaps."""
    u = np.ones(L)
    v = np.zeros(L)
    v[L//2 - 5:L//2 + 5] = 0.5
    u[L//2 - 5:L//2 + 5] = 0.5
    Du, Dv, F, k = 0.16, 0.08, 0.035, 0.065
    dt = 1.0
    for _ in range(steps):
        Lu = np.roll(u, 1) + np.roll(u, -1) - 2 * u
        Lv = np.roll(v, 1) + np.roll(v, -1) - 2 * v
        uvv = u * v * v
        u += dt * (Du * Lu - uvv + F * (1 - u))
        v += dt * (Dv * Lv + uvv - (F + k) * v)
    fft_v = np.abs(np.fft.rfft(v))[1:]
    peaks = np.where((fft_v[1:-1] > fft_v[:-2]) & (fft_v[1:-1] > fft_v[2:]))[0] + 1
    if len(peaks) < 5:
        return np.diff(np.sort(fft_v))
    spacings = np.diff(peaks).astype(float)
    return spacings


def gen_cellular_automata(rule=110, n=200, steps=500):
    """1D cellular automaton — column density gaps."""
    state = np.zeros(n, dtype=int)
    state[n // 2] = 1
    densities = []
    for _ in range(steps):
        new = np.zeros(n, dtype=int)
        for i in range(n):
            left = state[(i - 1) % n]
            center = state[i]
            right = state[(i + 1) % n]
            idx = left * 4 + center * 2 + right
            new[i] = (rule >> idx) & 1
        state = new
        densities.append(np.sum(state))
    d_sorted = np.sort(np.unique(densities)).astype(float)
    gaps = np.diff(d_sorted)
    gaps = gaps[gaps > 0]
    return gaps / np.mean(gaps) if len(gaps) > 10 else gaps


# Reference values
R_GUE = 0.5307  # 4 - 2√3 ≈ 0.5359 for GOE; for GUE: 2π/(3√3 + 4π/3) ≈ 0.5307 approx
R_POISSON = 2 * np.log(2) - 1  # ≈ 0.3863


DOMAINS = {
    'primes':              ('Numeri primi (100K)',        gen_primes),
    'gue':                 ('GUE random matrix',          gen_gue_eigenvalues),
    'poisson':             ('Poisson process',            gen_poisson),
    'logistic':            ('Logistic map (r=3.99)',      gen_logistic),
    'fibonacci_spectrum':  ('Fibonacci tight-binding',    gen_fibonacci_spectrum),
    'ising_2d':            ('Ising 2D (T_c)',             gen_ising_2d),
    'percolation':         ('Percolation (p_c)',          gen_percolation),
    'brownian':            ('Brownian zero-crossings',    gen_brownian),
    'coupled_oscillators': ('Coupled oscillators',        gen_coupled_oscillators),
    'reaction_diffusion':  ('Reaction-diffusion',         gen_reaction_diffusion),
    'cellular_automata':   ('Rule 110 CA',                gen_cellular_automata),
}


def run_all(verbose=True):
    results = {}
    for key, (label, gen_fn) in DOMAINS.items():
        if verbose:
            print(f"\n{'='*60}")
            print(f"  {label} ({key})")
            print(f"{'='*60}")
        try:
            gaps = gen_fn()
            if len(gaps) < 20:
                if verbose:
                    print(f"  SKIP: only {len(gaps)} gaps")
                continue
            res = shuffle_test(gaps)
            res['label'] = label
            res['n_gaps'] = len(gaps)

            # Classify
            dist_gue = abs(res['r_original'] - R_GUE)
            dist_poi = abs(res['r_original'] - R_POISSON)
            res['class_original'] = 'GUE' if dist_gue < dist_poi else 'Poisson'

            dist_gue_s = abs(res['r_shuffled_mean'] - R_GUE)
            dist_poi_s = abs(res['r_shuffled_mean'] - R_POISSON)
            res['class_shuffled'] = 'GUE' if dist_gue_s < dist_poi_s else 'Poisson'

            res['class_changes'] = res['class_original'] != res['class_shuffled']
            res['ordering_dependent'] = abs(res['z_score']) > 3.0

            if verbose:
                print(f"  N gaps:        {res['n_gaps']}")
                print(f"  r_original:    {res['r_original']:.4f}")
                print(f"  r_shuffled:    {res['r_shuffled_mean']:.4f} +/- {res['r_shuffled_std']:.4f}")
                print(f"  z-score:       {res['z_score']:.1f}")
                print(f"  Class:         {res['class_original']} -> shuffle -> {res['class_shuffled']}")
                print(f"  Ordering dep:  {'YES (non-trivial)' if res['ordering_dependent'] else 'NO (tautological)'}")
                if res['class_changes']:
                    print(f"  *** CLASS CHANGES ON SHUFFLE ***")

            results[key] = res
        except Exception as e:
            if verbose:
                print(f"  ERROR: {e}")
            results[key] = {'error': str(e), 'label': label}

    return results


def summarize(results):
    """Print summary table."""
    print(f"\n{'='*80}")
    print(f"  SUMMARY: GUE/Poisson Classification Shuffle Audit")
    print(f"{'='*80}")
    print(f"{'Domain':<25} {'r_orig':>7} {'r_shuf':>7} {'z':>7} {'Class':>8} {'Shuf':>8} {'Verdict':>14}")
    print(f"{'-'*25} {'-'*7} {'-'*7} {'-'*7} {'-'*8} {'-'*8} {'-'*14}")

    n_tautological = 0
    n_structural = 0
    n_class_change = 0

    for key, res in sorted(results.items()):
        if 'error' in res:
            print(f"{key:<25} ERROR: {res['error']}")
            continue
        verdict = 'STRUCTURAL' if res['ordering_dependent'] else 'TAUTOLOGICAL'
        if not res['ordering_dependent']:
            n_tautological += 1
        else:
            n_structural += 1
        if res.get('class_changes'):
            n_class_change += 1
            verdict += ' *'
        print(f"{key:<25} {res['r_original']:>7.4f} {res['r_shuffled_mean']:>7.4f} {res['z_score']:>7.1f} "
              f"{res['class_original']:>8} {res['class_shuffled']:>8} {verdict:>14}")

    total = n_tautological + n_structural
    print(f"\n  Structural (|z|>3):   {n_structural}/{total}")
    print(f"  Tautological (|z|<3): {n_tautological}/{total}")
    print(f"  Class changes:        {n_class_change}/{total}")
    print(f"\n  R_GUE = {R_GUE:.4f}, R_Poisson = {R_POISSON:.4f}")

    return {
        'n_structural': n_structural,
        'n_tautological': n_tautological,
        'n_class_change': n_class_change,
        'total': total,
    }


if __name__ == '__main__':
    results = run_all()
    summary = summarize(results)

    # Save results
    out = {
        'timestamp': datetime.now().isoformat(),
        'method': 'shuffle_audit_r_statistic',
        'n_shuffle': N_SHUFFLE,
        'reference': {'R_GUE': R_GUE, 'R_Poisson': R_POISSON},
        'domains': results,
        'summary': summary,
    }
    outfile = Path(__file__).parent / 'data' / 'boundary_shuffle_audit.json'
    with open(outfile, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved: {outfile}")
