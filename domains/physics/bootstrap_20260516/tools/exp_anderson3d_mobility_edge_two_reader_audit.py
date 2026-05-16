#!/usr/bin/env python3
"""
Two-reader BOUNDARY audit on a 3D Anderson tight-binding flow.

The live direction asks whether the Rosenzweig-Porter two-reader gate transfers
to a second physical row-aligned flow.  Each disorder value W is one row; the
classical reader uses spacing/Brody/Wigner-Poisson diagnostics and the graph
reader asks whether the same W row sits between metallic and localized poles
under kNN perturbations.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION, SR_local_rigidity
from exp_rosenzweig_porter_bridge_physical_audit import (
    brody_pdf,
    empirical_ks,
    fit_brody_q,
    fit_mixture_weight,
    gue_wigner_cdf,
    normalize_spacings,
    parse_floats,
    parse_ints,
    poisson_cdf,
)


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
FEATURE_NAMES = OBS_NAMES + [
    "SR_local_rigidity",
    "brody_q",
    "wigner_poisson_like_weight",
    "mean_ipr",
    "participation_entropy",
]


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def central_slice(n: int, fraction: float) -> slice:
    keep = max(8, min(n, int(round(n * fraction))))
    start = (n - keep) // 2
    return slice(start, start + keep)


def anderson_hamiltonian(l_size: int, disorder: float, rng: np.random.Generator) -> np.ndarray:
    n = l_size**3
    h = np.diag(rng.uniform(-disorder / 2.0, disorder / 2.0, n))

    def idx(x: int, y: int, z: int) -> int:
        return (x * l_size + y) * l_size + z

    for x in range(l_size):
        for y in range(l_size):
            for z in range(l_size):
                i = idx(x, y, z)
                for dx, dy, dz in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                    j = idx((x + dx) % l_size, (y + dy) % l_size, (z + dz) % l_size)
                    h[i, j] = 1.0
                    h[j, i] = 1.0
    return h


def row_spacings_and_ipr(
    disorder: float,
    l_size: int,
    reps: int,
    central_fraction: float,
    seed: int,
) -> tuple[np.ndarray, float, float]:
    rng = np.random.default_rng(seed)
    spacings: list[float] = []
    iprs: list[float] = []
    entropy_values: list[float] = []
    n_sites = l_size**3
    for _ in range(reps):
        h = anderson_hamiltonian(l_size, disorder, rng)
        levels, vectors = np.linalg.eigh(h)
        central = levels[central_slice(len(levels), central_fraction)]
        gaps = np.diff(np.sort(central))
        gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
        spacings.extend(gaps.tolist())

        subset = vectors[:, central_slice(vectors.shape[1], central_fraction)]
        probs = np.square(np.abs(subset))
        ipr = np.sum(probs * probs, axis=0)
        iprs.extend(ipr.tolist())
        for col in range(probs.shape[1]):
            p = probs[:, col]
            p = p[p > 1e-15]
            entropy_values.append(float(-np.sum(p * np.log(p)) / math.log(n_sites)))

    if not spacings:
        raise ValueError(f"W={disorder} produced no spacings")
    return (
        np.asarray(spacings, dtype=float),
        float(np.mean(iprs)) if iprs else 0.0,
        float(np.mean(entropy_values)) if entropy_values else 0.0,
    )


def source_type(disorder: float, metallic_max: float, localized_min: float) -> str:
    if disorder <= metallic_max:
        return "metallic_wigner_pole"
    if disorder >= localized_min:
        return "localized_poisson_pole"
    return "mobility_candidate"


def adjacent_ratio(spacings: np.ndarray) -> float:
    gaps = np.asarray(spacings, dtype=float)
    if len(gaps) < 2:
        return 0.0
    left = gaps[:-1]
    right = gaps[1:]
    return float(np.mean(np.minimum(left, right) / np.maximum(left, right)))


def compute_row(disorder: float, args: argparse.Namespace, seed: int) -> dict[str, Any]:
    gaps, mean_ipr, participation_entropy = row_spacings_and_ipr(
        disorder,
        args.l_size,
        args.reps,
        args.central_fraction,
        seed,
    )
    s = normalize_spacings(gaps)
    obs = {name: float(fn(s)) for name, fn in OBSERVABLES_CANONICAL.items()}
    obs["SR_local_rigidity"] = float(SR_local_rigidity(s))
    brody_q, brody_nll = fit_brody_q(s, args.grid_size)
    mixture_w, mixture_ks = fit_mixture_weight(s, args.grid_size)
    return {
        "domain_window": f"Anderson3D_W_{disorder:.2f}",
        "disorder_W": round(disorder, 6),
        "source_domain_type": source_type(disorder, args.metallic_pole_max, args.localized_pole_min),
        "n_spacings": int(len(s)),
        "adjacent_r": round(adjacent_ratio(s), 9),
        "mean_ipr": round(mean_ipr, 9),
        "participation_entropy": round(participation_entropy, 9),
        "observables": {key: round(value, 9) for key, value in obs.items()},
        "brody_q": round(brody_q, 6),
        "brody_nll": round(brody_nll, 6),
        "wigner_poisson_like_weight": round(mixture_w, 6),
        "mixture_ks": round(mixture_ks, 6),
    }


def standardized_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    matrix = []
    for row in rows:
        obs = row["observables"]
        matrix.append(
            [obs[name] for name in OBS_NAMES]
            + [
                obs["SR_local_rigidity"],
                row["brody_q"],
                row["wigner_poisson_like_weight"],
                row["mean_ipr"],
                row["participation_entropy"],
            ]
        )
    x = np.asarray(matrix, dtype=float)
    center = np.mean(x, axis=0)
    scale = np.std(x, axis=0, ddof=1)
    scale[scale <= 1e-15] = 1.0
    return (x - center) / scale


def build_knn_edges(x: np.ndarray, k: int) -> list[tuple[int, int, float]]:
    distances = np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)
    edges: set[tuple[int, int]] = set()
    for i in range(len(x)):
        for j in np.argsort(distances[i])[1 : k + 1]:
            edges.add((min(i, int(j)), max(i, int(j))))
    return [(i, j, float(distances[i, j])) for i, j in sorted(edges)]


def classify_graph(rows: list[dict[str, Any]], k: int, margin_max: float) -> dict[str, Any]:
    x = standardized_matrix(rows)
    labels = [row["source_domain_type"] for row in rows]
    metallic_idx = [i for i, label in enumerate(labels) if label == "metallic_wigner_pole"]
    localized_idx = [i for i, label in enumerate(labels) if label == "localized_poisson_pole"]
    if not metallic_idx or not localized_idx:
        raise ValueError("disorder grid must include metallic and localized poles")
    c_metal = np.mean(x[metallic_idx], axis=0)
    c_local = np.mean(x[localized_idx], axis=0)
    edges = build_knn_edges(x, k)
    degree = {i: 0 for i in range(len(rows))}
    for i, j, _ in edges:
        degree[i] += 1
        degree[j] += 1

    graph_rows = []
    for i, row in enumerate(rows):
        d_metal = float(np.linalg.norm(x[i] - c_metal))
        d_local = float(np.linalg.norm(x[i] - c_local))
        denom = d_metal + d_local
        margin = float(abs(d_metal - d_local) / denom) if denom > 1e-15 else 0.0
        incident = [(a, b) for a, b, _ in edges if a == i or b == i]
        cross = 0
        for a, b in incident:
            other = b if a == i else a
            if labels[i] == "mobility_candidate" and labels[other] in {
                "metallic_wigner_pole",
                "localized_poisson_pole",
            }:
                cross += 1
            elif {labels[i], labels[other]} == {"metallic_wigner_pole", "localized_poisson_pole"}:
                cross += 1
        cross_fraction = float(cross / len(incident)) if incident else 0.0
        state = "class_interior"
        if row["source_domain_type"] == "mobility_candidate" and cross_fraction > 0 and margin < margin_max:
            state = "third_included_candidate"
        elif cross_fraction > 0:
            state = "cut_edge"
        graph_rows.append(
            {
                "domain_window": row["domain_window"],
                "disorder_W": row["disorder_W"],
                "source_domain_type": row["source_domain_type"],
                "centroid_margin": round(margin, 6),
                "cross_neighbor_fraction": round(cross_fraction, 6),
                "degree": degree[i],
                "boundary_state": state,
            }
        )
    return {
        "k": k,
        "rows": graph_rows,
        "third_included_candidates": [r["domain_window"] for r in graph_rows if r["boundary_state"] == "third_included_candidate"],
    }


def classical_state(row: dict[str, Any]) -> str:
    r = float(row["adjacent_r"])
    q = float(row["brody_q"])
    w = float(row["wigner_poisson_like_weight"])
    if r <= 0.43 and q <= 0.35 and w <= 0.35:
        return "classical_poisson_endpoint"
    if r >= 0.50 and q >= 0.65:
        return "classical_wigner_endpoint"
    return "classical_intermediate"


def stability_state(freq: float) -> str:
    if freq >= 0.75:
        return "stable_graph_bridge"
    if freq >= 0.25:
        return "parameter_sensitive_bridge"
    return "unstable_non_bridge"


def scrambled_rows(rows: list[dict[str, Any]], rng: np.random.Generator) -> list[dict[str, Any]]:
    scrambled = []
    scalar_fields = [
        "adjacent_r",
        "brody_q",
        "wigner_poisson_like_weight",
        "mean_ipr",
        "participation_entropy",
    ]
    obs_values = {
        name: rng.permutation([row["observables"][name] for row in rows]).tolist()
        for name in OBS_NAMES
    }
    scalar_values = {field: rng.permutation([row[field] for row in rows]).tolist() for field in scalar_fields}
    for index, row in enumerate(rows):
        clone = dict(row)
        clone["observables"] = dict(row["observables"])
        for name in OBS_NAMES:
            clone["observables"][name] = float(obs_values[name][index])
        clone["observables"]["SR_local_rigidity"] = clone["observables"]["SR"]
        for field in scalar_fields:
            clone[field] = float(scalar_values[field][index])
        scrambled.append(clone)
    return scrambled


def two_reader_names_from_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> set[str]:
    graph_hits: dict[str, int] = {row["domain_window"]: 0 for row in rows}
    ks = parse_ints(args.k_values)
    for k in ks:
        graph = classify_graph(rows, k, args.graph_margin_max)
        for grow in graph["rows"]:
            if grow["boundary_state"] == "third_included_candidate":
                graph_hits[grow["domain_window"]] += 1
    names = set()
    for row in rows:
        freq = graph_hits[row["domain_window"]] / len(ks)
        if stability_state(freq) == "stable_graph_bridge" and classical_state(row) == "classical_intermediate":
            names.add(row["domain_window"])
    return names


def audit_size(args: argparse.Namespace, l_size: int) -> dict[str, Any]:
    disorders = parse_floats(args.disorders)
    seeds = parse_ints(args.seeds)
    ks = parse_ints(args.k_values)
    total_runs = len(seeds) * len(ks)
    row_hits: dict[str, dict[str, Any]] = {}
    reader_runs = []
    row_args = SimpleNamespace(**vars(args))
    row_args.l_size = l_size

    for seed in seeds:
        rows = [compute_row(w, row_args, seed + (l_size * 10000) + int(round(w * 100))) for w in disorders]
        for k in ks:
            graph = classify_graph(rows, k, args.graph_margin_max)
            reader_runs.append({"L": l_size, "seed": seed, "k": k, "third_included_candidates": graph["third_included_candidates"]})
            graph_by_name = {row["domain_window"]: row for row in graph["rows"]}
            for row in rows:
                name = row["domain_window"]
                if name not in row_hits:
                    row_hits[name] = {
                        "disorder_W": row["disorder_W"],
                        "source_domain_type": row["source_domain_type"],
                        "graph_hits": 0,
                        "margins": [],
                        "cross_fractions": [],
                        "brody_q": [],
                        "mixture_w": [],
                        "adjacent_r": [],
                        "mean_ipr": [],
                        "participation_entropy": [],
                    }
                grow = graph_by_name[name]
                if grow["boundary_state"] == "third_included_candidate":
                    row_hits[name]["graph_hits"] += 1
                row_hits[name]["margins"].append(float(grow["centroid_margin"]))
                row_hits[name]["cross_fractions"].append(float(grow["cross_neighbor_fraction"]))
                row_hits[name]["brody_q"].append(float(row["brody_q"]))
                row_hits[name]["mixture_w"].append(float(row["wigner_poisson_like_weight"]))
                row_hits[name]["adjacent_r"].append(float(row["adjacent_r"]))
                row_hits[name]["mean_ipr"].append(float(row["mean_ipr"]))
                row_hits[name]["participation_entropy"].append(float(row["participation_entropy"]))

    rows_out = []
    composite_counts: dict[str, int] = {}
    for name in sorted(row_hits, key=lambda key: row_hits[key]["disorder_W"]):
        item = row_hits[name]
        freq = item["graph_hits"] / total_runs
        class_row = {
            "adjacent_r": median(item["adjacent_r"]),
            "brody_q": median(item["brody_q"]),
            "wigner_poisson_like_weight": median(item["mixture_w"]),
        }
        c_state = classical_state(class_row)
        g_state = stability_state(freq)
        composite = f"{g_state}+{c_state}"
        composite_counts[composite] = composite_counts.get(composite, 0) + 1
        rows_out.append(
            {
                "domain_window": name,
                "disorder_W": item["disorder_W"],
                "source_domain_type": item["source_domain_type"],
                "graph_bridge_frequency": round(freq, 6),
                "stability_state": g_state,
                "classical_audit_state": c_state,
                "composite_state": composite,
                "median_adjacent_r": round(median(item["adjacent_r"]), 6),
                "median_brody_q": round(median(item["brody_q"]), 6),
                "median_wigner_poisson_like_weight": round(median(item["mixture_w"]), 6),
                "median_mean_ipr": round(median(item["mean_ipr"]), 9),
                "median_participation_entropy": round(median(item["participation_entropy"]), 6),
                "mean_centroid_margin": round(float(np.mean(item["margins"])), 6),
                "mean_cross_neighbor_fraction": round(float(np.mean(item["cross_fractions"])), 6),
            }
        )

    two_reader_rows = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] == "classical_intermediate"
    ]
    graph_only_rows = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] != "classical_intermediate"
    ]
    classic_only_rows = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] != "stable_graph_bridge" and row["classical_audit_state"] == "classical_intermediate"
    ]

    return {
        "L": l_size,
        "sites": l_size**3,
        "total_graph_reader_runs": total_runs,
        "summary": {
            "two_reader_boundary_confirmed": len(two_reader_rows),
            "two_reader_rows": two_reader_rows,
            "graph_only_residue": len(graph_only_rows),
            "graph_only_rows": graph_only_rows,
            "classic_only_residue": len(classic_only_rows),
            "classic_only_rows": classic_only_rows,
            "composite_counts": composite_counts,
        },
        "rows": rows_out,
        "reader_runs": reader_runs,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    sizes = parse_ints(args.sizes)
    by_size = [audit_size(args, l_size) for l_size in sizes]
    size_names = {entry["L"]: set(entry["summary"]["two_reader_rows"]) for entry in by_size}
    all_two_reader = sorted(set.intersection(*size_names.values())) if size_names else []
    any_two_reader = sorted(set.union(*size_names.values())) if size_names else []
    intermittent_two_reader = [name for name in any_two_reader if name not in all_two_reader]

    row_by_w: dict[str, dict[str, Any]] = {}
    for entry in by_size:
        for row in entry["rows"]:
            item = row_by_w.setdefault(
                row["domain_window"],
                {
                    "disorder_W": row["disorder_W"],
                    "size_states": {},
                    "frequencies": [],
                    "classical_states": [],
                    "stability_states": [],
                    "adjacent_r": [],
                },
            )
            item["size_states"][str(entry["L"])] = row["composite_state"]
            item["frequencies"].append(row["graph_bridge_frequency"])
            item["classical_states"].append(row["classical_audit_state"])
            item["stability_states"].append(row["stability_state"])
            item["adjacent_r"].append(row["median_adjacent_r"])

    cross_size_rows = []
    for name in sorted(row_by_w, key=lambda key: row_by_w[key]["disorder_W"]):
        item = row_by_w[name]
        cross_size_rows.append(
            {
                "domain_window": name,
                "disorder_W": item["disorder_W"],
                "size_states": item["size_states"],
                "min_graph_bridge_frequency": round(float(min(item["frequencies"])), 6),
                "max_graph_bridge_frequency": round(float(max(item["frequencies"])), 6),
                "median_adjacent_r_by_size": item["adjacent_r"],
                "two_reader_all_sizes": name in all_two_reader,
                "two_reader_intermittent": name in intermittent_two_reader,
                "classical_states_seen": sorted(set(item["classical_states"])),
                "stability_states_seen": sorted(set(item["stability_states"])),
            }
        )

    observed_all_size_count = len(all_two_reader)
    rng = np.random.default_rng(args.scramble_seed)
    null_counts = []
    base_rows_by_size = {}
    for entry in by_size:
        base_rows_by_size[entry["L"]] = []
        for row in entry["rows"]:
            obs = {
                "SR": row["median_adjacent_r"],
                "SR2": row["median_brody_q"],
                "L1": row["median_wigner_poisson_like_weight"],
                "L2": row["median_mean_ipr"],
                "triple_var": row["median_participation_entropy"],
                "SR_local_rigidity": row["median_adjacent_r"],
            }
            base_rows_by_size[entry["L"]].append(
                {
                    "domain_window": row["domain_window"],
                    "disorder_W": row["disorder_W"],
                    "source_domain_type": row["source_domain_type"],
                    "adjacent_r": row["median_adjacent_r"],
                    "brody_q": row["median_brody_q"],
                    "wigner_poisson_like_weight": row["median_wigner_poisson_like_weight"],
                    "mean_ipr": row["median_mean_ipr"],
                    "participation_entropy": row["median_participation_entropy"],
                    "observables": obs,
                }
            )

    for _ in range(args.scramble_trials):
        trial_sets = []
        for l_size in sizes:
            trial_rows = scrambled_rows(base_rows_by_size[l_size], rng)
            trial_sets.append(two_reader_names_from_rows(trial_rows, args))
        null_counts.append(len(set.intersection(*trial_sets)) if trial_sets else 0)

    null_ge = sum(1 for value in null_counts if value >= observed_all_size_count)
    raw_p = null_ge / args.scramble_trials if args.scramble_trials else 0.0
    add_one_p = (null_ge + 1) / (args.scramble_trials + 1) if args.scramble_trials else 1.0

    output = {
        "experiment": "anderson3d_mobility_edge_two_reader_audit",
        "question": "Does the two-reader BOUNDARY gate transfer from Rosenzweig-Porter to a 3D Anderson mobility-edge flow?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "graph_bridge_frequency",
            "size_stability",
            "centroid_margin",
            "cross_neighbor_fraction",
            "classical_audit_state",
        ],
        "parameters": {
            "sizes": sizes,
            "sites": [l_size**3 for l_size in sizes],
            "reps": args.reps,
            "disorders": parse_floats(args.disorders),
            "seeds": parse_ints(args.seeds),
            "k_values": parse_ints(args.k_values),
            "central_fraction": args.central_fraction,
            "grid_size": args.grid_size,
            "metallic_pole_max": args.metallic_pole_max,
            "localized_pole_min": args.localized_pole_min,
            "graph_margin_max": args.graph_margin_max,
            "scramble_trials": args.scramble_trials,
            "scramble_seed": args.scramble_seed,
        },
        "observable_contract": {
            "claim": "the BOUNDARY two-reader gate transfers beyond RP only if the same Anderson disorder row is stable_graph_bridge+classical_intermediate across tested sizes",
            "observable": "two_reader_all_sizes from graph_bridge_frequency joined with adjacent ratio, Brody q, Wigner/Poisson mixture weight, IPR and participation entropy",
            "operator": "3D Anderson tight-binding Hamiltonian with periodic boundaries, disorder sweep, seed and kNN perturbation",
            "generator": "H=sum_i eps_i |i><i| + nearest-neighbor hopping on L^3, eps_i uniform[-W/2,W/2]",
            "denominator": "same disorder grid across all tested sizes",
            "non_possible": "cross-domain transfer if no W row is stable_graph_bridge+classical_intermediate at every tested size",
            "not_tested": "thermodynamic mobility-edge exponent, alternative boundary conditions, sparse large-L scaling, experimental spectra",
        },
        "summary": {
            "sizes_analyzed": len(sizes),
            "disorder_rows": len(parse_floats(args.disorders)),
            "two_reader_all_sizes": len(all_two_reader),
            "two_reader_all_size_rows": all_two_reader,
            "two_reader_intermittent": len(intermittent_two_reader),
            "two_reader_intermittent_rows": intermittent_two_reader,
            "graph_only_residue_by_size": {str(entry["L"]): entry["summary"]["graph_only_residue"] for entry in by_size},
            "feature_scramble_null": {
                "observed": observed_all_size_count,
                "k_ge_observed": null_ge,
                "trials": args.scramble_trials,
                "raw_p": round(raw_p, 9),
                "add_one_p": round(add_one_p, 9),
                "max_null": max(null_counts) if null_counts else 0,
            },
        },
        "cross_size_rows": cross_size_rows,
        "by_size": by_size,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/anderson3d_mobility_edge_two_reader_audit_20260515_1947.json")
    parser.add_argument("--sizes", default="5,6")
    parser.add_argument("--reps", type=int, default=8)
    parser.add_argument("--disorders", default="2,4,8,12,14,16,16.5,17,20,24,32")
    parser.add_argument("--seeds", default="202605151947,202605151948")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--central-fraction", type=float, default=0.45)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--metallic-pole-max", type=float, default=4.0)
    parser.add_argument("--localized-pole-min", type=float, default=24.0)
    parser.add_argument("--graph-margin-max", type=float, default=0.45)
    parser.add_argument("--scramble-trials", type=int, default=128)
    parser.add_argument("--scramble-seed", type=int, default=202605161117)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
