#!/usr/bin/env python3
"""
Build a fit-ready scale table for V_c deposits.

The input is the direction audit JSON. This tool does not recompute spectra.
It separates rows where V_c exists from rows where the event is outside the
crossing contract before any scale curve is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def linear_slope(points: list[list[float]]) -> float | None:
    if len(points) < 2:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return None
    return float(sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom)


def denominator_state(by_n: dict[str, dict]) -> str:
    if not by_n:
        return "absent"
    has_fit_each_n = all(row.get("fit_ready_rows", 0) > 0 for row in by_n.values())
    has_exclusion = any(row.get("excluded_rows", 0) > 0 for row in by_n.values())
    if has_fit_each_n and not has_exclusion:
        return "complete"
    if has_fit_each_n and has_exclusion:
        return "contaminated"
    if any(row.get("fit_ready_rows", 0) > 0 for row in by_n.values()):
        return "broken"
    return "absent"


def summarize_entry(level: str, key: str, entry: dict) -> dict:
    by_n = entry.get("by_N", {})
    fit_points = entry.get("fit_points", [])
    total_rows = sum(int(row.get("rows", 0)) for row in by_n.values())
    total_fit = sum(int(row.get("fit_ready_rows", 0)) for row in by_n.values())
    total_excluded = sum(int(row.get("excluded_rows", 0)) for row in by_n.values())
    state = denominator_state(by_n)
    values = [float(point[1]) for point in fit_points]

    return {
        "level": level,
        "class_threshold": key,
        "denominator_state": state,
        "total_rows": total_rows,
        "fit_ready_rows": total_fit,
        "excluded_rows": total_excluded,
        "excluded_events": entry.get("excluded_events", {}),
        "event_counts": entry.get("event_counts", {}),
        "fit_points": fit_points,
        "fit_point_count": len(fit_points),
        "vc_first": values[0] if values else None,
        "vc_last": values[-1] if values else None,
        "delta_first_last": float(values[-1] - values[0]) if len(values) >= 2 else None,
        "slope_per_N": linear_slope(fit_points),
        "by_N": by_n,
    }


def build_table(data: dict, level: str) -> list[dict]:
    fit_ready = data.get(level, {}).get("fit_ready", {})
    table = fit_ready.get("by_class_threshold", {})
    return [summarize_entry(level, key, entry) for key, entry in sorted(table.items())]


def run(args: argparse.Namespace) -> dict:
    source = Path(args.input)
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = build_table(data, "per_mode_best") + build_table(data, "accepted_candidates")

    by_state: dict[str, list[str]] = {}
    for row in rows:
        by_state.setdefault(row["denominator_state"], []).append(
            f"{row['level']}:{row['class_threshold']}"
        )

    return {
        "experiment": "vc_fit_ready_scale_table",
        "input": str(source),
        "contract": {
            "vc_defined": "event in {internal_cross, internal_multi}",
            "fit_ready": "vc_defined and vc_interp is not null",
            "complete": "each N has fit-ready rows and zero excluded rows",
            "contaminated": "each N has fit-ready rows and at least one excluded row",
            "broken": "at least one N has no fit-ready row",
            "absent": "no fit-ready rows in the table",
        },
        "state_index": {key: sorted(value) for key, value in sorted(by_state.items())},
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

    compact = {
        "experiment": output["experiment"],
        "input": output["input"],
        "state_index": output["state_index"],
        "out": str(out),
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
