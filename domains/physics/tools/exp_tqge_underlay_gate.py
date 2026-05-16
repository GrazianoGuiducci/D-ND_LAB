#!/usr/bin/env python3
"""
exp_tqge_underlay_gate.py

Gate for G_POTENZIALE_NULLA on the TQGE tetrahedron.

The experiment does not infer physics from wording. It takes the bridge/operator
taxonomy already deposited in the lab context and asks what role G actually has
in that finite structure under count-preserving null assignments.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from itertools import combinations, permutations
from pathlib import Path


VERTICES = ("T", "Q", "G", "E")

# Source: tools/data/lab_riflessi.json entries around the "5 f->g concreti"
# operator taxonomy, echoed in tools/LAB_AGENT_CONTEXT.md as TQGE structure.
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


EDGE_MODES = {canon(k): v for k, v in EDGE_MODES.items()}
EDGES = tuple(sorted(EDGE_MODES))


def entropy(labels: list[str]) -> float:
    counts = Counter(labels)
    total = sum(counts.values())
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def vertex_profiles(edge_modes: dict[tuple[str, str], str]) -> dict[str, dict]:
    out = {}
    for vertex in VERTICES:
        incident = [mode for edge, mode in edge_modes.items() if vertex in edge]
        counts = Counter(incident)
        out[vertex] = {
            "incident_modes": dict(sorted(counts.items())),
            "mode_entropy_bits": round(entropy(incident), 6),
            "has_blank": "blank" in counts,
            "has_real_sourcing": "real_sourcing" in counts,
            "has_blank_and_real_sourcing": "blank" in counts and "real_sourcing" in counts,
        }
    return out


def void_triangles(edge_modes: dict[tuple[str, str], str]) -> list[str]:
    voids = []
    for tri in combinations(VERTICES, 3):
        tri_edges = [canon(edge) for edge in combinations(tri, 2)]
        if any(edge_modes[edge] == "blank" for edge in tri_edges):
            voids.append("".join(tri))
    return voids


def null_assignments() -> list[dict[tuple[str, str], str]]:
    labels = [EDGE_MODES[edge] for edge in EDGES]
    unique = set(permutations(labels, len(labels)))
    return [dict(zip(EDGES, labels_perm)) for labels_perm in unique]


def summarize_null(assignments: list[dict[tuple[str, str], str]]) -> dict:
    g_entropy = []
    max_entropy_vertices = []
    g_blank_real = 0
    any_blank_real = 0
    g_is_only_blank_real = 0
    void_with_g_count = 0
    void_with_qg_count = 0

    for assignment in assignments:
        profiles = vertex_profiles(assignment)
        entropies = {v: profiles[v]["mode_entropy_bits"] for v in VERTICES}
        max_e = max(entropies.values())
        max_vertices = tuple(sorted(v for v, e in entropies.items() if e == max_e))
        blank_real_vertices = [
            v for v, p in profiles.items() if p["has_blank_and_real_sourcing"]
        ]
        voids = void_triangles(assignment)

        g_entropy.append(entropies["G"])
        max_entropy_vertices.append(max_vertices)
        if "G" in blank_real_vertices:
            g_blank_real += 1
        if blank_real_vertices:
            any_blank_real += 1
        if blank_real_vertices == ["G"]:
            g_is_only_blank_real += 1
        if all("G" in tri for tri in voids):
            void_with_g_count += 1
        if assignment[canon(("Q", "G"))] == "blank":
            void_with_qg_count += 1

    n = len(assignments)
    return {
        "n_count_preserving_assignments": n,
        "p_G_has_blank_and_real_sourcing": g_blank_real / n,
        "p_any_vertex_has_blank_and_real_sourcing": any_blank_real / n,
        "p_G_is_only_blank_and_real_sourcing_vertex": g_is_only_blank_real / n,
        "p_all_void_triangles_include_G": void_with_g_count / n,
        "p_blank_is_QG_edge": void_with_qg_count / n,
        "G_entropy_bits_null_min": min(g_entropy),
        "G_entropy_bits_null_max": max(g_entropy),
        "max_entropy_vertex_patterns": {
            "+".join(k): v for k, v in sorted(Counter(max_entropy_vertices).items())
        },
    }


def run() -> dict:
    profiles = vertex_profiles(EDGE_MODES)
    voids = void_triangles(EDGE_MODES)
    assignments = null_assignments()
    null = summarize_null(assignments)

    observed_blank_real_vertices = [
        v for v, p in profiles.items() if p["has_blank_and_real_sourcing"]
    ]
    observed_max_entropy = max(p["mode_entropy_bits"] for p in profiles.values())
    observed_max_vertices = [
        v for v, p in profiles.items() if p["mode_entropy_bits"] == observed_max_entropy
    ]

    return {
        "experiment": "tqge_underlay_gate",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE edges and QxG void",
                "tools/data/lab_riflessi.json: operator taxonomy 3 Wick + 1 phase + 1 real + 1 void",
            ],
            "inferred": [
                "vertex profiles from incident edge modes",
                "count-preserving null assignments over the same six edges",
            ],
        },
        "edge_modes": {"".join(edge): mode for edge, mode in EDGE_MODES.items()},
        "vertex_profiles": profiles,
        "void_triangles": voids,
        "observed": {
            "max_entropy_vertices": observed_max_vertices,
            "blank_and_real_sourcing_vertices": observed_blank_real_vertices,
            "G_is_unique_max_entropy": observed_max_vertices == ["G"],
            "G_is_unique_blank_real_hinge": observed_blank_real_vertices == ["G"],
            "all_void_triangles_include_G": all("G" in tri for tri in voids),
        },
        "null": null,
        "interpretation": {
            "passes": [
                "G is the only vertex where the QG blank and GE real_sourcing edge meet.",
                "All void triangles include G because the observed blank edge is QG.",
            ],
            "fails": [
                "G is not a unique maximum-entropy vertex; Q, G, and E all see three distinct incident modes.",
                "The blank-real hinge is not rare under a count-preserving reassignment of one blank and one real edge.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, default=None)
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
