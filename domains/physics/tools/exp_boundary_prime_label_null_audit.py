#!/usr/bin/env python3
"""
Label-count-preserving null audit for the BOUNDARY prime bridge.

The audit keeps the row-local features and the same 27 graph-reader settings used
by the stability audit, then permutes only the GUE/Poisson source labels while
preserving the 8/5 count. This tests whether the named prime bridge depends on
the physical source labels or is often reconstructed by label geometry alone.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_graph_curvature_gate import (
    classify_geometry,
    compute_observables,
    load_scope,
    row_spacings,
    shuffle_z,
    standardized_matrix,
)
from exp_boundary_bridge_stability_audit import classical_map, parse_ints


TARGET = "numeri_primi:cycle_3"


def load_reader_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
                reader_runs.append({"k": k, "n_gaps": n_gaps, "seed": seed, "rows": graph_rows})
    return selected, reader_runs


def geometry_hits(rows: list[dict[str, Any]], k: int) -> set[str]:
    geometry = classify_geometry(rows, standardized_matrix(rows), k)
    return set(geometry["third_included_candidates"])


def relabel_rows(
    rows: list[dict[str, Any]],
    labels_by_name: dict[str, str],
) -> list[dict[str, Any]]:
    relabeled = []
    for row in rows:
        item = dict(row)
        item["source_domain_type"] = labels_by_name[row["domain_window"]]
        relabeled.append(item)
    return relabeled


def summarize_target(
    reader_runs: list[dict[str, Any]],
    labels_by_name: dict[str, str] | None = None,
) -> dict[str, Any]:
    target_hits = 0
    any_stable_hits: dict[str, int] = {}
    per_run = []
    for run in reader_runs:
        rows = run["rows"] if labels_by_name is None else relabel_rows(run["rows"], labels_by_name)
        hits = geometry_hits(rows, run["k"])
        if TARGET in hits:
            target_hits += 1
        for name in hits:
            any_stable_hits[name] = any_stable_hits.get(name, 0) + 1
        per_run.append(
            {
                "k": run["k"],
                "n_gaps": run["n_gaps"],
                "seed": run["seed"],
                "target_hit": TARGET in hits,
                "third_included_candidates": sorted(hits),
            }
        )
    stable_27 = sorted(name for name, hits in any_stable_hits.items() if hits == len(reader_runs))
    return {
        "target_hits": target_hits,
        "target_frequency": round(target_hits / len(reader_runs), 9),
        "stable_27_rows": stable_27,
        "per_run": per_run,
    }


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return [round(max(0.0, center - margin), 9), round(min(1.0, center + margin), 9)]


def run(args: argparse.Namespace) -> dict[str, Any]:
    selected, reader_runs = load_reader_rows(args)
    classical = classical_map(Path(args.classical_audit))
    observed = summarize_target(reader_runs)

    names = [row["domain_window"] for row in selected]
    original_labels = {row["domain_window"]: row["source_domain_type"] for row in selected}
    label_values = [original_labels[name] for name in names]
    rng = np.random.default_rng(args.null_seed)

    target_ge_observed = 0
    target_eq_27 = 0
    any_eq_27 = 0
    target_hits_distribution: dict[str, int] = {}
    target_label_distribution: dict[str, int] = {"GUE": 0, "Poisson": 0}
    target_eq_27_with_target_label: dict[str, int] = {"GUE": 0, "Poisson": 0}
    null_examples = []

    for trial in range(args.null_trials):
        permuted = list(rng.permutation(label_values))
        labels_by_name = dict(zip(names, permuted, strict=True))
        summary = summarize_target(reader_runs, labels_by_name)
        hits = summary["target_hits"]
        target_hits_distribution[str(hits)] = target_hits_distribution.get(str(hits), 0) + 1
        target_label = labels_by_name[TARGET]
        target_label_distribution[target_label] += 1
        if hits >= observed["target_hits"]:
            target_ge_observed += 1
        if hits == len(reader_runs):
            target_eq_27 += 1
            target_eq_27_with_target_label[target_label] += 1
        if summary["stable_27_rows"]:
            any_eq_27 += 1
        if len(null_examples) < args.example_count and (hits == len(reader_runs) or summary["stable_27_rows"]):
            null_examples.append(
                {
                    "trial": trial,
                    "target_label": target_label,
                    "target_hits": hits,
                    "stable_27_rows": summary["stable_27_rows"],
                }
            )

    output = {
        "experiment": "boundary_prime_label_null_audit",
        "question": "Does the prime two-reader bridge survive a label-count-preserving null on the same 13-row BOUNDARY reader?",
        "observables_registry": "1.0.0-2026-05-06 via boundary_graph_curvature_gate; classical audit joined for target only",
        "observables_used": [
            "target_graph_bridge_hits",
            "target_graph_bridge_frequency",
            "label_count_preserving_null_hits",
            "any_row_stable_27_under_null",
            "classical_audit_state",
            "brody_q",
            "berry_robnick_like_gue_weight",
        ],
        "params": {
            "scope": args.scope,
            "classical_audit": args.classical_audit,
            "k_values": parse_ints(args.k_values),
            "n_gaps_values": parse_ints(args.n_gaps_values),
            "seeds": parse_ints(args.seeds),
            "n_shuffle": args.n_shuffle,
            "min_gaps": args.min_gaps,
            "null_trials": args.null_trials,
            "null_seed": args.null_seed,
            "target": TARGET,
        },
        "observable_contract": {
            "claim": "the named prime bridge is physical only if its 27/27 graph-reader status is not commonly reconstructed when only the 8/5 labels are permuted",
            "observable": "target row bridge hit count across the same 27 graph-reader perturbations",
            "operator": "label-count-preserving permutation null over the 13 row-aligned BOUNDARY labels",
            "generator": "fixed row-local feature vectors from boundary_graph_curvature_gate; only source_domain_type changes under null",
            "denominator": "13 rows, 27 graph-reader reads, 512 null label permutations",
            "p_value_definition": "right-tail raw_p=k/N and add_one_p=(k+1)/(N+1), k = null trials with target_hits >= observed target_hits",
            "non_possible": "calling numeri_primi:cycle_3 a physical return if target 27/27 is reconstructed frequently by label permutations",
            "not_tested": "new spectra, new physical Hamiltonian, analytic source-label validity, asymptotic scaling",
        },
        "observed": {
            "target": TARGET,
            "target_source_label": original_labels[TARGET],
            "target_classical_audit": classical.get(TARGET),
            "target_hits": observed["target_hits"],
            "target_frequency": observed["target_frequency"],
            "stable_27_rows": observed["stable_27_rows"],
        },
        "null": {
            "target_ge_observed": target_ge_observed,
            "target_eq_27": target_eq_27,
            "any_row_eq_27": any_eq_27,
            "raw_p": round(target_ge_observed / args.null_trials, 9),
            "add_one_p": round((target_ge_observed + 1) / (args.null_trials + 1), 9),
            "wilson_95": wilson_interval(target_ge_observed, args.null_trials),
            "target_hits_distribution": dict(sorted(target_hits_distribution.items(), key=lambda item: int(item[0]))),
            "target_label_distribution": target_label_distribution,
            "target_eq_27_with_target_label": target_eq_27_with_target_label,
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
    parser.add_argument("--classical-audit", default="tools/data/boundary_classical_crossover_audit_20260515_1904.json")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--n-gaps-values", default="512,1024,2048")
    parser.add_argument("--seeds", default="20260515,20260516,20260517")
    parser.add_argument("--n-shuffle", type=int, default=32)
    parser.add_argument("--min-gaps", type=int, default=64)
    parser.add_argument("--null-trials", type=int, default=512)
    parser.add_argument("--null-seed", type=int, default=20260516)
    parser.add_argument("--example-count", type=int, default=8)
    parser.add_argument("--out", default="tools/data/boundary_prime_label_null_audit_20260516_1148.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
