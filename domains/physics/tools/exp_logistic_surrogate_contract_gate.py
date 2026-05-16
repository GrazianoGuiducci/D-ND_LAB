#!/usr/bin/env python3
"""
exp_logistic_surrogate_contract_gate.py

Regressive surrogate-contract test for ORDER_DENOMINATOR_GATE on the logistic
counter-scope.

The 10:06 cycle used a marginal-preserving shuffle null. This tool keeps the
same logistic-native observable suite and splits the null contract:

- marginal_shuffle: preserves values only;
- circular_shift: preserves the cyclic temporal order;
- block_shuffle: preserves local temporal blocks and breaks block order.

Support is reported as contract-stable only when the same observable clears the
gate against all declared surrogate classes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from exp_logistic_counter_scope_gate import (
    OBSERVABLES_NATIVE_VERSION,
    OBS_NAMES,
    compute_native,
    logistic_orbit,
    logistic_return_intervals,
    logistic_symbolic_itinerary,
)


SURROGATE_CLASSES = ["marginal_shuffle", "circular_shift", "block_shuffle"]


def circular_shift(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if len(values) < 2:
        return values.copy()
    shift = int(rng.integers(1, len(values)))
    return np.roll(values, shift)


def block_shuffle(values: np.ndarray, block_size: int, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(values)
    if block_size <= 1:
        return rng.permutation(values)
    blocks = [values[i : i + block_size] for i in range(0, len(values), block_size)]
    order = rng.permutation(len(blocks))
    return np.concatenate([blocks[i] for i in order])


def make_surrogate(
    values: np.ndarray,
    surrogate_class: str,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if surrogate_class == "marginal_shuffle":
        return rng.permutation(values)
    if surrogate_class == "circular_shift":
        return circular_shift(values, rng)
    if surrogate_class == "block_shuffle":
        return block_shuffle(values, block_size, rng)
    raise ValueError(f"unknown surrogate class: {surrogate_class}")


def z_against_surrogate_class(
    values: np.ndarray,
    surrogate_class: str,
    n_baseline: int,
    recurrence_max_points: int,
    block_size: int,
    rng: np.random.Generator,
) -> dict:
    original = compute_native(values, recurrence_max_points)
    baseline = {name: [] for name in OBS_NAMES}
    for _ in range(n_baseline):
        surrogate = make_surrogate(values, surrogate_class, block_size, rng)
        obs = compute_native(surrogate, recurrence_max_points)
        for name in OBS_NAMES:
            baseline[name].append(obs[name])

    means = {}
    sds = {}
    z = {}
    for name in OBS_NAMES:
        vals = np.array(baseline[name], dtype=float)
        means[name] = float(np.mean(vals))
        sds[name] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        z[name] = float((original[name] - means[name]) / sds[name]) if sds[name] > 1e-15 else 0.0

    return {
        "original": original,
        "baseline_mean": means,
        "baseline_std": sds,
        "z": z,
        "stable_observables": [name for name in OBS_NAMES if abs(z[name]) >= 2.0],
    }


def build_sequences(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, np.ndarray]:
    return {
        "logistic_orbit_values": logistic_orbit(args.n_values, rng),
        "logistic_symbolic_itinerary": logistic_symbolic_itinerary(args.n_values, rng),
        "logistic_return_intervals": logistic_return_intervals(args.n_returns, rng),
    }


def analyze_sequence(name: str, values: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict:
    surrogate_results = {}
    stable_sets = []
    for surrogate_class in SURROGATE_CLASSES:
        result = z_against_surrogate_class(
            values,
            surrogate_class,
            args.n_baseline,
            args.recurrence_max_points,
            args.block_size,
            np.random.default_rng(rng.integers(0, 2**63 - 1)),
        )
        surrogate_results[surrogate_class] = result
        stable_sets.append(set(result["stable_observables"]))

    contract_stable = sorted(set.intersection(*stable_sets)) if stable_sets else []
    marginal_only = sorted(set(surrogate_results["marginal_shuffle"]["stable_observables"]) - set(contract_stable))

    return {
        "source": {
            "n": int(len(values)),
            "mean": float(np.mean(values)),
            "variance": float(np.var(values)),
            "unique_values": int(len(np.unique(values))),
        },
        "surrogates": surrogate_results,
        "contract_stable_observables": contract_stable,
        "marginal_only_observables": marginal_only,
    }


def compact(perimeters: dict) -> dict:
    out = {}
    for name, data in perimeters.items():
        out[name] = {
            "n": data["source"]["n"],
            "contract_stable_observables": data["contract_stable_observables"],
            "marginal_only_observables": data["marginal_only_observables"],
            "stable_by_surrogate": {
                surrogate_class: data["surrogates"][surrogate_class]["stable_observables"]
                for surrogate_class in SURROGATE_CLASSES
            },
            "z_by_surrogate": {
                surrogate_class: data["surrogates"][surrogate_class]["z"]
                for surrogate_class in SURROGATE_CLASSES
            },
        }
    return out


def run(args: argparse.Namespace) -> dict:
    root_rng = np.random.default_rng(args.seed)
    sequences = build_sequences(args, root_rng)
    perimeters = {}
    for name, values in sequences.items():
        perimeters[name] = analyze_sequence(name, values, args, root_rng)

    output = {
        "experiment": "logistic_surrogate_contract_gate",
        "category": "gate_falsification_surrogate_contract",
        "question": "Does one-sided logistic support survive temporal-structure-preserving surrogates?",
        "observables_registry": "not used for canonical observables",
        "observables_native_version": OBSERVABLES_NATIVE_VERSION,
        "observables_used": OBS_NAMES,
        "surrogate_classes": SURROGATE_CLASSES,
        "params": vars(args),
        "matrix": compact(perimeters),
        "perimeters": perimeters,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_native_version={OBSERVABLES_NATIVE_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print("perimeter n contract_stable marginal_only stable_by_surrogate")
    for name, row in output["matrix"].items():
        print(
            f"{name:>29s} "
            f"{row['n']:>5d} "
            f"{','.join(row['contract_stable_observables']) or '[]':>32s} "
            f"{','.join(row['marginal_only_observables']) or '[]':>32s} "
            f"{row['stable_by_surrogate']}"
        )
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-values", type=int, default=4096)
    parser.add_argument("--n-returns", type=int, default=4096)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--recurrence-max-points", type=int, default=300)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=202605071042)
    parser.add_argument("--out", default="tools/data/logistic_surrogate_contract_gate_20260507_1042.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
