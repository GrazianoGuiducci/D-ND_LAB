#!/usr/bin/env python3
"""
exp_blank_shell_scale_law.py

Scale law for the blank shell around QG.

The previous gates measured TQGE, TQGE+R, and TQGE+R+S separately. This tool
turns that chain into one reusable perimeter: start from TQGE, add typed
external vertices one by one, and measure whether the deposit migrates or the
blank shell gains one typed non-depositing face per external vertex.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from functools import lru_cache
from itertools import combinations
from pathlib import Path


BASE_VERTICES = ("T", "Q", "G", "E")
EXTERNAL_VERTICES = (
    ("R", "frame_link"),
    ("S", "scale_link"),
    ("U", "boundary_link"),
    ("V", "observer_link"),
)

BASE_EDGE_MODES = {
    ("T", "Q"): "wick_time",
    ("T", "G"): "wick_time",
    ("T", "E"): "wick_time",
    ("Q", "E"): "gauge_phase",
    ("G", "E"): "real_sourcing",
    ("Q", "G"): "blank",
}


def canon(edge: tuple[str, str]) -> tuple[str, str]:
    return tuple(sorted(edge))


def edge_name(edge: tuple[str, str]) -> str:
    return "".join(edge)


def face_name(vertices: tuple[str, str, str], vertex_order: tuple[str, ...]) -> str:
    return "".join(vertex for vertex in vertex_order if vertex in vertices)


def face_edges(vertices: tuple[str, str, str]) -> list[tuple[str, str]]:
    return [canon(edge) for edge in combinations(vertices, 2)]


def multinomial(counts: Counter[str]) -> int:
    total = sum(counts.values())
    value = math.factorial(total)
    for count in counts.values():
        value //= math.factorial(count)
    return value


def build_edge_modes(external_count: int) -> tuple[tuple[str, ...], dict[tuple[str, str], str]]:
    externals = EXTERNAL_VERTICES[:external_count]
    vertices = (*BASE_VERTICES, *(name for name, _ in externals))
    edge_modes = {canon(edge): mode for edge, mode in BASE_EDGE_MODES.items()}

    for vertex, mode in externals:
        for prior in vertices:
            if prior == vertex:
                break
            edge_modes[canon((prior, vertex))] = mode

    return vertices, edge_modes


def classify_blank_face(nonblank_modes: list[str]) -> str:
    counts = Counter(nonblank_modes)
    if counts == Counter({"wick_time": 2}):
        return "inert_wick_pair"
    if counts == Counter({"gauge_phase": 1, "real_sourcing": 1}):
        return "deposit_gauge_real"

    if len(counts) == 1:
        mode = next(iter(counts))
        if counts[mode] == 2 and mode.endswith("_link"):
            return mode.replace("_link", "_pair")

    if "real_sourcing" in counts and "gauge_phase" not in counts:
        return "source_without_gauge"
    if "gauge_phase" in counts and "real_sourcing" not in counts:
        return "gauge_without_source"
    return "+".join(sorted(nonblank_modes))


def analyze(
    vertices: tuple[str, ...], edge_modes: dict[tuple[str, str], str]
) -> dict:
    blank_edges = [edge for edge, mode in edge_modes.items() if mode == "blank"]
    if len(blank_edges) != 1:
        raise ValueError("Expected exactly one blank edge")

    blank_edge = blank_edges[0]
    shell_faces = []
    for opposite in vertices:
        if opposite in blank_edge:
            continue
        face_vertices = tuple(sorted((*blank_edge, opposite)))
        edges = face_edges(face_vertices)
        modes = [edge_modes[edge] for edge in edges]
        nonblank_modes = sorted(mode for mode in modes if mode != "blank")
        shell_faces.append(
            {
                "face": face_name(face_vertices, vertices),
                "opposite_vertex": opposite,
                "edge_modes": {edge_name(edge): edge_modes[edge] for edge in edges},
                "nonblank_modes": nonblank_modes,
                "side_class": classify_blank_face(nonblank_modes),
            }
        )

    deposit_faces = [
        face for face in shell_faces if face["side_class"] == "deposit_gauge_real"
    ]
    inert_faces = [
        face for face in shell_faces if face["side_class"] == "inert_wick_pair"
    ]
    external_faces = [
        face
        for face in shell_faces
        if face["side_class"] not in {"deposit_gauge_real", "inert_wick_pair"}
    ]
    side_classes = sorted(face["side_class"] for face in shell_faces)

    expected_by_face = expected_shell_face_classes(vertices)
    expected_classes = list(expected_by_face.values())

    return {
        "vertices": list(vertices),
        "blank_edge": edge_name(blank_edge),
        "blank_shell_face_count": len(shell_faces),
        "blank_shell_faces": shell_faces,
        "blank_shell_classes": side_classes,
        "deposit_faces_on_blank": deposit_faces,
        "inert_faces_on_blank": inert_faces,
        "external_faces_on_blank": external_faces,
        "deposit_is_QGE": [face["face"] for face in deposit_faces] == ["QGE"],
        "inert_is_TQG": [face["face"] for face in inert_faces] == ["TQG"],
        "scale_law_holds": (
            edge_name(blank_edge) == "GQ"
            and [face["face"] for face in deposit_faces] == ["QGE"]
            and [face["face"] for face in inert_faces] == ["TQG"]
            and side_classes == sorted(expected_classes)
            and all(
                face["side_class"] == expected_by_face.get(face["face"])
                for face in shell_faces
            )
        ),
    }


def expected_shell_face_classes(vertices: tuple[str, ...]) -> dict[str, str]:
    expected = {"TQG": "inert_wick_pair", "QGE": "deposit_gauge_real"}
    for vertex, mode in EXTERNAL_VERTICES[: max(0, len(vertices) - len(BASE_VERTICES))]:
        expected[f"QG{vertex}"] = mode.replace("_link", "_pair")
    return expected


def shell_edge_pairs_for_blank(
    vertices: tuple[str, ...], blank_edge: tuple[str, str]
) -> list[tuple[str, list[tuple[str, str]]]]:
    pairs = []
    for opposite in vertices:
        if opposite in blank_edge:
            continue
        face = face_name(tuple(sorted((*blank_edge, opposite))), vertices)
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
    for index, first in enumerate(modes):
        for second in modes[index:]:
            if first == second:
                if remaining[first] >= 2:
                    options.append(((first, second), 1))
            elif remaining[first] >= 1 and remaining[second] >= 1:
                options.append(((first, second), 2))
    return options


def summarize_null(
    vertices: tuple[str, ...], edge_modes: dict[tuple[str, str], str]
) -> dict:
    edges = tuple(sorted(edge_modes))
    mode_counts = Counter(edge_modes.values())
    total_assignments = multinomial(mode_counts)
    counts = Counter()
    shell_patterns = Counter()
    mode_order = tuple(sorted(mode_counts))
    expected_by_face = expected_shell_face_classes(vertices)
    expected_classes = tuple(sorted(expected_by_face.values()))

    for blank_edge in edges:
        remaining_after_blank = mode_counts.copy()
        remaining_after_blank["blank"] -= 1
        if remaining_after_blank["blank"] < 0:
            continue

        shell_pairs = shell_edge_pairs_for_blank(vertices, blank_edge)
        rest_edge_count = len(edges) - 1 - (2 * len(shell_pairs))

        @lru_cache(maxsize=None)
        def rec(
            index: int,
            remaining_tuple: tuple[int, ...],
            classes: tuple[str, ...],
            deposit_faces: tuple[str, ...],
            inert_faces: tuple[str, ...],
            law_faces_ok: bool,
        ) -> Counter:
            remaining = Counter(dict(zip(mode_order, remaining_tuple)))
            if index == len(shell_pairs):
                if sum(remaining.values()) != rest_edge_count:
                    return Counter()
                weight = multinomial(remaining)
                pattern = "+".join(sorted(classes))
                aggregate = Counter({("pattern", pattern): weight})
                if edge_name(blank_edge) == "GQ":
                    aggregate[("count", "blank_edge_is_GQ")] += weight
                if deposit_faces:
                    aggregate[("count", "any_deposit_on_blank")] += weight
                if (
                    edge_name(blank_edge) == "GQ"
                    and law_faces_ok
                    and tuple(sorted(classes)) == expected_classes
                    and deposit_faces == ("QGE",)
                    and inert_faces == ("TQG",)
                ):
                    aggregate[("count", "scale_law_holds")] += weight
                return aggregate

            face, _ = shell_pairs[index]
            aggregate = Counter()
            for (first, second), pair_weight in mode_pair_options(remaining):
                remaining[first] -= 1
                remaining[second] -= 1
                side_class = classify_blank_face(sorted((first, second)))
                next_deposit_faces = deposit_faces
                next_inert_faces = inert_faces
                if side_class == "deposit_gauge_real":
                    next_deposit_faces = tuple(sorted((*deposit_faces, face)))
                if side_class == "inert_wick_pair":
                    next_inert_faces = tuple(sorted((*inert_faces, face)))
                next_law_faces_ok = law_faces_ok and (
                    side_class == expected_by_face.get(face)
                )
                suffix = rec(
                    index + 1,
                    tuple(remaining[mode] for mode in mode_order),
                    tuple(sorted((*classes, side_class))),
                    next_deposit_faces,
                    next_inert_faces,
                    next_law_faces_ok,
                )
                for key, value in suffix.items():
                    aggregate[key] += pair_weight * value
                remaining[first] += 1
                remaining[second] += 1
            return aggregate

        aggregate = rec(
            0,
            tuple(remaining_after_blank[mode] for mode in mode_order),
            (),
            (),
            (),
            True,
        )
        for key, value in aggregate.items():
            kind, name = key
            if kind == "pattern":
                shell_patterns[name] += value
            else:
                counts[name] += value

    return {
        "n_count_preserving_assignments": total_assignments,
        "count_blank_edge_is_GQ": counts["blank_edge_is_GQ"],
        "count_any_deposit_on_blank": counts["any_deposit_on_blank"],
        "count_scale_law_holds": counts["scale_law_holds"],
        "p_blank_edge_is_GQ": counts["blank_edge_is_GQ"] / total_assignments,
        "p_any_deposit_on_blank": counts["any_deposit_on_blank"] / total_assignments,
        "p_scale_law_holds": counts["scale_law_holds"] / total_assignments,
        "blank_shell_pattern_counts": dict(sorted(shell_patterns.items())),
    }


def sample_null(
    vertices: tuple[str, ...],
    edge_modes: dict[tuple[str, str], str],
    samples: int,
    seed: int,
) -> dict:
    edges = tuple(sorted(edge_modes))
    labels = [edge_modes[edge] for edge in edges]
    rng = random.Random(seed)
    counts = Counter()
    shell_patterns = Counter()

    for _ in range(samples):
        shuffled = labels[:]
        rng.shuffle(shuffled)
        assignment = dict(zip(edges, shuffled))
        result = analyze(vertices, assignment)
        pattern = "+".join(result["blank_shell_classes"])
        shell_patterns[pattern] += 1
        if result["blank_edge"] == "GQ":
            counts["blank_edge_is_GQ"] += 1
        if result["deposit_faces_on_blank"]:
            counts["any_deposit_on_blank"] += 1
        if result["scale_law_holds"]:
            counts["scale_law_holds"] += 1

    return {
        "n_sampled_assignments": samples,
        "seed": seed,
        "count_blank_edge_is_GQ": counts["blank_edge_is_GQ"],
        "count_any_deposit_on_blank": counts["any_deposit_on_blank"],
        "count_scale_law_holds": counts["scale_law_holds"],
        "p_blank_edge_is_GQ": counts["blank_edge_is_GQ"] / samples,
        "p_any_deposit_on_blank": counts["any_deposit_on_blank"] / samples,
        "p_scale_law_holds": counts["scale_law_holds"] / samples,
        "blank_shell_pattern_counts": dict(sorted(shell_patterns.items())),
    }


def run(max_external: int, exact_null_max_external: int, samples_after: int) -> dict:
    perimeters = []
    for external_count in range(max_external + 1):
        vertices, edge_modes = build_edge_modes(external_count)
        observed = analyze(vertices, edge_modes)
        if external_count <= exact_null_max_external:
            null_mode = "exact_count_preserving"
            null = summarize_null(vertices, edge_modes)
        else:
            null_mode = "sampled_count_preserving"
            null = sample_null(
                vertices,
                edge_modes,
                samples_after,
                seed=202605072203 + external_count,
            )
        perimeters.append(
            {
                "name": "+".join(vertices),
                "external_count": external_count,
                "null_mode": null_mode,
                "edge_mode_counts": dict(sorted(Counter(edge_modes.values()).items())),
                "edge_modes": {edge_name(edge): mode for edge, mode in sorted(edge_modes.items())},
                "observed": observed,
                "null": null,
            }
        )

    return {
        "experiment": "blank_shell_scale_law",
        "source": {
            "verified": [
                "tools/LAB_AGENT_CONTEXT.md: TQGE has 5 bridges and QxG void",
                "tools/LAB_AGENT_CONTEXT.md: R is connected to all but without i-pivot",
                "tools/data/reports/agent_20260507_1957.md: TQGE blank shell is TQG/QGE",
                "tools/data/reports/agent_20260507_2120.md: R adds QGR as frame face",
                "tools/data/reports/agent_20260507_2157.md: S adds QGS as scale face",
            ],
            "inferred": [
                "U and V are controlled typed external vertices, used only to test the scale law after R and S",
                "An external vertex carries one operator mode on every edge to the previous perimeter",
                "Deposit still requires blank + gauge_phase + real_sourcing on one face",
                "Count-preserving null permutes the same mode multiset inside each complete-graph perimeter",
                "K7 and K8 use sampled null audit when exact shell DP exceeds cycle budget",
            ],
        },
        "perimeters": perimeters,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-external", type=int, default=4, choices=range(0, 5))
    parser.add_argument("--exact-null-max-external", type=int, default=2, choices=range(0, 5))
    parser.add_argument("--samples-after", type=int, default=50000)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = run(args.max_external, args.exact_null_max_external, args.samples_after)
    text = json.dumps(result, indent=2, ensure_ascii=True)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
