#!/usr/bin/env python3
"""
exp_blank_to_source_hinge.py

Regressive gate for G_POTENZIALE_NULLA after tqge_underlay_gate.

The previous cycle found that G is not a global underlay vertex; it is the local
hinge where QG blank and GE real_sourcing touch. This tool measures that hinge
as a passage: blank endpoint without source -> blank endpoint with source.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import combinations, permutations
from pathlib import Path


VERTICES = ("T", "Q", "G", "E")

EDGE_MODES = {
    ("T", "Q"): "wick_time",
    ("T", "G"): "wick_time",
    ("T", "E"): "wick_time",
    ("Q", "E"): "gauge_phase",
    ("G", "E"): "real_sourcing",
    ("Q", "G"): "blank",
}


def canon(edge: tuple[str, str]) -> tuple[str, str]:
    return tuple(sorted(edge))


EDGE_MODES = {canon(edge): mode for edge, mode in EDGE_MODES.items()}
EDGES = tuple(sorted(EDGE_MODES))


def edge_name(edge: tuple[str, str]) -> str:
    return "".join(edge)


def triangle_name(triangle: tuple[str, str, str]) -> str:
    return "".join(triangle)


def incident_edges(vertex: str) -> list[tuple[str, str]]:
    return [edge for edge in EDGES if vertex in edge]


def endpoint_context(
    edge_modes: dict[tuple[str, str], str], blank_edge: tuple[str, str]
) -> dict[str, dict]:
    context = {}
    for endpoint in blank_edge:
        modes = []
        edges = []
        for edge in incident_edges(endpoint):
            if edge == blank_edge:
                continue
            modes.append(edge_modes[edge])
            edges.append(edge_name(edge))
        context[endpoint] = {
            "incident_nonblank_edges": edges,
            "incident_nonblank_modes": sorted(modes),
            "has_real_sourcing": "real_sourcing" in modes,
            "has_wick_time": "wick_time" in modes,
            "has_gauge_phase": "gauge_phase" in modes,
        }
    return context


def void_triangles(edge_modes: dict[tuple[str, str], str]) -> list[dict]:
    out = []
    for triangle in combinations(VERTICES, 3):
        tri_edges = [canon(edge) for edge in combinations(triangle, 2)]
        modes = [edge_modes[edge] for edge in tri_edges]
        out.append(
            {
                "triangle": triangle_name(triangle),
                "edge_modes": {edge_name(edge): edge_modes[edge] for edge in tri_edges},
                "has_blank": "blank" in modes,
                "has_real_sourcing": "real_sourcing" in modes,
                "has_gauge_phase": "gauge_phase" in modes,
                "is_deposit_face": "blank" in modes and "real_sourcing" in modes,
            }
        )
    return out


def analyze(edge_modes: dict[tuple[str, str], str]) -> dict:
    blank_edges = [edge for edge, mode in edge_modes.items() if mode == "blank"]
    real_edges = [edge for edge, mode in edge_modes.items() if mode == "real_sourcing"]
    if len(blank_edges) != 1 or len(real_edges) != 1:
        raise ValueError("Expected exactly one blank edge and one real_sourcing edge")

    blank_edge = blank_edges[0]
    real_edge = real_edges[0]
    shared = sorted(set(blank_edge) & set(real_edge))
    context = endpoint_context(edge_modes, blank_edge)
    source_endpoints = [v for v, c in context.items() if c["has_real_sourcing"]]
    non_source_endpoints = [v for v, c in context.items() if not c["has_real_sourcing"]]

    if len(source_endpoints) == 1 and len(non_source_endpoints) == 1:
        directed_passage = {
            "from": non_source_endpoints[0],
            "to": source_endpoints[0],
            "label": f"{non_source_endpoints[0]}->{source_endpoints[0]}",
        }
    else:
        directed_passage = None

    triangles = void_triangles(edge_modes)
    deposit_faces = [t for t in triangles if t["is_deposit_face"]]
    excluded_void_faces = [
        t for t in triangles if t["has_blank"] and not t["has_real_sourcing"]
    ]

    source_profile = None
    if source_endpoints:
        source_profile = "+".join(context[source_endpoints[0]]["incident_nonblank_modes"])

    return {
        "blank_edge": edge_name(blank_edge),
        "real_sourcing_edge": edge_name(real_edge),
        "blank_real_shared_vertices": shared,
        "blank_adjacent_to_real": bool(shared),
        "blank_endpoint_context": context,
        "source_endpoints_on_blank": source_endpoints,
        "non_source_endpoints_on_blank": non_source_endpoints,
        "directed_passage": directed_passage,
        "source_endpoint_profile": source_profile,
        "deposit_faces": deposit_faces,
        "excluded_void_faces": excluded_void_faces,
        "all_triangles": triangles,
    }


def null_assignments() -> list[dict[tuple[str, str], str]]:
    labels = [EDGE_MODES[edge] for edge in EDGES]
    unique = set(permutations(labels, len(labels)))
    return [dict(zip(EDGES, labels_perm)) for labels_perm in unique]


def summarize_null(assignments: list[dict[tuple[str, str], str]]) -> dict:
    n = len(assignments)
    counts = Counter()
    directed = Counter()
    source_endpoint_profiles = Counter()
    deposit_face_patterns = Counter()

    for assignment in assignments:
        result = analyze(assignment)
        if result["blank_adjacent_to_real"]:
            counts["blank_adjacent_to_real"] += 1
        else:
            counts["blank_opposite_real"] += 1
        if result["directed_passage"] is not None:
            counts["directed_passage_exists"] += 1
            directed[result["directed_passage"]["label"]] += 1
        if result["blank_edge"] == "GQ":
            counts["blank_edge_is_GQ"] += 1
        if result["real_sourcing_edge"] == "EG":
            counts["real_sourcing_edge_is_EG"] += 1
        if (
            result["blank_edge"] == "GQ"
            and result["real_sourcing_edge"] == "EG"
            and result["directed_passage"]
            and result["directed_passage"]["label"] == "Q->G"
        ):
            counts["exact_Q_to_G_deposit"] += 1
        if result["source_endpoint_profile"]:
            source_endpoint_profiles[result["source_endpoint_profile"]] += 1
        deposit_face_names = "+".join(
            sorted(face["triangle"] for face in result["deposit_faces"])
        )
        deposit_face_patterns[deposit_face_names or "none"] += 1

    return {
        "n_count_preserving_assignments": n,
        "p_blank_adjacent_to_real": counts["blank_adjacent_to_real"] / n,
        "p_blank_opposite_real": counts["blank_opposite_real"] / n,
        "p_directed_passage_exists": counts["directed_passage_exists"] / n,
        "p_blank_edge_is_GQ": counts["blank_edge_is_GQ"] / n,
        "p_real_sourcing_edge_is_EG": counts["real_sourcing_edge_is_EG"] / n,
        "p_exact_Q_to_G_deposit": counts["exact_Q_to_G_deposit"] / n,
        "directed_passage_counts": dict(sorted(directed.items())),
        "source_endpoint_profile_counts": dict(sorted(source_endpoint_profiles.items())),
        "deposit_face_pattern_counts": dict(sorted(deposit_face_patterns.items())),
    }


def run() -> dict:
    observed = analyze(EDGE_MODES)
    null = summarize_null(null_assignments())
    return {
        "experiment": "blank_to_source_hinge",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE edges and QxG void",
                "tools/data/lab_riflessi.json: 3 Wick + 1 phase + 1 real + 1 void taxonomy",
                "tools/data/reports/agent_20260507_1751.md: G as QG blank + GE real_sourcing hinge",
            ],
            "inferred": [
                "directed passage from blank endpoint without real_sourcing to endpoint with real_sourcing",
                "deposit face as triangle containing both blank and real_sourcing edges",
                "count-preserving null by permuting edge modes over the six TQGE edges",
            ],
        },
        "edge_modes": {edge_name(edge): mode for edge, mode in EDGE_MODES.items()},
        "observed": observed,
        "null": null,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = run()
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
