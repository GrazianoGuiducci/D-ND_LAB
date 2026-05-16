#!/usr/bin/env python3
"""
Raw-count null audit for the Rosenzweig-Porter BOUNDARY row.

This extends the finite-size RP audit with explicit observed/null counts.  The
question is not whether a lambda looks intermediate once, but whether the same
row has enough graph-reader support to beat row-aligned nulls before the word
"residue" is allowed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from exp_rosenzweig_porter_bridge_physical_audit import (
    FEATURE_NAMES,
    OBSERVABLES_REGISTRY_VERSION,
    build_knn_edges,
    classical_state,
    compute_row,
    parse_floats,
    parse_ints,
    stability_state,
    standardized_matrix,
)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    phat = successes / total
    denom = 1.0 + z * z / total
    center = (phat + z * z / (2.0 * total)) / denom
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * total)) / total) / denom
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def binomial_tail_at_least(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0 if k <= 0 else 0.0
    if p >= 1.0:
        return 1.0 if k <= n else 0.0
    return float(sum(math.comb(n, i) * (p**i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1)))


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def classify_with_labels(rows: list[dict[str, Any]], k: int, labels: list[str]) -> list[dict[str, Any]]:
    x = standardized_matrix(rows)
    poi_idx = [i for i, label in enumerate(labels) if label == "Poisson_pole"]
    gue_idx = [i for i, label in enumerate(labels) if label == "GUE_pole"]
    if not poi_idx or not gue_idx:
        raise ValueError("labels must include Poisson and GUE poles")
    c_poi = np.mean(x[poi_idx], axis=0)
    c_gue = np.mean(x[gue_idx], axis=0)
    edges = build_knn_edges(x, k)
    degree = {i: 0 for i in range(len(rows))}
    for i, j, _ in edges:
        degree[i] += 1
        degree[j] += 1

    out = []
    for i, row in enumerate(rows):
        d_poi = float(np.linalg.norm(x[i] - c_poi))
        d_gue = float(np.linalg.norm(x[i] - c_gue))
        denom = d_poi + d_gue
        margin = float(abs(d_poi - d_gue) / denom) if denom > 1e-15 else 0.0
        incident = [(a, b) for a, b, _ in edges if a == i or b == i]
        cross = 0
        for a, b in incident:
            other = b if a == i else a
            if {labels[i], labels[other]} == {"Poisson_pole", "GUE_pole"}:
                cross += 1
            elif labels[i] == "flow_candidate" and labels[other] in {"Poisson_pole", "GUE_pole"}:
                cross += 1
        cross_fraction = float(cross / len(incident)) if incident else 0.0
        state = "class_interior"
        if labels[i] == "flow_candidate" and cross_fraction > 0.0 and margin < 0.35:
            state = "third_included_candidate"
        elif cross_fraction > 0.0:
            state = "cut_edge"
        out.append(
            {
                "domain_window": row["domain_window"],
                "boundary_state": state,
                "centroid_margin": margin,
                "cross_neighbor_fraction": cross_fraction,
                "degree": degree[i],
            }
        )
    return out


def rotate_labels(labels: list[str], offset: int) -> list[str]:
    if not labels:
        return labels
    offset = offset % len(labels)
    return labels[offset:] + labels[:offset]


def shuffled_labels(labels: list[str], rng: np.random.Generator) -> list[str]:
    shuffled = list(labels)
    rng.shuffle(shuffled)
    return shuffled


def empty_hits(lambdas: list[float]) -> dict[str, dict[str, Any]]:
    return {
        f"RP_lambda_{lam:.3f}": {
            "lambda": round(float(lam), 6),
            "observed_hits": 0,
            "label_shuffle_hits": 0,
            "position_shift_hits": 0,
            "brody_q": [],
            "mixture_w": [],
            "mean_ipr": [],
            "sr": [],
            "margins": [],
            "cross_fractions": [],
        }
        for lam in lambdas
    }


def audit_size(args: argparse.Namespace, n: int) -> dict[str, Any]:
    lambdas = parse_floats(args.lambdas)
    seeds = parse_ints(args.seeds)
    ks = parse_ints(args.k_values)
    label_null_trials = int(args.label_null_trials)
    position_offsets = parse_ints(args.position_offsets)
    row_hits = empty_hits(lambdas)
    observed_total = len(seeds) * len(ks)
    label_null_total = observed_total * label_null_trials
    position_null_total = observed_total * len(position_offsets)
    reader_runs = []

    row_args = SimpleNamespace(
        n=n,
        reps=args.reps,
        central_fraction=args.central_fraction,
        grid_size=args.grid_size,
        poisson_pole_max=args.poisson_pole_max,
        gue_pole_min=args.gue_pole_min,
    )

    for seed in seeds:
        rows = [compute_row(lam, row_args, seed + (n * 10000) + int(round(lam * 1000))) for lam in lambdas]
        labels = [row["source_domain_type"] for row in rows]
        rng = np.random.default_rng(seed + n)
        for k in ks:
            observed = classify_with_labels(rows, k, labels)
            observed_by_name = {row["domain_window"]: row for row in observed}
            observed_candidates = [
                row["domain_window"] for row in observed if row["boundary_state"] == "third_included_candidate"
            ]
            reader_runs.append({"n": n, "seed": seed, "k": k, "observed_candidates": observed_candidates})
            for row in rows:
                name = row["domain_window"]
                graph_row = observed_by_name[name]
                item = row_hits[name]
                if graph_row["boundary_state"] == "third_included_candidate":
                    item["observed_hits"] += 1
                item["margins"].append(float(graph_row["centroid_margin"]))
                item["cross_fractions"].append(float(graph_row["cross_neighbor_fraction"]))
                item["brody_q"].append(float(row["brody_q"]))
                item["mixture_w"].append(float(row["berry_robnick_like_gue_weight"]))
                item["mean_ipr"].append(float(row["mean_ipr"]))
                item["sr"].append(float(row["observables"]["SR"]))

            for _ in range(label_null_trials):
                null_rows = classify_with_labels(rows, k, shuffled_labels(labels, rng))
                for null_row in null_rows:
                    if null_row["boundary_state"] == "third_included_candidate":
                        row_hits[null_row["domain_window"]]["label_shuffle_hits"] += 1

            for offset in position_offsets:
                null_rows = classify_with_labels(rows, k, rotate_labels(labels, offset))
                for null_row in null_rows:
                    if null_row["boundary_state"] == "third_included_candidate":
                        row_hits[null_row["domain_window"]]["position_shift_hits"] += 1

    rows_out = []
    two_reader_rows = []
    graph_only_rows = []
    for name in sorted(row_hits, key=lambda key: row_hits[key]["lambda"]):
        item = row_hits[name]
        class_row = {
            "brody_q": median(item["brody_q"]),
            "berry_robnick_like_gue_weight": median(item["mixture_w"]),
        }
        c_state = classical_state(class_row)
        observed_rate = item["observed_hits"] / observed_total
        label_rate = item["label_shuffle_hits"] / label_null_total
        position_rate = item["position_shift_hits"] / position_null_total
        min_lift = min(observed_rate - label_rate, observed_rate - position_rate)
        label_p = binomial_tail_at_least(item["observed_hits"], observed_total, label_rate)
        position_p = binomial_tail_at_least(item["observed_hits"], observed_total, position_rate)
        threshold_pass = (
            c_state == "classical_intermediate"
            and observed_rate >= args.min_observed_rate
            and min_lift >= args.min_lift
            and label_p <= args.alpha
            and position_p <= args.alpha
        )
        graph_stability = stability_state(observed_rate)
        if threshold_pass:
            two_reader_rows.append(name)
        if graph_stability == "stable_graph_bridge" and c_state != "classical_intermediate":
            graph_only_rows.append(name)
        rows_out.append(
            {
                "domain_window": name,
                "lambda": item["lambda"],
                "classical_audit_state": c_state,
                "graph_stability_state": graph_stability,
                "observed_successes": item["observed_hits"],
                "observed_total": observed_total,
                "observed_rate": round(observed_rate, 6),
                "observed_wilson_95": wilson_interval(item["observed_hits"], observed_total),
                "label_shuffle_successes": item["label_shuffle_hits"],
                "label_shuffle_total": label_null_total,
                "label_shuffle_rate": round(label_rate, 6),
                "label_shuffle_wilson_95": wilson_interval(item["label_shuffle_hits"], label_null_total),
                "label_shuffle_lift": round(observed_rate - label_rate, 6),
                "label_shuffle_binomial_tail_p": round(label_p, 6),
                "position_shift_successes": item["position_shift_hits"],
                "position_shift_total": position_null_total,
                "position_shift_rate": round(position_rate, 6),
                "position_shift_wilson_95": wilson_interval(item["position_shift_hits"], position_null_total),
                "position_shift_lift": round(observed_rate - position_rate, 6),
                "position_shift_binomial_tail_p": round(position_p, 6),
                "min_lift_against_nulls": round(min_lift, 6),
                "threshold_pass": threshold_pass,
                "median_brody_q": round(class_row["brody_q"], 6),
                "median_berry_robnick_like_gue_weight": round(class_row["berry_robnick_like_gue_weight"], 6),
                "median_SR": round(median(item["sr"]), 6),
                "median_mean_ipr": round(median(item["mean_ipr"]), 9),
                "mean_centroid_margin": round(float(np.mean(item["margins"])), 6),
                "mean_cross_neighbor_fraction": round(float(np.mean(item["cross_fractions"])), 6),
            }
        )

    return {
        "n": n,
        "observed_total": observed_total,
        "label_shuffle_total": label_null_total,
        "position_shift_total": position_null_total,
        "summary": {
            "thresholded_two_reader_rows": two_reader_rows,
            "thresholded_two_reader_count": len(two_reader_rows),
            "graph_only_stable_rows": graph_only_rows,
            "graph_only_stable_count": len(graph_only_rows),
        },
        "rows": rows_out,
        "reader_runs": reader_runs,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    sizes = parse_ints(args.sizes)
    by_size = [audit_size(args, n) for n in sizes]
    size_sets = {entry["n"]: set(entry["summary"]["thresholded_two_reader_rows"]) for entry in by_size}
    all_size_rows = sorted(set.intersection(*size_sets.values())) if size_sets else []
    any_size_rows = sorted(set.union(*size_sets.values())) if size_sets else []

    cross_rows = []
    lambdas = parse_floats(args.lambdas)
    for lam in lambdas:
        name = f"RP_lambda_{lam:.3f}"
        rows_for_lambda = []
        for entry in by_size:
            row = next(row for row in entry["rows"] if row["domain_window"] == name)
            rows_for_lambda.append(row)
        cross_rows.append(
            {
                "domain_window": name,
                "lambda": round(float(lam), 6),
                "threshold_pass_sizes": [
                    entry["n"]
                    for entry in by_size
                    if next(row for row in entry["rows"] if row["domain_window"] == name)["threshold_pass"]
                ],
                "all_size_threshold_pass": name in all_size_rows,
                "min_observed_rate": round(float(min(row["observed_rate"] for row in rows_for_lambda)), 6),
                "max_observed_rate": round(float(max(row["observed_rate"] for row in rows_for_lambda)), 6),
                "min_lift_against_nulls": round(float(min(row["min_lift_against_nulls"] for row in rows_for_lambda)), 6),
                "max_null_p": round(
                    float(
                        max(
                            max(row["label_shuffle_binomial_tail_p"], row["position_shift_binomial_tail_p"])
                            for row in rows_for_lambda
                        )
                    ),
                    6,
                ),
                "classical_states_seen": sorted(set(row["classical_audit_state"] for row in rows_for_lambda)),
                "graph_stability_seen": sorted(set(row["graph_stability_state"] for row in rows_for_lambda)),
            }
        )

    output = {
        "experiment": "rp_boundary_raw_count_null_audit",
        "question": "Does the Rosenzweig-Porter boundary row beat row-aligned graph nulls with raw counts across sizes?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "observed_successes",
            "label_shuffle_successes",
            "position_shift_successes",
            "observed_wilson_95",
            "label_shuffle_wilson_95",
            "position_shift_wilson_95",
            "label_shuffle_binomial_tail_p",
            "position_shift_binomial_tail_p",
            "min_lift_against_nulls",
            "threshold_pass",
        ],
        "parameters": {
            "sizes": sizes,
            "reps": args.reps,
            "lambdas": lambdas,
            "seeds": parse_ints(args.seeds),
            "k_values": parse_ints(args.k_values),
            "label_null_trials": args.label_null_trials,
            "position_offsets": parse_ints(args.position_offsets),
            "central_fraction": args.central_fraction,
            "grid_size": args.grid_size,
            "poisson_pole_max": args.poisson_pole_max,
            "gue_pole_min": args.gue_pole_min,
        },
        "threshold_preregistered": {
            "min_observed_rate": args.min_observed_rate,
            "min_lift_against_each_null": args.min_lift,
            "alpha_each_null": args.alpha,
            "classical_clause": "classical_intermediate required for two-reader threshold pass",
            "decision": "thresholded_two_reader_boundary only if all clauses pass; otherwise graph bridge remains positive_lift_unthresholded or classic-only",
        },
        "observable_contract": {
            "claim": "the RP boundary row is a controlled physical third-included only if raw graph hits beat label-shuffle and position-shift nulls at the same lambda row",
            "observable": "observed/null third-included graph successes, Wilson intervals, binomial-tail p-values, joined with Brody q and mixture weight",
            "operator": "finite-size RP diagonal-plus-GUE flow with kNN graph perturbations and two row-aligned nulls",
            "generator": "H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE across sizes, seeds and k values",
            "denominator": "same lambda grid per size; observed denominator seeds*k, null denominators observed*null_trials",
            "non_possible": "thresholded boundary if no lambda beats both nulls or if the pass is not size-stable",
            "not_tested": "N to infinity, experimental spectra, unfolding alternatives, Anderson 3D, many-body RP",
        },
        "summary": {
            "sizes_analyzed": len(sizes),
            "lambda_rows": len(lambdas),
            "thresholded_two_reader_any_size": len(any_size_rows),
            "thresholded_two_reader_any_size_rows": any_size_rows,
            "thresholded_two_reader_all_sizes": len(all_size_rows),
            "thresholded_two_reader_all_size_rows": all_size_rows,
        },
        "cross_size_rows": cross_rows,
        "by_size": by_size,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/rp_boundary_raw_count_null_audit_20260516_0820.json")
    parser.add_argument("--sizes", default="64,96,128")
    parser.add_argument("--reps", type=int, default=10)
    parser.add_argument("--lambdas", default="0,0.03,0.045,0.06,0.075,0.10,0.18,0.32,0.68,0.82,1.0")
    parser.add_argument("--seeds", default="202605160820,202605160821,202605160822,202605160823")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--label-null-trials", type=int, default=64)
    parser.add_argument("--position-offsets", default="1,2,3,4,5,6,7,8,9,10")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--poisson-pole-max", type=float, default=0.03)
    parser.add_argument("--gue-pole-min", type=float, default=0.82)
    parser.add_argument("--min-observed-rate", type=float, default=0.75)
    parser.add_argument("--min-lift", type=float, default=0.10)
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
