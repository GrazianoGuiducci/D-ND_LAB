#!/usr/bin/env python3
"""
Endpoint-preserving null for the Anderson 3D two-reader boundary candidate.

The 11:17 cycle found W=20 as a cross-size two-reader row, but a full feature
scramble reconstructed the count.  This audit makes the null stricter and more
physical: endpoint rows stay fixed, while only mobility-candidate feature rows
are permuted within each size before the candidate is named.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_anderson3d_mobility_edge_two_reader_audit import (
    OBS_NAMES,
    classify_graph,
    classical_state,
    parse_ints,
    stability_state,
    two_reader_names_from_rows,
)
from observables_registry import OBSERVABLES_REGISTRY_VERSION


SCALAR_FIELDS = [
    "adjacent_r",
    "brody_q",
    "wigner_poisson_like_weight",
    "mean_ipr",
    "participation_entropy",
]


def compact_rows(entry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in entry["rows"]:
        obs = {
            "SR": row["median_adjacent_r"],
            "SR2": row["median_brody_q"],
            "L1": row["median_wigner_poisson_like_weight"],
            "L2": row["median_mean_ipr"],
            "triple_var": row["median_participation_entropy"],
            "SR_local_rigidity": row["median_adjacent_r"],
        }
        rows.append(
            {
                "domain_window": row["domain_window"],
                "disorder_W": row["disorder_W"],
                "source_domain_type": row["source_domain_type"],
                "adjacent_r": row["median_adjacent_r"],
                "brody_q": row["median_brody_q"],
                "wigner_poisson_like_weight": row["median_wigner_poisson_like_weight"],
                "mean_ipr": row["median_mean_ipr"],
                "participation_entropy": row["median_participation_entropy"],
                "observables": obs,
            }
        )
    return rows


def endpoint_preserving_scramble(rows: list[dict[str, Any]], rng: np.random.Generator) -> list[dict[str, Any]]:
    trial = [{**row, "observables": dict(row["observables"])} for row in rows]
    candidate_indices = [
        idx for idx, row in enumerate(trial)
        if row["source_domain_type"] == "mobility_candidate"
    ]
    if len(candidate_indices) < 2:
        return trial

    for name in OBS_NAMES:
        values = [trial[idx]["observables"][name] for idx in candidate_indices]
        rng.shuffle(values)
        for idx, value in zip(candidate_indices, values):
            trial[idx]["observables"][name] = float(value)
    trial_values = {field: [trial[idx][field] for idx in candidate_indices] for field in SCALAR_FIELDS}
    for field, values in trial_values.items():
        rng.shuffle(values)
        for idx, value in zip(candidate_indices, values):
            trial[idx][field] = float(value)
    for idx in candidate_indices:
        trial[idx]["observables"]["SR_local_rigidity"] = trial[idx]["observables"]["SR"]
    return trial


def classify_size(rows: list[dict[str, Any]], k_values: list[int], graph_margin_max: float) -> dict[str, Any]:
    graph_hits = {row["domain_window"]: 0 for row in rows}
    graph_rows_by_k = []
    for k in k_values:
        graph = classify_graph(rows, k, graph_margin_max)
        graph_rows_by_k.append(graph)
        for grow in graph["rows"]:
            if grow["boundary_state"] == "third_included_candidate":
                graph_hits[grow["domain_window"]] += 1

    two_reader = []
    row_states = []
    for row in rows:
        freq = graph_hits[row["domain_window"]] / len(k_values)
        g_state = stability_state(freq)
        c_state = classical_state(row)
        if g_state == "stable_graph_bridge" and c_state == "classical_intermediate":
            two_reader.append(row["domain_window"])
        row_states.append(
            {
                "domain_window": row["domain_window"],
                "disorder_W": row["disorder_W"],
                "source_domain_type": row["source_domain_type"],
                "graph_bridge_frequency": round(freq, 6),
                "stability_state": g_state,
                "classical_audit_state": c_state,
                "composite_state": f"{g_state}+{c_state}",
            }
        )
    return {"two_reader_rows": sorted(two_reader), "row_states": row_states, "graph_rows_by_k": graph_rows_by_k}


def run(args: argparse.Namespace) -> dict[str, Any]:
    with Path(args.source).open(encoding="utf-8") as f:
        source = json.load(f)

    k_values = parse_ints(",".join(str(v) for v in source["parameters"]["k_values"]))
    graph_margin_max = float(source["parameters"]["graph_margin_max"])
    base_by_size = {entry["L"]: compact_rows(entry) for entry in source["by_size"]}

    observed_sets = {}
    observed_size_audit = {}
    for l_size, rows in base_by_size.items():
        audit = classify_size(rows, k_values, graph_margin_max)
        observed_sets[l_size] = set(audit["two_reader_rows"])
        observed_size_audit[str(l_size)] = audit["two_reader_rows"]
    observed_all = sorted(set.intersection(*observed_sets.values())) if observed_sets else []
    observed_count = len(observed_all)

    rng = np.random.default_rng(args.null_seed)
    null_counts = []
    named_hits: dict[str, int] = {}
    size_null_hits: dict[str, int] = {str(l_size): 0 for l_size in base_by_size}
    for _ in range(args.null_trials):
        trial_sets = []
        for l_size, rows in base_by_size.items():
            trial_rows = endpoint_preserving_scramble(rows, rng)
            names = two_reader_names_from_rows(trial_rows, argparse.Namespace(k_values=",".join(map(str, k_values)), graph_margin_max=graph_margin_max))
            trial_sets.append(names)
            if names:
                size_null_hits[str(l_size)] += 1
        cross = sorted(set.intersection(*trial_sets)) if trial_sets else []
        null_counts.append(len(cross))
        for name in cross:
            named_hits[name] = named_hits.get(name, 0) + 1

    k_ge = sum(1 for value in null_counts if value >= observed_count)
    raw_p = k_ge / args.null_trials if args.null_trials else 0.0
    add_one_p = (k_ge + 1) / (args.null_trials + 1) if args.null_trials else 1.0

    output = {
        "experiment": "anderson3d_endpoint_preserving_null",
        "question": "If endpoint rows stay fixed, does W=20 still beat a null that permutes only mobility-candidate feature alignment before candidate naming?",
        "source": args.source,
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": [
            "endpoint_preserving_mobility_candidate_feature_scramble",
            "two_reader_all_sizes",
            "graph_bridge_frequency",
            "classical_audit_state",
            "raw_p",
            "add_one_p",
        ],
        "parameters": {
            "sizes": sorted(base_by_size),
            "k_values": k_values,
            "graph_margin_max": graph_margin_max,
            "null_trials": args.null_trials,
            "null_seed": args.null_seed,
            "null_policy": "preserve metallic_wigner_pole and localized_poisson_pole rows; permute feature columns only among mobility_candidate rows inside each size",
        },
        "observable_contract": {
            "claim": "W=20 can be named only after endpoint-preserving candidate-row null fails to reconstruct the cross-size two-reader count",
            "observable": "cross-size intersection of stable_graph_bridge+classical_intermediate rows",
            "operator": "Anderson 3D cached row features from 20260516_1117; endpoint-preserving candidate feature permutation",
            "generator": "fixed endpoint rows plus mobility-candidate row-feature permutation within each size",
            "denominator": f"{args.null_trials} null trials, same 11 disorder rows and same L=5,6 compact rows from source",
            "non_possible": "physical promotion if raw_p is high or the named candidate appears frequently under endpoint-preserving null",
            "not_tested": "new eigensolver data, L>=7, mobility-edge exponent, experimental spectra",
        },
        "summary": {
            "observed_all_size_count": observed_count,
            "observed_all_size_rows": observed_all,
            "observed_size_audit": observed_size_audit,
            "endpoint_preserving_null": {
                "observed": observed_count,
                "k_ge_observed": k_ge,
                "trials": args.null_trials,
                "raw_p": round(raw_p, 9),
                "add_one_p": round(add_one_p, 9),
                "max_null": max(null_counts) if null_counts else 0,
                "mean_null": round(float(np.mean(null_counts)), 9) if null_counts else 0.0,
            },
            "size_null_hit_trials": size_null_hits,
            "cross_size_named_hits": dict(sorted(named_hits.items())),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="tools/data/anderson3d_mobility_edge_two_reader_audit_20260516_1117.json")
    parser.add_argument("--out", default="tools/data/anderson3d_endpoint_preserving_null_20260516_1124.json")
    parser.add_argument("--null-trials", type=int, default=512)
    parser.add_argument("--null-seed", type=int, default=202605161124)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
