#!/usr/bin/env python3
"""
exp_mobius_irrationality.py — Experiment: does det=-1 force irrational fixed points?

For integer-coefficient Möbius transforms x → (ax+b)/(cx+d):
- Fixed point satisfies: cx² + (d-a)x - b = 0
- Discriminant: Δ = (a-d)² + 4bc
- Irrational iff Δ is not a perfect square

Question: does det(M)=-1 (ad-bc=-1) constrain Δ to be non-square
more often than det=+1?

This is an experiment, not a tension. If the result is significant,
it enters the seme through the normal cycle.

Usage:
    python exp_mobius_irrationality.py
    python exp_mobius_irrationality.py --range 10  # coefficients -10..10
"""

import sys
import math
from collections import Counter

def is_perfect_square(n):
    if n < 0:
        return False
    r = int(math.isqrt(n))
    return r * r == n

def run(coeff_range=5):
    """Enumerate all 2x2 integer matrices with |det|=1, check discriminant."""

    results = {
        'det_minus1': {'total': 0, 'irrational': 0, 'rational': 0, 'no_fixed': 0},
        'det_plus1': {'total': 0, 'irrational': 0, 'rational': 0, 'no_fixed': 0},
    }

    examples = {'det_minus1_rational': [], 'det_minus1_irrational': [],
                'det_plus1_rational': [], 'det_plus1_irrational': []}

    R = range(-coeff_range, coeff_range + 1)

    for a in R:
        for b in R:
            for c in R:
                if c == 0:
                    continue  # skip non-Möbius (linear)
                for d in R:
                    det = a * d - b * c
                    if abs(det) != 1:
                        continue

                    key = 'det_minus1' if det == -1 else 'det_plus1'
                    results[key]['total'] += 1

                    # Discriminant of cx² + (d-a)x - b = 0
                    disc = (a - d) ** 2 + 4 * b * c

                    if disc < 0:
                        results[key]['no_fixed'] += 1  # complex fixed points
                    elif is_perfect_square(disc):
                        results[key]['rational'] += 1
                        if len(examples[key + '_rational']) < 3:
                            examples[key + '_rational'].append((a, b, c, d, disc))
                    else:
                        results[key]['irrational'] += 1
                        if len(examples[key + '_irrational']) < 3:
                            examples[key + '_irrational'].append((a, b, c, d, disc))

    return results, examples

def main():
    coeff_range = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--range' else 5

    print(f'=== Möbius Irrationality Criterion ===')
    print(f'Coefficient range: [{-coeff_range}, {coeff_range}]')
    print()

    results, examples = run(coeff_range)

    for key in ['det_minus1', 'det_plus1']:
        r = results[key]
        total_real = r['rational'] + r['irrational']
        irr_pct = (r['irrational'] / total_real * 100) if total_real > 0 else 0
        rat_pct = (r['rational'] / total_real * 100) if total_real > 0 else 0

        label = 'det = -1' if 'minus' in key else 'det = +1'
        print(f'{label}:')
        print(f'  Total matrices: {r["total"]}')
        print(f'  Real fixed points: {total_real}')
        print(f'    Rational: {r["rational"]} ({rat_pct:.1f}%)')
        print(f'    Irrational: {r["irrational"]} ({irr_pct:.1f}%)')
        print(f'  Complex fixed points: {r["no_fixed"]}')

        for ex_key in [key + '_rational', key + '_irrational']:
            if examples[ex_key]:
                label2 = 'rational' if 'rational' in ex_key else 'irrational'
                print(f'  Examples ({label2}):')
                for a, b, c, d, disc in examples[ex_key]:
                    print(f'    M=[{a},{b};{c},{d}] det={a*d-b*c} Δ={disc} √Δ={math.sqrt(abs(disc)):.4f}')
        print()

    # Comparison
    r1 = results['det_minus1']
    r2 = results['det_plus1']
    t1 = r1['rational'] + r1['irrational']
    t2 = r2['rational'] + r2['irrational']
    if t1 > 0 and t2 > 0:
        irr1 = r1['irrational'] / t1
        irr2 = r2['irrational'] / t2
        print(f'=== COMPARISON ===')
        print(f'det=-1 irrational rate: {irr1:.3f}')
        print(f'det=+1 irrational rate: {irr2:.3f}')
        print(f'Ratio: {irr1/irr2:.3f}' if irr2 > 0 else 'det=+1 has no irrationals')
        print()
        if irr1 > irr2:
            print('det=-1 produces MORE irrationals than det=+1')
        elif irr1 < irr2:
            print('det=-1 produces FEWER irrationals than det=+1')
        else:
            print('No difference')

if __name__ == '__main__':
    main()
