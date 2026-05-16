#!/usr/bin/env python3
"""
Endpoint-gated RP boundary test.

This cycle starts from the closed GUE/Poisson endpoint gate and only then asks
whether RP rows occupy a third-included position between the two endpoint
centroids.  The null preserves per-reader feature marginals and breaks the
row-level RP feature coupling.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_unfolding_transfer_matrix import parse_floats, rp_gaps
from exp_endpoint_feature_scramble_null import (
    count_histogram,
    feature_scramble_null_counts,
    tail_stats,
)
from exp_endpoint_stability_filter import (
    FEATURE_NAMES,
    build_rows,
    feature_vector,
    fit_reader_centroids,
    null_success_counts,
    parse_ints,
    read_gaps,
    score_sources,
)
from exp_rosenzweig_porter_bridge_physical_audit import OBSERVABLES_REGISTRY_VERSION


def readers(local_windows: str) -> list[str]:
    return ["global_mean"] + [
        f"{mode}:w{window}"
        for mode in ("exact_local", "odd_coerced")
        for window in parse_ints(local_windows)
    ]


def build_rp_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = []
    for n in parse_ints(args.sizes):
        for seed_idx, seed in enumerate(parse_ints(args.test_seeds)):
            for lam in parse_floats(args.rp_lambdas):
                gaps = rp_gaps(
                    lam,
                    n,
                    args.reps,
                    seed + n * 1019 + int(round(lam * 10000)),
                    args.central_fraction,
                )
                source_id = f"RP_lambda_{lam:.3f}_N{n}_s{seed_idx}"
                for reader in readers(args.local_windows):
                    features = feature_vector(read_gaps(gaps, reader), args.grid_size)
                    rows.append(
                        {
                            "source_id": source_id,
                            "source_type": "RP",
                            "lambda": round(float(lam), 6),
                            "n": n,
                            "seed": seed,
                            "reader": reader,
                            "n_spacings": int(len(gaps)),
                            "features": {key: round(value, 9) for key, value in features.items()},
                        }
                    )
    return rows


def classify_boundary_reader(row: dict[str, Any], model: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    item = model[row["reader"]]
    vector = np.array([row["features"][name] for name in FEATURE_NAMES], dtype=float)
    distances = {}
    for label, centroid in item["centroids"].items():
        delta = (vector - centroid) / item["scale"]
        distances[label] = float(np.linalg.norm(delta) / np.sqrt(len(FEATURE_NAMES)))
    d_gue = distances["GUE"]
    d_poisson = distances["Poisson"]
    denom = d_gue + d_poisson
    balance = 1.0 - abs(d_gue - d_poisson) / denom if denom > 1e-12 else 0.0
    bridge_distance = min(d_gue, d_poisson)
    pass_reader = bool(
        balance >= args.min_balance
        and bridge_distance >= args.min_bridge_distance
        and bridge_distance <= args.max_bridge_distance
    )
    return {
        "distance_gue": round(d_gue, 6),
        "distance_poisson": round(d_poisson, 6),
        "balance": round(balance, 6),
        "bridge_distance": round(bridge_distance, 6),
        "boundary_reader_pass": pass_reader,
    }


def score_rp_sources(rows: list[dict[str, Any]], model: dict[str, Any], args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reader_rows = []
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        judged = {**row, **classify_boundary_reader(row, model, args)}
        reader_rows.append(judged)
        by_source[row["source_id"]].append(judged)

    source_rows = []
    for source_id, items in sorted(by_source.items()):
        passes = sum(1 for item in items if item["boundary_reader_pass"])
        balances = [item["balance"] for item in items]
        distances = [item["bridge_distance"] for item in items]
        source_rows.append(
            {
                "source_id": source_id,
                "lambda": items[0]["lambda"],
                "n": items[0]["n"],
                "seed": items[0]["seed"],
                "reader_passes": passes,
                "reader_total": len(items),
                "median_balance": round(float(np.median(balances)), 6),
                "min_balance": round(float(min(balances)), 6),
                "median_bridge_distance": round(float(np.median(distances)), 6),
                "boundary_candidate": bool(passes >= args.min_reader_passes),
                "reader_scores": [
                    {
                        "reader": item["reader"],
                        "balance": item["balance"],
                        "bridge_distance": item["bridge_distance"],
                        "pass": item["boundary_reader_pass"],
                    }
                    for item in items
                ],
            }
        )
    return reader_rows, source_rows


def scramble_rows(rows: list[dict[str, Any]], rng: np.random.Generator) -> list[dict[str, Any]]:
    scrambled = [{**row, "features": dict(row["features"])} for row in rows]
    by_reader: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(scrambled):
        by_reader[row["reader"]].append(idx)
    for indices in by_reader.values():
        for feature in FEATURE_NAMES:
            values = [scrambled[idx]["features"][feature] for idx in indices]
            rng.shuffle(values)
            for idx, value in zip(indices, values):
                scrambled[idx]["features"][feature] = value
    return scrambled


def rp_feature_scramble_counts(rows: list[dict[str, Any]], model: dict[str, Any], args: argparse.Namespace) -> list[int]:
    rng = np.random.default_rng(args.rp_scramble_seed)
    counts = []
    for _ in range(args.rp_scramble_trials):
        _, source_rows = score_rp_sources(scramble_rows(rows, rng), model, args)
        counts.append(sum(1 for row in source_rows if row["boundary_candidate"]))
    return counts


def lambda_summary(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for lam in sorted({row["lambda"] for row in source_rows}):
        group = [row for row in source_rows if row["lambda"] == lam]
        out[f"{lam:.3f}"] = {
            "boundary_candidates": sum(1 for row in group if row["boundary_candidate"]),
            "total": len(group),
            "median_balance": round(float(np.median([row["median_balance"] for row in group])), 6),
            "median_bridge_distance": round(float(np.median([row["median_bridge_distance"] for row in group])), 6),
        }
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    calibration_rows = build_rows(args, "calibration", parse_ints(args.calibration_seeds))
    endpoint_test_rows = build_rows(args, "test", parse_ints(args.test_seeds))
    model = fit_reader_centroids(calibration_rows)

    _, endpoint_sources = score_sources(endpoint_test_rows, model, args.min_margin)
    endpoint_observed = sum(1 for row in endpoint_sources if row["endpoint_stable"])
    label_counts = null_success_counts(calibration_rows, endpoint_test_rows, args)
    endpoint_feature_counts = feature_scramble_null_counts(endpoint_test_rows, model, args)

    rp_rows = build_rp_rows(args)
    rp_reader_rows, rp_source_rows = score_rp_sources(rp_rows, model, args)
    rp_observed = sum(1 for row in rp_source_rows if row["boundary_candidate"])
    rp_null_counts = rp_feature_scramble_counts(rp_rows, model, args)

    output = {
        "experiment": "endpoint_gated_rp_boundary",
        "question": "After endpoint closure, do RP rows form a third-included boundary against a row-aligned feature-scramble null?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "endpoint_stable",
            "endpoint_feature_scramble_null_counts",
            "rp_boundary_candidate",
            "centroid_distance_balance",
            "rp_feature_scramble_null_counts",
            "raw_p",
            "add_one_p",
        ],
        "parameters": {
            "sizes": parse_ints(args.sizes),
            "calibration_seeds": parse_ints(args.calibration_seeds),
            "test_seeds": parse_ints(args.test_seeds),
            "reps": args.reps,
            "rp_lambdas": parse_floats(args.rp_lambdas),
            "local_windows": parse_ints(args.local_windows),
            "min_margin": args.min_margin,
            "min_balance": args.min_balance,
            "min_bridge_distance": args.min_bridge_distance,
            "max_bridge_distance": args.max_bridge_distance,
            "min_reader_passes": args.min_reader_passes,
            "label_null_trials": args.label_null_trials,
            "feature_scramble_trials": args.feature_scramble_trials,
            "rp_scramble_trials": args.rp_scramble_trials,
        },
        "threshold_preregistered": {
            "endpoint_gate": f"36/36 endpoint rows stable and endpoint feature-scramble add_one_p <= {args.alpha}",
            "rp_boundary_candidate": f"source row has at least {args.min_reader_passes}/5 readers with centroid balance >= {args.min_balance} and bridge_distance in [{args.min_bridge_distance}, {args.max_bridge_distance}]",
            "p_value_definition": "right tail; raw_p=k/N and add_one_p=(k+1)/(N+1), where k is null trials with candidate count >= observed",
        },
        "observable_contract": {
            "claim": "RP is an endpoint-gated third-included boundary only if endpoint closure holds and RP candidate count beats row-aligned feature-scramble nulls",
            "observable": "endpoint_stable count, RP centroid-distance balance count, raw/add-one p-values",
            "operator": "calibrate GUE/Poisson endpoint centroids; score RP rows by balanced distance to both endpoint centroids; compare to feature-scrambled RP rows",
            "generator": "GUE matrices, Poisson exponential spacings, RP H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE",
            "denominator": "endpoint: 36 source rows x 5 readers; RP: lambda x size x test seed source rows x 5 readers",
            "non_possible": "third included if endpoint gate fails or RP feature-scramble null reaches the observed candidate count",
            "not_tested": "Anderson 3D, experimental spectra, N to infinity, analytic universality, new lambda search",
        },
        "endpoint_gate": {
            "observed_successes": endpoint_observed,
            "observed_total": len(endpoint_sources),
            "label_permutation": {
                "histogram": count_histogram(label_counts),
                "tail_stats": tail_stats(label_counts, endpoint_observed),
            },
            "feature_scramble": {
                "histogram": count_histogram(endpoint_feature_counts),
                "tail_stats": tail_stats(endpoint_feature_counts, endpoint_observed),
            },
            "pass": bool(
                endpoint_observed == len(endpoint_sources)
                and tail_stats(endpoint_feature_counts, endpoint_observed)["add_one_p"] <= args.alpha
            ),
        },
        "rp_boundary": {
            "observed_candidates": rp_observed,
            "observed_total": len(rp_source_rows),
            "by_lambda": lambda_summary(rp_source_rows),
            "feature_scramble": {
                "histogram": count_histogram(rp_null_counts),
                "tail_stats": tail_stats(rp_null_counts, rp_observed),
            },
            "pass": bool(
                rp_observed > 0
                and tail_stats(rp_null_counts, rp_observed)["add_one_p"] <= args.alpha
            ),
        },
        "source_rows": {
            "endpoint": endpoint_sources,
            "rp": rp_source_rows,
        },
        "reader_rows": {
            "rp": rp_reader_rows,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "endpoint_gate": output["endpoint_gate"],
        "rp_boundary": output["rp_boundary"],
    }, indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/endpoint_gated_rp_boundary_20260516_1104.json")
    parser.add_argument("--sizes", default="128,192,256")
    parser.add_argument("--calibration-seeds", default="202605161101,202605161102,202605161103,202605161104")
    parser.add_argument("--test-seeds", default="202605161105,202605161106,202605161107,202605161108,202605161109,202605161110")
    parser.add_argument("--reps", type=int, default=6)
    parser.add_argument("--rp-lambdas", default="0.045,0.060,0.075")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--local-windows", default="9,12")
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--min-margin", type=float, default=0.15)
    parser.add_argument("--min-balance", type=float, default=0.85)
    parser.add_argument("--min-bridge-distance", type=float, default=0.35)
    parser.add_argument("--max-bridge-distance", type=float, default=2.75)
    parser.add_argument("--min-reader-passes", type=int, default=4)
    parser.add_argument("--label-null-trials", type=int, default=128)
    parser.add_argument("--null-seed", type=int, default=202605161045)
    parser.add_argument("--feature-scramble-trials", type=int, default=512)
    parser.add_argument("--feature-scramble-seed", type=int, default=202605161058)
    parser.add_argument("--rp-scramble-trials", type=int, default=512)
    parser.add_argument("--rp-scramble-seed", type=int, default=202605161104)
    parser.add_argument("--alpha", type=float, default=0.05)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
