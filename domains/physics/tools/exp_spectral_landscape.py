#!/usr/bin/env python3
"""
exp_spectral_landscape.py — Map the spectral landscape across domains.

Classifies sequences by their spacing statistics (<r>, Brody beta, gap_acf1).
Identifies: GUE domains, Poisson domains, and BOUNDARY domains.

The question: Is the boundary between GUE and Poisson populated by multiple
domains, or are primes special? If boundary sequences share cascade structure,
the boundary IS the content.

Usage:
    python exp_spectral_landscape.py [--N 5000] [--surrogates 20]
"""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import gamma as gamma_fn
import json, sys, os
from datetime import datetime

N_DEFAULT = 5000  # spacings per domain
N_SURROGATES = 20


# ─── Domain generators ───────────────────────────────────────────────

def gen_primes(n_spacings):
    """Prime gaps (unfolded via local density)."""
    # Sieve enough primes
    limit = int(n_spacings * 15 * np.log(n_spacings * 15))
    limit = max(limit, 100000)
    sieve = np.ones(limit, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    primes = np.where(sieve)[0].astype(float)
    primes = primes[:n_spacings + 1]
    # Unfold: s_n = (p_{n+1} - p_n) / <gap_local>
    gaps = np.diff(primes)
    # Local mean via rolling window
    w = min(50, len(gaps) // 5)
    kernel = np.ones(w) / w
    local_mean = np.convolve(gaps, kernel, mode='same')
    local_mean[local_mean < 0.1] = 1.0
    spacings = gaps / local_mean
    return spacings[:n_spacings]


def gen_gue(n_spacings):
    """GUE: eigenvalue spacings of complex Hermitian random matrix."""
    N = n_spacings + 50
    H = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    H = (H + H.conj().T) / 2
    eigs = np.sort(np.linalg.eigvalsh(H).real)
    spacings = np.diff(eigs)
    # Unfold
    local_mean = np.convolve(spacings, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = spacings / local_mean
    return s[:n_spacings]


def gen_goe(n_spacings):
    """GOE: eigenvalue spacings of real symmetric random matrix."""
    N = n_spacings + 50
    H = np.random.randn(N, N)
    H = (H + H.T) / 2
    eigs = np.sort(np.linalg.eigvalsh(H))
    spacings = np.diff(eigs)
    local_mean = np.convolve(spacings, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = spacings / local_mean
    return s[:n_spacings]


def gen_gse(n_spacings):
    """GSE (beta=4): eigenvalue spacings of quaternion self-dual matrix."""
    # Simulate via 2Nx2N antisymmetric construction
    N = n_spacings + 50
    A = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    B = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    # Quaternion matrix: H = [[A, B], [-B*, A*]]
    H_top = np.hstack([A, B])
    H_bot = np.hstack([-B.conj(), A.conj()])
    H = np.vstack([H_top, H_bot])
    H = (H + H.conj().T) / 2
    eigs = np.sort(np.linalg.eigvalsh(H).real)
    # GSE has doubly degenerate eigenvalues — take every other
    eigs = eigs[::2]
    spacings = np.diff(eigs)
    local_mean = np.convolve(spacings, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = spacings / local_mean
    return s[:n_spacings]


def gen_poisson(n_spacings):
    """Poisson: uncorrelated exponential spacings."""
    return np.random.exponential(1.0, n_spacings)


def gen_picket_fence(n_spacings):
    """Picket fence (rigid): equal spacings + tiny noise."""
    s = np.ones(n_spacings) + np.random.normal(0, 0.01, n_spacings)
    return np.abs(s)


def gen_semi_poisson(n_spacings):
    """Semi-Poisson: P(s) = 4s*exp(-2s). Known intermediate statistics."""
    # Inverse CDF sampling: CDF = 1 - (1+2s)e^{-2s}
    # Use rejection sampling
    samples = []
    while len(samples) < n_spacings:
        s = np.random.exponential(0.5, n_spacings * 2)
        accept = np.random.uniform(0, 1, len(s)) < 4 * s * np.exp(-2 * s) / (4 * 0.5 * np.exp(-1))
        samples.extend(s[accept])
    return np.array(samples[:n_spacings])


def gen_berry_robnik(n_spacings, rho=0.5):
    """Berry-Robnik: mixed system, fraction rho chaotic (GUE-like), 1-rho regular (Poisson).
    This is the canonical boundary model from quantum chaos."""
    n_chaotic = int(rho * n_spacings)
    n_regular = n_spacings - n_chaotic
    s_chaotic = gen_gue(n_chaotic) if n_chaotic > 100 else np.array([])
    s_regular = gen_poisson(n_regular) if n_regular > 100 else np.array([])
    s = np.concatenate([s_chaotic, s_regular])
    np.random.shuffle(s)
    return s[:n_spacings]


def gen_fibonacci_gaps(n_spacings):
    """Gaps between Fibonacci numbers (unfolded)."""
    fibs = [1, 1]
    while len(fibs) < n_spacings + 100:
        fibs.append(fibs[-1] + fibs[-2])
    fibs = np.array(fibs[10:], dtype=float)  # skip small ones
    gaps = np.diff(fibs)
    # Unfold by local mean (Fibonacci gaps grow exponentially)
    local_mean = np.convolve(gaps, np.ones(20)/20, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = gaps / local_mean
    return s[:n_spacings]


def gen_quadratic_residues(n_spacings):
    """Gaps between quadratic residues mod large prime (unfolded)."""
    # Find a large prime
    p = 100003  # prime
    qr = sorted(set((x * x) % p for x in range(1, p)))
    qr = np.array(qr, dtype=float)
    gaps = np.diff(qr)
    local_mean = np.convolve(gaps, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = gaps / local_mean
    return s[:n_spacings]


def gen_zeta_zeros_model(n_spacings):
    """Model for Riemann zeta zeros — Montgomery pair correlation (GUE).
    We use GUE directly since computing actual zeros is expensive."""
    return gen_gue(n_spacings)  # theoretically identical


def gen_cm_eigenvalues(n_spacings):
    """Anderson model at critical point (3D) — known to be at the boundary.
    Simplified: diagonal disorder + nearest-neighbor hopping on 1D chain."""
    L = n_spacings + 100
    W = 5.0  # disorder strength — tune for critical point
    diag = W * (np.random.uniform(size=L) - 0.5)
    H = np.diag(diag) + np.diag(np.ones(L - 1), 1) + np.diag(np.ones(L - 1), -1)
    eigs = np.sort(np.linalg.eigvalsh(H))
    spacings = np.diff(eigs)
    local_mean = np.convolve(spacings, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = spacings / local_mean
    return s[:n_spacings]


def gen_harper_model(n_spacings, alpha=None):
    """Harper/Hofstadter model: H = 2cos(2*pi*alpha*n + theta).
    alpha=golden ratio → critical (Cantor spectrum), alpha=rational → bands."""
    if alpha is None:
        alpha = (1 + np.sqrt(5)) / 2  # golden ratio — critical
    L = n_spacings + 100
    theta = np.random.uniform(0, 2 * np.pi)
    ns = np.arange(L)
    diag = 2 * np.cos(2 * np.pi * alpha * ns + theta)
    H = np.diag(diag) + np.diag(np.ones(L - 1), 1) + np.diag(np.ones(L - 1), -1)
    eigs = np.sort(np.linalg.eigvalsh(H))
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 1e-12]  # remove zero gaps from band edges
    local_mean = np.convolve(spacings, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    s = spacings / local_mean
    return s[:n_spacings]


def gen_power_law_gaps(n_spacings, exponent=1.5):
    """Sequence with power-law distributed gaps — tunable repulsion."""
    gaps = np.random.pareto(exponent, n_spacings) + 0.1
    return gaps / np.mean(gaps)


def gen_clock_jitter(n_spacings):
    """Regular clock + noise — models weakly perturbed regular spectrum."""
    s = np.ones(n_spacings) + 0.3 * np.random.normal(0, 1, n_spacings)
    return np.abs(s)


# ─── Observables ──────────────────────────────────────────────────────

def ratio_statistic(spacings):
    """<r> = mean of min(s_i, s_{i+1}) / max(s_i, s_{i+1})."""
    s = spacings[spacings > 0]
    if len(s) < 3:
        return np.nan
    r = np.minimum(s[:-1], s[1:]) / np.maximum(s[:-1], s[1:])
    return np.mean(r)


def brody_beta(spacings):
    """Fit Brody parameter beta. P(s) = (beta+1)*b*s^beta * exp(-b*s^{beta+1})."""
    s = spacings[spacings > 0]
    if len(s) < 10:
        return np.nan
    s = s / np.mean(s)

    def neg_loglik(beta):
        bp1 = beta + 1
        b = (gamma_fn(1 + 1/bp1)) ** bp1
        ll = np.log(bp1) + np.log(b) + beta * np.log(s + 1e-30) - b * (s ** bp1)
        return -np.mean(ll)

    res = minimize_scalar(neg_loglik, bounds=(0.01, 4.0), method='bounded')
    return res.x


def gap_acf1(spacings):
    """Lag-1 autocorrelation of spacings."""
    s = spacings - np.mean(spacings)
    if np.var(spacings) < 1e-15:
        return np.nan
    c0 = np.mean(s ** 2)
    c1 = np.mean(s[:-1] * s[1:])
    return c1 / c0 if c0 > 0 else np.nan


# ─── Main experiment ──────────────────────────────────────────────────

def run_domain(name, generator, n_spacings, n_surrogates, **kwargs):
    """Run observables on a domain + shuffled surrogates."""
    try:
        spacings = generator(n_spacings, **kwargs) if kwargs else generator(n_spacings)
    except Exception as e:
        return {"name": name, "error": str(e)}

    spacings = spacings[np.isfinite(spacings) & (spacings > 0)]
    if len(spacings) < 100:
        return {"name": name, "error": f"Too few spacings: {len(spacings)}"}

    r = ratio_statistic(spacings)
    beta = brody_beta(spacings)
    acf1 = gap_acf1(spacings)

    # Shuffled surrogates — destroy sequential structure
    r_shuf, beta_shuf, acf1_shuf = [], [], []
    for _ in range(n_surrogates):
        s_shuf = spacings.copy()
        np.random.shuffle(s_shuf)
        r_shuf.append(ratio_statistic(s_shuf))
        beta_shuf.append(brody_beta(s_shuf))
        acf1_shuf.append(gap_acf1(s_shuf))

    def z(val, surr):
        surr = np.array(surr)
        std = np.std(surr)
        if std < 1e-10:
            return 0.0
        return (val - np.mean(surr)) / std

    return {
        "name": name,
        "n_spacings": int(len(spacings)),
        "r_mean": float(r),
        "beta": float(beta),
        "acf1": float(acf1),
        "r_shuf_mean": float(np.mean(r_shuf)),
        "beta_shuf_mean": float(np.mean(beta_shuf)),
        "acf1_shuf_mean": float(np.mean(acf1_shuf)),
        "z_r": float(z(r, r_shuf)),
        "z_beta": float(z(beta, beta_shuf)),
        "z_acf1": float(z(acf1, acf1_shuf)),
    }


def classify(r_mean):
    """Classify domain by <r> statistic."""
    POISSON = 0.386
    GOE = 0.536
    GUE = 0.603
    if r_mean < POISSON + 0.03:
        return "POISSON"
    elif r_mean < (POISSON + GOE) / 2:
        return "BOUNDARY_low"
    elif r_mean < (GOE + GUE) / 2:
        return "GOE-like"
    elif r_mean < GUE + 0.03:
        return "GUE-like"
    else:
        return "RIGID"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--N", type=int, default=N_DEFAULT)
    parser.add_argument("--surrogates", type=int, default=N_SURROGATES)
    args = parser.parse_args()

    N = args.N
    NS = args.surrogates

    domains = [
        # Expected GUE
        ("GUE_matrix", gen_gue, {}),
        ("zeta_zeros_model", gen_zeta_zeros_model, {}),
        # Expected GOE
        ("GOE_matrix", gen_goe, {}),
        # Expected GSE (beta=4)
        ("GSE_matrix", gen_gse, {}),
        # Expected Poisson
        ("Poisson", gen_poisson, {}),
        ("power_law_1.5", gen_power_law_gaps, {"exponent": 1.5}),
        # Expected rigid
        ("picket_fence", gen_picket_fence, {}),
        ("clock_jitter", gen_clock_jitter, {}),
        # Boundary candidates
        ("primes", gen_primes, {}),
        ("semi_Poisson", gen_semi_poisson, {}),
        ("Berry_Robnik_0.3", gen_berry_robnik, {"rho": 0.3}),
        ("Berry_Robnik_0.5", gen_berry_robnik, {"rho": 0.5}),
        ("Berry_Robnik_0.7", gen_berry_robnik, {"rho": 0.7}),
        ("Anderson_1D_W5", gen_cm_eigenvalues, {}),
        ("Harper_phi", gen_harper_model, {}),
        ("Harper_rational", gen_harper_model, {"alpha": 1/3}),
        ("Fibonacci_gaps", gen_fibonacci_gaps, {}),
        ("quadratic_residues", gen_quadratic_residues, {}),
    ]

    print(f"Spectral Landscape — N={N}, surrogates={NS}")
    print(f"{'Domain':<25} {'<r>':>7} {'beta':>7} {'acf1':>7} {'z_r':>7} {'z_beta':>7} {'z_acf1':>7} {'class':>15}")
    print("-" * 100)

    results = []
    for name, gen, kwargs in domains:
        res = run_domain(name, gen, N, NS, **kwargs)
        results.append(res)
        if "error" in res:
            print(f"{name:<25} ERROR: {res['error']}")
            continue
        cls = classify(res["r_mean"])
        print(f"{res['name']:<25} {res['r_mean']:7.4f} {res['beta']:7.3f} {res['acf1']:7.4f} "
              f"{res['z_r']:7.1f} {res['z_beta']:7.1f} {res['z_acf1']:7.1f} {cls:>15}")

    # Reference values
    print("\nReference: Poisson <r>=0.386, GOE <r>=0.536, GUE <r>=0.603")

    # Classification summary
    classes = {}
    for res in results:
        if "error" in res:
            continue
        cls = classify(res["r_mean"])
        classes.setdefault(cls, []).append(res["name"])

    print("\n=== Classification ===")
    for cls in ["POISSON", "BOUNDARY_low", "GOE-like", "GUE-like", "RIGID"]:
        if cls in classes:
            print(f"  {cls}: {', '.join(classes[cls])}")

    # Boundary analysis — do boundary domains share structure?
    boundary = [r for r in results if "error" not in r and classify(r["r_mean"]) == "BOUNDARY_low"]
    if boundary:
        print(f"\n=== Boundary Domains ({len(boundary)}) ===")
        for b in boundary:
            print(f"  {b['name']}: <r>={b['r_mean']:.4f}, beta={b['beta']:.3f}, acf1={b['acf1']:.4f}, "
                  f"z_acf1={b['z_acf1']:.1f}")
        # Test: do boundary domains have correlated observables?
        if len(boundary) >= 3:
            r_vals = [b["r_mean"] for b in boundary]
            beta_vals = [b["beta"] for b in boundary]
            acf1_vals = [b["acf1"] for b in boundary]
            print(f"  <r> range: [{min(r_vals):.4f}, {max(r_vals):.4f}]")
            print(f"  beta range: [{min(beta_vals):.3f}, {max(beta_vals):.3f}]")
            print(f"  acf1 range: [{min(acf1_vals):.4f}, {max(acf1_vals):.4f}]")

    # Key question: are primes unique at the boundary or do others live there?
    prime_result = next((r for r in results if r["name"] == "primes"), None)
    if prime_result and "error" not in prime_result:
        print(f"\n=== Primes position ===")
        print(f"  <r>={prime_result['r_mean']:.4f}, beta={prime_result['beta']:.3f}, acf1={prime_result['acf1']:.4f}")
        print(f"  z-scores: r={prime_result['z_r']:.1f}, beta={prime_result['z_beta']:.1f}, acf1={prime_result['z_acf1']:.1f}")

        # Distance to each domain
        print(f"\n  Distance from primes (<r>):")
        for res in sorted(results, key=lambda x: abs(x.get("r_mean", 99) - prime_result["r_mean"])):
            if "error" in res or res["name"] == "primes":
                continue
            d = res["r_mean"] - prime_result["r_mean"]
            print(f"    {res['name']:<25} delta_r = {d:+.4f}")

    # Save results
    outpath = os.path.join(os.path.dirname(__file__), "data", "exp_spectral_landscape.json")
    with open(outpath, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "N": N,
            "surrogates": NS,
            "results": results,
            "classification": {k: v for k, v in classes.items()},
        }, f, indent=2)
    print(f"\nSaved: {outpath}")


if __name__ == "__main__":
    main()
