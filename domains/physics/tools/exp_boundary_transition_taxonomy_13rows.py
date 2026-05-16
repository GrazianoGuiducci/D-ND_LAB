#!/usr/bin/env python3
"""
Scale the post-extension BOUNDARY transition taxonomy to all 13 rows.

This script does not regenerate expensive signals. It composes the row-aligned
two-axis matrix, the non-exact audit, the denominator prescan, and the 15:56
source-denominator extension. The operator asks whether the short-denominator
transition taxonomy leaves any autonomous thin blank when read against the
full 13-row perimeter.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    with Path(path).open() as f:
        return json.load(f)


def index_rows(rows: list[dict[str, Any]], key: str = "row") -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in rows}


def prescan_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["domain_window"]: row for row in data.get("rows", [])}


def support_tier(one_sided_count: int, endpoint: float, stable: float) -> str:
    if one_sided_count >= 4 and endpoint >= 3.5 and stable >= 4.0:
        return "strong_multi_observable"
    if one_sided_count >= 3 and endpoint >= 3.0 and stable >= 3.0:
        return "medium_multi_observable"
    return "thin_observable_support"


def row_metrics(row: dict[str, Any], extension: dict[str, Any] | None = None) -> dict[str, Any]:
    if extension:
        one_sided_count = int(extension.get("after_one_sided") or 0)
        endpoint = float(extension.get("after_endpoint_distance") or 0.0)
        stable = float(extension.get("after_stable_count_coherent") or 0.0)
        beta = extension.get("after_beta", [])
        tier = extension.get("after_support_tier") or support_tier(one_sided_count, endpoint, stable)
        n_gaps = extension.get("after_n_gaps")
        return {
            "n_gaps_after": n_gaps,
            "one_sided_after": one_sided_count,
            "endpoint_after": endpoint,
            "stable_count_coherent_after": stable,
            "beta_after": beta,
            "support_tier_after": tier,
        }

    beta = row.get("ambiguous_beta", [])
    one_sided_count = len(row.get("one_sided_observables", []))
    endpoint = float(row.get("endpoint_distance") or 0.0)
    stable = float(row.get("stable_count_coherent") or 0.0)
    return {
        "n_gaps_after": row.get("n_gaps"),
        "one_sided_after": one_sided_count,
        "endpoint_after": endpoint,
        "stable_count_coherent_after": stable,
        "beta_after": beta,
        "support_tier_after": support_tier(one_sided_count, endpoint, stable),
    }


def transition_class(row: dict[str, Any], extension: dict[str, Any] | None) -> str:
    if extension:
        return extension["extension_state"]
    if not row.get("support_transfer"):
        return "fall_no_support"
    beta_state = row.get("beta_state")
    if beta_state == "beta_0_3_exact":
        return "beta_0_3_exact"
    if beta_state == "beta_0_3_local_nonunique":
        return "beta_0_3_local_nonunique"
    if beta_state == "local_beta_other":
        return "local_beta_other"
    if beta_state == "support_without_beta_blank":
        metrics = row_metrics(row)
        tier = metrics["support_tier_after"]
        if tier == "thin_observable_support":
            return "thin_persists"
        return "blank_medium_or_strong_beta_absent"
    return "unclassified"


def build(args: argparse.Namespace) -> dict[str, Any]:
    two_axis = load_json(args.two_axis)
    row_audit = load_json(args.row_audit)
    extension = load_json(args.extension)
    prescan = load_json(args.prescan)

    two_rows = index_rows(two_axis.get("rows", []))
    audit_rows = index_rows(row_audit.get("rows", []))
    extension_rows = index_rows(extension.get("transitions", []))
    prescan_rows = prescan_index(prescan)

    rows: list[dict[str, Any]] = []
    class_counts: dict[str, int] = {}
    support_blank_full_rows: list[str] = []
    thin_persist_rows: list[str] = []
    endpoint_by_class: dict[str, list[float]] = {}

    for name in sorted(two_rows):
        source = two_rows[name]
        ext = extension_rows.get(name)
        metrics = row_metrics(source, ext)
        cls = transition_class(source, ext)
        class_counts[cls] = class_counts.get(cls, 0) + 1
        endpoint_by_class.setdefault(cls, []).append(metrics["endpoint_after"])
        if cls == "thin_persists":
            thin_persist_rows.append(name)
        if cls in {"blank_medium_or_strong_beta_absent", "support_thickens_beta_blank"}:
            support_blank_full_rows.append(name)

        audit = audit_rows.get(name, {})
        pres = prescan_rows.get(name, {})
        rows.append({
            "row": name,
            "source_beta_state": source.get("beta_state"),
            "source_support_transfer": source.get("support_transfer"),
            "source_beta_coordinate_transfer": source.get("beta_coordinate_transfer"),
            "source_coordinate_failure": audit.get("coordinate_failure"),
            "transition_class": cls,
            "extension_applied": ext is not None,
            "n_gaps_before": source.get("n_gaps"),
            **metrics,
            "denominator_state": pres.get("denominator_state"),
            "excluded_mass": pres.get("excluded_mass"),
            "source_domain_type_audit_only": pres.get("source_domain_type"),
        })

    total = len(rows)
    support_transfer_after = sum(
        1 for row in rows
        if row["transition_class"] not in {"fall_no_support", "support_falls_after_extension"}
    )
    beta_chart_after = sum(1 for row in rows if row["beta_after"])
    exact_beta_after = sum(1 for row in rows if row["beta_after"] == [0.3])

    verdict = "TAXONOMY_SCALES_THIN_DISSOLVED"
    if thin_persist_rows:
        verdict = "TAXONOMY_FAILS_THIN_PERSISTS"

    return {
        "experiment": "boundary_transition_taxonomy_13rows",
        "question": "Does the post-extension transition taxonomy scale to all 13 BOUNDARY rows without leaving autonomous thin blanks?",
        "observables_registry": two_axis.get("observables_registry"),
        "observables_used": [
            "transition_class",
            "source_beta_state",
            "extension_state",
            "support_tier_after",
            "one_sided_after",
            "endpoint_after",
            "stable_count_coherent_after",
            "beta_after",
            "denominator_state",
            "excluded_mass",
        ],
        "sources": {
            "two_axis": args.two_axis,
            "row_audit": args.row_audit,
            "extension": args.extension,
            "prescan": args.prescan,
        },
        "observable_contract": {
            "claim": "the short-denominator transition taxonomy scales if no 13-row member remains thin_persists after extension composition",
            "observable": "row-aligned transition_class across 13 rows",
            "operator": "composition of measured deposits, no regeneration",
            "denominator": "13 semi-real BOUNDARY rows",
            "non_possible": "autonomous blank_thin_support if any row remains thin_persists",
            "not_tested": "new beta grid, new null surrogates, V_c fit, source GUE/Poisson label validity",
        },
        "label_policy": "source_domain_type is audit metadata only and is not used in transition_class.",
        "counts": {
            "total_rows": total,
            "support_transfer_after": support_transfer_after,
            "fall_after": total - support_transfer_after,
            "beta_chart_after_any": beta_chart_after,
            "beta_chart_after_exact_0_3": exact_beta_after,
            "thin_persist_rows": len(thin_persist_rows),
            "blank_medium_or_strong_beta_absent_rows": len(support_blank_full_rows),
            **{f"class_{key}": value for key, value in sorted(class_counts.items())},
        },
        "class_endpoint_means": {
            key: mean(values) for key, values in sorted(endpoint_by_class.items())
        },
        "thin_persist_rows": thin_persist_rows,
        "open_blank_rows": support_blank_full_rows,
        "verdict": verdict,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--two-axis", default="tools/data/boundary_two_axis_matrix_20260509_1532.json")
    parser.add_argument("--row-audit", default="tools/data/boundary_row_aligned_nonexact_audit_20260509_1538.json")
    parser.add_argument("--extension", default="tools/data/boundary_short_denominator_extension_20260509_1556.json")
    parser.add_argument("--prescan", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--out", default="tools/data/boundary_transition_taxonomy_13rows_20260509_1839.json")
    args = parser.parse_args()

    output = build(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(output, f, indent=2)

    c = output["counts"]
    print(f"rows={c['total_rows']}")
    print(f"support_transfer_after={c['support_transfer_after']}/{c['total_rows']}")
    print(f"fall_after={c['fall_after']}/{c['total_rows']}")
    print(f"beta_chart_after_any={c['beta_chart_after_any']}/{c['total_rows']}")
    print(f"thin_persist_rows={c['thin_persist_rows']}")
    print(f"open_blank_rows={output['open_blank_rows']}")
    for key, value in sorted(c.items()):
        if key.startswith("class_"):
            print(f"{key}={value}")
    print(f"verdict={output['verdict']}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
