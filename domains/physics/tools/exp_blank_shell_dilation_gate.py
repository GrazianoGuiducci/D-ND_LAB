#!/usr/bin/env python3
"""
exp_blank_shell_dilation_gate.py

Dilation gate for G_POTENZIALE_NULLA after TQGE+R.

The previous perimeter added R as frame and found that QG blank becomes a
three-face shell: TQG inert, QGE deposit, QGR frame. This tool adds a second
external vertex S as scale carrier and measures whether the deposit migrates or
the shell dilates again.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path


VERTICES = ("T", "Q", "G", "E", "R", "S")

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
    ("T", "S"): "scale_link",
    ("Q", "S"): "scale_link",
    ("G", "S"): "scale_link",
    ("E", "S"): "scale_link",
    ("R", "S"): "scale_link",
}


def canon(edge: tuple[str, str]) -> tuple[str, str]:
    return tuple(sorted(edge))


EDGE_MODES = {canon(edge): mode for edge, mode in EDGE_MODES.items()}
EDGES = tuple(sorted(EDGE_MODES))
MODE_COUNTS = Counter(EDGE_MODES.values())


def edge_name(edge: tuple[str, str]) -> str:
    return "".join(edge)


def face_name(vertices: tuple[str, str, str]) -> str:
    return "".join(vertex for vertex in VERTICES if vertex in vertices)


def face_edges(vertices: tuple[str, str, str]) -> list[tuple[str, str]]:
    return [canon(edge) for edge in combinations(vertices, 2)]


def multinomial(counts: Counter[str]) -> int:
    total = sum(counts.values())
    value = math.factorial(total)
    for count in counts.values():
        value //= math.factorial(count)
    return value


def classify_blank_face(nonblank_modes: list[str]) -> str:
    counts = Counter(nonblank_modes)
    if counts == Counter({"wick_time": 2}):
        return "inert_wick_pair"
    if counts == Counter({"gauge_phase": 1, "real_sourcing": 1}):
        return "deposit_gauge_real"
    if counts == Counter({"frame_link": 2}):
        return "frame_pair"
    if counts == Counter({"scale_link": 2}):
        return "scale_pair"
    if counts == Counter({"frame_link": 1, "scale_link": 1}):
        return "frame_scale"
    if counts == Counter({"frame_link": 1, "wick_time": 1}):
        return "frame_wick"
    if counts == Counter({"scale_link": 1, "wick_time": 1}):
        return "scale_wick"
    if counts == Counter({"frame_link": 1, "gauge_phase": 1}):
        return "frame_gauge"
    if counts == Counter({"scale_link": 1, "gauge_phase": 1}):
        return "scale_gauge"
    if counts == Counter({"frame_link": 1, "real_sourcing": 1}):
        return "frame_real"
    if counts == Counter({"scale_link": 1, "real_sourcing": 1}):
        return "scale_real"
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
    scale_faces = [face for face in shell_faces if face["side_class"] == "scale_pair"]
    side_classes = sorted(face["side_class"] for face in shell_faces)

    return {
        "blank_edge": edge_name(blank_edge),
        "blank_shell_faces": shell_faces,
        "blank_shell_classes": side_classes,
        "deposit_faces_on_blank": deposit_faces,
        "inert_faces_on_blank": inert_faces,
        "frame_faces_on_blank": frame_faces,
        "scale_faces_on_blank": scale_faces,
        "has_one_deposit_one_inert_one_frame_one_scale": side_classes
        == ["deposit_gauge_real", "frame_pair", "inert_wick_pair", "scale_pair"],
        "observed_QG_QGE_TQG_QGR_QGS": (
            edge_name(blank_edge) == "GQ"
            and [face["face"] for face in deposit_faces] == ["QGE"]
            and [face["face"] for face in inert_faces] == ["TQG"]
            and [face["face"] for face in frame_faces] == ["QGR"]
            and [face["face"] for face in scale_faces] == ["QGS"]
        ),
    }


def shell_edges_for_blank(blank_edge: tuple[str, str]) -> list[tuple[str, str]]:
    shell_edges = []
    for opposite in VERTICES:
        if opposite in blank_edge:
            continue
        shell_edges.extend([canon((blank_edge[0], opposite)), canon((blank_edge[1], opposite))])
    return shell_edges


def shell_edge_pairs_for_blank(blank_edge: tuple[str, str]) -> list[tuple[str, list[tuple[str, str]]]]:
    pairs = []
    for opposite in VERTICES:
        if opposite in blank_edge:
            continue
        face = face_name(tuple(sorted((*blank_edge, opposite))))
        pairs.append(
            (
                face,
                [canon((blank_edge[0], opposite)), canon((blank_edge[1], opposite))],
            )
        )
    return pairs


def mode_pair_options(remaining: Counter[str]) -> list[tuple[tuple[str, str], int]]:
    options = []
    modes = tuple(sorted(mode for mode, count in remaining.items() if count > 0))
    for i, first in enumerate(modes):
        for second in modes[i:]:
            if first == second:
                if remaining[first] >= 2:
                    options.append(((first, second), 1))
            elif remaining[first] >= 1 and remaining[second] >= 1:
                options.append(((first, second), 2))
    return options


def summarize_null() -> dict:
    total_assignments = multinomial(MODE_COUNTS)
    counts = Counter()
    shell_patterns = Counter()
    deposit_face_patterns = Counter()
    inert_face_patterns = Counter()
    frame_face_patterns = Counter()
    scale_face_patterns = Counter()

    mode_names = tuple(sorted(MODE_COUNTS))

    for blank_edge in EDGES:
        remaining_after_blank = MODE_COUNTS.copy()
        remaining_after_blank["blank"] -= 1
        if remaining_after_blank["blank"] < 0:
            continue

        shell_pairs = shell_edge_pairs_for_blank(blank_edge)
        rest_edge_count = len(EDGES) - 1 - (2 * len(shell_pairs))
        assignment: dict[tuple[str, str], str] = {blank_edge: "blank"}

        def rec(index: int, remaining: Counter[str], shell_weight: int) -> None:
            if index == len(shell_pairs):
                if sum(remaining.values()) != rest_edge_count:
                    return
                weight = shell_weight * multinomial(remaining)
                shell_modes = dict(assignment)
                result = analyze(shell_modes)
                pattern = "+".join(result["blank_shell_classes"])
                shell_patterns[pattern] += weight

                deposit_names = "+".join(
                    sorted(face["face"] for face in result["deposit_faces_on_blank"])
                )
                inert_names = "+".join(
                    sorted(face["face"] for face in result["inert_faces_on_blank"])
                )
                frame_names = "+".join(
                    sorted(face["face"] for face in result["frame_faces_on_blank"])
                )
                scale_names = "+".join(
                    sorted(face["face"] for face in result["scale_faces_on_blank"])
                )
                deposit_face_patterns[deposit_names or "none"] += weight
                inert_face_patterns[inert_names or "none"] += weight
                frame_face_patterns[frame_names or "none"] += weight
                scale_face_patterns[scale_names or "none"] += weight

                if result["has_one_deposit_one_inert_one_frame_one_scale"]:
                    counts["one_deposit_one_inert_one_frame_one_scale"] += weight
                if result["blank_edge"] == "GQ":
                    counts["blank_edge_is_GQ"] += weight
                if result["observed_QG_QGE_TQG_QGR_QGS"]:
                    counts["observed_QG_QGE_TQG_QGR_QGS"] += weight
                if result["deposit_faces_on_blank"]:
                    counts["any_deposit_on_blank"] += weight
                return

            _, pair_edges = shell_pairs[index]
            for (first, second), pair_weight in mode_pair_options(remaining):
                remaining[first] -= 1
                remaining[second] -= 1
                assignment[pair_edges[0]] = first
                assignment[pair_edges[1]] = second
                rec(index + 1, remaining, shell_weight * pair_weight)
                del assignment[pair_edges[0]]
                del assignment[pair_edges[1]]
                remaining[first] += 1
                remaining[second] += 1

        rec(0, remaining_after_blank, 1)

    return {
        "n_count_preserving_assignments": total_assignments,
        "p_blank_edge_is_GQ": counts["blank_edge_is_GQ"] / total_assignments,
        "p_any_deposit_on_blank": counts["any_deposit_on_blank"] / total_assignments,
        "p_one_deposit_one_inert_one_frame_one_scale": counts[
            "one_deposit_one_inert_one_frame_one_scale"
        ]
        / total_assignments,
        "p_observed_QG_QGE_TQG_QGR_QGS": counts[
            "observed_QG_QGE_TQG_QGR_QGS"
        ]
        / total_assignments,
        "blank_shell_pattern_counts": dict(sorted(shell_patterns.items())),
        "deposit_face_pattern_counts": dict(sorted(deposit_face_patterns.items())),
        "inert_face_pattern_counts": dict(sorted(inert_face_patterns.items())),
        "frame_face_pattern_counts": dict(sorted(frame_face_patterns.items())),
        "scale_face_pattern_counts": dict(sorted(scale_face_patterns.items())),
    }


def run() -> dict:
    observed = analyze(EDGE_MODES)
    null = summarize_null()
    return {
        "experiment": "blank_shell_dilation_gate",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE has 5 bridges and QxG void",
                "tools/LAB_AGENT_CONTEXT.md: R is connected to all but without i-pivot",
                "tools/data/reports/agent_20260507_2120.md: TQGE+R blank shell becomes tri-facial",
                "tools/build_lab_graph.py: graph header includes TQGE+R+S as lab graph perimeter",
            ],
            "inferred": [
                "S is represented as scale_link because it enters as controlled scale carrier",
                "deposit still requires blank + gauge_phase + real_sourcing on one face",
                "count-preserving null permutes 3 wick, 4 frame, 5 scale, 1 gauge, 1 real, 1 blank over K6 edges",
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
    text = json.dumps(result, indent=2, ensure_ascii=True)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
