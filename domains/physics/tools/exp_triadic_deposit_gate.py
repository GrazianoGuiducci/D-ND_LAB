#!/usr/bin/env python3
"""
exp_triadic_deposit_gate.py

Face-level gate for G_POTENZIALE_NULLA.

The previous hinge run localized Q->G on the QGE face. This tool measures the
next denominator explicitly: a deposit face is not only blank adjacent to
real_sourcing; it is the triangle where blank, gauge_phase and real_sourcing are
all present.
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


def face_modes(edge_modes: dict[tuple[str, str], str]) -> list[dict]:
    faces = []
    for triangle in combinations(VERTICES, 3):
        tri_edges = [canon(edge) for edge in combinations(triangle, 2)]
        modes = [edge_modes[edge] for edge in tri_edges]
        mode_set = set(modes)
        faces.append(
            {
                "triangle": triangle_name(triangle),
                "edge_modes": {edge_name(edge): edge_modes[edge] for edge in tri_edges},
                "has_blank": "blank" in mode_set,
                "has_gauge_phase": "gauge_phase" in mode_set,
                "has_real_sourcing": "real_sourcing" in mode_set,
                "is_triadic_deposit": {
                    "blank",
                    "gauge_phase",
                    "real_sourcing",
                }.issubset(mode_set),
                "is_binary_blank_source": {
                    "blank",
                    "real_sourcing",
                }.issubset(mode_set),
                "mode_signature": "+".join(sorted(modes)),
            }
        )
    return faces


def analyze(edge_modes: dict[tuple[str, str], str]) -> dict:
    faces = face_modes(edge_modes)
    triadic = [face for face in faces if face["is_triadic_deposit"]]
    binary = [face for face in faces if face["is_binary_blank_source"]]
    blank_without_source = [
        face for face in faces if face["has_blank"] and not face["has_real_sourcing"]
    ]
    source_without_blank = [
        face for face in faces if face["has_real_sourcing"] and not face["has_blank"]
    ]
    gauge_without_deposit = [
        face
        for face in faces
        if face["has_gauge_phase"] and not face["is_triadic_deposit"]
    ]
    return {
        "triadic_deposit_faces": triadic,
        "binary_blank_source_faces": binary,
        "blank_without_source_faces": blank_without_source,
        "source_without_blank_faces": source_without_blank,
        "gauge_without_deposit_faces": gauge_without_deposit,
        "all_faces": faces,
    }


def null_assignments() -> list[dict[tuple[str, str], str]]:
    labels = [EDGE_MODES[edge] for edge in EDGES]
    unique = set(permutations(labels, len(labels)))
    return [dict(zip(EDGES, labels_perm)) for labels_perm in unique]


def summarize_null(assignments: list[dict[tuple[str, str], str]]) -> dict:
    n = len(assignments)
    counts = Counter()
    triadic_patterns = Counter()
    binary_patterns = Counter()

    for assignment in assignments:
        result = analyze(assignment)
        triadic_names = "+".join(
            sorted(face["triangle"] for face in result["triadic_deposit_faces"])
        )
        binary_names = "+".join(
            sorted(face["triangle"] for face in result["binary_blank_source_faces"])
        )
        triadic_patterns[triadic_names or "none"] += 1
        binary_patterns[binary_names or "none"] += 1

        if result["triadic_deposit_faces"]:
            counts["triadic_exists"] += 1
        if result["binary_blank_source_faces"]:
            counts["binary_exists"] += 1
        if triadic_names == "QGE":
            counts["triadic_is_QGE"] += 1
        if binary_names == "QGE":
            counts["binary_is_QGE"] += 1

    return {
        "n_count_preserving_assignments": n,
        "p_triadic_deposit_exists": counts["triadic_exists"] / n,
        "p_binary_blank_source_exists": counts["binary_exists"] / n,
        "p_triadic_deposit_is_QGE": counts["triadic_is_QGE"] / n,
        "p_binary_blank_source_is_QGE": counts["binary_is_QGE"] / n,
        "triadic_face_pattern_counts": dict(sorted(triadic_patterns.items())),
        "binary_face_pattern_counts": dict(sorted(binary_patterns.items())),
    }


def run() -> dict:
    observed = analyze(EDGE_MODES)
    null = summarize_null(null_assignments())
    return {
        "experiment": "triadic_deposit_gate",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE edges and QxG void",
                "tools/data/reports/agent_20260507_1804.md: QGE as blank + gauge + source face",
                "tools/evolution_report.md: consecutio asks for triadic blank + gauge + source operator",
            ],
            "inferred": [
                "deposit face requires blank, gauge_phase and real_sourcing in one triangle",
                "binary blank-source contact is a weaker denominator than triadic deposit",
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
