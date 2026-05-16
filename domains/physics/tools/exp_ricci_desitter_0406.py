"""Test: Ricci scalar from prime metric g_n=(p_n/2)^2 in t=ln(p) coordinates.
If de Sitter 1+1D, expect R=2. Compare with shuffled-gap null baseline."""
import numpy as np
from sympy import primerange

primes = np.array(list(primerange(2, 500_000)), dtype=np.float64)
N = len(primes)

t = np.log(primes)          # coordinate time
a = primes / 2.0            # scale factor a(t) = p/2

# Discrete Ricci scalar: R = -2 * a''/a  (1+1D FLRW)
# Use central finite differences
dt = np.diff(t)
da = np.diff(a)
a_dot = da / dt  # a'(t) at midpoints

dt2 = (dt[:-1] + dt[1:]) / 2.0
a_ddot = np.diff(a_dot) / dt2  # a''(t)
a_mid = a[1:-1]

R = -2.0 * a_ddot / a_mid

# Windowed statistics
windows = [(100, 1000), (1000, 10000), (10000, len(R))]
print("=== Ricci scalar R from prime metric ===")
print(f"Total primes: {N}, R samples: {len(R)}")
for lo, hi in windows:
    seg = R[lo:hi]
    print(f"  [{lo}:{hi}] mean(R)={np.mean(seg):.4f}  std={np.std(seg):.4f}  median={np.median(seg):.4f}")

# Null baseline: shuffled gaps -> fake primes -> same computation
gaps = np.diff(primes)
rng = np.random.default_rng(42)
R_null = []
for _ in range(5):
    sg = rng.permutation(gaps)
    fp = np.cumsum(np.concatenate([[primes[0]], sg]))
    ft, fa = np.log(fp), fp / 2.0
    fdt = np.diff(ft)
    fda = np.diff(fa)
    fad = fda / fdt
    fdt2 = (fdt[:-1] + fdt[1:]) / 2.0
    fadd = np.diff(fad) / fdt2
    fR = -2.0 * fadd / fp[1:-1]
    R_null.append(np.mean(fR[1000:]))

print(f"\n  Null (shuffled gaps, 5 runs): mean(R)={np.mean(R_null):.4f} +/- {np.std(R_null):.4f}")
print(f"  Prime R (1000+): {np.mean(R[1000:]):.4f}")
print(f"  Ratio prime/null: {np.mean(R[1000:])/np.mean(R_null):.4f}")
print(f"\n  de Sitter prediction R=2.0, observed R={np.mean(R[1000:]):.4f}")
