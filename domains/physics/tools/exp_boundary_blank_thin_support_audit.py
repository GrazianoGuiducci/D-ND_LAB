#!/usr/bin/env python3
"""
Audit the thin support-without-beta blanks against the medium prime blank.

The input is the row-aligned nonexact BOUNDARY audit. The operator stays inside
the support_without_beta_blank subset and asks whether the thin rows separate by
denominator telemetry, null contamination, or an autonomous support signature.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


TARGET_STATE = "support_without_beta_blank"
THIN_FAILURE = "blank_thin_support"


def as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def denominator_bucket(row: dict[str, Any], full_gap_floor: int) -> str:
    n_gaps = int(row.get("n_gaps") or 0)
    if n_gaps >= full_gap_floor:
        return "full_denominator"
    return "short_denominator"


def blank_class(row: dict[str, Any], full_gap_floor: int) -> str:
    thin = row.get("coordinate_failure") == THIN_FAILURE
    short = denominator_bucket(row, full_gap_floor) == "short_denominator"
    contaminated = row.get("prescan", {}).get("denominator_state") == "contaminated"
    class_change = bool(row.get("prescan", {}).get("shuffle_class_changes"))
    if not thin:
        return "medium_blank_control"
    if short and contaminated:
        return "thin_short_contaminated"
    if short and class_change:
        return "thin_short_shuffle_unstable"
    if short:
        return "thin_short_complete"
    return "thin_not_denominator_explained"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "rows": len(rows),
        "n_gaps_mean": mean(as_float(row.get("n_gaps")) for row in rows),
        "one_sided_mean": mean(len(row.get("one_sided_observables", [])) for row in rows),
        "stable_count_coherent_mean": mean(as_float(row.get("stable_count_coherent")) for row in rows),
        "endpoint_distance_mean": mean(as_float(row.get("endpoint_distance")) for row in rows),
        "excluded_mass_mean": mean(as_float(row.get("prescan", {}).get("excluded_mass")) for row in rows),
        "abs_shuffle_z_mean": mean(abs(as_float(row.get("prescan", {}).get("shuffle_z_score"))) for row in rows),
    }


def build_audit(data: dict[str, Any], full_gap_floor: int) -> dict[str, Any]:
    blank_rows = [
        row for row in data.get("rows", [])
        if row.get("beta_state") == TARGET_STATE
    ]
    if not blank_rows:
        raise ValueError("input has no support_without_beta_blank rows")

    rows = []
    counts: dict[str, int] = {
        "support_without_beta_blank_rows": len(blank_rows),
        "thin_rows": 0,
        "medium_control_rows": 0,
        "short_denominator_rows": 0,
        "contaminated_rows": 0,
        "shuffle_class_change_rows": 0,
        "thin_short_rows": 0,
        "thin_contaminated_rows": 0,
        "thin_shuffle_class_change_rows": 0,
        "thin_not_denominator_explained_rows": 0,
    }
    by_class: dict[str, int] = {}

    for row in blank_rows:
        thin = row.get("coordinate_failure") == THIN_FAILURE
        bucket = denominator_bucket(row, full_gap_floor)
        prescan = row.get("prescan", {})
        contaminated = prescan.get("denominator_state") == "contaminated"
        class_change = bool(prescan.get("shuffle_class_changes"))
        cls = blank_class(row, full_gap_floor)

        counts["thin_rows" if thin else "medium_control_rows"] += 1
        if bucket == "short_denominator":
            counts["short_denominator_rows"] += 1
        if contaminated:
            counts["contaminated_rows"] += 1
        if class_change:
            counts["shuffle_class_change_rows"] += 1
        if thin and bucket == "short_denominator":
            counts["thin_short_rows"] += 1
        if thin and contaminated:
            counts["thin_contaminated_rows"] += 1
        if thin and class_change:
            counts["thin_shuffle_class_change_rows"] += 1
        if thin and cls == "thin_not_denominator_explained":
            counts["thin_not_denominator_explained_rows"] += 1
        by_class[cls] = by_class.get(cls, 0) + 1

        rows.append({
            "row": row["row"],
            "blank_class": cls,
            "coordinate_failure": row.get("coordinate_failure"),
            "support_tier": row.get("support_tier"),
            "denominator_bucket": bucket,
            "n_gaps": row.get("n_gaps"),
            "one_sided_count": len(row.get("one_sided_observables", [])),
            "one_sided_observables": row.get("one_sided_observables", []),
            "stable_count_coherent": row.get("stable_count_coherent"),
            "stable_count_illusory": row.get("stable_count_illusory"),
            "endpoint_distance": row.get("endpoint_distance"),
            "denominator_state": prescan.get("denominator_state"),
            "excluded_mass": prescan.get("excluded_mass"),
            "shuffle_z_score": prescan.get("shuffle_z_score"),
            "shuffle_class_changes": class_change,
        })

    thin_rows = [row for row in blank_rows if row.get("coordinate_failure") == THIN_FAILURE]
    medium_rows = [row for row in blank_rows if row.get("coordinate_failure") != THIN_FAILURE]
    all_thin_short = bool(thin_rows) and counts["thin_short_rows"] == len(thin_rows)
    all_thin_contaminated = bool(thin_rows) and counts["thin_contaminated_rows"] == len(thin_rows)
    all_thin_shuffle_unstable = bool(thin_rows) and counts["thin_shuffle_class_change_rows"] == len(thin_rows)

    if all_thin_short and not all_thin_contaminated:
        verdict = "DENOMINATOR_LIMITED_NOT_NULL_CONTAMINATION"
    elif all_thin_contaminated:
        verdict = "CONTAMINATION_LIMITED"
    elif counts["thin_not_denominator_explained_rows"] > 0:
        verdict = "AUTONOMOUS_THIN_BLANK_CANDIDATE"
    else:
        verdict = "AMBIGUOUS"

    counts.update({f"class_{key}": value for key, value in sorted(by_class.items())})

    return {
        "experiment": "boundary_blank_thin_support_audit",
        "question": "Are thin support-without-beta blanks denominator artifacts, null contamination artifacts, or autonomous boundary species?",
        "source": data.get("experiment"),
        "source_scope": data.get("source_scope"),
        "observables_registry": data.get("observables_registry"),
        "observables_used": [
            "blank_class",
            "coordinate_failure",
            "support_tier",
            "denominator_bucket",
            "n_gaps",
            "one_sided_count",
            "stable_count_coherent",
            "stable_count_illusory",
            "endpoint_distance",
            "denominator_state",
            "excluded_mass",
            "shuffle_z_score",
            "shuffle_class_changes",
        ],
        "params": {
            "full_gap_floor": full_gap_floor,
            "target_state": TARGET_STATE,
            "thin_failure": THIN_FAILURE,
        },
        "label_policy": "Does not use source_domain_type or GUE/Poisson label as an operator.",
        "tests": {
            "denominator_artifact": {
                "condition": "all thin rows have n_gaps below full_gap_floor",
                "passes": all_thin_short,
            },
            "contamination_artifact": {
                "condition": "all thin rows are prescan contaminated",
                "passes": all_thin_contaminated,
            },
            "shuffle_instability_artifact": {
                "condition": "all thin rows have shuffle_class_changes=true",
                "passes": all_thin_shuffle_unstable,
            },
            "autonomous_species_counter": {
                "condition": "at least one thin row is not short-denominator explained",
                "passes": counts["thin_not_denominator_explained_rows"] > 0,
            },
        },
        "counts": counts,
        "comparative_means": {
            "thin": summarize(thin_rows),
            "medium_control": summarize(medium_rows),
        },
        "verdict": verdict,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tools/data/boundary_row_aligned_nonexact_audit_20260509_1538.json")
    parser.add_argument("--full-gap-floor", type=int, default=500)
    parser.add_argument("--out", default="tools/data/boundary_blank_thin_support_audit_20260509_1548.json")
    args = parser.parse_args()

    with Path(args.input).open() as f:
        data = json.load(f)

    output = build_audit(data, args.full_gap_floor)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(output, f, indent=2)

    c = output["counts"]
    print(f"support_without_beta_blank_rows={c['support_without_beta_blank_rows']}")
    print(f"thin_rows={c['thin_rows']}")
    print(f"medium_control_rows={c['medium_control_rows']}")
    print(f"thin_short_rows={c['thin_short_rows']}")
    print(f"thin_contaminated_rows={c['thin_contaminated_rows']}")
    print(f"thin_shuffle_class_change_rows={c['thin_shuffle_class_change_rows']}")
    print(f"thin_not_denominator_explained_rows={c['thin_not_denominator_explained_rows']}")
    print(f"verdict={output['verdict']}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
