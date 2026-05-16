#!/usr/bin/env python3
"""
Endpoint stability filter for the GUE/Poisson boundary direction.

This is the regressively repaired reader check after the 10:31 cycle: before
asking whether RP is a third-included boundary, verify that the same reader
family recognizes the two endpoint poles under size/seed/window stress.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_unfolding_transfer_matrix import (
    clean_gaps,
    exact_local_unfold,
    gue_gaps,
    poisson_gaps,
)
from exp_rosenzweig_porter_bridge_physical_audit import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    fit_brody_q,
    fit_mixture_weight,
)
from exp_rp_boundary_raw_count_null_audit import wilson_interval
from exp_rp_unfolding_sensitivity_audit import local_unfold_gaps as odd_coerced_unfold


FEATURE_NAMES = [
    "SR",
    "SR2",
    "L1",
    "L2",
    "triple_var",
    "brody_q",
    "berry_robnick_like_gue_weight",
]


def parse_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def feature_vector(gaps: np.ndarray, grid_size: int) -> dict[str, float]:
    gaps = clean_gaps(gaps)
    features = {name: float(fn(gaps)) for name, fn in OBSERVABLES_CANONICAL.items()}
    q, _ = fit_brody_q(gaps, grid_size)
    w, _ = fit_mixture_weight(gaps, grid_size)
    features["brody_q"] = float(q)
    features["berry_robnick_like_gue_weight"] = float(w)
    return features


def read_gaps(gaps: np.ndarray, reader: str) -> np.ndarray:
    if reader == "global_mean":
        return clean_gaps(gaps)
    mode, window_raw = reader.split(":w", 1)
    window = int(window_raw)
    if mode == "exact_local":
        return exact_local_unfold(gaps, window)
    if mode == "odd_coerced":
        return clean_gaps(odd_coerced_unfold(gaps, window))
    raise ValueError(f"unknown reader: {reader}")


def build_rows(args: argparse.Namespace, split: str, seeds: list[int]) -> list[dict[str, Any]]:
    rows = []
    readers = ["global_mean"] + [
        f"{mode}:w{window}"
        for mode in ("exact_local", "odd_coerced")
        for window in parse_ints(args.local_windows)
    ]
    for n in parse_ints(args.sizes):
        for seed_idx, seed in enumerate(seeds):
            sources = {
                "GUE": gue_gaps(n, args.reps, seed + n * 1009, args.central_fraction),
                "Poisson": poisson_gaps(n, args.reps, seed + n * 1013, args.central_fraction),
            }
            for source_type, gaps in sources.items():
                source_id = f"{split}_{source_type}_N{n}_s{seed_idx}"
                for reader in readers:
                    features = feature_vector(read_gaps(gaps, reader), args.grid_size)
                    rows.append(
                        {
                            "split": split,
                            "source_id": source_id,
                            "source_type": source_type,
                            "n": n,
                            "seed": seed,
                            "reader": reader,
                            "n_spacings": int(len(gaps)),
                            "features": {key: round(value, 9) for key, value in features.items()},
                        }
                    )
    return rows


def fit_reader_centroids(rows: list[dict[str, Any]], labels: dict[str, str] | None = None) -> dict[str, Any]:
    by_reader: dict[str, dict[str, list[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        label = labels.get(row["source_id"], row["source_type"]) if labels else row["source_type"]
        by_reader[row["reader"]][label].append(np.array([row["features"][name] for name in FEATURE_NAMES], dtype=float))

    model = {}
    for reader, groups in by_reader.items():
        all_vectors = np.vstack([item for vectors in groups.values() for item in vectors])
        scale = np.std(all_vectors, axis=0)
        scale[scale <= 1e-9] = 1.0
        centroids = {}
        for label, vectors in groups.items():
            centroids[label] = np.mean(np.vstack(vectors), axis=0)
        model[reader] = {"scale": scale, "centroids": centroids}
    return model


def classify(row: dict[str, Any], model: dict[str, Any], min_margin: float) -> dict[str, Any]:
    item = model[row["reader"]]
    vector = np.array([row["features"][name] for name in FEATURE_NAMES], dtype=float)
    distances = {}
    for label, centroid in item["centroids"].items():
        delta = (vector - centroid) / item["scale"]
        distances[label] = float(np.linalg.norm(delta) / math.sqrt(len(FEATURE_NAMES)))
    own = distances[row["source_type"]]
    other_label = "Poisson" if row["source_type"] == "GUE" else "GUE"
    other = distances[other_label]
    margin = other - own
    predicted = min(distances, key=distances.get)
    return {
        "predicted": predicted,
        "own_distance": round(own, 6),
        "other_distance": round(other, 6),
        "margin": round(margin, 6),
        "endpoint_reader_pass": bool(predicted == row["source_type"] and margin >= min_margin),
    }


def score_sources(rows: list[dict[str, Any]], model: dict[str, Any], min_margin: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reader_rows = []
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        judged = {**row, **classify(row, model, min_margin)}
        reader_rows.append(judged)
        by_source[row["source_id"]].append(judged)

    source_rows = []
    for source_id, items in sorted(by_source.items()):
        passes = sum(1 for item in items if item["endpoint_reader_pass"])
        margins = [item["margin"] for item in items]
        source_rows.append(
            {
                "source_id": source_id,
                "source_type": items[0]["source_type"],
                "n": items[0]["n"],
                "seed": items[0]["seed"],
                "reader_passes": passes,
                "reader_total": len(items),
                "min_margin": round(float(min(margins)), 6),
                "median_margin": round(float(np.median(margins)), 6),
                "endpoint_stable": passes == len(items),
                "reader_predictions": [
                    {
                        "reader": item["reader"],
                        "predicted": item["predicted"],
                        "margin": item["margin"],
                        "pass": item["endpoint_reader_pass"],
                    }
                    for item in items
                ],
            }
        )
    return reader_rows, source_rows


def shuffled_label_map(calibration_rows: list[dict[str, Any]], rng: np.random.Generator) -> dict[str, str]:
    ids = sorted({row["source_id"] for row in calibration_rows})
    true_labels = [next(row["source_type"] for row in calibration_rows if row["source_id"] == source_id) for source_id in ids]
    shuffled = list(true_labels)
    rng.shuffle(shuffled)
    return dict(zip(ids, shuffled))


def null_success_counts(
    calibration_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[int]:
    rng = np.random.default_rng(args.null_seed)
    counts = []
    for _ in range(args.label_null_trials):
        labels = shuffled_label_map(calibration_rows, rng)
        model = fit_reader_centroids(calibration_rows, labels=labels)
        _, source_rows = score_sources(test_rows, model, args.min_margin)
        counts.append(sum(1 for row in source_rows if row["endpoint_stable"]))
    return counts


def summarize(source_rows: list[dict[str, Any]], null_counts: list[int]) -> dict[str, Any]:
    out = {}
    for source_type in ("GUE", "Poisson"):
        group = [row for row in source_rows if row["source_type"] == source_type]
        successes = sum(1 for row in group if row["endpoint_stable"])
        null_successes = sum(min(count, len(group)) for count in null_counts)
        null_total = len(null_counts) * len(group)
        p_value = (1 + sum(1 for count in null_counts if count >= successes)) / (1 + len(null_counts))
        out[source_type] = {
            "criterion": "all readers classify the endpoint with preregistered margin",
            "observed_successes": successes,
            "observed_total": len(group),
            "observed_rate": round(successes / len(group), 6) if group else None,
            "observed_wilson_95": wilson_interval(successes, len(group)) if group else None,
            "null_successes": null_successes,
            "null_total": null_total,
            "null_rate": round(null_successes / null_total, 6) if null_total else None,
            "permutation_p_value": round(p_value, 6),
            "min_margin": round(float(min(row["min_margin"] for row in group)), 6) if group else None,
            "median_margin": round(float(np.median([row["median_margin"] for row in group])), 6) if group else None,
        }
    all_successes = sum(1 for row in source_rows if row["endpoint_stable"])
    out["combined"] = {
        "observed_successes": all_successes,
        "observed_total": len(source_rows),
        "observed_rate": round(all_successes / len(source_rows), 6) if source_rows else None,
        "null_successes": sum(null_counts),
        "null_total": len(null_counts) * len(source_rows),
        "permutation_p_value": round((1 + sum(1 for count in null_counts if count >= all_successes)) / (1 + len(null_counts)), 6),
    }
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    calibration_seeds = parse_ints(args.calibration_seeds)
    test_seeds = parse_ints(args.test_seeds)
    calibration_rows = build_rows(args, "calibration", calibration_seeds)
    test_rows = build_rows(args, "test", test_seeds)
    model = fit_reader_centroids(calibration_rows)
    reader_rows, source_rows = score_sources(test_rows, model, args.min_margin)
    null_counts = null_success_counts(calibration_rows, test_rows, args)
    output = {
        "experiment": "endpoint_stability_filter",
        "question": "Do GUE and Poisson remain endpoint-stable under the reader family before RP boundary residue is tested again?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "endpoint_reader_pass",
            "endpoint_stable",
            "centroid_margin",
            "label_permutation_null_counts",
        ],
        "parameters": {
            "sizes": parse_ints(args.sizes),
            "calibration_seeds": calibration_seeds,
            "test_seeds": test_seeds,
            "reps": args.reps,
            "central_fraction": args.central_fraction,
            "local_windows": parse_ints(args.local_windows),
            "grid_size": args.grid_size,
            "min_margin": args.min_margin,
            "label_null_trials": args.label_null_trials,
            "null_seed": args.null_seed,
        },
        "threshold_preregistered": {
            "endpoint_stable": f"every reader for a source row predicts the true endpoint and centroid margin >= {args.min_margin}",
            "positive_lift_unthresholded": "not used; this cycle reports thresholded endpoint stability with raw counts and permutation p-value",
            "graph_specific_residue_after_nulls": "not tested; no graph-only residue is promoted",
        },
        "observable_contract": {
            "claim": "GUE/Poisson endpoints are valid filters for the boundary if both poles stay stable across reader/window/size/seed stress under a calibrated endpoint classifier",
            "observable": "endpoint_stable per source row, plus reader-level centroid margins from canonical spectral features",
            "operator": "calibrate endpoint centroids on held-out GUE/Poisson controls, then stress test readers on independent seeds",
            "generator": "GUE matrices and Poisson exponential spacings",
            "denominator": "domain x size x test seed source rows; each source row contains all readers",
            "non_possible": "boundary-terzo incluso cannot be tested with this reader if either endpoint fails stability or label-permutation nulls match observed stability",
            "not_tested": "RP boundary residue, Anderson 3D, experimental spectra, N to infinity, analytic universality",
        },
        "summary": summarize(source_rows, null_counts),
        "null_counts": null_counts,
        "source_rows": source_rows,
        "reader_rows": reader_rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/endpoint_stability_filter_20260516_1045.json")
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
    run(parser.parse_args())


if __name__ == "__main__":
    main()
