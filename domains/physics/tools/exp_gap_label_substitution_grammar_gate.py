#!/usr/bin/env python3
"""
Substitution-grammar gate for the phi gap-label core.

The block-scale audit showed that long Fibonacci block sizes carry the high
labels more often than long non-Fibonacci blocks. This tool separates block
length from internal grammar: it compares contiguous block shuffle with an
internal shuffle that preserves each block's length and symbol count while
destroying order inside the block.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_block_scale_gate import (
    REFERENCE_HIGH,
    REFERENCE_LOW,
    label_sort,
    parse_floats,
    parse_ints,
    retention,
)
from exp_gap_label_generator_gate import THETA, block_shuffle
from exp_gap_label_set_stability import gap_labels, jaccard, sturmian_sequence, summarize_sets


def internal_block_shuffle(seq: np.ndarray, block_size: int, rng: np.random.Generator) -> np.ndarray:
    blocks = []
    for start in range(0, len(seq), block_size):
        block = seq[start : start + block_size].copy()
        rng.shuffle(block)
        blocks.append(block)
    return np.concatenate(blocks)


def global_balanced_shuffle(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = seq.copy()
    rng.shuffle(out)
    return out


def summarize_rows(rows: list[dict], reference_core: set[int]) -> dict:
    summary = summarize_sets(rows)
    sets = [set(row["label_set"]) for row in rows if row["n_selected"] > 0]
    counter = Counter(label for s in sets for label in s)
    n_sets = len(sets)
    overlaps = [jaccard(set(row["label_set"]), reference_core) for row in rows if row["n_selected"] > 0]

    return {
        **summary,
        "median_overlap_with_phi_core": float(np.median(overlaps)) if overlaps else None,
        "median_low_retention": float(np.median([retention(row, REFERENCE_LOW) for row in rows])),
        "median_high_retention": float(np.median([retention(row, REFERENCE_HIGH) for row in rows])),
        "all_low_condition_rate": float(sum(REFERENCE_LOW <= s for s in sets) / n_sets) if n_sets else None,
        "all_high_condition_rate": float(sum(REFERENCE_HIGH <= s for s in sets) / n_sets) if n_sets else None,
        "high_label_condition_rates": {
            str(label): float(counter.get(label, 0) / n_sets) if n_sets else None
            for label in label_sort(REFERENCE_HIGH)
        },
        "low_label_condition_rates": {
            str(label): float(counter.get(label, 0) / n_sets) if n_sets else None
            for label in label_sort(REFERENCE_LOW)
        },
        "reference_core_retained_in_all": label_sort(set(summary.get("core_labels_all_conditions", [])) & reference_core),
        "reference_core_missing_from_all": label_sort(reference_core - set(summary.get("core_labels_all_conditions", []))),
    }


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
                    "mode": "reference_phi",
                    "N": n,
                    "phase": phase,
                    "threshold": threshold,
                    **gap_labels(phi, THETA, threshold, args.max_label, args.top_k),
                })
                for trial in range(args.trials):
                    balanced = global_balanced_shuffle(phi, rng)
                    rows.append({
                        "mode": "global_balanced_shuffle",
                        "block_size": None,
                        "block_family": "none",
                        "N": n,
                        "phase": phase,
                        "threshold": threshold,
                        "trial": trial,
                        **gap_labels(balanced, THETA, threshold, args.max_label, args.top_k),
                    })
                for block_size in block_sizes:
                    family = "fibonacci" if block_size in fibonacci_blocks else "non_fibonacci"
                    for trial in range(args.trials):
                        variants = {
                            "contiguous_block_shuffle": block_shuffle(phi, block_size, rng),
                            "internal_block_shuffle": internal_block_shuffle(phi, block_size, rng),
                        }
                        for mode, seq in variants.items():
                            rows.append({
                                "mode": mode,
                                "block_size": block_size,
                                "block_family": family,
                                "N": n,
                                "phase": phase,
                                "threshold": threshold,
                                "trial": trial,
                                **gap_labels(seq, THETA, threshold, args.max_label, args.top_k),
                            })

    reference_summary = summarize_sets(reference_rows)
    reference_core = set(reference_summary["core_labels_all_conditions"])

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = f"{row['mode']}|{row['block_size']}"
        grouped[key].append(row)

    mode_block_summary = {
        key: summarize_rows(group_rows, reference_core)
        for key, group_rows in grouped.items()
    }

    mode_summary = {}
    for mode in sorted({row["mode"] for row in rows}):
        mode_rows = [row for row in rows if row["mode"] == mode]
        mode_summary[mode] = summarize_rows(mode_rows, reference_core)

    return {
        "experiment": "gap_label_substitution_grammar_gate",
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
        },
        "reference_core_phi": label_sort(reference_core),
        "reference_low": label_sort(REFERENCE_LOW),
        "reference_high": label_sort(REFERENCE_HIGH),
        "reference_summary": reference_summary,
        "mode_block_summary": mode_block_summary,
        "mode_summary": mode_summary,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="377,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="2.0")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--fibonacci-blocks", default="34,55,89,144")
    parser.add_argument("--non-fibonacci-blocks", default="40,64,96,128")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=202605081834)
    parser.add_argument("--out", default="tools/data/gap_label_substitution_grammar_gate_20260508_1834.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {}
    for key, data in sorted(
        output["mode_block_summary"].items(),
        key=lambda item: (
            item[0].split("|")[0],
            -1 if item[0].split("|")[1] == "None" else int(item[0].split("|")[1]),
        ),
    ):
        mode, block = key.split("|")
        compact[key] = {
            "mode": mode,
            "block_size": None if block == "None" else int(block),
            "median_jaccard": data["median_jaccard"],
            "low_retention": data["median_low_retention"],
            "high_retention": data["median_high_retention"],
            "all_high_condition_rate": data["all_high_condition_rate"],
            "stable_labels_75pct": data["stable_labels_75pct"],
        }

    print(json.dumps({
        "reference_core_phi": output["reference_core_phi"],
        "reference_high": output["reference_high"],
        "mode_summary": {
            mode: {
                "median_jaccard": data["median_jaccard"],
                "low_retention": data["median_low_retention"],
                "high_retention": data["median_high_retention"],
                "all_high_condition_rate": data["all_high_condition_rate"],
            }
            for mode, data in output["mode_summary"].items()
        },
        "blocks": compact,
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
