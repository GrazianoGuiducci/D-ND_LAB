#!/usr/bin/env python3
"""
Provider-neutral audit for the `prime_persistent_blank` residue.

This is the next narrow step after
`exp_boundary_residual_beta_absent_audit.py`: do not reopen the global BOUNDARY
atlas; test whether `numeri_primi:cycle_3` keeps its beta-absent blank through
two prime providers, row-local offsets, and baseline seed shifts, with SR as the
common surviving observable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_short_denominator_extension import gue_spacing_blocks
from exp_boundary_residual_beta_absent_audit import support_state
from exp_semireal_boundary_transfer_gate import row_spacings
from exp_semireal_order_denominator_gate import (
    analyze_sequence,
    compact,
    logistic_return_intervals,
    normalize,
    prime_gap_sequence,
)
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
TARGET_ROW = "numeri_primi:cycle_3"


def offset_windows(values: np.ndarray, offsets: list[int], size: int) -> dict[str, np.ndarray]:
    out = {}
    for offset in offsets:
        end = offset + size
        if end <= len(values):
            out[f"offset_{offset}"] = normalize(values[offset:end])
    return out


def obs_jaccard(left: list[str], right: list[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def analyze_case(name: str, base: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict[str, Any]:
    perimeters = {name: analyze_sequence(name, base, args, rng)}
    row = compact(perimeters)[name]
    one_sided = list(row["coherent_one_sided_observables"])
    return {
        "case": name,
        "n_gaps": row["n_gaps"],
        "state": support_state(row, args),
        "one_sided_observables": one_sided,
        "has_sr": "SR" in one_sided,
        "endpoint_stable_observables": row["endpoint_stable_observables"],
        "stable_count_coherent": row["stable_count_coherent"],
        "stable_count_illusory": row["stable_count_illusory"],
        "endpoint_distance": row["endpoint_distance_one_sided_gated"],
        "ambiguous_beta": [round(float(x), 1) for x in row["ambiguous_beta_one_sided_gated"]],
        "z_mean_coherent": row["z_mean_coherent"],
        "z_mean_illusory": row["z_mean_illusory"],
    }


def summarize_family(cases: list[dict[str, Any]]) -> dict[str, Any]:
    obs_sets = [set(case["one_sided_observables"]) for case in cases if case["one_sided_observables"]]
    common_obs = sorted(set.intersection(*obs_sets)) if obs_sets else []
    union_obs = sorted(set.union(*obs_sets)) if obs_sets else []
    counts: dict[str, int] = {}
    for case in cases:
        counts[case["state"]] = counts.get(case["state"], 0) + 1
    blank_cases = [case for case in cases if case["state"] == "beta_absent_blank"]
    return {
        "case_count": len(cases),
        "state_counts": counts,
        "blank_rate": len(blank_cases) / len(cases) if cases else 0.0,
        "sr_rate": sum(1 for case in cases if case["has_sr"]) / len(cases) if cases else 0.0,
        "common_one_sided_observables": common_obs,
        "union_one_sided_observables": union_obs,
        "endpoint_distance_mean": float(np.mean([case["endpoint_distance"] for case in cases])) if cases else 0.0,
        "stable_count_coherent_mean": float(np.mean([case["stable_count_coherent"] for case in cases])) if cases else 0.0,
    }


def build_prime_cases(args: argparse.Namespace) -> dict[str, np.ndarray]:
    needed = max(args.offsets) + args.window_gaps
    providers = {
        "dnd_autoricerca": normalize(row_spacings("numeri_primi")[:needed]),
        "direct_sieve": normalize(prime_gap_sequence(needed)),
    }
    cases = {}
    for provider, values in providers.items():
        for label, window in offset_windows(values, args.offsets, args.window_gaps).items():
            cases[f"prime/{provider}/{label}"] = window
    return cases


def build_control_cases(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, np.ndarray]:
    cases = {}
    for idx in range(args.control_count):
        seed = int(rng.integers(0, 2**63 - 1))
        local_rng = np.random.default_rng(seed)
        random_matrix = gue_spacing_blocks(args.window_gaps, args.gue_matrix_size, local_rng)
        cases[f"control/random_matrix/seed_{idx}"] = random_matrix

    for idx in range(args.control_count):
        seed = int(rng.integers(0, 2**63 - 1))
        local_rng = np.random.default_rng(seed)
        logistic = logistic_return_intervals(args.window_gaps, local_rng)
        cases[f"control/logistic_return_intervals/seed_{idx}"] = logistic
    return cases


def verdict(prime_summary: dict[str, Any], control_summary: dict[str, Any], args: argparse.Namespace) -> str:
    prime_persists = (
        prime_summary["blank_rate"] == 1.0
        and prime_summary["sr_rate"] >= args.min_prime_sr_rate
        and prime_summary["common_one_sided_observables"] == ["SR"]
    )
    controls_do_not_match = not (
        control_summary["blank_rate"] == 1.0
        and "SR" in control_summary["common_one_sided_observables"]
    )
    if prime_persists and controls_do_not_match:
        return "PRIME_PERSISTENT_BLANK_SR_ISOLATED"
    if prime_persists:
        return "PRIME_PERSISTENT_BUT_CONTROL_COLLISION"
    return "PRIME_PERSISTENCE_NOT_REPLICATED"


def run(args: argparse.Namespace) -> dict[str, Any]:
    root_rng = np.random.default_rng(args.seed)
    prime_specs = build_prime_cases(args)
    control_specs = build_control_cases(args, root_rng)

    prime_cases = [
        analyze_case(name, base, args, np.random.default_rng(root_rng.integers(0, 2**63 - 1)))
        for name, base in prime_specs.items()
    ]
    control_cases = [
        analyze_case(name, base, args, np.random.default_rng(root_rng.integers(0, 2**63 - 1)))
        for name, base in control_specs.items()
    ]

    prime_summary = summarize_family(prime_cases)
    control_summary = summarize_family(control_cases)
    output = {
        "experiment": "prime_persistent_blank_gate",
        "question": "Does numeri_primi:cycle_3 keep a provider-neutral SR beta-absent blank under row-local offset and seed shifts?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": [
            *OBS_NAMES,
            "provider",
            "offset",
            "case_state",
            "blank_rate",
            "sr_rate",
            "prime_control_common_obs_jaccard",
        ],
        "params": vars(args),
        "target_row": TARGET_ROW,
        "observable_contract": {
            "claim": "prime_persistent_blank is isolated only if prime windows remain beta_absent_blank across providers and offsets with SR as the common one-sided observable",
            "observable": "case_state plus common one-sided observable signature focused on SR",
            "operator": "canonical order/null gate on row-local windows; provider and seed shifts only",
            "generator": "prime gaps from dnd_autoricerca row_spacings and direct sieve; controls from GUE random matrix blocks and logistic return intervals",
            "denominator": "8 prime row-local windows (2 providers x 4 offsets) plus 8 cross-domain controls",
            "non_possible": "prime_persistent_blank if any prime window recovers beta/falls, or if controls share a full SR blank signature",
            "not_tested": "global beta atlas, V_c, gap_ratio, source GUE/Poisson labels",
        },
        "prime_summary": prime_summary,
        "control_summary": control_summary,
        "prime_control_common_obs_jaccard": obs_jaccard(
            prime_summary["common_one_sided_observables"],
            control_summary["common_one_sided_observables"],
        ),
        "verdict": verdict(prime_summary, control_summary, args),
        "cases": {
            "prime": prime_cases,
            "controls": control_cases,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"target={TARGET_ROW}")
    print(
        "prime "
        f"blank={prime_summary['state_counts'].get('beta_absent_blank', 0)}/{prime_summary['case_count']} "
        f"sr_rate={prime_summary['sr_rate']:.3f} common={prime_summary['common_one_sided_observables']}"
    )
    print(
        "controls "
        f"blank={control_summary['state_counts'].get('beta_absent_blank', 0)}/{control_summary['case_count']} "
        f"sr_rate={control_summary['sr_rate']:.3f} common={control_summary['common_one_sided_observables']}"
    )
    print(f"prime_control_common_obs_jaccard={output['prime_control_common_obs_jaccard']:.3f}")
    print(f"verdict={output['verdict']}")
    print(f"saved {out}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-gaps", type=int, default=1024)
    parser.add_argument("--offsets", type=int, nargs="+", default=[0, 512, 1024, 1536])
    parser.add_argument("--control-count", type=int, default=4)
    parser.add_argument("--gue-matrix-size", type=int, default=64)
    parser.add_argument("--n-replicates", type=int, default=8)
    parser.add_argument("--n-beta", type=int, default=9)
    parser.add_argument("--n-baseline", type=int, default=16)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.75)
    parser.add_argument("--endpoint-distance-min", type=float, default=1.0)
    parser.add_argument("--min-prime-sr-rate", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=202605110330)
    parser.add_argument("--out", default="tools/data/prime_persistent_blank_gate_20260511_0330.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
