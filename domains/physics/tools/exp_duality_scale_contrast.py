#!/usr/bin/env python3
"""exp_duality_scale_contrast.py — Scale-dependent duality contrast.

Measures how the ordered-vs-shuffle contrast (z-score) changes with scale
for prime gaps, GUE eigenvalue spacings, and Poisson gaps.

Tension: DUALITA_DIPOLARE_VS_ILLUSORIA + BOUNDARY
Question: Where does dipolar duality (det=-1, generative structure)
dissolve into illusory duality (det=+1, noise-like)?

The vincolo DUALITA_DET_DENOMINATOR_GATE established that det(M) is not
the primary discriminator. The real information is the real-vs-shuffle gap
at different scales. This experiment maps that gap systematically.

Usage:
    python tools/exp_duality_scale_contrast.py [--out FILE] [--n-primes N]
"""
import argparse
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import numpy as np
from observables_registry import (
    OBSERVABLES_REGISTRY_VERSION,
    OBSERVABLES_CANONICAL,
    compute_canonical,
)


def sieve_primes(limit: int) -> np.ndarray:
    """Sieve of Eratosthenes."""
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    return np.nonzero(is_prime)[0]


def gue_spacings(n: int, rng: np.random.Generator) -> np.ndarray:
    """Generate GUE (beta=2) eigenvalue spacings from random Hermitian matrix."""
    size = max(int(n * 1.2), 50)
    A = rng.standard_normal((size, size)) + 1j * rng.standard_normal((size, size))
    H = (A + A.conj().T) / 2
    evals = np.sort(np.linalg.eigvalsh(H))
    gaps = np.diff(evals)
    # Unfold: normalize by local mean spacing
    if len(gaps) > 10:
        kernel = min(len(gaps) // 5, 50)
        local_mean = np.convolve(gaps, np.ones(kernel) / kernel, mode='same')
        local_mean[local_mean < 1e-15] = 1.0
        gaps = gaps / local_mean
    return gaps[:n]


def poisson_spacings(n: int, rng: np.random.Generator) -> np.ndarray:
    """Generate Poisson (uncorrelated) spacings."""
    return rng.exponential(scale=1.0, size=n)


def compute_z_scores(gaps: np.ndarray, n_shuffle: int, rng: np.random.Generator) -> dict:
    """Compute z-score of canonical observables (real vs shuffle)."""
    real = compute_canonical(gaps)

    shuffle_results = {name: [] for name in OBSERVABLES_CANONICAL}
    for _ in range(n_shuffle):
        shuffled = rng.permutation(gaps)
        for name, fn in OBSERVABLES_CANONICAL.items():
            shuffle_results[name].append(fn(shuffled))

    z = {}
    for name in OBSERVABLES_CANONICAL:
        arr = np.array(shuffle_results[name])
        mu, sigma = np.mean(arr), np.std(arr)
        if sigma > 1e-15:
            z[name] = float((real[name] - mu) / sigma)
        else:
            z[name] = 0.0
    return z, real


def windowed_contrast(gaps: np.ndarray, window_sizes: list[int],
                      n_shuffle: int, rng: np.random.Generator,
                      n_windows_per_size: int = 5) -> list[dict]:
    """Compute duality contrast at multiple scales.

    For each window size, sample n_windows_per_size non-overlapping windows
    from the gap sequence and compute z-scores.
    """
    results = []
    N = len(gaps)

    for wsize in window_sizes:
        if wsize > N:
            continue

        z_accum = {name: [] for name in OBSERVABLES_CANONICAL}

        # Sample non-overlapping windows
        max_start = N - wsize
        starts = np.linspace(0, max_start, min(n_windows_per_size, max_start // wsize + 1),
                             dtype=int)

        for s in starts:
            window = gaps[s:s + wsize]
            if len(window) < 10:
                continue
            z, _ = compute_z_scores(window, n_shuffle, rng)
            for name in z:
                z_accum[name].append(z[name])

        if not z_accum["SR"]:
            continue

        entry = {
            "window_size": int(wsize),
            "n_windows": len(z_accum["SR"]),
        }
        for name in OBSERVABLES_CANONICAL:
            vals = z_accum[name]
            entry[f"z_{name}_mean"] = float(np.mean(vals))
            entry[f"z_{name}_std"] = float(np.std(vals))
        results.append(entry)

    return results


def run_experiment(n_primes: int = 200000, n_shuffle: int = 50,
                   seed: int = 42) -> dict:
    """Main experiment."""
    rng = np.random.default_rng(seed)

    # Generate sequences
    print(f"Generating primes up to ~{n_primes} gaps...")
    limit = int(n_primes * np.log(n_primes) * 1.3) + 1000
    primes = sieve_primes(limit)
    prime_gaps = np.diff(primes).astype(float)
    # Normalize by local mean (unfold)
    kernel = 100
    local_mean = np.convolve(prime_gaps, np.ones(kernel) / kernel, mode='same')
    local_mean[local_mean < 1e-15] = 1.0
    prime_gaps_unf = prime_gaps / local_mean

    n_gaps = min(len(prime_gaps_unf), n_primes)
    prime_gaps_unf = prime_gaps_unf[:n_gaps]

    print(f"Got {n_gaps} prime gaps. Generating GUE and Poisson controls...")
    gue_gaps = gue_spacings(min(n_gaps, 2000), rng)  # GUE limited by matrix size
    poisson_gaps = poisson_spacings(n_gaps, rng)

    # Window sizes: log-spaced from 50 to n_gaps/2
    window_sizes = np.unique(np.logspace(
        np.log10(50), np.log10(min(n_gaps // 2, 50000)), 8
    ).astype(int)).tolist()

    print(f"Window sizes: {window_sizes}")
    print(f"Computing windowed contrast for prime gaps...")
    prime_contrast = windowed_contrast(prime_gaps_unf, window_sizes, n_shuffle, rng)

    print(f"Computing windowed contrast for Poisson gaps...")
    poisson_contrast = windowed_contrast(poisson_gaps, window_sizes, n_shuffle, rng)

    # GUE: smaller windows only (limited by matrix size)
    gue_window_sizes = [w for w in window_sizes if w <= len(gue_gaps) // 2]
    print(f"Computing windowed contrast for GUE gaps (sizes: {gue_window_sizes})...")
    gue_contrast = windowed_contrast(gue_gaps, gue_window_sizes, n_shuffle, rng)

    # Global observables for context
    print("Computing global observables...")
    prime_global_z, prime_global_real = compute_z_scores(
        prime_gaps_unf[:5000], n_shuffle, rng
    )
    poisson_global_z, poisson_global_real = compute_z_scores(
        poisson_gaps[:5000], n_shuffle, rng
    )
    gue_global_z, gue_global_real = compute_z_scores(
        gue_gaps[:min(len(gue_gaps), 1500)], n_shuffle, rng
    )

    result = {
        "experiment": "duality_scale_contrast",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": list(OBSERVABLES_CANONICAL.keys()),
        "params": {
            "n_prime_gaps": int(n_gaps),
            "n_gue_gaps": int(len(gue_gaps)),
            "n_poisson_gaps": int(len(poisson_gaps)),
            "n_shuffle": n_shuffle,
            "seed": seed,
            "window_sizes": window_sizes,
        },
        "global_z": {
            "primes": prime_global_z,
            "gue": gue_global_z,
            "poisson": poisson_global_z,
        },
        "global_real": {
            "primes": prime_global_real,
            "gue": gue_global_real,
            "poisson": poisson_global_real,
        },
        "windowed_contrast": {
            "primes": prime_contrast,
            "gue": gue_contrast,
            "poisson": poisson_contrast,
        },
    }

    return result


def summarize(result: dict) -> str:
    """Print human-readable summary."""
    lines = []
    lines.append("=" * 70)
    lines.append("DUALITY SCALE CONTRAST — Summary")
    lines.append("=" * 70)

    # Global z-scores
    lines.append("\n--- Global z-scores (real vs shuffle, N=5000 gaps) ---")
    for domain in ["primes", "gue", "poisson"]:
        z = result["global_z"][domain]
        zstr = "  ".join(f"{k}={v:+.2f}" for k, v in z.items())
        lines.append(f"  {domain:10s}: {zstr}")

    # Windowed contrast
    lines.append("\n--- Windowed contrast (z_SR_mean by window size) ---")
    lines.append(f"  {'W_size':>8s}  {'Primes':>10s}  {'GUE':>10s}  {'Poisson':>10s}")
    lines.append("  " + "-" * 44)

    prime_data = {d["window_size"]: d for d in result["windowed_contrast"]["primes"]}
    gue_data = {d["window_size"]: d for d in result["windowed_contrast"]["gue"]}
    poisson_data = {d["window_size"]: d for d in result["windowed_contrast"]["poisson"]}

    all_sizes = sorted(set(
        list(prime_data.keys()) + list(gue_data.keys()) + list(poisson_data.keys())
    ))
    for ws in all_sizes:
        pz = f"{prime_data[ws]['z_SR_mean']:+.2f}" if ws in prime_data else "—"
        gz = f"{gue_data[ws]['z_SR_mean']:+.2f}" if ws in gue_data else "—"
        qz = f"{poisson_data[ws]['z_SR_mean']:+.2f}" if ws in poisson_data else "—"
        lines.append(f"  {ws:>8d}  {pz:>10s}  {gz:>10s}  {qz:>10s}")

    # Multi-observable table for primes
    lines.append("\n--- Prime gaps: all observables by window size ---")
    obs_names = list(OBSERVABLES_CANONICAL.keys())
    header = f"  {'W_size':>8s}  " + "  ".join(f"{'z_'+n:>10s}" for n in obs_names)
    lines.append(header)
    lines.append("  " + "-" * (10 + 12 * len(obs_names)))
    for ws in sorted(prime_data.keys()):
        d = prime_data[ws]
        vals = "  ".join(f"{d[f'z_{n}_mean']:+10.2f}" for n in obs_names)
        lines.append(f"  {ws:>8d}  {vals}")

    # Boundary detection: where does |z| cross 2?
    lines.append("\n--- Boundary detection (where |z_SR| < 2) ---")
    for domain, data in [("primes", prime_data), ("poisson", poisson_data)]:
        crossing = None
        prev_z = None
        for ws in sorted(data.keys()):
            z_sr = data[ws]["z_SR_mean"]
            if prev_z is not None and abs(prev_z) >= 2 and abs(z_sr) < 2:
                crossing = ws
            prev_z = z_sr
        if crossing:
            lines.append(f"  {domain}: |z_SR| crosses 2 at window_size ~ {crossing}")
        else:
            lines.append(f"  {domain}: no crossing detected in range")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/duality_scale_contrast.json")
    parser.add_argument("--n-primes", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = run_experiment(n_primes=args.n_primes, seed=args.seed)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {args.out}")

    summary = summarize(result)
    print(summary)
