#!/usr/bin/env python3
"""
Audit `prime_SR_persistent_boundary` after `prime_persistent_blank` fell.

The claim under test is narrower than the previous blank audit: SR must persist
through prime providers and offsets, while non-prime controls should not share
the same one-sided SR support under the same gate.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_short_denominator_extension import gue_spacing_blocks
from exp_boundary_residual_beta_absent_audit import support_state
from exp_prime_persistent_blank_gate import offset_windows, obs_jaccard
from exp_semireal_boundary_transfer_gate import row_spacings
from exp_semireal_order_denominator_gate import (
    analyze_sequence,
    compact,
    logistic_return_intervals,
    normalize,
    prime_gap_sequence,
    sieve_primes_for_count,
)
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
TARGET_ROW = "numeri_primi:cycle_3"


def sieve_bool(limit: int) -> np.ndarray:
    sieve = np.ones(limit + 1, dtype=bool)
    sieve[:2] = False
    for p in range(2, int(limit**0.5) + 1):
        if sieve[p]:
            sieve[p * p : limit + 1 : p] = False
    return sieve


def composite_gap_sequence(n_gaps: int) -> np.ndarray:
    limit = max(100, int(n_gaps * (math.log(max(n_gaps, 3)) + 8)))
    while True:
        prime_mask = sieve_bool(limit)
        values = np.flatnonzero(~prime_mask)
        values = values[values >= 4]
        if len(values) >= n_gaps + 1:
            return normalize(np.diff(values[: n_gaps + 1]))
        limit *= 2


def mod6_candidate_gap_sequence(n_gaps: int) -> np.ndarray:
    values: list[int] = []
    k = 1
    while len(values) < n_gaps + 1:
        values.append(6 * k - 1)
        values.append(6 * k + 1)
        k += 1
    arr = np.array(sorted(values[: n_gaps + 1]), dtype=float)
    return normalize(np.diff(arr))


def cramer_like_gap_sequence(n_gaps: int, rng: np.random.Generator) -> np.ndarray:
    events = [2]
    n = 3
    while len(events) < n_gaps + 1:
        p = min(0.95, 1.0 / max(math.log(n), 1.0))
        if rng.random() < p:
            events.append(n)
        n += 1
        if n > 50_000_000:
            raise RuntimeError("cramer_like_gap_sequence did not produce enough events")
    return normalize(np.diff(np.array(events, dtype=float)))


def prime_cases(args: argparse.Namespace) -> dict[str, np.ndarray]:
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


def control_cases(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, np.ndarray]:
    needed = max(args.offsets) + args.window_gaps
    base_controls = {
        "composite_gaps": composite_gap_sequence(needed),
        "mod6_candidates": mod6_candidate_gap_sequence(needed),
        "cramer_like": cramer_like_gap_sequence(needed, np.random.default_rng(rng.integers(0, 2**63 - 1))),
    }
    cases: dict[str, np.ndarray] = {}
    for family, values in base_controls.items():
        for label, window in offset_windows(values, args.offsets, args.window_gaps).items():
            cases[f"control/{family}/{label}"] = window

    for idx in range(args.stochastic_control_count):
        local_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
        cases[f"control/random_matrix/seed_{idx}"] = gue_spacing_blocks(
            args.window_gaps, args.gue_matrix_size, local_rng
        )
    for idx in range(args.stochastic_control_count):
        local_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
        cases[f"control/logistic_return_intervals/seed_{idx}"] = logistic_return_intervals(
            args.window_gaps, local_rng
        )
    return cases


def analyze_case(name: str, base: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict[str, Any]:
    perimeters = {name: analyze_sequence(name, base, args, rng)}
    row = compact(perimeters)[name]
    one_sided = list(row["coherent_one_sided_observables"])
    return {
        "case": name,
        "family": name.split("/")[0],
        "subfamily": name.split("/")[1],
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


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    obs_sets = [set(case["one_sided_observables"]) for case in cases]
    state_counts: dict[str, int] = {}
    for case in cases:
        state_counts[case["state"]] = state_counts.get(case["state"], 0) + 1
    return {
        "case_count": len(cases),
        "state_counts": state_counts,
        "sr_count": sum(1 for case in cases if case["has_sr"]),
        "sr_rate": sum(1 for case in cases if case["has_sr"]) / len(cases) if cases else 0.0,
        "common_one_sided_observables": sorted(set.intersection(*obs_sets)) if cases else [],
        "union_one_sided_observables": sorted(set.union(*obs_sets)) if obs_sets else [],
        "blank_count": state_counts.get("beta_absent_blank", 0),
        "beta_recovered_count": state_counts.get("beta_chart_recovered", 0),
        "support_fall_count": state_counts.get("support_falls", 0),
        "endpoint_distance_mean": float(np.mean([case["endpoint_distance"] for case in cases])) if cases else 0.0,
        "stable_count_coherent_mean": float(np.mean([case["stable_count_coherent"] for case in cases])) if cases else 0.0,
    }


def summarize_by_subfamily(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for subfamily in sorted({case["subfamily"] for case in cases}):
        out[subfamily] = summarize([case for case in cases if case["subfamily"] == subfamily])
    return out


def verdict(prime_summary: dict[str, Any], control_summary: dict[str, Any], control_subfamilies: dict[str, dict[str, Any]]) -> str:
    prime_sr_persists = prime_summary["sr_rate"] == 1.0 and prime_summary["common_one_sided_observables"] == ["SR"]
    control_common_sr = "SR" in control_summary["common_one_sided_observables"]
    any_control_subfamily_sr_complete = any(
        summary["sr_rate"] == 1.0 and "SR" in summary["common_one_sided_observables"]
        for summary in control_subfamilies.values()
    )
    if prime_sr_persists and not control_common_sr and not any_control_subfamily_sr_complete:
        return "PRIME_SR_PERSISTENT_BOUNDARY_SPECIFIC"
    if prime_sr_persists:
        return "PRIME_SR_PERSISTS_BUT_CONTROL_COLLISION"
    return "PRIME_SR_NOT_PERSISTENT"


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    prime_specs = prime_cases(args)
    control_specs = control_cases(args, rng)
    prime_results = [
        analyze_case(name, base, args, np.random.default_rng(rng.integers(0, 2**63 - 1)))
        for name, base in prime_specs.items()
    ]
    control_results = [
        analyze_case(name, base, args, np.random.default_rng(rng.integers(0, 2**63 - 1)))
        for name, base in control_specs.items()
    ]
    prime_summary = summarize(prime_results)
    control_summary = summarize(control_results)
    control_subfamilies = summarize_by_subfamily(control_results)

    output = {
        "experiment": "prime_sr_persistent_boundary",
        "question": "Does SR remain a prime-specific one-sided boundary signature across providers, offsets, and broader non-prime controls?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": [
            *OBS_NAMES,
            "provider",
            "offset",
            "case_state",
            "sr_rate",
            "common_one_sided_observables",
            "prime_control_common_obs_jaccard",
        ],
        "params": vars(args),
        "target_row": TARGET_ROW,
        "observable_contract": {
            "claim": "prime_SR_persistent_boundary holds only if prime windows keep SR as the common one-sided observable across providers and offsets while broadened non-prime controls do not share full SR persistence",
            "observable": "SR membership in coherent_one_sided_observables plus common one-sided observable signature",
            "operator": "canonical order/null gate on row-local windows; provider, offset, and non-prime control expansion",
            "generator": "prime gaps from dnd_autoricerca row_spacings and direct sieve; controls from composite gaps, mod6 candidates, Cramer-like events, GUE random matrix blocks, logistic return intervals",
            "denominator": "8 prime row-local windows plus 20 non-prime controls (3 deterministic families x 4 offsets + 4 stochastic GUE/logistic cases each by default)",
            "non_possible": "prime-specific SR boundary if prime SR rate falls below 8/8, if prime common obs is not exactly [SR], or if any control subfamily shares full SR persistence",
            "not_tested": "global beta atlas, V_c, gap_ratio, source GUE/Poisson labels, analytic origin of SR",
        },
        "prime_summary": prime_summary,
        "control_summary": control_summary,
        "control_subfamilies": control_subfamilies,
        "prime_control_common_obs_jaccard": obs_jaccard(
            prime_summary["common_one_sided_observables"],
            control_summary["common_one_sided_observables"],
        ),
        "verdict": verdict(prime_summary, control_summary, control_subfamilies),
        "cases": {
            "prime": prime_results,
            "controls": control_results,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"target={TARGET_ROW}")
    print(
        "prime "
        f"sr={prime_summary['sr_count']}/{prime_summary['case_count']} "
        f"common={prime_summary['common_one_sided_observables']} "
        f"states={prime_summary['state_counts']}"
    )
    print(
        "controls "
        f"sr={control_summary['sr_count']}/{control_summary['case_count']} "
        f"common={control_summary['common_one_sided_observables']} "
        f"states={control_summary['state_counts']}"
    )
    for family, summary in control_subfamilies.items():
        print(
            f"control/{family} sr={summary['sr_count']}/{summary['case_count']} "
            f"common={summary['common_one_sided_observables']}"
        )
    print(f"prime_control_common_obs_jaccard={output['prime_control_common_obs_jaccard']:.3f}")
    print(f"verdict={output['verdict']}")
    print(f"saved {out}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-gaps", type=int, default=1024)
    parser.add_argument("--offsets", type=int, nargs="+", default=[0, 512, 1024, 1536])
    parser.add_argument("--stochastic-control-count", type=int, default=4)
    parser.add_argument("--gue-matrix-size", type=int, default=64)
    parser.add_argument("--n-replicates", type=int, default=8)
    parser.add_argument("--n-beta", type=int, default=9)
    parser.add_argument("--n-baseline", type=int, default=16)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.75)
    parser.add_argument("--endpoint-distance-min", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=202605120330)
    parser.add_argument("--out", default="tools/data/prime_sr_persistent_boundary_20260512_0330.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
