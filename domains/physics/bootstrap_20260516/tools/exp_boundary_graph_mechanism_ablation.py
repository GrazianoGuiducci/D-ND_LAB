#!/usr/bin/env python3
"""
Mechanism ablation for graph-only BOUNDARY residues.

The experiment keeps the same 13-row 8 GUE / 5 Poisson perimeter and the same
27 graph-reader settings used by the 11:40/12:06 audits. It separates the graph
reader into:

- centroid gate;
- kNN cross-label gate;
- degree-preserving topology;
- row-local feature vectors.

Rows are not promoted here. The script identifies which reader component can
reconstruct or destroy the graph-only 27/27 residues.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_graph_curvature_gate import (
    OBS_NAMES,
    build_knn_edges,
    classify_geometry,
    standardized_matrix,
)
from exp_boundary_graph_null_audit import (
    bridge_flags,
    centroid_margins,
    degree_preserving_rewire,
    incident_cross_fractions,
    parse_ints,
)
from exp_boundary_residue_label_count_null_audit import (
    DEFAULT_TARGETS,
    load_reader_runs,
    parse_targets,
    relabel_rows,
)


FEATURE_GROUPS = {
    "canonical": OBS_NAMES,
    "sr_local": ["SR_local_rigidity"],
    "shuffle_z": [f"z_{name}" for name in OBS_NAMES],
}


def feature_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    matrix = []
    for row in rows:
        obs = row["observables"]
        z = row["shuffle_z"]
        matrix.append([obs[name] for name in OBS_NAMES] + [obs["SR_local_rigidity"]] + [z[name] for name in OBS_NAMES])
    return np.asarray(matrix, dtype=float)


def standardize_raw(x: np.ndarray) -> np.ndarray:
    center = np.mean(x, axis=0)
    scale = np.std(x, axis=0, ddof=1)
    scale[scale <= 1e-15] = 1.0
    return (x - center) / scale


def group_columns(group: str) -> list[int]:
    if group == "canonical":
        return list(range(len(OBS_NAMES)))
    if group == "sr_local":
        return [len(OBS_NAMES)]
    if group == "shuffle_z":
        start = len(OBS_NAMES) + 1
        return list(range(start, start + len(OBS_NAMES)))
    raise ValueError(f"unknown group: {group}")


def labels_for(rows: list[dict[str, Any]]) -> list[str]:
    return [row["source_domain_type"] for row in rows]


def names_for(rows: list[dict[str, Any]]) -> list[str]:
    return [row["domain_window"] for row in rows]


def deterministic_states(rows: list[dict[str, Any]], k: int) -> dict[str, set[str]]:
    x = standardized_matrix(rows)
    labels = labels_for(rows)
    names = names_for(rows)
    edges = build_knn_edges(x, k)
    margins = centroid_margins(x, labels)
    cross = incident_cross_fractions(len(rows), edges, labels)
    full = set(classify_geometry(rows, x, k)["third_included_candidates"])
    centroid_only = {names[i] for i, margin in enumerate(margins) if margin < 0.25}
    knn_only = {names[i] for i, value in enumerate(cross) if value > 0.0}
    return {
        "full": full,
        "centroid_only_no_knn": centroid_only,
        "knn_only_no_centroid": knn_only,
    }


def zero_group_rows(rows: list[dict[str, Any]], group: str) -> list[dict[str, Any]]:
    cols = set(group_columns(group))
    matrix = feature_matrix(rows)
    matrix[:, list(cols)] = np.mean(matrix[:, list(cols)], axis=0)
    names = names_for(rows)
    labels = labels_for(rows)
    out = []
    for i, row in enumerate(rows):
        item = dict(row)
        obs = dict(row["observables"])
        z = dict(row["shuffle_z"])
        values = matrix[i]
        for idx, name in enumerate(OBS_NAMES):
            obs[name] = float(values[idx])
        obs["SR_local_rigidity"] = float(values[len(OBS_NAMES)])
        for offset, name in enumerate(OBS_NAMES):
            z[name] = float(values[len(OBS_NAMES) + 1 + offset])
        item["observables"] = obs
        item["shuffle_z"] = z
        item["domain_window"] = names[i]
        item["source_domain_type"] = labels[i]
        out.append(item)
    return out


def shuffled_feature_x(rows: list[dict[str, Any]], rng: np.random.Generator) -> np.ndarray:
    x = feature_matrix(rows).copy()
    for col in range(x.shape[1]):
        x[:, col] = rng.permutation(x[:, col])
    return standardize_raw(x)


def count_hits(reader_runs: list[dict[str, Any]], names: list[str], mode: str) -> dict[str, int]:
    counts = {name: 0 for name in names}
    for run in reader_runs:
        states = deterministic_states(run["rows"], run["k"])
        for name in states[mode]:
            counts[name] += 1
    return counts


def count_group_ablation(reader_runs: list[dict[str, Any]], names: list[str], group: str) -> dict[str, int]:
    counts = {name: 0 for name in names}
    for run in reader_runs:
        rows = zero_group_rows(run["rows"], group)
        hits = set(classify_geometry(rows, standardized_matrix(rows), run["k"])["third_included_candidates"])
        for name in hits:
            counts[name] += 1
    return counts


def null_trial_counts(
    reader_runs: list[dict[str, Any]],
    names: list[str],
    base_labels: dict[str, str],
    rng: np.random.Generator,
    trials: int,
    null_kind: str,
    rewire_swap_multiplier: int,
) -> dict[str, Any]:
    distributions = {name: {} for name in names}
    ge_full = {name: 0 for name in names}
    full_counts = count_hits(reader_runs, names, "full")
    label_values = [base_labels[name] for name in names]

    for _ in range(trials):
        trial_counts = {name: 0 for name in names}
        if null_kind == "label_permutation":
            permuted = list(rng.permutation(label_values))
            labels_by_name = dict(zip(names, permuted, strict=True))
        else:
            labels_by_name = None

        for run in reader_runs:
            rows = run["rows"]
            if null_kind == "label_permutation":
                rows = relabel_rows(rows, labels_by_name or {})
                hits = set(classify_geometry(rows, standardized_matrix(rows), run["k"])["third_included_candidates"])
            else:
                labels = labels_for(rows)
                x = standardized_matrix(rows)
                if null_kind == "degree_rewire":
                    edges = build_knn_edges(x, run["k"])
                    rewired = degree_preserving_rewire(
                        edges,
                        len(names),
                        rng,
                        max(len(edges) * rewire_swap_multiplier, 1),
                    )
                    margins = centroid_margins(x, labels)
                    flags = bridge_flags(rewired, labels, margins, 0.25)
                elif null_kind == "feature_column_shuffle":
                    x = shuffled_feature_x(rows, rng)
                    edges = build_knn_edges(x, run["k"])
                    margins = centroid_margins(x, labels)
                    flags = bridge_flags(edges, labels, margins, 0.25)
                else:
                    raise ValueError(f"unknown null kind: {null_kind}")
                hits = {names[i] for i, flag in enumerate(flags) if flag}
            for name in hits:
                trial_counts[name] += 1

        for name, hits in trial_counts.items():
            distributions[name][str(hits)] = distributions[name].get(str(hits), 0) + 1
            if hits >= full_counts[name]:
                ge_full[name] += 1

    return {
        "trials": trials,
        "ge_full": ge_full,
        "hit_distributions": {
            name: dict(sorted(dist.items(), key=lambda item: int(item[0])))
            for name, dist in distributions.items()
        },
    }


def row_state(name: str, counts: dict[str, dict[str, int]], nulls: dict[str, Any], run_count: int) -> dict[str, Any]:
    full = counts["full"][name]
    row = {
        "domain_window": name,
        "full_hits": full,
        "full_frequency": round(full / run_count, 9),
        "centroid_only_no_knn_hits": counts["centroid_only_no_knn"][name],
        "knn_only_no_centroid_hits": counts["knn_only_no_centroid"][name],
        "drop_without_knn": full - counts["centroid_only_no_knn"][name],
        "drop_without_centroid": full - counts["knn_only_no_centroid"][name],
        "drop_without_canonical": full - counts["without_canonical"][name],
        "drop_without_sr_local": full - counts["without_sr_local"][name],
        "drop_without_shuffle_z": full - counts["without_shuffle_z"][name],
    }
    for key, value in nulls.items():
        trials = value["trials"]
        k = value["ge_full"][name]
        row[f"{key}_ge_full"] = k
        row[f"{key}_raw_p"] = round(k / trials, 9)
        row[f"{key}_hit_distribution"] = value["hit_distributions"][name]
    drops = []
    for component, field in [
        ("knn_cross_gate", "drop_without_knn"),
        ("centroid_gate", "drop_without_centroid"),
        ("canonical_features", "drop_without_canonical"),
        ("sr_local_feature", "drop_without_sr_local"),
        ("shuffle_z_features", "drop_without_shuffle_z"),
    ]:
        if row[field] > 0:
            drops.append(component)
    row["components_that_drop_full_residue"] = drops
    row["mechanism_state"] = "component_specific" if drops else "reader_reconstructable"
    return row


def run(args: argparse.Namespace) -> dict[str, Any]:
    targets = parse_targets(args.targets)
    selected, reader_runs = load_reader_runs(args)
    names = [row["domain_window"] for row in selected]
    for target in targets:
        if target not in names:
            raise ValueError(f"target not in 13-row scope: {target}")
    base_labels = {row["domain_window"]: row["source_domain_type"] for row in selected}
    run_count = len(reader_runs)

    counts = {
        "full": count_hits(reader_runs, names, "full"),
        "centroid_only_no_knn": count_hits(reader_runs, names, "centroid_only_no_knn"),
        "knn_only_no_centroid": count_hits(reader_runs, names, "knn_only_no_centroid"),
        "without_canonical": count_group_ablation(reader_runs, names, "canonical"),
        "without_sr_local": count_group_ablation(reader_runs, names, "sr_local"),
        "without_shuffle_z": count_group_ablation(reader_runs, names, "shuffle_z"),
    }

    rng = np.random.default_rng(args.null_seed)
    nulls = {
        key: null_trial_counts(
            reader_runs,
            names,
            base_labels,
            rng,
            args.null_trials,
            key,
            args.rewire_swap_multiplier,
        )
        for key in ["label_permutation", "degree_rewire", "feature_column_shuffle"]
    }

    rows = [row_state(name, counts, nulls, run_count) for name in names]
    target_rows = [row for row in rows if row["domain_window"] in targets]
    graph_only_full = [
        row["domain_window"]
        for row in rows
        if row["full_hits"] == run_count and row["domain_window"] in targets
    ]

    output = {
        "experiment": "boundary_graph_mechanism_ablation",
        "question": "Which graph-reader component reconstructs graph-only residues in the fixed 8 GUE / 5 Poisson perimeter?",
        "observables_registry": "1.0.0-2026-05-06 via boundary_graph_curvature_gate",
        "observables_used": [
            "full_graph_bridge_hits",
            "centroid_only_no_knn_hits",
            "knn_only_no_centroid_hits",
            "feature_group_ablation_hits",
            "label_permutation_ge_full",
            "degree_rewire_ge_full",
            "feature_column_shuffle_ge_full",
        ],
        "params": {
            "scope": args.scope,
            "targets": targets,
            "k_values": parse_ints(args.k_values),
            "n_gaps_values": parse_ints(args.n_gaps_values),
            "seeds": parse_ints(args.seeds),
            "n_shuffle": args.n_shuffle,
            "null_trials": args.null_trials,
            "null_seed": args.null_seed,
            "reader_runs": run_count,
            "rewire_swap_multiplier": args.rewire_swap_multiplier,
        },
        "observable_contract": {
            "claim": "a graph-only residue is mechanism-specific only if it falls under a named reader ablation and is not reconstructed by comparable label/degree/feature nulls",
            "observable": "target bridge hit count across 27 fixed graph-reader runs under deterministic ablations and N-matched nulls",
            "operator": "split the original bridge predicate into centroid, kNN cross-label, degree-preserving topology, and row-local feature-vector components",
            "generator": "13 row-aligned BOUNDARY denominator; feature vectors from boundary_graph_curvature_gate",
            "denominator": f"13 rows, {run_count} graph-reader reads, {args.null_trials} null trials per stochastic ablation",
            "p_value_definition": "right-tail raw_p=k/N, k = null trials with target hits >= full observed hits",
            "non_possible": "promoting a graph-only residue if no specific component drops it or if N-matched nulls reconstruct the full hit count frequently",
            "not_tested": "new physical dynamics, new domains, asymptotic scaling, two-reader promotion",
        },
        "summary": {
            "rows_analyzed": len(rows),
            "reader_runs": run_count,
            "target_full_27_rows": graph_only_full,
            "target_component_specific": [
                row["domain_window"] for row in target_rows if row["mechanism_state"] == "component_specific"
            ],
            "target_reader_reconstructable": [
                row["domain_window"] for row in target_rows if row["mechanism_state"] == "reader_reconstructable"
            ],
            "nulls_comparable": f"N={args.null_trials} for label_permutation, degree_rewire, feature_column_shuffle",
        },
        "target_rows": target_rows,
        "rows": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    for row in target_rows:
        print(json.dumps(row, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--n-gaps-values", default="512,1024,2048")
    parser.add_argument("--seeds", default="20260515,20260516,20260517")
    parser.add_argument("--n-shuffle", type=int, default=32)
    parser.add_argument("--min-gaps", type=int, default=64)
    parser.add_argument("--null-trials", type=int, default=128)
    parser.add_argument("--null-seed", type=int, default=20260516)
    parser.add_argument("--rewire-swap-multiplier", type=int, default=8)
    parser.add_argument("--out", default="tools/data/boundary_graph_mechanism_ablation_20260516_1230.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
