#!/usr/bin/env python3
"""
Quasiperiodic grammar-vs-scale gate.

This tool keeps the old gap_ratio observable but prevents it from deciding the
cycle alone. It pairs it with a local symbolic grammar audit around the largest
spectral gaps, using tridiagonal eigensolver so the denominator stays bounded.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.linalg import eigvalsh_tridiagonal


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)
THETA = 1 / PHI


def parse_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def sturmian_sequence(theta: float, n: int, phase: float = 0.0) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(float)


def balanced_random_like(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.array(seq, copy=True)
    rng.shuffle(out)
    return out


def block_shuffle(seq: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    chunks = [seq[i : i + block] for i in range(0, len(seq), block)]
    rng.shuffle(chunks)
    return np.concatenate(chunks)


def circular_distance(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def nearest_label(ids_value: float, theta: float, max_label: int) -> tuple[int, float]:
    candidates = []
    for label in range(-max_label, max_label + 1):
        if label == 0:
            continue
        frac = (label * theta) % 1.0
        candidates.append((label, circular_distance(ids_value, frac)))
    best_label, error = min(candidates, key=lambda item: (item[1], abs(item[0])))
    return int(best_label), float(error)


def factors(word: str, k: int) -> list[str]:
    if k <= 0 or k > len(word):
        return []
    return [word[i : i + k] for i in range(len(word) - k + 1)]


def palindromic_defect(word: str) -> int:
    pals = {""}
    for i in range(len(word)):
        for j in range(i + 1, len(word) + 1):
            item = word[i:j]
            if item == item[::-1]:
                pals.add(item)
    return max(0, len(word) + 1 - len(pals))


def grammar_excess(word: str, ks: list[int]) -> dict:
    complexity = 0
    right_special = 0
    for k in ks:
        fs = set(factors(word, k))
        complexity += max(0, len(fs) - (k + 1))
        prefixes: dict[str, set[str]] = defaultdict(set)
        for item in factors(word, k + 1):
            prefixes[item[:-1]].add(item[-1])
        right_special += max(0, sum(1 for tails in prefixes.values() if len(tails) > 1) - 1)
    defect = palindromic_defect(word)
    return {
        "complexity_excess": int(complexity),
        "right_special_excess": int(right_special),
        "palindromic_defect": int(defect),
        "grammar_excess_total": int(complexity + right_special + defect),
    }


def window(seq: np.ndarray, center: int, length: int) -> str:
    half = length // 2
    n = len(seq)
    return "".join(str(int(seq[(center - half + i) % n])) for i in range(length))


def summarize(values: list[float | int | None]) -> dict:
    finite = np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if len(finite) == 0:
        return {"count": 0, "none_count": len(values)}
    return {
        "count": int(len(finite)),
        "none_count": int(len(values) - len(finite)),
        "median": float(np.median(finite)),
        "q25": float(np.quantile(finite, 0.25)),
        "q75": float(np.quantile(finite, 0.75)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }


def sequence_observables(seq: np.ndarray, reader_theta: float, threshold: float, args: argparse.Namespace) -> dict:
    diagonal = args.v * seq
    offdiag = np.ones(len(seq) - 1, dtype=float)
    eigs = eigvalsh_tridiagonal(diagonal, offdiag, check_finite=False)
    spacings = np.diff(np.sort(eigs))
    mean_sp = float(np.mean(spacings))
    large = [
        (index, float(spacing))
        for index, spacing in enumerate(spacings)
        if spacing > threshold * mean_sp
    ]
    if len(large) >= 2:
        first_two_ratio = large[0][1] / large[1][1]
    else:
        first_two_ratio = None
    top = sorted((float(spacing) for spacing in spacings), reverse=True)
    top2_ratio = top[0] / top[1] if len(top) >= 2 and top[1] > 0 else None

    selected = sorted(large, key=lambda item: item[1], reverse=True)[: args.top_k]
    labels = []
    grammar_rows = []
    for index, spacing in selected:
        ids = (index + 1) / len(seq)
        label, label_error = nearest_label(ids, reader_theta, args.max_label)
        labels.append(label)
        center = int(round(ids * len(seq))) % len(seq)
        grammar_rows.append({
            "label": label,
            "label_error": label_error,
            "spacing": spacing,
            **grammar_excess(window(seq, center, args.window), parse_ints(args.ks)),
        })

    return {
        "n_large": len(large),
        "first_two_ratio": first_two_ratio,
        "top2_ratio": top2_ratio,
        "label_set": sorted(set(labels), key=lambda value: (abs(value), value)),
        "median_label_error": None if not grammar_rows else float(np.median([row["label_error"] for row in grammar_rows])),
        "median_grammar_excess_total": None if not grammar_rows else float(np.median([row["grammar_excess_total"] for row in grammar_rows])),
        "zero_excess_hits": int(sum(row["grammar_excess_total"] == 0 for row in grammar_rows)),
        "zero_excess_total": len(grammar_rows),
        "grammar_rows": grammar_rows,
    }


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_ints(args.ns)
    phases = parse_floats(args.phases)
    thresholds = parse_floats(args.thresholds)
    domains = {
        "phi": THETA,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }

    rows = []
    comparisons = []
    for n in ns:
        for phase in phases:
            phi_seq = sturmian_sequence(THETA, n, phase)
            for threshold in thresholds:
                matched = {}
                for name, theta in domains.items():
                    seq = sturmian_sequence(theta, n, phase)
                    reader = theta if args.native_reader else THETA
                    obs = sequence_observables(seq, reader, threshold, args)
                    row = {"mode": name, "N": n, "phase": phase, "threshold": threshold, "trial": None, **obs}
                    rows.append(row)
                    matched[name] = row

                for trial in range(args.random_trials):
                    variants = {
                        "balanced_random_phi_density": balanced_random_like(phi_seq, rng),
                        "block_shuffle_phi_density": block_shuffle(phi_seq, args.block_size, rng),
                    }
                    for mode, seq in variants.items():
                        obs = sequence_observables(seq, THETA, threshold, args)
                        rows.append({"mode": mode, "N": n, "phase": phase, "threshold": threshold, "trial": trial, **obs})

                if all(matched[name]["first_two_ratio"] is not None for name in ("phi", "silver", "bronze")):
                    phi_v = float(matched["phi"]["first_two_ratio"])
                    silver_v = float(matched["silver"]["first_two_ratio"])
                    bronze_v = float(matched["bronze"]["first_two_ratio"])
                    comparisons.append({
                        "N": n,
                        "phase": phase,
                        "threshold": threshold,
                        "phi_value": phi_v,
                        "silver_value": silver_v,
                        "bronze_value": bronze_v,
                        "phi_lt_silver": phi_v < silver_v,
                        "phi_lt_bronze": phi_v < bronze_v,
                    })

    summary = {}
    for mode in sorted({row["mode"] for row in rows}):
        subset = [row for row in rows if row["mode"] == mode]
        zero_hits = sum(row["zero_excess_hits"] for row in subset)
        zero_total = sum(row["zero_excess_total"] for row in subset)
        summary[mode] = {
            "conditions": len(subset),
            "first_two_ratio": summarize([row["first_two_ratio"] for row in subset]),
            "top2_ratio": summarize([row["top2_ratio"] for row in subset]),
            "large_gap_count": summarize([row["n_large"] for row in subset]),
            "median_label_error": summarize([row["median_label_error"] for row in subset]),
            "median_grammar_excess_total": summarize([row["median_grammar_excess_total"] for row in subset]),
            "zero_excess_hits": int(zero_hits),
            "zero_excess_total": int(zero_total),
            "zero_excess_rate": None if zero_total == 0 else float(zero_hits / zero_total),
        }

    comparison_summary = {
        "count": len(comparisons),
        "phi_lt_silver": int(sum(row["phi_lt_silver"] for row in comparisons)),
        "phi_lt_bronze": int(sum(row["phi_lt_bronze"] for row in comparisons)),
        "phi_lt_both": int(sum(row["phi_lt_silver"] and row["phi_lt_bronze"] for row in comparisons)),
    }
    return {
        "experiment": "quasiperiodic_grammar_scale_gate",
        "parameters": vars(args),
        "summary": summary,
        "matched_comparison": comparison_summary,
        "comparison_rows": comparisons,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="233,377,610")
    parser.add_argument("--phases", default="0,0.25,0.5")
    parser.add_argument("--thresholds", default="1.75,2.0,2.25")
    parser.add_argument("--random-trials", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--window", type=int, default=55)
    parser.add_argument("--ks", default="3,4,5,6")
    parser.add_argument("--block-size", type=int, default=34)
    parser.add_argument("--v", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=202605141701)
    parser.add_argument("--native-reader", action="store_true")
    parser.add_argument("--out", default="tools/data/quasiperiodic_grammar_scale_gate_20260514_1701.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    compact = {
        mode: {
            "conditions": data["conditions"],
            "first_two_ratio_median": data["first_two_ratio"]["median"],
            "grammar_excess_median": data["median_grammar_excess_total"]["median"],
            "zero_excess_hits": data["zero_excess_hits"],
            "zero_excess_total": data["zero_excess_total"],
            "zero_excess_rate": data["zero_excess_rate"],
        }
        for mode, data in output["summary"].items()
    }
    print(json.dumps({
        "summary": compact,
        "matched_comparison": output["matched_comparison"],
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
