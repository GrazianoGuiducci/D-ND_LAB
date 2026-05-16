#!/usr/bin/env python3
"""
exp_blank_shell_tqger_gate.py

Transfer gate for G_POTENZIALE_NULLA from TQGE to TQGE+R.

The TQGE run found a polarized two-face shell around the blank QG edge:
TQG inert and QGE deposit. This tool extends the perimeter to K5 with R as
frame: R connects to T,Q,G,E through frame edges with no i-pivot. It measures
whether the blank shell stays a two-face object, moves its deposit face, or
dilates into a three-face shell.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import combinations, permutations
from pathlib import Path


VERTICES = ("T", "Q", "G", "E", "R")

EDGE_MODES = {
    ("T", "Q"): "wick_time",
    ("T", "G"): "wick_time",
    ("T", "E"): "wick_time",
    ("Q", "E"): "gauge_phase",
    ("G", "E"): "real_sourcing",
    ("Q", "G"): "blank",
    ("T", "R"): "frame_link",
    ("Q", "R"): "frame_link",
    ("G", "R"): "frame_link",
    ("E", "R"): "frame_link",
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


def classify_blank_face(nonblank_modes: list[str]) -> str:
    counts = Counter(nonblank_modes)
    if counts == Counter({"wick_time": 2}):
        return "inert_wick_pair"
    if counts == Counter({"gauge_phase": 1, "real_sourcing": 1}):
        return "deposit_gauge_real"
    if counts == Counter({"frame_link": 2}):
        return "frame_pair"
    if counts == Counter({"frame_link": 1, "wick_time": 1}):
        return "frame_wick"
    if counts == Counter({"frame_link": 1, "gauge_phase": 1}):
        return "frame_gauge"
    if counts == Counter({"frame_link": 1, "real_sourcing": 1}):
        return "frame_real"
    if "real_sourcing" in counts and "gauge_phase" not in counts:
        return "source_without_gauge"
    if "gauge_phase" in counts and "real_sourcing" not in counts:
        return "gauge_without_source"
    return "+".join(sorted(nonblank_modes))


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
                "side_class": classify_blank_face(nonblank_modes),
            }
        )

    deposit_faces = [
        face for face in shell_faces if face["side_class"] == "deposit_gauge_real"
    ]
    inert_faces = [
        face for face in shell_faces if face["side_class"] == "inert_wick_pair"
    ]
    frame_faces = [face for face in shell_faces if face["side_class"] == "frame_pair"]
    side_classes = sorted(face["side_class"] for face in shell_faces)

    return {
        "blank_edge": edge_name(blank_edge),
        "blank_shell_faces": shell_faces,
        "blank_shell_classes": side_classes,
        "deposit_faces_on_blank": deposit_faces,
        "inert_faces_on_blank": inert_faces,
        "frame_faces_on_blank": frame_faces,
        "has_one_deposit_one_inert_one_frame": side_classes
        == ["deposit_gauge_real", "frame_pair", "inert_wick_pair"],
        "observed_QG_QGE_TQG_QGR": (
            edge_name(blank_edge) == "GQ"
            and [face["face"] for face in deposit_faces] == ["QGE"]
            and [face["face"] for face in inert_faces] == ["TQG"]
            and [face["face"] for face in frame_faces] == ["QGR"]
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
    frame_face_patterns = Counter()

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
        frame_names = "+".join(
            sorted(face["face"] for face in result["frame_faces_on_blank"])
        )
        deposit_face_patterns[deposit_names or "none"] += 1
        inert_face_patterns[inert_names or "none"] += 1
        frame_face_patterns[frame_names or "none"] += 1

        if result["has_one_deposit_one_inert_one_frame"]:
            counts["one_deposit_one_inert_one_frame"] += 1
        if result["blank_edge"] == "GQ":
            counts["blank_edge_is_GQ"] += 1
        if result["observed_QG_QGE_TQG_QGR"]:
            counts["observed_QG_QGE_TQG_QGR"] += 1

    return {
        "n_count_preserving_assignments": n,
        "p_blank_edge_is_GQ": counts["blank_edge_is_GQ"] / n,
        "p_one_deposit_one_inert_one_frame": counts[
            "one_deposit_one_inert_one_frame"
        ]
        / n,
        "p_observed_QG_QGE_TQG_QGR": counts["observed_QG_QGE_TQG_QGR"] / n,
        "blank_shell_pattern_counts": dict(sorted(shell_patterns.items())),
        "deposit_face_pattern_counts": dict(sorted(deposit_face_patterns.items())),
        "inert_face_pattern_counts": dict(sorted(inert_face_patterns.items())),
        "frame_face_pattern_counts": dict(sorted(frame_face_patterns.items())),
    }


def run() -> dict:
    observed = analyze(EDGE_MODES)
    null = summarize_null(null_assignments())
    return {
        "experiment": "blank_shell_tqger_gate",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE has 5 bridges and QxG void",
                "tools/LAB_AGENT_CONTEXT.md: R is connected to all but without i-pivot",
                "tools/dnd_incrocio.py: PONTI_NOTI includes TxR,QxR,GxR,ExR",
                "tools/data/reports/agent_20260507_1957.md: TQGE blank shell polarity",
            ],
            "inferred": [
                "R edges are represented as frame_link category because R is the frame",
                "deposit still requires blank + gauge_phase + real_sourcing on one face",
                "count-preserving null permutes 3 wick, 4 frame, 1 gauge, 1 real, 1 blank over K5 edges",
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
        args_json = args.json_out
        args_json.parent.mkdir(parents=True, exist_ok=True)
        args_json.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
