#!/usr/bin/env python3
"""
Rosenzweig-Porter physical bridge audit for the live BOUNDARY direction.

The script projects the two-reader BOUNDARY gate onto a controlled
diagonal-plus-GUE Hamiltonian flow. Each lambda value is one row. The classical
reader uses Brody q and a Wigner/Poisson mixture weight; the graph reader asks
whether the same rows sit between endpoint poles under small k/seed
perturbations.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION, SR_local_rigidity


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
FEATURE_NAMES = OBS_NAMES + ["SR_local_rigidity", "brody_q", "berry_robnick_like_gue_weight", "mean_ipr"]


def parse_floats(raw: str) -> list[float]:
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("empty float list")
    return values


def parse_ints(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("empty integer list")
    return values


def normalize_spacings(gaps: np.ndarray) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
    if len(gaps) == 0:
        raise ValueError("no positive finite spacings")
    return gaps / float(np.mean(gaps))


def brody_pdf(s: np.ndarray, q: float) -> np.ndarray:
    beta = math.gamma((q + 2.0) / (q + 1.0)) ** (q + 1.0)
    return (q + 1.0) * beta * np.power(s, q) * np.exp(-beta * np.power(s, q + 1.0))


def fit_brody_q(s: np.ndarray, grid_size: int) -> tuple[float, float]:
    best_q = 0.0
    best_nll = float("inf")
    for q in np.linspace(0.0, 1.0, grid_size):
        pdf = np.maximum(brody_pdf(s, float(q)), 1e-300)
        nll = -float(np.sum(np.log(pdf)))
        if nll < best_nll:
            best_q = float(q)
            best_nll = nll
    return best_q, best_nll


def poisson_cdf(s: np.ndarray) -> np.ndarray:
    return 1.0 - np.exp(-s)


def gue_wigner_cdf(s: np.ndarray) -> np.ndarray:
    a = 4.0 / math.pi
    return 1.0 - np.exp(-a * s * s) * (1.0 + a * s * s)


def empirical_ks(sorted_s: np.ndarray, model_cdf: np.ndarray) -> float:
    empirical = np.arange(1, len(sorted_s) + 1, dtype=float) / float(len(sorted_s))
    return float(np.max(np.abs(empirical - model_cdf)))


def fit_mixture_weight(s: np.ndarray, grid_size: int) -> tuple[float, float]:
    sorted_s = np.sort(s)
    poi = poisson_cdf(sorted_s)
    gue = gue_wigner_cdf(sorted_s)
    best_w = 0.0
    best_ks = float("inf")
    for w in np.linspace(0.0, 1.0, grid_size):
        ks = empirical_ks(sorted_s, (1.0 - w) * poi + w * gue)
        if ks < best_ks:
            best_w = float(w)
            best_ks = ks
    return best_w, best_ks


def central_slice(n: int, fraction: float) -> slice:
    keep = max(8, min(n, int(round(n * fraction))))
    start = (n - keep) // 2
    return slice(start, start + keep)


def gue_matrix(rng: np.random.Generator, n: int) -> np.ndarray:
    real = rng.normal(0.0, 1.0, (n, n))
    imag = rng.normal(0.0, 1.0, (n, n))
    z = real + 1j * imag
    h = (z + z.conj().T) / (2.0 * math.sqrt(n))
    return h.real


def rp_hamiltonian(rng: np.random.Generator, n: int, lam: float) -> np.ndarray:
    diagonal = np.diag(rng.normal(0.0, 1.0, n))
    gue = gue_matrix(rng, n)
    return math.sqrt(max(0.0, 1.0 - lam)) * diagonal + math.sqrt(max(0.0, lam)) * gue


def row_spacings_and_ipr(
    lam: float,
    n: int,
    reps: int,
    central_fraction: float,
    seed: int,
) -> tuple[np.ndarray, float]:
    rng = np.random.default_rng(seed)
    spacings = []
    iprs = []
    for _ in range(reps):
        h = rp_hamiltonian(rng, n, lam)
        levels, vectors = np.linalg.eigh(h)
        central = levels[central_slice(len(levels), central_fraction)]
        gaps = np.diff(np.sort(central))
        gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
        if len(gaps):
            spacings.extend(gaps.tolist())
        probs = np.square(np.abs(vectors[:, central_slice(vectors.shape[1], central_fraction)]))
        ipr = np.sum(probs * probs, axis=0)
        if len(ipr):
            iprs.extend(ipr.tolist())
    if not spacings:
        raise ValueError(f"lambda {lam} produced no spacings")
    return np.asarray(spacings, dtype=float), float(np.mean(iprs)) if iprs else 0.0


def source_type(lam: float, poisson_max: float, gue_min: float) -> str:
    if lam <= poisson_max:
        return "Poisson_pole"
    if lam >= gue_min:
        return "GUE_pole"
    return "flow_candidate"


def compute_row(lam: float, args: argparse.Namespace, seed: int) -> dict[str, Any]:
    gaps, mean_ipr = row_spacings_and_ipr(lam, args.n, args.reps, args.central_fraction, seed)
    s = normalize_spacings(gaps)
    obs = {name: float(fn(s)) for name, fn in OBSERVABLES_CANONICAL.items()}
    obs["SR_local_rigidity"] = float(SR_local_rigidity(s))
    brody_q, brody_nll = fit_brody_q(s, args.grid_size)
    mixture_w, mixture_ks = fit_mixture_weight(s, args.grid_size)
    return {
        "domain_window": f"RP_lambda_{lam:.3f}",
        "lambda": round(lam, 6),
        "source_domain_type": source_type(lam, args.poisson_pole_max, args.gue_pole_min),
        "n_spacings": int(len(s)),
        "mean_ipr": round(mean_ipr, 9),
        "observables": {key: round(value, 9) for key, value in obs.items()},
        "brody_q": round(brody_q, 6),
        "brody_nll": round(brody_nll, 6),
        "berry_robnick_like_gue_weight": round(mixture_w, 6),
        "mixture_ks": round(mixture_ks, 6),
    }


def standardized_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    matrix = []
    for row in rows:
        obs = row["observables"]
        matrix.append(
            [obs[name] for name in OBS_NAMES]
            + [obs["SR_local_rigidity"], row["brody_q"], row["berry_robnick_like_gue_weight"], row["mean_ipr"]]
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


def classify_graph(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    x = standardized_matrix(rows)
    labels = [row["source_domain_type"] for row in rows]
    poi_idx = [i for i, label in enumerate(labels) if label == "Poisson_pole"]
    gue_idx = [i for i, label in enumerate(labels) if label == "GUE_pole"]
    if not poi_idx or not gue_idx:
        raise ValueError("lambda grid must include Poisson and GUE poles")
    c_poi = np.mean(x[poi_idx], axis=0)
    c_gue = np.mean(x[gue_idx], axis=0)
    edges = build_knn_edges(x, k)
    degree = {i: 0 for i in range(len(rows))}
    for i, j, _ in edges:
        degree[i] += 1
        degree[j] += 1

    graph_rows = []
    for i, row in enumerate(rows):
        d_poi = float(np.linalg.norm(x[i] - c_poi))
        d_gue = float(np.linalg.norm(x[i] - c_gue))
        denom = d_poi + d_gue
        margin = float(abs(d_poi - d_gue) / denom) if denom > 1e-15 else 0.0
        incident = [(a, b) for a, b, _ in edges if a == i or b == i]
        cross = 0
        for a, b in incident:
            other = b if a == i else a
            if {labels[i], labels[other]} == {"Poisson_pole", "GUE_pole"}:
                cross += 1
            elif labels[i] == "flow_candidate" and labels[other] in {"Poisson_pole", "GUE_pole"}:
                cross += 1
        cross_fraction = float(cross / len(incident)) if incident else 0.0
        state = "class_interior"
        if row["source_domain_type"] == "flow_candidate" and cross_fraction > 0 and margin < 0.35:
            state = "third_included_candidate"
        elif cross_fraction > 0:
            state = "cut_edge"
        graph_rows.append(
            {
                "domain_window": row["domain_window"],
                "lambda": row["lambda"],
                "source_domain_type": row["source_domain_type"],
                "centroid_margin": round(margin, 6),
                "cross_neighbor_fraction": round(cross_fraction, 6),
                "degree": degree[i],
                "boundary_state": state,
            }
        )
    return {"k": k, "rows": graph_rows, "third_included_candidates": [r["domain_window"] for r in graph_rows if r["boundary_state"] == "third_included_candidate"]}


def classical_state(row: dict[str, Any]) -> str:
    q = float(row["brody_q"])
    w = float(row["berry_robnick_like_gue_weight"])
    if q <= 0.25 and w <= 0.25:
        return "classical_poisson_endpoint"
    if q >= 0.75 and w >= 0.75:
        return "classical_gue_endpoint"
    return "classical_intermediate"


def stability_state(freq: float) -> str:
    if freq >= 0.75:
        return "stable_graph_bridge"
    if freq >= 0.25:
        return "parameter_sensitive_bridge"
    return "unstable_non_bridge"


def run(args: argparse.Namespace) -> dict[str, Any]:
    lambdas = parse_floats(args.lambdas)
    seeds = parse_ints(args.seeds)
    ks = parse_ints(args.k_values)
    total_runs = len(seeds) * len(ks)
    row_hits: dict[str, dict[str, Any]] = {}
    reader_runs = []
    seed_rows: dict[int, list[dict[str, Any]]] = {}

    for seed in seeds:
        rows = [compute_row(lam, args, seed + int(round(lam * 1000))) for lam in lambdas]
        seed_rows[seed] = rows
        for k in ks:
            graph = classify_graph(rows, k)
            reader_runs.append({"seed": seed, "k": k, "third_included_candidates": graph["third_included_candidates"]})
            graph_by_name = {row["domain_window"]: row for row in graph["rows"]}
            for row in rows:
                name = row["domain_window"]
                if name not in row_hits:
                    row_hits[name] = {
                        "lambda": row["lambda"],
                        "source_domain_type": row["source_domain_type"],
                        "graph_hits": 0,
                        "margins": [],
                        "cross_fractions": [],
                        "brody_q": [],
                        "mixture_w": [],
                        "mean_ipr": [],
                        "sr": [],
                    }
                grow = graph_by_name[name]
                if grow["boundary_state"] == "third_included_candidate":
                    row_hits[name]["graph_hits"] += 1
                row_hits[name]["margins"].append(float(grow["centroid_margin"]))
                row_hits[name]["cross_fractions"].append(float(grow["cross_neighbor_fraction"]))
                row_hits[name]["brody_q"].append(float(row["brody_q"]))
                row_hits[name]["mixture_w"].append(float(row["berry_robnick_like_gue_weight"]))
                row_hits[name]["mean_ipr"].append(float(row["mean_ipr"]))
                row_hits[name]["sr"].append(float(row["observables"]["SR"]))

    rows_out = []
    counts: dict[str, int] = {}
    for name in sorted(row_hits, key=lambda key: row_hits[key]["lambda"]):
        item = row_hits[name]
        freq = item["graph_hits"] / total_runs
        class_row = {
            "brody_q": float(np.median(item["brody_q"])),
            "berry_robnick_like_gue_weight": float(np.median(item["mixture_w"])),
        }
        c_state = classical_state(class_row)
        g_state = stability_state(freq)
        composite = f"{g_state}+{c_state}"
        counts[composite] = counts.get(composite, 0) + 1
        rows_out.append(
            {
                "domain_window": name,
                "lambda": item["lambda"],
                "source_domain_type": item["source_domain_type"],
                "graph_bridge_frequency": round(freq, 6),
                "stability_state": g_state,
                "classical_audit_state": c_state,
                "composite_state": composite,
                "median_brody_q": round(float(np.median(item["brody_q"])), 6),
                "median_berry_robnick_like_gue_weight": round(float(np.median(item["mixture_w"])), 6),
                "median_SR": round(float(np.median(item["sr"])), 6),
                "median_mean_ipr": round(float(np.median(item["mean_ipr"])), 9),
                "mean_centroid_margin": round(float(np.mean(item["margins"])), 6),
                "mean_cross_neighbor_fraction": round(float(np.mean(item["cross_fractions"])), 6),
            }
        )

    two_reader_confirmed = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] == "classical_intermediate"
    ]
    graph_only_residue = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] == "stable_graph_bridge" and row["classical_audit_state"] != "classical_intermediate"
    ]
    classic_only_residue = [
        row["domain_window"]
        for row in rows_out
        if row["stability_state"] != "stable_graph_bridge" and row["classical_audit_state"] == "classical_intermediate"
    ]

    output = {
        "experiment": "rosenzweig_porter_bridge_physical_audit",
        "question": "Does the two-reader BOUNDARY gate survive on a controlled Rosenzweig-Porter flow?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES
        + [
            "graph_bridge_frequency",
            "centroid_margin",
            "cross_neighbor_fraction",
            "classical_audit_state",
        ],
        "parameters": {
            "n": args.n,
            "reps": args.reps,
            "lambdas": lambdas,
            "seeds": seeds,
            "k_values": ks,
            "central_fraction": args.central_fraction,
            "grid_size": args.grid_size,
            "poisson_pole_max": args.poisson_pole_max,
            "gue_pole_min": args.gue_pole_min,
            "total_graph_reader_runs": total_runs,
        },
        "observable_contract": {
            "claim": "the BOUNDARY two-reader gate transfers to a controlled physical crossover only where graph bridge stability and classical intermediacy agree on the same lambda row",
            "observable": "graph_bridge_frequency joined with Brody q, Wigner/Poisson mixture weight, SR and IPR",
            "operator": "Rosenzweig-Porter diagonal-plus-GUE Hamiltonian flow with kNN graph perturbation",
            "generator": "H(lambda)=sqrt(1-lambda)D+sqrt(lambda)GUE, finite N, repeated seeds",
            "denominator": "13 lambda rows, repeated across graph k and random seeds",
            "non_possible": "Lab-specific graph-only boundary if every stable graph bridge is classically intermediate, or physical boundary claim if classical-only rows dominate",
            "not_tested": "asymptotic RP universality, unfolding alternatives, experimental spectra, many-body localization",
        },
        "summary": {
            "rows_analyzed": len(rows_out),
            "two_reader_boundary_confirmed": len(two_reader_confirmed),
            "two_reader_rows": two_reader_confirmed,
            "graph_only_residue": len(graph_only_residue),
            "graph_only_rows": graph_only_residue,
            "classic_only_residue": len(classic_only_residue),
            "classic_only_rows": classic_only_residue,
            "composite_counts": counts,
        },
        "rows": rows_out,
        "reader_runs": reader_runs,
        "seed_rows": seed_rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/data/rosenzweig_porter_bridge_physical_audit_20260515_1933.json")
    parser.add_argument("--n", type=int, default=96)
    parser.add_argument("--reps", type=int, default=24)
    parser.add_argument("--lambdas", default="0,0.01,0.03,0.06,0.10,0.18,0.32,0.50,0.68,0.82,0.90,0.97,1.0")
    parser.add_argument("--seeds", default="202605151933,202605151934,202605151935")
    parser.add_argument("--k-values", default="2,3,4")
    parser.add_argument("--central-fraction", type=float, default=0.6)
    parser.add_argument("--grid-size", type=int, default=151)
    parser.add_argument("--poisson-pole-max", type=float, default=0.03)
    parser.add_argument("--gue-pole-min", type=float, default=0.82)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
