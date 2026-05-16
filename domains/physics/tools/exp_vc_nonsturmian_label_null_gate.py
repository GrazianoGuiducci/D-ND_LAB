#!/usr/bin/env python3
"""
Non-Sturmian label-preserving null gate for the quasiperiodic V_c boundary.

The phase bridge made the label set reachable at N=144, but only inside a
Sturmian source mode. This tool asks the narrower next question: can a
non-Sturmian generator preserve the phi gap-label reader enough to pass
Jaccard>=0.75 while keeping a non-trivial Hamming distance?
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from exp_gap_label_set_stability import PHI, gap_labels, jaccard, sturmian_sequence
from exp_vc_label_preserving_swap_gate import crossing_event, curve_for_sequence, hamming_ratio


THETA = 1 / PHI
STURMIAN_SOURCE_MODES = {"phi_sturmian", "phase_shift_sturmian"}


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def make_candidate_id(n: int, phase: float, source_mode: str, trial: int) -> str:
    return f"N{n}:phase{phase:g}:{source_mode}:trial{trial}"


def label_set(seq: np.ndarray, args: argparse.Namespace) -> set[int]:
    obs = gap_labels(seq, THETA, args.label_threshold, args.max_label, args.top_k)
    return set(obs["label_set"])


def score_sequence(seq: np.ndarray, reference_labels: set[int], args: argparse.Namespace) -> float:
    return float(jaccard(label_set(seq, args), reference_labels))


def balanced_random(reference: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.array(reference, copy=True)
    rng.shuffle(out)
    return out


def block_shuffle(reference: np.ndarray, block_size: int, rng: np.random.Generator) -> np.ndarray:
    chunks = [reference[i : i + block_size].copy() for i in range(0, len(reference), block_size)]
    rng.shuffle(chunks)
    return np.concatenate(chunks)


def periodic_approximant(reference: np.ndarray, period: int, rng: np.random.Generator) -> np.ndarray:
    word = np.array(reference[:period], copy=True)
    out = np.resize(word, len(reference)).astype(float)
    target_ones = int(np.sum(reference))
    delta = int(target_ones - np.sum(out))
    if delta > 0:
        zeros = np.flatnonzero(out < 0.5)
        if len(zeros):
            out[rng.choice(zeros, size=min(delta, len(zeros)), replace=False)] = 1.0
    elif delta < 0:
        ones = np.flatnonzero(out > 0.5)
        if len(ones):
            out[rng.choice(ones, size=min(-delta, len(ones)), replace=False)] = 0.0
    return out


def markov_density(reference: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    counts = np.ones((2, 2), dtype=float)
    bits = reference.astype(int)
    for a, b in zip(bits[:-1], bits[1:]):
        counts[a, b] += 1.0
    probs = counts / counts.sum(axis=1, keepdims=True)
    out = np.zeros(len(reference), dtype=float)
    out[0] = float(rng.choice([0, 1], p=[1 - np.mean(reference), np.mean(reference)]))
    for i in range(1, len(out)):
        prev = int(out[i - 1])
        out[i] = float(rng.choice([0, 1], p=probs[prev]))

    target_ones = int(np.sum(reference))
    delta = int(target_ones - np.sum(out))
    if delta > 0:
        zeros = np.flatnonzero(out < 0.5)
        if len(zeros):
            out[rng.choice(zeros, size=min(delta, len(zeros)), replace=False)] = 1.0
    elif delta < 0:
        ones = np.flatnonzero(out > 0.5)
        if len(ones):
            out[rng.choice(ones, size=min(-delta, len(ones)), replace=False)] = 0.0
    return out


def candidate_pool(reference: np.ndarray, rng: np.random.Generator, args: argparse.Namespace):
    block_sizes = parse_csv_ints(args.block_sizes)
    periods = parse_csv_ints(args.periods)
    for trial in range(args.random_trials):
        yield "balanced_random", trial, balanced_random(reference, rng)
    for block_size in block_sizes:
        for trial in range(args.mode_trials):
            yield f"block_shuffle_{block_size}", trial, block_shuffle(reference, block_size, rng)
    for period in periods:
        for trial in range(args.mode_trials):
            yield f"periodic_approximant_{period}", trial, periodic_approximant(reference, period, rng)
    for trial in range(args.mode_trials):
        yield "markov_density", trial, markov_density(reference, rng)


def summarize_candidates(rows: list[dict]) -> dict:
    out = {}
    for mode in sorted({row["source_mode"] for row in rows}):
        group = [row for row in rows if row["source_mode"] == mode]
        accepted = [row for row in group if row["accepted"]]
        scores = [row["label_jaccard"] for row in group]
        hamming = [row["hamming_ratio"] for row in group]
        out[mode] = {
            "candidates": len(group),
            "accepted": len(accepted),
            "acceptance_rate": float(len(accepted) / len(group)) if group else None,
            "best_label_jaccard": float(max(scores)) if scores else None,
            "median_label_jaccard": float(np.median(scores)) if scores else None,
            "median_hamming_ratio": float(np.median(hamming)) if hamming else None,
        }
    return out


def summarize_events(rows: list[dict]) -> dict:
    out = {}
    for mode in sorted({row["source_mode"] for row in rows}):
        group = [row for row in rows if row["source_mode"] == mode]
        events = Counter(row["event"] for row in group)
        vc_values = [row["vc_interp"] for row in group if row["vc_interp"] is not None]
        candidate_ids = {
            row.get("candidate_id")
            for row in group
            if row.get("candidate_id")
        }
        out[mode] = {
            "conditions": len(group),
            "candidates": len(candidate_ids) if candidate_ids else None,
            "events": dict(sorted(events.items())),
            "vc_median": float(np.median(vc_values)) if vc_values else None,
            "label_jaccard_median": float(np.median([row["label_jaccard"] for row in group])),
            "hamming_ratio_median": float(np.median([row["hamming_ratio"] for row in group])),
            "r_floor_median": float(np.median([row["r_floor"] for row in group])),
        }
    return out


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    thresholds = parse_csv_floats(args.r_thresholds)
    v_values = np.arange(args.v_min, args.v_max + args.v_step / 2, args.v_step)

    audit_rows = []
    event_rows = []
    accepted_event_rows = []
    for n in ns:
        for phase in phases:
            reference = sturmian_sequence(THETA, n, phase)
            reference_labels = label_set(reference, args)
            per_mode_best: dict[str, dict] = {
                "phi_sturmian": {
                    "candidate_id": make_candidate_id(n, phase, "phi_sturmian", 0),
                    "seq": reference,
                    "label_jaccard": 1.0,
                    "hamming_ratio": 0.0,
                    "accepted": True,
                    "trial": 0,
                }
            }

            for source_mode, trial, seq in candidate_pool(reference, rng, args):
                distance = hamming_ratio(seq, reference)
                if distance < args.min_hamming_ratio:
                    continue
                score = score_sequence(seq, reference_labels, args)
                accepted = score >= args.label_jaccard_min
                cid = make_candidate_id(n, phase, source_mode, trial)
                audit = {
                    "candidate_id": cid,
                    "N": n,
                    "phase": phase,
                    "source_mode": source_mode,
                    "trial": trial,
                    "label_jaccard": score,
                    "hamming_ratio": distance,
                    "accepted": accepted,
                }
                audit_rows.append(audit)
                if accepted:
                    r_values = curve_for_sequence(seq, v_values)
                    for threshold in thresholds:
                        accepted_event_rows.append({
                            **audit,
                            "r_threshold": threshold,
                            "event_source": "accepted_candidate",
                            **crossing_event(v_values, r_values, threshold),
                        })

                current = per_mode_best.get(source_mode)
                key = (score, distance)
                old_key = (-1.0, -1.0) if current is None else (
                    current["label_jaccard"],
                    current["hamming_ratio"],
                )
                if key > old_key:
                    per_mode_best[source_mode] = {**audit, "seq": seq}

            for source_mode, best in per_mode_best.items():
                if source_mode != "phi_sturmian" and not best["accepted"] and not args.include_rejected_best:
                    continue
                r_values = curve_for_sequence(best["seq"], v_values)
                for threshold in thresholds:
                    event_rows.append({
                        "N": n,
                        "phase": phase,
                        "source_mode": source_mode,
                        "trial": best["trial"],
                        "candidate_id": best["candidate_id"],
                        "r_threshold": threshold,
                        "label_jaccard": best["label_jaccard"],
                        "hamming_ratio": best["hamming_ratio"],
                        "accepted": best["accepted"],
                        "event_source": "per_mode_best",
                        **crossing_event(v_values, r_values, threshold),
                    })

    accepted_nonsturmian = [
        row for row in audit_rows
        if row["accepted"] and row["source_mode"] not in STURMIAN_SOURCE_MODES
    ]
    return {
        "experiment": "vc_nonsturmian_label_null_gate",
        "parameters": vars(args),
        "accepted_nonsturmian_count": len(accepted_nonsturmian),
        "candidate_summary": summarize_candidates(audit_rows),
        "event_summary": summarize_events(event_rows),
        "accepted_event_summary": summarize_events(accepted_event_rows),
        "audit_rows": audit_rows,
        "event_rows": event_rows,
        "accepted_event_rows": accepted_event_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="144")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--r-thresholds", default="0.48,0.50,0.52")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=3.0)
    parser.add_argument("--v-step", type=float, default=0.01)
    parser.add_argument("--random-trials", type=int, default=64)
    parser.add_argument("--mode-trials", type=int, default=48)
    parser.add_argument("--block-sizes", default="2,3,5,8,13,21,34")
    parser.add_argument("--periods", default="13,21,34,55,89")
    parser.add_argument("--min-hamming-ratio", type=float, default=0.03)
    parser.add_argument("--label-jaccard-min", type=float, default=0.75)
    parser.add_argument("--label-threshold", type=float, default=2.0)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=202605090819)
    parser.add_argument("--include-rejected-best", action="store_true")
    parser.add_argument("--out", default="tools/data/vc_nonsturmian_label_null_gate_20260509_0819.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        "accepted_nonsturmian_count": output["accepted_nonsturmian_count"],
        "candidate_summary": output["candidate_summary"],
        "event_summary": output["event_summary"],
        "accepted_event_summary": output["accepted_event_summary"],
        "out": str(out),
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
