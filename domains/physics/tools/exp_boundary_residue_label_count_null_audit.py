#!/usr/bin/env python3
"""
Label-count-preserving null audit for BOUNDARY graph-only residues.

The script reuses the 13-row 8 GUE / 5 Poisson reader grid and asks whether
named graph-only residues remain 27/27 bridge rows when only source labels are
permuted with the 8/5 count preserved. It does not promote graph-only rows to a
two-reader boundary; it measures their null cost inside the graph reader.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_bridge_stability_audit import classical_map, parse_ints
from exp_boundary_graph_curvature_gate import (
    classify_geometry,
    compute_observables,
    load_scope,
    row_spacings,
    shuffle_z,
    standardized_matrix,
)


DEFAULT_TARGETS = "logistica_biforcazione_var_3.5699:cycle_13,percolation:cycle_9"


def parse_targets(raw: str) -> list[str]:
    targets = [part.strip() for part in raw.split(",") if part.strip()]
    if not targets:
        raise ValueError("empty target list")
    return targets


def load_reader_runs(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ks = parse_ints(args.k_values)
    n_gaps_values = parse_ints(args.n_gaps_values)
    seeds = parse_ints(args.seeds)
    source_rows = load_scope(Path(args.scope))
    selected = [row for row in source_rows if row.get("source_domain_type") in {"GUE", "Poisson"}]
    selected = sorted(selected, key=lambda row: int(row["cycle"]))
    gap_cache = {row["domain_window"]: row_spacings(row["domain"]) for row in selected}

    reader_runs = []
    for k in ks:
        for n_gaps in n_gaps_values:
            for seed in seeds:
                rng = np.random.default_rng(seed)
                rows = []
                for source in selected:
                    gaps = gap_cache[source["domain_window"]]
                    if len(gaps) < args.min_gaps:
                        continue
                    gaps = gaps[:n_gaps] if len(gaps) > n_gaps else gaps
                    obs = compute_observables(gaps)
                    z = shuffle_z(gaps, obs, args.n_shuffle, rng)
                    rows.append(
                        {
                            "domain_window": source["domain_window"],
                            "domain": source["domain"],
                            "cycle": source["cycle"],
                            "source_domain_type": source["source_domain_type"],
                            "n_gaps": int(len(gaps)),
                            "observables": {key: round(value, 9) for key, value in obs.items()},
                            "shuffle_z": {key: round(value, 6) for key, value in z.items()},
                        }
                    )
                reader_runs.append({"k": k, "n_gaps": n_gaps, "seed": seed, "rows": rows})
    return selected, reader_runs


def relabel_rows(rows: list[dict[str, Any]], labels_by_name: dict[str, str]) -> list[dict[str, Any]]:
    relabeled = []
    for row in rows:
        item = dict(row)
        item["source_domain_type"] = labels_by_name[row["domain_window"]]
        relabeled.append(item)
    return relabeled


def geometry_hits(rows: list[dict[str, Any]], k: int) -> set[str]:
    geometry = classify_geometry(rows, standardized_matrix(rows), k)
    return set(geometry["third_included_candidates"])


def summarize_hits(
    reader_runs: list[dict[str, Any]],
    names: list[str],
    labels_by_name: dict[str, str] | None = None,
) -> dict[str, Any]:
    hit_counts = {name: 0 for name in names}
    stable_rows_by_run = []
    for run in reader_runs:
        rows = run["rows"] if labels_by_name is None else relabel_rows(run["rows"], labels_by_name)
        hits = geometry_hits(rows, run["k"])
        for name in hits:
            hit_counts[name] += 1
        stable_rows_by_run.append(
            {
                "k": run["k"],
                "n_gaps": run["n_gaps"],
                "seed": run["seed"],
                "third_included_candidates": sorted(hits),
            }
        )
    stable_27_rows = sorted(name for name, count in hit_counts.items() if count == len(reader_runs))
    return {
        "hit_counts": hit_counts,
        "stable_27_rows": stable_27_rows,
        "per_run": stable_rows_by_run,
    }


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return [round(max(0.0, center - margin), 9), round(min(1.0, center + margin), 9)]


def audit_state(row: dict[str, Any]) -> Any:
    return row.get("audit_state", row.get("classical_audit_state"))


def run(args: argparse.Namespace) -> dict[str, Any]:
    targets = parse_targets(args.targets)
    selected, reader_runs = load_reader_runs(args)
    names = [row["domain_window"] for row in selected]
    original_labels = {row["domain_window"]: row["source_domain_type"] for row in selected}
    label_values = [original_labels[name] for name in names]
    classical = classical_map(Path(args.classical_audit))
    observed_summary = summarize_hits(reader_runs, names)

    for target in targets:
        if target not in names:
            raise ValueError(f"target not in 13-row scope: {target}")

    rng = np.random.default_rng(args.null_seed)
    target_stats: dict[str, dict[str, Any]] = {
        target: {
            "null_ge_observed": 0,
            "null_eq_27": 0,
            "null_eq_27_with_original_label": 0,
            "null_eq_27_with_swapped_label": 0,
            "null_label_distribution": {"GUE": 0, "Poisson": 0},
            "null_hit_distribution": {},
        }
        for target in targets
    }
    any_graph_only_eq_27 = 0
    null_examples = []

    graph_only_names = [
        name
        for name in names
        if audit_state(classical.get(name, {})) == "graph_only_bridge"
    ]

    for trial in range(args.null_trials):
        permuted = list(rng.permutation(label_values))
        labels_by_name = dict(zip(names, permuted, strict=True))
        summary = summarize_hits(reader_runs, names, labels_by_name)
        stable_27 = set(summary["stable_27_rows"])
        if any(name in stable_27 for name in graph_only_names):
            any_graph_only_eq_27 += 1

        example_targets = []
        for target in targets:
            observed_hits = observed_summary["hit_counts"][target]
            hits = summary["hit_counts"][target]
            stats = target_stats[target]
            stats["null_hit_distribution"][str(hits)] = stats["null_hit_distribution"].get(str(hits), 0) + 1
            assigned_label = labels_by_name[target]
            stats["null_label_distribution"][assigned_label] += 1
            if hits >= observed_hits:
                stats["null_ge_observed"] += 1
            if hits == len(reader_runs):
                stats["null_eq_27"] += 1
                if assigned_label == original_labels[target]:
                    stats["null_eq_27_with_original_label"] += 1
                else:
                    stats["null_eq_27_with_swapped_label"] += 1
                example_targets.append(target)
        if len(null_examples) < args.example_count and example_targets:
            null_examples.append(
                {
                    "trial": trial,
                    "stable_target_rows": sorted(example_targets),
                    "stable_graph_only_rows": sorted(name for name in graph_only_names if name in stable_27),
                    "target_labels": {target: labels_by_name[target] for target in targets},
                }
            )

    target_rows = []
    for target in targets:
        stats = target_stats[target]
        observed_hits = observed_summary["hit_counts"][target]
        null_ge = stats["null_ge_observed"]
        null_eq = stats["null_eq_27"]
        target_rows.append(
            {
                "target": target,
                "source_label": original_labels[target],
                "classical_audit": classical.get(target, {}),
                "observed_hits": observed_hits,
                "observed_frequency": round(observed_hits / len(reader_runs), 9),
                "null_ge_observed": null_ge,
                "null_eq_27": null_eq,
                "raw_p": round(null_ge / args.null_trials, 9),
                "add_one_p": round((null_ge + 1) / (args.null_trials + 1), 9),
                "wilson_95": wilson_interval(null_ge, args.null_trials),
                "null_eq_27_with_original_label": stats["null_eq_27_with_original_label"],
                "null_eq_27_with_swapped_label": stats["null_eq_27_with_swapped_label"],
                "null_label_distribution": stats["null_label_distribution"],
                "null_hit_distribution": dict(
                    sorted(stats["null_hit_distribution"].items(), key=lambda item: int(item[0]))
                ),
                "label_survival_state": (
                    "does_not_survive_label_null"
                    if stats["null_eq_27_with_swapped_label"] > 0
                    else "not_reconstructed_when_label_swapped"
                ),
            }
        )

    output = {
        "experiment": "boundary_residue_label_count_null_audit",
        "question": "Do graph-only residues survive a label-count-preserving null on the same 13-row BOUNDARY reader?",
        "observables_registry": "1.0.0-2026-05-06 via boundary_graph_curvature_gate",
        "observables_used": [
            "target_graph_bridge_hits",
            "target_graph_bridge_frequency",
            "label_count_preserving_null_hits",
            "source_label_survival_state",
            "any_graph_only_stable_under_null",
            "classical_audit_state",
        ],
        "params": {
            "scope": args.scope,
            "classical_audit": args.classical_audit,
            "targets": targets,
            "k_values": parse_ints(args.k_values),
            "n_gaps_values": parse_ints(args.n_gaps_values),
            "seeds": parse_ints(args.seeds),
            "n_shuffle": args.n_shuffle,
            "min_gaps": args.min_gaps,
            "null_trials": args.null_trials,
            "null_seed": args.null_seed,
        },
        "observable_contract": {
            "claim": "graph-only residues carry source-label cost only if their 27/27 graph-reader status is rare under 8/5 label-count-preserving permutations and does not persist under swapped labels",
            "observable": "target row bridge hit count across the same 27 graph-reader perturbations",
            "operator": "label-count-preserving permutation null over the 13 row-aligned BOUNDARY labels",
            "generator": "fixed row-local feature vectors from boundary_graph_curvature_gate; only source_domain_type changes under null",
            "denominator": f"13 rows, 27 graph-reader reads, {args.null_trials} null label permutations",
            "p_value_definition": "right-tail raw_p=k/N and add_one_p=(k+1)/(N+1), k = null trials with target_hits >= observed target_hits",
            "non_possible": "calling graph-only rows Lab-specific residues if 27/27 is reconstructed frequently or under swapped source label",
            "not_tested": "new graph construction, physical source dynamics, asymptotic scaling, two-reader promotion",
        },
        "observed": {
            "stable_27_rows": observed_summary["stable_27_rows"],
            "target_rows": [
                {
                    "target": target,
                    "source_label": original_labels[target],
                    "classical_audit_state": audit_state(classical.get(target, {})),
                    "observed_hits": observed_summary["hit_counts"][target],
                    "observed_frequency": round(observed_summary["hit_counts"][target] / len(reader_runs), 9),
                }
                for target in targets
            ],
        },
        "null": {
            "any_graph_only_eq_27": any_graph_only_eq_27,
            "any_graph_only_eq_27_frequency": round(any_graph_only_eq_27 / args.null_trials, 9),
            "target_rows": target_rows,
            "examples": null_examples,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"observed": output["observed"], "null": output["null"]}, indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--classical-audit", default="tools/data/boundary_bridge_stability_audit_20260516_1140.json")
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--n-gaps-values", default="512,1024,2048")
    parser.add_argument("--seeds", default="20260515,20260516,20260517")
    parser.add_argument("--n-shuffle", type=int, default=32)
    parser.add_argument("--min-gaps", type=int, default=64)
    parser.add_argument("--null-trials", type=int, default=512)
    parser.add_argument("--null-seed", type=int, default=20260516)
    parser.add_argument("--example-count", type=int, default=8)
    parser.add_argument("--out", default="tools/data/boundary_residue_label_count_null_audit_20260516_1206.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
