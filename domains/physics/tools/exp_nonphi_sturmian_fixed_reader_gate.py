#!/usr/bin/env python3
"""
Non-phi Sturmian gate with fixed phi reader.

The preceding boundary readers did not identify the exact supertile boundary.
This tool contracts the claim to the carrier found by earlier cycles: internal
order plus Fibonacci-like scale. It keeps the label reader fixed at theta=1/phi
and changes the Sturmian generator slope. A native-reader control is included
to distinguish "non-phi has no structure" from "non-phi does not carry the
phi label taxonomy".
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_block_scale_gate import REFERENCE_HIGH, REFERENCE_LOW, label_sort, parse_floats, parse_ints
from exp_gap_label_generator_gate import THETA
from exp_gap_label_set_stability import BRONZE, PHI, SILVER, gap_labels, jaccard, sturmian_sequence, summarize_sets


PHI_CORE = set(REFERENCE_LOW) | set(REFERENCE_HIGH)


def plastic_number() -> float:
    roots = np.roots([1.0, 0.0, -1.0, -1.0])
    real_roots = [float(root.real) for root in roots if abs(root.imag) < 1e-10 and root.real > 1]
    return real_roots[0]


def domain_thetas() -> dict[str, float]:
    plastic = plastic_number()
    return {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
        "plastic": 1 / plastic,
    }


def hit_rate(rows: list[dict], labels: set[int]) -> tuple[int, int, float]:
    denominator = len(rows)
    if denominator == 0:
        return 0, 0, 0.0
    hits = sum(labels <= set(row["label_set"]) for row in rows if row["n_selected"] > 0)
    return int(hits), int(denominator), float(hits / denominator)


def overlap_values(rows: list[dict], labels: set[int]) -> list[float]:
    values = []
    for row in rows:
        if row["n_selected"] <= 0:
            continue
        values.append(jaccard(set(row["label_set"]), labels))
    return values


def label_counter(rows: list[dict]) -> Counter:
    counter: Counter = Counter()
    for row in rows:
        counter.update(set(row["label_set"]))
    return counter


def summarize_group(rows: list[dict]) -> dict:
    base = summarize_sets(rows)
    if not base:
        return {"conditions": 0}
    high_hits, high_total, high_rate = hit_rate(rows, set(REFERENCE_HIGH))
    low_hits, low_total, low_rate = hit_rate(rows, set(REFERENCE_LOW))
    core_hits, core_total, core_rate = hit_rate(rows, PHI_CORE)
    high_overlap = overlap_values(rows, set(REFERENCE_HIGH))
    low_overlap = overlap_values(rows, set(REFERENCE_LOW))
    core_overlap = overlap_values(rows, PHI_CORE)
    counter = label_counter(rows)
    n_rows = len(rows)
    return {
        **base,
        "phi_low_core_hits": low_hits,
        "phi_low_core_total": low_total,
        "phi_low_core_rate": low_rate,
        "phi_high_core_hits": high_hits,
        "phi_high_core_total": high_total,
        "phi_high_core_rate": high_rate,
        "phi_full_core_hits": core_hits,
        "phi_full_core_total": core_total,
        "phi_full_core_rate": core_rate,
        "median_overlap_phi_low": float(np.median(low_overlap)) if low_overlap else None,
        "median_overlap_phi_high": float(np.median(high_overlap)) if high_overlap else None,
        "median_overlap_phi_full": float(np.median(core_overlap)) if core_overlap else None,
        "phi_core_frequency": {
            str(label): int(counter[label])
            for label in label_sort(PHI_CORE)
        },
        "phi_core_frequency_rate": {
            str(label): float(counter[label] / n_rows) if n_rows else 0.0
            for label in label_sort(PHI_CORE)
        },
    }


def grouped_summary(rows: list[dict], keys: list[str]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups["|".join(f"{key}={row[key]}" for key in keys)].append(row)
    return {key: summarize_group(group) for key, group in sorted(groups.items())}


def run(args: argparse.Namespace) -> dict:
    ns = parse_ints(args.ns)
    phases = parse_floats(args.phases)
    thresholds = parse_floats(args.thresholds)
    domains = domain_thetas()
    rows = []

    for n in ns:
        for phase in phases:
            for threshold in thresholds:
                for generator, generator_theta in domains.items():
                    seq = sturmian_sequence(generator_theta, n, phase)
                    readers = {
                        "fixed_phi": THETA,
                        "native": generator_theta,
                    }
                    for reader, reader_theta in readers.items():
                        obs = gap_labels(seq, reader_theta, threshold, args.max_label, args.top_k)
                        rows.append({
                            "generator": generator,
                            "reader": reader,
                            "N": n,
                            "phase": phase,
                            "threshold": threshold,
                            "generator_theta": float(generator_theta),
                            "reader_theta": float(reader_theta),
                            **obs,
                        })

    return {
        "experiment": "nonphi_sturmian_fixed_reader_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "top_k": args.top_k,
            "max_label": args.max_label,
        },
        "phi_core": label_sort(PHI_CORE),
        "phi_low_core": label_sort(set(REFERENCE_LOW)),
        "phi_high_core": label_sort(set(REFERENCE_HIGH)),
        "summary_by_generator_reader": grouped_summary(rows, ["generator", "reader"]),
        "summary_by_generator_reader_threshold": grouped_summary(rows, ["generator", "reader", "threshold"]),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="233,377,500,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="1.75,2.0,2.25")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--out", default="tools/data/nonphi_sturmian_fixed_reader_gate_20260508_2019.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {}
    for key, value in output["summary_by_generator_reader"].items():
        compact[key] = {
            "conditions": value["conditions"],
            "core_labels_all_conditions": value["core_labels_all_conditions"],
            "stable_labels_75pct": value["stable_labels_75pct"],
            "phi_low_core_rate": value["phi_low_core_rate"],
            "phi_high_core_rate": value["phi_high_core_rate"],
            "phi_full_core_rate": value["phi_full_core_rate"],
            "median_overlap_phi_full": value["median_overlap_phi_full"],
            "median_label_error": value["median_label_error"],
        }
    print(json.dumps({
        "phi_core": output["phi_core"],
        "summary": compact,
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
