#!/usr/bin/env python3
"""
exp_logistic_cyclic_block_entropy_gate.py

Falsification node after the logistic surrogate-contract gate.

The 10:42 cycle left one surviving object:
`logistic_orbit_values / block_entropy_deficit_k4`.  Circular-shift
denominators were very small, so this tool separates local grammar from the
linear starting-cut artifact:

- linear block entropy: the existing non-wrapping observable;
- cyclic block entropy: wrapping blocks are included, so circular shifts leave
  the observable unchanged up to numerical precision;
- block-shuffle scan: tests whether support survives when local chunks are
  preserved but chunk order is broken at different block sizes.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from exp_logistic_counter_scope_gate import (
    OBSERVABLES_NATIVE_VERSION,
    block_entropy_deficit,
    logistic_orbit,
    logistic_return_intervals,
    logistic_symbolic_itinerary,
    quantile_symbols,
)
from exp_logistic_surrogate_contract_gate import block_shuffle, circular_shift


OBSERVABLES_CYCLIC_VERSION = "logistic-cyclic-block-entropy-1.0.0-2026-05-07"
OBS_NAMES = ["linear_block_entropy_deficit_k4", "cyclic_block_entropy_deficit_k4"]
PERIMETERS = ["logistic_orbit_values", "logistic_symbolic_itinerary", "logistic_return_intervals"]


def cyclic_block_entropy_deficit(values: np.ndarray, k: int = 4, bins: int = 4) -> float:
    symbols = quantile_symbols(values, bins)
    n = len(symbols)
    if n < k + 1:
        return 0.0
    alphabet = max(2, int(np.max(symbols)) + 1)
    blocks = [tuple(symbols[(i + j) % n] for j in range(k)) for i in range(n)]
    counts = np.array(list(Counter(blocks).values()), dtype=float)
    probs = counts / float(np.sum(counts))
    entropy = -float(np.sum(probs * np.log2(probs)))
    max_entropy = k * math.log2(alphabet)
    return float(max(0.0, 1.0 - entropy / max_entropy)) if max_entropy > 1e-15 else 0.0


def compute(values: np.ndarray, k: int = 4, bins: int = 4) -> dict[str, float]:
    return {
        "linear_block_entropy_deficit_k4": block_entropy_deficit(values, k=k, bins=bins),
        "cyclic_block_entropy_deficit_k4": cyclic_block_entropy_deficit(values, k=k, bins=bins),
    }


def z_against(values: np.ndarray, maker, n_baseline: int, rng: np.random.Generator) -> dict:
    original = compute(values)
    baseline = {name: [] for name in OBS_NAMES}
    for _ in range(n_baseline):
        surrogate = maker(values, rng)
        row = compute(surrogate)
        for name in OBS_NAMES:
            baseline[name].append(row[name])

    means = {}
    sds = {}
    z = {}
    for name in OBS_NAMES:
        vals = np.array(baseline[name], dtype=float)
        means[name] = float(np.mean(vals))
        sds[name] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        z[name] = float((original[name] - means[name]) / sds[name]) if sds[name] > 1e-15 else 0.0
    return {"original": original, "baseline_mean": means, "baseline_std": sds, "z": z}


def rotation_sensitivity(values: np.ndarray, n_rotations: int, rng: np.random.Generator) -> dict:
    original = compute(values)
    rows = {name: [] for name in OBS_NAMES}
    for _ in range(n_rotations):
        row = compute(circular_shift(values, rng))
        for name in OBS_NAMES:
            rows[name].append(row[name])

    out = {}
    for name in OBS_NAMES:
        vals = np.array(rows[name], dtype=float)
        out[name] = {
            "original": original[name],
            "rotation_mean": float(np.mean(vals)),
            "rotation_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
            "max_abs_delta": float(np.max(np.abs(vals - original[name]))) if len(vals) else 0.0,
        }
    return out


def build_sequences(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, np.ndarray]:
    return {
        "logistic_orbit_values": logistic_orbit(args.n_values, rng),
        "logistic_symbolic_itinerary": logistic_symbolic_itinerary(args.n_values, rng),
        "logistic_return_intervals": logistic_return_intervals(args.n_returns, rng),
    }


def analyze(values: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict:
    marginal = z_against(values, lambda v, r: r.permutation(v), args.n_baseline, rng)
    rotation = rotation_sensitivity(values, args.n_rotations, rng)
    blocks = {}
    for block_size in args.block_sizes:
        blocks[str(block_size)] = z_against(
            values,
            lambda v, r, bs=block_size: block_shuffle(v, bs, r),
            args.n_baseline,
            np.random.default_rng(rng.integers(0, 2**63 - 1)),
        )

    cyclic_block_support = [
        int(block_size)
        for block_size in args.block_sizes
        if abs(blocks[str(block_size)]["z"]["cyclic_block_entropy_deficit_k4"]) >= args.z_min
    ]
    linear_block_support = [
        int(block_size)
        for block_size in args.block_sizes
        if abs(blocks[str(block_size)]["z"]["linear_block_entropy_deficit_k4"]) >= args.z_min
    ]

    return {
        "source": {
            "n": int(len(values)),
            "mean": float(np.mean(values)),
            "variance": float(np.var(values)),
            "unique_values": int(len(np.unique(values))),
        },
        "marginal_shuffle": marginal,
        "rotation_sensitivity": rotation,
        "block_shuffle_scan": blocks,
        "support_summary": {
            "marginal_stable": [
                name for name in OBS_NAMES if abs(marginal["z"][name]) >= args.z_min
            ],
            "rotation_invariant": [
                name
                for name in OBS_NAMES
                if rotation[name]["max_abs_delta"] <= args.rotation_eps
            ],
            "linear_block_shuffle_support_sizes": linear_block_support,
            "cyclic_block_shuffle_support_sizes": cyclic_block_support,
            "cyclic_support_all_declared_block_sizes": cyclic_block_support == list(args.block_sizes),
        },
    }


def compact(perimeters: dict) -> dict:
    out = {}
    for name, data in perimeters.items():
        out[name] = {
            "n": data["source"]["n"],
            "marginal_stable": data["support_summary"]["marginal_stable"],
            "rotation_invariant": data["support_summary"]["rotation_invariant"],
            "linear_block_shuffle_support_sizes": data["support_summary"]["linear_block_shuffle_support_sizes"],
            "cyclic_block_shuffle_support_sizes": data["support_summary"]["cyclic_block_shuffle_support_sizes"],
            "cyclic_support_all_declared_block_sizes": data["support_summary"][
                "cyclic_support_all_declared_block_sizes"
            ],
            "marginal_z": data["marginal_shuffle"]["z"],
            "rotation_max_abs_delta": {
                obs: row["max_abs_delta"] for obs, row in data["rotation_sensitivity"].items()
            },
            "block_shuffle_z": {
                block_size: row["z"] for block_size, row in data["block_shuffle_scan"].items()
            },
        }
    return out


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    sequences = build_sequences(args, rng)
    perimeters = {}
    for name in PERIMETERS:
        perimeters[name] = analyze(
            sequences[name],
            args,
            np.random.default_rng(rng.integers(0, 2**63 - 1)),
        )

    output = {
        "experiment": "logistic_cyclic_block_entropy_gate",
        "category": "meta_cut_artifact_falsification",
        "question": "Does logistic orbit block-entropy support survive a cyclic/start-invariant observable and block-size scan?",
        "observables_registry": "not used for canonical observables",
        "observables_native_version": OBSERVABLES_NATIVE_VERSION,
        "observables_cyclic_version": OBSERVABLES_CYCLIC_VERSION,
        "observables_used": OBS_NAMES,
        "params": {
            **vars(args),
            "block_sizes": list(args.block_sizes),
        },
        "matrix": compact(perimeters),
        "perimeters": perimeters,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_native_version={OBSERVABLES_NATIVE_VERSION}")
    print(f"observables_cyclic_version={OBSERVABLES_CYCLIC_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print("perimeter n marginal_stable rotation_invariant cyclic_block_sizes")
    for name, row in output["matrix"].items():
        print(
            f"{name:>29s} "
            f"{row['n']:>5d} "
            f"{','.join(row['marginal_stable']) or '[]':>62s} "
            f"{','.join(row['rotation_invariant']) or '[]':>62s} "
            f"{row['cyclic_block_shuffle_support_sizes']}"
        )
    print(f"saved {out_path}")
    return output


def parse_block_sizes(raw: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one block size is required")
    if any(value < 2 for value in values):
        raise argparse.ArgumentTypeError("block sizes must be >= 2")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-values", type=int, default=4096)
    parser.add_argument("--n-returns", type=int, default=4096)
    parser.add_argument("--n-baseline", type=int, default=32)
    parser.add_argument("--n-rotations", type=int, default=32)
    parser.add_argument("--block-sizes", type=parse_block_sizes, default=(4, 8, 16, 32, 64, 128, 256))
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--rotation-eps", type=float, default=1e-12)
    parser.add_argument("--seed", type=int, default=202605071419)
    parser.add_argument("--out", default="tools/data/logistic_cyclic_block_entropy_gate_20260507_1419.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
