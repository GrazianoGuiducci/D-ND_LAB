#!/usr/bin/env python3
"""
Size-stability audit for the Rosenzweig-Porter BOUNDARY two-reader gate.

This is the follow-up to the finite-N physical bridge audit: keep the
Rosenzweig-Porter Hamiltonian flow, perturb the graph reader, and ask whether
the same lambda row survives when the matrix size changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from exp_rosenzweig_porter_bridge_physical_audit import (
    FEATURE_NAMES,
    OBSERVABLES_REGISTRY_VERSION,
    classify_graph,
    classical_state,
    compute_row,
    parse_floats,
    parse_ints,
    stability_state,
)


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def audit_size(args: argparse.Namespace, n: int) -> dict[str, Any]:
    lambdas = parse_floats(args.lambdas)
    seeds = parse_ints(args.seeds)
    ks = parse_ints(args.k_values)
    total_runs = len(seeds) * len(ks)
    row_hits: dict[str, dict[str, Any]] = {}
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
        for k in ks:
            graph = classify_graph(rows, k)
            reader_runs.append({"n": n, "seed": seed, "k": k, "third_included_candidates": graph["third_included_candidates"]})
            graph_by_name = {row["domain_window"]: row for row in graph["rows"]}
            for row in rows:
                name = row["domain_window"]
                if name not in row_hits:
                    row_hits[name] = {
                        "lambda": row["lambda"],
                        "source_domain_type": row["source_domain_type"],
                        "graph_hits": 0,
                        "margins": [],
                        "cross_fractions": [],
                        "brody_q": [],
                        "mixture_w": [],
                        "mean_ipr": [],
                        "sr": [],
                    }
                graph_row = graph_by_name[name]
                if graph_row["boundary_state"] == "third_included_candidate":
                    row_hits[name]["graph_hits"] += 1
                row_hits[name]["margins"].append(float(graph_row["centroid_margin"]))
                row_hits[name]["cross_fractions"].append(float(graph_row["cross_neighbor_fraction"]))
                row_hits[name]["brody_q"].append(float(row["brody_q"]))
                row_hits[name]["mixture_w"].append(float(row["berry_robnick_like_gue_weight"]))
                row_hits[name]["mean_ipr"].append(float(row["mean_ipr"]))
                row_hits[name]["sr"].append(float(row["observables"]["SR"]))

    rows_out = []
    composite_counts: dict[str, int] = {}
    for name in sorted(row_hits, key=lambda key: row_hits[key]["lambda"]):
        item = row_hits[name]
        freq = item["graph_hits"] / total_runs
        class_row = {
            "brody_q": median(item["brody_q"]),
            "berry_robnick_like_gue_weight": median(item["mixture_w"]),
        }
        c_state = classical_state(class_row)
        g_state = stability_state(freq)
        composite = f"{g_state}+{c_state}"
        composite_counts[composite] = composite_counts.get(composite, 0) + 1
        rows_out.append(
            {
                "domain_window": name,
                "lambda": item["lambda"],
                "source_domain_type": item["source_domain_type"],
                "graph_bridge_frequency": round(freq, 6),
                "stability_state": g_state,
                "classical_audit_state": c_state,
                "composite_state": composite,
                "median_brody_q": round(median(item["brody_q"]), 6),
                "median_berry_robnick_like_gue_weight": round(median(item["mixture_w"]), 6),
                "median_SR": round(median(item["sr"]), 6),
                "median_mean_ipr": round(median(item["mean_ipr"]), 9),
                "mean_centroid_margin": round(float(np.mean(item["margins"])), 6),
                "mean_cross_neighbor_fraction": round(float(np.mean(item["cross_fractions"])), 6),
            }
        )

    two_reader_rows = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] == "classical_intermediate"
    ]
    graph_only_rows = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] != "classical_intermediate"
    ]
    classic_only_rows = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] != "stable_graph_bridge" and row["classical_audit_state"] == "classical_intermediate"
    ]

    return {
        "n": n,
        "total_graph_reader_runs": total_runs,
        "summary": {
            "two_reader_boundary_confirmed": len(two_reader_rows),
            "two_reader_rows": two_reader_rows,
            "graph_only_residue": len(graph_only_rows),
            "graph_only_rows": graph_only_rows,
            "classic_only_residue": len(classic_only_rows),
            "classic_only_rows": classic_only_rows,
            "composite_counts": composite_counts,
        },
        "rows": rows_out,
        "reader_runs": reader_runs,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    sizes = parse_ints(args.sizes)
    by_size = [audit_size(args, n) for n in sizes]
    size_names = {entry["n"]: set(entry["summary"]["two_reader_rows"]) for entry in by_size}
    all_two_reader = sorted(set.intersection(*size_names.values())) if size_names else []
    any_two_reader = sorted(set.union(*size_names.values())) if size_names else []
    intermittent_two_reader = [name for name in any_two_reader if name not in all_two_reader]

    row_by_lambda: dict[str, dict[str, Any]] = {}
    for entry in by_size:
        for row in entry["rows"]:
            item = row_by_lambda.setdefault(
                row["domain_window"],
                {
                    "lambda": row["lambda"],
                    "size_states": {},
                    "frequencies": [],
                    "classical_states": [],
                    "stability_states": [],
                },
            )
            item["size_states"][str(entry["n"])] = row["composite_state"]
            item["frequencies"].append(row["graph_bridge_frequency"])
            item["classical_states"].append(row["classical_audit_state"])
            item["stability_states"].append(row["stability_state"])

    rows_out = []
    for name in sorted(row_by_lambda, key=lambda key: row_by_lambda[key]["lambda"]):
        item = row_by_lambda[name]
        rows_out.append(
            {
                "domain_window": name,
                "lambda": item["lambda"],
                "size_states": item["size_states"],
                "min_graph_bridge_frequency": round(float(min(item["frequencies"])), 6),
                "max_graph_bridge_frequency": round(float(max(item["frequencies"])), 6),
                "two_reader_all_sizes": name in all_two_reader,
                "two_reader_intermittent": name in intermittent_two_reader,
                "classical_states_seen": sorted(set(item["classical_states"])),
                "stability_states_seen": sorted(set(item["stability_states"])),
            }
        )

    output = {
        "experiment": "rp_boundary_size_stability_audit",
        "question": "Does the Rosenzweig-Porter two-reader BOUNDARY row survive across matrix sizes?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "graph_bridge_frequency",
            "size_stability",
            "centroid_margin",
            "cross_neighbor_fraction",
            "classical_audit_state",
        ],
        "parameters": {
            "sizes": sizes,
            "reps": args.reps,
            "lambdas": parse_floats(args.lambdas),
            "seeds": parse_ints(args.seeds),
            "k_values": parse_ints(args.k_values),
            "central_fraction": args.central_fraction,
            "grid_size": args.grid_size,
            "poisson_pole_max": args.poisson_pole_max,
            "gue_pole_min": args.gue_pole_min,
        },
        "observable_contract": {
            "claim": "the RP two-reader BOUNDARY gate is physical only if the same lambda row remains stable across matrix sizes",
            "observable": "two_reader_all_sizes from graph_bridge_frequency joined with Brody q, Wigner/Poisson mixture weight, SR and IPR",
            "operator": "repeat the RP diagonal-plus-GUE Hamiltonian flow over sizes, seeds and kNN graph perturbations",
            "generator": "H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE, finite N size sweep",
            "denominator": "same lambda grid across all tested sizes",
            "non_possible": "physical two-reader row if no lambda is stable_graph_bridge+classical_intermediate at every tested size",
            "not_tested": "N to infinity, unfolding variants, Anderson mobility edge, many-body RP variants",
        },
        "summary": {
            "sizes_analyzed": len(sizes),
            "lambda_rows": len(parse_floats(args.lambdas)),
            "two_reader_all_sizes": len(all_two_reader),
            "two_reader_all_size_rows": all_two_reader,
            "two_reader_intermittent": len(intermittent_two_reader),
            "two_reader_intermittent_rows": intermittent_two_reader,
        },
        "cross_size_rows": rows_out,
        "by_size": by_size,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/rp_boundary_size_stability_audit_20260515_1940.json")
    parser.add_argument("--sizes", default="64,96,128")
    parser.add_argument("--reps", type=int, default=12)
    parser.add_argument("--lambdas", default="0,0.03,0.045,0.06,0.075,0.10,0.18,0.32,0.68,0.82,1.0")
    parser.add_argument("--seeds", default="202605151940,202605151941")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--poisson-pole-max", type=float, default=0.03)
    parser.add_argument("--gue-pole-min", type=float, default=0.82)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
