#!/usr/bin/env python3
"""
Targeted audit for the two medium/strong beta-absent BOUNDARY residues.

This does not rebuild the global beta atlas. It tests only the two open rows
from the 13-row taxonomy (`numeri_primi:cycle_3`, `random_matrix:cycle_7`) with
row-local windows and the same canonical observable gate used by the prior
BOUNDARY reports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_short_denominator_extension import gue_spacing_blocks
from exp_semireal_boundary_transfer_gate import row_spacings
from exp_semireal_order_denominator_gate import analyze_sequence, compact, normalize
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


TARGET_ROWS = ("numeri_primi:cycle_3", "random_matrix:cycle_7")
OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())


def windowed(values: np.ndarray, size: int, count: int) -> list[np.ndarray]:
    chunks = []
    for idx in range(count):
        start = idx * size
        end = start + size
        if end <= len(values):
            chunks.append(normalize(values[start:end]))
    return chunks


def support_state(row: dict[str, Any], args: argparse.Namespace) -> str:
    one_sided = len(row.get("coherent_one_sided_observables", []))
    illusory = float(row.get("stable_count_illusory") or 0.0)
    endpoint = float(row.get("endpoint_distance_one_sided_gated") or 0.0)
    beta = row.get("ambiguous_beta_one_sided_gated", [])
    transfers = (
        one_sided >= args.min_one_sided
        and illusory <= args.illusory_residue_max
        and endpoint >= args.endpoint_distance_min
    )
    if not transfers:
        return "support_falls"
    if beta:
        return "beta_chart_recovered"
    return "beta_absent_blank"


def obs_jaccard(left: list[str], right: list[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def build_sequences(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, dict[str, Any]]:
    prime = row_spacings("numeri_primi")
    prime = normalize(prime[: args.prime_gaps])

    gue_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
    random_matrix = gue_spacing_blocks(args.random_matrix_gaps, args.gue_matrix_size, gue_rng)

    return {
        "numeri_primi:cycle_3": {
            "base": prime,
            "domain": "numeri_primi",
            "generator": "dnd_autoricerca.genera_segnale -> prime gap spacings",
            "source_n_gaps": int(len(prime)),
        },
        "random_matrix:cycle_7": {
            "base": random_matrix,
            "domain": "random_matrix",
            "generator": "gue_spacing_blocks",
            "source_n_gaps": int(len(random_matrix)),
        },
    }


def analyze_case(name: str, label: str, base: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict[str, Any]:
    perimeters = {f"{name}/{label}": analyze_sequence(f"{name}/{label}", base, args, rng)}
    row = compact(perimeters)[f"{name}/{label}"]
    return {
        "label": label,
        "n_gaps": row["n_gaps"],
        "one_sided_observables": row["coherent_one_sided_observables"],
        "one_sided_count": len(row["coherent_one_sided_observables"]),
        "endpoint_stable_observables": row["endpoint_stable_observables"],
        "stable_count_coherent": row["stable_count_coherent"],
        "stable_count_illusory": row["stable_count_illusory"],
        "endpoint_distance": row["endpoint_distance_one_sided_gated"],
        "ambiguous_beta": [round(float(x), 1) for x in row["ambiguous_beta_one_sided_gated"]],
        "state": support_state(row, args),
        "z_mean_coherent": row["z_mean_coherent"],
        "z_mean_illusory": row["z_mean_illusory"],
    }


def summarize_row(cases: list[dict[str, Any]]) -> dict[str, Any]:
    window_cases = [case for case in cases if case["label"].startswith("window_")]
    blank_windows = [case for case in window_cases if case["state"] == "beta_absent_blank"]
    beta_windows = [case for case in window_cases if case["state"] == "beta_chart_recovered"]
    fall_windows = [case for case in window_cases if case["state"] == "support_falls"]
    obs_sets = [set(case["one_sided_observables"]) for case in window_cases if case["one_sided_observables"]]
    common_obs = sorted(set.intersection(*obs_sets)) if obs_sets else []
    union_obs = sorted(set.union(*obs_sets)) if obs_sets else []
    return {
        "window_count": len(window_cases),
        "blank_windows": len(blank_windows),
        "beta_recovered_windows": len(beta_windows),
        "support_fall_windows": len(fall_windows),
        "blank_window_rate": len(blank_windows) / len(window_cases) if window_cases else 0.0,
        "common_one_sided_observables": common_obs,
        "union_one_sided_observables": union_obs,
        "endpoint_distance_mean": float(np.mean([case["endpoint_distance"] for case in window_cases])) if window_cases else 0.0,
        "stable_count_coherent_mean": float(np.mean([case["stable_count_coherent"] for case in window_cases])) if window_cases else 0.0,
    }


def verdict(row_summaries: dict[str, dict[str, Any]], full_rows: dict[str, dict[str, Any]]) -> str:
    both_persist = all(summary["blank_window_rate"] == 1.0 for summary in row_summaries.values())
    any_beta = any(summary["beta_recovered_windows"] > 0 for summary in row_summaries.values())
    any_fall = any(summary["support_fall_windows"] > 0 for summary in row_summaries.values())
    jaccard = obs_jaccard(
        full_rows["numeri_primi:cycle_3"]["one_sided_observables"],
        full_rows["random_matrix:cycle_7"]["one_sided_observables"],
    )
    if any_beta or any_fall:
        return "RESIDUAL_ATLAS_ARTIFACT_OR_UNSTABLE"
    if both_persist and jaccard < 0.5:
        return "TWO_DISTINCT_BETA_ABSENT_OPERATORS"
    if both_persist:
        return "SAME_BETA_ABSENT_OPERATOR"
    return "RESIDUAL_AMBIGUOUS"


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    specs = build_sequences(args, rng)
    cases_by_row: dict[str, list[dict[str, Any]]] = {}
    full_rows: dict[str, dict[str, Any]] = {}

    for name, spec in specs.items():
        row_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
        cases = [analyze_case(name, "full", spec["base"], args, row_rng)]
        full_rows[name] = cases[0]
        for idx, chunk in enumerate(windowed(spec["base"], args.window_gaps, args.window_count), start=1):
            cases.append(analyze_case(name, f"window_{idx}", chunk, args, row_rng))
        cases_by_row[name] = cases

    row_summaries = {name: summarize_row(cases) for name, cases in cases_by_row.items()}
    full_signature_jaccard = obs_jaccard(
        full_rows["numeri_primi:cycle_3"]["one_sided_observables"],
        full_rows["random_matrix:cycle_7"]["one_sided_observables"],
    )
    common_window_obs_jaccard = obs_jaccard(
        row_summaries["numeri_primi:cycle_3"]["common_one_sided_observables"],
        row_summaries["random_matrix:cycle_7"]["common_one_sided_observables"],
    )

    output = {
        "experiment": "boundary_residual_beta_absent_audit",
        "question": "Are the two medium/strong beta-absent BOUNDARY residues the same operator, distinct classes, or atlas artifacts?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": [
            *OBS_NAMES,
            "window_state",
            "blank_window_rate",
            "full_signature_jaccard",
            "common_window_obs_jaccard",
        ],
        "params": vars(args),
        "targets": TARGET_ROWS,
        "observable_contract": {
            "claim": "the two residual beta-absent blanks are structural only if beta_absent_blank persists across row-local 1024-gap windows",
            "observable": "window_state plus one-sided observable signature",
            "operator": "canonical order/null gate on target rows only",
            "denominator": "two open BOUNDARY rows; full row plus row-local 1024-gap windows",
            "non_possible": "residual class if a target recovers beta or loses support under row-local windows",
            "not_tested": "global beta grid, V_c, source GUE/Poisson label validity",
        },
        "sequence_sources": {
            name: {key: value for key, value in spec.items() if key != "base"}
            for name, spec in specs.items()
        },
        "row_summaries": row_summaries,
        "full_signature_jaccard": full_signature_jaccard,
        "common_window_obs_jaccard": common_window_obs_jaccard,
        "verdict": verdict(row_summaries, full_rows),
        "cases": cases_by_row,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"targets={TARGET_ROWS}")
    for name, summary in row_summaries.items():
        print(
            f"{name} blank_windows={summary['blank_windows']}/{summary['window_count']} "
            f"beta_recovered={summary['beta_recovered_windows']} falls={summary['support_fall_windows']} "
            f"common_obs={summary['common_one_sided_observables']}"
        )
    print(f"full_signature_jaccard={full_signature_jaccard:.3f}")
    print(f"common_window_obs_jaccard={common_window_obs_jaccard:.3f}")
    print(f"verdict={output['verdict']}")
    print(f"saved {out}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prime-gaps", type=int, default=4096)
    parser.add_argument("--random-matrix-gaps", type=int, default=4096)
    parser.add_argument("--window-gaps", type=int, default=1024)
    parser.add_argument("--window-count", type=int, default=4)
    parser.add_argument("--gue-matrix-size", type=int, default=64)
    parser.add_argument("--n-replicates", type=int, default=12)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.75)
    parser.add_argument("--endpoint-distance-min", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=202605100330)
    parser.add_argument("--out", default="tools/data/boundary_residual_beta_absent_audit_20260510_0330.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
