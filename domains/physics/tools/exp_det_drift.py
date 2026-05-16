#!/usr/bin/env python3
"""
exp_det_drift.py — Measure det(M) of gap transfer matrix across prime scales.

Hypothesis (from operator tension DUALITA_DIPOLARE_VS_ILLUSORIA):
  Dipolar duality = det(M) ~ -1 (generative, structured).
  Illusory duality = det(M) ~ +1 (dispersive, entropic).
  If primes drift toward Poisson, det(M) should drift toward +1.

Method:
  For each scale window of N consecutive prime gaps g_i:
    Build vectors x = (g_i, g_{i-1}), y = (g_{i+1}, g_i)  [state-space embedding]
    Fit 2x2 matrix M via least squares: y = M @ x
    Compute det(M), trace(M), eigenvalues
  
  Null baseline: shuffled gaps (same distribution, destroyed order).
  
  Output: det(M) vs ln(p) — does it drift?
"""

import numpy as np
from sympy import nextprime
import json
from pathlib import Path

def generate_primes(n_primes, start=2):
    """Generate n_primes primes starting from start."""
    primes = []
    p = start
    for _ in range(n_primes):
        primes.append(p)
        p = int(nextprime(p))
    return np.array(primes)

def fit_transfer_matrix(gaps):
    """Fit 2x2 transfer matrix M: (g_{i+1}, g_i) = M @ (g_i, g_{i-1})."""
    n = len(gaps)
    # State vectors: x_i = (g_i, g_{i-1}), y_i = (g_{i+1}, g_i)
    X = np.column_stack([gaps[1:n-1], gaps[0:n-2]]).T  # 2 x (n-2)
    Y = np.column_stack([gaps[2:n], gaps[1:n-1]]).T      # 2 x (n-2)
    # Least squares: M = Y @ X^T @ (X @ X^T)^{-1}
    XXT = X @ X.T
    YXT = Y @ X.T
    try:
        M = YXT @ np.linalg.inv(XXT)
        det_M = np.linalg.det(M)
        tr_M = np.trace(M)
        eigvals = np.linalg.eigvals(M)
        return M, det_M, tr_M, eigvals
    except np.linalg.LinAlgError:
        return None, None, None, None

def main():
    print("=== det(M) Drift Across Prime Scales ===\n")
    
    # Generate primes in scale windows
    # Use logarithmically spaced starting points
    starts = [100, 1000, 10_000, 100_000, 1_000_000, 10_000_000, 50_000_000]
    window_size = 50_000  # gaps per window
    n_shuffles = 20
    
    results = []
    
    for s in starts:
        print(f"--- Scale: p ~ {s:,} ---")
        primes = generate_primes(window_size + 1, start=s)
        gaps = np.diff(primes)
        median_p = float(np.median(primes))
        ln_p = np.log(median_p)
        
        # Fit on real gaps
        M, det_M, tr_M, eigvals = fit_transfer_matrix(gaps)
        if M is None:
            print("  SKIP: singular matrix")
            continue
        
        # Null: shuffled gaps (same marginal distribution, destroyed order)
        det_shuffled = []
        for _ in range(n_shuffles):
            sg = gaps.copy()
            np.random.shuffle(sg)
            _, d, _, _ = fit_transfer_matrix(sg)
            if d is not None:
                det_shuffled.append(d)
        
        det_shuf_mean = np.mean(det_shuffled)
        det_shuf_std = np.std(det_shuffled)
        z_score = (det_M - det_shuf_mean) / det_shuf_std if det_shuf_std > 0 else 0
        
        print(f"  median p = {median_p:.0f}, ln(p) = {ln_p:.2f}")
        print(f"  det(M) = {det_M:.6f}")
        print(f"  trace(M) = {tr_M:.6f}")
        print(f"  eigenvalues = {eigvals[0]:.4f}, {eigvals[1]:.4f}")
        print(f"  det(M_shuffled) = {det_shuf_mean:.6f} +/- {det_shuf_std:.6f}")
        print(f"  z-score = {z_score:.2f}")
        print()
        
        results.append({
            'start_prime': int(s),
            'median_prime': float(median_p),
            'ln_p': float(ln_p),
            'det_M': float(det_M),
            'trace_M': float(tr_M),
            'eig_1': complex(eigvals[0]).real,
            'eig_2': complex(eigvals[1]).real,
            'eig_1_imag': complex(eigvals[0]).imag,
            'eig_2_imag': complex(eigvals[1]).imag,
            'det_shuffled_mean': float(det_shuf_mean),
            'det_shuffled_std': float(det_shuf_std),
            'z_score': float(z_score),
            'window_size': window_size,
        })
    
    # Summary: linear fit of det(M) vs ln(p)
    ln_ps = np.array([r['ln_p'] for r in results])
    dets = np.array([r['det_M'] for r in results])
    det_shuf = np.array([r['det_shuffled_mean'] for r in results])
    
    # Linear fit
    coeffs = np.polyfit(ln_ps, dets, 1)
    slope, intercept = coeffs
    predicted = np.polyval(coeffs, ln_ps)
    ss_res = np.sum((dets - predicted)**2)
    ss_tot = np.sum((dets - np.mean(dets))**2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    
    print("=== SUMMARY ===")
    print(f"det(M) = {intercept:.6f} + {slope:.6f} * ln(p)")
    print(f"R^2 = {r_squared:.4f}")
    print(f"det range: {dets.min():.6f} to {dets.max():.6f}")
    print(f"det_shuffled range: {det_shuf.min():.6f} to {det_shuf.max():.6f}")
    zs = ", ".join(f"{r['z_score']:.1f}" for r in results)
    print(f"All z-scores: [{zs}]")
    
    # Does det drift toward +1?
    if slope > 0:
        # Extrapolate to det = +1
        if slope > 0 and intercept < 1:
            p_star = np.exp((1.0 - intercept) / slope)
            print(f"\nExtrapolation: det(M) -> +1 at p* ~ {p_star:.2e}")
    elif slope < 0:
        print(f"\ndet(M) DECREASES with scale (away from +1)")
        if intercept > -1:
            p_star = np.exp((-1.0 - intercept) / slope)
            print(f"Extrapolation: det(M) -> -1 at p* ~ {p_star:.2e}")
    
    # Save
    output = {
        'experiment': 'det_drift',
        'results': results,
        'fit': {
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r_squared),
        }
    }
    out_path = Path('/opt/MM_D-ND/tools/data/exp_det_drift.json')
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {out_path}")

if __name__ == '__main__':
    main()
