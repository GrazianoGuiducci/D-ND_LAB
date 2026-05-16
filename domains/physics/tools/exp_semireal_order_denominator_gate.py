#!/usr/bin/env python3
"""
exp_semireal_order_denominator_gate.py

Falsification attempt for ORDER_DENOMINATOR_GATE on non-synthetic / semi-real
ordered sequences. The coherent endpoint is the observed order of each sequence;
the illusory endpoint is a marginal-preserving permutation. The same
original-vs-shuffle denominator gate used in the prior reports is applied to
canonical observables from observables_registry.py.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from observables_registry import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    compute_canonical,
)


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())


def normalize(gaps: np.ndarray) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = np.maximum(gaps, 1e-12)
    mean = float(np.mean(gaps))
    return gaps / mean if mean > 1e-15 else gaps


def sieve_primes_for_count(n_primes: int) -> np.ndarray:
    if n_primes < 6:
        limit = 20
    else:
        limit = int(n_primes * (math.log(n_primes) + math.log(math.log(n_primes))) * 1.25)
    while True:
        sieve = np.ones(limit + 1, dtype=bool)
        sieve[:2] = False
        for p in range(2, int(limit**0.5) + 1):
            if sieve[p]:
                sieve[p * p : limit + 1 : p] = False
        primes = np.flatnonzero(sieve)
        if len(primes) >= n_primes:
            return primes[:n_primes].astype(float)
        limit *= 2


def prime_gap_sequence(n_gaps: int) -> np.ndarray:
    primes = sieve_primes_for_count(n_gaps + 1)
    return normalize(np.diff(primes))


def zeta_zero_spacings(n_gaps: int) -> np.ndarray:
    try:
        import mpmath as mp
    except ImportError as exc:
        raise RuntimeError("mpmath is required for zeta_zero_spacings") from exc

    zeros = np.empty(n_gaps + 1, dtype=float)
    for i in range(n_gaps + 1):
        zeros[i] = float(mp.im(mp.zetazero(i + 1)))
    return normalize(np.diff(zeros))


def logistic_return_intervals(n_gaps: int, rng: np.random.Generator) -> np.ndarray:
    # Return intervals to a high-density-edge event in the fully chaotic logistic map.
    threshold = 0.95
    burn = 2000
    needed = n_gaps + 1
    returns: list[int] = []
    last_hit: int | None = None
    x = float(rng.random())
    i = 0
    max_steps = 50_000_000
    while len(returns) < needed and i < max_steps:
        x = 4.0 * x * (1.0 - x)
        if i >= burn and x > threshold:
            if last_hit is not None:
                returns.append(i - last_hit)
            last_hit = i
        i += 1
    if len(returns) < needed:
        raise RuntimeError(f"logistic generator produced {len(returns)} intervals, need {needed}")
    return normalize(np.array(returns[:n_gaps], dtype=float))


def beta_replace(base: np.ndarray, beta: float, rng: np.random.Generator) -> np.ndarray:
    illusory = rng.permutation(base)
    if beta <= 0.0:
        return base.copy()
    if beta >= 1.0:
        return illusory
    out = base.copy()
    mask = rng.random(len(base)) < beta
    out[mask] = illusory[mask]
    return normalize(out)


def z_against_shuffle(
    gaps: np.ndarray,
    n_baseline: int,
    rng: np.random.Generator,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, float]]:
    original = compute_canonical(gaps)
    baseline = {name: [] for name in OBS_NAMES}
    for _ in range(n_baseline):
        obs = compute_canonical(rng.permutation(gaps))
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
    return original, means, sds, z


def vector(row: dict, names: list[str]) -> np.ndarray:
    return np.array([row["observables"][name] for name in names], dtype=float)


def classify_layers(rows: list[dict], obs_names: list[str]) -> dict:
    if not obs_names:
        return {"observables": [], "endpoint_distance": 0.0, "layers": {}, "ambiguous_beta": []}

    by_beta: dict[float, list[dict]] = {}
    for row in rows:
        by_beta.setdefault(float(row["beta"]), []).append(row)

    coherent = np.array([vector(row, obs_names) for row in by_beta[0.0]], dtype=float)
    illusory = np.array([vector(row, obs_names) for row in by_beta[1.0]], dtype=float)
    endpoints = np.vstack([coherent, illusory])
    scale = np.std(endpoints, axis=0, ddof=1)
    scale[scale <= 1e-15] = 1.0
    coherent_centroid = np.mean(coherent, axis=0)
    illusory_centroid = np.mean(illusory, axis=0)
    endpoint_distance = float(np.linalg.norm((illusory_centroid - coherent_centroid) / scale))

    layers = {}
    ambiguous_beta = []
    for beta, beta_rows in sorted(by_beta.items()):
        margins = []
        labels = []
        coords = []
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
        ambiguous_fraction = float(np.mean(np.array(margins) < 0.15))
        if ambiguous_fraction >= 0.5:
            ambiguous_beta.append(beta)
        layers[f"{beta:.3f}"] = {
            "coordinate_mean": float(np.mean(coords)),
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
            "stable_frequency": {name: float(np.mean(vals)) for name, vals in stable_freq.items()},
            "z_mean": {name: float(np.mean(vals)) for name, vals in z_values.items()},
        }

    one_sided = []
    endpoint_stable = []
    coherent_rows = by_beta[0.0]
    illusory_rows = by_beta[1.0]
    for name in OBS_NAMES:
        coherent_freq = float(np.mean([abs(row["z"][name]) >= z_min for row in coherent_rows]))
        illusory_freq = float(np.mean([abs(row["z"][name]) >= z_min for row in illusory_rows]))
        if coherent_freq >= 0.75 and illusory_freq < 0.25:
            one_sided.append(name)
        if coherent_freq >= 0.75 and illusory_freq >= 0.75:
            endpoint_stable.append(name)

    return {
        "z_min": z_min,
        "coherent_one_sided_observables": one_sided,
        "endpoint_stable_observables": endpoint_stable,
        "layers": layers,
    }


def analyze_sequence(name: str, base: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict:
    rows = []
    betas = [float(x) for x in np.linspace(0.0, 1.0, args.n_beta)]
    for rep in range(args.n_replicates):
        rep_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
        for beta in betas:
            gaps = beta_replace(base, beta, rep_rng)
            obs, shuffle_mean, shuffle_std, z = z_against_shuffle(
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
                    "shuffle_mean": shuffle_mean,
                    "shuffle_std": shuffle_std,
                    "z": z,
                    "stable_observables": [obs_name for obs_name in OBS_NAMES if abs(z[obs_name]) >= args.z_min],
                }
            )

    gate = summarize_gate(rows, args.z_min)
    return {
        "source": {
            "n_gaps": int(len(base)),
            "mean": float(np.mean(base)),
            "variance": float(np.var(base)),
        },
        "gate": gate,
        "classification_all_observables": classify_layers(rows, OBS_NAMES),
        "classification_one_sided_gated": classify_layers(rows, gate["coherent_one_sided_observables"]),
        "rows": rows,
    }


def build_sequences(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, np.ndarray]:
    sequences = {
        "prime_gaps_first": prime_gap_sequence(args.n_gaps),
        "logistic_return_intervals": logistic_return_intervals(args.n_gaps, rng),
    }
    if args.include_zeta:
        sequences["zeta_zero_spacings_first"] = zeta_zero_spacings(args.zeta_gaps)
    return sequences


def compact(perimeters: dict) -> dict:
    out = {}
    for name, data in perimeters.items():
        gate = data["gate"]
        all_cls = data["classification_all_observables"]
        gated_cls = data["classification_one_sided_gated"]
        out[name] = {
            "n_gaps": data["source"]["n_gaps"],
            "coherent_one_sided_observables": gate["coherent_one_sided_observables"],
            "endpoint_stable_observables": gate["endpoint_stable_observables"],
            "stable_count_coherent": gate["layers"]["0.000"]["stable_count_mean"],
            "stable_count_illusory": gate["layers"]["1.000"]["stable_count_mean"],
            "z_mean_coherent": gate["layers"]["0.000"]["z_mean"],
            "z_mean_illusory": gate["layers"]["1.000"]["z_mean"],
            "endpoint_distance_all": all_cls["endpoint_distance"],
            "endpoint_distance_one_sided_gated": gated_cls["endpoint_distance"],
            "ambiguous_beta_one_sided_gated": gated_cls["ambiguous_beta"],
        }
    return out


def run(args: argparse.Namespace) -> dict:
    root_rng = np.random.default_rng(args.seed)
    sequences = build_sequences(args, root_rng)
    perimeters = {}
    for name, base in sequences.items():
        perimeters[name] = analyze_sequence(name, base, args, root_rng)

    output = {
        "experiment": "semireal_order_denominator_gate",
        "category": "gate_falsification_semireal",
        "question": "Does ORDER_DENOMINATOR_GATE survive on non-synthetic / semi-real ordered sequences?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "params": vars(args),
        "matrix": compact(perimeters),
        "perimeters": perimeters,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print("perimeter n one_sided stable0 stable1 dist_gate ambiguous_gate")
    for name, row in output["matrix"].items():
        print(
            f"{name:>28s} "
            f"{row['n_gaps']:>5d} "
            f"{','.join(row['coherent_one_sided_observables']) or '[]':>22s} "
            f"{row['stable_count_coherent']:>7.3f} "
            f"{row['stable_count_illusory']:>7.3f} "
            f"{row['endpoint_distance_one_sided_gated']:>9.3f} "
            f"{row['ambiguous_beta_one_sided_gated']}"
        )
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-gaps", type=int, default=4096)
    parser.add_argument("--zeta-gaps", type=int, default=1024)
    parser.add_argument("--include-zeta", action="store_true")
    parser.add_argument("--n-replicates", type=int, default=20)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=32)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=202605070923)
    parser.add_argument("--out", default="tools/data/semireal_order_denominator_gate_20260507_0923.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
