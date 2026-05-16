#!/usr/bin/env python3
"""
exp_spectral_2d.py — The 2D spectral plane: <r> vs acf1.

The spectral landscape (exp_spectral_landscape.py) revealed that <r> alone
doesn't separate primes from Berry-Robnik mixtures. But acf1 does.

Question: What creates primes' unique position (r~0.48, acf1~-0.10)?
Hypothesis: The mod-6 confinement (F2) forces gap alternation, creating
sequential anti-correlation mechanically.

Test:
1. Primes: (r, acf1) as measured
2. Berry-Robnik sweep: rho from 0 to 1 — traces a path in (r, acf1)
3. Mod-6 constrained random: gaps drawn from prime distribution, forced to
   alternate between mod-6 classes → isolates confinement contribution
4. Anti-correlated Poisson: Poisson gaps with imposed negative acf1 →
   what <r> results from pure anti-correlation?

If mod-6 model matches primes' (r, acf1): the confinement explains everything.
If not: something deeper than mod-6 creates the prime signature.

Usage:
    python exp_spectral_2d.py [--N 10000] [--surrogates 20]
"""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import gamma as gamma_fn
import json, sys, os
from datetime import datetime

N_DEFAULT = 10000
N_SURROGATES = 20


# ─── Observables ──────────────────────────────────────────────────

def ratio_statistic(spacings):
    s = spacings[spacings > 0]
    if len(s) < 3:
        return np.nan
    r = np.minimum(s[:-1], s[1:]) / np.maximum(s[:-1], s[1:])
    return np.mean(r)

def brody_beta(spacings):
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
    s = spacings - np.mean(spacings)
    if np.var(spacings) < 1e-15:
        return np.nan
    c0 = np.mean(s ** 2)
    c1 = np.mean(s[:-1] * s[1:])
    return c1 / c0 if c0 > 0 else np.nan


# ─── Domain generators ──────────────────────────────────────────

def gen_primes(n_spacings):
    """Prime gaps, unfolded by local density."""
    limit = int(n_spacings * 15 * np.log(max(n_spacings * 15, 100)))
    limit = max(limit, 200000)
    sieve = np.ones(limit, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    primes = np.where(sieve)[0].astype(float)
    primes = primes[:n_spacings + 1]
    gaps = np.diff(primes)
    w = min(50, len(gaps) // 5)
    kernel = np.ones(w) / w
    local_mean = np.convolve(gaps, kernel, mode='same')
    local_mean[local_mean < 0.1] = 1.0
    return gaps / local_mean

def gen_primes_raw_gaps(n_spacings):
    """Raw prime gaps (not unfolded) for distribution sampling."""
    limit = int(n_spacings * 15 * np.log(max(n_spacings * 15, 100)))
    limit = max(limit, 200000)
    sieve = np.ones(limit, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    primes = np.where(sieve)[0].astype(float)
    primes = primes[2:]  # skip 2,3 for mod-6 analysis
    gaps = np.diff(primes[:n_spacings + 1])
    return gaps

def gen_gue(n_spacings):
    N = n_spacings + 50
    H = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    H = (H + H.conj().T) / 2
    eigs = np.sort(np.linalg.eigvalsh(H).real)
    spacings = np.diff(eigs)
    local_mean = np.convolve(spacings, np.ones(30)/30, mode='same')
    local_mean[local_mean < 1e-10] = 1e-10
    return spacings / local_mean

def gen_berry_robnik(n_spacings, rho=0.5):
    n_chaotic = int(rho * n_spacings)
    n_regular = n_spacings - n_chaotic
    s_chaotic = gen_gue(n_chaotic) if n_chaotic > 50 else np.random.exponential(1.0, n_chaotic)
    s_regular = np.random.exponential(1.0, n_regular)
    s = np.concatenate([s_chaotic, s_regular])
    np.random.shuffle(s)
    return s[:n_spacings]


# ─── New synthetic models ─────────────────────────────────────────

def gen_mod6_constrained(n_spacings):
    """
    Model: gaps drawn from empirical prime gap distribution,
    but constrained to alternate mod-6 residue classes.

    Primes > 3 are ≡ 1 or 5 (mod 6). From class 1: gaps are 4 or 0 (mod 6).
    From class 5: gaps are 2 or 0 (mod 6). Multiples of 6 stay in same class.

    This model preserves the mod-6 structure but randomizes gap magnitudes.
    """
    # Get empirical prime gap distribution
    raw_gaps = gen_primes_raw_gaps(max(n_spacings * 2, 20000))

    # Separate gaps by type:
    # from class-1 primes: gap ≡ 4 mod 6 (switch to class 5) or ≡ 0 mod 6 (stay)
    # from class-5 primes: gap ≡ 2 mod 6 (switch to class 1) or ≡ 0 mod 6 (stay)
    gaps_switch_1to5 = raw_gaps[raw_gaps % 6 == 4]  # from 1, gap≡4→5
    gaps_switch_5to1 = raw_gaps[raw_gaps % 6 == 2]  # from 5, gap≡2→1
    gaps_stay = raw_gaps[raw_gaps % 6 == 0]          # stay in same class

    # Build a sequence that respects mod-6 alternation
    state = 1  # start at class 1
    gaps = []
    for _ in range(n_spacings):
        # Decide: switch class or stay?
        # Use empirical switch probability
        p_switch = len(gaps_switch_1to5 if state == 1 else gaps_switch_5to1) / len(raw_gaps)

        if np.random.random() < p_switch:
            if state == 1:
                g = np.random.choice(gaps_switch_1to5) if len(gaps_switch_1to5) > 0 else 4
                state = 5
            else:
                g = np.random.choice(gaps_switch_5to1) if len(gaps_switch_5to1) > 0 else 2
                state = 1
        else:
            g = np.random.choice(gaps_stay) if len(gaps_stay) > 0 else 6
        gaps.append(g)

    gaps = np.array(gaps, dtype=float)
    # Unfold
    w = min(50, len(gaps) // 5)
    kernel = np.ones(w) / w
    local_mean = np.convolve(gaps, kernel, mode='same')
    local_mean[local_mean < 0.1] = 1.0
    return gaps / local_mean


def gen_alternating_magnitude(n_spacings):
    """
    Model: Poisson gaps, but forced to alternate large-small.
    Tests: does magnitude alternation alone create the prime signature?
    """
    gaps = np.random.exponential(1.0, n_spacings)
    # Sort into small and large halves
    sorted_gaps = np.sort(gaps)
    small = sorted_gaps[:n_spacings // 2]
    large = sorted_gaps[n_spacings // 2:]
    np.random.shuffle(small)
    np.random.shuffle(large)
    # Interleave: small, large, small, large...
    result = np.empty(n_spacings)
    n_pairs = min(len(small), len(large))
    result[:2*n_pairs:2] = small[:n_pairs]
    result[1:2*n_pairs:2] = large[:n_pairs]
    if 2*n_pairs < n_spacings:
        result[2*n_pairs:] = gaps[2*n_pairs:]
    return result


def gen_anticorr_poisson(n_spacings, strength=0.3):
    """
    Model: Exponential gaps with injected negative lag-1 correlation.
    g_{n+1} = (1-s)*exponential + s*(2*mean - g_n)  [reflect from mean]
    Tests: what <r> does pure anti-correlation produce?
    """
    result = np.zeros(n_spacings)
    result[0] = np.random.exponential(1.0)
    for i in range(1, n_spacings):
        noise = np.random.exponential(1.0)
        reflected = max(0.01, 2.0 - result[i-1])  # reflect around mean=1
        result[i] = (1 - strength) * noise + strength * reflected
    return result / np.mean(result)


def gen_markov_mod6(n_spacings):
    """
    Markov chain on mod-6 states with empirical transition probabilities from primes.
    More faithful model: the gap DISTRIBUTION depends on current state.
    """
    raw_gaps = gen_primes_raw_gaps(max(n_spacings * 2, 20000))

    # Compute actual primes to get state sequence
    limit = max(n_spacings * 20, 200000)
    sieve = np.ones(limit, dtype=bool)
    sieve[:2] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i*i::i] = False
    primes = np.where(sieve)[0]
    primes = primes[2:]  # skip 2,3

    # State = prime mod 6 (always 1 or 5)
    states = primes[:len(raw_gaps)+1] % 6
    gaps_by_state = {1: [], 5: []}
    for i in range(len(raw_gaps)):
        s = int(states[i])
        if s in gaps_by_state:
            gaps_by_state[s].append(raw_gaps[i])

    for k in gaps_by_state:
        gaps_by_state[k] = np.array(gaps_by_state[k])

    # Transition matrix
    trans = {1: {1: 0, 5: 0}, 5: {1: 0, 5: 0}}
    for i in range(len(states) - 1):
        s_from = int(states[i])
        s_to = int(states[i+1])
        if s_from in trans and s_to in trans[s_from]:
            trans[s_from][s_to] += 1

    # Normalize
    for s in trans:
        total = sum(trans[s].values())
        if total > 0:
            for t in trans[s]:
                trans[s][t] /= total

    # Generate
    state = 1
    gaps = []
    for _ in range(n_spacings):
        if len(gaps_by_state.get(state, [])) > 0:
            g = np.random.choice(gaps_by_state[state])
        else:
            g = 6.0
        gaps.append(g)
        # Transition
        if np.random.random() < trans.get(state, {}).get(5, 0.5):
            state = 5
        else:
            state = 1

    gaps = np.array(gaps, dtype=float)
    w = min(50, len(gaps) // 5)
    kernel = np.ones(w) / w
    local_mean = np.convolve(gaps, kernel, mode='same')
    local_mean[local_mean < 0.1] = 1.0
    return gaps / local_mean


# ─── Main ──────────────────────────────────────────────────────────

def measure(spacings, n_surrogates=20):
    """Measure observables + shuffled null."""
    spacings = spacings[np.isfinite(spacings) & (spacings > 0)]
    if len(spacings) < 100:
        return None

    r = ratio_statistic(spacings)
    beta = brody_beta(spacings)
    acf = gap_acf1(spacings)

    r_s, beta_s, acf_s = [], [], []
    for _ in range(n_surrogates):
        sh = spacings.copy()
        np.random.shuffle(sh)
        r_s.append(ratio_statistic(sh))
        beta_s.append(brody_beta(sh))
        acf_s.append(gap_acf1(sh))

    def z(val, surr):
        surr = np.array(surr)
        std = np.std(surr)
        return (val - np.mean(surr)) / std if std > 1e-10 else 0.0

    return {
        "n": int(len(spacings)),
        "r": float(r),
        "beta": float(beta),
        "acf1": float(acf),
        "r_shuf": float(np.mean(r_s)),
        "acf1_shuf": float(np.mean(acf_s)),
        "z_r": float(z(r, r_s)),
        "z_acf1": float(z(acf, acf_s)),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--N", type=int, default=N_DEFAULT)
    parser.add_argument("--surrogates", type=int, default=N_SURROGATES)
    args = parser.parse_args()
    N = args.N
    NS = args.surrogates

    print(f"=== 2D Spectral Plane: <r> vs acf1 ===")
    print(f"N={N}, surrogates={NS}\n")

    # --- Reference domains ---
    domains = [
        ("Primes", lambda n: gen_primes(n)),
        ("GUE", lambda n: gen_gue(n)),
        ("Poisson", lambda n: np.random.exponential(1.0, n)),
    ]

    # --- Berry-Robnik sweep (traces a 1D path in the plane) ---
    for rho in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        domains.append((f"BR_{rho:.1f}", lambda n, r=rho: gen_berry_robnik(n, r)))

    # --- Synthetic models targeting prime position ---
    domains.extend([
        ("Mod6_constrained", lambda n: gen_mod6_constrained(n)),
        ("Markov_mod6", lambda n: gen_markov_mod6(n)),
        ("Alternating_mag", lambda n: gen_alternating_magnitude(n)),
        ("Anticorr_0.1", lambda n: gen_anticorr_poisson(n, 0.1)),
        ("Anticorr_0.2", lambda n: gen_anticorr_poisson(n, 0.2)),
        ("Anticorr_0.3", lambda n: gen_anticorr_poisson(n, 0.3)),
        ("Anticorr_0.5", lambda n: gen_anticorr_poisson(n, 0.5)),
    ])

    print(f"{'Domain':<20} {'<r>':>7} {'acf1':>8} {'beta':>7} {'z_r':>7} {'z_acf1':>8}")
    print("-" * 70)

    results = []
    for name, gen in domains:
        try:
            spacings = gen(N)
        except Exception as e:
            print(f"{name:<20} ERROR: {e}")
            results.append({"name": name, "error": str(e)})
            continue

        m = measure(spacings, NS)
        if m is None:
            print(f"{name:<20} ERROR: too few spacings")
            results.append({"name": name, "error": "too few"})
            continue

        m["name"] = name
        results.append(m)
        print(f"{name:<20} {m['r']:7.4f} {m['acf1']:8.4f} {m['beta']:7.3f} {m['z_r']:7.1f} {m['z_acf1']:8.1f}")

    # --- Analysis: distance from primes in (r, acf1) plane ---
    prime = next((r for r in results if r["name"] == "Primes" and "error" not in r), None)
    if prime:
        print(f"\n=== Distance from Primes in (<r>, acf1) plane ===")
        print(f"  Primes: <r>={prime['r']:.4f}, acf1={prime['acf1']:.4f}")
        print()

        dists = []
        for r in results:
            if "error" in r or r["name"] == "Primes":
                continue
            # Normalize: <r> range ~0.3, acf1 range ~0.3 → equal weight
            dr = r["r"] - prime["r"]
            da = r["acf1"] - prime["acf1"]
            d = np.sqrt(dr**2 + da**2)
            dists.append((d, r["name"], dr, da))

        dists.sort()
        for d, name, dr, da in dists:
            print(f"  {name:<20} d={d:.4f}  (dr={dr:+.4f}, da={da:+.4f})")

        # --- Key test: does any model reach the primes' position? ---
        print(f"\n=== Can any model reach primes? ===")
        closest = dists[0]
        print(f"  Closest: {closest[1]} (d={closest[0]:.4f})")

        # Check if Berry-Robnik path passes through primes' acf1
        br_results = [r for r in results if r["name"].startswith("BR_") and "error" not in r]
        if br_results:
            br_acf1 = [r["acf1"] for r in br_results]
            print(f"  Berry-Robnik acf1 range: [{min(br_acf1):.4f}, {max(br_acf1):.4f}]")
            print(f"  Primes acf1: {prime['acf1']:.4f}")
            if prime["acf1"] < min(br_acf1):
                print(f"  --> Berry-Robnik CANNOT reach primes' acf1. The anti-correlation is NOT from mixing.")

        # Check mod-6 models
        mod6_results = [r for r in results if ("Mod6" in r["name"] or "Markov" in r["name"]) and "error" not in r]
        if mod6_results:
            print(f"\n  Mod-6 models:")
            for r in mod6_results:
                dr = r["r"] - prime["r"]
                da = r["acf1"] - prime["acf1"]
                d = np.sqrt(dr**2 + da**2)
                print(f"    {r['name']}: <r>={r['r']:.4f}, acf1={r['acf1']:.4f} (d={d:.4f})")
                if d < 0.02:
                    print(f"    --> MATCH: mod-6 confinement explains primes' spectral position!")
                elif abs(da) < 0.02:
                    print(f"    --> acf1 matches but <r> differs: confinement explains anti-correlation, not repulsion")
                elif abs(dr) < 0.02:
                    print(f"    --> <r> matches but acf1 differs: confinement does NOT explain anti-correlation")

    # Save
    outpath = os.path.join(os.path.dirname(__file__), "data", "exp_spectral_2d.json")
    with open(outpath, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "N": N,
            "surrogates": NS,
            "results": results,
        }, f, indent=2)
    print(f"\nSaved: {outpath}")


if __name__ == "__main__":
    main()
