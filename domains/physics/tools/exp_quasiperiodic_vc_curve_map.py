#!/usr/bin/env python3
"""
Interpolated V_c curve map for quasiperiodic Sturmian-Harper sequences.

Previous cycle showed that first-grid V_c is phase-sensitive and does not
separate phi from metallic controls as a lattice value. This tool keeps the
same boundary observable but moves one step regressively: measure the local
shape of r(V) and interpolate the crossing instead of letting the grid decide.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.linalg import eigvalsh_tridiagonal


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def sturmian_sequence(theta: float, n: int, phase: float = 0.0) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(float)


def r_statistic_from_diag(diagonal: np.ndarray) -> float:
    offdiag = np.ones(len(diagonal) - 1, dtype=float)
    eigs = eigvalsh_tridiagonal(diagonal, offdiag, check_finite=False)
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 1e-12]
    if len(spacings) < 2:
        return 0.5
    left = spacings[:-1]
    right = spacings[1:]
    return float(np.mean(np.minimum(left, right) / np.maximum(left, right)))


def curve_for_sequence(seq: np.ndarray, v_values: np.ndarray) -> np.ndarray:
    return np.array([r_statistic_from_diag(v * seq) for v in v_values], dtype=float)


def first_interpolated_crossing(v_values: np.ndarray, r_values: np.ndarray, threshold: float) -> dict:
    below = r_values < threshold
    crossing_count = int(np.sum(below[1:] != below[:-1]))
    if not np.any(below):
        return {
            "vc_interp": None,
            "vc_grid": None,
            "r_at_grid": None,
            "slope_at_cross": None,
            "crossed": False,
            "crossing_count": crossing_count,
        }

    idx = int(np.argmax(below))
    vc_grid = float(v_values[idx])
    r_at_grid = float(r_values[idx])

    if idx == 0:
        vc_interp = vc_grid
        slope = None
    else:
        v0, v1 = float(v_values[idx - 1]), float(v_values[idx])
        r0, r1 = float(r_values[idx - 1]), float(r_values[idx])
        if abs(r1 - r0) < 1e-15:
            vc_interp = vc_grid
            slope = 0.0
        else:
            vc_interp = v0 + (threshold - r0) * (v1 - v0) / (r1 - r0)
            slope = (r1 - r0) / (v1 - v0)

    return {
        "vc_interp": float(vc_interp),
        "vc_grid": vc_grid,
        "r_at_grid": r_at_grid,
        "slope_at_cross": None if slope is None else float(slope),
        "crossed": True,
        "crossing_count": crossing_count,
    }


def summarize(values: list[float | None]) -> dict:
    finite = np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if len(finite) == 0:
        return {"count": 0, "none_count": len(values)}
    return {
        "count": int(len(finite)),
        "none_count": int(len(values) - len(finite)),
        "median": float(np.median(finite)),
        "q25": float(np.quantile(finite, 0.25)),
        "q75": float(np.quantile(finite, 0.75)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }


def summarize_ints(values: list[int]) -> dict:
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return {"count": 0}
    return {
        "count": int(len(arr)),
        "median": float(np.median(arr)),
        "max": int(np.max(arr)),
        "zero_count": int(np.sum(arr == 0)),
        "one_count": int(np.sum(arr == 1)),
        "multi_count": int(np.sum(arr > 1)),
    }


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    r_thresholds = parse_csv_floats(args.r_thresholds)
    v_values = np.arange(args.v_min, args.v_max + (args.v_step / 2), args.v_step)
    domains = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }

    rows = []
    curve_rows = []
    for n in ns:
        for phase in phases:
            phi_seq = sturmian_sequence(1 / PHI, n, phase)
            ones = int(np.sum(phi_seq))
            seqs = []
            for domain, theta in domains.items():
                seqs.append((domain, None, sturmian_sequence(theta, n, phase)))
            for trial in range(args.random_trials):
                seq = np.array([1.0] * ones + [0.0] * (n - ones), dtype=float)
                rng.shuffle(seq)
                seqs.append(("balanced_random_phi_density", trial, seq))

            for domain, trial, seq in seqs:
                r_values = curve_for_sequence(seq, v_values)
                curve_rows.append({
                    "domain": domain,
                    "trial": trial,
                    "N": n,
                    "phase": phase,
                    "r_min": float(np.min(r_values)),
                    "r_max": float(np.max(r_values)),
                    "r_span": float(np.max(r_values) - np.min(r_values)),
                    "r_at_v_min": float(r_values[0]),
                    "r_at_v_max": float(r_values[-1]),
                })
                for threshold in r_thresholds:
                    cross = first_interpolated_crossing(v_values, r_values, threshold)
                    rows.append({
                        "domain": domain,
                        "trial": trial,
                        "N": n,
                        "phase": phase,
                        "r_threshold": threshold,
                        **cross,
                    })

    summary = {}
    for domain in sorted({row["domain"] for row in rows}):
        subset = [row for row in rows if row["domain"] == domain]
        summary[domain] = {
            "vc_interp": summarize([row["vc_interp"] for row in subset]),
            "vc_grid": summarize([row["vc_grid"] for row in subset]),
            "slope_at_cross": summarize([
                None if row["slope_at_cross"] is None else abs(row["slope_at_cross"])
                for row in subset
            ]),
            "crossing_count": summarize_ints([row["crossing_count"] for row in subset]),
        }

    summary_by_threshold = {}
    grouped_threshold: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for row in rows:
        grouped_threshold[(row["domain"], row["r_threshold"])].append(row)
    for (domain, threshold), subset in sorted(grouped_threshold.items()):
        summary_by_threshold[f"{domain}|r_threshold={threshold}"] = {
            "vc_interp": summarize([row["vc_interp"] for row in subset]),
            "slope_at_cross": summarize([
                None if row["slope_at_cross"] is None else abs(row["slope_at_cross"])
                for row in subset
            ]),
            "crossing_count": summarize_ints([row["crossing_count"] for row in subset]),
        }

    matched = []
    for n in ns:
        for phase in phases:
            for threshold in r_thresholds:
                key_rows = [
                    row for row in rows
                    if row["N"] == n
                    and row["phase"] == phase
                    and row["r_threshold"] == threshold
                    and row["trial"] is None
                ]
                by_domain = {row["domain"]: row for row in key_rows}
                if {"phi", "silver", "bronze"} <= set(by_domain):
                    values = {name: by_domain[name]["vc_interp"] for name in ("phi", "silver", "bronze")}
                    if all(value is not None for value in values.values()):
                        phi = float(values["phi"])
                        silver = float(values["silver"])
                        bronze = float(values["bronze"])
                        matched.append({
                            "N": n,
                            "phase": phase,
                            "r_threshold": threshold,
                            "phi_vc": phi,
                            "silver_vc": silver,
                            "bronze_vc": bronze,
                            "phi_lt_silver": phi < silver,
                            "phi_lt_bronze": phi < bronze,
                            "phi_between_controls": min(silver, bronze) <= phi <= max(silver, bronze),
                            "phi_abs_delta_to_control_median": abs(phi - float(np.median([silver, bronze]))),
                        })

    matched_summary = {
        "count": len(matched),
        "phi_lt_silver": int(sum(item["phi_lt_silver"] for item in matched)),
        "phi_lt_bronze": int(sum(item["phi_lt_bronze"] for item in matched)),
        "phi_lt_both": int(sum(item["phi_lt_silver"] and item["phi_lt_bronze"] for item in matched)),
        "phi_between_controls": int(sum(item["phi_between_controls"] for item in matched)),
        "phi_abs_delta_to_control_median": summarize([
            item["phi_abs_delta_to_control_median"] for item in matched
        ]),
    }

    return {
        "experiment": "quasiperiodic_vc_curve_map",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "r_thresholds": r_thresholds,
            "v_min": args.v_min,
            "v_max": args.v_max,
            "v_step": args.v_step,
            "random_trials": args.random_trials,
            "seed": args.seed,
        },
        "summary": summary,
        "summary_by_threshold": summary_by_threshold,
        "matched_summary": matched_summary,
        "matched_rows": matched,
        "curve_summary_rows": curve_rows,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="89,144,233,377,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--r-thresholds", default="0.48,0.50,0.52")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=3.0)
    parser.add_argument("--v-step", type=float, default=0.01)
    parser.add_argument("--random-trials", type=int, default=3)
    parser.add_argument("--seed", type=int, default=202605090330)
    parser.add_argument("--out", default="tools/data/quasiperiodic_vc_curve_map_20260509_0330.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps({
        "summary": output["summary"],
        "matched_summary": output["matched_summary"],
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
