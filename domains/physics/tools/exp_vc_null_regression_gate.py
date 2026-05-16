#!/usr/bin/env python3
"""
Regression gate for the quasiperiodic V_c null.

The previous V_c curve map separated metallic curve shape from balanced random,
but the random null mixed two events: curves already below threshold at V_min
and curves with an internal crossing. This tool separates those events and adds
a stricter surrogate: random words are accepted only when their spectral
gap-label set overlaps the matched Sturmian reference.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.linalg import eigvalsh_tridiagonal

from exp_gap_label_set_stability import PHI, gap_labels, jaccard, sturmian_sequence


THETA = 1 / PHI


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def r_statistic_from_diag(diagonal: np.ndarray) -> float:
    offdiag = np.ones(len(diagonal) - 1, dtype=float)
    eigs = eigvalsh_tridiagonal(diagonal, offdiag, check_finite=False)
    spacings = np.diff(eigs)
    spacings = spacings[spacings > 1e-12]
    if len(spacings) < 2:
        return 0.5
    left = spacings[:-1]
    right = spacings[1:]
    return float(np.mean(np.minimum(left, right) / np.maximum(left, right)))


def curve_for_sequence(seq: np.ndarray, v_values: np.ndarray) -> np.ndarray:
    return np.array([r_statistic_from_diag(v * seq) for v in v_values], dtype=float)


def crossing_event(v_values: np.ndarray, r_values: np.ndarray, threshold: float) -> dict:
    below = r_values < threshold
    crossing_count = int(np.sum(below[1:] != below[:-1]))
    r_floor = float(r_values[0])
    r_end = float(r_values[-1])

    if bool(below[0]):
        event = "floor_hit"
        vc_interp = float(v_values[0])
        slope = None
    elif not np.any(below):
        event = "no_cross"
        vc_interp = None
        slope = None
    else:
        event = "internal_cross"
        idx = int(np.argmax(below))
        v0, v1 = float(v_values[idx - 1]), float(v_values[idx])
        r0, r1 = float(r_values[idx - 1]), float(r_values[idx])
        if abs(r1 - r0) < 1e-15:
            vc_interp = v1
            slope = 0.0
        else:
            vc_interp = v0 + (threshold - r0) * (v1 - v0) / (r1 - r0)
            slope = (r1 - r0) / (v1 - v0)

    if crossing_count > 1 and event == "internal_cross":
        event = "internal_multi"

    return {
        "event": event,
        "crossing_count": crossing_count,
        "vc_interp": None if vc_interp is None else float(vc_interp),
        "slope_at_cross": None if slope is None else float(slope),
        "r_floor": r_floor,
        "r_end": r_end,
        "r_span": float(np.max(r_values) - np.min(r_values)),
    }


def balanced_random(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.array(seq, dtype=float)
    rng.shuffle(out)
    return out


def label_set(seq: np.ndarray, args: argparse.Namespace) -> set[int]:
    obs = gap_labels(seq, THETA, args.label_threshold, args.max_label, args.top_k)
    return set(obs["label_set"])


def label_preserving_surrogate(
    reference_seq: np.ndarray,
    reference_labels: set[int],
    rng: np.random.Generator,
    args: argparse.Namespace,
) -> tuple[np.ndarray, float, int]:
    best_seq = None
    best_score = -1.0
    best_size = 0
    for _ in range(args.label_candidates):
        candidate = balanced_random(reference_seq, rng)
        candidate_labels = label_set(candidate, args)
        score = jaccard(candidate_labels, reference_labels)
        if score > best_score:
            best_score = score
            best_seq = candidate
            best_size = len(candidate_labels)
        if score >= args.label_jaccard_min:
            return candidate, float(score), len(candidate_labels)
    assert best_seq is not None
    return best_seq, float(best_score), best_size


def summarize_rows(rows: list[dict]) -> dict:
    out = {}
    for generator in sorted({row["generator"] for row in rows}):
        group = [row for row in rows if row["generator"] == generator]
        events = Counter(row["event"] for row in group)
        internal = events["internal_cross"] + events["internal_multi"]
        vc_values = [row["vc_interp"] for row in group if row["vc_interp"] is not None]
        slopes = [abs(row["slope_at_cross"]) for row in group if row["slope_at_cross"] is not None]
        label_scores = [row["label_jaccard"] for row in group if row.get("label_jaccard") is not None]
        out[generator] = {
            "conditions": len(group),
            "events": dict(sorted(events.items())),
            "internal_rate": float(internal / len(group)) if group else None,
            "floor_hit_rate": float(events["floor_hit"] / len(group)) if group else None,
            "no_cross_rate": float(events["no_cross"] / len(group)) if group else None,
            "vc_median": float(np.median(vc_values)) if vc_values else None,
            "vc_q25": float(np.quantile(vc_values, 0.25)) if vc_values else None,
            "vc_q75": float(np.quantile(vc_values, 0.75)) if vc_values else None,
            "slope_median": float(np.median(slopes)) if slopes else None,
            "r_floor_median": float(np.median([row["r_floor"] for row in group])),
            "r_span_median": float(np.median([row["r_span"] for row in group])),
            "label_jaccard_median": float(np.median(label_scores)) if label_scores else None,
            "label_jaccard_min": float(np.min(label_scores)) if label_scores else None,
        }
    return out


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    thresholds = parse_csv_floats(args.r_thresholds)
    v_values = np.arange(args.v_min, args.v_max + args.v_step / 2, args.v_step)

    rows = []
    for n in ns:
        for phase in phases:
            reference = sturmian_sequence(THETA, n, phase)
            reference_labels = label_set(reference, args)
            seqs = [("phi_sturmian", 0, reference, 1.0, len(reference_labels))]

            for trial in range(args.phase_trials):
                phase_prime = float(rng.random())
                seqs.append((
                    "sturmian_phase_shuffle",
                    trial,
                    sturmian_sequence(THETA, n, phase_prime),
                    None,
                    None,
                ))

            for trial in range(args.random_trials):
                seqs.append(("balanced_random", trial, balanced_random(reference, rng), None, None))

            for trial in range(args.label_trials):
                surrogate, score, size = label_preserving_surrogate(reference, reference_labels, rng, args)
                seqs.append(("label_preserving_surrogate", trial, surrogate, score, size))

            for generator, trial, seq, label_score, label_count in seqs:
                for threshold in thresholds:
                    r_values = curve_for_sequence(seq, v_values)
                    rows.append({
                        "generator": generator,
                        "trial": trial,
                        "N": n,
                        "phase": phase,
                        "r_threshold": threshold,
                        "ones": int(np.sum(seq)),
                        "label_jaccard": label_score,
                        "label_count": label_count,
                        **crossing_event(v_values, r_values, threshold),
                    })

    by_threshold = defaultdict(list)
    for row in rows:
        by_threshold[(row["generator"], row["r_threshold"])].append(row)

    return {
        "experiment": "vc_null_regression_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "r_thresholds": thresholds,
            "v_min": args.v_min,
            "v_max": args.v_max,
            "v_step": args.v_step,
            "phase_trials": args.phase_trials,
            "random_trials": args.random_trials,
            "label_trials": args.label_trials,
            "label_candidates": args.label_candidates,
            "label_jaccard_min": args.label_jaccard_min,
            "label_threshold": args.label_threshold,
            "top_k": args.top_k,
            "max_label": args.max_label,
            "seed": args.seed,
        },
        "summary": summarize_rows(rows),
        "summary_by_threshold": {
            f"{generator}|r_threshold={threshold}": summarize_rows(group).get(generator, {})
            for (generator, threshold), group in sorted(by_threshold.items())
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="89,144,233,377")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--r-thresholds", default="0.48,0.50,0.52")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=3.0)
    parser.add_argument("--v-step", type=float, default=0.01)
    parser.add_argument("--phase-trials", type=int, default=3)
    parser.add_argument("--random-trials", type=int, default=3)
    parser.add_argument("--label-trials", type=int, default=3)
    parser.add_argument("--label-candidates", type=int, default=12)
    parser.add_argument("--label-jaccard-min", type=float, default=0.75)
    parser.add_argument("--label-threshold", type=float, default=2.0)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=202605090637)
    parser.add_argument("--out", default="tools/data/vc_null_regression_gate_20260509_0637.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        generator: {
            "conditions": data["conditions"],
            "events": data["events"],
            "internal_rate": data["internal_rate"],
            "floor_hit_rate": data["floor_hit_rate"],
            "vc_median": data["vc_median"],
            "r_floor_median": data["r_floor_median"],
            "label_jaccard_median": data["label_jaccard_median"],
        }
        for generator, data in output["summary"].items()
    }
    print(json.dumps({"summary": compact, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
