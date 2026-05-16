#!/usr/bin/env python3
"""
Build the two-axis BOUNDARY matrix requested by the 1532 cycle.

Input is a row-aligned semi-real boundary gate deposit. The operator deliberately
does not use GUE/Poisson source labels: it only reads transfer support and beta
coordinate state from each row's measured gate fields.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def norm_beta(values: list[float]) -> list[float]:
    return [round(float(v), 1) for v in values]


def beta_state(row: dict[str, Any], support_transfer: bool) -> str:
    beta = norm_beta(row.get("ambiguous_beta_one_sided_gated", []))
    if not support_transfer:
        return "fall_no_support"
    if not beta:
        return "support_without_beta_blank"
    if beta == [0.3]:
        return "beta_0_3_exact"
    if 0.3 in beta:
        return "beta_0_3_local_nonunique"
    return "local_beta_other"


def build_matrix(data: dict[str, Any]) -> dict[str, Any]:
    source_rows = data.get("evaluation", {}).get("rows", {})
    if not isinstance(source_rows, dict) or not source_rows:
        raise ValueError("input does not contain evaluation.rows")

    rows = []
    counts = {
        "rows": 0,
        "support_transfer_true": 0,
        "support_transfer_false": 0,
        "raw_beta_exact_0_3": 0,
        "raw_beta_exact_0_3_without_support": 0,
        "beta_coordinate_exact_0_3": 0,
        "beta_coordinate_local_nonunique_0_3": 0,
        "beta_coordinate_other": 0,
        "support_without_beta_blank": 0,
        "fall_no_support": 0,
    }

    for name, row in sorted(source_rows.items()):
        state = row.get("state")
        support_transfer = state in {"transfer_with_blank", "transfer_no_blank"}
        beta = norm_beta(row.get("ambiguous_beta_one_sided_gated", []))
        b_state = beta_state(row, support_transfer)
        beta_coordinate_transfer = support_transfer and b_state == "beta_0_3_exact"

        counts["rows"] += 1
        counts["support_transfer_true" if support_transfer else "support_transfer_false"] += 1
        if beta == [0.3]:
            counts["raw_beta_exact_0_3"] += 1
            if not support_transfer:
                counts["raw_beta_exact_0_3_without_support"] += 1
        if b_state == "beta_0_3_exact":
            counts["beta_coordinate_exact_0_3"] += 1
        elif b_state == "beta_0_3_local_nonunique":
            counts["beta_coordinate_local_nonunique_0_3"] += 1
        elif b_state == "local_beta_other":
            counts["beta_coordinate_other"] += 1
        elif b_state == "support_without_beta_blank":
            counts["support_without_beta_blank"] += 1
        elif b_state == "fall_no_support":
            counts["fall_no_support"] += 1

        rows.append(
            {
                "row": name,
                "support_transfer": support_transfer,
                "beta_coordinate_transfer": beta_coordinate_transfer,
                "beta_state": b_state,
                "raw_beta_exact_0_3": beta == [0.3],
                "ambiguous_beta": beta,
                "one_sided_observables": row.get("coherent_one_sided_observables", []),
                "stable_count_coherent": row.get("stable_count_coherent"),
                "stable_count_illusory": row.get("stable_count_illusory"),
                "endpoint_distance": row.get("endpoint_distance_one_sided_gated"),
                "source_state": state,
                "n_gaps": row.get("n_gaps"),
            }
        )

    counts["support_transfer_ratio"] = counts["support_transfer_true"] / counts["rows"]
    counts["raw_beta_exact_0_3_ratio"] = counts["raw_beta_exact_0_3"] / counts["rows"]
    counts["beta_coordinate_exact_0_3_ratio"] = counts["beta_coordinate_exact_0_3"] / counts["rows"]
    counts["any_beta_blank_on_support"] = (
        counts["beta_coordinate_exact_0_3"]
        + counts["beta_coordinate_local_nonunique_0_3"]
        + counts["beta_coordinate_other"]
    )
    counts["any_beta_blank_on_support_ratio"] = counts["any_beta_blank_on_support"] / counts["rows"]

    return {
        "experiment": "boundary_two_axis_matrix",
        "question": "Separate support_transfer from beta_coordinate_transfer on the 13 semi-real BOUNDARY rows without using GUE/Poisson labels.",
        "source": data.get("experiment"),
        "source_scope": data.get("source_scope"),
        "observables_registry": data.get("observables_registry"),
        "observables_used": [
            "support_transfer",
            "beta_coordinate_transfer",
            "beta_state",
            "ambiguous_beta",
            "stable_count_coherent",
            "stable_count_illusory",
            "endpoint_distance",
        ],
        "label_policy": "GUE/Poisson source labels are not read by this operator.",
        "axis_contract": {
            "raw_beta_exact_0_3": "ambiguous_beta is exactly [0.3], independent of support",
            "beta_coordinate_transfer": "raw_beta_exact_0_3 and support_transfer are both true",
            "edge_case": "raw beta 0.3 without support remains a beta observation, not a transfer coordinate",
        },
        "counts": counts,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tools/data/semireal_boundary_transfer_gate_20260509_1516.json")
    parser.add_argument("--out", default="tools/data/boundary_two_axis_matrix_20260509_1532.json")
    args = parser.parse_args()

    with Path(args.input).open() as f:
        data = json.load(f)

    output = build_matrix(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(output, f, indent=2)

    c = output["counts"]
    print(f"rows={c['rows']}")
    print(f"support_transfer={c['support_transfer_true']}/{c['rows']}")
    print(f"raw_beta_exact_0_3={c['raw_beta_exact_0_3']}/{c['rows']}")
    print(f"raw_beta_exact_0_3_without_support={c['raw_beta_exact_0_3_without_support']}/{c['rows']}")
    print(f"beta_coordinate_exact_0_3={c['beta_coordinate_exact_0_3']}/{c['rows']}")
    print(f"any_beta_blank_on_support={c['any_beta_blank_on_support']}/{c['rows']}")
    print(f"support_without_beta_blank={c['support_without_beta_blank']}/{c['rows']}")
    print(f"fall_no_support={c['fall_no_support']}/{c['rows']}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
