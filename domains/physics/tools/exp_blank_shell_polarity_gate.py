#!/usr/bin/env python3
"""
exp_blank_shell_polarity_gate.py

Regressive gate for G_POTENZIALE_NULLA after triadic_deposit_gate.

The previous run localized the deposit denominator in QGE as
blank + gauge_phase + real_sourcing. This tool measures the shell around the
blank edge itself: the two faces incident to blank split into an inert face
(blank + wick_time + wick_time) and a deposit face
(blank + gauge_phase + real_sourcing).
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


def face_name(vertices: tuple[str, str, str]) -> str:
    return "".join(vertex for vertex in VERTICES if vertex in vertices)


def face_edges(vertices: tuple[str, str, str]) -> list[tuple[str, str]]:
    return [canon(edge) for edge in combinations(vertices, 2)]


def classify_side(modes_without_blank: list[str]) -> str:
    counts = Counter(modes_without_blank)
    if counts == Counter({"wick_time": 2}):
        return "inert_wick_pair"
    if counts == Counter({"gauge_phase": 1, "real_sourcing": 1}):
        return "deposit_gauge_real"
    if "real_sourcing" in counts and "gauge_phase" not in counts:
        return "source_without_gauge"
    if "gauge_phase" in counts and "real_sourcing" not in counts:
        return "gauge_without_source"
    return "+".join(sorted(modes_without_blank))


def analyze(edge_modes: dict[tuple[str, str], str]) -> dict:
    blank_edges = [edge for edge, mode in edge_modes.items() if mode == "blank"]
    if len(blank_edges) != 1:
        raise ValueError("Expected exactly one blank edge")

    blank_edge = blank_edges[0]
    opposite_vertices = [vertex for vertex in VERTICES if vertex not in blank_edge]
    shell_faces = []

    for opposite in opposite_vertices:
        vertices = tuple(sorted((*blank_edge, opposite)))
        edges = face_edges(vertices)
        modes = [edge_modes[edge] for edge in edges]
        nonblank_modes = [mode for mode in modes if mode != "blank"]
        shell_faces.append(
            {
                "face": face_name(vertices),
                "opposite_vertex": opposite,
                "edge_modes": {edge_name(edge): edge_modes[edge] for edge in edges},
                "nonblank_modes": sorted(nonblank_modes),
                "side_class": classify_side(nonblank_modes),
            }
        )

    side_classes = sorted(face["side_class"] for face in shell_faces)
    deposit_faces = [
        face for face in shell_faces if face["side_class"] == "deposit_gauge_real"
    ]
    inert_faces = [
        face for face in shell_faces if face["side_class"] == "inert_wick_pair"
    ]

    return {
        "blank_edge": edge_name(blank_edge),
        "blank_shell_faces": shell_faces,
        "blank_shell_classes": side_classes,
        "has_polarized_blank_shell": side_classes
        == ["deposit_gauge_real", "inert_wick_pair"],
        "deposit_faces_on_blank": deposit_faces,
        "inert_faces_on_blank": inert_faces,
        "observed_QGE_deposit_TQG_inert": (
            edge_name(blank_edge) == "GQ"
            and [face["face"] for face in deposit_faces] == ["QGE"]
            and [face["face"] for face in inert_faces] == ["TQG"]
        ),
    }


def null_assignments() -> list[dict[tuple[str, str], str]]:
    labels = [EDGE_MODES[edge] for edge in EDGES]
    unique = set(permutations(labels, len(labels)))
    return [dict(zip(EDGES, labels_perm)) for labels_perm in unique]


def summarize_null(assignments: list[dict[tuple[str, str], str]]) -> dict:
    n = len(assignments)
    counts = Counter()
    shell_patterns = Counter()
    deposit_face_patterns = Counter()
    inert_face_patterns = Counter()

    for assignment in assignments:
        result = analyze(assignment)
        pattern = "+".join(result["blank_shell_classes"])
        shell_patterns[pattern] += 1

        deposit_names = "+".join(
            sorted(face["face"] for face in result["deposit_faces_on_blank"])
        )
        inert_names = "+".join(
            sorted(face["face"] for face in result["inert_faces_on_blank"])
        )
        deposit_face_patterns[deposit_names or "none"] += 1
        inert_face_patterns[inert_names or "none"] += 1

        if result["has_polarized_blank_shell"]:
            counts["polarized_blank_shell"] += 1
        if result["blank_edge"] == "GQ":
            counts["blank_edge_is_GQ"] += 1
        if result["observed_QGE_deposit_TQG_inert"]:
            counts["observed_QGE_deposit_TQG_inert"] += 1

    return {
        "n_count_preserving_assignments": n,
        "p_polarized_blank_shell": counts["polarized_blank_shell"] / n,
        "p_blank_edge_is_GQ": counts["blank_edge_is_GQ"] / n,
        "p_observed_QGE_deposit_TQG_inert": counts[
            "observed_QGE_deposit_TQG_inert"
        ]
        / n,
        "blank_shell_pattern_counts": dict(sorted(shell_patterns.items())),
        "deposit_face_pattern_counts": dict(sorted(deposit_face_patterns.items())),
        "inert_face_pattern_counts": dict(sorted(inert_face_patterns.items())),
    }


def run() -> dict:
    observed = analyze(EDGE_MODES)
    null = summarize_null(null_assignments())
    return {
        "experiment": "blank_shell_polarity_gate",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE edges and QxG void",
                "tools/data/reports/agent_20260507_1938.md: QGE triadic deposit face",
                "tools/data/triadic_deposit_gate_20260507_1938.json: TQG as blank without source",
            ],
            "inferred": [
                "the blank edge has a two-face shell in a tetrahedron",
                "deposit requires gauge_phase and real_sourcing on one blank incident face",
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
