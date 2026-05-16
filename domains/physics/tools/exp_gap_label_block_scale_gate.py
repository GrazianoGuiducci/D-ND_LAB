#!/usr/bin/env python3
"""
Block-scale gate for phi gap-label core retention.

The generator gate showed that short block shuffles keep local Sturmian texture
but lose the high labels of the phi core. This tool scans block length directly:
Fibonacci and non-Fibonacci block sizes are tested with the same phi label
reader, separating low-core retention from high-core re-entry.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_generator_gate import THETA, block_shuffle
from exp_gap_label_set_stability import gap_labels, jaccard, sturmian_sequence, summarize_sets


REFERENCE_LOW = {-1, 1, -2, 2}
REFERENCE_HIGH = {3, -4, 4, 6}


def parse_ints(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip()]


def parse_floats(raw: str) -> list[float]:
    return [float(x) for x in raw.split(",") if x.strip()]


def label_sort(labels: set[int] | list[int]) -> list[int]:
    return sorted(labels, key=lambda x: (abs(x), x))


def retention(row: dict, labels: set[int]) -> float:
    present = set(row["label_set"])
    return len(present & labels) / len(labels)


def summarize_block(rows: list[dict], reference_core: set[int]) -> dict:
    summary = summarize_sets(rows)
    sets = [set(row["label_set"]) for row in rows if row["n_selected"] > 0]
    counter = Counter(label for s in sets for label in s)
    n_sets = len(sets)
    high_rates = {
        str(label): float(counter.get(label, 0) / n_sets) if n_sets else None
        for label in label_sort(REFERENCE_HIGH)
    }
    low_rates = {
        str(label): float(counter.get(label, 0) / n_sets) if n_sets else None
        for label in label_sort(REFERENCE_LOW)
    }
    all_high_rate = (
        float(sum(REFERENCE_HIGH <= s for s in sets) / n_sets)
        if n_sets
        else None
    )
    all_low_rate = (
        float(sum(REFERENCE_LOW <= s for s in sets) / n_sets)
        if n_sets
        else None
    )
    overlaps = [jaccard(set(row["label_set"]), reference_core) for row in rows if row["n_selected"] > 0]
    return {
        **summary,
        "median_overlap_with_phi_core": float(np.median(overlaps)) if overlaps else None,
        "min_overlap_with_phi_core": float(np.min(overlaps)) if overlaps else None,
        "median_low_retention": float(np.median([retention(row, REFERENCE_LOW) for row in rows])),
        "median_high_retention": float(np.median([retention(row, REFERENCE_HIGH) for row in rows])),
        "all_low_condition_rate": all_low_rate,
        "all_high_condition_rate": all_high_rate,
        "low_label_condition_rates": low_rates,
        "high_label_condition_rates": high_rates,
        "reference_core_retained_in_all": label_sort(set(summary.get("core_labels_all_conditions", [])) & reference_core),
        "reference_core_missing_from_all": label_sort(reference_core - set(summary.get("core_labels_all_conditions", []))),
    }


def first_crossing(block_summaries: dict[str, dict], key: str, threshold: float) -> int | None:
    ordered = sorted((int(block), data) for block, data in block_summaries.items())
    for block, data in ordered:
        value = data.get(key)
        if value is not None and value >= threshold:
            return block
    return None


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_ints(args.ns)
    phases = parse_floats(args.phases)
    thresholds = parse_floats(args.thresholds)
    fibonacci_blocks = parse_ints(args.fibonacci_blocks)
    non_fibonacci_blocks = parse_ints(args.non_fibonacci_blocks)
    block_sizes = sorted(set(fibonacci_blocks + non_fibonacci_blocks))

    reference_rows = []
    rows = []
    for n in ns:
        for phase in phases:
            phi = sturmian_sequence(THETA, n, phase)
            for threshold in thresholds:
                reference_rows.append({
                    "generator": "phi_sturmian",
                    "N": n,
                    "phase": phase,
                    "threshold": threshold,
                    **gap_labels(phi, THETA, threshold, args.max_label, args.top_k),
                })
                for block_size in block_sizes:
                    for trial in range(args.trials):
                        shuffled = block_shuffle(phi, block_size, rng)
                        rows.append({
                            "generator": "block_shuffle",
                            "block_size": block_size,
                            "block_family": "fibonacci" if block_size in fibonacci_blocks else "non_fibonacci",
                            "N": n,
                            "phase": phase,
                            "threshold": threshold,
                            "trial": trial,
                            **gap_labels(shuffled, THETA, threshold, args.max_label, args.top_k),
                        })

    reference_summary = summarize_sets(reference_rows)
    reference_core = set(reference_summary["core_labels_all_conditions"])

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["block_size"])].append(row)

    block_summary = {
        block: summarize_block(group_rows, reference_core)
        for block, group_rows in grouped.items()
    }

    family_summary = {}
    for family in ("fibonacci", "non_fibonacci"):
        family_rows = [row for row in rows if row["block_family"] == family]
        family_summary[family] = summarize_block(family_rows, reference_core)

    high_any_crossing = first_crossing(block_summary, "median_high_retention", args.crossing_threshold)
    high_all_crossing = first_crossing(block_summary, "all_high_condition_rate", args.crossing_threshold)
    low_all_crossing = first_crossing(block_summary, "all_low_condition_rate", args.crossing_threshold)

    return {
        "experiment": "gap_label_block_scale_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "trials": args.trials,
            "fibonacci_blocks": fibonacci_blocks,
            "non_fibonacci_blocks": non_fibonacci_blocks,
            "top_k": args.top_k,
            "max_label": args.max_label,
            "seed": args.seed,
            "crossing_threshold": args.crossing_threshold,
        },
        "reference_core_phi": label_sort(reference_core),
        "reference_low": label_sort(REFERENCE_LOW),
        "reference_high": label_sort(REFERENCE_HIGH),
        "reference_summary": reference_summary,
        "block_summary": block_summary,
        "family_summary": family_summary,
        "crossings": {
            "median_high_retention_ge_threshold": high_any_crossing,
            "all_high_condition_rate_ge_threshold": high_all_crossing,
            "all_low_condition_rate_ge_threshold": low_all_crossing,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="377,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="2.0")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--fibonacci-blocks", default="5,8,13,21,34,55,89,144")
    parser.add_argument("--non-fibonacci-blocks", default="6,10,16,24,40,64,96,128")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--crossing-threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=202605081805)
    parser.add_argument("--out", default="tools/data/gap_label_block_scale_gate_20260508_1805.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        block: {
            "family": next(row["block_family"] for row in output["rows"] if row["block_size"] == int(block)),
            "median_jaccard": data["median_jaccard"],
            "median_overlap_with_phi_core": data["median_overlap_with_phi_core"],
            "median_low_retention": data["median_low_retention"],
            "median_high_retention": data["median_high_retention"],
            "all_high_condition_rate": data["all_high_condition_rate"],
            "stable_labels_75pct": data["stable_labels_75pct"],
        }
        for block, data in sorted(output["block_summary"].items(), key=lambda item: int(item[0]))
    }
    print(json.dumps({
        "reference_core_phi": output["reference_core_phi"],
        "reference_high": output["reference_high"],
        "crossings": output["crossings"],
        "blocks": compact,
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
