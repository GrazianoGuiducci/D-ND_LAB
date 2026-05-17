#!/usr/bin/env python3
"""Precondition audit for the finance lag-memory detector.

This tool does not promote a finance claim and does not touch market data. It
tests whether the synthetic positive object used by the Finance Lab has a
measurable admission precondition before another block21 repair cycle is run.

The current candidate precondition is local and readable:

    matched_filter_score_at_candidate_split >= threshold

where the matched filter is:

    max(delta rho_1, 0) + max(-delta rho_2, 0)

The audit validates threshold candidates against synthetic positives and
controls, then reports whether any precondition reaches the recovery/control
gate. The result is a design constraint for the next cycle, not a trading
signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


N = 768
SEEDS = tuple(range(6200, 6212))
PLANTED_SPLITS = (0.35, 0.50, 0.65)
VARIANTS = (
    "lag_memory_const_vol",
    "iid_const_vol",
    "drift_const_vol",
    "vol_only",
)
POSITIVE = "lag_memory_const_vol"
FRACTIONS = np.arange(0.20, 0.81, 0.05)
MATCH_WINDOW = 100
NULL_FAMILIES = ("iid_shuffle", "circular_block_5", "circular_block_21")
Z_PROMOTE = 3.0
P_PROMOTE = 0.05

DEFAULT_SCORE_THRESHOLDS = (0.45, 0.50, 0.55, 0.60, 0.65)
DEFAULT_AREA_THRESHOLDS = (0.00, 0.08, 0.10, 0.12, 0.14)


def seed_for(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def standardize_segment(values: np.ndarray, target_sigma: float) -> np.ndarray:
    centered = values - float(np.mean(values))
    std = float(np.std(centered, ddof=1))
    if std <= 0 or not math.isfinite(std):
        return np.zeros_like(values)
    return centered / std * target_sigma


def lag_memory_filter(noise: np.ndarray) -> np.ndarray:
    """Stationary oscillatory AR(2)-like post-split memory object."""
    x = np.zeros_like(noise)
    a1 = 0.74
    a2 = -0.52
    for i, eps in enumerate(noise):
        if i == 0:
            x[i] = eps
        elif i == 1:
            x[i] = eps + a1 * x[i - 1]
        else:
            x[i] = eps + a1 * x[i - 1] + a2 * x[i - 2]
    return x


def variant_returns(n: int, seed: int, split_fraction: float, variant: str) -> np.ndarray:
    rng = np.random.default_rng(seed_for("variant", seed, split_fraction, variant))
    split = int(round(n * split_fraction))
    target_sigma = 0.0115
    df = 5.0
    scale = math.sqrt(df / (df - 2.0))
    pre_noise = rng.standard_t(df, size=split) / scale
    post_noise = rng.standard_t(df, size=n - split) / scale

    if variant == "lag_memory_const_vol":
        left = standardize_segment(pre_noise, target_sigma)
        right = standardize_segment(lag_memory_filter(post_noise), target_sigma)
        return np.concatenate([left, right])
    if variant == "iid_const_vol":
        left = standardize_segment(pre_noise, target_sigma)
        right = standardize_segment(post_noise, target_sigma)
        return np.concatenate([left, right])
    if variant == "drift_const_vol":
        left = standardize_segment(pre_noise, target_sigma) + 0.00075
        right = standardize_segment(post_noise, target_sigma) - 0.00105
        return np.concatenate([left, right])
    if variant == "vol_only":
        left = standardize_segment(pre_noise, 0.0080)
        right = standardize_segment(post_noise, 0.0160)
        return np.concatenate([left, right])
    raise ValueError(f"unknown variant: {variant}")


def rolling_scale(returns: np.ndarray, radius: int = 10) -> np.ndarray:
    window = 2 * radius + 1
    kernel = np.ones(window, dtype=float)
    values = returns.astype(float)
    counts = np.convolve(np.ones_like(values), kernel, mode="same")
    sums = np.convolve(values, kernel, mode="same")
    sums2 = np.convolve(values * values, kernel, mode="same")
    mean = sums / counts
    variance = np.maximum((sums2 - counts * mean * mean) / np.maximum(counts - 1.0, 1.0), 0.0)
    std = np.sqrt(variance)
    return np.where((std > 1e-12) & np.isfinite(std), std, 1.0)


def autocorr(values: np.ndarray, lag: int) -> float:
    if len(values) <= lag + 3:
        return 0.0
    x = values[:-lag]
    y = values[lag:]
    sx = float(np.std(x, ddof=1))
    sy = float(np.std(y, ddof=1))
    if sx <= 0 or sy <= 0 or not math.isfinite(sx) or not math.isfinite(sy):
        return 0.0
    return float(np.mean((x - np.mean(x)) * (y - np.mean(y))) / (sx * sy))


def local_orientation_area(returns: np.ndarray) -> np.ndarray:
    z = returns / rolling_scale(returns)
    return z[1:-1] ** 2 - z[:-2] * z[2:]


def matched_filter_score_at(returns: np.ndarray, split_fraction: float) -> float:
    z = returns / rolling_scale(returns)
    split = int(round(len(returns) * split_fraction))
    split = max(MATCH_WINDOW, min(len(z) - MATCH_WINDOW, split))
    left = z[split - MATCH_WINDOW:split]
    right = z[split:split + MATCH_WINDOW]
    lag1_delta = autocorr(right, 1) - autocorr(left, 1)
    lag2_delta = autocorr(right, 2) - autocorr(left, 2)
    return max(lag1_delta, 0.0) + max(-lag2_delta, 0.0)


def area_gap_at(returns: np.ndarray, split_fraction: float) -> float:
    split = int(round(len(returns) * split_fraction))
    area_split = max(2, min(len(returns) - 4, split - 1))
    areas = local_orientation_area(returns)
    left_area = areas[:area_split]
    right_area = areas[area_split:]
    return abs(float(np.mean(right_area) - np.mean(left_area)))


def split_profile(returns: np.ndarray) -> np.ndarray:
    return np.asarray([matched_filter_score_at(returns, float(frac)) for frac in FRACTIONS], dtype=float)


def iid_shuffle(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = values.copy()
    rng.shuffle(out)
    return out


def circular_block_shuffle(values: np.ndarray, rng: np.random.Generator, block: int) -> np.ndarray:
    n = len(values)
    starts = rng.integers(0, n, size=math.ceil(n / block))
    pieces = []
    for start in starts:
        idx = (np.arange(start, start + block) % n).astype(int)
        pieces.append(values[idx])
    return np.concatenate(pieces)[:n]


def shuffled(values: np.ndarray, rng: np.random.Generator, null_name: str) -> np.ndarray:
    if null_name == "iid_shuffle":
        return iid_shuffle(values, rng)
    if null_name == "circular_block_5":
        return circular_block_shuffle(values, rng, 5)
    if null_name == "circular_block_21":
        return circular_block_shuffle(values, rng, 21)
    raise ValueError(f"unknown null: {null_name}")


def clusterize(z_profile: np.ndarray, threshold: float = Z_PROMOTE) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    start: int | None = None
    values: list[float] = []
    for i, value in enumerate(z_profile):
        if value >= threshold:
            if start is None:
                start = i
                values = []
            values.append(float(value))
        elif start is not None:
            clusters.append(make_cluster(start, i - 1, values))
            start = None
            values = []
    if start is not None:
        clusters.append(make_cluster(start, len(z_profile) - 1, values))
    return clusters


def make_cluster(start: int, end: int, values: list[float]) -> dict[str, Any]:
    return {
        "start_index": start,
        "end_index": end,
        "start_fraction": float(FRACTIONS[start]),
        "end_fraction": float(FRACTIONS[end]),
        "length": end - start + 1,
        "mass": float(sum(v - Z_PROMOTE for v in values)),
        "peak_z": float(max(values)),
        "endpoint_touch": start == 0 or end == len(FRACTIONS) - 1,
        "endpoint_adjacent": start <= 1 or end >= len(FRACTIONS) - 2,
    }


def best_cluster(clusters: list[dict[str, Any]]) -> dict[str, Any] | None:
    filtered = [
        c for c in clusters
        if not c.get("endpoint_touch") and not c.get("endpoint_adjacent")
    ]
    if not filtered:
        return None
    return max(filtered, key=lambda c: (float(c["mass"]), float(c["peak_z"])))


def profile_stats(ordered_profile: np.ndarray, null_profiles: np.ndarray) -> dict[str, Any]:
    split_mean = np.mean(null_profiles, axis=0)
    split_std = np.std(null_profiles, axis=0, ddof=1)
    split_std = np.where(split_std > 0, split_std, np.inf)
    ordered_z = (ordered_profile - split_mean) / split_std
    ordered_cluster = best_cluster(clusterize(ordered_z))
    ordered_mass = float(ordered_cluster["mass"]) if ordered_cluster else 0.0

    null_masses = []
    for row in null_profiles:
        row_z = (row - split_mean) / split_std
        cluster = best_cluster(clusterize(row_z))
        null_masses.append(float(cluster["mass"]) if cluster else 0.0)

    null_arr = np.asarray(null_masses, dtype=float)
    null_mean = float(np.mean(null_arr))
    null_std = float(np.std(null_arr, ddof=1))
    effect_z = (ordered_mass - null_mean) / null_std if null_std > 0 else 0.0
    p_value = float((1 + np.sum(null_arr >= ordered_mass)) / (len(null_arr) + 1))
    return {
        "cluster_effect_z": float(effect_z),
        "cluster_p_value": p_value,
        "best_cluster_non_endpoint": ordered_cluster,
        "verdict": (
            "DND_DELTA"
            if ordered_cluster and effect_z >= Z_PROMOTE and p_value <= P_PROMOTE
            else "NO_DELTA"
        ),
    }


def evaluate_case(seed: int, split: float, variant: str, shuffles: int) -> dict[str, Any]:
    returns = variant_returns(N, seed, split, variant)
    ordered_profile = split_profile(returns)
    null_results = {}
    for null_name in NULL_FAMILIES:
        rng = np.random.default_rng(seed_for("precondition", seed, split, variant, null_name))
        null_profiles = np.asarray([
            split_profile(shuffled(returns, rng, null_name))
            for _ in range(shuffles)
        ], dtype=float)
        null_results[null_name] = profile_stats(ordered_profile, null_profiles)

    robust = all(result["verdict"] == "DND_DELTA" for result in null_results.values())
    stage1 = (
        null_results["iid_shuffle"]["verdict"] == "DND_DELTA"
        and null_results["circular_block_5"]["verdict"] == "DND_DELTA"
    )
    return {
        "seed": seed,
        "split": split,
        "variant": variant,
        "positive": variant == POSITIVE,
        "matched_filter_score_at_split": matched_filter_score_at(returns, split),
        "area_gap_abs_at_split": area_gap_at(returns, split),
        "stage1_iid_block5_delta": stage1,
        "robust_delta_all_nulls": robust,
        "null_results": null_results,
    }


def rate(count: int, denom: int) -> float:
    return float(count / denom) if denom else 0.0


def evaluate_thresholds(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for score_min in DEFAULT_SCORE_THRESHOLDS:
        for area_min in DEFAULT_AREA_THRESHOLDS:
            selected = [
                r for r in records
                if r["matched_filter_score_at_split"] >= score_min
                and r["area_gap_abs_at_split"] >= area_min
            ]
            positives = [r for r in selected if r["positive"]]
            controls = [r for r in selected if not r["positive"]]
            positive_total = sum(1 for r in records if r["positive"])
            control_total = sum(1 for r in records if not r["positive"])
            positive_robust = sum(1 for r in positives if r["robust_delta_all_nulls"])
            control_robust = sum(1 for r in controls if r["robust_delta_all_nulls"])
            entry = {
                "score_min": score_min,
                "area_gap_min": area_min,
                "selected_total": len(selected),
                "selected_positives": len(positives),
                "selected_controls": len(controls),
                "positive_coverage_rate": rate(len(positives), positive_total),
                "control_selection_rate": rate(len(controls), control_total),
                "positive_robust_rate_after_precondition": rate(positive_robust, len(positives)),
                "control_robust_rate_after_precondition": rate(control_robust, len(controls)),
                "gate_pass": (
                    len(positives) >= 12
                    and rate(positive_robust, len(positives)) >= 0.70
                    and rate(len(controls), control_total) <= 0.05
                    and rate(control_robust, len(controls)) <= 0.05
                ),
            }
            out.append(entry)
    return out


def audit(shuffles: int) -> dict[str, Any]:
    records = [
        evaluate_case(seed, split, variant, shuffles)
        for seed in SEEDS
        for split in PLANTED_SPLITS
        for variant in VARIANTS
    ]
    thresholds = evaluate_thresholds(records)
    passing = [t for t in thresholds if t["gate_pass"]]
    passing.sort(key=lambda t: (-t["selected_positives"], t["score_min"], t["area_gap_min"]))
    selected = passing[0] if passing else None

    aggregate = {
        "cases": len(records),
        "positive_cases": sum(1 for r in records if r["positive"]),
        "control_cases": sum(1 for r in records if not r["positive"]),
        "positive_stage1_rate": rate(
            sum(1 for r in records if r["positive"] and r["stage1_iid_block5_delta"]),
            sum(1 for r in records if r["positive"]),
        ),
        "positive_robust_rate": rate(
            sum(1 for r in records if r["positive"] and r["robust_delta_all_nulls"]),
            sum(1 for r in records if r["positive"]),
        ),
        "control_robust_rate": rate(
            sum(1 for r in records if (not r["positive"]) and r["robust_delta_all_nulls"]),
            sum(1 for r in records if not r["positive"]),
        ),
    }
    return {
        "schema": "finance_lag_memory_precondition.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "question": (
            "Which measurable precondition must hold before lag_memory_const_vol "
            "is admitted to another block21 repair or aggregation cycle?"
        ),
        "precondition_candidate": (
            "matched_filter_score_at_candidate_split >= score_min and optional "
            "area_gap_abs_at_candidate_split >= area_gap_min"
        ),
        "interpretation": (
            "This is synthetic detector calibration. A passing precondition "
            "authorizes a narrower next cycle; it does not authorize a market "
            "claim or trading signal."
        ),
        "n": N,
        "seeds": list(SEEDS),
        "splits": list(PLANTED_SPLITS),
        "variants": list(VARIANTS),
        "null_families": list(NULL_FAMILIES),
        "shuffles": shuffles,
        "aggregate": aggregate,
        "thresholds": thresholds,
        "selected_precondition": selected,
        "verdict": "PRECONDITION_FOUND" if selected else "NO_PRECONDITION_FOUND",
        "next_cycle_constraint": (
            "If PRECONDITION_FOUND, the next cycle may test the selected "
            "precondition as an admission gate against iid, block5 and block21 "
            "nulls. It must not broaden window/jitter tuning before this gate "
            "is tested."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--shuffles", type=int, default=48, help="surrogates per null; minimum 48")
    args = parser.parse_args()

    if args.shuffles < 48:
        print("--shuffles must be >= 48 for this precondition audit", file=sys.stderr)
        return 2

    payload = audit(args.shuffles)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Finance lag-memory precondition audit")
        print(f"verdict: {payload['verdict']}")
        print(f"cases: {payload['aggregate']['cases']}")
        print(f"positive_robust_rate: {payload['aggregate']['positive_robust_rate']:.3f}")
        selected = payload["selected_precondition"]
        if selected:
            print(
                "selected_precondition: "
                f"score_min={selected['score_min']}, "
                f"area_gap_min={selected['area_gap_min']}, "
                f"selected_positives={selected['selected_positives']}, "
                f"positive_robust_after={selected['positive_robust_rate_after_precondition']:.3f}, "
                f"selected_controls={selected['selected_controls']}"
            )
        else:
            print("selected_precondition: none")
    return 0 if payload["verdict"] == "PRECONDITION_FOUND" else 1


if __name__ == "__main__":
    raise SystemExit(main())
