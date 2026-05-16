#!/usr/bin/env python3
"""
Markov Memory Decomposition Across GUE Types

Question: The TWO_KINDS_GUE result (2026-04-24) found that distribution-GUE
domains (primes, GUE matrices) retain GUE classification after shuffle, while
ordering-GUE domains (fibonacci, coupled_osc, percolation) collapse to Poisson.
The Markov-3 result (2026-04-23) found 33.6% scale-invariant ordering memory
in prime gap residues.

This experiment asks: what is the Markov memory profile of each GUE type?
If ordering-GUE domains get their classification FROM sequential ordering,
they should have high Markov memory. But at what order does it saturate?

Method:
- For each domain, compute gap sequence
- Classify gaps into 3 categories (terciles: S/M/L)
- Compute conditional entropy H_k for Markov orders k=1,2,3
- Compare H_k(real) vs H_k(shuffled) -> ordering fraction at each order
- The saturation profile discriminates mechanisms

Null baseline: 200 shuffles per domain (same distribution, destroyed order).
"""

import numpy as np
import sys
import json
from collections import Counter

sys.path.insert(0, '/opt/MM_D-ND/tools')
from dnd_autoricerca import genera_segnale


def gaps_from_signal(signal, metadata):
    """Extract gaps from a signal. If already gaps, return as-is."""
    if metadata.get('is_spacings') or metadata.get('dominio') in ('numeri_primi',):
        return np.array(signal, dtype=float)
    vals = np.sort(signal)
    g = np.diff(vals)
    g = g[g > 0]
    return g


def tercile_classify(gaps):
    """Classify gaps into 3 categories by terciles: 0=small, 1=medium, 2=large."""
    t1, t2 = np.percentile(gaps, [33.33, 66.67])
    cats = np.zeros(len(gaps), dtype=int)
    cats[gaps > t2] = 2
    cats[(gaps > t1) & (gaps <= t2)] = 1
    return cats


def conditional_entropy(cats, order):
    """Compute conditional entropy H(X_t | X_{t-1},...,X_{t-order}).
    Returns H in bits."""
    n = len(cats)
    if n <= order + 1:
        return float('nan')

    context_counts = Counter()
    joint_counts = Counter()

    for i in range(order, n):
        context = tuple(cats[i - order:i])
        outcome = cats[i]
        context_counts[context] += 1
        joint_counts[(context, outcome)] += 1

    H = 0.0
    total = sum(context_counts.values())
    for (ctx, out), count in joint_counts.items():
        p_joint = count / total
        p_cond = count / context_counts[ctx]
        if p_cond > 0:
            H -= p_joint * np.log2(p_cond)
    return H


def ordering_fraction(cats, order, n_shuffles=200):
    """Compute ordering fraction at given Markov order.
    Returns (H_real, H_shuffle_mean, H_shuffle_std, ordering_frac, z_score)."""
    H_real = conditional_entropy(cats, order)

    H_shuffles = []
    for _ in range(n_shuffles):
        perm = np.random.permutation(cats)
        H_shuffles.append(conditional_entropy(perm, order))

    H_shuf_mean = np.mean(H_shuffles)
    H_shuf_std = np.std(H_shuffles)

    if H_shuf_mean > 0:
        of = (H_shuf_mean - H_real) / H_shuf_mean
    else:
        of = 0.0

    z = (H_real - H_shuf_mean) / H_shuf_std if H_shuf_std > 0 else 0.0

    return H_real, H_shuf_mean, H_shuf_std, of, z


def generate_large_primes(n_limit=200000):
    """Generate prime gaps up to n_limit."""
    is_prime = np.ones(n_limit + 1, dtype=bool)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n_limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i*i::i] = False
    primes = np.where(is_prime)[0]
    return np.diff(primes).astype(float)


def generate_poisson_gaps(n=5000):
    """Pure Poisson process gaps (exponential)."""
    return np.random.exponential(1.0, n)


def generate_gue_gaps(n=2000):
    """GUE random matrix eigenvalue spacings."""
    from scipy.linalg import eigvalsh
    N = int(np.sqrt(2 * n)) + 10
    H = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    H = (H + H.conj().T) / 2
    evals = eigvalsh(H)
    spacings = np.diff(evals)
    spacings = spacings / np.mean(spacings)
    return spacings


def main():
    np.random.seed(42)

    # Domain definitions with GUE type from TWO_KINDS_GUE result
    domains = {}

    # Distribution-GUE domains (survive shuffle)
    print("Generating domains...")
    domains['primes'] = {
        'gaps': generate_large_primes(200000),
        'type': 'distribution-GUE',
        'delta_r_sign': '-'
    }
    domains['gue_matrix'] = {
        'gaps': generate_gue_gaps(3000),
        'type': 'distribution-GUE',
        'delta_r_sign': '-'
    }

    # Ordering-GUE domains (collapse to Poisson on shuffle)
    for dom_name in ['percolation', 'coupled_oscillators']:
        signal, meta = genera_segnale(dom_name)
        gaps = gaps_from_signal(signal, meta)
        if len(gaps) < 50:
            print(f"  {dom_name}: only {len(gaps)} gaps, skipping")
            continue
        domains[dom_name] = {
            'gaps': gaps,
            'type': 'ordering-GUE',
            'delta_r_sign': '+'
        }

    # Fibonacci spectrum
    try:
        signal, meta = genera_segnale('string_vibration')
        gaps = gaps_from_signal(signal, meta)
        if len(gaps) >= 50:
            domains['string_vibration'] = {
                'gaps': gaps, 'type': 'ordering-GUE', 'delta_r_sign': '+'
            }
    except Exception:
        pass

    # Poisson domains (control)
    domains['poisson'] = {
        'gaps': generate_poisson_gaps(5000),
        'type': 'Poisson',
        'delta_r_sign': '0'
    }

    for dom_name in ['logistica_biforcazione', 'brownian_motion']:
        try:
            signal, meta = genera_segnale(dom_name)
            gaps = gaps_from_signal(signal, meta)
            if len(gaps) >= 50:
                domains[dom_name] = {
                    'gaps': gaps, 'type': 'Poisson', 'delta_r_sign': '0'
                }
        except Exception:
            pass

    print(f"Domains ready: {list(domains.keys())}")
    print()

    # Run Markov memory decomposition
    results = []
    max_order = 3

    for name, info in domains.items():
        gaps = info['gaps']
        cats = tercile_classify(gaps)
        N = len(cats)

        print(f"=== {name} (N={N}, type={info['type']}) ===")

        row = {
            'domain': name,
            'N': N,
            'gue_type': info['type'],
            'delta_r_sign': info['delta_r_sign']
        }

        for k in range(1, max_order + 1):
            H_real, H_shuf_mean, H_shuf_std, of, z = ordering_fraction(cats, k, n_shuffles=200)
            print(f"  Order {k}: H_real={H_real:.4f}  H_shuf={H_shuf_mean:.4f}  "
                  f"ordering={of*100:.1f}%  z={z:.1f}")
            row[f'H_real_{k}'] = round(H_real, 5)
            row[f'H_shuf_{k}'] = round(H_shuf_mean, 5)
            row[f'ordering_pct_{k}'] = round(of * 100, 2)
            row[f'z_{k}'] = round(z, 1)

        # Saturation: how much of order-3 memory is already captured at order 1?
        if row.get('ordering_pct_3', 0) > 0:
            sat_1 = row['ordering_pct_1'] / row['ordering_pct_3'] * 100
            sat_2 = row['ordering_pct_2'] / row['ordering_pct_3'] * 100
        else:
            sat_1 = sat_2 = float('nan')
        row['saturation_at_1'] = round(sat_1, 1)
        row['saturation_at_2'] = round(sat_2, 1)

        print(f"  Saturation: order-1 captures {sat_1:.0f}% of order-3 memory")
        print()

        results.append(row)

    # Summary table
    print("\n" + "=" * 100)
    print(f"{'Domain':<22} {'Type':<18} {'N':>6}  "
          f"{'Ord1%':>6} {'Ord2%':>6} {'Ord3%':>6}  "
          f"{'z1':>7} {'z2':>7} {'z3':>7}  {'Sat@1':>5}")
    print("-" * 100)

    for r in sorted(results, key=lambda x: x['gue_type']):
        print(f"{r['domain']:<22} {r['gue_type']:<18} {r['N']:>6}  "
              f"{r.get('ordering_pct_1',0):>6.1f} {r.get('ordering_pct_2',0):>6.1f} "
              f"{r.get('ordering_pct_3',0):>6.1f}  "
              f"{r.get('z_1',0):>7.1f} {r.get('z_2',0):>7.1f} {r.get('z_3',0):>7.1f}  "
              f"{r.get('saturation_at_1',0):>5.0f}%")
    print("=" * 100)

    # Aggregate by type
    print("\nAggregate by GUE type:")
    for gtype in ['distribution-GUE', 'ordering-GUE', 'Poisson']:
        subset = [r for r in results if r['gue_type'] == gtype]
        if not subset:
            continue
        avg_ord1 = np.mean([r.get('ordering_pct_1', 0) for r in subset])
        avg_ord3 = np.mean([r.get('ordering_pct_3', 0) for r in subset])
        avg_sat = np.mean([r.get('saturation_at_1', 0) for r in subset
                           if not np.isnan(r.get('saturation_at_1', 0))])
        print(f"  {gtype}: avg_ord1={avg_ord1:.1f}%, avg_ord3={avg_ord3:.1f}%, "
              f"avg_sat@1={avg_sat:.0f}%")

    # Save results
    output = {
        'experiment': 'markov_memory_by_gue_type',
        'date': '2026-04-25',
        'question': 'Does Markov memory discriminate distribution-GUE from ordering-GUE?',
        'results': results
    }
    outpath = '/opt/MM_D-ND/tools/data/markov_memory_by_gue_type.json'
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved to {outpath}")

    return results


if __name__ == '__main__':
    main()
