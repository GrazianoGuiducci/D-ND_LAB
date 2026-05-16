#!/usr/bin/env python3
"""
exp_dipolar_crossover.py — Topology of the GUE-Poisson transition in the dipolar plane.

Question: As ordering is gradually destroyed (GUE → shuffled), does the dipolar
angle rotate smoothly or undergo a phase transition? And where do primes sit
relative to this crossover curve?

Method:
  1. Generate GUE bulk spacings from random matrices
  2. For each alpha in [0, 1], partially shuffle the spacings:
     - Select floor(alpha * N) random positions
     - Shuffle spacings at those positions among themselves
     - Leave the rest in original (GUE) order
  3. Compute SR, L1, theta, magnitude at each alpha
  4. Compare prime (SR, L1) against the crossover curve
  5. Null: each alpha level vs its own full-shuffle (to isolate partial-shuffle from marginal)

If primes sit on the curve → they're "partially disordered GUE"
If primes sit off the curve → their ordering is structurally distinct

Usage:
    python tools/exp_dipolar_crossover.py [--N_mat 400] [--n_matrices 80] [--n_alpha 21] [--n_trials 30]
"""

import argparse
import json
import numpy as np
from pathlib import Path


def gue_spacings(N_mat, n_matrices, rng):
    """Generate bulk spacings from GUE matrices."""
    all_spacings = []
    for _ in range(n_matrices):
        H = rng.standard_normal((N_mat, N_mat)) + 1j * rng.standard_normal((N_mat, N_mat))
        H = (H + H.conj().T) / 2.0
        eigs = np.sort(np.linalg.eigvalsh(H))
        # bulk: central 60%
        lo = int(0.2 * N_mat)
        hi = int(0.8 * N_mat)
        s = np.diff(eigs[lo:hi])
        # normalize to mean 1
        s = s / np.mean(s)
        all_spacings.append(s)
    return all_spacings  # list of arrays, one per matrix


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
    return np.mean(r[np.isfinite(r)])


def lag1_acf(gaps):
    """Lag-1 autocorrelation."""
    g = gaps - np.mean(gaps)
    c0 = np.mean(g**2)
    if c0 < 1e-15:
        return 0.0
    return np.mean(g[:-1] * g[1:]) / c0


def partial_shuffle(spacings, alpha, rng):
    """Shuffle a fraction alpha of positions, keep rest in order."""
    s = spacings.copy()
    n = len(s)
    n_shuffle = int(alpha * n)
    if n_shuffle < 2:
        return s
    idx = rng.choice(n, size=n_shuffle, replace=False)
    vals = s[idx].copy()
    rng.shuffle(vals)
    s[idx] = vals
    return s


def compute_dipolar(gaps_list):
    """Compute (SR, L1) per matrix, then average and get theta, magnitude."""
    srs = [spacing_ratio(g) for g in gaps_list if len(g) > 3]
    l1s = [lag1_acf(g) for g in gaps_list if len(g) > 3]
    return np.mean(srs), np.mean(l1s), np.std(srs), np.std(l1s)


def run_crossover(N_mat, n_matrices, n_alpha, n_trials, seed=42):
    rng = np.random.default_rng(seed)

    print(f"Generating GUE spacings: {n_matrices} matrices of size {N_mat}...")
    gue_mats = gue_spacings(N_mat, n_matrices, rng)

    # GUE baseline (alpha=0)
    sr0, l1_0, _, _ = compute_dipolar(gue_mats)

    # Full shuffle baseline (alpha=1) — per-matrix shuffle
    shuffled_mats = []
    for s in gue_mats:
        sc = s.copy()
        rng.shuffle(sc)
        shuffled_mats.append(sc)
    sr1, l1_1, _, _ = compute_dipolar(shuffled_mats)

    alphas = np.linspace(0, 1, n_alpha)
    results = []

    print(f"Scanning {n_alpha} alpha levels, {n_trials} trials each...")
    for alpha in alphas:
        srs_trials = []
        l1s_trials = []
        for trial in range(n_trials):
            rng_trial = np.random.default_rng(seed + trial * 1000 + int(alpha * 100))
            trial_mats = [partial_shuffle(s, alpha, rng_trial) for s in gue_mats]
            sr, l1, _, _ = compute_dipolar(trial_mats)
            srs_trials.append(sr)
            l1s_trials.append(l1)

        sr_mean = np.mean(srs_trials)
        sr_std = np.std(srs_trials)
        l1_mean = np.mean(l1s_trials)
        l1_std = np.std(l1s_trials)

        # Dipolar angle relative to full-shuffle
        dSR = sr_mean - sr1
        dL1 = l1_mean - l1_1
        theta = np.degrees(np.arctan2(dL1, dSR))
        mag = np.sqrt(dSR**2 + dL1**2)

        results.append({
            "alpha": float(alpha),
            "SR": float(sr_mean),
            "SR_std": float(sr_std),
            "L1": float(l1_mean),
            "L1_std": float(l1_std),
            "theta": float(theta),
            "magnitude": float(mag),
            "dSR": float(dSR),
            "dL1": float(dL1)
        })
        print(f"  alpha={alpha:.2f}: SR={sr_mean:.4f} L1={l1_mean:.4f} theta={theta:.1f} mag={mag:.4f}")

    # Prime reference
    print("Computing prime reference...")
    primes = get_primes(1_500_000)
    gaps = np.diff(primes)
    # normalize by local mean (running window)
    win = 100
    local_mean = np.convolve(gaps, np.ones(win)/win, mode='same')
    local_mean[local_mean < 1] = 1
    norm_gaps = gaps / local_mean

    # Split into chunks for per-matrix-equivalent stats
    chunk_size = len(norm_gaps) // n_matrices
    prime_chunks = [norm_gaps[i*chunk_size:(i+1)*chunk_size] for i in range(n_matrices)]
    sr_p, l1_p, sr_p_std, l1_p_std = compute_dipolar(prime_chunks)

    # Prime shuffle baseline
    prime_shuffled = []
    for c in prime_chunks:
        cs = c.copy()
        rng.shuffle(cs)
        prime_shuffled.append(cs)
    sr_ps, l1_ps, _, _ = compute_dipolar(prime_shuffled)

    dSR_p = sr_p - sr_ps
    dL1_p = l1_p - l1_ps
    theta_p = np.degrees(np.arctan2(dL1_p, dSR_p))
    mag_p = np.sqrt(dSR_p**2 + dL1_p**2)

    prime_ref = {
        "SR": float(sr_p), "L1": float(l1_p),
        "SR_shuffle": float(sr_ps), "L1_shuffle": float(l1_ps),
        "theta": float(theta_p), "magnitude": float(mag_p),
        "dSR": float(dSR_p), "dL1": float(dL1_p)
    }
    print(f"  Primes: SR={sr_p:.4f} L1={l1_p:.4f} theta={theta_p:.1f} mag={mag_p:.4f}")

    # Distance from prime to crossover curve
    crossover_sr = np.array([r["SR"] for r in results])
    crossover_l1 = np.array([r["L1"] for r in results])
    dists = np.sqrt((crossover_sr - sr_p)**2 + (crossover_l1 - l1_p)**2)
    closest_idx = np.argmin(dists)
    closest_alpha = results[closest_idx]["alpha"]
    min_dist = float(dists[closest_idx])

    # Phase transition detection: find where d(mag)/d(alpha) is maximal
    mags = np.array([r["magnitude"] for r in results])
    dmag = np.diff(mags)
    dalpha = np.diff(alphas)
    deriv = dmag / dalpha
    max_deriv_idx = np.argmax(np.abs(deriv))
    transition_alpha = float((alphas[max_deriv_idx] + alphas[max_deriv_idx + 1]) / 2)
    max_deriv_val = float(deriv[max_deriv_idx])

    # Curvature of the crossover path
    dx = np.diff(crossover_sr)
    dy = np.diff(crossover_l1)
    path_angles = np.degrees(np.arctan2(dy, dx))

    output = {
        "method": "partial_shuffle_crossover",
        "N_mat": N_mat,
        "n_matrices": n_matrices,
        "n_alpha": n_alpha,
        "n_trials": n_trials,
        "GUE_baseline": {"SR": float(sr0), "L1": float(l1_0)},
        "shuffle_baseline": {"SR": float(sr1), "L1": float(l1_1)},
        "crossover": results,
        "prime_ref": prime_ref,
        "closest_alpha": float(closest_alpha),
        "min_distance_to_curve": float(min_dist),
        "transition": {
            "alpha_max_deriv": float(transition_alpha),
            "max_deriv": float(max_deriv_val),
            "smooth_or_sharp": "sharp" if abs(max_deriv_val) > 2 * np.mean(np.abs(deriv)) else "smooth"
        },
        "path_direction_changes": float(np.std(path_angles))
    }

    out_path = Path("tools/data/dipolar_crossover.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--N_mat", type=int, default=400)
    parser.add_argument("--n_matrices", type=int, default=80)
    parser.add_argument("--n_alpha", type=int, default=21)
    parser.add_argument("--n_trials", type=int, default=20)
    args = parser.parse_args()

    run_crossover(args.N_mat, args.n_matrices, args.n_alpha, args.n_trials)
