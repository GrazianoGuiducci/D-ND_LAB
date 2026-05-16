#!/usr/bin/env python3
"""
Unfolding-sensitivity audit for the finite Rosenzweig-Porter BOUNDARY window.

The previous raw-count audit promoted RP lambda 0.045 and 0.060 under a global
mean spacing normalization.  This script asks whether the same row-aligned
two-reader boundary survives when the spacing normalization is changed to a
local-window unfolding.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from exp_rosenzweig_porter_bridge_physical_audit import (
    FEATURE_NAMES,
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    SR_local_rigidity,
    central_slice,
    fit_brody_q,
    fit_mixture_weight,
    rp_hamiltonian,
    source_type,
)
from exp_rp_boundary_raw_count_null_audit import (
    binomial_tail_at_least,
    classify_with_labels,
    parse_floats,
    parse_ints,
    rotate_labels,
    shuffled_labels,
    wilson_interval,
)


def local_unfold_gaps(gaps: np.ndarray, window: int) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
    if len(gaps) == 0:
        return gaps
    width = max(3, min(int(window), len(gaps)))
    if width % 2 == 0:
        width -= 1
    if width < 3:
        return gaps / float(np.mean(gaps))
    pad = width // 2
    padded = np.pad(gaps, (pad, pad), mode="edge")
    kernel = np.ones(width, dtype=float) / float(width)
    local_mean = np.convolve(padded, kernel, mode="valid")
    local_mean[local_mean <= 1e-12] = float(np.mean(gaps))
    return gaps / local_mean


def row_spacings_and_ipr(
    lam: float,
    n: int,
    reps: int,
    central_fraction: float,
    seed: int,
    unfolding_mode: str,
    local_window: int,
) -> tuple[np.ndarray, float]:
    rng = np.random.default_rng(seed)
    spacings = []
    iprs = []
    for _ in range(reps):
        h = rp_hamiltonian(rng, n, lam)
        levels, vectors = np.linalg.eigh(h)
        central = levels[central_slice(len(levels), central_fraction)]
        gaps = np.diff(np.sort(central))
        gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
        if len(gaps):
            if unfolding_mode == "local_window":
                gaps = local_unfold_gaps(gaps, local_window)
            spacings.extend(gaps.tolist())
        probs = np.square(np.abs(vectors[:, central_slice(vectors.shape[1], central_fraction)]))
        ipr = np.sum(probs * probs, axis=0)
        if len(ipr):
            iprs.extend(ipr.tolist())
    if not spacings:
        raise ValueError(f"lambda {lam} produced no spacings")
    s = np.asarray(spacings, dtype=float)
    if unfolding_mode == "global_mean":
        s = s / float(np.mean(s))
    elif unfolding_mode == "local_window":
        s = s / float(np.mean(s))
    else:
        raise ValueError(f"unknown unfolding mode: {unfolding_mode}")
    s = s[np.isfinite(s) & (s > 1e-12)]
    return s, float(np.mean(iprs)) if iprs else 0.0


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def classical_state(row: dict[str, Any]) -> str:
    q = float(row["brody_q"])
    w = float(row["berry_robnick_like_gue_weight"])
    if q <= 0.25 and w <= 0.25:
        return "classical_poisson_endpoint"
    if q >= 0.75 and w >= 0.75:
        return "classical_gue_endpoint"
    return "classical_intermediate"


def stability_state(freq: float) -> str:
    if freq >= 0.75:
        return "stable_graph_bridge"
    if freq >= 0.25:
        return "parameter_sensitive_bridge"
    return "unstable_non_bridge"


def compute_row(lam: float, args: argparse.Namespace, n: int, seed: int, unfolding_mode: str) -> dict[str, Any]:
    s, mean_ipr = row_spacings_and_ipr(
        lam,
        n,
        args.reps,
        args.central_fraction,
        seed,
        unfolding_mode,
        args.local_window,
    )
    obs = {name: float(fn(s)) for name, fn in OBSERVABLES_CANONICAL.items()}
    obs["SR_local_rigidity"] = float(SR_local_rigidity(s))
    brody_q, brody_nll = fit_brody_q(s, args.grid_size)
    mixture_w, mixture_ks = fit_mixture_weight(s, args.grid_size)
    return {
        "domain_window": f"RP_lambda_{lam:.3f}",
        "lambda": round(lam, 6),
        "source_domain_type": source_type(lam, args.poisson_pole_max, args.gue_pole_min),
        "n_spacings": int(len(s)),
        "mean_ipr": round(mean_ipr, 9),
        "observables": {key: round(value, 9) for key, value in obs.items()},
        "brody_q": round(brody_q, 6),
        "brody_nll": round(brody_nll, 6),
        "berry_robnick_like_gue_weight": round(mixture_w, 6),
        "mixture_ks": round(mixture_ks, 6),
    }


def empty_hits(lambdas: list[float]) -> dict[str, dict[str, Any]]:
    return {
        f"RP_lambda_{lam:.3f}": {
            "lambda": round(float(lam), 6),
            "observed_hits": 0,
            "label_shuffle_hits": 0,
            "position_shift_hits": 0,
            "brody_q": [],
            "mixture_w": [],
            "mean_ipr": [],
            "sr": [],
            "margins": [],
            "cross_fractions": [],
        }
        for lam in lambdas
    }


def audit_size_mode(args: argparse.Namespace, n: int, unfolding_mode: str) -> dict[str, Any]:
    lambdas = parse_floats(args.lambdas)
    seeds = parse_ints(args.seeds)
    ks = parse_ints(args.k_values)
    label_null_trials = int(args.label_null_trials)
    position_offsets = parse_ints(args.position_offsets)
    row_hits = empty_hits(lambdas)
    observed_total = len(seeds) * len(ks)
    label_null_total = observed_total * label_null_trials
    position_null_total = observed_total * len(position_offsets)
    reader_runs = []

    for seed in seeds:
        rows = [
            compute_row(lam, args, n, seed + (n * 10000) + int(round(lam * 1000)), unfolding_mode)
            for lam in lambdas
        ]
        labels = [row["source_domain_type"] for row in rows]
        rng = np.random.default_rng(seed + n + (0 if unfolding_mode == "global_mean" else 1000003))
        for k in ks:
            observed = classify_with_labels(rows, k, labels)
            observed_by_name = {row["domain_window"]: row for row in observed}
            observed_candidates = [
                row["domain_window"] for row in observed if row["boundary_state"] == "third_included_candidate"
            ]
            reader_runs.append(
                {"n": n, "seed": seed, "k": k, "unfolding_mode": unfolding_mode, "observed_candidates": observed_candidates}
            )
            for row in rows:
                name = row["domain_window"]
                graph_row = observed_by_name[name]
                item = row_hits[name]
                if graph_row["boundary_state"] == "third_included_candidate":
                    item["observed_hits"] += 1
                item["margins"].append(float(graph_row["centroid_margin"]))
                item["cross_fractions"].append(float(graph_row["cross_neighbor_fraction"]))
                item["brody_q"].append(float(row["brody_q"]))
                item["mixture_w"].append(float(row["berry_robnick_like_gue_weight"]))
                item["mean_ipr"].append(float(row["mean_ipr"]))
                item["sr"].append(float(row["observables"]["SR"]))

            for _ in range(label_null_trials):
                null_rows = classify_with_labels(rows, k, shuffled_labels(labels, rng))
                for null_row in null_rows:
                    if null_row["boundary_state"] == "third_included_candidate":
                        row_hits[null_row["domain_window"]]["label_shuffle_hits"] += 1

            for offset in position_offsets:
                null_rows = classify_with_labels(rows, k, rotate_labels(labels, offset))
                for null_row in null_rows:
                    if null_row["boundary_state"] == "third_included_candidate":
                        row_hits[null_row["domain_window"]]["position_shift_hits"] += 1

    rows_out = []
    thresholded = []
    graph_only = []
    for name in sorted(row_hits, key=lambda key: row_hits[key]["lambda"]):
        item = row_hits[name]
        class_row = {
            "brody_q": median(item["brody_q"]),
            "berry_robnick_like_gue_weight": median(item["mixture_w"]),
        }
        c_state = classical_state(class_row)
        observed_rate = item["observed_hits"] / observed_total
        label_rate = item["label_shuffle_hits"] / label_null_total
        position_rate = item["position_shift_hits"] / position_null_total
        min_lift = min(observed_rate - label_rate, observed_rate - position_rate)
        label_p = binomial_tail_at_least(item["observed_hits"], observed_total, label_rate)
        position_p = binomial_tail_at_least(item["observed_hits"], observed_total, position_rate)
        threshold_pass = (
            c_state == "classical_intermediate"
            and observed_rate >= args.min_observed_rate
            and min_lift >= args.min_lift
            and label_p <= args.alpha
            and position_p <= args.alpha
        )
        graph_stability = stability_state(observed_rate)
        if threshold_pass:
            thresholded.append(name)
        if graph_stability == "stable_graph_bridge" and c_state != "classical_intermediate":
            graph_only.append(name)
        rows_out.append(
            {
                "domain_window": name,
                "lambda": item["lambda"],
                "classical_audit_state": c_state,
                "graph_stability_state": graph_stability,
                "observed_successes": item["observed_hits"],
                "observed_total": observed_total,
                "observed_rate": round(observed_rate, 6),
                "observed_wilson_95": wilson_interval(item["observed_hits"], observed_total),
                "label_shuffle_successes": item["label_shuffle_hits"],
                "label_shuffle_total": label_null_total,
                "label_shuffle_rate": round(label_rate, 6),
                "label_shuffle_wilson_95": wilson_interval(item["label_shuffle_hits"], label_null_total),
                "label_shuffle_lift": round(observed_rate - label_rate, 6),
                "label_shuffle_binomial_tail_p": round(label_p, 6),
                "position_shift_successes": item["position_shift_hits"],
                "position_shift_total": position_null_total,
                "position_shift_rate": round(position_rate, 6),
                "position_shift_wilson_95": wilson_interval(item["position_shift_hits"], position_null_total),
                "position_shift_lift": round(observed_rate - position_rate, 6),
                "position_shift_binomial_tail_p": round(position_p, 6),
                "min_lift_against_nulls": round(min_lift, 6),
                "threshold_pass": threshold_pass,
                "median_brody_q": round(class_row["brody_q"], 6),
                "median_berry_robnick_like_gue_weight": round(class_row["berry_robnick_like_gue_weight"], 6),
                "median_SR": round(median(item["sr"]), 6),
                "median_mean_ipr": round(median(item["mean_ipr"]), 9),
                "mean_centroid_margin": round(float(np.mean(item["margins"])), 6),
                "mean_cross_neighbor_fraction": round(float(np.mean(item["cross_fractions"])), 6),
            }
        )

    return {
        "n": n,
        "unfolding_mode": unfolding_mode,
        "observed_total": observed_total,
        "label_shuffle_total": label_null_total,
        "position_shift_total": position_null_total,
        "summary": {
            "thresholded_two_reader_rows": thresholded,
            "thresholded_two_reader_count": len(thresholded),
            "graph_only_stable_rows": graph_only,
            "graph_only_stable_count": len(graph_only),
        },
        "rows": rows_out,
        "reader_runs": reader_runs,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    sizes = parse_ints(args.sizes)
    modes = [part.strip() for part in args.unfolding_modes.split(",") if part.strip()]
    by_size_mode = [audit_size_mode(args, n, mode) for mode in modes for n in sizes]

    per_mode: dict[str, Any] = {}
    for mode in modes:
        entries = [entry for entry in by_size_mode if entry["unfolding_mode"] == mode]
        size_sets = {entry["n"]: set(entry["summary"]["thresholded_two_reader_rows"]) for entry in entries}
        all_size_rows = sorted(set.intersection(*size_sets.values())) if size_sets else []
        any_size_rows = sorted(set.union(*size_sets.values())) if size_sets else []
        per_mode[mode] = {
            "thresholded_two_reader_all_sizes": len(all_size_rows),
            "thresholded_two_reader_all_size_rows": all_size_rows,
            "thresholded_two_reader_any_size": len(any_size_rows),
            "thresholded_two_reader_any_size_rows": any_size_rows,
        }

    mode_sets = {mode: set(item["thresholded_two_reader_all_size_rows"]) for mode, item in per_mode.items()}
    all_mode_stable = sorted(set.intersection(*mode_sets.values())) if mode_sets else []
    mode_sensitive = sorted(set.union(*mode_sets.values()) - set(all_mode_stable)) if mode_sets else []

    comparison_rows = []
    for lam in parse_floats(args.lambdas):
        name = f"RP_lambda_{lam:.3f}"
        row = {"domain_window": name, "lambda": round(float(lam), 6)}
        for mode in modes:
            entries = [entry for entry in by_size_mode if entry["unfolding_mode"] == mode]
            rows_for_lambda = [
                next(item for item in entry["rows"] if item["domain_window"] == name)
                for entry in entries
            ]
            row[f"{mode}_pass_sizes"] = [
                entry["n"]
                for entry in entries
                if next(item for item in entry["rows"] if item["domain_window"] == name)["threshold_pass"]
            ]
            row[f"{mode}_min_observed_rate"] = round(float(min(item["observed_rate"] for item in rows_for_lambda)), 6)
            row[f"{mode}_min_lift"] = round(float(min(item["min_lift_against_nulls"] for item in rows_for_lambda)), 6)
            row[f"{mode}_max_null_p"] = round(
                float(
                    max(
                        max(item["label_shuffle_binomial_tail_p"], item["position_shift_binomial_tail_p"])
                        for item in rows_for_lambda
                    )
                ),
                6,
            )
        comparison_rows.append(row)

    output = {
        "experiment": "rp_unfolding_sensitivity_audit",
        "question": "Do the RP boundary rows 0.045/0.060 remain thresholded under an alternate local-window unfolding?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "observed_successes",
            "label_shuffle_successes",
            "position_shift_successes",
            "Wilson intervals",
            "binomial-tail p-values",
            "min_lift_against_nulls",
            "threshold_pass",
            "unfolding_mode",
        ],
        "parameters": {
            "sizes": sizes,
            "reps": args.reps,
            "lambdas": parse_floats(args.lambdas),
            "seeds": parse_ints(args.seeds),
            "k_values": parse_ints(args.k_values),
            "label_null_trials": args.label_null_trials,
            "position_offsets": parse_ints(args.position_offsets),
            "central_fraction": args.central_fraction,
            "grid_size": args.grid_size,
            "poisson_pole_max": args.poisson_pole_max,
            "gue_pole_min": args.gue_pole_min,
            "unfolding_modes": modes,
            "local_window": args.local_window,
        },
        "threshold_preregistered": {
            "min_observed_rate": args.min_observed_rate,
            "min_lift_against_each_null": args.min_lift,
            "alpha_each_null": args.alpha,
            "classical_clause": "classical_intermediate required for two-reader threshold pass",
            "unfolding_stability_clause": "boundary-stable only if row passes all sizes in every unfolding mode",
        },
        "observable_contract": {
            "claim": "the finite RP boundary window is unfolding-stable only if the same lambda rows beat label-shuffle and position-shift nulls under global and local spacing normalization",
            "observable": "thresholded two-reader raw-count pass by lambda, size and unfolding mode",
            "operator": "repeat the RP raw-count gate with global mean and local-window unfolded spacings",
            "generator": "H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE across size, seed, k and unfolding mode",
            "denominator": "same lambda grid per size and unfolding; observed denominator seeds*k, null denominators observed*null_trials",
            "non_possible": "unfolding-stable boundary if any promoted lambda fails all-size pass under local-window unfolding",
            "not_tested": "larger N, different local windows beyond the preregistered one, experimental spectra, Anderson 3D, many-body RP",
        },
        "summary": {
            "per_mode": per_mode,
            "thresholded_two_reader_all_modes": len(all_mode_stable),
            "thresholded_two_reader_all_mode_rows": all_mode_stable,
            "unfolding_sensitive_rows": mode_sensitive,
        },
        "comparison_rows": comparison_rows,
        "by_size_mode": by_size_mode,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/rp_unfolding_sensitivity_audit_20260516_0921.json")
    parser.add_argument("--sizes", default="64,96,128")
    parser.add_argument("--reps", type=int, default=10)
    parser.add_argument("--lambdas", default="0,0.03,0.045,0.06,0.075,0.10,0.18,0.32,0.68,0.82,1.0")
    parser.add_argument("--seeds", default="202605160820,202605160821,202605160822,202605160823")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--label-null-trials", type=int, default=64)
    parser.add_argument("--position-offsets", default="1,2,3,4,5,6,7,8,9,10")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--poisson-pole-max", type=float, default=0.03)
    parser.add_argument("--gue-pole-min", type=float, default=0.82)
    parser.add_argument("--min-observed-rate", type=float, default=0.75)
    parser.add_argument("--min-lift", type=float, default=0.10)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--unfolding-modes", default="global_mean,local_window")
    parser.add_argument("--local-window", type=int, default=7)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
