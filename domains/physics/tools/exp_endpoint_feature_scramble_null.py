#!/usr/bin/env python3
"""
Feature-scramble null for the endpoint stability filter.

The 10:45 endpoint filter repaired the reader but left label permutation too
permissive. This audit keeps the same observed reader/model contract and
scrambles feature columns within each reader on test rows. It preserves the
per-reader marginal distribution of every observable while breaking the
row-level multivariate endpoint signature.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_endpoint_stability_filter import (
    FEATURE_NAMES,
    build_rows,
    fit_reader_centroids,
    null_success_counts,
    parse_ints,
    score_sources,
    summarize,
)
from exp_rosenzweig_porter_bridge_physical_audit import OBSERVABLES_REGISTRY_VERSION


def scramble_test_features(
    rows: list[dict[str, Any]],
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    scrambled = [{**row, "features": dict(row["features"])} for row in rows]
    by_reader: dict[str, list[int]] = {}
    for idx, row in enumerate(scrambled):
        by_reader.setdefault(row["reader"], []).append(idx)

    for indices in by_reader.values():
        for feature in FEATURE_NAMES:
            values = [scrambled[idx]["features"][feature] for idx in indices]
            rng.shuffle(values)
            for idx, value in zip(indices, values):
                scrambled[idx]["features"][feature] = value
    return scrambled


def feature_scramble_null_counts(
    test_rows: list[dict[str, Any]],
    model: dict[str, Any],
    args: argparse.Namespace,
) -> list[int]:
    rng = np.random.default_rng(args.feature_scramble_seed)
    counts = []
    for _ in range(args.feature_scramble_trials):
        scrambled = scramble_test_features(test_rows, rng)
        _, source_rows = score_sources(scrambled, model, args.min_margin)
        counts.append(sum(1 for row in source_rows if row["endpoint_stable"]))
    return counts


def tail_stats(counts: list[int], observed: int) -> dict[str, Any]:
    ge = sum(1 for count in counts if count >= observed)
    total = len(counts)
    return {
        "tail": "right",
        "criterion": "null endpoint-stable source count >= observed endpoint-stable source count",
        "k_ge_observed": ge,
        "n_trials": total,
        "raw_p": round(ge / total, 9) if total else None,
        "add_one_p": round((ge + 1) / (total + 1), 9) if total else None,
        "max_null_count": max(counts) if counts else None,
        "mean_null_count": round(float(np.mean(counts)), 6) if counts else None,
        "median_null_count": round(float(np.median(counts)), 6) if counts else None,
    }


def count_histogram(counts: list[int]) -> dict[str, int]:
    values, freq = np.unique(np.array(counts, dtype=int), return_counts=True)
    return {str(int(value)): int(n) for value, n in zip(values, freq)}


def run(args: argparse.Namespace) -> dict[str, Any]:
    calibration_rows = build_rows(args, "calibration", parse_ints(args.calibration_seeds))
    test_rows = build_rows(args, "test", parse_ints(args.test_seeds))
    model = fit_reader_centroids(calibration_rows)
    reader_rows, source_rows = score_sources(test_rows, model, args.min_margin)
    observed_successes = sum(1 for row in source_rows if row["endpoint_stable"])

    label_counts = null_success_counts(calibration_rows, test_rows, args)
    feature_counts = feature_scramble_null_counts(test_rows, model, args)

    output = {
        "experiment": "endpoint_feature_scramble_null",
        "question": "Does the endpoint filter remain specific when row-level feature coupling is destroyed but per-reader feature marginals are preserved?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "endpoint_reader_pass",
            "endpoint_stable",
            "centroid_margin",
            "label_permutation_null_counts",
            "feature_scramble_null_counts",
            "raw_p",
            "add_one_p",
        ],
        "parameters": {
            "sizes": parse_ints(args.sizes),
            "calibration_seeds": parse_ints(args.calibration_seeds),
            "test_seeds": parse_ints(args.test_seeds),
            "reps": args.reps,
            "central_fraction": args.central_fraction,
            "local_windows": parse_ints(args.local_windows),
            "grid_size": args.grid_size,
            "min_margin": args.min_margin,
            "label_null_trials": args.label_null_trials,
            "null_seed": args.null_seed,
            "feature_scramble_trials": args.feature_scramble_trials,
            "feature_scramble_seed": args.feature_scramble_seed,
        },
        "threshold_preregistered": {
            "endpoint_stable": f"every reader for a source row predicts the true endpoint and centroid margin >= {args.min_margin}",
            "feature_scramble_null": "within each reader, independently permute each feature column across test rows; keep true source labels for scoring",
            "p_value_definition": "right tail; raw_p=k/N and add_one_p=(k+1)/(N+1), where k is null trials with stable source count >= observed",
        },
        "observable_contract": {
            "claim": "GUE/Poisson endpoint filter is specific if observed endpoint stability remains complete and feature-scramble nulls do not reconstruct complete stability",
            "observable": "endpoint_stable source count, reader centroid margin, feature-scramble null count distribution",
            "operator": "calibrate endpoint centroids once on true calibration rows; score true test rows and feature-scrambled test rows row-aligned by reader",
            "generator": "GUE matrices and Poisson exponential spacings",
            "denominator": "2 domains x sizes x test seeds source rows; each row requires all readers to pass",
            "non_possible": "specific endpoint filter if feature-scramble null reaches observed complete endpoint stability",
            "not_tested": "RP boundary residue, Anderson 3D, experimental spectra, asymptotic universality",
        },
        "summary": summarize(source_rows, label_counts),
        "observed_successes": observed_successes,
        "observed_total": len(source_rows),
        "label_permutation": {
            "counts": label_counts,
            "histogram": count_histogram(label_counts),
            "tail_stats": tail_stats(label_counts, observed_successes),
        },
        "feature_scramble": {
            "counts": feature_counts,
            "histogram": count_histogram(feature_counts),
            "tail_stats": tail_stats(feature_counts, observed_successes),
        },
        "source_rows": source_rows,
        "reader_rows": reader_rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "observed_successes": observed_successes,
        "observed_total": len(source_rows),
        "label_permutation": output["label_permutation"]["tail_stats"],
        "feature_scramble": output["feature_scramble"]["tail_stats"],
    }, indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/endpoint_feature_scramble_null_20260516_1058.json")
    parser.add_argument("--sizes", default="128,192,256")
    parser.add_argument("--calibration-seeds", default="202605161101,202605161102,202605161103,202605161104")
    parser.add_argument("--test-seeds", default="202605161105,202605161106,202605161107,202605161108,202605161109,202605161110")
    parser.add_argument("--reps", type=int, default=6)
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--local-windows", default="9,12")
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--min-margin", type=float, default=0.15)
    parser.add_argument("--label-null-trials", type=int, default=128)
    parser.add_argument("--null-seed", type=int, default=202605161045)
    parser.add_argument("--feature-scramble-trials", type=int, default=512)
    parser.add_argument("--feature-scramble-seed", type=int, default=202605161058)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
