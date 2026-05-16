#!/usr/bin/env python3
"""
Swap-constrained label-preserving null for the quasiperiodic V_c gate.

The 2026-05-09 06:37 regression gate showed that choosing the best of a few
balanced random words does not preserve the spectral gap-label set. The 06:59
repair showed that blind swaps still struggle at N=144. This tool repairs that
node by adding structured Fibonacci-like starts, then still reports the
Hamming distance from the matched Sturmian reference so a near-copy cannot
silently become a fake counterproof. Phase-shift Sturmian candidates are an
explicit bridge mode: they test reachability inside the Sturmian family, not
independent nullhood.
"""

from __future__ import annotations

import argparse
import json
import math
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
        "r_end": float(r_values[-1]),
        "r_span": float(np.max(r_values) - np.min(r_values)),
    }


def balanced_random(reference_seq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = np.array(reference_seq, dtype=float)
    rng.shuffle(out)
    return out


def hamming_ratio(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.asarray(a) != np.asarray(b)))


def fibonacci_lengths(order: int) -> tuple[int, int]:
    if order < 2:
        raise ValueError("supertile_order must be >= 2")
    a, b = 1, 1
    for _ in range(2, order + 1):
        a, b = b, a + b
    return b, a


def fibonacci_type_word(n_types: int) -> np.ndarray:
    word = "1"
    previous = "0"
    while len(word) < n_types:
        word, previous = word + previous, word
    return np.array([int(ch) for ch in word[:n_types]], dtype=int)


def supertile_lengths(n: int, order: int) -> list[int]:
    long_len, short_len = fibonacci_lengths(order)
    if short_len >= n:
        return []
    types = fibonacci_type_word(max(8, int(np.ceil(n / short_len)) + 4))
    lengths: list[int] = []
    total = 0
    for t in types:
        length = long_len if t == 1 else short_len
        if total + length >= n:
            lengths.append(n - total)
            break
        lengths.append(length)
        total += length
    return [length for length in lengths if length > 0]


def chunks_from_lengths(seq: np.ndarray, lengths: list[int]) -> list[np.ndarray]:
    chunks = []
    start = 0
    for length in lengths:
        chunks.append(seq[start : start + length].copy())
        start += length
    if start < len(seq):
        chunks.append(seq[start:].copy())
    return chunks


def shuffle_chunks(chunks: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    shuffled = list(chunks)
    rng.shuffle(shuffled)
    return np.concatenate(shuffled)


def misaligned_same_lengths(seq: np.ndarray, lengths: list[int], rng: np.random.Generator) -> np.ndarray:
    if len(seq) < 2:
        return seq.copy()
    offset = int(rng.integers(1, len(seq)))
    rotated = np.roll(seq, -offset)
    chunks = chunks_from_lengths(rotated, lengths)
    shuffled = shuffle_chunks(chunks, rng)
    return np.roll(shuffled, offset)


def structured_start_candidates(
    reference_seq: np.ndarray,
    rng: np.random.Generator,
    args: argparse.Namespace,
) -> list[tuple[str, np.ndarray]]:
    orders = parse_csv_ints(args.supertile_orders)
    candidates: list[tuple[str, np.ndarray]] = []
    for order in orders:
        lengths = supertile_lengths(len(reference_seq), order)
        if len(lengths) < 3:
            continue
        chunks = chunks_from_lengths(reference_seq, lengths)
        for _ in range(args.structured_trials):
            variants = {
                f"supertile_shuffle_order_{order}": shuffle_chunks(chunks, rng),
                f"misaligned_same_lengths_order_{order}": misaligned_same_lengths(reference_seq, lengths, rng),
            }
            for mode, seq in variants.items():
                if hamming_ratio(seq, reference_seq) >= args.min_hamming_ratio:
                    candidates.append((mode, seq))
    return candidates


def phase_shift_candidates(
    reference_seq: np.ndarray,
    rng: np.random.Generator,
    args: argparse.Namespace,
) -> list[tuple[str, np.ndarray]]:
    candidates: list[tuple[str, np.ndarray]] = []
    for _ in range(args.phase_candidate_trials):
        phase = float(rng.random())
        seq = sturmian_sequence(THETA, len(reference_seq), phase)
        if hamming_ratio(seq, reference_seq) >= args.min_hamming_ratio:
            candidates.append(("phase_shift_sturmian", seq))
    return candidates


def label_set(seq: np.ndarray, args: argparse.Namespace) -> set[int]:
    obs = gap_labels(seq, THETA, args.label_threshold, args.max_label, args.top_k)
    return set(obs["label_set"])


def score_sequence(seq: np.ndarray, reference_labels: set[int], args: argparse.Namespace) -> tuple[float, set[int]]:
    labels = label_set(seq, args)
    return float(jaccard(labels, reference_labels)), labels


def swapped(seq: np.ndarray, rng: np.random.Generator) -> np.ndarray | None:
    ones = np.flatnonzero(seq > 0.5)
    zeros = np.flatnonzero(seq < 0.5)
    if len(ones) == 0 or len(zeros) == 0:
        return None
    out = np.array(seq, copy=True)
    i = int(rng.choice(ones))
    j = int(rng.choice(zeros))
    out[i], out[j] = out[j], out[i]
    return out


def annealed_label_surrogate(
    reference_seq: np.ndarray,
    reference_labels: set[int],
    rng: np.random.Generator,
    args: argparse.Namespace,
) -> dict:
    initial_pool: list[tuple[str, np.ndarray]] = [("balanced_random", balanced_random(reference_seq, rng))]
    if not args.disable_structured_starts:
        initial_pool.extend(structured_start_candidates(reference_seq, rng, args))
    initial_pool.extend(phase_shift_candidates(reference_seq, rng, args))

    best_result = None

    for source_mode, initial in initial_pool:
        current = np.array(initial, copy=True)
        current_score, current_labels = score_sequence(current, reference_labels, args)
        best = np.array(current, copy=True)
        best_score = current_score
        best_labels = set(current_labels)
        accepted_steps = 0
        steps_used = 0

        for step in range(args.swap_steps):
            if best_score >= args.label_jaccard_min:
                break
            candidate = swapped(current, rng)
            if candidate is None:
                break
            candidate_hamming = hamming_ratio(candidate, reference_seq)
            if candidate_hamming < args.min_hamming_ratio:
                continue
            candidate_score, candidate_labels = score_sequence(candidate, reference_labels, args)
            delta = candidate_score - current_score
            temp = max(args.temp_end, args.temp_start * ((args.swap_steps - step) / args.swap_steps))
            accept = delta >= 0 or rng.random() < math.exp(delta / max(temp, 1e-9))
            if accept:
                current = candidate
                current_score = candidate_score
                current_labels = candidate_labels
                accepted_steps += 1
            if candidate_score > best_score:
                best = np.array(candidate, copy=True)
                best_score = candidate_score
                best_labels = set(candidate_labels)
            steps_used = step + 1

        candidate_result = {
            "seq": best,
            "source_mode": source_mode,
            "label_jaccard": float(best_score),
            "label_count": len(best_labels),
            "hamming_ratio": hamming_ratio(best, reference_seq),
            "accepted": bool(best_score >= args.label_jaccard_min),
            "steps_used": int(steps_used),
            "accepted_steps": int(accepted_steps),
        }
        key = (
            candidate_result["accepted"],
            candidate_result["label_jaccard"],
            candidate_result["hamming_ratio"],
            -candidate_result["steps_used"],
        )
        if best_result is None or key > best_result[0]:
            best_result = (key, candidate_result)

    if best_result is None:
        raise RuntimeError("no surrogate candidate generated")
    return best_result[1]


def summarize_rows(rows: list[dict]) -> dict:
    out = {}
    for generator in sorted({row["generator"] for row in rows}):
        group = [row for row in rows if row["generator"] == generator]
        events = Counter(row["event"] for row in group)
        internal = events["internal_cross"] + events["internal_multi"]
        vc_values = [row["vc_interp"] for row in group if row["vc_interp"] is not None]
        label_scores = [row["label_jaccard"] for row in group if row.get("label_jaccard") is not None]
        accepted = [row["accepted"] for row in group if row.get("accepted") is not None]
        hamming_values = [row["hamming_ratio"] for row in group if row.get("hamming_ratio") is not None]
        out[generator] = {
            "conditions": len(group),
            "events": dict(sorted(events.items())),
            "internal_rate": float(internal / len(group)) if group else None,
            "floor_hit_rate": float(events["floor_hit"] / len(group)) if group else None,
            "vc_median": float(np.median(vc_values)) if vc_values else None,
            "vc_q25": float(np.quantile(vc_values, 0.25)) if vc_values else None,
            "vc_q75": float(np.quantile(vc_values, 0.75)) if vc_values else None,
            "r_floor_median": float(np.median([row["r_floor"] for row in group])),
            "r_span_median": float(np.median([row["r_span"] for row in group])),
            "label_jaccard_median": float(np.median(label_scores)) if label_scores else None,
            "label_jaccard_min": float(np.min(label_scores)) if label_scores else None,
            "acceptance_rate": float(sum(accepted) / len(accepted)) if accepted else None,
            "hamming_ratio_median": float(np.median(hamming_values)) if hamming_values else None,
            "hamming_ratio_min": float(np.min(hamming_values)) if hamming_values else None,
        }
    return out


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    ns = parse_csv_ints(args.ns)
    phases = parse_csv_floats(args.phases)
    thresholds = parse_csv_floats(args.r_thresholds)
    v_values = np.arange(args.v_min, args.v_max + args.v_step / 2, args.v_step)

    rows = []
    surrogate_audit = []
    for n in ns:
        for phase in phases:
            reference = sturmian_sequence(THETA, n, phase)
            reference_labels = label_set(reference, args)
            generators = [("phi_sturmian", 0, reference, 1.0, len(reference_labels), True, 0, 0, None, 0.0)]

            for trial in range(args.random_trials):
                random_seq = balanced_random(reference, rng)
                generators.append((
                    "balanced_random",
                    trial,
                    random_seq,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "balanced_random",
                    hamming_ratio(random_seq, reference),
                ))

            for trial in range(args.label_trials):
                result = annealed_label_surrogate(reference, reference_labels, rng, args)
                generators.append((
                    "swap_label_surrogate",
                    trial,
                    result["seq"],
                    result["label_jaccard"],
                    result["label_count"],
                    result["accepted"],
                    result["steps_used"],
                    result["accepted_steps"],
                    result["source_mode"],
                    result["hamming_ratio"],
                ))
                surrogate_audit.append({
                    "N": n,
                    "phase": phase,
                    "trial": trial,
                    "source_mode": result["source_mode"],
                    "label_jaccard": result["label_jaccard"],
                    "hamming_ratio": result["hamming_ratio"],
                    "accepted": result["accepted"],
                    "steps_used": result["steps_used"],
                    "accepted_steps": result["accepted_steps"],
                })

            for generator, trial, seq, label_score, label_count, accepted, steps_used, accepted_steps, source_mode, hamming in generators:
                r_values = curve_for_sequence(seq, v_values)
                for threshold in thresholds:
                    rows.append({
                        "generator": generator,
                        "trial": trial,
                        "N": n,
                        "phase": phase,
                        "r_threshold": threshold,
                        "ones": int(np.sum(seq)),
                        "label_jaccard": label_score,
                        "label_count": label_count,
                        "accepted": accepted,
                        "steps_used": steps_used,
                        "accepted_steps": accepted_steps,
                        "source_mode": source_mode,
                        "hamming_ratio": hamming,
                        **crossing_event(v_values, r_values, threshold),
                    })

    by_threshold = defaultdict(list)
    for row in rows:
        by_threshold[(row["generator"], row["r_threshold"])].append(row)

    return {
        "experiment": "vc_label_preserving_swap_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "r_thresholds": thresholds,
            "v_min": args.v_min,
            "v_max": args.v_max,
            "v_step": args.v_step,
            "random_trials": args.random_trials,
            "label_trials": args.label_trials,
            "swap_steps": args.swap_steps,
            "structured_trials": args.structured_trials,
            "phase_candidate_trials": args.phase_candidate_trials,
            "supertile_orders": args.supertile_orders,
            "min_hamming_ratio": args.min_hamming_ratio,
            "disable_structured_starts": args.disable_structured_starts,
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
        "surrogate_audit": surrogate_audit,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="89,144")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--r-thresholds", default="0.48,0.50,0.52")
    parser.add_argument("--v-min", type=float, default=0.5)
    parser.add_argument("--v-max", type=float, default=3.0)
    parser.add_argument("--v-step", type=float, default=0.01)
    parser.add_argument("--random-trials", type=int, default=2)
    parser.add_argument("--label-trials", type=int, default=2)
    parser.add_argument("--swap-steps", type=int, default=120)
    parser.add_argument("--structured-trials", type=int, default=24)
    parser.add_argument("--phase-candidate-trials", type=int, default=0)
    parser.add_argument("--supertile-orders", default="6,7,8")
    parser.add_argument("--min-hamming-ratio", type=float, default=0.03)
    parser.add_argument("--disable-structured-starts", action="store_true")
    parser.add_argument("--temp-start", type=float, default=0.05)
    parser.add_argument("--temp-end", type=float, default=0.002)
    parser.add_argument("--label-jaccard-min", type=float, default=0.75)
    parser.add_argument("--label-threshold", type=float, default=2.0)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=202605090652)
    parser.add_argument("--out", default="tools/data/vc_label_preserving_swap_gate_20260509_0652.json")
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
            "acceptance_rate": data["acceptance_rate"],
            "hamming_ratio_median": data["hamming_ratio_median"],
        }
        for generator, data in output["summary"].items()
    }
    print(json.dumps({"summary": compact, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
