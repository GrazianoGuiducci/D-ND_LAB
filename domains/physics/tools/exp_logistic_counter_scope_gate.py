#!/usr/bin/env python3
"""
exp_logistic_counter_scope_gate.py

Regressive test for ORDER_DENOMINATOR_GATE on the logistic counter-scope.

The 09:23 run showed that canonical gap observables do not read denominator
support in logistic return intervals. This tool keeps the same
original-vs-shuffle denominator gate and changes only the observable contract:

- symbolic block entropy deficit;
- return-tail exponent;
- recurrence-plot diagonal statistics.

These are logistic-native observables, not aliases of the canonical
SR/SR2/L1/L2/triple_var registry names.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np


OBSERVABLES_NATIVE_VERSION = "logistic-native-1.0.0-2026-05-07"
OBS_NAMES = [
    "block_entropy_deficit_k4",
    "return_tail_alpha",
    "recurrence_diag_mean",
    "recurrence_determinism",
]


def normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return values
    values = values - float(np.min(values))
    scale = float(np.max(values))
    return values / scale if scale > 1e-15 else values


def logistic_orbit(n: int, rng: np.random.Generator, burn: int = 2000) -> np.ndarray:
    x = float(rng.random())
    out = np.empty(n, dtype=float)
    for i in range(n + burn):
        x = 4.0 * x * (1.0 - x)
        if i >= burn:
            out[i - burn] = x
    return out


def logistic_symbolic_itinerary(n: int, rng: np.random.Generator) -> np.ndarray:
    orbit = logistic_orbit(n, rng)
    return (orbit > 0.5).astype(float)


def logistic_return_intervals(n: int, rng: np.random.Generator) -> np.ndarray:
    threshold = 0.95
    burn = 2000
    returns: list[int] = []
    last_hit: int | None = None
    x = float(rng.random())
    i = 0
    max_steps = 50_000_000
    while len(returns) < n and i < max_steps:
        x = 4.0 * x * (1.0 - x)
        if i >= burn and x > threshold:
            if last_hit is not None:
                returns.append(i - last_hit)
            last_hit = i
        i += 1
    if len(returns) < n:
        raise RuntimeError(f"logistic generator produced {len(returns)} intervals, need {n}")
    return np.array(returns, dtype=float)


def quantile_symbols(values: np.ndarray, bins: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(np.unique(values)) <= bins:
        unique = {value: idx for idx, value in enumerate(sorted(set(values)))}
        return np.array([unique[value] for value in values], dtype=int)
    qs = np.quantile(values, np.linspace(0.0, 1.0, bins + 1)[1:-1])
    return np.searchsorted(qs, values, side="right").astype(int)


def block_entropy_deficit(values: np.ndarray, k: int = 4, bins: int = 4) -> float:
    symbols = quantile_symbols(values, bins)
    if len(symbols) < k + 1:
        return 0.0
    alphabet = max(2, int(np.max(symbols)) + 1)
    blocks = [tuple(symbols[i : i + k]) for i in range(len(symbols) - k + 1)]
    counts = np.array(list(Counter(blocks).values()), dtype=float)
    probs = counts / float(np.sum(counts))
    entropy = -float(np.sum(probs * np.log2(probs)))
    max_entropy = k * math.log2(alphabet)
    return float(max(0.0, 1.0 - entropy / max_entropy)) if max_entropy > 1e-15 else 0.0


def exceedance_intervals(values: np.ndarray, quantile: float = 0.95) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) < 3:
        return np.array([], dtype=float)
    threshold = float(np.quantile(values, quantile))
    hits = np.flatnonzero(values >= threshold)
    if len(hits) < 3:
        return np.array([], dtype=float)
    return np.diff(hits).astype(float)


def hill_tail_alpha(samples: np.ndarray) -> float:
    samples = np.asarray(samples, dtype=float)
    samples = samples[np.isfinite(samples) & (samples > 0)]
    if len(samples) < 16:
        return 0.0
    tail_count = max(8, int(0.20 * len(samples)))
    tail = np.sort(samples)[-tail_count:]
    xmin = float(tail[0])
    if xmin <= 0:
        return 0.0
    denom = float(np.mean(np.log(tail / xmin)))
    return float(1.0 / denom) if denom > 1e-15 else 0.0


def return_tail_alpha(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if np.all(values >= 1.0) and len(np.unique(values)) < max(64, len(values) // 2):
        intervals = values
    else:
        intervals = exceedance_intervals(values)
    return hill_tail_alpha(intervals)


def recurrence_diagonal_stats(values: np.ndarray, max_points: int = 1200, target_rr: float = 0.035) -> tuple[float, float]:
    values = normalize(values)
    if len(values) > max_points:
        idx = np.linspace(0, len(values) - 1, max_points).astype(int)
        values = values[idx]
    n = len(values)
    if n < 16:
        return 0.0, 0.0

    diff = np.abs(values[:, None] - values[None, :])
    upper = diff[np.triu_indices(n, k=1)]
    epsilon = float(np.quantile(upper, target_rr))
    rec = diff <= epsilon
    np.fill_diagonal(rec, False)

    lengths: list[int] = []
    recurrence_points = int(np.sum(rec))
    diagonal_points = 0
    for offset in range(-(n - 2), n - 1):
        diag = np.diagonal(rec, offset=offset)
        run = 0
        for item in diag:
            if item:
                run += 1
            else:
                if run >= 2:
                    lengths.append(run)
                    diagonal_points += run
                run = 0
        if run >= 2:
            lengths.append(run)
            diagonal_points += run

    if not lengths or recurrence_points == 0:
        return 0.0, 0.0
    return float(np.mean(lengths)), float(diagonal_points / recurrence_points)


def compute_native(values: np.ndarray, recurrence_max_points: int) -> dict[str, float]:
    diag_mean, determinism = recurrence_diagonal_stats(values, max_points=recurrence_max_points)
    return {
        "block_entropy_deficit_k4": block_entropy_deficit(values),
        "return_tail_alpha": return_tail_alpha(values),
        "recurrence_diag_mean": diag_mean,
        "recurrence_determinism": determinism,
    }


def beta_replace(base: np.ndarray, beta: float, rng: np.random.Generator) -> np.ndarray:
    illusory = rng.permutation(base)
    if beta <= 0.0:
        return base.copy()
    if beta >= 1.0:
        return illusory
    out = base.copy()
    mask = rng.random(len(base)) < beta
    out[mask] = illusory[mask]
    return out


def z_against_shuffle(
    values: np.ndarray,
    n_baseline: int,
    recurrence_max_points: int,
    rng: np.random.Generator,
) -> tuple[dict, dict, dict, dict]:
    original = compute_native(values, recurrence_max_points)
    baseline = {name: [] for name in OBS_NAMES}
    for _ in range(n_baseline):
        obs = compute_native(rng.permutation(values), recurrence_max_points)
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


def build_sequences(args: argparse.Namespace, rng: np.random.Generator) -> dict[str, np.ndarray]:
    return {
        "logistic_orbit_values": logistic_orbit(args.n_values, rng),
        "logistic_symbolic_itinerary": logistic_symbolic_itinerary(args.n_values, rng),
        "logistic_return_intervals": logistic_return_intervals(args.n_returns, rng),
    }


def analyze_sequence(name: str, base: np.ndarray, args: argparse.Namespace, rng: np.random.Generator) -> dict:
    rows = []
    betas = [float(x) for x in np.linspace(0.0, 1.0, args.n_beta)]
    for rep in range(args.n_replicates):
        rep_rng = np.random.default_rng(rng.integers(0, 2**63 - 1))
        for beta in betas:
            values = beta_replace(base, beta, rep_rng)
            obs, shuffle_mean, shuffle_std, z = z_against_shuffle(
                values,
                args.n_baseline,
                args.recurrence_max_points,
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
            "n": int(len(base)),
            "mean": float(np.mean(base)),
            "variance": float(np.var(base)),
            "unique_values": int(len(np.unique(base))),
        },
        "gate": gate,
        "classification_all_observables": classify_layers(rows, OBS_NAMES),
        "classification_one_sided_gated": classify_layers(rows, gate["coherent_one_sided_observables"]),
        "rows": rows,
    }


def compact(perimeters: dict) -> dict:
    out = {}
    for name, data in perimeters.items():
        gate = data["gate"]
        all_cls = data["classification_all_observables"]
        gated_cls = data["classification_one_sided_gated"]
        out[name] = {
            "n": data["source"]["n"],
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
        "experiment": "logistic_counter_scope_gate",
        "category": "gate_falsification_logistic_observability",
        "question": "Does the logistic counter-scope stay blank under logistic-native observables?",
        "observables_native_version": OBSERVABLES_NATIVE_VERSION,
        "observables_used": OBS_NAMES,
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
    print("perimeter n one_sided stable0 stable1 dist_gate ambiguous_gate")
    for name, row in output["matrix"].items():
        print(
            f"{name:>29s} "
            f"{row['n']:>5d} "
            f"{','.join(row['coherent_one_sided_observables']) or '[]':>55s} "
            f"{row['stable_count_coherent']:>7.3f} "
            f"{row['stable_count_illusory']:>7.3f} "
            f"{row['endpoint_distance_one_sided_gated']:>9.3f} "
            f"{row['ambiguous_beta_one_sided_gated']}"
        )
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-values", type=int, default=4096)
    parser.add_argument("--n-returns", type=int, default=4096)
    parser.add_argument("--n-replicates", type=int, default=12)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=24)
    parser.add_argument("--recurrence-max-points", type=int, default=360)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=202605071006)
    parser.add_argument("--out", default="tools/data/logistic_counter_scope_gate_20260507_1006.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
