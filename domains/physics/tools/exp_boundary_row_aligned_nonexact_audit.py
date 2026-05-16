#!/usr/bin/env python3
"""
Audit BOUNDARY rows where support transfers but beta 0.3 is not exact.

The operator is row-aligned with the 1532 two-axis matrix and deliberately
does not read GUE/Poisson labels as decision fields. It only uses support,
beta-state, denominator telemetry, shuffle telemetry, and measured gate
strength.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


NONEXACT_STATES = {
    "beta_0_3_local_nonunique",
    "local_beta_other",
    "support_without_beta_blank",
}


def row_key(domain: str, cycle: int) -> str:
    return f"{domain}:cycle_{cycle}"


def build_prescan_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in data.get("rows", []):
        key = row_key(row["domain"], row["cycle"])
        observable = row.get("observable", {})
        null = row.get("null_surrogate", {})
        index[key] = {
            "denominator_state": row.get("denominator_state"),
            "excluded_mass": row.get("excluded_mass"),
            "observable_name": observable.get("name"),
            "observable_value": observable.get("value"),
            "n_points": observable.get("n_points"),
            "null_name": null.get("name"),
            "shuffle_z_score": null.get("z_score"),
            "shuffle_class_changes": null.get("class_changes"),
            "domain_window": row.get("domain_window"),
        }
    return index


def beta_span(beta: list[float]) -> float:
    if len(beta) < 2:
        return 0.0
    return max(beta) - min(beta)


def support_tier(row: dict[str, Any]) -> str:
    n_obs = len(row.get("one_sided_observables", []))
    endpoint = float(row.get("endpoint_distance") or 0.0)
    stable = float(row.get("stable_count_coherent") or 0.0)
    if n_obs >= 4 and endpoint >= 3.5 and stable >= 4.0:
        return "strong_multi_observable"
    if n_obs >= 3 and endpoint >= 3.0 and stable >= 3.0:
        return "medium_multi_observable"
    return "thin_observable_support"


def coordinate_failure(row: dict[str, Any]) -> str:
    state = row["beta_state"]
    beta = row.get("ambiguous_beta", [])
    tier = support_tier(row)
    if state == "beta_0_3_local_nonunique":
        if len(beta) >= 5:
            return "beta_grid_saturation"
        return "adjacent_beta_interval"
    if state == "local_beta_other":
        return "coordinate_shifted"
    if state == "support_without_beta_blank":
        if tier == "thin_observable_support":
            return "blank_thin_support"
        return "blank_despite_multi_observable_support"
    return "not_in_scope"


def build_audit(two_axis: dict[str, Any], prescan: dict[str, Any]) -> dict[str, Any]:
    prescan_index = build_prescan_index(prescan)
    exact_rows = [
        row for row in two_axis.get("rows", [])
        if row.get("support_transfer") and row.get("beta_coordinate_transfer")
    ]
    nonexact_rows = [
        row for row in two_axis.get("rows", [])
        if row.get("support_transfer") and row.get("beta_state") in NONEXACT_STATES
    ]
    fall_rows = [
        row for row in two_axis.get("rows", [])
        if not row.get("support_transfer")
    ]

    rows = []
    counts: dict[str, int] = {
        "total_rows": len(two_axis.get("rows", [])),
        "support_transfer_rows": len(exact_rows) + len(nonexact_rows),
        "beta_exact_rows": len(exact_rows),
        "support_nonexact_rows": len(nonexact_rows),
        "fall_rows": len(fall_rows),
    }
    by_state: dict[str, int] = {}
    by_failure: dict[str, int] = {}
    by_tier: dict[str, int] = {}

    for row in nonexact_rows:
        key = row["row"]
        beta = row.get("ambiguous_beta", [])
        failure = coordinate_failure(row)
        tier = support_tier(row)
        by_state[row["beta_state"]] = by_state.get(row["beta_state"], 0) + 1
        by_failure[failure] = by_failure.get(failure, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        rows.append({
            "row": key,
            "beta_state": row["beta_state"],
            "coordinate_failure": failure,
            "support_tier": tier,
            "ambiguous_beta": beta,
            "beta_cardinality": len(beta),
            "beta_span": round(beta_span(beta), 10),
            "one_sided_count": len(row.get("one_sided_observables", [])),
            "one_sided_observables": row.get("one_sided_observables", []),
            "stable_count_coherent": row.get("stable_count_coherent"),
            "stable_count_illusory": row.get("stable_count_illusory"),
            "endpoint_distance": row.get("endpoint_distance"),
            "n_gaps": row.get("n_gaps"),
            "prescan": prescan_index.get(key, {}),
        })

    exact_endpoint = [float(row.get("endpoint_distance") or 0.0) for row in exact_rows]
    nonexact_endpoint = [float(row.get("endpoint_distance") or 0.0) for row in nonexact_rows]
    exact_obs = [len(row.get("one_sided_observables", [])) for row in exact_rows]
    nonexact_obs = [len(row.get("one_sided_observables", [])) for row in nonexact_rows]

    counts.update({
        f"state_{key}": value for key, value in sorted(by_state.items())
    })
    counts.update({
        f"failure_{key}": value for key, value in sorted(by_failure.items())
    })
    counts.update({
        f"tier_{key}": value for key, value in sorted(by_tier.items())
    })

    mismatch = counts["support_nonexact_rows"] != 6

    return {
        "experiment": "boundary_row_aligned_nonexact_audit",
        "question": "Which measured condition separates beta local non-unique, beta local other, and support-without-beta rows after the beta 0.3 universal coordinate fails?",
        "source_matrix": two_axis.get("experiment"),
        "source_scope": two_axis.get("source_scope"),
        "prescan_source": "boundary_denominator_prescan_full_20260509_1500",
        "observables_registry": two_axis.get("observables_registry"),
        "observables_used": [
            "beta_state",
            "coordinate_failure",
            "support_tier",
            "beta_cardinality",
            "beta_span",
            "one_sided_count",
            "stable_count_coherent",
            "stable_count_illusory",
            "endpoint_distance",
            "denominator_state",
            "excluded_mass",
            "shuffle_z_score",
        ],
        "label_policy": "Does not use source_domain_type or GUE/Poisson label as an operator.",
        "direction_check": {
            "expected_nonexact_rows_from_field": 6,
            "measured_support_nonexact_rows": counts["support_nonexact_rows"],
            "mismatch_is_result": mismatch,
        },
        "counts": counts,
        "comparative_means": {
            "exact_endpoint_distance_mean": mean(exact_endpoint) if exact_endpoint else None,
            "nonexact_endpoint_distance_mean": mean(nonexact_endpoint) if nonexact_endpoint else None,
            "exact_one_sided_count_mean": mean(exact_obs) if exact_obs else None,
            "nonexact_one_sided_count_mean": mean(nonexact_obs) if nonexact_obs else None,
        },
        "rows": rows,
        "falls": [
            {
                "row": row["row"],
                "raw_beta_exact_0_3": row.get("raw_beta_exact_0_3"),
                "ambiguous_beta": row.get("ambiguous_beta", []),
                "one_sided_count": len(row.get("one_sided_observables", [])),
                "stable_count_illusory": row.get("stable_count_illusory"),
                "endpoint_distance": row.get("endpoint_distance"),
            }
            for row in fall_rows
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="tools/data/boundary_two_axis_matrix_20260509_1532.json")
    parser.add_argument("--prescan", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--out", default="tools/data/boundary_row_aligned_nonexact_audit_20260509_1538.json")
    args = parser.parse_args()

    with Path(args.matrix).open() as f:
        two_axis = json.load(f)
    with Path(args.prescan).open() as f:
        prescan = json.load(f)

    output = build_audit(two_axis, prescan)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(output, f, indent=2)

    c = output["counts"]
    print(f"total_rows={c['total_rows']}")
    print(f"support_transfer_rows={c['support_transfer_rows']}")
    print(f"beta_exact_rows={c['beta_exact_rows']}")
    print(f"support_nonexact_rows={c['support_nonexact_rows']}")
    print(f"fall_rows={c['fall_rows']}")
    print(f"direction_expected_nonexact=6 measured={c['support_nonexact_rows']}")
    for key, value in sorted(c.items()):
        if key.startswith("state_") or key.startswith("failure_") or key.startswith("tier_"):
            print(f"{key}={value}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
