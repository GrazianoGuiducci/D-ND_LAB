#!/usr/bin/env python3
"""
Classical crossover audit for the 8 GUE / 5 Poisson BOUNDARY perimeter.

The row unit is inherited from the graph-curvature gate. This script adds two
standard one-dimensional crossover readers to the same rows:

- Brody q in [0, 1], fitted by grid likelihood on mean-normalized spacings.
- A simple Berry-Robnik-like mixture weight in [0, 1], fitted by KS distance
  between the empirical CDF and w * GUE_surmise + (1-w) * Poisson.

These are audit coordinates, not new Lab observables. The Lab-specific residue
is the disagreement between graph bridge rows and classical scalar intermediacy.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from exp_semireal_boundary_transfer_gate import row_spacings


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def normalize_spacings(gaps: np.ndarray) -> np.ndarray:
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[np.isfinite(gaps)]
    gaps = gaps[gaps > 0]
    if len(gaps) == 0:
        raise ValueError("no positive finite spacings")
    mean = float(np.mean(gaps))
    if mean <= 1e-15:
        raise ValueError("spacing mean is zero")
    return gaps / mean


def brody_pdf(s: np.ndarray, q: float) -> np.ndarray:
    beta = math.gamma((q + 2.0) / (q + 1.0)) ** (q + 1.0)
    return (q + 1.0) * beta * np.power(s, q) * np.exp(-beta * np.power(s, q + 1.0))


def fit_brody_q(s: np.ndarray, grid_size: int) -> tuple[float, float]:
    qs = np.linspace(0.0, 1.0, grid_size)
    best_q = 0.0
    best_nll = float("inf")
    for q in qs:
        pdf = np.maximum(brody_pdf(s, float(q)), 1e-300)
        nll = -float(np.sum(np.log(pdf)))
        if nll < best_nll:
            best_nll = nll
            best_q = float(q)
    return best_q, best_nll


def poisson_cdf(s: np.ndarray) -> np.ndarray:
    return 1.0 - np.exp(-s)


def gue_wigner_cdf(s: np.ndarray) -> np.ndarray:
    a = 4.0 / math.pi
    return 1.0 - np.exp(-a * s * s) * (1.0 + a * s * s)


def empirical_ks(s: np.ndarray, model_cdf: np.ndarray) -> float:
    empirical = np.arange(1, len(s) + 1, dtype=float) / float(len(s))
    return float(np.max(np.abs(empirical - model_cdf)))


def fit_mixture_weight(s: np.ndarray, grid_size: int) -> tuple[float, float]:
    sorted_s = np.sort(s)
    poi = poisson_cdf(sorted_s)
    gue = gue_wigner_cdf(sorted_s)
    best_w = 0.0
    best_ks = float("inf")
    for w in np.linspace(0.0, 1.0, grid_size):
        model = (1.0 - w) * poi + w * gue
        ks = empirical_ks(sorted_s, model)
        if ks < best_ks:
            best_ks = ks
            best_w = float(w)
    return best_w, best_ks


def classical_state(brody_q: float, mixture_w: float, graph_state: str) -> str:
    brody_mid = 0.25 <= brody_q <= 0.75
    mix_mid = 0.25 <= mixture_w <= 0.75
    if graph_state == "third_included_candidate" and (brody_mid or mix_mid):
        return "classic_and_graph_bridge"
    if graph_state == "third_included_candidate":
        return "graph_only_bridge"
    if brody_mid or mix_mid:
        return "classic_only_intermediate"
    return "endpoint_like"


def run(args: argparse.Namespace) -> dict[str, Any]:
    graph = load_json(Path(args.graph))
    graph_rows = graph.get("geometry", {}).get("rows", [])
    if not isinstance(graph_rows, list) or not graph_rows:
        raise ValueError("graph input has no geometry.rows")

    rows = []
    for grow in graph_rows:
        gaps = row_spacings(grow["domain"])
        gaps = gaps[: args.n_gaps] if len(gaps) > args.n_gaps else gaps
        s = normalize_spacings(gaps)
        brody_q, brody_nll = fit_brody_q(s, args.grid_size)
        mixture_w, mixture_ks = fit_mixture_weight(s, args.grid_size)
        rows.append(
            {
                "domain_window": grow["domain_window"],
                "domain": grow["domain"],
                "source_domain_type": grow["source_domain_type"],
                "graph_state": grow["boundary_state"],
                "centroid_margin": grow["centroid_margin"],
                "cross_neighbor_fraction": grow["cross_neighbor_fraction"],
                "n_spacings": int(len(s)),
                "brody_q": round(brody_q, 6),
                "brody_nll": round(brody_nll, 6),
                "berry_robnick_like_gue_weight": round(mixture_w, 6),
                "mixture_ks": round(mixture_ks, 6),
                "audit_state": classical_state(brody_q, mixture_w, grow["boundary_state"]),
            }
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["audit_state"]] = counts.get(row["audit_state"], 0) + 1

    third = [row for row in rows if row["graph_state"] == "third_included_candidate"]
    graph_only = [row["domain_window"] for row in third if row["audit_state"] == "graph_only_bridge"]
    classic_and_graph = [row["domain_window"] for row in third if row["audit_state"] == "classic_and_graph_bridge"]
    classic_only = [row["domain_window"] for row in rows if row["audit_state"] == "classic_only_intermediate"]

    output = {
        "experiment": "boundary_classical_crossover_audit",
        "question": "Do graph bridge rows collapse to standard Brody/Berry-Robnik-like crossover coordinates?",
        "observables_registry": "none; classical audit coordinates plus prior graph observables",
        "observables_used": [
            "brody_q",
            "berry_robnick_like_gue_weight",
            "mixture_ks",
            "graph_boundary_state_from_1855",
            "centroid_margin_from_1855",
            "cross_neighbor_fraction_from_1855",
        ],
        "params": vars(args),
        "source_graph": args.graph,
        "observable_contract": {
            "claim": "Lab bridge rows retain residue after comparison with classical crossover scalars",
            "observable": "row-aligned Brody q, Berry-Robnik-like GUE mixture weight, graph bridge state",
            "operator": "classical scalar audit over the same 13 BOUNDARY rows used by the graph gate",
            "generator": "row_spacings(domain) with graph states imported from boundary_graph_curvature_gate",
            "denominator": "13 rows: 8 GUE and 5 Poisson",
            "non_possible": "Lab-specific bridge if every graph bridge is exactly a classical intermediate and no classical-only intermediate appears",
            "not_tested": "true Rosenzweig-Porter Hamiltonian flow, physical unfolding alternatives, asymptotic universality",
        },
        "summary": {
            "rows_analyzed": len(rows),
            "audit_counts": counts,
            "graph_third_included": [row["domain_window"] for row in third],
            "classic_and_graph_bridge": classic_and_graph,
            "graph_only_bridge": graph_only,
            "classic_only_intermediate": classic_only,
            "lab_residue_present": bool(graph_only or classic_only),
        },
        "rows": rows,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default="tools/data/boundary_graph_curvature_gate_20260515_1855.json")
    parser.add_argument("--n-gaps", type=int, default=2048)
    parser.add_argument("--grid-size", type=int, default=201)
    parser.add_argument("--out", default="tools/data/boundary_classical_crossover_audit_20260515_1904.json")
    args = parser.parse_args()
    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
