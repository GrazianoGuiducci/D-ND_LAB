#!/usr/bin/env python3
"""
Repair audit for the phi high-core gap-label gate.

This does not rerun the spectral generator. It re-reads a prior row-level
supertile gate output and separates three observables that the report must not
merge: full high-core closure, per-label retention, and stable-label count.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_block_scale_gate import REFERENCE_HIGH, REFERENCE_LOW, label_sort
from exp_gap_label_set_stability import PHI, jaccard


def label_counts(rows: list[dict]) -> tuple[Counter, list[set[int]]]:
    sets = [set(row["label_set"]) for row in rows if row.get("n_selected", 0) > 0]
    return Counter(label for labels in sets for label in labels), sets


def selected_for_label(row: dict, label: int) -> list[dict]:
    return [item for item in row.get("selected", []) if item.get("label") == label]


def summarize(rows: list[dict], reference_high: set[int], reference_low: set[int]) -> dict:
    counts, sets = label_counts(rows)
    total = len(sets)
    core_hits = sum(1 for labels in sets if reference_high <= labels)
    low_hits = sum(1 for labels in sets if reference_low <= labels)
    stable_75 = label_sort({label for label, count in counts.items() if total and count / total >= 0.75})

    per_label = {}
    for label in label_sort(reference_high):
        errors = [
            item["label_error"]
            for row in rows
            for item in selected_for_label(row, label)
        ]
        per_label[str(label)] = {
            "hits": int(counts.get(label, 0)),
            "total": int(total),
            "rate": float(counts.get(label, 0) / total) if total else None,
            "median_label_error": float(np.median(errors)) if errors else None,
            "max_label_error": float(np.max(errors)) if errors else None,
        }

    stable_high = [label for label in stable_75 if label in reference_high]
    return {
        "conditions": int(total),
        "all_high_hits": int(core_hits),
        "all_high_rate": float(core_hits / total) if total else None,
        "all_low_hits": int(low_hits),
        "all_low_rate": float(low_hits / total) if total else None,
        "stable_labels_75pct": stable_75,
        "stable_label_count": int(len(stable_75)),
        "stable_high_labels_75pct": label_sort(stable_high),
        "stable_high_label_count": int(len(stable_high)),
        "per_high_label": per_label,
    }


def summarize_grouped(rows: list[dict], key_names: tuple[str, ...], reference_high: set[int], reference_low: set[int]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = "|".join(f"{name}={row[name]}" for name in key_names)
        grouped[key].append(row)
    return {
        key: summarize(group_rows, reference_high, reference_low)
        for key, group_rows in sorted(grouped.items())
    }


def theoretical_baseline(max_label: int) -> dict:
    labels = [n for n in range(-max_label, max_label + 1) if n != 0]
    theta = 1 / PHI
    return {
        "reader": "Sturmian/Fibonacci gap-labeling group Z + theta Z mod 1",
        "theta": float(theta),
        "max_label": int(max_label),
        "expected_label_group": "{n*theta mod 1 | n in Z, n != 0}",
        "reference_high_in_group": {
            str(label): {
                "in_group": True,
                "ids_fraction": float((label * theta) % 1.0),
            }
            for label in label_sort(REFERENCE_HIGH)
        },
        "baseline_statement": (
            "The labels [3,-4,4,6] are classical Fibonacci/Sturmian gap labels; "
            "the D-ND novelty tested here is not their membership, but their "
            "joint and per-label survival under order/boundary perturbations."
        ),
        "candidate_count_in_reader_window": int(len(labels)),
    }


def run(input_path: Path) -> dict:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    rows = source["rows"]
    reference_high = set(source.get("reference_high", label_sort(REFERENCE_HIGH)))
    reference_low = set(source.get("reference_low", label_sort(REFERENCE_LOW)))

    mode_summary = summarize_grouped(rows, ("mode",), reference_high, reference_low)
    mode_order_summary = summarize_grouped(rows, ("mode", "supertile_order"), reference_high, reference_low)

    source_core = set(source["reference_core_phi"])
    repair = {
        "experiment": "gap_label_repair_audit",
        "source": str(input_path),
        "parameters": source["parameters"],
        "reference_core_phi": label_sort(source_core),
        "reference_low": label_sort(reference_low),
        "reference_high": label_sort(reference_high),
        "observables_separated": [
            "all_high_hits",
            "per_high_label",
            "stable_label_count",
            "stable_high_label_count",
            "label_error",
            "theoretical_gap_labeling_baseline",
        ],
        "theoretical_baseline": theoretical_baseline(source["parameters"]["max_label"]),
        "mode_summary": mode_summary,
        "mode_order_summary": mode_order_summary,
        "core_vs_stable_note": (
            "all_high_hits requires every high label in the same condition; "
            "per_high_label counts survival of each label independently; "
            "stable_high_label_count counts high labels present in at least 75% of conditions."
        ),
    }
    return repair


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tools/data/gap_label_supertile_tiling_gate_20260508_1909.json")
    parser.add_argument("--out", default="tools/data/gap_label_repair_audit_20260508_1915.json")
    args = parser.parse_args()

    output = run(Path(args.input))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        mode_key: {
            "all_high": f"{data['all_high_hits']}/{data['conditions']}",
            "stable_high": data["stable_high_labels_75pct"],
            "stable_high_count": data["stable_high_label_count"],
            "per_high_label": {
                label: f"{v['hits']}/{v['total']}"
                for label, v in data["per_high_label"].items()
            },
        }
        for mode_key, data in output["mode_summary"].items()
    }
    print(json.dumps({"summary": compact, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
