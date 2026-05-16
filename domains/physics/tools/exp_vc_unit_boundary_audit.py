#!/usr/bin/env python3
"""
Audit the V_c=1 boundary after the fit-ready/model gate.

This tool does not recompute spectra. It reads the model-gate deposit and asks
whether the observed fit-ready curves stay above 1, cross 1 inside the measured
window, or are already below 1. The unit boundary is treated as a structural
cut, not as a fitted attractor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def crossing_n(points: list[list[float]], target: float = 1.0) -> float | None:
    ordered = sorted((float(n), float(v)) for n, v in points)
    for (n0, v0), (n1, v1) in zip(ordered[:-1], ordered[1:]):
        if v0 == target:
            return n0
        if (v0 - target) * (v1 - target) <= 0 and v0 != v1:
            return n0 + (target - v0) * (n1 - n0) / (v1 - v0)
    if ordered and ordered[-1][1] == target:
        return ordered[-1][0]
    return None


def unit_status(points: list[list[float]]) -> str:
    values = [float(point[1]) for point in points]
    if not values:
        return "absent"
    below = [value < 1.0 for value in values]
    above = [value > 1.0 for value in values]
    if all(above):
        return "all_above_unit"
    if all(below):
        return "all_below_unit"
    if above[0] and below[-1]:
        return "crosses_down_inside_window"
    if below[0] and above[-1]:
        return "crosses_up_inside_window"
    return "mixed_inside_window"


def split_class(class_threshold: str) -> str:
    return class_threshold.split(":", 1)[0]


def summarize_row(row: dict[str, Any]) -> dict[str, Any]:
    points = row.get("fit_points", [])
    values = [float(point[1]) for point in points]
    status = unit_status(points)
    return {
        "row_id": f"{row['level']}:{row['class_threshold']}",
        "level": row["level"],
        "generator_class": split_class(row["class_threshold"]),
        "class_threshold": row["class_threshold"],
        "denominator_state": row["denominator_state"],
        "fit_ready_rows": row["fit_ready_rows"],
        "total_rows": row["total_rows"],
        "excluded_rows": row["excluded_rows"],
        "best_model": row.get("best_model"),
        "delta_aicc_to_second": row.get("delta_aicc_to_second"),
        "unit_status": status,
        "unit_crossing_N": crossing_n(points),
        "first_value": values[0] if values else None,
        "last_value": values[-1] if values else None,
        "below_unit_count": sum(1 for value in values if value < 1.0),
        "fit_points": points,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input)
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = [summarize_row(row) for row in data.get("summaries", [])]

    by_status: dict[str, int] = {}
    by_class_status: dict[str, dict[str, int]] = {}
    for row in rows:
        by_status[row["unit_status"]] = by_status.get(row["unit_status"], 0) + 1
        class_index = by_class_status.setdefault(row["generator_class"], {})
        class_index[row["unit_status"]] = class_index.get(row["unit_status"], 0) + 1

    crosses = [row for row in rows if row["unit_status"] == "crosses_down_inside_window"]
    ordered_crosses = sorted(
        crosses,
        key=lambda row: row["unit_crossing_N"] if row["unit_crossing_N"] is not None else 1e18,
    )

    return {
        "experiment": "vc_unit_boundary_audit",
        "input": str(source),
        "contract": {
            "unit_boundary": "V_c = 1",
            "observable": "fit-ready V_c points from vc_fit_model_gate",
            "operator": "classify each admissible row by its observed relation to V_c=1",
            "non_possible": "claiming convergence to 1 from above when an observed fit-ready point is already below 1",
            "not_tested": "new spectra, new N, new candidates, asymptotic limit beyond observed window",
        },
        "counts": {
            "rows": len(rows),
            "by_unit_status": dict(sorted(by_status.items())),
            "by_generator_class_status": {
                klass: dict(sorted(statuses.items()))
                for klass, statuses in sorted(by_class_status.items())
            },
            "rows_below_unit": sum(1 for row in rows if row["below_unit_count"] > 0),
            "crosses_down_inside_window": len(crosses),
        },
        "earliest_crosses": ordered_crosses[:8],
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps({
        "experiment": output["experiment"],
        "counts": output["counts"],
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
