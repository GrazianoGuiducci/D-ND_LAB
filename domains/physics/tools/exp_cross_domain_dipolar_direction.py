#!/usr/bin/env python3
"""
exp_cross_domain_dipolar_direction.py — Is the dipolar direction a universality-class
property or domain-specific?

Primes have theta=-111 deg in the (SR, L1) plane. GUE has theta=-97 deg.
Do all GUE-like domains share -97, or does each have its own direction?
Do all Poisson-like domains lack direction?

Tests 8 domains:
  GUE-like: GUE spacings, GOE spacings, CUE spacings, Riemann zeta zeros (via GUE proxy)
  Poisson-like: exponential iid, uniform iid, geometric iid
  Structured: primes, logistic map r=4

For each: compute dipolar vector (SR, L1) relative to own shuffle baseline.
Map all domains in the angle-magnitude plane.

Usage:
    python tools/exp_cross_domain_dipolar_direction.py [--N 50000] [--n_trials 20]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def get_primes(n_max):
    """Sieve of Eratosthenes."""
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n_max**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    return np.where(sieve)[0]


def spacing_ratio(gaps):
    """Mean ratio min/max of consecutive gaps."""
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.mean(r[np.isfinite(r) & (r > 0)])


def lag1_acf(gaps):
    """Lag-1 autocorrelation."""
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 == 0:
        return 0.0
    return np.mean(g[:-1] * g[1:]) / c0


def dipolar_vector(gaps, n_shuffle=100, rng_seed=7777):
    """Compute dipolar vector relative to own shuffle baseline."""
    rng = np.random.default_rng(rng_seed)
    sr_real = spacing_ratio(gaps)
    l1_real = lag1_acf(gaps)
    sr_list, l1_list = [], []
    for _ in range(n_shuffle):
        sg = rng.permutation(gaps)
        sr_list.append(spacing_ratio(sg))
        l1_list.append(lag1_acf(sg))
    sr_shuf, l1_shuf = np.mean(sr_list), np.mean(l1_list)
    sr_std, l1_std = np.std(sr_list), np.std(l1_list)
    dsr = sr_real - sr_shuf
    dl1 = l1_real - l1_shuf
    theta = np.degrees(np.arctan2(dl1, dsr))
    mag = np.sqrt(dsr**2 + dl1**2)
    ratio = abs(dl1 / dsr) if abs(dsr) > 1e-10 else float('inf')
    z_sr = dsr / sr_std if sr_std > 1e-12 else 0
    z_l1 = dl1 / l1_std if l1_std > 1e-12 else 0
    return {
        'theta': float(theta), 'magnitude': float(mag),
        'dL1_over_dSR': float(ratio),
        'delta_SR': float(dsr), 'delta_L1': float(dl1),
        'SR_real': float(sr_real), 'L1_real': float(l1_real),
        'z_SR': float(z_sr), 'z_L1': float(z_l1),
    }


def gen_rmt_spacings(N_mat, ensemble='GUE', rng=None):
    """Generate spacings from random matrix ensemble."""
    if rng is None:
        rng = np.random.default_rng()
    if ensemble == 'GUE':
        # Complex Hermitian: H = (A + A^H) / 2, A has iid complex normal
        A = (rng.standard_normal((N_mat, N_mat)) +
             1j * rng.standard_normal((N_mat, N_mat))) / np.sqrt(2)
        H = (A + A.conj().T) / 2
    elif ensemble == 'GOE':
        A = rng.standard_normal((N_mat, N_mat))
        H = (A + A.T) / 2
    elif ensemble == 'CUE':
        # Circular unitary ensemble: eigenvalues of random unitary
        A = (rng.standard_normal((N_mat, N_mat)) +
             1j * rng.standard_normal((N_mat, N_mat))) / np.sqrt(2)
        Q, R = np.linalg.qr(A)
        D = np.diag(R)
        Q = Q * (D / np.abs(D))
        eigs = np.angle(np.linalg.eigvals(Q))
        eigs.sort()
        spacings = np.diff(eigs)
        # Unfold: divide by mean spacing
        spacings = spacings / np.mean(spacings)
        return spacings[spacings > 0]
    else:
        raise ValueError(f"Unknown ensemble: {ensemble}")

    eigs = np.linalg.eigvalsh(H)
    spacings = np.diff(eigs)
    # Unfold: divide by local mean spacing (simple unfolding)
    spacings = spacings / np.mean(spacings)
    return spacings[spacings > 0]


def gen_logistic(N, r=4.0, rng=None):
    """Logistic map x_{n+1} = r*x_n*(1-x_n). Return gaps between successive values."""
    if rng is None:
        rng = np.random.default_rng()
    x = rng.uniform(0.1, 0.9)
    vals = np.zeros(N + 1000)  # burn-in
    for i in range(len(vals)):
        x = r * x * (1 - x)
        vals[i] = x
    vals = vals[1000:][:N]
    # Gaps = differences of sorted values (spacing-like)
    vals_sorted = np.sort(vals)
    spacings = np.diff(vals_sorted) * N  # normalize by N to get O(1) spacings
    return spacings[spacings > 0]


def gen_poisson(N, rng=None):
    """Poisson process: exponential iid spacings."""
    if rng is None:
        rng = np.random.default_rng()
    return rng.exponential(1.0, size=N)


def gen_uniform(N, rng=None):
    """Uniform iid on [0,2] — mean 1, same as unfolded."""
    if rng is None:
        rng = np.random.default_rng()
    return rng.uniform(0, 2, size=N)


def gen_geometric(N, rng=None):
    """Geometric-distributed gaps (discrete, heavy-tail)."""
    if rng is None:
        rng = np.random.default_rng()
    return rng.geometric(p=0.3, size=N).astype(float)


def run_experiment(N=50000, n_trials=20, n_shuffle=100):
    """Main experiment."""
    print("=" * 72)
    print("CROSS-DOMAIN DIPOLAR DIRECTION")
    print("Is the dipolar angle a universality-class property or domain-specific?")
    print("=" * 72)

    # === 1. PRIMES ===
    print("\n--- PRIMES ---")
    primes = get_primes(N * 25)
    p = primes[primes > 10000][:N + 1]
    prime_gaps = np.diff(p).astype(float)
    prime_dv = dipolar_vector(prime_gaps, n_shuffle)
    print(f"  N={len(prime_gaps)}, theta={prime_dv['theta']:.1f}, "
          f"|d|={prime_dv['magnitude']:.4f}, dL1/dSR={prime_dv['dL1_over_dSR']:.3f}")
    print(f"  z_SR={prime_dv['z_SR']:.1f}, z_L1={prime_dv['z_L1']:.1f}")

    # === 2-4. Random matrix ensembles (multiple trials for statistics) ===
    domains = {}
    domains['primes'] = {'class': 'unique', 'single': prime_dv}

    N_mat = 500  # matrix size — 499 spacings per matrix
    n_matrices = max(1, N // N_mat)  # concatenate to get N spacings

    for ens_name in ['GUE', 'GOE', 'CUE']:
        print(f"\n--- {ens_name} ---")
        trial_results = []
        for trial in range(n_trials):
            rng = np.random.default_rng(100 * hash(ens_name) % 10000 + trial)
            # Concatenate multiple matrices for longer sequence
            all_spacings = []
            for _ in range(n_matrices):
                s = gen_rmt_spacings(N_mat, ensemble=ens_name, rng=rng)
                all_spacings.append(s)
            spacings = np.concatenate(all_spacings)[:N]
            dv = dipolar_vector(spacings, n_shuffle=50, rng_seed=3000 + trial)
            trial_results.append(dv)

        thetas = [r['theta'] for r in trial_results]
        mags = [r['magnitude'] for r in trial_results]
        ratios = [r['dL1_over_dSR'] for r in trial_results]
        tm, ts = np.mean(thetas), np.std(thetas)
        mm = np.mean(mags)
        rm, rs = np.mean(ratios), np.std(ratios)
        print(f"  {n_trials} trials x {n_matrices} matrices ({N_mat}x{N_mat})")
        print(f"  theta = {tm:.1f} +/- {ts:.1f}, |d| = {mm:.4f}, "
              f"dL1/dSR = {rm:.3f} +/- {rs:.3f}")
        domains[ens_name] = {
            'class': 'RMT',
            'theta_mean': float(tm), 'theta_std': float(ts),
            'mag_mean': float(mm),
            'ratio_mean': float(rm), 'ratio_std': float(rs),
            'n_trials': n_trials,
        }

    # === 5. Logistic map (r=4, fully chaotic) ===
    print("\n--- LOGISTIC MAP (r=4, chaos) ---")
    trial_results = []
    for trial in range(n_trials):
        rng = np.random.default_rng(5000 + trial)
        log_gaps = gen_logistic(N, r=4.0, rng=rng)
        dv = dipolar_vector(log_gaps, n_shuffle=50, rng_seed=5500 + trial)
        trial_results.append(dv)
    thetas = [r['theta'] for r in trial_results]
    mags = [r['magnitude'] for r in trial_results]
    tm, ts = np.mean(thetas), np.std(thetas)
    mm = np.mean(mags)
    print(f"  theta = {tm:.1f} +/- {ts:.1f}, |d| = {mm:.4f}")
    domains['logistic_r4'] = {
        'class': 'chaotic',
        'theta_mean': float(tm), 'theta_std': float(ts),
        'mag_mean': float(mm),
        'ratio_mean': float(np.mean([r['dL1_over_dSR'] for r in trial_results])),
        'n_trials': n_trials,
    }

    # === 6-8. Poisson-like domains ===
    for name, gen_fn in [('exponential', gen_poisson),
                          ('uniform', gen_uniform),
                          ('geometric', gen_geometric)]:
        print(f"\n--- {name.upper()} (iid, Poisson-class) ---")
        trial_results = []
        for trial in range(n_trials):
            rng = np.random.default_rng(6000 + hash(name) % 1000 + trial)
            gaps = gen_fn(N, rng=rng)
            dv = dipolar_vector(gaps, n_shuffle=50, rng_seed=6500 + trial)
            trial_results.append(dv)
        thetas = [r['theta'] for r in trial_results]
        mags = [r['magnitude'] for r in trial_results]
        tm, ts = np.mean(thetas), np.std(thetas)
        mm = np.mean(mags)
        print(f"  theta = {tm:.1f} +/- {ts:.1f}, |d| = {mm:.6f}")
        domains[name] = {
            'class': 'Poisson',
            'theta_mean': float(tm), 'theta_std': float(ts),
            'mag_mean': float(mm),
            'ratio_mean': float(np.mean([r['dL1_over_dSR'] for r in trial_results])),
            'n_trials': n_trials,
        }

    # === SUMMARY ===
    print("\n" + "=" * 72)
    print("SUMMARY — DIPOLAR DIRECTIONS ACROSS DOMAINS")
    print("=" * 72)
    print(f"\n{'Domain':<16} {'Class':<10} {'theta (deg)':<20} "
          f"{'|d|':<12} {'dL1/dSR':<12}")
    print("-" * 70)
    for name, d in domains.items():
        if 'single' in d:
            v = d['single']
            print(f"{name:<16} {d['class']:<10} {v['theta']:>7.1f}{'':>13} "
                  f"{v['magnitude']:<12.4f} {v['dL1_over_dSR']:<12.3f}")
        else:
            ts = f"{d['theta_mean']:>7.1f} +/- {d['theta_std']:>5.1f}"
            print(f"{name:<16} {d['class']:<10} {ts:<20} "
                  f"{d['mag_mean']:<12.4f} {d.get('ratio_mean', 0):<12.3f}")

    # === ANGULAR SEPARATION ANALYSIS ===
    print("\n--- ANGULAR SEPARATIONS ---")
    # Reference: primes
    prime_theta = prime_dv['theta']

    rmt_names = ['GUE', 'GOE', 'CUE']
    poisson_names = ['exponential', 'uniform', 'geometric']

    # Pairwise separations among RMT
    print("\n  Pairwise within RMT ensembles:")
    for i, a in enumerate(rmt_names):
        for b in rmt_names[i+1:]:
            da = domains[a]['theta_mean']
            db = domains[b]['theta_mean']
            sep = da - db
            while sep > 180: sep -= 360
            while sep < -180: sep += 360
            # Combined uncertainty
            ua = domains[a]['theta_std']
            ub = domains[b]['theta_std']
            z = abs(sep) / max(np.sqrt(ua**2 + ub**2), 0.1)
            print(f"    {a} - {b}: {sep:+.1f} deg (z = {z:.1f})")

    # Each RMT vs primes
    print("\n  RMT vs Primes:")
    for name in rmt_names:
        sep = prime_theta - domains[name]['theta_mean']
        while sep > 180: sep -= 360
        while sep < -180: sep += 360
        z = abs(sep) / max(domains[name]['theta_std'], 0.1)
        print(f"    Primes - {name}: {sep:+.1f} deg (z = {z:.1f})")

    # Magnitude comparison
    print("\n  Magnitude comparison (|d|):")
    print(f"    Primes:  {prime_dv['magnitude']:.4f}")
    for name in rmt_names:
        print(f"    {name}:  {domains[name]['mag_mean']:.4f}")
    print(f"    ---")
    for name in poisson_names:
        print(f"    {name}:  {domains[name]['mag_mean']:.6f}")

    # Poisson direction scatter
    print("\n  Poisson direction scatter (std of theta):")
    for name in poisson_names:
        print(f"    {name}: std = {domains[name]['theta_std']:.1f} deg")

    # Save
    output = {
        'domains': domains,
        'N_target': N,
        'n_trials': n_trials,
        'N_mat': N_mat,
        'n_matrices': n_matrices,
        'n_shuffle': n_shuffle,
    }
    out_path = Path(__file__).parent / "data" / "cross_domain_dipolar_direction.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=50000,
                        help='Target number of spacings per domain')
    parser.add_argument('--n_trials', type=int, default=20,
                        help='Number of independent trials per domain')
    parser.add_argument('--n_shuffle', type=int, default=100,
                        help='Number of shuffles for baseline')
    args = parser.parse_args()
    run_experiment(N=args.N, n_trials=args.n_trials, n_shuffle=args.n_shuffle)
