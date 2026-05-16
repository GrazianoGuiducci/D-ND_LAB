#!/usr/bin/env python3
"""
exp_boundary_mixture_gate.py

Reusable META/BOUNDARY audit for the GUE-Poisson boundary.

Question:
    Does the GUE/Poisson boundary remain a clean two-class split after the
    original-vs-shuffle denominator gate, or is the mixed region an operational
    third state where canonical observables lose stable denominators?

The script uses only canonical observables from observables_registry.py.
It builds synthetic mixtures by replacing a fraction beta of unfolded GUE
spacings with Poisson spacings, then measures:

- canonical observable vectors;
- original-vs-shuffle z-score per observable;
- endpoint separability in all observables and in gate-stable observables;
- ambiguity of each beta layer relative to pure GUE and pure Poisson centroids.
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


def gue_spacings(matrix_size: int, min_spacings: int, rng: np.random.Generator) -> np.ndarray:
    """Generate unfolded GUE spacings by concatenating independent matrices."""
    parts: list[np.ndarray] = []
    edge = max(2, matrix_size // 10)
    while sum(len(x) for x in parts) < min_spacings:
        real = rng.standard_normal((matrix_size, matrix_size))
        imag = rng.standard_normal((matrix_size, matrix_size))
        h = real + 1j * imag
        h = (h + h.conj().T) / (2.0 * np.sqrt(matrix_size))
        eigs = np.sort(np.linalg.eigvalsh(h).real)
        bulk = eigs[edge:-edge]
        gaps = np.diff(bulk)
        mean = float(np.mean(gaps))
        if mean > 1e-15:
            parts.append(gaps / mean)
    return np.concatenate(parts)[:min_spacings].astype(float)


def mixture_spacings(gue: np.ndarray, poisson: np.ndarray, beta: float, rng: np.random.Generator) -> np.ndarray:
    """Return a beta Poisson / (1-beta) GUE spacing sequence with mean spacing 1."""
    if len(gue) != len(poisson):
        raise ValueError("gue and poisson arrays must have the same length")
    mask = rng.random(len(gue)) < beta
    out = gue.copy()
    out[mask] = poisson[mask]
    mean = float(np.mean(out))
    return out / mean if mean > 1e-15 else out


def z_against_shuffle(
    gaps: np.ndarray,
    n_baseline: int,
    rng: np.random.Generator,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return original observables, shuffle baseline std, and original-vs-shuffle z."""
    original = compute_canonical(gaps)
    baseline_vals = {name: [] for name in OBS_NAMES}
    for _ in range(n_baseline):
        obs = compute_canonical(rng.permutation(gaps))
        for name in OBS_NAMES:
            baseline_vals[name].append(obs[name])

    std = {}
    z = {}
    for name in OBS_NAMES:
        vals = np.array(baseline_vals[name], dtype=float)
        mean = float(np.mean(vals))
        sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        std[name] = sd
        z[name] = float((original[name] - mean) / sd) if sd > 1e-15 else 0.0
    return original, std, z


def vector(row: dict, names: list[str]) -> np.ndarray:
    return np.array([row["observables"][name] for name in names], dtype=float)


def classify_layers(rows: list[dict], obs_names: list[str]) -> dict:
    """Classify each beta layer by standardized distance to endpoint centroids."""
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

    gue_vectors = np.array([vector(row, obs_names) for row in by_beta[0.0]], dtype=float)
    poi_vectors = np.array([vector(row, obs_names) for row in by_beta[1.0]], dtype=float)
    all_endpoint = np.vstack([gue_vectors, poi_vectors])
    scale = np.std(all_endpoint, axis=0, ddof=1)
    scale[scale <= 1e-15] = 1.0
    gue_centroid = np.mean(gue_vectors, axis=0)
    poi_centroid = np.mean(poi_vectors, axis=0)
    endpoint_distance = float(np.linalg.norm((poi_centroid - gue_centroid) / scale))

    layers = {}
    ambiguous_beta = []
    for beta, beta_rows in sorted(by_beta.items()):
        coords = []
        margins = []
        labels = []
        for row in beta_rows:
            x = vector(row, obs_names)
            d_gue = float(np.linalg.norm((x - gue_centroid) / scale))
            d_poi = float(np.linalg.norm((x - poi_centroid) / scale))
            denom = d_gue + d_poi
            coord = float((d_gue - d_poi) / denom) if denom > 1e-15 else 0.0
            margin = float(abs(d_gue - d_poi) / denom) if denom > 1e-15 else 0.0
            coords.append(coord)
            margins.append(margin)
            labels.append("gue" if d_gue < d_poi else "poisson")
        ambiguous_fraction = float(np.mean(np.array(margins) < 0.15))
        if ambiguous_fraction >= 0.5:
            ambiguous_beta.append(beta)
        layers[f"{beta:.3f}"] = {
            "coordinate_mean": float(np.mean(coords)),
            "coordinate_std": float(np.std(coords, ddof=1)) if len(coords) > 1 else 0.0,
            "margin_mean": float(np.mean(margins)),
            "ambiguous_fraction": ambiguous_fraction,
            "poisson_label_fraction": float(np.mean(np.array(labels) == "poisson")),
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
        for row in beta_rows:
            stable = [name for name in OBS_NAMES if abs(row["z"][name]) >= z_min]
            stable_counts.append(len(stable))
            for name in OBS_NAMES:
                stable_freq[name].append(1.0 if name in stable else 0.0)
        layers[f"{beta:.3f}"] = {
            "stable_count_mean": float(np.mean(stable_counts)),
            "stable_count_std": float(np.std(stable_counts, ddof=1)) if len(stable_counts) > 1 else 0.0,
            "stable_frequency": {name: float(np.mean(vals)) for name, vals in stable_freq.items()},
        }

    endpoint_stable = []
    for name in OBS_NAMES:
        endpoint_rows = by_beta[0.0] + by_beta[1.0]
        freq = np.mean([1.0 if abs(row["z"][name]) >= z_min else 0.0 for row in endpoint_rows])
        if freq >= 0.75:
            endpoint_stable.append(name)

    return {
        "z_min": z_min,
        "endpoint_stable_observables": endpoint_stable,
        "layers": layers,
    }


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    betas = [float(x) for x in np.linspace(0.0, 1.0, args.n_beta)]
    rows = []

    for rep in range(args.n_replicates):
        rep_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
        gue = gue_spacings(args.gue_matrix_size, args.n_gaps, rep_rng)
        poisson = rep_rng.exponential(1.0, size=args.n_gaps)
        poisson = poisson / float(np.mean(poisson))
        for beta in betas:
            layer_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
            gaps = mixture_spacings(gue, poisson, beta, layer_rng)
            obs, shuffle_std, z = z_against_shuffle(
                gaps,
                n_baseline=args.n_baseline,
                rng=np.random.default_rng(rng.integers(0, 2**63 - 1)),
            )
            rows.append(
                {
                    "replicate": rep,
                    "beta": beta,
                    "observables": obs,
                    "shuffle_std": shuffle_std,
                    "z": z,
                    "stable_observables": [name for name in OBS_NAMES if abs(z[name]) >= args.z_min],
                }
            )

    gate = summarize_gate(rows, args.z_min)
    all_classification = classify_layers(rows, OBS_NAMES)
    gated_classification = classify_layers(rows, gate["endpoint_stable_observables"])

    output = {
        "experiment": "boundary_mixture_gate",
        "question": "Is the GUE-Poisson mixed layer cleanly classifiable after denominator gating?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "params": vars(args),
        "gate": gate,
        "classification_all_observables": all_classification,
        "classification_endpoint_gated": gated_classification,
        "rows": rows,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print(f"endpoint_stable_observables={gate['endpoint_stable_observables']}")
    print(
        "endpoint_distance_all="
        f"{all_classification['endpoint_distance']:.3f} "
        "endpoint_distance_gated="
        f"{gated_classification['endpoint_distance']:.3f}"
    )
    if gate["endpoint_stable_observables"]:
        print("beta stable_count margin_gated ambiguous_gated poisson_fraction_gated")
    else:
        print("endpoint gate is empty; printing all-observable classification")
        print("beta stable_count margin_all ambiguous_all poisson_fraction_all")
    for beta in betas:
        key = f"{beta:.3f}"
        stable_count = gate["layers"][key]["stable_count_mean"]
        source = gated_classification if gate["endpoint_stable_observables"] else all_classification
        layer = source["layers"].get(key, {})
        print(
            f"{beta:>4.2f} {stable_count:>12.3f} "
            f"{layer.get('margin_mean', 0.0):>12.3f} "
            f"{layer.get('ambiguous_fraction', 0.0):>15.3f} "
            f"{layer.get('poisson_label_fraction', 0.0):>21.3f}"
        )
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-gaps", type=int, default=1536)
    parser.add_argument("--n-replicates", type=int, default=16)
    parser.add_argument("--gue-matrix-size", type=int, default=180)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=20260507)
    parser.add_argument("--out", default="tools/data/boundary_mixture_gate.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
