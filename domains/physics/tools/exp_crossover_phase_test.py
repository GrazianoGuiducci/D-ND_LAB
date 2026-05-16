"""
exp_crossover_phase_test.py — Is the dipolar phase transition universal or diagnostic?

Tests whether the direction-lock + magnitude-decay + zero-crossing phase transition
observed in the GUE crossover is a property of the PARTIAL SHUFFLE METHOD (tautology)
or a property of SPECIFIC ORDERING TYPES (discovery).

Multiple ordered sequences undergo the same partial-shuffle protocol. If ALL show
direction lock + linear decay + phase transition, the finding is methodological.
If only some do, the phase transition is diagnostic.

Usage:
    python tools/exp_crossover_phase_test.py [--N 10000] [--alphas 15] [--trials 12]
"""
import numpy as np
from scipy import stats
import json, argparse, os

def spacing_ratio(gaps):
    """Spacing ratio: mean of min(g_i, g_{i+1}) / max(g_i, g_{i+1})"""
    r = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return np.nanmean(r[np.isfinite(r)])

def lag1_acf(gaps):
    """Lag-1 autocorrelation"""
    if len(gaps) < 3:
        return 0.0
    g = gaps - np.mean(gaps)
    var = np.var(gaps)
    if var == 0:
        return 0.0
    return np.mean(g[:-1] * g[1:]) / var

def partial_shuffle(seq, alpha, rng):
    """Shuffle a fraction alpha of positions in seq"""
    s = seq.copy()
    n = len(s)
    k = int(alpha * n)
    if k < 2:
        return s
    idx = rng.choice(n, size=k, replace=False)
    vals = s[idx].copy()
    rng.shuffle(vals)
    s[idx] = vals
    return s

def dipolar_coords(sr, l1, sr_ref, l1_ref):
    """Dipolar coordinates relative to reference (full shuffle baseline)"""
    dsr = sr - sr_ref
    dl1 = l1 - l1_ref
    theta = np.degrees(np.arctan2(dl1, dsr))
    mag = np.sqrt(dsr**2 + dl1**2)
    return theta, mag

def crossover_analysis(gaps, alphas, n_trials, rng):
    """Run crossover analysis on a gap sequence"""
    # Full shuffle baseline (alpha=1.0)
    sr_refs = []
    l1_refs = []
    for _ in range(n_trials * 3):
        shuffled = partial_shuffle(gaps, 1.0, rng)
        sr_refs.append(spacing_ratio(shuffled))
        l1_refs.append(lag1_acf(shuffled))
    sr_ref = np.mean(sr_refs)
    l1_ref = np.mean(l1_refs)

    results = []
    for alpha in alphas:
        thetas = []
        mags = []
        for _ in range(n_trials):
            s = partial_shuffle(gaps, alpha, rng)
            sr = spacing_ratio(s)
            l1 = lag1_acf(s)
            theta, mag = dipolar_coords(sr, l1, sr_ref, l1_ref)
            thetas.append(theta)
            mags.append(mag)
        results.append({
            'alpha': float(alpha),
            'theta_mean': float(np.mean(thetas)),
            'theta_std': float(np.std(thetas)),
            'mag_mean': float(np.mean(mags)),
            'mag_std': float(np.std(mags)),
        })
    return results, sr_ref, l1_ref

def generate_gue_gaps(N, rng):
    """Generate GUE-like spacings from random matrices"""
    dim = max(50, int(np.sqrt(N * 2)))
    all_spacings = []
    while len(all_spacings) < N:
        H = rng.standard_normal((dim, dim))
        H = (H + H.T) / np.sqrt(2)
        evals = np.sort(np.linalg.eigvalsh(H))
        start = int(0.2 * dim)
        end = int(0.8 * dim)
        sp = np.diff(evals[start:end])
        sp = sp / np.mean(sp)
        all_spacings.extend(sp.tolist())
    return np.array(all_spacings[:N])

def generate_prime_gaps(N):
    """Generate normalized prime gaps"""
    import sympy
    limit = int(N * (np.log(N) + np.log(np.log(N + 10)) + 5))
    primes = list(sympy.primerange(2, limit))
    if len(primes) < N + 1:
        primes = list(sympy.primerange(2, limit * 2))
    primes = np.array(primes[:N+1], dtype=float)
    gaps = np.diff(primes)
    w = 100
    local_mean = np.convolve(gaps, np.ones(w)/w, mode='same')
    local_mean[local_mean == 0] = 1
    return gaps / local_mean

def generate_logistic_gaps(N, rng):
    """Logistic map at edge of chaos (Feigenbaum point)"""
    r = 3.5699456
    x = 0.5 + rng.random() * 0.01
    for _ in range(10000):
        x = r * x * (1 - x)
    vals = []
    for _ in range(N + 1):
        x = r * x * (1 - x)
        vals.append(x)
    vals = np.array(vals)
    gaps = np.abs(np.diff(vals))
    gaps[gaps == 0] = 1e-15
    gaps = gaps / np.mean(gaps)
    return gaps

def generate_ar1_neg(N, rng):
    """AR(1) with negative autocorrelation (mimics level repulsion)"""
    phi = -0.5
    eps = rng.standard_normal(N)
    x = np.zeros(N)
    x[0] = eps[0]
    for i in range(1, N):
        x[i] = phi * x[i-1] + eps[i]
    x = x - x.min() + 0.1
    x = x / np.mean(x)
    return x

def generate_periodic(N):
    """Periodic 2,4,2,4,... (Z/6Z confinement analog)"""
    gaps = np.tile([2.0, 4.0], N // 2 + 1)[:N]
    gaps = gaps / np.mean(gaps)
    return gaps

def generate_rw_excursions(N, rng):
    """Gaps between zero-crossings of random walk"""
    walk = np.cumsum(rng.choice([-1, 1], size=N * 50))
    crossings = np.where(np.diff(np.sign(walk)))[0]
    if len(crossings) < N + 1:
        walk = np.cumsum(rng.choice([-1, 1], size=N * 200))
        crossings = np.where(np.diff(np.sign(walk)))[0]
    gaps = np.diff(crossings[:N+1]).astype(float)
    gaps = gaps / np.mean(gaps)
    return gaps

def generate_poisson(N, rng):
    """Pure Poisson (exponential gaps) — should show NO ordering signal"""
    gaps = rng.exponential(1.0, size=N)
    return gaps

def analyze_direction_lock(results):
    """Analyze if direction locks in low-alpha regime"""
    ordered = [r for r in results if 0 < r['alpha'] <= 0.50]
    if not ordered:
        return None
    thetas = [r['theta_mean'] for r in ordered]
    theta_mean = np.mean(thetas)
    theta_std = np.std(thetas)

    # Magnitude linearity
    alphas_ord = [r['alpha'] for r in ordered]
    mags_ord = [r['mag_mean'] for r in ordered]
    if len(alphas_ord) > 2:
        slope, intercept, r_value, p_value, _ = stats.linregress(alphas_ord, mags_ord)
    else:
        slope, intercept, r_value, p_value = 0, 0, 0, 1

    # Transition point (minimum magnitude)
    all_mags = [(r['alpha'], r['mag_mean']) for r in results if r['alpha'] > 0]
    min_mag_alpha, min_mag_val = min(all_mags, key=lambda x: x[1]) if all_mags else (0, 0)

    # Direction flip
    pre = [r['theta_mean'] for r in results if 0 < r['alpha'] <= 0.50]
    post = [r['theta_mean'] for r in results if r['alpha'] >= 0.80]
    direction_flip = abs(np.mean(post) - np.mean(pre)) if pre and post else 0

    return {
        'direction_locked_theta': float(theta_mean),
        'direction_std': float(theta_std),
        'mag_slope': float(slope),
        'mag_linearity_r2': float(r_value**2),
        'transition_alpha': float(min_mag_alpha),
        'transition_min_mag': float(min_mag_val),
        'direction_flip_deg': float(direction_flip),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', type=int, default=10000)
    parser.add_argument('--alphas', type=int, default=15)
    parser.add_argument('--trials', type=int, default=12)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    alphas = np.linspace(0.0, 1.0, args.alphas)

    print("Generating sequences...")
    sequences = {}
    sequences['GUE'] = generate_gue_gaps(args.N, rng)
    print(f"  GUE: {len(sequences['GUE'])} gaps")
    sequences['Primes'] = generate_prime_gaps(args.N)
    print(f"  Primes: {len(sequences['Primes'])} gaps")
    sequences['Logistic'] = generate_logistic_gaps(args.N, rng)
    print(f"  Logistic: {len(sequences['Logistic'])} gaps")
    sequences['AR1_neg'] = generate_ar1_neg(args.N, rng)
    print(f"  AR1_neg: {len(sequences['AR1_neg'])} gaps")
    sequences['Periodic'] = generate_periodic(args.N)
    print(f"  Periodic: {len(sequences['Periodic'])} gaps")
    sequences['RW_excursions'] = generate_rw_excursions(args.N, rng)
    print(f"  RW_excursions: {len(sequences['RW_excursions'])} gaps")
    sequences['Poisson'] = generate_poisson(args.N, rng)
    print(f"  Poisson: {len(sequences['Poisson'])} gaps")

    all_results = {}
    for name, gaps in sequences.items():
        print(f"\nCrossover analysis: {name}...")
        results, sr_ref, l1_ref = crossover_analysis(gaps, alphas, args.trials, rng)
        analysis = analyze_direction_lock(results)
        all_results[name] = {
            'crossover': results,
            'analysis': analysis,
            'baseline': {'sr_ref': float(sr_ref), 'l1_ref': float(l1_ref)},
            'original_sr': float(spacing_ratio(gaps)),
            'original_l1': float(lag1_acf(gaps)),
        }
        if analysis:
            print(f"  Locked theta: {analysis['direction_locked_theta']:.1f} +/- {analysis['direction_std']:.1f} deg")
            print(f"  Mag slope: {analysis['mag_slope']:.4f}, R2: {analysis['mag_linearity_r2']:.3f}")
            print(f"  Transition: alpha={analysis['transition_alpha']:.2f}, min_mag={analysis['transition_min_mag']:.5f}")
            print(f"  Flip: {analysis['direction_flip_deg']:.1f} deg")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY: Crossover Phase Transition Universality")
    print("="*80)
    print(f"{'Sequence':<15} {'Locked θ':<12} {'θ std':<8} {'Mag slope':<12} {'R²':<8} {'Trans α':<10} {'Flip°':<8}")
    print("-"*80)
    for name, data in all_results.items():
        a = data['analysis']
        if a:
            print(f"{name:<15} {a['direction_locked_theta']:>8.1f}    {a['direction_std']:>5.1f}   {a['mag_slope']:>9.4f}   {a['mag_linearity_r2']:>5.3f}   {a['transition_alpha']:>6.2f}     {a['direction_flip_deg']:>5.1f}")

    # Classification
    print("\n" + "="*80)
    print("CLASSIFICATION: Does each sequence show the full GUE-like phase transition?")
    print("="*80)
    phase_transition_count = 0
    total = 0
    for name, data in all_results.items():
        a = data['analysis']
        if not a:
            print(f"  {name}: NO ANALYSIS")
            continue
        total += 1
        has_lock = a['direction_std'] < 15
        has_linear_decay = a['mag_linearity_r2'] > 0.85 and a['mag_slope'] < 0
        has_transition = a['transition_min_mag'] < 0.02
        has_flip = a['direction_flip_deg'] > 60

        features = []
        if has_lock: features.append("LOCK")
        if has_linear_decay: features.append("LINEAR_DECAY")
        if has_transition: features.append("ZERO_CROSS")
        if has_flip: features.append("FLIP")

        full = has_lock and has_linear_decay and has_transition and has_flip
        if full:
            phase_transition_count += 1
        label = "FULL PHASE TRANSITION" if full else f"PARTIAL ({'+'.join(features) if features else 'NONE'})"
        print(f"  {name}: {label}")

    print(f"\n  RESULT: {phase_transition_count}/{total} sequences show full phase transition pattern")
    if phase_transition_count == total:
        print("  VERDICT: UNIVERSAL — the phase transition is a property of the partial-shuffle METHOD")
        print("           The GUE crossover finding is TAUTOLOGICAL (methodological artifact)")
    elif phase_transition_count <= 2:
        print("  VERDICT: DIAGNOSTIC — the phase transition is specific to certain ordering types")
        print("           The GUE crossover finding is a REAL structural property")
    else:
        print("  VERDICT: MIXED — some orderings show it, some don't")
        print("           The phase transition discriminates ordering CLASSES, not individual sequences")

    # Save
    output = {
        'params': {'N': args.N, 'alphas': args.alphas, 'trials': args.trials, 'seed': args.seed},
        'results': {},
        'classification': {}
    }
    for name, data in all_results.items():
        a = data['analysis']
        output['results'][name] = {
            'analysis': a,
            'baseline': data['baseline'],
            'original_sr': data['original_sr'],
            'original_l1': data['original_l1'],
        }
        if a:
            output['classification'][name] = {
                'has_lock': a['direction_std'] < 15,
                'has_linear_decay': a['mag_linearity_r2'] > 0.85 and a['mag_slope'] < 0,
                'has_transition': a['transition_min_mag'] < 0.02,
                'has_flip': a['direction_flip_deg'] > 60,
            }

    outpath = os.path.join(os.path.dirname(__file__), 'data', 'crossover_phase_test.json')
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {outpath}")

if __name__ == '__main__':
    main()
