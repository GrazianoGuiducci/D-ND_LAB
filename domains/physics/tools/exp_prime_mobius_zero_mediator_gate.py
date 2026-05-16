#!/usr/bin/env python3
"""Prime x Mobius zero-mediator gate.

Repairs the 20260508_2102 interval-charge gate by keeping transitions with
S=0 in the denominator as an explicit third class.
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


METRIC_KEYS = [
    "low_low_aligned_rate",
    "low_low_misaligned_rate",
    "low_low_zero_rate",
    "high_high_aligned_rate",
    "high_high_misaligned_rate",
    "high_high_zero_rate",
    "sr_aligned_mean",
    "sr_misaligned_mean",
    "sr_zero_mean",
    "low_low_aligned_minus_misaligned",
    "low_low_zero_minus_nonzero",
    "high_high_aligned_minus_misaligned",
    "high_high_zero_minus_nonzero",
    "sr_aligned_minus_misaligned",
    "sr_zero_minus_nonzero",
]


def _rate(mask: np.ndarray, event: np.ndarray) -> tuple[int, int, float]:
    denom = int(np.sum(mask))
    hits = int(np.sum(mask & event))
    rate = float(hits / denom) if denom else float("nan")
    return hits, denom, rate


def _mean(mask: np.ndarray, values: np.ndarray) -> tuple[int, float]:
    denom = int(np.sum(mask))
    mean = float(np.mean(values[mask])) if denom else float("nan")
    return denom, mean


def transition_metrics_three_class(gaps: np.ndarray, charges: np.ndarray) -> dict[str, float | int]:
    left = charges[:-1]
    right = charges[1:]
    product = left * right
    aligned = product < 0
    misaligned = product > 0
    zero = product == 0
    nonzero = ~zero

    g0 = gaps[:-1].astype(float)
    g1 = gaps[1:].astype(float)
    ratio = np.minimum(g0, g1) / np.maximum(g0, g1)
    low_low = (g0 <= 6) & (g1 <= 6)
    q75 = float(np.quantile(gaps, 0.75))
    high_high = (g0 >= q75) & (g1 >= q75)

    metrics: dict[str, float | int] = {
        "q75_gap": q75,
        "aligned_count": int(np.sum(aligned)),
        "misaligned_count": int(np.sum(misaligned)),
        "zero_count": int(np.sum(zero)),
        "nonzero_count": int(np.sum(nonzero)),
    }

    for name, event in (("low_low", low_low), ("high_high", high_high)):
        for cls_name, mask in (
            ("aligned", aligned),
            ("misaligned", misaligned),
            ("zero", zero),
            ("nonzero", nonzero),
        ):
            hits, denom, rate = _rate(mask, event)
            metrics[f"{name}_{cls_name}_hits"] = hits
            metrics[f"{name}_{cls_name}_denom"] = denom
            metrics[f"{name}_{cls_name}_rate"] = rate

    for cls_name, mask in (
        ("aligned", aligned),
        ("misaligned", misaligned),
        ("zero", zero),
        ("nonzero", nonzero),
    ):
        denom, mean = _mean(mask, ratio)
        metrics[f"sr_{cls_name}_denom"] = denom
        metrics[f"sr_{cls_name}_mean"] = mean

    metrics["low_low_aligned_minus_misaligned"] = (
        float(metrics["low_low_aligned_rate"]) - float(metrics["low_low_misaligned_rate"])
    )
    metrics["high_high_aligned_minus_misaligned"] = (
        float(metrics["high_high_aligned_rate"]) - float(metrics["high_high_misaligned_rate"])
    )
    metrics["sr_aligned_minus_misaligned"] = (
        float(metrics["sr_aligned_mean"]) - float(metrics["sr_misaligned_mean"])
    )
    metrics["low_low_zero_minus_nonzero"] = (
        float(metrics["low_low_zero_rate"]) - float(metrics["low_low_nonzero_rate"])
    )
    metrics["high_high_zero_minus_nonzero"] = (
        float(metrics["high_high_zero_rate"]) - float(metrics["high_high_nonzero_rate"])
    )
    metrics["sr_zero_minus_nonzero"] = (
        float(metrics["sr_zero_mean"]) - float(metrics["sr_nonzero_mean"])
    )
    return metrics


def permutation_test(
    gaps: np.ndarray,
    charges: np.ndarray,
    observed: dict[str, float | int],
    rng: np.random.Generator,
    permutations: int,
) -> dict[str, dict[str, float]]:
    nulls = {key: [] for key in METRIC_KEYS}
    for _ in range(permutations):
        shuffled = np.array(charges, copy=True)
        rng.shuffle(shuffled)
        metrics = transition_metrics_three_class(gaps, shuffled)
        for key in METRIC_KEYS:
            nulls[key].append(float(metrics[key]))

    out: dict[str, dict[str, float]] = {}
    for key, values in nulls.items():
        arr = np.array(values, dtype=float)
        obs = float(observed[key])
        finite = np.isfinite(arr)
        arr = arr[finite]
        if arr.size == 0 or not np.isfinite(obs):
            out[key] = {"observed": obs, "null_mean": float("nan"), "null_std": float("nan"), "z": float("nan"), "p_two_sided": float("nan")}
            continue
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


def det_m_direct_control(gaps: np.ndarray) -> dict[str, float | int | str]:
    g0 = gaps[:-1].astype(float)
    g1 = gaps[1:].astype(float)
    ratio = np.minimum(g0, g1) / np.maximum(g0, g1)
    low_low = (g0 <= 6) & (g1 <= 6)
    q75 = float(np.quantile(gaps, 0.75))
    high_high = (g0 >= q75) & (g1 >= q75)
    denom = int(g0.size)
    return {
        "det_M": -1,
        "class_count": 1,
        "reason": "M=[[1,1],[1,0]] has constant determinant -1 on every transition, so direct det(M) does not partition the denominator.",
        "denominator": denom,
        "low_low_hits": int(np.sum(low_low)),
        "low_low_rate": float(np.sum(low_low) / denom),
        "high_high_hits": int(np.sum(high_high)),
        "high_high_rate": float(np.sum(high_high) / denom),
        "sr_mean": float(np.mean(ratio)),
    }


def classify_zero_role(observed: dict[str, float | int], tests: dict[str, dict[str, float]]) -> str:
    low_z = tests["low_low_zero_minus_nonzero"]["z"]
    high_z = tests["high_high_zero_minus_nonzero"]["z"]
    sr_z = tests["sr_zero_minus_nonzero"]["z"]
    passes = [
        abs(low_z) >= 2 and tests["low_low_zero_minus_nonzero"]["p_two_sided"] <= 0.05,
        abs(high_z) >= 2 and tests["high_high_zero_minus_nonzero"]["p_two_sided"] <= 0.05,
        abs(sr_z) >= 2 and tests["sr_zero_minus_nonzero"]["p_two_sided"] <= 0.05,
    ]
    low = float(observed["low_low_zero_rate"])
    high = float(observed["high_high_zero_rate"])
    sr = float(observed["sr_zero_mean"])
    low_a = float(observed["low_low_aligned_rate"])
    low_m = float(observed["low_low_misaligned_rate"])
    high_a = float(observed["high_high_aligned_rate"])
    high_m = float(observed["high_high_misaligned_rate"])
    sr_a = float(observed["sr_aligned_mean"])
    sr_m = float(observed["sr_misaligned_mean"])

    between_low = min(low_a, low_m) <= low <= max(low_a, low_m)
    between_high = min(high_a, high_m) <= high <= max(high_a, high_m)
    between_sr = min(sr_a, sr_m) <= sr <= max(sr_a, sr_m)

    if any(passes) and (between_low or between_high or between_sr):
        return "boundary"
    if any(passes):
        return "third_class"
    return "noise_under_this_null"


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
    observed = transition_metrics_three_class(gaps, charges)
    tests = permutation_test(gaps, charges, observed, rng, permutations)
    return {
        "n_primes": n_primes,
        "offset": offset,
        "prime_start": int(segment[0]),
        "prime_stop": int(segment[-1]),
        "zero_charge_count": int(np.sum(charges == 0)),
        "charge_count": int(charges.size),
        "observed": observed,
        "permutation_tests": tests,
        "zero_role": classify_zero_role(observed, tests),
        "det_m_direct_control": det_m_direct_control(gaps),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1_000_000)
    parser.add_argument("--permutations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=2108)
    parser.add_argument("--out", default="tools/data/prime_mobius_zero_mediator_gate_20260508_2108.json")
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
    summary = []
    for result in results:
        tests = result["permutation_tests"]
        summary.append(
            {
                "n_primes": result["n_primes"],
                "offset": result["offset"],
                "low_low_aligned_minus_misaligned_pass": abs(tests["low_low_aligned_minus_misaligned"]["z"]) >= 2.0
                and tests["low_low_aligned_minus_misaligned"]["p_two_sided"] <= 0.05,
                "high_high_aligned_minus_misaligned_pass": abs(tests["high_high_aligned_minus_misaligned"]["z"]) >= 2.0
                and tests["high_high_aligned_minus_misaligned"]["p_two_sided"] <= 0.05,
                "sr_aligned_minus_misaligned_pass": abs(tests["sr_aligned_minus_misaligned"]["z"]) >= 2.0
                and tests["sr_aligned_minus_misaligned"]["p_two_sided"] <= 0.05,
                "zero_role": result["zero_role"],
            }
        )

    payload = {
        "experiment": "prime_mobius_zero_mediator_gate",
        "question": "Does S=0 behave as noise, boundary, or mediator in the Mobius interval-charge gate?",
        "threshold_ex_ante": "|z|>=2 and permutation p<=0.05 across main and offset conditions",
        "null": "Permutation of the interval-charge sequence preserves the full charge multiset and therefore preserves zero frequency.",
        "limit": args.limit,
        "permutations": args.permutations,
        "seed": args.seed,
        "conditions": results,
        "significance_summary": summary,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for result in results:
        obs = result["observed"]
        tests = result["permutation_tests"]
        print(
            f"N={result['n_primes']} offset={result['offset']} "
            f"a/m/z={obs['aligned_count']}/{obs['misaligned_count']}/{obs['zero_count']} "
            f"low_am={obs['low_low_aligned_minus_misaligned']:.5f} z={tests['low_low_aligned_minus_misaligned']['z']:.2f} p={tests['low_low_aligned_minus_misaligned']['p_two_sided']:.3f} "
            f"low_z0={obs['low_low_zero_minus_nonzero']:.5f} z={tests['low_low_zero_minus_nonzero']['z']:.2f} p={tests['low_low_zero_minus_nonzero']['p_two_sided']:.3f} "
            f"high_am={obs['high_high_aligned_minus_misaligned']:.5f} z={tests['high_high_aligned_minus_misaligned']['z']:.2f} p={tests['high_high_aligned_minus_misaligned']['p_two_sided']:.3f} "
            f"high_z0={obs['high_high_zero_minus_nonzero']:.5f} z={tests['high_high_zero_minus_nonzero']['z']:.2f} p={tests['high_high_zero_minus_nonzero']['p_two_sided']:.3f} "
            f"sr_am={obs['sr_aligned_minus_misaligned']:.5f} z={tests['sr_aligned_minus_misaligned']['z']:.2f} p={tests['sr_aligned_minus_misaligned']['p_two_sided']:.3f} "
            f"role={result['zero_role']}"
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
