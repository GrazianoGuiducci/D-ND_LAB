#!/usr/bin/env python3
"""
Supertile tiling gate for the phi gap-label core.

The substitution-grammar gate showed that length and symbol count do not carry
the high labels when internal order is destroyed. This tool moves one node
upstream: it separates true Fibonacci supertile boundaries from contiguous
chunks with the same length multiset.
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


def fibonacci_lengths(order: int) -> tuple[int, int]:
    if order < 2:
        raise ValueError("supertile_order must be >= 2")
    a, b = 1, 1
    for _ in range(2, order + 1):
        a, b = b, a + b
    return b, a


def fibonacci_type_word(n_types: int) -> np.ndarray:
    word = "1"
    previous = "0"
    while len(word) < n_types:
        word, previous = word + previous, word
    return np.array([int(ch) for ch in word[:n_types]], dtype=int)


def supertile_lengths(n: int, order: int) -> list[int]:
    long_len, short_len = fibonacci_lengths(order)
    types = fibonacci_type_word(max(8, int(np.ceil(n / short_len)) + 4))
    lengths: list[int] = []
    total = 0
    for t in types:
        length = long_len if t == 1 else short_len
        if total + length >= n:
            lengths.append(n - total)
            break
        lengths.append(length)
        total += length
    return [length for length in lengths if length > 0]


def chunks_from_lengths(seq: np.ndarray, lengths: list[int]) -> list[np.ndarray]:
    chunks = []
    start = 0
    for length in lengths:
        chunks.append(seq[start : start + length].copy())
        start += length
    if start < len(seq):
        chunks.append(seq[start:].copy())
    return chunks


def shuffle_chunks(chunks: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    shuffled = list(chunks)
    rng.shuffle(shuffled)
    return np.concatenate(shuffled)


def internal_count_shuffle(chunks: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    out = []
    for chunk in chunks:
        copied = chunk.copy()
        rng.shuffle(copied)
        out.append(copied)
    return np.concatenate(out)


def misaligned_same_lengths(seq: np.ndarray, lengths: list[int], rng: np.random.Generator) -> np.ndarray:
    if len(seq) < 2:
        return seq.copy()
    offset = int(rng.integers(1, len(seq)))
    rotated = np.roll(seq, -offset)
    chunks = chunks_from_lengths(rotated, lengths)
    shuffled = shuffle_chunks(chunks, rng)
    return np.roll(shuffled, offset)


def fixed_block_same_mean(seq: np.ndarray, lengths: list[int], rng: np.random.Generator) -> np.ndarray:
    mean_len = max(1, int(round(float(np.mean(lengths)))))
    return block_shuffle(seq, mean_len, rng)


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
        "all_low_count": int(sum(REFERENCE_LOW <= s for s in sets)),
        "all_high_count": int(sum(REFERENCE_HIGH <= s for s in sets)),
        "condition_count": int(n_sets),
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
    orders = parse_ints(args.supertile_orders)

    reference_rows = []
    rows = []
    tiling_meta = {}
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

            for order in orders:
                lengths = supertile_lengths(n, order)
                tiling_meta[f"N={n}|order={order}"] = {
                    "lengths": lengths,
                    "count": len(lengths),
                    "total": sum(lengths),
                    "unique_lengths": sorted(set(lengths)),
                }
                aligned_chunks = chunks_from_lengths(phi, lengths)
                mean_block = max(1, int(round(float(np.mean(lengths)))))
                for trial in range(args.trials):
                    variants = {
                        "supertile_shuffle": shuffle_chunks(aligned_chunks, rng),
                        "same_length_contiguous_shuffle": misaligned_same_lengths(phi, lengths, rng),
                        "same_count_internal_shuffle": internal_count_shuffle(aligned_chunks, rng),
                        "same_mean_block_shuffle": fixed_block_same_mean(phi, lengths, rng),
                    }
                    for mode, seq in variants.items():
                        for threshold in thresholds:
                            rows.append({
                                "mode": mode,
                                "N": n,
                                "phase": phase,
                                "threshold": threshold,
                                "trial": trial,
                                "supertile_order": order,
                                "mean_block": mean_block,
                                **gap_labels(seq, THETA, threshold, args.max_label, args.top_k),
                            })

    reference_summary = summarize_sets(reference_rows)
    reference_core = set(reference_summary["core_labels_all_conditions"])

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['mode']}|order={row['supertile_order']}"].append(row)

    mode_order_summary = {
        key: summarize_rows(group_rows, reference_core)
        for key, group_rows in grouped.items()
    }

    mode_summary = {}
    for mode in sorted({row["mode"] for row in rows}):
        mode_rows = [row for row in rows if row["mode"] == mode]
        mode_summary[mode] = summarize_rows(mode_rows, reference_core)

    return {
        "experiment": "gap_label_supertile_tiling_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "trials": args.trials,
            "supertile_orders": orders,
            "top_k": args.top_k,
            "max_label": args.max_label,
            "seed": args.seed,
        },
        "reference_core_phi": label_sort(reference_core),
        "reference_low": label_sort(REFERENCE_LOW),
        "reference_high": label_sort(REFERENCE_HIGH),
        "reference_summary": reference_summary,
        "tiling_meta": tiling_meta,
        "mode_order_summary": mode_order_summary,
        "mode_summary": mode_summary,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="377,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="2.0")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--supertile-orders", default="8,9,10,11")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=202605081909)
    parser.add_argument("--out", default="tools/data/gap_label_supertile_tiling_gate_20260508_1909.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {}
    for key, data in sorted(output["mode_order_summary"].items()):
        mode, order = key.split("|")
        compact[key] = {
            "mode": mode,
            "supertile_order": int(order.split("=")[1]),
            "median_jaccard": data["median_jaccard"],
            "low_retention": data["median_low_retention"],
            "high_retention": data["median_high_retention"],
            "all_high": f"{data['all_high_count']}/{data['condition_count']}",
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
                "all_high": f"{data['all_high_count']}/{data['condition_count']}",
                "all_high_condition_rate": data["all_high_condition_rate"],
            }
            for mode, data in output["mode_summary"].items()
        },
        "orders": compact,
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
