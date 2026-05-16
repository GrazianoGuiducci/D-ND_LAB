#!/usr/bin/env python3
"""
Graph-null audit for the BOUNDARY composite gate.

This script keeps the 13 row-aligned 8 GUE / 5 Poisson denominator and asks
whether the stable graph-only bridge residue from the two-reader audit survives
against graph-native nulls:

- label shuffle on the same feature embedding;
- degree-preserving rewiring of the kNN graph with labels fixed.

The goal is not to add a third reader. It audits the graph reader itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_graph_curvature_gate import (
    build_knn_edges,
    compute_observables,
    load_scope,
    row_spacings,
    shuffle_z,
    standardized_matrix,
)


def parse_ints(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("empty integer list")
    return values


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def centroid_margins(x: np.ndarray, labels: list[str]) -> list[float]:
    gue_idx = [i for i, label in enumerate(labels) if label == "GUE"]
    poi_idx = [i for i, label in enumerate(labels) if label == "Poisson"]
    c_gue = np.mean(x[gue_idx], axis=0)
    c_poi = np.mean(x[poi_idx], axis=0)
    margins = []
    for i in range(len(labels)):
        d_gue = float(np.linalg.norm(x[i] - c_gue))
        d_poi = float(np.linalg.norm(x[i] - c_poi))
        denom = d_gue + d_poi
        margins.append(float(abs(d_gue - d_poi) / denom) if denom > 1e-15 else 0.0)
    return margins


def incident_cross_fractions(
    n_rows: int,
    edges: list[tuple[int, int, float]],
    labels: list[str],
) -> list[float]:
    incident = [0 for _ in range(n_rows)]
    cross = [0 for _ in range(n_rows)]
    for i, j, _ in edges:
        incident[i] += 1
        incident[j] += 1
        if labels[i] != labels[j]:
            cross[i] += 1
            cross[j] += 1
    return [float(cross[i] / incident[i]) if incident[i] else 0.0 for i in range(n_rows)]


def bridge_flags(
    edges: list[tuple[int, int, float]],
    labels: list[str],
    margins: list[float],
    margin_threshold: float,
) -> list[bool]:
    cross_fractions = incident_cross_fractions(len(labels), edges, labels)
    return [cross_fractions[i] > 0.0 and margins[i] < margin_threshold for i in range(len(labels))]


def edge_key(edge: tuple[int, int, float]) -> tuple[int, int]:
    i, j, _ = edge
    return (min(i, j), max(i, j))


def degree_preserving_rewire(
    edges: list[tuple[int, int, float]],
    n_rows: int,
    rng: np.random.Generator,
    swaps: int,
) -> list[tuple[int, int, float]]:
    current = {edge_key(edge) for edge in edges}
    if len(current) < 2:
        return [(i, j, 1.0) for i, j in sorted(current)]

    edge_list = list(current)
    attempts = max(swaps * 20, 100)
    accepted = 0
    for _ in range(attempts):
        if accepted >= swaps:
            break
        a_idx, b_idx = rng.choice(len(edge_list), size=2, replace=False)
        a, b = edge_list[a_idx]
        c, d = edge_list[b_idx]
        if len({a, b, c, d}) < 4:
            continue
        if rng.random() < 0.5:
            e1 = tuple(sorted((a, d)))
            e2 = tuple(sorted((c, b)))
        else:
            e1 = tuple(sorted((a, c)))
            e2 = tuple(sorted((b, d)))
        if e1[0] == e1[1] or e2[0] == e2[1] or e1 == e2:
            continue
        if e1 in current or e2 in current:
            continue
        old1 = edge_list[a_idx]
        old2 = edge_list[b_idx]
        current.remove(old1)
        current.remove(old2)
        current.add(e1)
        current.add(e2)
        edge_list[a_idx] = e1
        edge_list[b_idx] = e2
        accepted += 1
    return [(i, j, 1.0) for i, j in sorted(current)]


def classical_state_by_row(path: Path) -> dict[str, str]:
    data = load_json(path)
    rows = data.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("stability audit has no rows")
    return {row["domain_window"]: row.get("classical_audit_state", "") for row in rows}


def run(args: argparse.Namespace) -> dict[str, Any]:
    ks = parse_ints(args.k_values)
    n_gaps_values = parse_ints(args.n_gaps_values)
    seeds = parse_ints(args.seeds)
    source_rows = load_scope(Path(args.scope))
    selected = [row for row in source_rows if row.get("source_domain_type") in {"GUE", "Poisson"}]
    selected = sorted(selected, key=lambda row: int(row["cycle"]))
    names = [row["domain_window"] for row in selected]
    base_labels = [row["source_domain_type"] for row in selected]
    classical = classical_state_by_row(Path(args.stability_audit))

    gap_cache = {row["domain_window"]: row_spacings(row["domain"]) for row in selected}
    rng = np.random.default_rng(args.seed)

    totals = {name: {"observed": 0, "label_null": 0, "rewire_null": 0, "margin": [], "cross": []} for name in names}
    run_count = 0
    label_null_trials = 0
    rewire_null_trials = 0

    for k in ks:
        for n_gaps in n_gaps_values:
            for seed in seeds:
                run_count += 1
                local_rng = np.random.default_rng(seed)
                graph_rows = []
                for source in selected:
                    gaps = gap_cache[source["domain_window"]]
                    gaps = gaps[:n_gaps] if len(gaps) > n_gaps else gaps
                    obs = compute_observables(gaps)
                    z = shuffle_z(gaps, obs, args.n_shuffle, local_rng)
                    graph_rows.append(
                        {
                            "domain_window": source["domain_window"],
                            "domain": source["domain"],
                            "cycle": source["cycle"],
                            "source_domain_type": source["source_domain_type"],
                            "n_gaps": int(len(gaps)),
                            "observables": obs,
                            "shuffle_z": z,
                        }
                    )
                x = standardized_matrix(graph_rows)
                edges = build_knn_edges(x, k)
                margins = centroid_margins(x, base_labels)
                cross = incident_cross_fractions(len(names), edges, base_labels)
                observed = bridge_flags(edges, base_labels, margins, args.margin_threshold)
                for i, name in enumerate(names):
                    totals[name]["observed"] += int(observed[i])
                    totals[name]["margin"].append(margins[i])
                    totals[name]["cross"].append(cross[i])

                labels_array = np.asarray(base_labels, dtype=object)
                for _ in range(args.label_nulls):
                    shuffled = labels_array.copy()
                    rng.shuffle(shuffled)
                    shuffled_labels = [str(label) for label in shuffled.tolist()]
                    shuffled_margins = centroid_margins(x, shuffled_labels)
                    flags = bridge_flags(edges, shuffled_labels, shuffled_margins, args.margin_threshold)
                    for i, name in enumerate(names):
                        totals[name]["label_null"] += int(flags[i])
                    label_null_trials += 1

                swap_count = max(len(edges) * args.rewire_swap_multiplier, 1)
                for _ in range(args.rewire_nulls):
                    rewired = degree_preserving_rewire(edges, len(names), rng, swap_count)
                    flags = bridge_flags(rewired, base_labels, margins, args.margin_threshold)
                    for i, name in enumerate(names):
                        totals[name]["rewire_null"] += int(flags[i])
                    rewire_null_trials += 1

    rows = []
    for source in selected:
        name = source["domain_window"]
        item = totals[name]
        observed_freq = item["observed"] / run_count
        label_freq = item["label_null"] / label_null_trials if label_null_trials else 0.0
        rewire_freq = item["rewire_null"] / rewire_null_trials if rewire_null_trials else 0.0
        audit_state = classical.get(name, "")
        graph_only = audit_state == "graph_only_bridge" and observed_freq >= args.stable_threshold
        rows.append(
            {
                "domain_window": name,
                "domain": source["domain"],
                "source_domain_type": source["source_domain_type"],
                "classical_audit_state": audit_state,
                "observed_graph_bridge_frequency": round(observed_freq, 6),
                "label_shuffle_bridge_frequency": round(label_freq, 6),
                "degree_rewire_bridge_frequency": round(rewire_freq, 6),
                "label_shuffle_lift": round(observed_freq - label_freq, 6),
                "degree_rewire_lift": round(observed_freq - rewire_freq, 6),
                "mean_centroid_margin": round(float(np.mean(item["margin"])), 6),
                "mean_cross_neighbor_fraction": round(float(np.mean(item["cross"])), 6),
                "stable_graph_only_residue": graph_only,
                "graph_baseline_state": (
                    "graph_specific_residue"
                    if graph_only and observed_freq > label_freq and observed_freq > rewire_freq
                    else "not_graph_specific_residue"
                ),
            }
        )

    two_reader = [
        row["domain_window"]
        for row in rows
        if row["classical_audit_state"] == "classic_and_graph_bridge"
        and row["observed_graph_bridge_frequency"] >= args.stable_threshold
    ]
    graph_only = [row["domain_window"] for row in rows if row["stable_graph_only_residue"]]
    graph_specific = [row["domain_window"] for row in rows if row["graph_baseline_state"] == "graph_specific_residue"]

    output = {
        "experiment": "boundary_graph_null_audit",
        "question": "Does the stable graph-only residue survive graph-native null baselines?",
        "observables_registry": "1.0.0-2026-05-06 via boundary_graph_curvature_gate",
        "observables_used": [
            "observed_graph_bridge_frequency",
            "label_shuffle_bridge_frequency",
            "degree_rewire_bridge_frequency",
            "label_shuffle_lift",
            "degree_rewire_lift",
            "mean_centroid_margin",
            "mean_cross_neighbor_fraction",
        ],
        "params": {
            "scope": args.scope,
            "stability_audit": args.stability_audit,
            "k_values": ks,
            "n_gaps_values": n_gaps_values,
            "seeds": seeds,
            "n_shuffle": args.n_shuffle,
            "label_nulls": args.label_nulls,
            "rewire_nulls": args.rewire_nulls,
            "margin_threshold": args.margin_threshold,
            "stable_threshold": args.stable_threshold,
            "graph_reader_runs": run_count,
            "label_null_trials": label_null_trials,
            "rewire_null_trials": rewire_null_trials,
        },
        "observable_contract": {
            "claim": "graph-only residues are Lab-specific only if their bridge frequency exceeds label-shuffle and degree-preserving graph null frequencies",
            "observable": "observed graph bridge frequency versus graph-native null bridge frequencies",
            "operator": "rerun BOUNDARY graph reader and compare each row to label-shuffle and degree-preserving rewiring nulls",
            "generator": "13 row-aligned BOUNDARY denominator with canonical+rigidity+shuffle-z feature graph",
            "denominator": "13 rows: 8 GUE and 5 Poisson, repeated across graph-reader parameter grid and graph null trials",
            "non_possible": "graph-only Lab residue if null frequencies match or exceed observed graph bridge frequency",
            "not_tested": "new Hamiltonian systems, alternative unfolding, physical universality of graph-only rows",
        },
        "summary": {
            "rows_analyzed": len(rows),
            "graph_reader_runs": run_count,
            "two_reader_boundary_confirmed": len(two_reader),
            "two_reader_boundary_rows": two_reader,
            "graph_only_residue": len(graph_only),
            "graph_only_residue_rows": graph_only,
            "graph_specific_residue_after_nulls": len(graph_specific),
            "graph_specific_residue_rows": graph_specific,
            "scope_change_declared": "two-reader boundary remains only classic_and_graph rows; graph-only rows are frequency-graph residues under audit, not two-reader confirmations",
            "graph_baseline_audit": "label_shuffle + degree_preserving_rewire",
        },
        "rows": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--stability-audit", default="tools/data/boundary_bridge_stability_audit_20260515_1915.json")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--n-gaps-values", default="512,1024,2048")
    parser.add_argument("--seeds", default="20260515,20260516,20260517")
    parser.add_argument("--n-shuffle", type=int, default=32)
    parser.add_argument("--label-nulls", type=int, default=64)
    parser.add_argument("--rewire-nulls", type=int, default=64)
    parser.add_argument("--rewire-swap-multiplier", type=int, default=8)
    parser.add_argument("--margin-threshold", type=float, default=0.25)
    parser.add_argument("--stable-threshold", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=20260516)
    parser.add_argument("--out", default="tools/data/boundary_graph_null_audit_20260516_0330.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
