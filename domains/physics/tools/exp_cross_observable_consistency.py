#!/usr/bin/env python3
"""
Cross-Observable Consistency Test (META)

Question: Do independent RMT observables (r-statistic, number variance)
give the SAME effective Brody parameter for primes?

- If yes: our tests are tautological (measuring the same thing N times)
- If no, with predictable structure: the observables are genuinely independent,
  the two-channel structure creates observable-dependent β, META resolved.

Method:
1. Load Brody calibration (r vs β, Σ²/L vs β at each L)
2. Measure r and Σ²(L)/L for primes at multiple windows
3. Invert each to get β_r and β_Σ(L) using calibration curves
4. Null: shuffled primes (should show β_r ≈ β_Σ since no ordering channel)
5. GUE control: synthetic GUE eigenvalues (should show β_r ≈ β_Σ ≈ 1)

The TWO-CHANNEL PREDICTION:
  β_r (short-range) > β_Σ(large L) because the ordering channel
  contributes more at large scales, pulling Σ² toward Poisson faster
  than r sees it.
"""

import numpy as np
import json
import sys
from datetime import datetime

# ── Load Brody calibration ──────────────────────────────────────────
with open('/opt/MM_D-ND/tools/data/brody_calibration_results.json') as f:
    cal = json.load(f)

cal_curve = cal['brody_curve']
cal_betas = np.array([c['beta'] for c in cal_curve])
cal_r = np.array([c['r'] for c in cal_curve])

# Σ²/L calibration at each L
L_KEYS = ['1', '2', '5', '10', '20', '50']
cal_sig2 = {}
for lk in L_KEYS:
    cal_sig2[lk] = np.array([c['sig2_over_L'][lk] for c in cal_curve])


def beta_from_r(r_val):
    """Invert r → β using calibration curve (linear interpolation)."""
    if r_val <= cal_r[0]:
        return 0.0
    if r_val >= cal_r[-1]:
        return cal_betas[-1]
    return float(np.interp(r_val, cal_r, cal_betas))


def beta_from_sig2(sig2_over_L, L_key):
    """Invert Σ²/L → β using calibration curve.
    Note: Σ²/L is DECREASING with β, so we need to flip."""
    curve = cal_sig2[L_key]
    if sig2_over_L >= curve[0]:
        return 0.0
    if sig2_over_L <= curve[-1]:
        return cal_betas[-1]
    # curve is decreasing, so flip for interp
    return float(np.interp(sig2_over_L, curve[::-1], cal_betas[::-1]))


# ── Generate prime gaps ─────────────────────────────────────────────
from sympy import primerange

PRIME_LIMIT = 200_000
primes = np.array(list(primerange(2, PRIME_LIMIT)), dtype=float)
gaps = np.diff(primes)
N = len(gaps)
print(f"Primes up to {PRIME_LIMIT}: {len(primes)} primes, {N} gaps")


# ── r-statistic ─────────────────────────────────────────────────────
def r_statistic(g):
    """Gap ratio r = mean(min(g_i, g_{i+1}) / max(g_i, g_{i+1}))."""
    r_vals = []
    for i in range(len(g) - 1):
        mn = min(g[i], g[i + 1])
        mx = max(g[i], g[i + 1])
        if mx > 0:
            r_vals.append(mn / mx)
    return np.mean(r_vals)


# ── Number variance ─────────────────────────────────────────────────
def unfold_primes(p):
    """Unfold using smooth part: n(p) ~ p/ln(p), normalize to unit spacing."""
    u = p / np.log(p)
    s = np.diff(u)
    u = u / np.mean(s)
    return u


def number_variance_at_L(unfolded, L, n_samples=3000):
    """Compute Σ²(L) = Var[N(x, x+L)] over random windows."""
    x_min, x_max = unfolded[0], unfolded[-1]
    if x_max - x_min <= L:
        return np.nan
    starts = np.linspace(x_min, x_max - L, min(n_samples, int((x_max - x_min) / L)))
    counts = np.array([np.sum((unfolded >= x0) & (unfolded < x0 + L)) for x0 in starts])
    return float(np.var(counts))


# ── GUE control (small ensemble) ────────────────────────────────────
def gue_gaps(n_eigenvalues=2000, n_matrices=5):
    """Generate GUE eigenvalue gaps."""
    all_gaps = []
    for _ in range(n_matrices):
        H = np.random.randn(n_eigenvalues, n_eigenvalues) + 1j * np.random.randn(n_eigenvalues, n_eigenvalues)
        H = (H + H.conj().T) / 2
        evals = np.sort(np.linalg.eigvalsh(H).real)
        # Unfold: for GUE bulk, spacing ~ semicircle
        mid = len(evals) // 4
        end = 3 * len(evals) // 4
        bulk = evals[mid:end]
        g = np.diff(bulk)
        mean_g = np.mean(g)
        if mean_g > 0:
            all_gaps.extend((g / mean_g).tolist())
    return np.array(all_gaps)


# ── Measure primes ──────────────────────────────────────────────────
print("\n=== PRIMES (real) ===")
r_prime = r_statistic(gaps)
beta_r_prime = beta_from_r(r_prime)
print(f"r = {r_prime:.6f} → β_r = {beta_r_prime:.3f}")

unfolded = unfold_primes(primes)
L_values = [1, 2, 5, 10, 20, 50]
beta_sig_prime = {}
sig2_prime = {}
for L in L_values:
    s2 = number_variance_at_L(unfolded, L)
    s2_over_L = s2 / L
    b = beta_from_sig2(s2_over_L, str(L))
    beta_sig_prime[L] = b
    sig2_prime[L] = s2_over_L
    print(f"  L={L:3d}: Σ²/L = {s2_over_L:.4f} → β_Σ = {b:.3f}")

# ── Measure shuffled primes (null) ──────────────────────────────────
print("\n=== PRIMES (shuffled, 20 trials) ===")
n_shuf = 20
r_shuf_list = []
beta_sig_shuf = {L: [] for L in L_values}

for trial in range(n_shuf):
    g_shuf = gaps.copy()
    np.random.shuffle(g_shuf)
    r_shuf_list.append(r_statistic(g_shuf))

    # Reconstruct positions from shuffled gaps
    p_shuf = np.cumsum(np.concatenate([[primes[0]], g_shuf]))
    u_shuf = unfold_primes(p_shuf)
    for L in L_values:
        s2 = number_variance_at_L(u_shuf, L, n_samples=1000)
        beta_sig_shuf[L].append(beta_from_sig2(s2 / L, str(L)))

r_shuf_mean = np.mean(r_shuf_list)
beta_r_shuf = beta_from_r(r_shuf_mean)
print(f"r = {r_shuf_mean:.6f} → β_r = {beta_r_shuf:.3f}")
for L in L_values:
    bm = np.mean(beta_sig_shuf[L])
    print(f"  L={L:3d}: β_Σ = {bm:.3f} ± {np.std(beta_sig_shuf[L]):.3f}")

# ── Measure GUE (positive control) ──────────────────────────────────
print("\n=== GUE (positive control) ===")
gue_g = gue_gaps(n_eigenvalues=1500, n_matrices=4)
r_gue = r_statistic(gue_g)
beta_r_gue = beta_from_r(r_gue)
print(f"r = {r_gue:.6f} → β_r = {beta_r_gue:.3f}")

# For GUE, unfold eigenvalues directly
all_evals = []
for _ in range(4):
    H = np.random.randn(1500, 1500) + 1j * np.random.randn(1500, 1500)
    H = (H + H.conj().T) / 2
    evals = np.sort(np.linalg.eigvalsh(H).real)
    mid = len(evals) // 4
    end = 3 * len(evals) // 4
    bulk = evals[mid:end]
    sp = np.diff(bulk)
    ms = np.mean(sp)
    all_evals.extend((bulk / ms).tolist())

all_evals = np.sort(all_evals)
beta_sig_gue = {}
for L in L_values:
    s2 = number_variance_at_L(all_evals, L, n_samples=1000)
    s2_over_L = s2 / L
    b = beta_from_sig2(s2_over_L, str(L))
    beta_sig_gue[L] = b
    print(f"  L={L:3d}: Σ²/L = {s2_over_L:.4f} → β_Σ = {b:.3f}")


# ── Analysis: β-disagreement ────────────────────────────────────────
print("\n" + "=" * 60)
print("CROSS-OBSERVABLE β DISAGREEMENT")
print("=" * 60)

print(f"\n{'Source':<12} {'β_r':>6} | " + " | ".join(f"β_Σ(L={L})" for L in L_values))
print("-" * 80)

# Primes
vals_prime = [f"{beta_sig_prime[L]:.3f}" for L in L_values]
print(f"{'Primes':<12} {beta_r_prime:>6.3f} | " + " | ".join(f"{v:>9}" for v in vals_prime))

# Shuffle
vals_shuf = [f"{np.mean(beta_sig_shuf[L]):.3f}" for L in L_values]
print(f"{'Shuffle':<12} {beta_r_shuf:>6.3f} | " + " | ".join(f"{v:>9}" for v in vals_shuf))

# GUE
vals_gue = [f"{beta_sig_gue[L]:.3f}" for L in L_values]
print(f"{'GUE':<12} {beta_r_gue:>6.3f} | " + " | ".join(f"{v:>9}" for v in vals_gue))

# Disagreement metric: max |β_r - β_Σ(L)| across L
disagree_prime = max(abs(beta_r_prime - beta_sig_prime[L]) for L in L_values)
disagree_shuf = max(abs(beta_r_shuf - np.mean(beta_sig_shuf[L])) for L in L_values)
disagree_gue = max(abs(beta_r_gue - beta_sig_gue[L]) for L in L_values)

print(f"\nMax β-disagreement:")
print(f"  Primes:  {disagree_prime:.3f}")
print(f"  Shuffle: {disagree_shuf:.3f}")
print(f"  GUE:     {disagree_gue:.3f}")

# Scale dependence of β_Σ for primes
print(f"\nScale dependence of β_Σ for primes:")
print(f"  β_Σ(L=1) - β_Σ(L=50) = {beta_sig_prime[1] - beta_sig_prime[50]:.3f}")
print(f"  (positive = more GUE-like at short range, more Poisson-like at long range)")

# ── Save results ────────────────────────────────────────────────────
results = {
    "timestamp": datetime.now().isoformat(),
    "experiment": "cross_observable_consistency",
    "tension": "META",
    "n_primes": len(primes),
    "primes": {
        "r": float(r_prime),
        "beta_r": float(beta_r_prime),
        "beta_sigma": {str(L): float(beta_sig_prime[L]) for L in L_values},
        "sig2_over_L": {str(L): float(sig2_prime[L]) for L in L_values},
        "max_disagreement": float(disagree_prime),
    },
    "shuffle": {
        "r": float(r_shuf_mean),
        "beta_r": float(beta_r_shuf),
        "beta_sigma_mean": {str(L): float(np.mean(beta_sig_shuf[L])) for L in L_values},
        "beta_sigma_std": {str(L): float(np.std(beta_sig_shuf[L])) for L in L_values},
        "max_disagreement": float(disagree_shuf),
    },
    "gue": {
        "r": float(r_gue),
        "beta_r": float(beta_r_gue),
        "beta_sigma": {str(L): float(beta_sig_gue[L]) for L in L_values},
        "max_disagreement": float(disagree_gue),
    },
}

with open('/opt/MM_D-ND/tools/data/cross_observable_consistency.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to tools/data/cross_observable_consistency.json")
