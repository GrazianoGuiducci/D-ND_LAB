#!/usr/bin/env python3
"""
Stability audit for the BOUNDARY two-reader gate.

The audit keeps the 13 row-aligned GUE/Poisson denominator and reruns the graph
reader across small perturbations of k, spacing length, and shuffle seed. It then
joins those frequencies with the classical crossover audit states.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from exp_boundary_graph_curvature_gate import (
    compute_observables,
    classify_geometry,
    load_scope,
    row_spacings,
    shuffle_z,
    standardized_matrix,
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def parse_ints(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("empty integer list")
    return values


def classical_map(path: Path) -> dict[str, dict[str, Any]]:
    audit = load_json(path)
    rows = audit.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain rows")
    return {row["domain_window"]: row for row in rows}


def classify_frequency(freq: float) -> str:
    if freq >= 0.75:
        return "stable_graph_bridge"
    if freq >= 0.25:
        return "parameter_sensitive_bridge"
    return "unstable_non_bridge"


def run(args: argparse.Namespace) -> dict[str, Any]:
    ks = parse_ints(args.k_values)
    n_gaps_values = parse_ints(args.n_gaps_values)
    seeds = parse_ints(args.seeds)
    classical = classical_map(Path(args.classical_audit))

    source_rows = load_scope(Path(args.scope))
    selected = [row for row in source_rows if row.get("source_domain_type") in {"GUE", "Poisson"}]
    selected = sorted(selected, key=lambda row: int(row["cycle"]))
    gap_cache = {row["domain_window"]: row_spacings(row["domain"]) for row in selected}

    runs = []
    row_hits: dict[str, dict[str, Any]] = {}
    total_runs = 0

    for k in ks:
        for n_gaps in n_gaps_values:
            for seed in seeds:
                total_runs += 1
                import numpy as np

                rng = np.random.default_rng(seed)
                graph_rows = []
                for source in selected:
                    gaps = gap_cache[source["domain_window"]]
                    if len(gaps) < args.min_gaps:
                        continue
                    gaps = gaps[:n_gaps] if len(gaps) > n_gaps else gaps
                    obs = compute_observables(gaps)
                    z = shuffle_z(gaps, obs, args.n_shuffle, rng)
                    graph_rows.append(
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
                graph = {
                    "summary": {},
                    "geometry": classify_geometry(graph_rows, standardized_matrix(graph_rows), k),
                }
                graph["summary"]["third_included_candidates"] = graph["geometry"]["third_included_candidates"]
                graph["summary"]["edge_counts"] = graph["geometry"]["edge_counts"]
                candidates = set(graph["summary"]["third_included_candidates"])
                runs.append(
                    {
                        "k": k,
                        "n_gaps": n_gaps,
                        "seed": seed,
                        "third_included_candidates": sorted(candidates),
                        "cross_edges": graph["summary"]["edge_counts"]["cross_label"],
                    }
                )
                for row in graph["geometry"]["rows"]:
                    name = row["domain_window"]
                    if name not in row_hits:
                        row_hits[name] = {
                            "domain_window": name,
                            "domain": row["domain"],
                            "source_domain_type": row["source_domain_type"],
                            "hit_count": 0,
                            "cut_edge_count": 0,
                            "margin_values": [],
                            "cross_fraction_values": [],
                        }
                    if row["boundary_state"] == "third_included_candidate":
                        row_hits[name]["hit_count"] += 1
                    if row["boundary_state"] == "cut_edge":
                        row_hits[name]["cut_edge_count"] += 1
                    row_hits[name]["margin_values"].append(float(row["centroid_margin"]))
                    row_hits[name]["cross_fraction_values"].append(float(row["cross_neighbor_fraction"]))

    rows = []
    counts: dict[str, int] = {}
    for name in sorted(row_hits):
        item = row_hits[name]
        hit_frequency = item["hit_count"] / total_runs
        cut_frequency = item["cut_edge_count"] / total_runs
        classic = classical.get(name, {})
        stability_state = classify_frequency(hit_frequency)
        composite_state = f"{stability_state}+{classic.get('audit_state', 'missing_classical_audit')}"
        row = {
            "domain_window": name,
            "domain": item["domain"],
            "source_domain_type": item["source_domain_type"],
            "graph_bridge_hits": item["hit_count"],
            "graph_bridge_frequency": round(hit_frequency, 6),
            "cut_edge_frequency": round(cut_frequency, 6),
            "mean_margin": round(sum(item["margin_values"]) / len(item["margin_values"]), 6),
            "mean_cross_neighbor_fraction": round(
                sum(item["cross_fraction_values"]) / len(item["cross_fraction_values"]), 6
            ),
            "stability_state": stability_state,
            "classical_audit_state": classic.get("audit_state"),
            "brody_q": classic.get("brody_q"),
            "berry_robnick_like_gue_weight": classic.get("berry_robnick_like_gue_weight"),
            "composite_state": composite_state,
        }
        rows.append(row)
        counts[composite_state] = counts.get(composite_state, 0) + 1

    stable_graph_only = [
        row["domain_window"]
        for row in rows
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] == "graph_only_bridge"
    ]
    stable_classic_and_graph = [
        row["domain_window"]
        for row in rows
        if row["stability_state"] == "stable_graph_bridge"
        and row["classical_audit_state"] == "classic_and_graph_bridge"
    ]
    classic_only_stable_graph_absent = [
        row["domain_window"]
        for row in rows
        if row["stability_state"] == "unstable_non_bridge"
        and row["classical_audit_state"] == "classic_only_intermediate"
    ]

    output = {
        "experiment": "boundary_bridge_stability_audit",
        "question": "Do BOUNDARY graph bridge rows survive small graph-reader perturbations after the classical audit?",
        "observables_registry": "1.0.0-2026-05-06 via boundary_graph_curvature_gate; classical audit coordinates joined",
        "observables_used": [
            "graph_bridge_frequency",
            "cut_edge_frequency",
            "mean_centroid_margin",
            "mean_cross_neighbor_fraction",
            "classical_audit_state",
            "brody_q",
            "berry_robnick_like_gue_weight",
        ],
        "params": {
            "scope": args.scope,
            "classical_audit": args.classical_audit,
            "k_values": ks,
            "n_gaps_values": n_gaps_values,
            "seeds": seeds,
            "n_shuffle": args.n_shuffle,
            "min_gaps": args.min_gaps,
            "total_runs": total_runs,
        },
        "observable_contract": {
            "claim": "a two-reader boundary row is operational only if graph bridge status is stable enough to survive reader perturbation and remains classically audited",
            "observable": "graph bridge hit frequency joined with Brody/Berry-Robnik-like audit state",
            "operator": "parameter perturbation over kNN graph reader with row-aligned classical audit join",
            "generator": "boundary_graph_curvature_gate over the 13-row BOUNDARY denominator",
            "denominator": "13 rows: 8 GUE and 5 Poisson, repeated across graph-reader parameter grid",
            "non_possible": "stable Lab bridge if bridge frequency collapses under k/n_gaps/seed perturbation",
            "not_tested": "new physical Hamiltonian flow, alternative unfolding, asymptotic scaling beyond this finite denominator",
        },
        "summary": {
            "rows_analyzed": len(rows),
            "graph_reader_runs": total_runs,
            "composite_counts": counts,
            "stable_graph_only": stable_graph_only,
            "stable_classic_and_graph": stable_classic_and_graph,
            "classic_only_stable_graph_absent": classic_only_stable_graph_absent,
            "lab_residue_after_stability": bool(stable_graph_only or classic_only_stable_graph_absent),
        },
        "rows": rows,
        "runs": runs,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--classical-audit", default="tools/data/boundary_classical_crossover_audit_20260515_1904.json")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--n-gaps-values", default="512,1024,2048")
    parser.add_argument("--seeds", default="20260515,20260516,20260517")
    parser.add_argument("--n-shuffle", type=int, default=32)
    parser.add_argument("--min-gaps", type=int, default=64)
    parser.add_argument("--out", default="tools/data/boundary_bridge_stability_audit_20260515_1915.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
