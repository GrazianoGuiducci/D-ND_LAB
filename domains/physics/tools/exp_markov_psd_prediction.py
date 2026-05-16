#!/usr/bin/env python3
"""
exp_markov_psd_prediction.py — Analytical Markov PSD vs measured residue PSD

Question: Does the Z/6Z Markov chain analytically predict the residue channel's
PSD slope (+0.160 measured)? If yes → residue PSD is algebraic. If no → the
spectral slope carries number-theoretic content beyond the ACF amplitude.

Design:
- Extract empirical Z/6Z transition matrix from primes
- Compute analytical PSD of 2-state Markov chain: S(f) = 2*Re[(I - P*e^{-2πif})^{-1}]
- Generate N_synth synthetic Markov sequences, compute PSD
- Compare with measured prime residue PSD
- Null baseline: i.i.d. Bernoulli with same marginal (no memory)

Usage:
  python exp_markov_psd_prediction.py [--N 2000000] [--n_synth 20] [--nperseg 4096]
"""

import numpy as np
from scipy.signal import welch
from scipy.stats import linregress
import argparse, json, time

def get_primes_sieve(n_max):
    """Sieve of Eratosthenes up to n_max."""
    sieve = np.ones(n_max // 2, dtype=bool)
    for i in range(3, int(n_max**0.5) + 1, 2):
        if sieve[i // 2]:
            sieve[i*i // 2::i] = False
    primes = np.empty(sieve.sum() + 1, dtype=np.int64)
    primes[0] = 2
    primes[1:] = 2 * np.nonzero(sieve)[0] + 1
    return primes

def residue_sequence(primes):
    """Map primes > 3 to residue class: 1 mod 6 → 0, 5 mod 6 → 1."""
    p = primes[primes > 3]
    return (p % 6 == 5).astype(int), p

def transition_matrix(res_seq):
    """Empirical 2x2 transition matrix from residue sequence."""
    T = np.zeros((2, 2))
    for i in range(len(res_seq) - 1):
        T[res_seq[i], res_seq[i+1]] += 1
    # Normalize rows
    T[0] /= T[0].sum()
    T[1] /= T[1].sum()
    return T

def analytical_markov_psd(P, freqs):
    """
    Analytical PSD of a 2-state Markov chain.
    
    For stationary Markov chain with transition matrix P and stationary
    distribution π, the autocorrelation is:
      R(k) = π_0*π_1*(λ_2)^|k|  (for the indicator of state 1)
    where λ_2 is the second eigenvalue of P.
    
    PSD = Σ_k R(k) e^{-2πifk} = π_0*π_1 * 2*Re[1/(1 - λ_2*e^{-2πif})] - π_0*π_1
    
    But more precisely for the centered process X_n - μ:
    S(f) = var(X) * (1 - λ_2^2) / |1 - λ_2*e^{-2πif}|^2
    """
    # Stationary distribution
    # π P = π → π_0 = P[1,0]/(P[0,1]+P[1,0]), π_1 = P[0,1]/(P[0,1]+P[1,0])
    a = P[0, 1]  # 0→1
    b = P[1, 0]  # 1→0
    pi0 = b / (a + b)
    pi1 = a / (a + b)
    
    # Second eigenvalue
    lam2 = 1 - a - b  # = P[0,0] + P[1,1] - 1
    
    # Variance of indicator
    var_X = pi0 * pi1
    
    # PSD of centered process
    # S(f) = var_X * (1 - lam2^2) / |1 - lam2 * e^{-2πif}|^2
    z = np.exp(-2j * np.pi * freqs)
    denom = np.abs(1 - lam2 * z)**2
    S = var_X * (1 - lam2**2) / denom
    
    return S, {'pi0': pi0, 'pi1': pi1, 'lam2': lam2, 'var_X': var_X}

def compute_psd(seq, nperseg=4096):
    """Welch PSD of a binary sequence (centered)."""
    x = seq - seq.mean()
    f, S = welch(x, fs=1.0, nperseg=nperseg, noverlap=nperseg//2)
    return f, S

def spectral_slope(f, S, fmin=0.01, fmax=0.45):
    """Log-log slope of PSD in frequency range."""
    mask = (f >= fmin) & (f <= fmax) & (f > 0) & (S > 0)
    if mask.sum() < 5:
        return np.nan, np.nan, np.nan
    lf = np.log10(f[mask])
    lS = np.log10(S[mask])
    res = linregress(lf, lS)
    return res.slope, res.rvalue**2, res.stderr

def generate_markov(P, n, pi0=None):
    """Generate Markov chain of length n."""
    if pi0 is None:
        a, b = P[0, 1], P[1, 0]
        pi0 = b / (a + b)
    seq = np.empty(n, dtype=int)
    seq[0] = 0 if np.random.random() < pi0 else 1
    rands = np.random.random(n - 1)
    for i in range(n - 1):
        seq[i+1] = 0 if rands[i] >= P[seq[i], 1] else 1
    return seq

def generate_bernoulli(pi1, n):
    """i.i.d. Bernoulli (no memory) with same marginal."""
    return (np.random.random(n) < pi1).astype(int)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=2_000_000, help='Number of primes')
    parser.add_argument('--n_synth', type=int, default=20, help='Synthetic trials')
    parser.add_argument('--nperseg', type=int, default=4096, help='Welch segment size')
    args = parser.parse_args()

    t0 = time.time()
    
    # --- Step 1: Get primes and residue sequence ---
    print(f"Sieving primes (target {args.N})...")
    # Estimate sieve limit (PNT: p_n ~ n*ln(n))
    est = int(args.N * (np.log(args.N) + np.log(np.log(args.N))) * 1.1)
    primes = get_primes_sieve(est)
    if len(primes) < args.N:
        primes = get_primes_sieve(int(est * 1.3))
    primes = primes[:args.N]
    print(f"  Got {len(primes)} primes up to {primes[-1]}")
    
    res_seq, p_used = residue_sequence(primes)
    N = len(res_seq)
    print(f"  Residue sequence length: {N}")
    
    # --- Step 2: Empirical transition matrix ---
    P = transition_matrix(res_seq)
    a = P[0, 1]  # prob(1→5)
    b = P[1, 0]  # prob(5→1)
    lam2 = 1 - a - b
    pi1 = a / (a + b)
    print(f"\n  Transition matrix:")
    print(f"    P(1→1)={P[0,0]:.6f}  P(1→5)={P[0,1]:.6f}")
    print(f"    P(5→1)={P[1,0]:.6f}  P(5→5)={P[1,1]:.6f}")
    print(f"  λ₂ = {lam2:.6f}")
    print(f"  π(class 5) = {pi1:.6f}")
    print(f"  Chebyshev bias: P(1→5)={a:.4f} vs P(5→1)={b:.4f}, diff={a-b:.6f}")
    
    # --- Step 3: Compute prime residue PSD ---
    print(f"\nComputing prime residue PSD (nperseg={args.nperseg})...")
    f_prime, S_prime = compute_psd(res_seq, nperseg=args.nperseg)
    slope_prime, r2_prime, se_prime = spectral_slope(f_prime, S_prime)
    print(f"  Prime residue slope: {slope_prime:+.4f} (R²={r2_prime:.4f}, SE={se_prime:.4f})")
    
    # --- Step 4: Analytical Markov PSD ---
    print(f"\nAnalytical Markov PSD...")
    f_pos = f_prime[f_prime > 0]
    S_analytical, params = analytical_markov_psd(P, f_pos)
    slope_analytical, r2_analytical, se_analytical = spectral_slope(f_pos, S_analytical)
    print(f"  Analytical Markov slope: {slope_analytical:+.4f} (R²={r2_analytical:.4f})")
    
    # Scale analytical to match normalization
    # Welch PSD has specific normalization; analytical is the theoretical spectral density
    # We compare SHAPES (slopes), not absolute amplitudes
    
    # --- Step 5: Synthetic Markov PSD ---
    print(f"\nGenerating {args.n_synth} synthetic Markov sequences...")
    slopes_markov = []
    for i in range(args.n_synth):
        seq = generate_markov(P, N)
        f_m, S_m = compute_psd(seq, nperseg=args.nperseg)
        sl, r2, se = spectral_slope(f_m, S_m)
        slopes_markov.append(sl)
    slopes_markov = np.array(slopes_markov)
    mean_markov = slopes_markov.mean()
    std_markov = slopes_markov.std()
    print(f"  Markov synthetic slope: {mean_markov:+.4f} ± {std_markov:.4f}")
    
    # --- Step 6: Bernoulli baseline (no memory) ---
    print(f"\nGenerating {args.n_synth} Bernoulli (i.i.d.) sequences...")
    slopes_bern = []
    for i in range(args.n_synth):
        seq = generate_bernoulli(pi1, N)
        f_b, S_b = compute_psd(seq, nperseg=args.nperseg)
        sl, r2, se = spectral_slope(f_b, S_b)
        slopes_bern.append(sl)
    slopes_bern = np.array(slopes_bern)
    mean_bern = slopes_bern.mean()
    std_bern = slopes_bern.std()
    print(f"  Bernoulli slope: {mean_bern:+.4f} ± {std_bern:.4f}")
    
    # --- Step 7: z-scores ---
    z_markov = (slope_prime - mean_markov) / std_markov if std_markov > 0 else np.inf
    z_bern = (slope_prime - mean_bern) / std_bern if std_bern > 0 else np.inf
    z_analytical = (slope_prime - slope_analytical) / se_prime if se_prime > 0 else np.inf
    
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Prime residue PSD slope:      {slope_prime:+.4f} (R²={r2_prime:.4f})")
    print(f"  Analytical Markov PSD slope:   {slope_analytical:+.4f} (R²={r2_analytical:.4f})")
    print(f"  Synthetic Markov PSD slope:    {mean_markov:+.4f} ± {std_markov:.4f}")
    print(f"  Bernoulli (no memory) slope:   {mean_bern:+.4f} ± {std_bern:.4f}")
    print(f"")
    print(f"  z(prime vs Markov synthetic):  {z_markov:+.2f}")
    print(f"  z(prime vs analytical):        {z_analytical:+.2f}")
    print(f"  z(prime vs Bernoulli):         {z_bern:+.2f}")
    
    # --- Step 8: Decompose what Markov captures ---
    # Ratio of slopes: how much of the prime slope does Markov explain?
    if slope_prime != 0:
        ratio_markov = mean_markov / slope_prime
        ratio_analytical = slope_analytical / slope_prime
    else:
        ratio_markov = ratio_analytical = np.nan
    
    print(f"\n  Markov captures {ratio_markov*100:.1f}% of prime residue slope")
    print(f"  Analytical captures {ratio_analytical*100:.1f}% of prime residue slope")
    
    # --- Step 9: Scale dependence ---
    # Split primes into windows and check if the gap changes with scale
    print(f"\n--- Scale dependence of Markov gap ---")
    n_windows = 5
    win_size = N // n_windows
    scale_results = []
    for w in range(n_windows):
        start = w * win_size
        end = start + win_size
        chunk = res_seq[start:end]
        p_mid = p_used[(start + end) // 2]
        
        # Prime residue slope for this window
        f_w, S_w = compute_psd(chunk, nperseg=min(args.nperseg, win_size//4))
        sl_w, r2_w, _ = spectral_slope(f_w, S_w)
        
        # Local transition matrix
        P_local = transition_matrix(chunk)
        lam2_local = 1 - P_local[0, 1] - P_local[1, 0]
        
        # Generate local Markov synthetics  
        slopes_local = []
        for _ in range(10):
            syn = generate_markov(P_local, win_size)
            f_s, S_s = compute_psd(syn, nperseg=min(args.nperseg, win_size//4))
            sl_s, _, _ = spectral_slope(f_s, S_s)
            slopes_local.append(sl_s)
        mean_local = np.mean(slopes_local)
        gap = sl_w - mean_local
        
        scale_results.append({
            'ln_p': float(np.log(p_mid)),
            'p_mid': int(p_mid),
            'slope_prime': float(sl_w),
            'slope_markov': float(mean_local),
            'gap': float(gap),
            'lam2': float(lam2_local)
        })
        print(f"  ln(p)={np.log(p_mid):.1f}: prime={sl_w:+.4f}, markov={mean_local:+.4f}, gap={gap:+.4f}, λ₂={lam2_local:.5f}")
    
    # Fit gap vs ln(p)
    lnp_arr = np.array([r['ln_p'] for r in scale_results])
    gap_arr = np.array([r['gap'] for r in scale_results])
    if len(lnp_arr) >= 3:
        gap_fit = linregress(lnp_arr, gap_arr)
        print(f"  Gap trend: {gap_fit.slope:+.5f}/ln(p) (R²={gap_fit.rvalue**2:.3f})")
    
    elapsed = time.time() - t0
    print(f"\n  Elapsed: {elapsed:.1f}s")
    
    # --- Output ---
    results = {
        'N_primes': int(args.N),
        'N_residue': int(N),
        'transition_matrix': P.tolist(),
        'lam2': float(lam2),
        'chebyshev_bias': float(a - b),
        'slope_prime': float(slope_prime),
        'slope_analytical': float(slope_analytical),
        'slope_markov_mean': float(mean_markov),
        'slope_markov_std': float(std_markov),
        'slope_bernoulli_mean': float(mean_bern),
        'slope_bernoulli_std': float(std_bern),
        'z_prime_vs_markov': float(z_markov),
        'z_prime_vs_analytical': float(z_analytical),
        'z_prime_vs_bernoulli': float(z_bern),
        'ratio_markov': float(ratio_markov),
        'ratio_analytical': float(ratio_analytical),
        'r2_prime': float(r2_prime),
        'r2_analytical': float(r2_analytical),
        'scale_results': scale_results,
        'elapsed_s': float(elapsed)
    }
    
    out_path = '/opt/MM_D-ND/tools/data/exp_markov_psd_prediction.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {out_path}")
    
    return results

if __name__ == '__main__':
    main()
