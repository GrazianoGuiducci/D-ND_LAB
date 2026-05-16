#!/usr/bin/env python3
"""
Symbolic grammar gate for the phi high-core gap labels.

The position/error gate did not separate exact supertile boundaries from
misaligned chunks. This tool moves to native word grammar around the IDS
positions of selected gap labels. It keeps the classical Sturmian baseline
explicit: low complexity p(k) <= k + 1, at most one right-special factor per k,
palindromic richness, and two-return-word behavior when finite data can see it.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_block_scale_gate import REFERENCE_HIGH, REFERENCE_LOW, label_sort, parse_floats, parse_ints
from exp_gap_label_generator_gate import THETA
from exp_gap_label_set_stability import gap_labels, sturmian_sequence
from exp_gap_label_supertile_tiling_gate import (
    chunks_from_lengths,
    internal_count_shuffle,
    misaligned_same_lengths,
    shuffle_chunks,
    supertile_lengths,
)


def selected_by_label(row: dict) -> dict[int, dict]:
    best: dict[int, dict] = {}
    for item in row["selected"]:
        current = best.get(item["label"])
        if current is None or item["label_error"] < current["label_error"]:
            best[item["label"]] = item
    return best


def circular_window(seq: np.ndarray, center: int, length: int) -> str:
    n = len(seq)
    half = length // 2
    indexes = [(center - half + i) % n for i in range(length)]
    return "".join(str(int(seq[i])) for i in indexes)


def factors(word: str, k: int) -> list[str]:
    if k <= 0 or k > len(word):
        return []
    return [word[i : i + k] for i in range(len(word) - k + 1)]


def palindromic_defect(word: str) -> int:
    pals = {""}
    for i in range(len(word)):
        for j in range(i + 1, len(word) + 1):
            f = word[i:j]
            if f == f[::-1]:
                pals.add(f)
    return len(word) + 1 - len(pals)


def return_word_excess(word: str, k: int) -> int:
    max_excess = 0
    seen = set(factors(word, k))
    for factor in seen:
        starts = [i for i in range(len(word) - k + 1) if word[i : i + k] == factor]
        if len(starts) < 2:
            continue
        returns = set()
        for a, b in zip(starts[:-1], starts[1:]):
            returns.add(word[a:b])
        max_excess = max(max_excess, max(0, len(returns) - 2))
    return max_excess


def grammar_metrics(word: str, ks: list[int]) -> dict:
    by_k = {}
    complexity_excess = 0
    right_special_excess = 0
    return_excess = 0
    for k in ks:
        fs = factors(word, k)
        unique = sorted(set(fs))
        p_k = len(unique)
        prefixes: dict[str, set[str]] = defaultdict(set)
        for f in factors(word, k + 1):
            prefixes[f[:-1]].add(f[-1])
        right_special = sum(1 for suffixes in prefixes.values() if len(suffixes) > 1)
        k_return_excess = return_word_excess(word, k)
        c_excess = max(0, p_k - (k + 1))
        rs_excess = max(0, right_special - 1)
        complexity_excess += c_excess
        right_special_excess += rs_excess
        return_excess += k_return_excess
        by_k[str(k)] = {
            "p_k": p_k,
            "sturmian_bound": k + 1,
            "complexity_excess": c_excess,
            "right_special_count": right_special,
            "right_special_excess": rs_excess,
            "return_word_excess": k_return_excess,
        }
    defect = palindromic_defect(word)
    return {
        "length": len(word),
        "complexity_excess_sum": int(complexity_excess),
        "right_special_excess_sum": int(right_special_excess),
        "return_word_excess_sum": int(return_excess),
        "palindromic_defect": int(defect),
        "grammar_excess_total": int(complexity_excess + right_special_excess + return_excess + defect),
        "by_k": by_k,
    }


def row_with_obs(mode: str, seq: np.ndarray, n: int, phase: float, threshold: float, trial: int | None, order: int | None, args: argparse.Namespace) -> dict:
    row = {
        "mode": mode,
        "N": n,
        "phase": phase,
        "threshold": threshold,
        **gap_labels(seq, THETA, threshold, args.max_label, args.top_k),
    }
    if trial is not None:
        row["trial"] = trial
    if order is not None:
        row["supertile_order"] = order
    return row


def collect_label_windows(row: dict, seq: np.ndarray, labels: set[int], label_group: str, window: int, ks: list[int]) -> list[dict]:
    selected = selected_by_label(row)
    output = []
    for label in label_sort(labels & set(selected)):
        item = selected[label]
        center = int(round(item["ids"] * len(seq))) % len(seq)
        word = circular_window(seq, center, window)
        output.append({
            "mode": row["mode"],
            "N": row["N"],
            "phase": row["phase"],
            "threshold": row["threshold"],
            "trial": row.get("trial"),
            "supertile_order": row.get("supertile_order"),
            "label_group": label_group,
            "label": int(label),
            "ids": item["ids"],
            "label_error": item["label_error"],
            "center": center,
            "word": word,
            **grammar_metrics(word, ks),
        })
    return output


def summarize_windows(rows: list[dict]) -> dict:
    if not rows:
        return {
            "windows": 0,
            "zero_excess_rate": None,
            "median_grammar_excess_total": None,
            "median_complexity_excess_sum": None,
            "median_right_special_excess_sum": None,
            "median_return_word_excess_sum": None,
            "median_palindromic_defect": None,
        }
    return {
        "windows": len(rows),
        "zero_excess_count": int(sum(row["grammar_excess_total"] == 0 for row in rows)),
        "zero_excess_rate": float(sum(row["grammar_excess_total"] == 0 for row in rows) / len(rows)),
        "median_grammar_excess_total": float(np.median([row["grammar_excess_total"] for row in rows])),
        "median_complexity_excess_sum": float(np.median([row["complexity_excess_sum"] for row in rows])),
        "median_right_special_excess_sum": float(np.median([row["right_special_excess_sum"] for row in rows])),
        "median_return_word_excess_sum": float(np.median([row["return_word_excess_sum"] for row in rows])),
        "median_palindromic_defect": float(np.median([row["palindromic_defect"] for row in rows])),
    }


def grouped_summary(rows: list[dict], keys: list[str]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = "|".join(f"{k}={row.get(k)}" for k in keys)
        groups[key].append(row)
    return {key: summarize_windows(group) for key, group in sorted(groups.items())}


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_ints(args.ns)
    phases = parse_floats(args.phases)
    thresholds = parse_floats(args.thresholds)
    orders = parse_ints(args.supertile_orders)
    ks = parse_ints(args.ks)

    reference_rows = []
    grammar_rows = []
    for n in ns:
        for phase in phases:
            phi = sturmian_sequence(THETA, n, phase)
            for threshold in thresholds:
                ref = row_with_obs("reference_phi", phi, n, phase, threshold, None, None, args)
                reference_rows.append(ref)
                grammar_rows.extend(collect_label_windows(ref, phi, set(REFERENCE_HIGH), "high", args.window, ks))
                grammar_rows.extend(collect_label_windows(ref, phi, set(REFERENCE_LOW), "low", args.window, ks))

            for order in orders:
                lengths = supertile_lengths(n, order)
                aligned_chunks = chunks_from_lengths(phi, lengths)
                for trial in range(args.trials):
                    variants = {
                        "supertile_shuffle": shuffle_chunks(aligned_chunks, rng),
                        "same_length_contiguous_shuffle": misaligned_same_lengths(phi, lengths, rng),
                        "same_count_internal_shuffle": internal_count_shuffle(aligned_chunks, rng),
                    }
                    for mode, seq in variants.items():
                        for threshold in thresholds:
                            row = row_with_obs(mode, seq, n, phase, threshold, trial, order, args)
                            grammar_rows.extend(collect_label_windows(row, seq, set(REFERENCE_HIGH), "high", args.window, ks))
                            grammar_rows.extend(collect_label_windows(row, seq, set(REFERENCE_LOW), "low", args.window, ks))

    return {
        "experiment": "gap_label_symbolic_grammar_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "trials": args.trials,
            "supertile_orders": orders,
            "window": args.window,
            "ks": ks,
            "top_k": args.top_k,
            "max_label": args.max_label,
            "seed": args.seed,
        },
        "sturmian_baseline": {
            "complexity_bound": "p(k) <= k + 1 on finite factors; equality is not required in a short window",
            "right_special_bound": "at most one right-special factor for each k in the ideal Sturmian language",
            "palindromic_baseline": "Sturmian factors are rich; palindromic defect 0 is the finite-window target",
            "return_words_baseline": "each recurrent Sturmian factor has two return words; finite windows only test excess above two when repeated occurrences exist",
        },
        "summary_by_mode_group": grouped_summary(grammar_rows, ["mode", "label_group"]),
        "summary_by_mode_order_group": grouped_summary(grammar_rows, ["mode", "supertile_order", "label_group"]),
        "summary_by_label": grouped_summary(grammar_rows, ["mode", "label_group", "label"]),
        "grammar_rows": grammar_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="377,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="2.0")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--supertile-orders", default="8,9,10,11")
    parser.add_argument("--window", type=int, default=89)
    parser.add_argument("--ks", default="3,4,5,6,7,8")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=202605082005)
    parser.add_argument("--out", default="tools/data/gap_label_symbolic_grammar_gate_20260508_2005.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        key: {
            "windows": data["windows"],
            "zero_excess": f"{data.get('zero_excess_count')}/{data['windows']}" if data["windows"] else None,
            "median_total": data["median_grammar_excess_total"],
            "median_complexity": data["median_complexity_excess_sum"],
            "median_right_special": data["median_right_special_excess_sum"],
            "median_return_excess": data["median_return_word_excess_sum"],
            "median_pal_defect": data["median_palindromic_defect"],
        }
        for key, data in output["summary_by_mode_group"].items()
    }
    print(json.dumps({"summary_by_mode_group": compact, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
