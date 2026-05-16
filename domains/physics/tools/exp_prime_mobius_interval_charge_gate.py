#!/usr/bin/env python3
"""Prime x Mobius interval-charge gate.

Measures whether the Mobius charge inside prime-free intervals selects a
different gap-transition perimeter than a permutation null.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def sieve_primes(limit: int) -> np.ndarray:
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for p in range(2, int(limit**0.5) + 1):
        if is_prime[p]:
            is_prime[p * p : limit + 1 : p] = False
    return np.flatnonzero(is_prime)


def mobius_sieve(limit: int) -> np.ndarray:
    mu = np.ones(limit + 1, dtype=np.int8)
    is_prime = np.ones(limit + 1, dtype=bool)
    is_prime[:2] = False
    for p in range(2, limit + 1):
        if not is_prime[p]:
            continue
        mu[p::p] *= -1
        p2 = p * p
        if p2 <= limit:
            mu[p2::p2] = 0
            is_prime[p2::p] = False
    return mu


def interval_charges(primes: np.ndarray, mu: np.ndarray) -> np.ndarray:
    prefix = np.concatenate(([0], np.cumsum(mu, dtype=np.int64)))
    starts = primes[:-1] + 1
    stops = primes[1:]
    return prefix[stops] - prefix[starts]


def transition_metrics(gaps: np.ndarray, charges: np.ndarray) -> dict[str, float | int]:
    left = charges[:-1]
    right = charges[1:]
    product = left * right
    aligned = product < 0
    misaligned = product > 0

    g0 = gaps[:-1].astype(float)
    g1 = gaps[1:].astype(float)
    ratio = np.minimum(g0, g1) / np.maximum(g0, g1)
    low_low = (g0 <= 6) & (g1 <= 6)
    q75 = float(np.quantile(gaps, 0.75))
    high_high = (g0 >= q75) & (g1 >= q75)

    def rate(mask: np.ndarray, event: np.ndarray) -> float:
        denom = int(np.sum(mask))
        if denom == 0:
            return float("nan")
        return float(np.sum(event & mask) / denom)

    def mean(mask: np.ndarray, values: np.ndarray) -> float:
        if int(np.sum(mask)) == 0:
            return float("nan")
        return float(np.mean(values[mask]))

    a_count = int(np.sum(aligned))
    m_count = int(np.sum(misaligned))
    a_low_hits = int(np.sum(low_low & aligned))
    m_low_hits = int(np.sum(low_low & misaligned))
    a_high_hits = int(np.sum(high_high & aligned))
    m_high_hits = int(np.sum(high_high & misaligned))
    a_low_rate = rate(aligned, low_low)
    m_low_rate = rate(misaligned, low_low)
    a_high_rate = rate(aligned, high_high)
    m_high_rate = rate(misaligned, high_high)
    a_sr = mean(aligned, ratio)
    m_sr = mean(misaligned, ratio)

    return {
        "aligned_count": a_count,
        "misaligned_count": m_count,
        "low_low_aligned_hits": a_low_hits,
        "low_low_misaligned_hits": m_low_hits,
        "low_low_aligned_rate": a_low_rate,
        "low_low_misaligned_rate": m_low_rate,
        "low_low_diff": a_low_rate - m_low_rate,
        "low_low_ratio": a_low_rate / m_low_rate if m_low_rate > 0 else float("inf"),
        "high_high_aligned_hits": a_high_hits,
        "high_high_misaligned_hits": m_high_hits,
        "high_high_aligned_rate": a_high_rate,
        "high_high_misaligned_rate": m_high_rate,
        "high_high_diff": a_high_rate - m_high_rate,
        "high_high_ratio": a_high_rate / m_high_rate if m_high_rate > 0 else float("inf"),
        "sr_aligned_mean": a_sr,
        "sr_misaligned_mean": m_sr,
        "sr_diff": a_sr - m_sr,
        "q75_gap": q75,
    }


def permutation_test(
    gaps: np.ndarray,
    charges: np.ndarray,
    observed: dict[str, float | int],
    rng: np.random.Generator,
    permutations: int,
) -> dict[str, dict[str, float]]:
    keys = ["low_low_diff", "high_high_diff", "sr_diff"]
    nulls = {key: [] for key in keys}
    for _ in range(permutations):
        shuffled = np.array(charges, copy=True)
        rng.shuffle(shuffled)
        metrics = transition_metrics(gaps, shuffled)
        for key in keys:
            nulls[key].append(float(metrics[key]))

    out: dict[str, dict[str, float]] = {}
    for key in keys:
        arr = np.array(nulls[key], dtype=float)
        obs = float(observed[key])
        std = float(np.std(arr, ddof=1))
        z = (obs - float(np.mean(arr))) / std if std > 0 else 0.0
        p = float((np.sum(np.abs(arr) >= abs(obs)) + 1) / (len(arr) + 1))
        out[key] = {
            "observed": obs,
            "null_mean": float(np.mean(arr)),
            "null_std": std,
            "z": float(z),
            "p_two_sided": p,
        }
    return out


def run_condition(
    primes: np.ndarray,
    mu: np.ndarray,
    n_primes: int,
    offset: int,
    rng: np.random.Generator,
    permutations: int,
) -> dict[str, object]:
    segment = primes[offset : offset + n_primes + 1]
    gaps = np.diff(segment)
    charges = interval_charges(segment, mu)
    observed = transition_metrics(gaps, charges)
    tests = permutation_test(gaps, charges, observed, rng, permutations)
    return {
        "n_primes": n_primes,
        "offset": offset,
        "prime_start": int(segment[0]),
        "prime_stop": int(segment[-1]),
        "observed": observed,
        "permutation_tests": tests,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1_000_000)
    parser.add_argument("--permutations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=2102)
    parser.add_argument("--out", default="tools/data/prime_mobius_interval_charge_gate_20260508_2102.json")
    args = parser.parse_args()

    primes = sieve_primes(args.limit)
    mu = mobius_sieve(args.limit)
    rng = np.random.default_rng(args.seed)

    conditions = [
        {"n_primes": 5_000, "offset": 0},
        {"n_primes": 10_000, "offset": 0},
        {"n_primes": 20_000, "offset": 0},
        {"n_primes": 5_000, "offset": 3_000},
        {"n_primes": 10_000, "offset": 7_000},
        {"n_primes": 20_000, "offset": 11_000},
    ]
    max_needed = max(c["offset"] + c["n_primes"] + 1 for c in conditions)
    if len(primes) <= max_needed:
        raise SystemExit(f"limit={args.limit} yields only {len(primes)} primes, need {max_needed}")

    results = [
        run_condition(primes, mu, c["n_primes"], c["offset"], rng, args.permutations)
        for c in conditions
    ]
    significant = []
    for result in results:
        tests = result["permutation_tests"]
        significant.append(
            {
                "n_primes": result["n_primes"],
                "offset": result["offset"],
                "low_low_pass": abs(tests["low_low_diff"]["z"]) >= 2.0
                and tests["low_low_diff"]["p_two_sided"] <= 0.05,
                "high_high_pass": abs(tests["high_high_diff"]["z"]) >= 2.0
                and tests["high_high_diff"]["p_two_sided"] <= 0.05,
                "sr_pass": abs(tests["sr_diff"]["z"]) >= 2.0
                and tests["sr_diff"]["p_two_sided"] <= 0.05,
            }
        )

    payload = {
        "experiment": "prime_mobius_interval_charge_gate",
        "question": "Does Mobius interval-charge alignment select a prime-gap perimeter beyond permutation null?",
        "threshold_ex_ante": "|z|>=2 and permutation p<=0.05, replicated across main and offset conditions",
        "limit": args.limit,
        "permutations": args.permutations,
        "seed": args.seed,
        "conditions": results,
        "significance_summary": significant,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for result in results:
        obs = result["observed"]
        tests = result["permutation_tests"]
        print(
            f"N={result['n_primes']} offset={result['offset']} "
            f"aligned={obs['aligned_count']} misaligned={obs['misaligned_count']} "
            f"low_diff={obs['low_low_diff']:.5f} z={tests['low_low_diff']['z']:.2f} p={tests['low_low_diff']['p_two_sided']:.3f} "
            f"high_diff={obs['high_high_diff']:.5f} z={tests['high_high_diff']['z']:.2f} p={tests['high_high_diff']['p_two_sided']:.3f} "
            f"sr_diff={obs['sr_diff']:.5f} z={tests['sr_diff']['z']:.2f} p={tests['sr_diff']['p_two_sided']:.3f}"
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
