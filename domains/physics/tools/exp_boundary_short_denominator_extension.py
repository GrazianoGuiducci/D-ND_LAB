#!/usr/bin/env python3
"""
Extend the three short BOUNDARY denominator rows opened by the 15:48 audit.

This is deliberately narrower than the 13-row semi-real gate. It repairs the
denominator at the source row for percolation, random_matrix, and zeta_zeros,
then applies the same canonical observable gate used by
exp_semireal_boundary_transfer_gate.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from exp_semireal_boundary_transfer_gate import evaluate_matrix
from exp_semireal_order_denominator_gate import analyze_sequence, compact, normalize
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
TARGET_ROWS = ("percolation:cycle_9", "random_matrix:cycle_7", "zeta_zeros:cycle_4")


def largest_cluster_sizes(n_samples: int, lattice_size: int, p: float, rng: np.random.Generator) -> np.ndarray:
    try:
        from scipy import ndimage
    except ImportError as exc:
        raise RuntimeError("scipy.ndimage is required for the percolation extension") from exc

    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=int)
    sizes = np.empty(n_samples, dtype=float)
    for i in range(n_samples):
        grid = rng.random((lattice_size, lattice_size)) < p
        labels, n_labels = ndimage.label(grid, structure=structure)
        if n_labels == 0:
            sizes[i] = 0.0
            continue
        counts = np.bincount(labels.ravel())
        sizes[i] = float(np.max(counts[1:])) if len(counts) > 1 else 0.0
    return normalize(sizes)


def gue_spacing_blocks(n_gaps: int, matrix_size: int, rng: np.random.Generator) -> np.ndarray:
    spacings: list[np.ndarray] = []
    while sum(len(block) for block in spacings) < n_gaps:
        a = rng.normal(size=(matrix_size, matrix_size)) + 1j * rng.normal(size=(matrix_size, matrix_size))
        h = (a + a.conj().T) / (2.0 * np.sqrt(matrix_size))
        eig = np.linalg.eigvalsh(h)
        block = np.diff(np.sort(np.real(eig)))
        block = block[np.isfinite(block) & (block > 0)]
        if len(block):
            spacings.append(normalize(block))
    return normalize(np.concatenate(spacings)[:n_gaps])


def zeta_zero_spacings(n_gaps: int) -> np.ndarray:
    try:
        import mpmath as mp
    except ImportError as exc:
        raise RuntimeError("mpmath is required for the zeta extension") from exc

    zeros = np.empty(n_gaps + 1, dtype=float)
    for i in range(n_gaps + 1):
        zeros[i] = float(mp.im(mp.zetazero(i + 1)))
    return normalize(np.diff(zeros))


def build_sequences(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, dict[str, Any]]:
    child_rngs = {
        name: np.random.default_rng(rng.integers(0, 2**63 - 1))
        for name in TARGET_ROWS
    }
    return {
        "percolation:cycle_9": {
            "base": largest_cluster_sizes(args.n_gaps, args.percolation_lattice, args.percolation_p, child_rngs["percolation:cycle_9"]),
            "extension": {
                "generator": "site_percolation_largest_cluster_sizes",
                "lattice_size": args.percolation_lattice,
                "p": args.percolation_p,
                "n_samples": args.n_gaps,
            },
        },
        "random_matrix:cycle_7": {
            "base": gue_spacing_blocks(args.n_gaps, args.gue_matrix_size, child_rngs["random_matrix:cycle_7"]),
            "extension": {
                "generator": "gue_spacing_blocks",
                "matrix_size": args.gue_matrix_size,
                "target_n_gaps": args.n_gaps,
            },
        },
        "zeta_zeros:cycle_4": {
            "base": zeta_zero_spacings(args.zeta_gaps),
            "extension": {
                "generator": "mpmath.zetazero_first_spacings",
                "n_gaps": args.zeta_gaps,
            },
        },
    }


def source_lookup(path: Path) -> dict[str, dict[str, Any]]:
    with path.open() as f:
        data = json.load(f)
    return {
        row["row"]: row
        for row in data.get("rows", [])
        if row.get("row") in TARGET_ROWS
    }


def support_tier(row: dict[str, Any]) -> str:
    n_obs = len(row.get("coherent_one_sided_observables", []))
    endpoint = float(row.get("endpoint_distance_one_sided_gated") or 0.0)
    stable = float(row.get("stable_count_coherent") or 0.0)
    if n_obs >= 4 and endpoint >= 3.5 and stable >= 4.0:
        return "strong_multi_observable"
    if n_obs >= 3 and endpoint >= 3.0 and stable >= 3.0:
        return "medium_multi_observable"
    return "thin_observable_support"


def summarize_transition(name: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    beta = [round(float(x), 1) for x in after.get("ambiguous_beta_one_sided_gated", [])]
    one_sided_count = len(after.get("coherent_one_sided_observables", []))
    tier = support_tier(after)
    if beta:
        extension_state = "beta_chart_recovered"
    elif one_sided_count == 0:
        extension_state = "support_falls_after_extension"
    elif tier == "thin_observable_support":
        extension_state = "thin_persists"
    else:
        extension_state = "support_thickens_beta_blank"
    return {
        "row": name,
        "before_n_gaps": before.get("n_gaps"),
        "after_n_gaps": after.get("n_gaps"),
        "before_one_sided": before.get("one_sided_count"),
        "after_one_sided": one_sided_count,
        "before_endpoint_distance": before.get("endpoint_distance"),
        "after_endpoint_distance": after.get("endpoint_distance_one_sided_gated"),
        "before_stable_count_coherent": before.get("stable_count_coherent"),
        "after_stable_count_coherent": after.get("stable_count_coherent"),
        "after_stable_count_illusory": after.get("stable_count_illusory"),
        "after_beta": beta,
        "after_support_tier": tier,
        "extension_state": extension_state,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    before = source_lookup(Path(args.source_audit))
    sequence_specs = build_sequences(args, rng)

    perimeters = {}
    extension_meta = {}
    for name, spec in sequence_specs.items():
        base = np.asarray(spec["base"], dtype=float)
        perimeters[name] = analyze_sequence(name, base, args, rng)
        extension_meta[name] = {
            **spec["extension"],
            "actual_n_gaps": int(len(base)),
            "mean": float(np.mean(base)),
            "variance": float(np.var(base)),
        }

    matrix = compact(perimeters)
    evaluation = evaluate_matrix(matrix, args)
    transitions = [
        summarize_transition(name, before.get(name, {}), evaluation["rows"][name])
        for name in TARGET_ROWS
    ]
    state_counts: dict[str, int] = {}
    for row in transitions:
        state_counts[row["extension_state"]] = state_counts.get(row["extension_state"], 0) + 1

    verdict = "DENOMINATOR_EXTENSION_RESOLVES_THINNESS"
    if state_counts.get("thin_persists", 0) == len(TARGET_ROWS):
        verdict = "AUTONOMOUS_THIN_BLANK_AFTER_EXTENSION"
    elif state_counts.get("thin_persists", 0) > 0:
        verdict = "MIXED_EXTENSION"

    output = {
        "experiment": "boundary_short_denominator_extension",
        "question": "Do the three short support-without-beta blanks remain thin after source-denominator extension?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "source_audit": args.source_audit,
        "target_rows": list(TARGET_ROWS),
        "params": vars(args),
        "observable_contract": {
            "claim": "blank_thin_support survives only if thin support persists after denominator extension",
            "observable": "canonical one-sided support, endpoint distance, beta chart on extended source rows",
            "operator": "source-denominator extension plus semireal boundary transfer gate",
            "denominator": "three rows from the 15:48 short-denominator audit",
            "non_possible": "promoting blank_thin_support when support thickens or beta chart appears after extension",
            "not_tested": "global 13-row boundary redesign, V_c fit, source GUE/Poisson label validity",
        },
        "label_policy": "Source labels are not decision fields; row names select only the 15:48 denominator-short perimeter.",
        "extension_meta": extension_meta,
        "matrix": matrix,
        "evaluation": evaluation,
        "transitions": transitions,
        "state_counts": state_counts,
        "verdict": verdict,
        "perimeters": perimeters if args.include_perimeters else {},
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print(f"verdict={verdict}")
    print(f"state_counts={state_counts}")
    for row in transitions:
        print(
            f"{row['row']}\t{row['before_n_gaps']}->{row['after_n_gaps']}\t"
            f"{row['before_one_sided']}->{row['after_one_sided']}\t"
            f"dist={row['after_endpoint_distance']:.3f}\tbeta={row['after_beta']}\t"
            f"{row['extension_state']}"
        )
    print(f"saved {out}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-audit", default="tools/data/boundary_blank_thin_support_audit_20260509_1548.json")
    parser.add_argument("--n-gaps", type=int, default=1024)
    parser.add_argument("--zeta-gaps", type=int, default=1024)
    parser.add_argument("--percolation-lattice", type=int, default=48)
    parser.add_argument("--percolation-p", type=float, default=0.5927)
    parser.add_argument("--gue-matrix-size", type=int, default=160)
    parser.add_argument("--n-replicates", type=int, default=12)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.75)
    parser.add_argument("--endpoint-distance-min", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=202605091556)
    parser.add_argument("--include-perimeters", action="store_true")
    parser.add_argument("--out", default="tools/data/boundary_short_denominator_extension_20260509_1556.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
