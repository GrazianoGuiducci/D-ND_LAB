#!/usr/bin/env python3
"""
exp_blank_shell_stratified_gate.py

Exact stratified denominator for the blank-shell scale law.

The scale-law experiment found transfer through K7/K8 but left those nulls as
sampled audits. This tool counts only the structural conditions used by the
claim, so the denominator closes without enumerating shell pattern histories.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
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


def subtract(counts: Counter[str], required: Counter[str]) -> Counter[str]:
    remaining = counts.copy()
    for mode, count in required.items():
        remaining[mode] -= count
        if remaining[mode] < 0:
            raise ValueError(f"negative count for {mode}: {remaining[mode]}")
    return remaining


def count_any_deposit_on_blank(vertices: tuple[str, ...], mode_counts: Counter[str]) -> int:
    n_edges = math.comb(len(vertices), 2)
    # Choose the blank edge, choose the opposite shell vertex, put gauge and
    # real on the two shell edges in either order. The rest is unconstrained.
    remaining = subtract(mode_counts, Counter({"blank": 1, "gauge_phase": 1, "real_sourcing": 1}))
    return n_edges * (len(vertices) - 2) * 2 * multinomial(remaining)


def scale_law_requirements(external_count: int) -> Counter[str]:
    required = Counter({"blank": 1, "wick_time": 2, "gauge_phase": 1, "real_sourcing": 1})
    for _, mode in EXTERNAL_VERTICES[:external_count]:
        required[mode] += 2
    return required


def count_scale_law(vertices: tuple[str, ...], mode_counts: Counter[str], external_count: int) -> int:
    # QG is fixed as blank. TQG consumes two wick edges. QGE consumes gauge and
    # real in either order. Every external QGX consumes two edges of its own type.
    remaining = subtract(mode_counts, scale_law_requirements(external_count))
    return 2 * multinomial(remaining)


def observed_shell_faces(external_count: int) -> list[dict[str, str]]:
    faces = [
        {"face": "TQG", "side_class": "inert_wick_pair", "status": "inert"},
        {"face": "QGE", "side_class": "deposit_gauge_real", "status": "deposit"},
    ]
    for vertex, mode in EXTERNAL_VERTICES[:external_count]:
        faces.append(
            {
                "face": f"QG{vertex}",
                "side_class": mode.replace("_link", "_pair"),
                "status": "external_typed",
            }
        )
    return faces


def run(max_external: int) -> dict:
    perimeters = []
    for external_count in range(max_external + 1):
        vertices, edge_modes = build_edge_modes(external_count)
        mode_counts = Counter(edge_modes.values())
        total = multinomial(mode_counts)
        n_edges = math.comb(len(vertices), 2)
        blank_edge_count = total // n_edges
        any_deposit_count = count_any_deposit_on_blank(vertices, mode_counts)
        scale_law_count = count_scale_law(vertices, mode_counts, external_count)

        perimeters.append(
            {
                "name": "+".join(vertices),
                "external_count": external_count,
                "edge_count": n_edges,
                "edge_mode_counts": dict(sorted(mode_counts.items())),
                "observed": {
                    "blank_edge": "GQ",
                    "blank_shell_face_count": len(vertices) - 2,
                    "blank_shell_faces": observed_shell_faces(external_count),
                    "deposit_faces_on_blank": ["QGE"],
                    "scale_law_holds": True,
                },
                "exact_strata": {
                    "n_count_preserving_assignments": total,
                    "blank_edge_is_GQ": {
                        "count": blank_edge_count,
                        "p": blank_edge_count / total,
                    },
                    "any_deposit_on_blank": {
                        "count": any_deposit_count,
                        "p": any_deposit_count / total,
                    },
                    "full_scale_law": {
                        "count": scale_law_count,
                        "p": scale_law_count / total,
                    },
                },
                "verified_formula": {
                    "any_deposit_on_blank": "C(n,2)*(n-2)*2*Multiset(rest after blank,gauge,real)",
                    "full_scale_law": "2*Multiset(rest after blank,2 wick,gauge,real,2 of each external mode)",
                },
            }
        )

    return {
        "experiment": "blank_shell_stratified_gate",
        "source": {
            "verified": [
                "tools/data/reports/agent_20260507_2203.md: sampled K7/K8 audit left exact denominator open",
                "tools/exp_blank_shell_scale_law.py: observed shell law conditions",
            ],
            "inferred": [
                "The null denominator can be stratified by the claim conditions instead of shell pattern histories",
                "U and V remain controlled typed external vertices from the previous perimeter",
            ],
        },
        "observable_names": [
            "blank_edge_is_GQ_count",
            "any_deposit_on_blank_count",
            "full_scale_law_count",
            "shell_face_count",
        ],
        "perimeters": perimeters,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-external", type=int, default=4, choices=range(0, 5))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = run(args.max_external)
    text = json.dumps(result, indent=2, ensure_ascii=True)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
