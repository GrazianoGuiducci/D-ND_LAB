#!/usr/bin/env python3
"""
Generator gate for phi gap-label stability.

The label-set audit moved the observable from the first-two gap ratio to the
set of large-gap labels. This tool tests the next denominator: the generator.
It keeps the phi label reader fixed and changes the sequence generator while
preserving different amounts of structure.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from exp_gap_label_set_stability import PHI, gap_labels, jaccard, sturmian_sequence, summarize_sets


THETA = 1 / PHI


def fibonacci_word(n: int) -> np.ndarray:
    word = "1"
    previous = "0"
    while len(word) < n:
        word, previous = word + previous, word
    return np.array([float(ch) for ch in word[:n]], dtype=float)


def rotate(seq: np.ndarray, phase: float) -> np.ndarray:
    if len(seq) == 0:
        return seq
    shift = int(round((phase % 1.0) * len(seq)))
    return np.roll(seq, shift)


def transition_matrix(seq: np.ndarray) -> tuple[np.ndarray, float]:
    counts = np.ones((2, 2), dtype=float)
    ints = seq.astype(int)
    for a, b in zip(ints[:-1], ints[1:]):
        counts[a, b] += 1
    probs = counts / counts.sum(axis=1, keepdims=True)
    start_prob = float(np.mean(ints))
    return probs, start_prob


def markov_surrogate(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    probs, start_prob = transition_matrix(seq)
    out = np.zeros(len(seq), dtype=float)
    out[0] = 1.0 if rng.random() < start_prob else 0.0
    for i in range(1, len(seq)):
        prev = int(out[i - 1])
        out[i] = 1.0 if rng.random() < probs[prev, 1] else 0.0
    return out


def balanced_random(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.array(seq, dtype=float)
    rng.shuffle(out)
    return out


def block_shuffle(seq: np.ndarray, block_size: int, rng: np.random.Generator) -> np.ndarray:
    blocks = [seq[i : i + block_size].copy() for i in range(0, len(seq), block_size)]
    rng.shuffle(blocks)
    return np.concatenate(blocks)


def generator_sequences(n: int, phase: float, trial: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    phi = sturmian_sequence(THETA, n, phase)
    fib = rotate(fibonacci_word(n), phase)
    return {
        "phi_sturmian": phi,
        "fibonacci_substitution": fib,
        "markov_phi": markov_surrogate(phi, rng),
        "block_shuffle_13": block_shuffle(phi, 13, rng),
        "block_shuffle_34": block_shuffle(phi, 34, rng),
        "balanced_random": balanced_random(phi, rng),
    }


def summarize_generators(rows: list[dict], reference_core: set[int]) -> dict:
    output = {}
    for generator in sorted({row["generator"] for row in rows}):
        group = [row for row in rows if row["generator"] == generator]
        summary = summarize_sets(group)
        if not summary:
            continue
        overlaps = [jaccard(set(row["label_set"]), reference_core) for row in group if row["n_selected"] > 0]
        core = set(summary["core_labels_all_conditions"])
        output[generator] = {
            **summary,
            "median_overlap_with_phi_core": float(np.median(overlaps)) if overlaps else None,
            "min_overlap_with_phi_core": float(np.min(overlaps)) if overlaps else None,
            "reference_core_retained": sorted(core & reference_core, key=lambda x: (abs(x), x)),
            "reference_core_missing": sorted(reference_core - core, key=lambda x: (abs(x), x)),
        }
    return output


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = [int(x) for x in args.ns.split(",")]
    phases = [float(x) for x in args.phases.split(",")]
    thresholds = [float(x) for x in args.thresholds.split(",")]

    rows = []
    for n in ns:
        for phase in phases:
            for trial in range(args.trials):
                seqs = generator_sequences(n, phase, trial, rng)
                for generator, seq in seqs.items():
                    for threshold in thresholds:
                        obs = gap_labels(seq, THETA, threshold, args.max_label, args.top_k)
                        rows.append({
                            "generator": generator,
                            "N": n,
                            "phase": phase,
                            "trial": trial,
                            "threshold": threshold,
                            **obs,
                        })

    phi_rows = [row for row in rows if row["generator"] == "phi_sturmian"]
    reference_core = set(summarize_sets(phi_rows)["core_labels_all_conditions"])
    summary = summarize_generators(rows, reference_core)

    by_generator_threshold = defaultdict(list)
    for row in rows:
        by_generator_threshold[(row["generator"], row["threshold"])].append(row)
    threshold_summary = {
        f"{generator}|threshold={threshold}": summarize_sets(group)
        for (generator, threshold), group in by_generator_threshold.items()
    }

    return {
        "experiment": "gap_label_generator_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "trials": args.trials,
            "top_k": args.top_k,
            "max_label": args.max_label,
            "seed": args.seed,
        },
        "reference_core_phi": sorted(reference_core, key=lambda x: (abs(x), x)),
        "summary": summary,
        "threshold_summary": threshold_summary,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="233,377,500,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="1.75,2.0,2.25")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=20260508)
    parser.add_argument("--out", default="tools/data/gap_label_generator_gate_20260508_1715.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        generator: {
            "median_jaccard": data["median_jaccard"],
            "min_jaccard": data["min_jaccard"],
            "median_overlap_with_phi_core": data["median_overlap_with_phi_core"],
            "reference_core_missing": data["reference_core_missing"],
            "core_labels_all_conditions": data["core_labels_all_conditions"],
        }
        for generator, data in output["summary"].items()
    }
    print(json.dumps({
        "reference_core_phi": output["reference_core_phi"],
        "summary": compact,
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
