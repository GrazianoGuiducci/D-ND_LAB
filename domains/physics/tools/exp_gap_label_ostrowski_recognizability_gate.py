#!/usr/bin/env python3
"""
Global recognizability gate for the phi high-core gap labels.

Local readers did not separate exact supertile boundaries from misaligned
same-length chunks. This tool tests the next global level: whether selected
gap positions sit closer to chunk boundaries or carry a different Fibonacci /
Zeckendorf numeration signature under true supertile chunks than under
misaligned same-length chunks.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_block_scale_gate import REFERENCE_HIGH, REFERENCE_LOW, label_sort, parse_floats, parse_ints
from exp_gap_label_generator_gate import THETA
from exp_gap_label_set_stability import gap_labels, sturmian_sequence
from exp_gap_label_supertile_tiling_gate import chunks_from_lengths, internal_count_shuffle, supertile_lengths
from exp_gap_label_symbolic_grammar_gate import selected_by_label


def fibonacci_basis(n: int) -> list[int]:
    basis = [1, 2]
    while basis[-1] + basis[-2] <= n:
        basis.append(basis[-1] + basis[-2])
    return basis


def zeckendorf_digits(x: int, basis: list[int]) -> list[int]:
    remaining = int(x)
    digits = []
    for f in reversed(basis):
        if f <= remaining:
            digits.append(1)
            remaining -= f
        else:
            digits.append(0)
    return list(reversed(digits))


def digit_features(x: int, n: int) -> dict:
    basis = fibonacci_basis(max(2, n))
    digits = zeckendorf_digits(x % n, basis)
    weight = sum(digits)
    suffix_zeros = 0
    for d in reversed(digits):
        if d == 0:
            suffix_zeros += 1
        else:
            break
    last_one_index = max((i for i, d in enumerate(digits) if d), default=-1)
    return {
        "zeckendorf_weight": int(weight),
        "zeckendorf_suffix_zeros": int(suffix_zeros),
        "zeckendorf_last_one_index": int(last_one_index),
    }


def shuffled_concat_with_boundaries(chunks: list[np.ndarray], rng: np.random.Generator) -> tuple[np.ndarray, list[int]]:
    order = list(range(len(chunks)))
    rng.shuffle(order)
    ordered = [chunks[i] for i in order]
    boundaries = [0]
    total = 0
    for chunk in ordered:
        total += len(chunk)
        boundaries.append(total)
    return np.concatenate(ordered), boundaries


def internal_shuffle_with_boundaries(chunks: list[np.ndarray], rng: np.random.Generator) -> tuple[np.ndarray, list[int]]:
    seq = internal_count_shuffle(chunks, rng)
    boundaries = [0]
    total = 0
    for chunk in chunks:
        total += len(chunk)
        boundaries.append(total)
    return seq, boundaries


def misaligned_chunks(seq: np.ndarray, lengths: list[int], rng: np.random.Generator) -> list[np.ndarray]:
    offset = int(rng.integers(1, len(seq)))
    return chunks_from_lengths(np.roll(seq, -offset), lengths)


def boundary_distance(center: int, n: int, boundaries: list[int]) -> tuple[int, int]:
    circular = sorted({b % n for b in boundaries})
    best = n
    nearest = 0
    for b in circular:
        d = min((center - b) % n, (b - center) % n)
        if d < best:
            best = d
            nearest = b
    return int(best), int(nearest)


def collect_rows(row: dict, labels: set[int], label_group: str, boundaries: list[int]) -> list[dict]:
    selected = selected_by_label(row)
    output = []
    n = row["N"]
    for label in label_sort(labels & set(selected)):
        item = selected[label]
        center = int(round(item["ids"] * n)) % n
        distance, nearest = boundary_distance(center, n, boundaries)
        local_scale = max(1, min(abs(a - b) for a, b in zip(boundaries[:-1], boundaries[1:]) if abs(a - b) > 0))
        output.append({
            "mode": row["mode"],
            "N": n,
            "phase": row["phase"],
            "threshold": row["threshold"],
            "trial": row.get("trial"),
            "supertile_order": row.get("supertile_order"),
            "label_group": label_group,
            "label": int(label),
            "ids": item["ids"],
            "center": center,
            "nearest_boundary": nearest,
            "boundary_distance": distance,
            "boundary_distance_over_N": float(distance / n),
            "boundary_distance_over_min_chunk": float(distance / local_scale),
            "boundary_hit_le_2": bool(distance <= 2),
            **digit_features(center, n),
        })
    return output


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"rows": 0}
    return {
        "rows": len(rows),
        "boundary_hit_le_2_count": int(sum(r["boundary_hit_le_2"] for r in rows)),
        "boundary_hit_le_2_rate": float(sum(r["boundary_hit_le_2"] for r in rows) / len(rows)),
        "median_boundary_distance": float(np.median([r["boundary_distance"] for r in rows])),
        "median_boundary_distance_over_N": float(np.median([r["boundary_distance_over_N"] for r in rows])),
        "median_boundary_distance_over_min_chunk": float(np.median([r["boundary_distance_over_min_chunk"] for r in rows])),
        "median_zeckendorf_weight": float(np.median([r["zeckendorf_weight"] for r in rows])),
        "median_zeckendorf_suffix_zeros": float(np.median([r["zeckendorf_suffix_zeros"] for r in rows])),
    }


def grouped_summary(rows: list[dict], keys: list[str]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups["|".join(f"{key}={row.get(key)}" for key in keys)].append(row)
    return {key: summarize(group) for key, group in sorted(groups.items())}


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_ints(args.ns)
    phases = parse_floats(args.phases)
    thresholds = parse_floats(args.thresholds)
    orders = parse_ints(args.supertile_orders)
    all_rows = []

    for n in ns:
        for phase in phases:
            phi = sturmian_sequence(THETA, n, phase)
            for order in orders:
                lengths = supertile_lengths(n, order)
                aligned_chunks = chunks_from_lengths(phi, lengths)
                for trial in range(args.trials):
                    variants = {}
                    variants["supertile_shuffle"] = shuffled_concat_with_boundaries(aligned_chunks, rng)
                    variants["same_length_contiguous_shuffle"] = shuffled_concat_with_boundaries(misaligned_chunks(phi, lengths, rng), rng)
                    variants["same_count_internal_shuffle"] = internal_shuffle_with_boundaries(aligned_chunks, rng)
                    for mode, (seq, boundaries) in variants.items():
                        for threshold in thresholds:
                            row = {
                                "mode": mode,
                                "N": n,
                                "phase": phase,
                                "threshold": threshold,
                                "trial": trial,
                                "supertile_order": order,
                                **gap_labels(seq, THETA, threshold, args.max_label, args.top_k),
                            }
                            all_rows.extend(collect_rows(row, set(REFERENCE_HIGH), "high", boundaries))
                            all_rows.extend(collect_rows(row, set(REFERENCE_LOW), "low", boundaries))

    return {
        "experiment": "gap_label_ostrowski_recognizability_gate",
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
        "reference_high": label_sort(REFERENCE_HIGH),
        "reference_low": label_sort(REFERENCE_LOW),
        "summary_by_mode_group": grouped_summary(all_rows, ["mode", "label_group"]),
        "summary_by_mode_order_group": grouped_summary(all_rows, ["mode", "supertile_order", "label_group"]),
        "summary_by_label": grouped_summary(all_rows, ["mode", "label_group", "label"]),
        "rows": all_rows,
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
    parser.add_argument("--seed", type=int, default=202605082013)
    parser.add_argument("--out", default="tools/data/gap_label_ostrowski_recognizability_gate_20260508_2013.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        key: {
            "rows": data["rows"],
            "hit_le_2": f"{data.get('boundary_hit_le_2_count')}/{data['rows']}",
            "median_dist": data["median_boundary_distance"],
            "median_dist_over_min_chunk": data["median_boundary_distance_over_min_chunk"],
            "median_z_weight": data["median_zeckendorf_weight"],
            "median_suffix_zeros": data["median_zeckendorf_suffix_zeros"],
        }
        for key, data in output["summary_by_mode_group"].items()
    }
    print(json.dumps({"summary_by_mode_group": compact, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
