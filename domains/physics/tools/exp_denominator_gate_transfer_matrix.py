#!/usr/bin/env python3
"""
exp_denominator_gate_transfer_matrix.py

Reusable META audit for the denominator gate transfer matrix.

The experiment moves the original-vs-shuffle denominator gate away from the
GUE/Poisson BOUNDARY perimeter. Each perimeter has a coherent endpoint and an
illusory endpoint built as a permutation of the same gap multiset. That keeps
the one-point distribution fixed and isolates ordering support.

Measured for each perimeter:
- canonical observables from observables_registry.py;
- original-vs-shuffle z-score for each observable;
- endpoint-stable observable set under |z| >= z_min;
- endpoint classification using all observables and endpoint-gated observables;
- beta layer ambiguity between coherent and illusory endpoints.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from observables_registry import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    compute_canonical,
)


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
PHI = (1.0 + 5.0**0.5) / 2.0


def normalize(gaps: np.ndarray) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = np.maximum(gaps, 1e-12)
    mean = float(np.mean(gaps))
    return gaps / mean if mean > 1e-15 else gaps


def golden_beatty(n_gaps: int, rng: np.random.Generator) -> np.ndarray:
    phase = float(rng.random())
    n = np.arange(n_gaps + 1, dtype=float) + phase
    positions = np.floor(n * PHI)
    return normalize(np.diff(positions))


def periodic_triad(n_gaps: int, rng: np.random.Generator) -> np.ndarray:
    base = np.array([0.55, 1.0, 1.45, 1.0, 0.75, 1.25], dtype=float)
    shift = int(rng.integers(0, len(base)))
    tiled = np.tile(np.roll(base, shift), int(np.ceil(n_gaps / len(base))))[:n_gaps]
    jitter = rng.normal(0.0, 0.015, size=n_gaps)
    return normalize(tiled + jitter)


def markov_alternating(n_gaps: int, rng: np.random.Generator) -> np.ndarray:
    vals = np.array([0.62, 1.38], dtype=float)
    state = int(rng.integers(0, 2))
    out = np.empty(n_gaps, dtype=float)
    for i in range(n_gaps):
        out[i] = vals[state] + rng.normal(0.0, 0.03)
        if rng.random() < 0.88:
            state = 1 - state
    return normalize(out)


def ar1_continuity(n_gaps: int, rng: np.random.Generator) -> np.ndarray:
    rho = 0.86
    x = np.empty(n_gaps, dtype=float)
    x[0] = rng.normal()
    noise_scale = (1.0 - rho * rho) ** 0.5
    for i in range(1, n_gaps):
        x[i] = rho * x[i - 1] + noise_scale * rng.normal()
    return normalize(np.exp(0.42 * x))


PERIMETERS = {
    "DUALITA_golden": golden_beatty,
    "R_periodic_triad": periodic_triad,
    "T_markov_alternating": markov_alternating,
    "E_ar1_continuity": ar1_continuity,
}


def beta_layer(base: np.ndarray, beta: float, rng: np.random.Generator) -> np.ndarray:
    illusory = rng.permutation(base)
    if beta <= 0.0:
        out = base.copy()
    elif beta >= 1.0:
        out = illusory.copy()
    else:
        mask = rng.random(len(base)) < beta
        out = base.copy()
        out[mask] = illusory[mask]
    return normalize(out)


def z_against_shuffle(
    gaps: np.ndarray,
    n_baseline: int,
    rng: np.random.Generator,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    original = compute_canonical(gaps)
    baseline_vals = {name: [] for name in OBS_NAMES}
    for _ in range(n_baseline):
        obs = compute_canonical(rng.permutation(gaps))
        for name in OBS_NAMES:
            baseline_vals[name].append(obs[name])

    shuffle_std = {}
    z = {}
    for name in OBS_NAMES:
        vals = np.array(baseline_vals[name], dtype=float)
        mean = float(np.mean(vals))
        sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        shuffle_std[name] = sd
        z[name] = float((original[name] - mean) / sd) if sd > 1e-15 else 0.0
    return original, shuffle_std, z


def vector(row: dict, names: list[str]) -> np.ndarray:
    return np.array([row["observables"][name] for name in names], dtype=float)


def classify_layers(rows: list[dict], obs_names: list[str], ambiguous_margin: float) -> dict:
    if not obs_names:
        return {
            "observables": [],
            "endpoint_distance": 0.0,
            "layers": {},
            "ambiguous_beta": [],
        }

    by_beta: dict[float, list[dict]] = {}
    for row in rows:
        by_beta.setdefault(float(row["beta"]), []).append(row)

    coherent_vectors = np.array([vector(row, obs_names) for row in by_beta[0.0]], dtype=float)
    illusory_vectors = np.array([vector(row, obs_names) for row in by_beta[1.0]], dtype=float)
    endpoints = np.vstack([coherent_vectors, illusory_vectors])
    scale = np.std(endpoints, axis=0, ddof=1)
    scale[scale <= 1e-15] = 1.0
    coherent_centroid = np.mean(coherent_vectors, axis=0)
    illusory_centroid = np.mean(illusory_vectors, axis=0)
    endpoint_distance = float(np.linalg.norm((illusory_centroid - coherent_centroid) / scale))

    layers = {}
    ambiguous_beta = []
    for beta, beta_rows in sorted(by_beta.items()):
        coords = []
        margins = []
        labels = []
        for row in beta_rows:
            x = vector(row, obs_names)
            d_coherent = float(np.linalg.norm((x - coherent_centroid) / scale))
            d_illusory = float(np.linalg.norm((x - illusory_centroid) / scale))
            denom = d_coherent + d_illusory
            coord = float((d_coherent - d_illusory) / denom) if denom > 1e-15 else 0.0
            margin = float(abs(d_coherent - d_illusory) / denom) if denom > 1e-15 else 0.0
            coords.append(coord)
            margins.append(margin)
            labels.append("coherent" if d_coherent < d_illusory else "illusory")
        ambiguous_fraction = float(np.mean(np.array(margins) < ambiguous_margin))
        if ambiguous_fraction >= 0.5:
            ambiguous_beta.append(beta)
        layers[f"{beta:.3f}"] = {
            "coordinate_mean": float(np.mean(coords)),
            "coordinate_std": float(np.std(coords, ddof=1)) if len(coords) > 1 else 0.0,
            "margin_mean": float(np.mean(margins)),
            "ambiguous_fraction": ambiguous_fraction,
            "illusory_label_fraction": float(np.mean(np.array(labels) == "illusory")),
        }

    return {
        "observables": obs_names,
        "endpoint_distance": endpoint_distance,
        "layers": layers,
        "ambiguous_beta": ambiguous_beta,
    }


def summarize_gate(rows: list[dict], z_min: float) -> dict:
    by_beta: dict[float, list[dict]] = {}
    for row in rows:
        by_beta.setdefault(float(row["beta"]), []).append(row)

    layers = {}
    for beta, beta_rows in sorted(by_beta.items()):
        stable_counts = []
        stable_freq = {name: [] for name in OBS_NAMES}
        z_values = {name: [] for name in OBS_NAMES}
        for row in beta_rows:
            stable = [name for name in OBS_NAMES if abs(row["z"][name]) >= z_min]
            stable_counts.append(len(stable))
            for name in OBS_NAMES:
                stable_freq[name].append(1.0 if name in stable else 0.0)
                z_values[name].append(row["z"][name])
        layers[f"{beta:.3f}"] = {
            "stable_count_mean": float(np.mean(stable_counts)),
            "stable_count_std": float(np.std(stable_counts, ddof=1)) if len(stable_counts) > 1 else 0.0,
            "stable_frequency": {name: float(np.mean(vals)) for name, vals in stable_freq.items()},
            "z_mean": {name: float(np.mean(vals)) for name, vals in z_values.items()},
        }

    endpoint_stable = []
    coherent_rows = by_beta[0.0]
    illusory_rows = by_beta[1.0]
    endpoint_one_sided = []
    for name in OBS_NAMES:
        coherent_freq = np.mean([1.0 if abs(row["z"][name]) >= z_min else 0.0 for row in coherent_rows])
        illusory_freq = np.mean([1.0 if abs(row["z"][name]) >= z_min else 0.0 for row in illusory_rows])
        if coherent_freq >= 0.75 and illusory_freq < 0.25:
            endpoint_one_sided.append(name)
        if coherent_freq >= 0.75 and illusory_freq >= 0.75:
            endpoint_stable.append(name)

    return {
        "z_min": z_min,
        "endpoint_stable_observables": endpoint_stable,
        "coherent_one_sided_observables": endpoint_one_sided,
        "layers": layers,
    }


def analyze_perimeter(name: str, generator, args: argparse.Namespace, rng: np.random.Generator) -> dict:
    rows = []
    betas = [float(x) for x in np.linspace(0.0, 1.0, args.n_beta)]
    for rep in range(args.n_replicates):
        base = generator(args.n_gaps, np.random.default_rng(rng.integers(0, 2**63 - 1)))
        for beta in betas:
            gaps = beta_layer(base, beta, np.random.default_rng(rng.integers(0, 2**63 - 1)))
            obs, shuffle_std, z = z_against_shuffle(
                gaps,
                args.n_baseline,
                np.random.default_rng(rng.integers(0, 2**63 - 1)),
            )
            rows.append(
                {
                    "perimeter": name,
                    "replicate": rep,
                    "beta": beta,
                    "observables": obs,
                    "shuffle_std": shuffle_std,
                    "z": z,
                    "stable_observables": [obs_name for obs_name in OBS_NAMES if abs(z[obs_name]) >= args.z_min],
                }
            )

    gate = summarize_gate(rows, args.z_min)
    all_classification = classify_layers(rows, OBS_NAMES, args.ambiguous_margin)
    one_sided_classification = classify_layers(rows, gate["coherent_one_sided_observables"], args.ambiguous_margin)
    return {
        "gate": gate,
        "classification_all_observables": all_classification,
        "classification_one_sided_gated": one_sided_classification,
        "rows": rows,
    }


def compact_matrix(perimeters: dict) -> dict:
    matrix = {}
    for name, data in perimeters.items():
        gate = data["gate"]
        class_all = data["classification_all_observables"]
        class_gate = data["classification_one_sided_gated"]
        matrix[name] = {
            "coherent_one_sided_observables": gate["coherent_one_sided_observables"],
            "endpoint_stable_observables": gate["endpoint_stable_observables"],
            "endpoint_distance_all": class_all["endpoint_distance"],
            "endpoint_distance_one_sided_gated": class_gate["endpoint_distance"],
            "ambiguous_beta_all": class_all["ambiguous_beta"],
            "ambiguous_beta_one_sided_gated": class_gate["ambiguous_beta"],
            "stable_count_coherent": gate["layers"]["0.000"]["stable_count_mean"],
            "stable_count_illusory": gate["layers"]["1.000"]["stable_count_mean"],
        }
    return matrix


def evaluate_contract(matrix: dict, args: argparse.Namespace) -> dict:
    rows = {}
    transfer = 0
    blank = 0
    fall = 0
    for name, row in matrix.items():
        one_sided_count = len(row["coherent_one_sided_observables"])
        illusory_residue = float(row["stable_count_illusory"])
        endpoint_distance = float(row["endpoint_distance_one_sided_gated"])
        ambiguous_beta = row["ambiguous_beta_one_sided_gated"]

        has_order = one_sided_count >= args.min_one_sided
        null_suppressed = illusory_residue <= args.illusory_residue_max
        separated = endpoint_distance >= args.endpoint_distance_min
        has_blank = bool(ambiguous_beta)

        if not has_order or not separated:
            state = "fall"
            fall += 1
        elif not null_suppressed:
            state = "blank"
            blank += 1
        else:
            state = "transfer"
            transfer += 1

        rows[name] = {
            "state": state,
            "one_sided_count": one_sided_count,
            "illusory_residue": illusory_residue,
            "endpoint_distance": endpoint_distance,
            "ambiguous_beta": ambiguous_beta,
            "checks": {
                "has_order": has_order,
                "null_suppressed": null_suppressed,
                "separated": separated,
                "has_blank_layer": has_blank,
            },
        }

    return {
        "thresholds": {
            "z_min": args.z_min,
            "min_one_sided": args.min_one_sided,
            "illusory_residue_max": args.illusory_residue_max,
            "endpoint_distance_min": args.endpoint_distance_min,
            "ambiguous_margin": args.ambiguous_margin,
        },
        "lexicon": {
            "transfer": "one-sided order observables plus suppressed non-zero null residue",
            "blank": "contract not decidable under current thresholds or explicit ambiguous beta layer",
            "fall": "missing order observables or insufficient endpoint separation",
            "forbidden_wording": "Do not call the null pole collapsed unless illusory_residue is exactly 0. Use suppressed/residual otherwise.",
        },
        "summary": {
            "perimeters": len(matrix),
            "transfer": transfer,
            "blank": blank,
            "fall": fall,
        },
        "rows": rows,
    }


def run(args: argparse.Namespace) -> dict:
    root_rng = np.random.default_rng(args.seed)
    perimeters = {}
    for name, generator in PERIMETERS.items():
        perimeters[name] = analyze_perimeter(name, generator, args, root_rng)

    output = {
        "experiment": "denominator_gate_transfer_matrix",
        "category": "gate_transferability",
        "question": "Which parts of the denominator gate transfer outside BOUNDARY?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "params": vars(args),
        "matrix": compact_matrix(perimeters),
        "perimeters": perimeters,
    }
    output["gate_transfer_contract"] = evaluate_contract(output["matrix"], args)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print("perimeter one_sided stable0 stable1 dist_all dist_gate ambiguous_gate")
    for name, row in output["matrix"].items():
        print(
            f"{name:>21s} "
            f"{','.join(row['coherent_one_sided_observables']) or '[]':>22s} "
            f"{row['stable_count_coherent']:>7.3f} "
            f"{row['stable_count_illusory']:>7.3f} "
            f"{row['endpoint_distance_all']:>8.3f} "
            f"{row['endpoint_distance_one_sided_gated']:>9.3f} "
            f"{row['ambiguous_beta_one_sided_gated']}"
        )
    print(f"saved {out_path}")
    print(f"contract_summary={output['gate_transfer_contract']['summary']}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-gaps", type=int, default=4096)
    parser.add_argument("--n-replicates", type=int, default=20)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=32)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--min-one-sided", type=int, default=1)
    parser.add_argument("--illusory-residue-max", type=float, default=0.5)
    parser.add_argument("--endpoint-distance-min", type=float, default=2.0)
    parser.add_argument("--ambiguous-margin", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=202605070901)
    parser.add_argument("--out", default="tools/data/denominator_gate_transfer_matrix.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
