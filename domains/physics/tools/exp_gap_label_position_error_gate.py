#!/usr/bin/env python3
"""
Position/error gate for the phi gap-label core.

The supertile tiling gate showed that the label set does not discriminate exact
supertile boundaries from misaligned chunks with the same length multiset. This
tool keeps that perimeter and asks whether the geometry of the selected gaps
does discriminate: IDS position, spectral index, and label error for core
labels.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_block_scale_gate import REFERENCE_HIGH, REFERENCE_LOW, label_sort, parse_floats, parse_ints
from exp_gap_label_generator_gate import THETA
from exp_gap_label_set_stability import gap_labels, sturmian_sequence, summarize_sets
from exp_gap_label_supertile_tiling_gate import (
    chunks_from_lengths,
    internal_count_shuffle,
    misaligned_same_lengths,
    shuffle_chunks,
    supertile_lengths,
)


def selected_by_label(row: dict) -> dict[int, dict]:
    best: dict[int, dict] = {}
    for size_rank, item in enumerate(row["selected"]):
        enriched = {**item, "size_rank": size_rank}
        current = best.get(item["label"])
        if current is None or (item["label_error"], size_rank) < (current["label_error"], current["size_rank"]):
            best[item["label"]] = enriched
    return best


def row_with_obs(mode: str, seq: np.ndarray, n: int, phase: float, threshold: float, trial: int | None, order: int | None, args: argparse.Namespace) -> dict:
    row = {
        "mode": mode,
        "N": n,
        "phase": phase,
        "threshold": threshold,
        **gap_labels(seq, THETA, threshold, args.max_label, args.top_k),
    }
    if trial is not None:
        row["trial"] = trial
    if order is not None:
        row["supertile_order"] = order
    return row


def compare_to_reference(row: dict, reference_row: dict, core: set[int]) -> dict:
    selected = selected_by_label(row)
    reference = selected_by_label(reference_row)
    present = label_sort(set(selected) & core)
    missing = label_sort(core - set(selected))
    deltas = []
    for label in present:
        if label not in reference:
            continue
        item = selected[label]
        ref = reference[label]
        deltas.append({
            "label": int(label),
            "ids_delta_abs": float(abs(item["ids"] - ref["ids"])),
            "index_delta_abs": int(abs(item["index"] - ref["index"])),
            "index_delta_norm": float(abs(item["index"] - ref["index"]) / row["N"]),
            "size_rank_delta_abs": int(abs(item["size_rank"] - ref["size_rank"])),
            "label_error": float(item["label_error"]),
            "reference_label_error": float(ref["label_error"]),
            "label_error_delta": float(item["label_error"] - ref["label_error"]),
            "spacing_ratio_to_reference": float(item["spacing"] / ref["spacing"]) if ref["spacing"] else None,
        })

    return {
        "mode": row["mode"],
        "N": row["N"],
        "phase": row["phase"],
        "threshold": row["threshold"],
        "trial": row.get("trial"),
        "supertile_order": row.get("supertile_order"),
        "present_core": present,
        "missing_core": missing,
        "present_count": len(present),
        "core_size": len(core),
        "all_core_present": set(present) == core,
        "median_ids_delta_abs": float(np.median([d["ids_delta_abs"] for d in deltas])) if deltas else None,
        "median_index_delta_norm": float(np.median([d["index_delta_norm"] for d in deltas])) if deltas else None,
        "median_size_rank_delta_abs": float(np.median([d["size_rank_delta_abs"] for d in deltas])) if deltas else None,
        "median_label_error": float(np.median([d["label_error"] for d in deltas])) if deltas else None,
        "median_label_error_delta": float(np.median([d["label_error_delta"] for d in deltas])) if deltas else None,
        "median_spacing_ratio_to_reference": float(np.median([d["spacing_ratio_to_reference"] for d in deltas if d["spacing_ratio_to_reference"] is not None])) if deltas else None,
        "label_deltas": deltas,
    }


def summarize_comparisons(rows: list[dict]) -> dict:
    if not rows:
        return {}
    numeric_fields = [
        "present_count",
        "median_ids_delta_abs",
        "median_index_delta_norm",
        "median_size_rank_delta_abs",
        "median_label_error",
        "median_label_error_delta",
        "median_spacing_ratio_to_reference",
    ]
    summary = {
        "conditions": len(rows),
        "all_core_count": int(sum(row["all_core_present"] for row in rows)),
        "all_core_rate": float(sum(row["all_core_present"] for row in rows) / len(rows)),
    }
    for field in numeric_fields:
        values = [row[field] for row in rows if row[field] is not None]
        summary[field] = float(np.median(values)) if values else None

    label_counts = defaultdict(int)
    label_ids_delta = defaultdict(list)
    label_error = defaultdict(list)
    for row in rows:
        for delta in row["label_deltas"]:
            label = delta["label"]
            label_counts[label] += 1
            label_ids_delta[label].append(delta["ids_delta_abs"])
            label_error[label].append(delta["label_error"])

    summary["per_label"] = {
        str(label): {
            "hit_count": int(label_counts[label]),
            "hit_rate": float(label_counts[label] / len(rows)),
            "median_ids_delta_abs": float(np.median(label_ids_delta[label])) if label_ids_delta[label] else None,
            "median_label_error": float(np.median(label_error[label])) if label_error[label] else None,
        }
        for label in label_sort(set(label_counts))
    }
    return summary


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_ints(args.ns)
    phases = parse_floats(args.phases)
    thresholds = parse_floats(args.thresholds)
    orders = parse_ints(args.supertile_orders)

    reference_rows = []
    rows = []
    for n in ns:
        for phase in phases:
            phi = sturmian_sequence(THETA, n, phase)
            reference_by_threshold = {}
            for threshold in thresholds:
                ref = row_with_obs("reference_phi", phi, n, phase, threshold, None, None, args)
                reference_rows.append(ref)
                reference_by_threshold[threshold] = ref

            for order in orders:
                lengths = supertile_lengths(n, order)
                aligned_chunks = chunks_from_lengths(phi, lengths)
                for trial in range(args.trials):
                    variants = {
                        "supertile_shuffle": shuffle_chunks(aligned_chunks, rng),
                        "same_length_contiguous_shuffle": misaligned_same_lengths(phi, lengths, rng),
                        "same_count_internal_shuffle": internal_count_shuffle(aligned_chunks, rng),
                    }
                    for mode, seq in variants.items():
                        for threshold in thresholds:
                            row = row_with_obs(mode, seq, n, phase, threshold, trial, order, args)
                            rows.append(row)

    reference_core = set(summarize_sets(reference_rows)["core_labels_all_conditions"])
    high_core = set(REFERENCE_HIGH) & reference_core
    low_core = set(REFERENCE_LOW) & reference_core

    references = {
        (row["N"], row["phase"], row["threshold"]): row
        for row in reference_rows
    }
    comparisons = []
    high_comparisons = []
    low_comparisons = []
    for row in rows:
        ref = references[(row["N"], row["phase"], row["threshold"])]
        comparisons.append(compare_to_reference(row, ref, reference_core))
        high_comparisons.append(compare_to_reference(row, ref, high_core))
        low_comparisons.append(compare_to_reference(row, ref, low_core))

    def by_mode(comp_rows: list[dict]) -> dict:
        return {
            mode: summarize_comparisons([row for row in comp_rows if row["mode"] == mode])
            for mode in sorted({row["mode"] for row in comp_rows})
        }

    def by_mode_order(comp_rows: list[dict]) -> dict:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in comp_rows:
            grouped[f"{row['mode']}|order={row['supertile_order']}"].append(row)
        return {key: summarize_comparisons(group) for key, group in sorted(grouped.items())}

    return {
        "experiment": "gap_label_position_error_gate",
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
        "reference_low": label_sort(low_core),
        "reference_high": label_sort(high_core),
        "summary_all_core_by_mode": by_mode(comparisons),
        "summary_high_core_by_mode": by_mode(high_comparisons),
        "summary_low_core_by_mode": by_mode(low_comparisons),
        "summary_high_core_by_mode_order": by_mode_order(high_comparisons),
        "comparisons_all_core": comparisons,
        "comparisons_high_core": high_comparisons,
        "comparisons_low_core": low_comparisons,
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
    parser.add_argument("--seed", type=int, default=202605081947)
    parser.add_argument("--out", default="tools/data/gap_label_position_error_gate_20260508_1947.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        mode: {
            "all_high": f"{data['all_core_count']}/{data['conditions']}",
            "present_count": data["present_count"],
            "median_ids_delta_abs": data["median_ids_delta_abs"],
            "median_index_delta_norm": data["median_index_delta_norm"],
            "median_label_error": data["median_label_error"],
            "median_label_error_delta": data["median_label_error_delta"],
        }
        for mode, data in output["summary_high_core_by_mode"].items()
    }
    print(json.dumps({
        "reference_core_phi": output["reference_core_phi"],
        "reference_high": output["reference_high"],
        "high_core_by_mode": compact,
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
