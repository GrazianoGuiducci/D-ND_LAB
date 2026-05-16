#!/usr/bin/env python3
"""
Comparable null audit for the Anderson 3D compact boundary rows.

The 11:24 falsifier rejected a comparison between a full feature-scramble null
and an endpoint-preserving null because the two runs used different readers,
denominators and trial counts.  This script keeps one compact row perimeter and
one observable, then runs both nulls with the same N before interpreting them.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

from exp_anderson3d_endpoint_preserving_null import (
    classify_size,
    compact_rows,
    endpoint_preserving_scramble,
)
from exp_anderson3d_mobility_edge_two_reader_audit import (
    OBS_NAMES,
    parse_ints,
    scrambled_rows,
    two_reader_names_from_rows,
)
from observables_registry import OBSERVABLES_REGISTRY_VERSION


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> dict[str, float]:
    if n <= 0:
        return {"low": 0.0, "high": 1.0}
    phat = k / n
    denom = 1.0 + (z * z / n)
    center = (phat + (z * z) / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt((phat * (1.0 - phat) / n) + (z * z / (4.0 * n * n)))
    return {"low": round(max(0.0, center - half), 9), "high": round(min(1.0, center + half), 9)}


def count_histogram(counts: list[int]) -> dict[str, int]:
    values, freq = np.unique(np.asarray(counts, dtype=int), return_counts=True)
    return {str(int(value)): int(n) for value, n in zip(values, freq)}


def summarize_null(
    name: str,
    counts: list[int],
    observed: int,
    named_hits: dict[str, int],
    trials: int,
) -> dict[str, Any]:
    k_ge = sum(1 for value in counts if value >= observed)
    raw_p = k_ge / trials if trials else 0.0
    add_one_p = (k_ge + 1) / (trials + 1) if trials else 1.0
    return {
        "null_name": name,
        "observed": observed,
        "k_ge_observed": k_ge,
        "trials": trials,
        "raw_p": round(raw_p, 9),
        "add_one_p": round(add_one_p, 9),
        "wilson_95": wilson_interval(k_ge, trials),
        "max_null": max(counts) if counts else 0,
        "mean_null": round(float(np.mean(counts)), 9) if counts else 0.0,
        "median_null": round(float(np.median(counts)), 9) if counts else 0.0,
        "histogram": count_histogram(counts),
        "cross_size_named_hits": dict(sorted(named_hits.items())),
    }


def run_null(
    base_by_size: dict[int, list[dict[str, Any]]],
    sizes: list[int],
    args: argparse.Namespace,
    rng: np.random.Generator,
    scramble_fn: Callable[[list[dict[str, Any]], np.random.Generator], list[dict[str, Any]]],
) -> tuple[list[int], dict[str, int]]:
    counts: list[int] = []
    named_hits: dict[str, int] = {}
    reader_args = argparse.Namespace(k_values=",".join(map(str, args.k_values)), graph_margin_max=args.graph_margin_max)
    for _ in range(args.null_trials):
        trial_sets = []
        for l_size in sizes:
            trial_rows = scramble_fn(base_by_size[l_size], rng)
            trial_sets.append(two_reader_names_from_rows(trial_rows, reader_args))
        cross = sorted(set.intersection(*trial_sets)) if trial_sets else []
        counts.append(len(cross))
        for name in cross:
            named_hits[name] = named_hits.get(name, 0) + 1
    return counts, named_hits


def difference_summary(endpoint: dict[str, Any], full: dict[str, Any]) -> dict[str, Any]:
    p_endpoint = endpoint["raw_p"]
    p_full = full["raw_p"]
    n_endpoint = endpoint["trials"]
    n_full = full["trials"]
    diff = p_full - p_endpoint
    se = math.sqrt((p_full * (1.0 - p_full) / n_full) + (p_endpoint * (1.0 - p_endpoint) / n_endpoint))
    z = diff / se if se > 0 else 0.0
    ci_low = diff - 1.959963984540054 * se
    ci_high = diff + 1.959963984540054 * se
    return {
        "comparison": "full_feature_scramble_raw_p - endpoint_preserving_raw_p",
        "difference": round(diff, 9),
        "wald_95": {"low": round(ci_low, 9), "high": round(ci_high, 9)},
        "z_approx": round(z, 6),
        "interpretation_unit": "same compact row perimeter, same cross-size two-reader observable, same N",
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    with Path(args.source).open(encoding="utf-8") as f:
        source = json.load(f)

    args.k_values = parse_ints(",".join(str(v) for v in source["parameters"]["k_values"]))
    args.graph_margin_max = float(source["parameters"]["graph_margin_max"])
    sizes = sorted(entry["L"] for entry in source["by_size"])
    base_by_size = {entry["L"]: compact_rows(entry) for entry in source["by_size"]}

    observed_sets: dict[int, set[str]] = {}
    observed_size_audit: dict[str, list[str]] = {}
    for l_size, rows in base_by_size.items():
        audit = classify_size(rows, args.k_values, args.graph_margin_max)
        observed_sets[l_size] = set(audit["two_reader_rows"])
        observed_size_audit[str(l_size)] = audit["two_reader_rows"]
    observed_all = sorted(set.intersection(*observed_sets.values())) if observed_sets else []
    observed_count = len(observed_all)

    endpoint_counts, endpoint_named_hits = run_null(
        base_by_size,
        sizes,
        args,
        np.random.default_rng(args.endpoint_seed),
        endpoint_preserving_scramble,
    )
    full_counts, full_named_hits = run_null(
        base_by_size,
        sizes,
        args,
        np.random.default_rng(args.full_seed),
        scrambled_rows,
    )

    endpoint_summary = summarize_null(
        "endpoint_preserving_candidate_only",
        endpoint_counts,
        observed_count,
        endpoint_named_hits,
        args.null_trials,
    )
    full_summary = summarize_null(
        "full_feature_scramble",
        full_counts,
        observed_count,
        full_named_hits,
        args.null_trials,
    )

    output = {
        "experiment": "anderson3d_comparable_null_audit",
        "question": "On the same compact Anderson perimeter, does endpoint-preserving candidate-only scrambling differ from full feature scrambling for the same cross-size two-reader observable?",
        "source": args.source,
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": [
            *OBS_NAMES,
            "SR_local_rigidity",
            "brody_q",
            "wigner_poisson_like_weight",
            "mean_ipr",
            "participation_entropy",
            "two_reader_all_sizes",
            "raw_p",
            "add_one_p",
            "wilson_95",
        ],
        "parameters": {
            "sizes": sizes,
            "k_values": args.k_values,
            "graph_margin_max": args.graph_margin_max,
            "null_trials": args.null_trials,
            "endpoint_seed": args.endpoint_seed,
            "full_seed": args.full_seed,
            "source_perimeter": "compact median rows from 20260516_1117",
        },
        "observable_contract": {
            "claim": "Nulls can be compared only when they share one observable, one row perimeter and one N",
            "observable": "cross-size intersection count of stable_graph_bridge+classical_intermediate rows",
            "operator": "compact Anderson 3D rows from 11:17, classified by the same kNN/classical reader",
            "generator": "same source rows; two null operators differ only in preserved structure",
            "denominator": f"{args.null_trials} trials for each null on the same {len(base_by_size[sizes[0]]) if sizes else 0} rows per size",
            "p_value_definition": "right tail; raw_p=k/N and add_one_p=(k+1)/(N+1), where k is null trials with cross-size count >= observed",
            "non_possible": "calling one null more restrictive if the perimeters or N differ",
            "not_tested": "raw multi-seed reader, new Hamiltonian samples, L>=7, full 8 GUE / 5 Poisson seed perimeter",
        },
        "summary": {
            "observed_all_size_count": observed_count,
            "observed_all_size_rows": observed_all,
            "observed_size_audit": observed_size_audit,
            "endpoint_preserving": endpoint_summary,
            "full_feature_scramble": full_summary,
            "difference": difference_summary(endpoint_summary, full_summary),
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
    parser.add_argument("--out", default="tools/data/anderson3d_comparable_null_audit_20260516_1135.json")
    parser.add_argument("--null-trials", type=int, default=512)
    parser.add_argument("--endpoint-seed", type=int, default=202605161135)
    parser.add_argument("--full-seed", type=int, default=202605161136)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
