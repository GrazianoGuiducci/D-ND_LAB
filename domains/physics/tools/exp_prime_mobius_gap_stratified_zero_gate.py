#!/usr/bin/env python3
"""Prime x Mobius zero gate with gap-length stratified null.

Follow-up to ``exp_prime_mobius_zero_mediator_gate.py``.  The previous null
preserved the interval-charge multiset but could still let a trivial
gap-length dependency explain the zero class.  This experiment shuffles
charges only inside gap-length buckets, preserving the first-order relation
between each interval charge and the length class of its prime gap.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from exp_prime_mobius_interval_charge_gate import (
    interval_charges,
    mobius_sieve,
    sieve_primes,
)
from exp_prime_mobius_zero_mediator_gate import METRIC_KEYS, transition_metrics_three_class


def gap_buckets(gaps: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    """Return stable bucket ids for individual prime gaps."""
    q50 = float(np.quantile(gaps, 0.50))
    q75 = float(np.quantile(gaps, 0.75))
    buckets = np.full(gaps.shape, 1, dtype=np.int8)
    buckets[gaps <= 6] = 0
    buckets[(gaps > 6) & (gaps <= q50)] = 1
    buckets[(gaps > q50) & (gaps < q75)] = 2
    buckets[gaps >= q75] = 3
    return buckets, {"low_max": 6.0, "q50": q50, "q75": q75}


def shuffle_within_buckets(
    charges: np.ndarray,
    buckets: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    shuffled = np.array(charges, copy=True)
    for bucket in np.unique(buckets):
        idx = np.flatnonzero(buckets == bucket)
        if idx.size > 1:
            shuffled[idx] = rng.permutation(shuffled[idx])
    return shuffled


def empirical_two_sided(obs: float, arr: np.ndarray) -> tuple[float, float, float]:
    arr = arr[np.isfinite(arr)]
    if arr.size == 0 or not np.isfinite(obs):
        return float("nan"), float("nan"), float("nan")
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    z = (obs - mean) / std if std > 0 else 0.0
    p = float((np.sum(np.abs(arr - mean) >= abs(obs - mean)) + 1) / (arr.size + 1))
    return z, p, mean


def stratified_permutation_test(
    gaps: np.ndarray,
    charges: np.ndarray,
    observed: dict[str, float | int],
    buckets: np.ndarray,
    rng: np.random.Generator,
    permutations: int,
) -> dict[str, dict[str, float]]:
    nulls = {key: [] for key in METRIC_KEYS}
    for _ in range(permutations):
        shuffled = shuffle_within_buckets(charges, buckets, rng)
        metrics = transition_metrics_three_class(gaps, shuffled)
        for key in METRIC_KEYS:
            nulls[key].append(float(metrics[key]))

    out: dict[str, dict[str, float]] = {}
    for key, values in nulls.items():
        arr = np.array(values, dtype=float)
        obs = float(observed[key])
        z, p, mean = empirical_two_sided(obs, arr)
        finite = arr[np.isfinite(arr)]
        out[key] = {
            "observed": obs,
            "null_mean": mean,
            "null_std": float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0,
            "z": z,
            "p_two_sided": p,
        }
    return out


def charge_bucket_profile(gaps: np.ndarray, charges: np.ndarray, buckets: np.ndarray) -> list[dict[str, float | int | str]]:
    labels = {
        0: "low_gap_le_6",
        1: "mid_low_gap",
        2: "mid_high_gap",
        3: "high_gap_ge_q75",
    }
    rows: list[dict[str, float | int | str]] = []
    for bucket in sorted(labels):
        mask = buckets == bucket
        count = int(np.sum(mask))
        zero = int(np.sum(mask & (charges == 0)))
        rows.append(
            {
                "bucket": labels[bucket],
                "interval_count": count,
                "zero_charge_count": zero,
                "zero_charge_rate": float(zero / count) if count else float("nan"),
                "mean_gap": float(np.mean(gaps[mask])) if count else float("nan"),
            }
        )
    return rows


def transition_bucket_profile(gaps: np.ndarray, charges: np.ndarray) -> dict[str, dict[str, float | int]]:
    g0 = gaps[:-1].astype(float)
    g1 = gaps[1:].astype(float)
    product = charges[:-1] * charges[1:]
    zero_transition = product == 0
    q75 = float(np.quantile(gaps, 0.75))
    masks = {
        "low_low": (g0 <= 6) & (g1 <= 6),
        "high_high": (g0 >= q75) & (g1 >= q75),
        "mixed_or_mid": ~(((g0 <= 6) & (g1 <= 6)) | ((g0 >= q75) & (g1 >= q75))),
    }
    profile: dict[str, dict[str, float | int]] = {}
    for name, mask in masks.items():
        denom = int(np.sum(mask))
        hits = int(np.sum(mask & zero_transition))
        profile[name] = {
            "transition_count": denom,
            "zero_transition_count": hits,
            "zero_transition_rate": float(hits / denom) if denom else float("nan"),
        }
    return profile


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
    buckets, bucket_edges = gap_buckets(gaps)
    observed = transition_metrics_three_class(gaps, charges)
    tests = stratified_permutation_test(gaps, charges, observed, buckets, rng, permutations)
    key_passes = {
        key: abs(test["z"]) >= 2.0 and test["p_two_sided"] <= 0.05
        for key, test in tests.items()
        if key in {
            "low_low_zero_minus_nonzero",
            "high_high_zero_minus_nonzero",
            "sr_zero_minus_nonzero",
            "low_low_aligned_minus_misaligned",
            "high_high_aligned_minus_misaligned",
            "sr_aligned_minus_misaligned",
        }
    }
    return {
        "n_primes": n_primes,
        "offset": offset,
        "prime_start": int(segment[0]),
        "prime_stop": int(segment[-1]),
        "bucket_edges": bucket_edges,
        "charge_bucket_profile": charge_bucket_profile(gaps, charges, buckets),
        "transition_bucket_profile": transition_bucket_profile(gaps, charges),
        "observed": observed,
        "gap_stratified_permutation_tests": tests,
        "key_passes": key_passes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1_000_000)
    parser.add_argument("--permutations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=2116)
    parser.add_argument("--out", default="tools/data/prime_mobius_gap_stratified_zero_gate_20260508_2116.json")
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
    payload = {
        "experiment": "prime_mobius_gap_stratified_zero_gate",
        "question": "Does the Mobius zero-transition class survive a null that preserves charge distribution inside gap-length buckets?",
        "threshold_ex_ante": "|z|>=2 and empirical p<=0.05 across main and offset conditions",
        "null": "Shuffle interval charges only within individual gap-length buckets: low<=6, mid_low<=q50, mid_high<q75, high>=q75. This preserves zero frequency by gap-length class.",
        "limit": args.limit,
        "permutations": args.permutations,
        "seed": args.seed,
        "conditions": results,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for result in results:
        obs = result["observed"]
        tests = result["gap_stratified_permutation_tests"]
        print(
            f"N={result['n_primes']} offset={result['offset']} "
            f"a/m/z={obs['aligned_count']}/{obs['misaligned_count']}/{obs['zero_count']} "
            f"low_z0={obs['low_low_zero_minus_nonzero']:.5f} "
            f"z={tests['low_low_zero_minus_nonzero']['z']:.2f} "
            f"p={tests['low_low_zero_minus_nonzero']['p_two_sided']:.3f} "
            f"high_z0={obs['high_high_zero_minus_nonzero']:.5f} "
            f"z={tests['high_high_zero_minus_nonzero']['z']:.2f} "
            f"p={tests['high_high_zero_minus_nonzero']['p_two_sided']:.3f} "
            f"sr_z0={obs['sr_zero_minus_nonzero']:.5f} "
            f"z={tests['sr_zero_minus_nonzero']['z']:.2f} "
            f"p={tests['sr_zero_minus_nonzero']['p_two_sided']:.3f}"
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
