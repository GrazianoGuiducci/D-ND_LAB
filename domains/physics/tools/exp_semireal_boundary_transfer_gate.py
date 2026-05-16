#!/usr/bin/env python3
"""
exp_semireal_boundary_transfer_gate.py

Move the BOUNDARY transfer matrix from controlled synthetic perimeters to the
13 semi-real rows of the base BOUNDARY perimeter.

The coherent endpoint is the domain-native spacing order reconstructed from
dnd_autoricerca. The illusory endpoint is a marginal-preserving permutation.
Intermediate beta layers replace a beta fraction of the coherent row with the
permuted row, preserving the row denominator while destroying order locally.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_blank_null_audit import generate_domain_signal, normalized_spacings
from exp_semireal_order_denominator_gate import analyze_sequence, compact
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())


def load_scope(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        data = json.load(f)
    rows = data.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain a list under rows")
    return rows


def row_spacings(domain: str) -> np.ndarray:
    signal, metadata = generate_domain_signal(domain)
    if domain == "numeri_primi":
        metadata = {**metadata, "is_spacings": True}
    spacings = normalized_spacings(signal, metadata)
    spacings = np.asarray(spacings, dtype=float)
    spacings = spacings[np.isfinite(spacings) & (spacings > 0)]
    if len(spacings) == 0:
        return spacings
    mean = float(np.mean(spacings))
    return spacings / mean if mean > 1e-15 else spacings


def evaluate_matrix(matrix: dict[str, dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    rows = {}
    counts = {
        "transfer_with_blank": 0,
        "transfer_no_blank": 0,
        "fall": 0,
        "errors": 0,
    }
    for name, row in matrix.items():
        if row.get("error"):
            state = "error"
            counts["errors"] += 1
        else:
            one_sided_count = len(row["coherent_one_sided_observables"])
            illusory_residue = float(row["stable_count_illusory"])
            endpoint_distance = float(row["endpoint_distance_one_sided_gated"])
            ambiguous_beta = row["ambiguous_beta_one_sided_gated"]
            has_transfer = (
                one_sided_count >= args.min_one_sided
                and illusory_residue <= args.illusory_residue_max
                and endpoint_distance >= args.endpoint_distance_min
            )
            if not has_transfer:
                state = "fall"
                counts["fall"] += 1
            elif ambiguous_beta:
                state = "transfer_with_blank"
                counts["transfer_with_blank"] += 1
            else:
                state = "transfer_no_blank"
                counts["transfer_no_blank"] += 1
        rows[name] = {"state": state}
        rows[name].update(row)
    return {"counts": counts, "rows": rows}


def run(args: argparse.Namespace) -> dict[str, Any]:
    scope_rows = load_scope(Path(args.scope))
    rng = np.random.default_rng(args.seed)
    perimeters = {}
    build_errors = {}

    for source in scope_rows:
        domain = source["domain"]
        name = source["domain_window"]
        try:
            spacings = row_spacings(domain)
            source_meta = {
                "denominator_state": source.get("denominator_state"),
                "source_transfer": source.get("transfer"),
                "source_excluded_mass": source.get("excluded_mass"),
            }
            if args.include_source_labels:
                source_meta["source_domain_type"] = source.get("source_domain_type")

            if len(spacings) < args.min_gaps:
                build_errors[name] = {
                    "error": f"insufficient gaps: {len(spacings)} < {args.min_gaps}",
                    "n_gaps": int(len(spacings)),
                    "denominator_state": source.get("denominator_state"),
                }
                if args.include_source_labels:
                    build_errors[name]["source_domain_type"] = source.get("source_domain_type")
                continue
            base = spacings[: args.n_gaps] if len(spacings) > args.n_gaps else spacings
            perimeters[name] = analyze_sequence(name, base, args, rng)
            perimeters[name]["source"].update({"domain": domain, **source_meta})
        except Exception as exc:  # noqa: BLE001 - report row-level telemetry.
            build_errors[name] = {
                "error": type(exc).__name__,
                "message": str(exc),
                "denominator_state": source.get("denominator_state"),
            }
            if args.include_source_labels:
                build_errors[name]["source_domain_type"] = source.get("source_domain_type")

    matrix = compact(perimeters)
    for name, err in build_errors.items():
        matrix[name] = err

    evaluation = evaluate_matrix(matrix, args)
    output = {
        "experiment": "semireal_boundary_transfer_gate",
        "question": "Does the BOUNDARY coherent/null/beta gate transfer from synthetic perimeters to the 13 semi-real base rows?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "params": vars(args),
        "source_scope": args.scope,
        "source_summary": {
            "rows": len(scope_rows),
            "label_policy": (
                "source_domain_type included as audit metadata only"
                if args.include_source_labels
                else "source_domain_type omitted; states are label-independent"
            ),
        },
        "matrix": matrix,
        "evaluation": evaluation,
        "perimeters": perimeters,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print(f"source_rows={len(scope_rows)} analyzed={len(perimeters)} errors={len(build_errors)}")
    print("state counts:", output["evaluation"]["counts"])
    print("row state n one_sided stable0 stable1 dist ambiguous")
    for name, row in sorted(output["evaluation"]["rows"].items()):
        if row.get("error"):
            print(f"{name:45s} {row['state']:>20s} {row.get('n_gaps', 0):>5d} ERROR")
            continue
        print(
            f"{name:45s} {row['state']:>20s} "
            f"{row['n_gaps']:>5d} "
            f"{','.join(row['coherent_one_sided_observables']) or '[]':>22s} "
            f"{row['stable_count_coherent']:>7.3f} "
            f"{row['stable_count_illusory']:>7.3f} "
            f"{row['endpoint_distance_one_sided_gated']:>7.3f} "
            f"{row['ambiguous_beta_one_sided_gated']}"
        )
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--n-gaps", type=int, default=4096)
    parser.add_argument("--min-gaps", type=int, default=96)
    parser.add_argument("--n-replicates", type=int, default=12)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.75)
    parser.add_argument("--endpoint-distance-min", type=float, default=1.0)
    parser.add_argument(
        "--include-source-labels",
        action="store_true",
        help="Include GUE/Poisson source labels as audit metadata only. Default omits them from output.",
    )
    parser.add_argument("--seed", type=int, default=202605091516)
    parser.add_argument("--out", default="tools/data/semireal_boundary_transfer_gate_20260509_1516.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
