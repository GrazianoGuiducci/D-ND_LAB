"""
exp_return_map.py — Empirical return map of prime gap ratios
Measures f_emp(r) = E[r_{n+1} | r_n = r] and finds fixed points.
Fixed points: where f_emp(r) = r (the diagonal crossing).

Usage:
    python3 tools/exp_return_map.py [--N_primes 2000000] [--n_bins 50] [--n_shuffles 100]
"""

import numpy as np
import argparse
from sympy import primerange

def compute_return_map(gaps, n_bins=50, r_range=(0.1, 5.0)):
    """Compute empirical return map of gap ratios."""
    # Ratios r_n = g_{n+1}/g_n
    ratios = gaps[1:] / gaps[:-1]
    
    # Bin edges (log-spaced for better coverage)
    bin_edges = np.logspace(np.log10(r_range[0]), np.log10(r_range[1]), n_bins + 1)
    bin_centers = np.sqrt(bin_edges[:-1] * bin_edges[1:])  # geometric mean
    
    # For each bin of r_n, compute E[r_{n+1}]
    f_emp = np.full(n_bins, np.nan)
    f_std = np.full(n_bins, np.nan)
    counts = np.zeros(n_bins, dtype=int)
    
    for i in range(n_bins):
        mask = (ratios[:-1] >= bin_edges[i]) & (ratios[:-1] < bin_edges[i+1])
        counts[i] = mask.sum()
        if counts[i] >= 30:  # minimum for reliable estimate
            f_emp[i] = np.mean(ratios[1:][mask])
            f_std[i] = np.std(ratios[1:][mask]) / np.sqrt(counts[i])
    
    return bin_centers, f_emp, f_std, counts

def find_fixed_points(bin_centers, f_emp):
    """Find where f_emp(r) crosses the diagonal (f_emp = r)."""
    valid = ~np.isnan(f_emp)
    x = bin_centers[valid]
    y = f_emp[valid]
    
    # Find crossings of y - x = 0
    diff = y - x
    crossings = []
    for i in range(len(diff) - 1):
        if diff[i] * diff[i+1] < 0:  # sign change
            # Linear interpolation
            r_cross = x[i] - diff[i] * (x[i+1] - x[i]) / (diff[i+1] - diff[i])
            crossings.append(r_cross)
    
    return np.array(crossings)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N_primes', type=int, default=2000000)
    parser.add_argument('--n_bins', type=int, default=50)
    parser.add_argument('--n_shuffles', type=int, default=200)
    args = parser.parse_args()
    
    phi = (1 + np.sqrt(5)) / 2
    
    print(f"Generating primes up to find {args.N_primes} primes...")
    # Estimate upper bound using PNT
    upper = int(args.N_primes * (np.log(args.N_primes) + np.log(np.log(args.N_primes)) + 2))
    primes = np.array(list(primerange(2, upper)))[:args.N_primes]
    print(f"Got {len(primes)} primes, max = {primes[-1]}")
    
    gaps = np.diff(primes).astype(float)
    print(f"Gaps: {len(gaps)}, mean = {gaps.mean():.2f}, median = {np.median(gaps):.1f}")
    
    # Compute return map for real data
    print("\nComputing return map for real gaps...")
    bin_centers, f_emp, f_std, counts = compute_return_map(gaps, args.n_bins)
    
    # Find fixed points
    fps_real = find_fixed_points(bin_centers, f_emp)
    print(f"\nFixed points of return map (real): {fps_real}")
    print(f"phi = {phi:.6f}, 1/phi = {1/phi:.6f}, 1 = 1.000000")
    for fp in fps_real:
        print(f"  r* = {fp:.6f}, ratio to phi = {fp/phi:.4f}, ratio to 1 = {fp:.4f}")
    
    # Global mean reversion target
    valid = ~np.isnan(f_emp)
    mean_f = np.nanmean(f_emp[valid])
    print(f"\nMean of f_emp (global attractor): {mean_f:.6f}")
    print(f"  vs 1/phi = {1/phi:.6f} (diff = {abs(mean_f - 1/phi):.6f})")
    print(f"  vs 1.0 = (diff = {abs(mean_f - 1.0):.6f})")
    
    # Slope at fixed point (stability)
    for fp in fps_real:
        # Find nearest bin
        idx = np.argmin(np.abs(bin_centers - fp))
        if idx > 0 and idx < len(f_emp) - 1 and not np.isnan(f_emp[idx-1]) and not np.isnan(f_emp[idx+1]):
            slope = (f_emp[idx+1] - f_emp[idx-1]) / (bin_centers[idx+1] - bin_centers[idx-1])
            print(f"  Slope at r*={fp:.4f}: {slope:.4f} ({'stable' if abs(slope) < 1 else 'unstable'})")
    
    # Shuffle null test
    print(f"\nRunning {args.n_shuffles} shuffles for null baseline...")
    fps_shuffle_all = []
    f_emp_shuffles = []
    
    for s in range(args.n_shuffles):
        gaps_shuf = gaps.copy()
        np.random.shuffle(gaps_shuf)
        bc_s, fe_s, _, _ = compute_return_map(gaps_shuf, args.n_bins)
        fps_s = find_fixed_points(bc_s, fe_s)
        fps_shuffle_all.append(fps_s)
        f_emp_shuffles.append(fe_s)
    
    # Statistics on shuffle fixed points
    fps_counts = [len(fps) for fps in fps_shuffle_all]
    print(f"Shuffle fixed points: mean count = {np.mean(fps_counts):.1f}, std = {np.std(fps_counts):.2f}")
    print(f"Real fixed points count: {len(fps_real)}")
    
    # Mean shuffle return map
    f_emp_shuf_mean = np.nanmean(f_emp_shuffles, axis=0)
    fps_shuffle_mean = find_fixed_points(bin_centers, f_emp_shuf_mean)
    print(f"Fixed points of MEAN shuffle return map: {fps_shuffle_mean}")
    
    # Compare real vs shuffle at each bin
    print("\n--- Return map comparison (real vs shuffle) ---")
    print(f"{'r':>8} {'f_real':>8} {'f_shuf':>8} {'diff':>8} {'z-score':>8} {'N':>6}")
    f_emp_shuf_std = np.nanstd(f_emp_shuffles, axis=0)
    
    for i in range(len(bin_centers)):
        if not np.isnan(f_emp[i]) and not np.isnan(f_emp_shuf_mean[i]) and f_emp_shuf_std[i] > 0:
            z = (f_emp[i] - f_emp_shuf_mean[i]) / f_emp_shuf_std[i]
            if abs(z) > 2 or abs(bin_centers[i] - 1.0) < 0.3:  # show significant or near r=1
                print(f"{bin_centers[i]:8.3f} {f_emp[i]:8.4f} {f_emp_shuf_mean[i]:8.4f} {f_emp[i]-f_emp_shuf_mean[i]:8.4f} {z:8.2f} {counts[i]:6d}")
    
    # Key structural question: does the return map show mean reversion to a SPECIFIC value?
    # For shuffle, f_emp should be ~constant (no memory), so f(r) ≈ <r> for all r
    # For real, if there's structure, f(r) should depend on r
    
    # Measure: variance of f_emp across bins (real vs shuffle)
    var_real = np.nanvar(f_emp[valid])
    var_shuffles = [np.nanvar(fe[valid]) for fe in f_emp_shuffles]
    z_var = (var_real - np.mean(var_shuffles)) / np.std(var_shuffles)
    print(f"\nVariance of return map: real = {var_real:.6f}, shuffle = {np.mean(var_shuffles):.6f}")
    print(f"z-score (variance excess): {z_var:.2f}")
    
    # Conditional mean at extremes vs center
    low_mask = bin_centers < 0.5
    high_mask = bin_centers > 2.0
    mid_mask = (bin_centers >= 0.8) & (bin_centers <= 1.2)
    
    f_low = np.nanmean(f_emp[low_mask & valid])
    f_high = np.nanmean(f_emp[high_mask & valid])
    f_mid = np.nanmean(f_emp[mid_mask & valid])
    
    print(f"\nMean reversion structure:")
    print(f"  After small ratio (r<0.5): f = {f_low:.4f} (expect >1 if mean-reverting)")
    print(f"  After unit ratio (0.8<r<1.2): f = {f_mid:.4f}")  
    print(f"  After large ratio (r>2.0): f = {f_high:.4f} (expect <1 if mean-reverting)")
    print(f"  Reversion amplitude: {f_low - f_high:.4f}")
    
    # Same for shuffle
    f_low_s = np.nanmean(f_emp_shuf_mean[low_mask & ~np.isnan(f_emp_shuf_mean)])
    f_high_s = np.nanmean(f_emp_shuf_mean[high_mask & ~np.isnan(f_emp_shuf_mean)])
    print(f"  Shuffle reversion amplitude: {f_low_s - f_high_s:.4f}")
    print(f"  Structural excess: {(f_low - f_high) - (f_low_s - f_high_s):.4f}")
    
    # Output summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Fixed points (real data): {[f'{x:.4f}' for x in fps_real]}")
    print(f"Fixed points (shuffle mean): {[f'{x:.4f}' for x in fps_shuffle_mean]}")
    print(f"Return map variance z-score: {z_var:.2f}")
    print(f"Mean reversion amplitude (real): {f_low - f_high:.4f}")
    print(f"Mean reversion amplitude (shuffle): {f_low_s - f_high_s:.4f}")
    print(f"phi = {phi:.6f}")
    
if __name__ == '__main__':
    main()
