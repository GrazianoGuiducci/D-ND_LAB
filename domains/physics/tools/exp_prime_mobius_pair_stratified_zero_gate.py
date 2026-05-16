#!/usr/bin/env python3
"""Prime x Mobius zero gate with gap-pair stratified transition null.

Follow-up to ``exp_prime_mobius_gap_stratified_zero_gate.py``.  That cycle
showed that low/high effects are explained by individual gap-length buckets,
while an SR residual survives.  This script attacks that residual by shuffling
transition labels only inside pair buckets ``(bucket(g_i), bucket(g_{i+1}))``.

This is a transition-level null: it preserves the count of aligned,
misaligned, and zero transitions inside each coarse gap-pair class.  It does
not claim to reconstruct a globally consistent Mobius charge sequence after
shuffle; it tests whether exact gap-pair shape still carries information after
the coarse pair class is fixed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from exp_prime_mobius_gap_stratified_zero_gate import empirical_two_sided, gap_buckets
from exp_prime_mobius_interval_charge_gate import interval_charges, mobius_sieve, sieve_primes


TRANSITION_METRIC_KEYS = [
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

PAIR_LABELS = {
    0: "low_low",
    1: "low_mid_low",
    2: "low_mid_high",
    3: "low_high",
    4: "mid_low_low",
    5: "mid_low_mid_low",
    6: "mid_low_mid_high",
    7: "mid_low_high",
    8: "mid_high_low",
    9: "mid_high_mid_low",
    10: "mid_high_mid_high",
    11: "mid_high_high",
    12: "high_low",
    13: "high_mid_low",
    14: "high_mid_high",
    15: "high_high",
}


def transition_labels(charges: np.ndarray) -> np.ndarray:
    product = charges[:-1] * charges[1:]
    labels = np.zeros(product.shape, dtype=np.int8)
    labels[product < 0] = -1
    labels[product > 0] = 1
    return labels


def pair_buckets(gap_bucket_ids: np.ndarray) -> np.ndarray:
    return gap_bucket_ids[:-1] * 4 + gap_bucket_ids[1:]


def _rate(mask: np.ndarray, event: np.ndarray) -> tuple[int, int, float]:
    denom = int(np.sum(mask))
    hits = int(np.sum(mask & event))
    return hits, denom, float(hits / denom) if denom else float("nan")


def _mean(mask: np.ndarray, values: np.ndarray) -> tuple[int, float]:
    denom = int(np.sum(mask))
    return denom, float(np.mean(values[mask])) if denom else float("nan")


def transition_metrics_from_labels(gaps: np.ndarray, labels: np.ndarray) -> dict[str, float | int]:
    aligned = labels == -1
    misaligned = labels == 1
    zero = labels == 0
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


def shuffle_labels_within_pair_buckets(
    labels: np.ndarray,
    pair_bucket_ids: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    shuffled = np.array(labels, copy=True)
    for bucket in np.unique(pair_bucket_ids):
        idx = np.flatnonzero(pair_bucket_ids == bucket)
        if idx.size > 1:
            shuffled[idx] = rng.permutation(shuffled[idx])
    return shuffled


def pair_stratified_permutation_test(
    gaps: np.ndarray,
    labels: np.ndarray,
    observed: dict[str, float | int],
    pair_bucket_ids: np.ndarray,
    rng: np.random.Generator,
    permutations: int,
) -> dict[str, dict[str, float]]:
    nulls = {key: [] for key in TRANSITION_METRIC_KEYS}
    for _ in range(permutations):
        shuffled = shuffle_labels_within_pair_buckets(labels, pair_bucket_ids, rng)
        metrics = transition_metrics_from_labels(gaps, shuffled)
        for key in TRANSITION_METRIC_KEYS:
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


def pair_bucket_profile(pair_bucket_ids: np.ndarray, labels: np.ndarray, gaps: np.ndarray) -> list[dict[str, float | int | str]]:
    g0 = gaps[:-1].astype(float)
    g1 = gaps[1:].astype(float)
    ratio = np.minimum(g0, g1) / np.maximum(g0, g1)
    rows: list[dict[str, float | int | str]] = []
    for bucket in sorted(np.unique(pair_bucket_ids)):
        mask = pair_bucket_ids == bucket
        count = int(np.sum(mask))
        zero = int(np.sum(mask & (labels == 0)))
        aligned = int(np.sum(mask & (labels == -1)))
        misaligned = int(np.sum(mask & (labels == 1)))
        rows.append(
            {
                "pair_bucket": PAIR_LABELS[int(bucket)],
                "transition_count": count,
                "zero_count": zero,
                "aligned_count": aligned,
                "misaligned_count": misaligned,
                "zero_rate": float(zero / count) if count else float("nan"),
                "mean_sr": float(np.mean(ratio[mask])) if count else float("nan"),
            }
        )
    return rows


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
    gap_bucket_ids, bucket_edges = gap_buckets(gaps)
    pair_bucket_ids = pair_buckets(gap_bucket_ids)
    labels = transition_labels(charges)
    observed = transition_metrics_from_labels(gaps, labels)
    tests = pair_stratified_permutation_test(gaps, labels, observed, pair_bucket_ids, rng, permutations)
    key_passes = {
        key: abs(test["z"]) >= 2.0 and test["p_two_sided"] <= 0.05
        for key, test in tests.items()
        if key in {
            "sr_zero_minus_nonzero",
            "sr_aligned_minus_misaligned",
            "low_low_zero_minus_nonzero",
            "high_high_zero_minus_nonzero",
        }
    }
    return {
        "n_primes": n_primes,
        "offset": offset,
        "prime_start": int(segment[0]),
        "prime_stop": int(segment[-1]),
        "bucket_edges": bucket_edges,
        "observed": observed,
        "pair_bucket_profile": pair_bucket_profile(pair_bucket_ids, labels, gaps),
        "pair_stratified_transition_tests": tests,
        "key_passes": key_passes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1_000_000)
    parser.add_argument("--permutations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=2134)
    parser.add_argument("--out", default="tools/data/prime_mobius_pair_stratified_zero_gate_20260508_2134.json")
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
        "experiment": "prime_mobius_pair_stratified_zero_gate",
        "question": "Does the SR residual of Mobius zero transitions survive a transition-label null inside gap-pair buckets?",
        "threshold_ex_ante": "|z|>=2 and empirical p<=0.05 across main and offset conditions",
        "null": "Shuffle transition labels aligned/misaligned/zero only within pair buckets (bucket(g_i), bucket(g_{i+1})). Preserves class counts inside coarse gap-pair geometry.",
        "null_scope_warning": "Transition-level null; shuffled labels are not required to reconstruct one globally consistent Mobius charge sequence.",
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
        tests = result["pair_stratified_transition_tests"]
        print(
            f"N={result['n_primes']} offset={result['offset']} "
            f"a/m/z={obs['aligned_count']}/{obs['misaligned_count']}/{obs['zero_count']} "
            f"sr_z0={obs['sr_zero_minus_nonzero']:.5f} "
            f"null={tests['sr_zero_minus_nonzero']['null_mean']:.5f} "
            f"z={tests['sr_zero_minus_nonzero']['z']:.2f} "
            f"p={tests['sr_zero_minus_nonzero']['p_two_sided']:.3f} "
            f"sr_am={obs['sr_aligned_minus_misaligned']:.5f} "
            f"z={tests['sr_aligned_minus_misaligned']['z']:.2f} "
            f"p={tests['sr_aligned_minus_misaligned']['p_two_sided']:.3f}"
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
