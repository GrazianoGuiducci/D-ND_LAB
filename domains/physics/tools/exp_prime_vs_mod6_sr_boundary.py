#!/usr/bin/env python3
"""
Strict prime-vs-mod6 audit for the SR boundary residue.

The previous cycle falsified `prime_SR_persistent_boundary` in the broad
control perimeter and exposed `mod6_candidates` as the nearest antagonist. This
script keeps the denominator row-local: every prime window is paired with two
6k +/- 1 candidate windows at the same provider/offset row.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from exp_boundary_residual_beta_absent_audit import support_state
from exp_prime_persistent_blank_gate import offset_windows, obs_jaccard
from exp_semireal_boundary_transfer_gate import row_spacings
from exp_semireal_order_denominator_gate import (
    analyze_sequence,
    compact,
    normalize,
    prime_gap_sequence,
    sieve_primes_for_count,
)
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
FOCUS_OBS = ["SR", "L1", "triple_var"]
TARGET_ROW = "numeri_primi:cycle_3"
VECTOR_P_MAX = 0.01
VECTOR_MIN_POSITIVE = 0.0
NEXT_SCALE_WINDOW_GAPS = 16384


def mod6_candidates_between(start: float, end: float) -> np.ndarray:
    lo = int(math.floor(start))
    hi = int(math.ceil(end))
    first_k = max(1, (lo - 1) // 6 - 2)
    values: list[int] = []
    k = first_k
    while 6 * k - 1 <= hi:
        for value in (6 * k - 1, 6 * k + 1):
            if lo <= value <= hi:
                values.append(value)
        k += 1
    return np.array(sorted(set(values)), dtype=float)


def quantile_downsample(values: np.ndarray, count: int) -> np.ndarray:
    if len(values) < count:
        raise ValueError(f"cannot downsample {len(values)} values to {count}")
    if len(values) == count:
        return values.astype(float)
    idx = np.linspace(0, len(values) - 1, count)
    picked = np.unique(np.rint(idx).astype(int))
    if len(picked) < count:
        missing = [i for i in range(len(values)) if i not in set(picked)]
        picked = np.array(sorted([*picked, *missing[: count - len(picked)]]), dtype=int)
    return values[np.sort(picked[:count])].astype(float)


def mod6_index_gap_sequence(n_gaps: int, offset: int) -> np.ndarray:
    values: list[int] = []
    k = 1
    needed = offset + n_gaps + 1
    while len(values) < needed:
        values.append(6 * k - 1)
        values.append(6 * k + 1)
        k += 1
    arr = np.array(sorted(values[offset : offset + n_gaps + 1]), dtype=float)
    return normalize(np.diff(arr))


def mod6_span_gap_sequence(prime_values: np.ndarray, n_gaps: int) -> np.ndarray:
    candidates = mod6_candidates_between(float(prime_values[0]), float(prime_values[-1]))
    sampled = quantile_downsample(candidates, n_gaps + 1)
    return normalize(np.diff(sampled))


def direct_prime_values(needed: int) -> np.ndarray:
    return sieve_primes_for_count(needed).astype(float)


def build_specs(args: argparse.Namespace) -> dict[str, np.ndarray]:
    needed = max(args.offsets) + args.window_gaps + 1
    direct_values = direct_prime_values(needed)
    provider_gaps = {
        "dnd_autoricerca": normalize(row_spacings("numeri_primi")[: needed - 1]),
        "direct_sieve": normalize(np.diff(direct_values)),
    }

    specs: dict[str, np.ndarray] = {}
    for provider, gaps in provider_gaps.items():
        for offset in args.offsets:
            end = offset + args.window_gaps
            if end > len(gaps):
                continue
            row_id = f"{provider}/offset_{offset}"
            specs[f"prime/{row_id}"] = normalize(gaps[offset:end])
            specs[f"mod6_index_aligned/{row_id}"] = mod6_index_gap_sequence(args.window_gaps, offset)
            prime_window_values = direct_values[offset : offset + args.window_gaps + 1]
            specs[f"mod6_span_matched/{row_id}"] = mod6_span_gap_sequence(
                prime_window_values, args.window_gaps
            )
    return specs


def analyze_case(name: str, base: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict[str, Any]:
    perimeters = {name: analyze_sequence(name, base, args, rng)}
    row = compact(perimeters)[name]
    one_sided = list(row["coherent_one_sided_observables"])
    parts = name.split("/")
    return {
        "case": name,
        "class": parts[0],
        "provider": parts[1],
        "offset": parts[2],
        "row_id": "/".join(parts[1:]),
        "n_gaps": row["n_gaps"],
        "state": support_state(row, args),
        "one_sided_observables": one_sided,
        "has_sr": "SR" in one_sided,
        "has_focus_signature": all(obs in one_sided for obs in FOCUS_OBS),
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
        "focus_signature_count": sum(1 for case in cases if case["has_focus_signature"]),
        "common_one_sided_observables": sorted(set.intersection(*obs_sets)) if obs_sets else [],
        "union_one_sided_observables": sorted(set.union(*obs_sets)) if obs_sets else [],
        "endpoint_distance_mean": float(np.mean([case["endpoint_distance"] for case in cases])) if cases else 0.0,
        "stable_count_coherent_mean": float(np.mean([case["stable_count_coherent"] for case in cases])) if cases else 0.0,
        "mean_z_coherent": {
            obs: float(np.mean([case["z_mean_coherent"][obs] for case in cases])) if cases else 0.0
            for obs in OBS_NAMES
        },
    }


def paired_rows(cases: list[dict[str, Any]], mod6_class: str) -> list[dict[str, Any]]:
    by_key = {(case["class"], case["row_id"]): case for case in cases}
    rows = []
    for (_, row_id), prime in sorted(by_key.items()):
        if prime["class"] != "prime":
            continue
        mod6 = by_key.get((mod6_class, row_id))
        if mod6 is None:
            continue
        rows.append(
            {
                "row_id": row_id,
                "prime_case": prime["case"],
                "mod6_case": mod6["case"],
                "prime_obs": prime["one_sided_observables"],
                "mod6_obs": mod6["one_sided_observables"],
                "signature_jaccard": obs_jaccard(prime["one_sided_observables"], mod6["one_sided_observables"]),
                "sr_delta": int(prime["has_sr"]) - int(mod6["has_sr"]),
                "focus_signature_delta": int(prime["has_focus_signature"]) - int(mod6["has_focus_signature"]),
                "endpoint_delta": float(prime["endpoint_distance"] - mod6["endpoint_distance"]),
                "stable_count_delta": float(prime["stable_count_coherent"] - mod6["stable_count_coherent"]),
                "z_delta": {
                    obs: float(prime["z_mean_coherent"][obs] - mod6["z_mean_coherent"][obs])
                    for obs in OBS_NAMES
                },
            }
        )
    return rows


def row_local_swap_audit(rows: list[dict[str, Any]], args: argparse.Namespace, rng: np.random.Generator) -> dict[str, Any]:
    if not rows:
        return {}
    metrics = {
        "sr_delta_mean": np.array([row["sr_delta"] for row in rows], dtype=float),
        "focus_signature_delta_mean": np.array([row["focus_signature_delta"] for row in rows], dtype=float),
        "endpoint_delta_mean": np.array([row["endpoint_delta"] for row in rows], dtype=float),
        "stable_count_delta_mean": np.array([row["stable_count_delta"] for row in rows], dtype=float),
    }
    for obs in OBS_NAMES:
        metrics[f"z_delta_{obs}_mean"] = np.array([row["z_delta"][obs] for row in rows], dtype=float)

    observed = {name: float(np.mean(values)) for name, values in metrics.items()}
    null_values = {name: [] for name in metrics}
    for _ in range(args.label_swap_trials):
        signs = rng.choice(np.array([-1.0, 1.0]), size=len(rows), replace=True)
        for name, values in metrics.items():
            null_values[name].append(float(np.mean(values * signs)))
    p_two_sided = {}
    for name, obs_value in observed.items():
        null = np.array(null_values[name], dtype=float)
        p_two_sided[name] = float((np.sum(np.abs(null) >= abs(obs_value)) + 1) / (len(null) + 1))
    return {
        "null": "row_local_label_swap_preserving_provider_offset_denominator",
        "trials": args.label_swap_trials,
        "observed": observed,
        "p_two_sided": p_two_sided,
    }


def vector_pair_summary(pair_summaries: dict[str, Any]) -> dict[str, Any]:
    pair_results: dict[str, Any] = {}
    for label, summary in pair_summaries.items():
        audit = summary["label_swap_audit"]
        observed = audit.get("observed", {})
        p_two_sided = audit.get("p_two_sided", {})
        vector = {}
        for obs in FOCUS_OBS:
            metric = f"z_delta_{obs}_mean"
            vector[obs] = {
                "delta_mean": float(observed.get(metric, 0.0)),
                "p_two_sided": float(p_two_sided.get(metric, 1.0)),
                "passes": (
                    float(observed.get(metric, 0.0)) > VECTOR_MIN_POSITIVE
                    and float(p_two_sided.get(metric, 1.0)) <= VECTOR_P_MAX
                ),
            }
        pair_results[label] = {
            "row_count": summary["row_count"],
            "vector": vector,
            "vector_pass_count": sum(1 for item in vector.values() if item["passes"]),
            "vector_complete": all(item["passes"] for item in vector.values()),
            "sr_binary_delta_mean": float(observed.get("sr_delta_mean", 0.0)),
            "sr_binary_p_two_sided": float(p_two_sided.get("sr_delta_mean", 1.0)),
        }
    return {
        "focus_observables": FOCUS_OBS,
        "criterion": {
            "delta_mean": f">{VECTOR_MIN_POSITIVE}",
            "p_two_sided": f"<={VECTOR_P_MAX}",
            "all_focus_observables_required_per_antagonist": True,
        },
        "pairs": pair_results,
        "complete_for_all_antagonists": all(
            item["vector_complete"] for item in pair_results.values()
        )
        if pair_results
        else False,
    }


def denominator_contract(pair_summaries: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    rows_by_antagonist = {
        label: int(summary["row_count"]) for label, summary in pair_summaries.items()
    }
    min_observed = min(rows_by_antagonist.values()) if rows_by_antagonist else 0
    passes = min_observed >= args.min_paired_rows
    return {
        "min_paired_rows_declared": args.min_paired_rows,
        "rows_by_antagonist": rows_by_antagonist,
        "min_observed_paired_rows": min_observed,
        "passes": passes,
        "next_scale_window_gaps": NEXT_SCALE_WINDOW_GAPS,
        "next_scale_allowed": passes and args.window_gaps >= 8192,
        "failure_mode": None
        if passes
        else "denominator_sparse_below_predeclared_min_paired_rows",
    }


def verdict(vector_summary: dict[str, Any], denom_contract: dict[str, Any]) -> str:
    if not denom_contract.get("passes"):
        return "PRIME_MINUS_MOD6_Z_VECTOR_REVIEW_REQUIRED_DENOMINATOR"
    if vector_summary["complete_for_all_antagonists"]:
        return "PRIME_MINUS_MOD6_Z_VECTOR_CONFIRMED"
    pass_counts = [
        pair["vector_pass_count"] for pair in vector_summary["pairs"].values()
    ]
    if pass_counts and max(pass_counts) >= 2:
        return "PRIME_MINUS_MOD6_Z_VECTOR_PARTIAL"
    return "PRIME_MINUS_MOD6_Z_VECTOR_FALSIFIED"


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.trace_jsonl:
        raise SystemExit("--trace-jsonl is required: the micro-trace is part of the observable contract")
    rng = np.random.default_rng(args.seed)
    specs = build_specs(args)
    cases = [
        analyze_case(name, base, args, np.random.default_rng(rng.integers(0, 2**63 - 1)))
        for name, base in specs.items()
    ]
    class_summaries = {
        label: summarize([case for case in cases if case["class"] == label])
        for label in ("prime", "mod6_index_aligned", "mod6_span_matched")
    }
    pair_summaries = {}
    for mod6_class in ("mod6_index_aligned", "mod6_span_matched"):
        rows = paired_rows(cases, mod6_class)
        pair_summaries[mod6_class] = {
            "row_count": len(rows),
            "rows": rows,
            "mean_signature_jaccard": float(np.mean([row["signature_jaccard"] for row in rows])) if rows else 0.0,
            "label_swap_audit": row_local_swap_audit(
                rows, args, np.random.default_rng(rng.integers(0, 2**63 - 1))
            ),
        }
    vector_summary = vector_pair_summary(pair_summaries)
    denom_contract = denominator_contract(pair_summaries, args)
    final_verdict = verdict(vector_summary, denom_contract)
    verdict_authority = {
        "authority": "tool_candidate"
        if final_verdict in {
            "PRIME_MINUS_MOD6_Z_VECTOR_CONFIRMED",
            "PRIME_MINUS_MOD6_Z_VECTOR_PARTIAL",
        }
        else "review_required",
        "promotion_allowed": False,
        "reason": (
            "denominator_contract_failed"
            if not denom_contract.get("passes")
            else "vector_contract_audit_only"
        ),
        "has_SR_authority": "audit_only",
    }

    output = {
        "experiment": "prime_vs_mod6_sr_boundary",
        "question": "Does SR belong to prime selection or to the row-local 6k +/- 1 pre-boundary?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": [
            *OBS_NAMES,
            "provider",
            "offset",
            "row_id",
            "source_mode",
            "case_state",
            "sr_rate",
            "focus_signature_count",
            "signature_jaccard",
            "row_local_label_swap_p",
            "prime_minus_mod6_z_vector",
            "trace_jsonl_event",
        ],
        "params": vars(args),
        "target_row": TARGET_ROW,
        "observable_contract": {
            "claim": "prime_minus_mod6_z_vector(SR,L1,triple_var) survives row-local 6k +/- 1 subtraction; binary has_SR is audit-only and cannot decide the verdict",
            "observable": "paired z-deltas for SR,L1,triple_var against mod6_index_aligned and mod6_span_matched, plus audit-only SR membership and focus signature in coherent_one_sided_observables",
            "operator": "canonical order/null gate with row-local prime-vs-mod6 pairing and label-swap audit",
            "generator": "prime gaps from dnd_autoricerca row_spacings and direct sieve; mod6_index_aligned from 6k +/- 1 by same gap offset; mod6_span_matched from 6k +/- 1 candidates inside the matching direct-sieve prime span downsampled to the same denominator",
            "denominator": f"row-local prime windows paired with both mod6 antagonists; min_paired_rows predeclared at {args.min_paired_rows}",
            "non_possible": "vector residue if any focus observable has non-positive mean z-delta or label-swap p > 0.01 in either mod6 antagonist",
            "not_tested": "global beta atlas, V_c, gap_ratio, analytic source of mod6 transfer, primality tests inside mod6 candidates",
        },
        "class_summaries": class_summaries,
        "pair_summaries": pair_summaries,
        "vector_summary": vector_summary,
        "denominator_contract": denom_contract,
        "verdict": final_verdict,
        "verdict_authority": verdict_authority,
        "cases": cases,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    if args.trace_jsonl:
        trace_out = Path(args.trace_jsonl)
        trace_out.parent.mkdir(parents=True, exist_ok=True)
        with trace_out.open("w", encoding="utf-8") as fh:
            for case in cases:
                fh.write(json.dumps({"event": "case", **case}, sort_keys=True) + "\n")
            for label, summary in class_summaries.items():
                fh.write(
                    json.dumps(
                        {"event": "class_summary", "class": label, **summary},
                        sort_keys=True,
                    )
                    + "\n"
                )
            for label, summary in pair_summaries.items():
                for row in summary["rows"]:
                    fh.write(
                        json.dumps(
                            {"event": "paired_row", "mod6_class": label, **row},
                            sort_keys=True,
                        )
                        + "\n"
                    )
                fh.write(
                    json.dumps(
                        {
                            "event": "pair_summary",
                            "mod6_class": label,
                            "row_count": summary["row_count"],
                            "mean_signature_jaccard": summary["mean_signature_jaccard"],
                            "label_swap_audit": summary["label_swap_audit"],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
            fh.write(
                json.dumps(
                    {
                        "event": "vector_summary",
                        **vector_summary,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            fh.write(
                json.dumps(
                    {
                        "event": "denominator_contract",
                        **denom_contract,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            fh.write(
                json.dumps(
                    {
                        "event": "verdict",
                        "verdict": output["verdict"],
                        "verdict_authority": output["verdict_authority"],
                        "params": output["params"],
                        "observables_registry": output["observables_registry"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    for label, summary in class_summaries.items():
        print(
            f"{label} sr={summary['sr_count']}/{summary['case_count']} "
            f"focus={summary['focus_signature_count']}/{summary['case_count']} "
            f"common={summary['common_one_sided_observables']} "
            f"states={summary['state_counts']}"
        )
    for label, summary in pair_summaries.items():
        audit = summary["label_swap_audit"]
        p_sr = audit.get("p_two_sided", {}).get("sr_delta_mean")
        p_z_sr = audit.get("p_two_sided", {}).get("z_delta_SR_mean")
        print(
            f"pair/{label} rows={summary['row_count']} "
            f"jaccard={summary['mean_signature_jaccard']:.3f} "
            f"p_sr={p_sr:.4f} p_z_sr={p_z_sr:.4f}"
        )
    for label, pair in vector_summary["pairs"].items():
        vector_bits = " ".join(
            f"{obs}=({item['delta_mean']:.3f},p={item['p_two_sided']:.4f})"
            for obs, item in pair["vector"].items()
        )
        print(f"vector/{label} complete={pair['vector_complete']} {vector_bits}")
    print(
        "denominator_contract="
        f"min_declared={denom_contract['min_paired_rows_declared']} "
        f"min_observed={denom_contract['min_observed_paired_rows']} "
        f"passes={denom_contract['passes']} "
        f"next_scale_allowed={denom_contract['next_scale_allowed']}"
    )
    print(f"verdict={output['verdict']}")
    print(f"saved {out}")
    if args.trace_jsonl:
        print(f"trace {args.trace_jsonl}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-gaps", type=int, default=1024)
    parser.add_argument("--offsets", type=int, nargs="+", default=[0, 512, 1024, 1536])
    parser.add_argument("--n-replicates", type=int, default=8)
    parser.add_argument("--n-beta", type=int, default=9)
    parser.add_argument("--n-baseline", type=int, default=16)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.75)
    parser.add_argument("--endpoint-distance-min", type=float, default=1.0)
    parser.add_argument("--label-swap-trials", type=int, default=4096)
    parser.add_argument("--min-paired-rows", type=int, default=10)
    parser.add_argument("--seed", type=int, default=202605130330)
    parser.add_argument("--out", default="tools/data/prime_vs_mod6_sr_boundary_20260513_0330.json")
    parser.add_argument("--trace-jsonl", required=True)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
