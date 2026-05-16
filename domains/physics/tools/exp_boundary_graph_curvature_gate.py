#!/usr/bin/env python3
"""
Graph-curvature gate for the 8 GUE / 5 Poisson BOUNDARY perimeter.

The unit is the row-aligned domain/window from the base BOUNDARY perimeter.
Labels are kept as audit metadata; the geometry is built from observables:
canonical registry values, explicit spectral rigidity, and shuffle z values.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from exp_semireal_boundary_transfer_gate import row_spacings
from observables_registry import (
    OBSERVABLES_CANONICAL,
    OBSERVABLES_REGISTRY_VERSION,
    SR_local_rigidity,
)


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
FEATURE_NAMES = OBS_NAMES + ["SR_local_rigidity"] + [f"z_{name}" for name in OBS_NAMES]


def load_scope(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        data = json.load(f)
    rows = data.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain rows")
    return rows


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def compute_observables(gaps: np.ndarray) -> dict[str, float]:
    values = {name: float(fn(gaps)) for name, fn in OBSERVABLES_CANONICAL.items()}
    values["SR_local_rigidity"] = float(SR_local_rigidity(gaps))
    return values


def shuffle_z(
    gaps: np.ndarray,
    original: dict[str, float],
    n_shuffle: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    samples = {name: [] for name in OBS_NAMES}
    for _ in range(n_shuffle):
        shuffled = rng.permutation(gaps)
        obs = compute_observables(shuffled)
        for name in OBS_NAMES:
            samples[name].append(obs[name])

    z = {}
    for name in OBS_NAMES:
        arr = np.asarray(samples[name], dtype=float)
        sd = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        mean = float(np.mean(arr)) if len(arr) else 0.0
        z[name] = float((original[name] - mean) / sd) if sd > 1e-15 else 0.0
    return z


def standardized_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    matrix = []
    for row in rows:
        obs = row["observables"]
        z = row["shuffle_z"]
        matrix.append([obs[name] for name in OBS_NAMES] + [obs["SR_local_rigidity"]] + [z[name] for name in OBS_NAMES])
    x = np.asarray(matrix, dtype=float)
    center = np.mean(x, axis=0)
    scale = np.std(x, axis=0, ddof=1)
    scale[scale <= 1e-15] = 1.0
    return (x - center) / scale


def build_knn_edges(x: np.ndarray, k: int) -> list[tuple[int, int, float]]:
    n = len(x)
    distances = np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)
    edges: set[tuple[int, int]] = set()
    for i in range(n):
        nearest = np.argsort(distances[i])[1 : k + 1]
        for j in nearest:
            edges.add((min(i, int(j)), max(i, int(j))))
    return [(i, j, float(distances[i, j])) for i, j in sorted(edges)]


def classify_geometry(rows: list[dict[str, Any]], x: np.ndarray, k: int) -> dict[str, Any]:
    labels = [row["source_domain_type"] for row in rows]
    gue_idx = [i for i, label in enumerate(labels) if label == "GUE"]
    poi_idx = [i for i, label in enumerate(labels) if label == "Poisson"]
    if not gue_idx or not poi_idx:
        raise ValueError("scope must include both GUE and Poisson rows")

    c_gue = np.mean(x[gue_idx], axis=0)
    c_poi = np.mean(x[poi_idx], axis=0)
    edges = build_knn_edges(x, k)
    degree = {i: 0 for i in range(len(rows))}
    for i, j, _ in edges:
        degree[i] += 1
        degree[j] += 1

    row_out = []
    third_rows = []
    for i, row in enumerate(rows):
        d_gue = float(np.linalg.norm(x[i] - c_gue))
        d_poi = float(np.linalg.norm(x[i] - c_poi))
        denom = d_gue + d_poi
        centroid_coord = float((d_gue - d_poi) / denom) if denom > 1e-15 else 0.0
        centroid_margin = float(abs(d_gue - d_poi) / denom) if denom > 1e-15 else 0.0
        incident = [(a, b, dist) for a, b, dist in edges if a == i or b == i]
        cross = 0
        cross_curvatures = []
        same_curvatures = []
        for a, b, _ in incident:
            other = b if a == i else a
            curvature = 4 - degree[a] - degree[b]
            if labels[other] != labels[i]:
                cross += 1
                cross_curvatures.append(curvature)
            else:
                same_curvatures.append(curvature)
        cross_fraction = float(cross / len(incident)) if incident else 0.0
        state = "class_interior"
        if cross_fraction > 0 and centroid_margin < 0.25:
            state = "third_included_candidate"
            third_rows.append(row["domain_window"])
        elif cross_fraction > 0:
            state = "cut_edge"
        row_out.append(
            {
                "domain_window": row["domain_window"],
                "domain": row["domain"],
                "source_domain_type": row["source_domain_type"],
                "degree": degree[i],
                "centroid_coord": round(centroid_coord, 6),
                "centroid_margin": round(centroid_margin, 6),
                "cross_neighbor_fraction": round(cross_fraction, 6),
                "cross_edge_curvature_mean": round(float(np.mean(cross_curvatures)), 6) if cross_curvatures else None,
                "same_edge_curvature_mean": round(float(np.mean(same_curvatures)), 6) if same_curvatures else None,
                "boundary_state": state,
            }
        )

    cross_edges = [
        {
            "a": rows[i]["domain_window"],
            "b": rows[j]["domain_window"],
            "distance": round(dist, 6),
            "forman_unweighted": 4 - degree[i] - degree[j],
        }
        for i, j, dist in edges
        if labels[i] != labels[j]
    ]
    same_edges = [
        {"distance": dist, "forman_unweighted": 4 - degree[i] - degree[j]}
        for i, j, dist in edges
        if labels[i] == labels[j]
    ]

    return {
        "feature_names": FEATURE_NAMES,
        "k": k,
        "label_counts": {
            "GUE": len(gue_idx),
            "Poisson": len(poi_idx),
        },
        "edge_counts": {
            "total": len(edges),
            "cross_label": len(cross_edges),
            "same_label": len(same_edges),
        },
        "curvature": {
            "cross_edge_mean": round(float(np.mean([e["forman_unweighted"] for e in cross_edges])), 6) if cross_edges else None,
            "same_edge_mean": round(float(np.mean([e["forman_unweighted"] for e in same_edges])), 6) if same_edges else None,
        },
        "third_included_candidates": third_rows,
        "rows": row_out,
        "cross_edges": cross_edges,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    scope = load_scope(Path(args.scope))
    selected = [row for row in scope if row.get("source_domain_type") in {"GUE", "Poisson"}]
    selected = sorted(selected, key=lambda row: int(row["cycle"]))

    rows = []
    errors = []
    for source in selected:
        try:
            gaps = row_spacings(source["domain"])
            if len(gaps) < args.min_gaps:
                errors.append(
                    {
                        "domain_window": source["domain_window"],
                        "error": f"insufficient gaps {len(gaps)} < {args.min_gaps}",
                    }
                )
                continue
            gaps = gaps[: args.n_gaps] if len(gaps) > args.n_gaps else gaps
            obs = compute_observables(gaps)
            z = shuffle_z(gaps, obs, args.n_shuffle, rng)
            rows.append(
                {
                    "domain_window": source["domain_window"],
                    "domain": source["domain"],
                    "cycle": source["cycle"],
                    "source_domain_type": source["source_domain_type"],
                    "n_gaps": int(len(gaps)),
                    "observables": {key: round(value, 9) for key, value in obs.items()},
                    "shuffle_z": {key: round(value, 6) for key, value in z.items()},
                }
            )
        except Exception as exc:  # noqa: BLE001 - row-level telemetry is part of the result.
            errors.append(
                {
                    "domain_window": source.get("domain_window"),
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
            )

    x = standardized_matrix(rows)
    geometry = classify_geometry(rows, x, args.k)
    output = {
        "experiment": "boundary_graph_curvature_gate",
        "question": "Does the 8 GUE / 5 Poisson perimeter expose a graph boundary row instead of a clean two-class split?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": FEATURE_NAMES,
        "params": vars(args),
        "source_scope": args.scope,
        "observable_contract": {
            "claim": "the boundary is operational when row geometry produces cross-label graph nodes with low centroid margin",
            "observable": "kNN graph position, cross-neighbor fraction, centroid margin, unweighted Forman edge curvature",
            "operator": "row-aligned domain/window graph in canonical+rigidity+shuffle-z feature space",
            "generator": "dnd_autoricerca row_spacings via semireal boundary transfer gate",
            "denominator": "base BOUNDARY rows with source_domain_type in {GUE, Poisson}",
            "non_possible": "third-included boundary if all cross-label edges vanish or only high-margin class interiors cross",
            "not_tested": "V_c, Sturmian denominators, analytic source of each domain label",
        },
        "summary": {
            "rows_analyzed": len(rows),
            "errors": len(errors),
            "third_included_candidate_count": len(geometry["third_included_candidates"]),
            "third_included_candidates": geometry["third_included_candidates"],
            "edge_counts": geometry["edge_counts"],
            "curvature": geometry["curvature"],
        },
        "geometry": geometry,
        "rows": rows,
        "errors": errors,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={FEATURE_NAMES}")
    print(f"rows_analyzed={len(rows)} errors={len(errors)}")
    print(f"label_counts={geometry['label_counts']}")
    print(f"edge_counts={geometry['edge_counts']}")
    print(f"curvature={geometry['curvature']}")
    print(f"third_included_candidates={geometry['third_included_candidates']}")
    for row in geometry["rows"]:
        print(
            f"{row['domain_window']}\t{row['source_domain_type']}\t"
            f"margin={row['centroid_margin']:.3f}\tcross={row['cross_neighbor_fraction']:.3f}\t"
            f"state={row['boundary_state']}"
        )
    print(f"saved={out}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="tools/data/boundary_denominator_prescan_full_20260509_1500.json")
    parser.add_argument("--n-gaps", type=int, default=2048)
    parser.add_argument("--min-gaps", type=int, default=64)
    parser.add_argument("--n-shuffle", type=int, default=64)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260515)
    parser.add_argument("--out", default="tools/data/boundary_graph_curvature_gate_20260515_1855.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
