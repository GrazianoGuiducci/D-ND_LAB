#!/usr/bin/env python3
"""
Gap-label set stability for quasiperiodic spectra.

The previous denominator audit showed that the first-two gap ratio moves with
N, Sturmian phase, and threshold. This tool moves the observable from the value
of the first two large gaps to the labels of the large gaps.

For each large spectral gap, the integrated density of states is approximated
by (gap_index + 1) / N. The nearest gap label is the integer n whose fractional
part {n * theta} is closest to that IDS, modulo 1. The label set is then tested
for stability across phase, N, and threshold.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from numpy.linalg import eigvalsh


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)


def sturmian_sequence(theta: float, n: int, phase: float = 0.0) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(float)


def hamiltonian(seq: np.ndarray, v: float = 1.0) -> np.ndarray:
    n = len(seq)
    h = np.zeros((n, n), dtype=float)
    h[np.arange(n), np.arange(n)] = v * seq
    off = np.arange(n - 1)
    h[off, off + 1] = 1.0
    h[off + 1, off] = 1.0
    return h


def circular_distance(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def nearest_label(ids_value: float, theta: float, max_label: int) -> tuple[int, float, float]:
    candidates = []
    for n in range(-max_label, max_label + 1):
        if n == 0:
            continue
        frac = (n * theta) % 1.0
        candidates.append((n, circular_distance(ids_value, frac), frac))
    best_n, best_dist, best_frac = min(candidates, key=lambda item: (item[1], abs(item[0])))
    return int(best_n), float(best_dist), float(best_frac)


def gap_labels(seq: np.ndarray, theta: float, threshold: float, max_label: int, top_k: int) -> dict:
    eigs = np.sort(eigvalsh(hamiltonian(seq)))
    spacings = np.diff(eigs)
    mean_spacing = float(np.mean(spacings))
    large = []
    for index, spacing in enumerate(spacings):
        if spacing > threshold * mean_spacing:
            ids_value = (index + 1) / len(seq)
            label, error, label_value = nearest_label(ids_value, theta, max_label)
            large.append({
                "index": int(index),
                "spacing": float(spacing),
                "ids": float(ids_value),
                "label": label,
                "label_error": error,
                "label_value": label_value,
            })

    by_size = sorted(large, key=lambda item: item["spacing"], reverse=True)
    selected = by_size[:top_k]
    label_set = sorted({item["label"] for item in selected}, key=lambda x: (abs(x), x))
    errors = [item["label_error"] for item in selected]
    return {
        "n_large": len(large),
        "n_selected": len(selected),
        "label_set": label_set,
        "median_label_error": float(np.median(errors)) if errors else None,
        "max_label_error": float(np.max(errors)) if errors else None,
        "selected": selected,
    }


def jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def summarize_sets(rows: list[dict]) -> dict:
    sets = [set(row["label_set"]) for row in rows if row["n_selected"] > 0]
    if not sets:
        return {}
    pairwise = [jaccard(a, b) for a, b in itertools.combinations(sets, 2)]
    counter = Counter(label for s in sets for label in s)
    n_sets = len(sets)
    core = sorted(
        [label for label, count in counter.items() if count == n_sets],
        key=lambda x: (abs(x), x),
    )
    stable_75 = sorted(
        [label for label, count in counter.items() if count / n_sets >= 0.75],
        key=lambda x: (abs(x), x),
    )
    return {
        "conditions": n_sets,
        "median_jaccard": float(np.median(pairwise)) if pairwise else 1.0,
        "min_jaccard": float(np.min(pairwise)) if pairwise else 1.0,
        "core_labels_all_conditions": core,
        "stable_labels_75pct": stable_75,
        "label_frequency_top": [
            {"label": int(label), "count": int(count)}
            for label, count in sorted(counter.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))[:12]
        ],
        "median_label_error": float(np.median([row["median_label_error"] for row in rows if row["median_label_error"] is not None])),
        "median_selected": float(np.median([row["n_selected"] for row in rows])),
        "median_n_large": float(np.median([row["n_large"] for row in rows])),
    }


def grouped_stability(rows: list[dict], keys: tuple[str, ...]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        group_key = "|".join(f"{key}={row[key]}" for key in keys)
        groups[group_key].append(row)
    summaries = [summarize_sets(group_rows) for group_rows in groups.values() if len(group_rows) > 1]
    summaries = [s for s in summaries if s]
    if not summaries:
        return {}
    return {
        "groups": len(summaries),
        "median_jaccard": float(np.median([s["median_jaccard"] for s in summaries])),
        "min_jaccard": float(np.min([s["min_jaccard"] for s in summaries])),
    }


def run(args: argparse.Namespace) -> dict:
    rng = np.random.default_rng(args.seed)
    domains = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }
    ns = [int(x) for x in args.ns.split(",")]
    phases = [float(x) for x in args.phases.split(",")]
    thresholds = [float(x) for x in args.thresholds.split(",")]

    rows = []
    for n in ns:
        for phase in phases:
            phi_ones = int(np.sum(sturmian_sequence(1 / PHI, n, phase)))
            for threshold in thresholds:
                for name, theta in domains.items():
                    seq = sturmian_sequence(theta, n, phase)
                    obs = gap_labels(seq, theta, threshold, args.max_label, args.top_k)
                    rows.append({"domain": name, "N": n, "phase": phase, "threshold": threshold, **obs})

                for trial in range(args.random_trials):
                    seq = np.array([1.0] * phi_ones + [0.0] * (n - phi_ones))
                    rng.shuffle(seq)
                    obs = gap_labels(seq, 1 / PHI, threshold, args.max_label, args.top_k)
                    rows.append({
                        "domain": "balanced_random_phi_labels",
                        "trial": trial,
                        "N": n,
                        "phase": phase,
                        "threshold": threshold,
                        **obs,
                    })

    by_domain = {}
    for domain in sorted({row["domain"] for row in rows}):
        domain_rows = [row for row in rows if row["domain"] == domain]
        by_domain[domain] = {
            "global": summarize_sets(domain_rows),
            "phase_stability_by_N_threshold": grouped_stability(domain_rows, ("N", "threshold")),
            "threshold_stability_by_N_phase": grouped_stability(domain_rows, ("N", "phase")),
            "scale_stability_by_phase_threshold": grouped_stability(domain_rows, ("phase", "threshold")),
        }

    output = {
        "experiment": "gap_label_set_stability",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "thresholds": thresholds,
            "random_trials": args.random_trials,
            "top_k": args.top_k,
            "max_label": args.max_label,
            "seed": args.seed,
        },
        "summary": by_domain,
        "rows": rows,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="233,377,500,610")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--thresholds", default="1.75,2.0,2.25")
    parser.add_argument("--random-trials", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-label", type=int, default=34)
    parser.add_argument("--seed", type=int, default=20260508)
    parser.add_argument("--out", default="tools/data/gap_label_set_stability_20260508_1632.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        domain: {
            "median_jaccard": data["global"].get("median_jaccard"),
            "stable_labels_75pct": data["global"].get("stable_labels_75pct"),
            "phase_stability": data["phase_stability_by_N_threshold"].get("median_jaccard"),
            "threshold_stability": data["threshold_stability_by_N_phase"].get("median_jaccard"),
            "scale_stability": data["scale_stability_by_phase_threshold"].get("median_jaccard"),
        }
        for domain, data in output["summary"].items()
    }
    print(json.dumps({"summary": compact, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
