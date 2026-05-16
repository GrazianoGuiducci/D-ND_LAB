#!/usr/bin/env python3
"""
Cross-domain unfolding-transfer matrix for the BOUNDARY redesign.

The unit is the reader axis, not a new RP lambda crest.  For each row-aligned
domain/size/seed spectrum, the script measures how much the observable vector
changes when the same raw spacings are read by global, exact-local and
odd-coerced local unfolding.  Row-aligned permutation and circular-shift nulls
test whether the reader residue is stronger than order-preserving baselines.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from exp_rosenzweig_porter_bridge_physical_audit import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    fit_brody_q,
    fit_mixture_weight,
    rp_hamiltonian,
)
from exp_rp_boundary_raw_count_null_audit import binomial_tail_at_least, wilson_interval
from exp_rp_unfolding_sensitivity_audit import local_unfold_gaps as odd_coerced_unfold


def parse_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def central_slice(length: int, fraction: float) -> slice:
    keep = max(4, int(round(length * fraction)))
    start = max(0, (length - keep) // 2)
    return slice(start, start + keep)


def exact_local_unfold(gaps: np.ndarray, window: int) -> np.ndarray:
    gaps = clean_gaps(gaps)
    if len(gaps) == 0:
        return gaps
    width = max(2, min(int(window), len(gaps)))
    left = width // 2
    out = np.empty_like(gaps)
    for idx in range(len(gaps)):
        start = idx - left
        end = start + width
        if start < 0:
            start = 0
            end = width
        if end > len(gaps):
            end = len(gaps)
            start = max(0, end - width)
        denom = float(np.mean(gaps[start:end]))
        if denom <= 1e-12:
            denom = float(np.mean(gaps))
        out[idx] = gaps[idx] / denom
    return out / float(np.mean(out))


def clean_gaps(gaps: np.ndarray) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
    if len(gaps) == 0:
        return gaps
    return gaps / float(np.mean(gaps))


def gue_gaps(n: int, reps: int, seed: int, central_fraction: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    all_gaps: list[float] = []
    for _ in range(reps):
        real = rng.normal(0.0, 1.0, size=(n, n))
        imag = rng.normal(0.0, 1.0, size=(n, n))
        h = (real + real.T) / 2.0 + 1j * (imag - imag.T) / 2.0
        levels = np.linalg.eigvalsh(h / math.sqrt(2.0 * n))
        bulk = np.sort(levels)[central_slice(len(levels), central_fraction)]
        all_gaps.extend(np.diff(bulk).tolist())
    return clean_gaps(np.asarray(all_gaps, dtype=float))


def poisson_gaps(n: int, reps: int, seed: int, _central_fraction: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return clean_gaps(rng.exponential(1.0, size=max(4, (n - 1) * reps)))


def rp_gaps(lam: float, n: int, reps: int, seed: int, central_fraction: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    all_gaps: list[float] = []
    for _ in range(reps):
        levels = np.linalg.eigvalsh(rp_hamiltonian(rng, n, lam))
        bulk = np.sort(levels)[central_slice(len(levels), central_fraction)]
        all_gaps.extend(np.diff(bulk).tolist())
    return clean_gaps(np.asarray(all_gaps, dtype=float))


def read_by_mode(gaps: np.ndarray, mode: str, window: int) -> np.ndarray:
    gaps = clean_gaps(gaps)
    if mode == "global_mean":
        return gaps
    if mode.startswith("exact"):
        return exact_local_unfold(gaps, window)
    if mode.startswith("odd_coerced"):
        return clean_gaps(odd_coerced_unfold(gaps, window))
    raise ValueError(f"unknown unfolding mode: {mode}")


def feature_vector(gaps: np.ndarray, grid_size: int) -> dict[str, float]:
    gaps = clean_gaps(gaps)
    obs = {name: float(fn(gaps)) for name, fn in OBSERVABLES_CANONICAL.items()}
    q, _ = fit_brody_q(gaps, grid_size)
    w, _ = fit_mixture_weight(gaps, grid_size)
    obs["brody_q"] = float(q)
    obs["berry_robnick_like_gue_weight"] = float(w)
    return obs


def classify(features: dict[str, float]) -> str:
    q = features["brody_q"]
    w = features["berry_robnick_like_gue_weight"]
    if q <= 0.25 and w <= 0.25:
        return "poisson_endpoint"
    if q >= 0.75 and w >= 0.75:
        return "gue_endpoint"
    return "intermediate"


def mode_matrix(gaps: np.ndarray, modes: list[str], windows: list[int], grid_size: int) -> list[dict[str, Any]]:
    rows = []
    for mode in modes:
        for window in windows:
            if mode == "global_mean" and window != windows[0]:
                continue
            features = feature_vector(read_by_mode(gaps, mode, window), grid_size)
            rows.append(
                {
                    "reader": f"{mode}:w{window}" if mode != "global_mean" else "global_mean",
                    "mode": mode,
                    "window": window if mode != "global_mean" else None,
                    "features": {key: round(value, 9) for key, value in features.items()},
                    "classical_state": classify(features),
                }
            )
    return rows


def sensitivity(rows: list[dict[str, Any]], feature_names: list[str]) -> float:
    matrix = np.asarray([[row["features"][name] for name in feature_names] for row in rows], dtype=float)
    if len(matrix) < 2:
        return 0.0
    scale = np.std(matrix, axis=0)
    scale[scale <= 1e-9] = 1.0
    z = matrix / scale
    best = 0.0
    for i in range(len(z)):
        for j in range(i + 1, len(z)):
            best = max(best, float(np.linalg.norm(z[i] - z[j]) / math.sqrt(len(feature_names))))
    return best


def stable_endpoint(source_type: str, states: list[str]) -> bool:
    if source_type == "GUE":
        return all(state == "gue_endpoint" for state in states)
    if source_type == "Poisson":
        return all(state == "poisson_endpoint" for state in states)
    return False


def row_nulls(
    gaps: np.ndarray,
    args: argparse.Namespace,
    modes: list[str],
    windows: list[int],
    feature_names: list[str],
    seed: int,
) -> tuple[list[float], list[float]]:
    rng = np.random.default_rng(seed)
    perm_scores = []
    shift_scores = []
    for _ in range(args.permutation_null_trials):
        permuted = np.array(gaps, copy=True)
        rng.shuffle(permuted)
        perm_scores.append(sensitivity(mode_matrix(permuted, modes, windows, args.grid_size), feature_names))
    for shift in parse_ints(args.position_offsets):
        shifted = np.roll(gaps, shift)
        shift_scores.append(sensitivity(mode_matrix(shifted, modes, windows, args.grid_size), feature_names))
    return perm_scores, shift_scores


def build_source_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = []
    sizes = parse_ints(args.sizes)
    seeds = parse_ints(args.seeds)
    for n in sizes:
        for seed_idx, seed in enumerate(seeds):
            rows.append(
                {
                    "row_id": f"GUE_N{n}_s{seed_idx}",
                    "source_type": "GUE",
                    "n": n,
                    "seed": seed,
                    "gaps": gue_gaps(n, args.reps, seed + n * 1009, args.central_fraction),
                }
            )
            rows.append(
                {
                    "row_id": f"Poisson_N{n}_s{seed_idx}",
                    "source_type": "Poisson",
                    "n": n,
                    "seed": seed,
                    "gaps": poisson_gaps(n, args.reps, seed + n * 1013, args.central_fraction),
                }
            )
            for lam in parse_floats(args.rp_lambdas):
                rows.append(
                    {
                        "row_id": f"RP_lambda_{lam:.3f}_N{n}_s{seed_idx}",
                        "source_type": "RP",
                        "lambda": round(lam, 6),
                        "n": n,
                        "seed": seed,
                        "gaps": rp_gaps(lam, n, args.reps, seed + n * 1019 + int(round(lam * 10000)), args.central_fraction),
                    }
                )
    return rows


def summarize_group(rows: list[dict[str, Any]], source_type: str, args: argparse.Namespace) -> dict[str, Any]:
    group = [row for row in rows if row["source_type"] == source_type]
    if not group:
        return {}
    if source_type in {"GUE", "Poisson"}:
        successes = sum(1 for row in group if row["endpoint_transfer_stable"])
        null_successes = sum(1 for row in group for score in row["permutation_null_scores"] if score <= args.endpoint_max_sensitivity)
        null_total = sum(len(row["permutation_null_scores"]) for row in group)
        p = 1.0 - binomial_tail_at_least(successes, len(group), null_successes / null_total) if null_total else None
        return {
            "source_type": source_type,
            "criterion": "endpoint_transfer_stable",
            "observed_successes": successes,
            "observed_total": len(group),
            "observed_rate": round(successes / len(group), 6),
            "observed_wilson_95": wilson_interval(successes, len(group)),
            "null_successes": null_successes,
            "null_total": null_total,
            "null_rate": round(null_successes / null_total, 6) if null_total else None,
            "binomial_tail_note": "left-tail endpoint failure risk; high observed rate is expected for true endpoints",
            "left_tail_p_approx": round(p, 6) if p is not None else None,
            "median_sensitivity": round(float(np.median([row["reader_sensitivity"] for row in group])), 6),
        }
    successes = sum(1 for row in group if row["reader_residue_pass"])
    null_successes = sum(
        1
        for row in group
        for score in row["permutation_null_scores"] + row["position_shift_null_scores"]
        if score >= row["reader_sensitivity"]
    )
    null_total = sum(len(row["permutation_null_scores"]) + len(row["position_shift_null_scores"]) for row in group)
    p = binomial_tail_at_least(successes, len(group), null_successes / null_total) if null_total else None
    by_lambda = {}
    for lam in sorted({row.get("lambda") for row in group}):
        lam_rows = [row for row in group if row.get("lambda") == lam]
        by_lambda[f"{lam:.3f}"] = {
            "reader_residue_pass": sum(1 for row in lam_rows if row["reader_residue_pass"]),
            "total": len(lam_rows),
            "median_sensitivity": round(float(np.median([row["reader_sensitivity"] for row in lam_rows])), 6),
            "state_sequences": [row["state_sequence"] for row in lam_rows],
        }
    return {
        "source_type": source_type,
        "criterion": "reader_residue_pass",
        "observed_successes": successes,
        "observed_total": len(group),
        "observed_rate": round(successes / len(group), 6),
        "observed_wilson_95": wilson_interval(successes, len(group)),
        "null_successes": null_successes,
        "null_total": null_total,
        "null_rate": round(null_successes / null_total, 6) if null_total else None,
        "binomial_tail_p": round(p, 6) if p is not None else None,
        "median_sensitivity": round(float(np.median([row["reader_sensitivity"] for row in group])), 6),
        "by_lambda": by_lambda,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    modes = [part.strip() for part in args.unfolding_modes.split(",") if part.strip()]
    windows = parse_ints(args.local_windows)
    feature_names = ["SR", "SR2", "L1", "L2", "triple_var", "brody_q", "berry_robnick_like_gue_weight"]
    output_rows = []
    for source in build_source_rows(args):
        gaps = source.pop("gaps")
        readers = mode_matrix(gaps, modes, windows, args.grid_size)
        score = sensitivity(readers, feature_names)
        perm, shift = row_nulls(gaps, args, modes, windows, feature_names, int(source["seed"]) + int(source["n"]))
        null_combined = perm + shift
        null_ge = sum(1 for item in null_combined if item >= score)
        row_p = (1 + null_ge) / (1 + len(null_combined))
        states = [reader["classical_state"] for reader in readers]
        endpoint_ok = stable_endpoint(source["source_type"], states)
        reader_pass = (
            source["source_type"] == "RP"
            and score >= args.min_reader_sensitivity
            and row_p <= args.alpha
            and len(set(states)) > 1
        )
        output_rows.append(
            {
                **source,
                "n_spacings": int(len(gaps)),
                "reader_sensitivity": round(score, 6),
                "null_ge_observed": null_ge,
                "null_total": len(null_combined),
                "row_aligned_p": round(row_p, 6),
                "endpoint_transfer_stable": endpoint_ok,
                "reader_residue_pass": reader_pass,
                "state_sequence": states,
                "readers": readers,
                "permutation_null_scores": [round(item, 6) for item in perm],
                "position_shift_null_scores": [round(item, 6) for item in shift],
            }
        )

    summary = {
        "GUE": summarize_group(output_rows, "GUE", args),
        "Poisson": summarize_group(output_rows, "Poisson", args),
        "RP": summarize_group(output_rows, "RP", args),
    }
    output = {
        "experiment": "boundary_unfolding_transfer_matrix",
        "question": "Does the unfolding/window reader axis transfer across GUE, Poisson and RP as boundary coordinate rather than as a stable RP lambda?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": feature_names
        + [
            "reader_sensitivity",
            "endpoint_transfer_stable",
            "reader_residue_pass",
            "row_aligned_p",
            "permutation_null_scores",
            "position_shift_null_scores",
        ],
        "parameters": {
            "sizes": parse_ints(args.sizes),
            "seeds": parse_ints(args.seeds),
            "reps": args.reps,
            "rp_lambdas": parse_floats(args.rp_lambdas),
            "unfolding_modes": modes,
            "local_windows": windows,
            "permutation_null_trials": args.permutation_null_trials,
            "position_offsets": parse_ints(args.position_offsets),
            "central_fraction": args.central_fraction,
            "grid_size": args.grid_size,
        },
        "threshold_preregistered": {
            "rp_reader_residue": f"reader_sensitivity >= {args.min_reader_sensitivity}, row_aligned_p <= {args.alpha}, and at least two reader states",
            "endpoint_transfer": f"all reader states match endpoint and reader_sensitivity <= {args.endpoint_max_sensitivity} is audited, not forced",
            "nulls": "permutation and circular-shift scores computed from the same row spacings",
        },
        "observable_contract": {
            "claim": "window_mode/unfolding is a boundary coordinate if endpoints transfer while RP boundary rows expose reader-specific residue against row-aligned nulls",
            "observable": "reader_sensitivity of canonical spectral vector across global, exact-local and odd-coerced readers",
            "operator": "same raw spacing row read by multiple unfolding/window modes",
            "generator": "GUE matrices, Poisson exponential spacings, and RP H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE",
            "denominator": "domain x size x seed rows; nulls use the same row spacings under permutation and circular shifts",
            "non_possible": "reader axis as boundary coordinate if GUE/Poisson endpoints also fracture or RP residue does not beat row-aligned nulls",
            "not_tested": "experimental spectra, N to infinity, Anderson 3D, analytic universality class proof",
        },
        "summary": summary,
        "rows": output_rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/boundary_unfolding_transfer_matrix_20260516_1031.json")
    parser.add_argument("--sizes", default="128,192")
    parser.add_argument("--seeds", default="202605161031,202605161032,202605161033,202605161034")
    parser.add_argument("--reps", type=int, default=6)
    parser.add_argument("--rp-lambdas", default="0.045,0.060,0.075")
    parser.add_argument("--unfolding-modes", default="global_mean,exact_local,odd_coerced")
    parser.add_argument("--local-windows", default="9,12")
    parser.add_argument("--permutation-null-trials", type=int, default=32)
    parser.add_argument("--position-offsets", default="1,2,3,4,5,6,7,8")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--min-reader-sensitivity", type=float, default=0.75)
    parser.add_argument("--endpoint-max-sensitivity", type=float, default=0.75)
    parser.add_argument("--alpha", type=float, default=0.05)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
