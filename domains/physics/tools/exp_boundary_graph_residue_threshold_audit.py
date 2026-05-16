#!/usr/bin/env python3
"""
Threshold audit for graph-only BOUNDARY residues.

Input is the graph-null audit JSON. This pass does not rerun the graph reader;
it repairs the statistical contract by exposing raw counts, binomial intervals,
and an ex-ante threshold before any graph-only row is called residue.
"""

from __future__ import annotations

import argparse
import json
from math import comb, sqrt
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    phat = successes / total
    denom = 1.0 + z * z / total
    center = (phat + z * z / (2.0 * total)) / denom
    margin = z * sqrt((phat * (1.0 - phat) + z * z / (4.0 * total)) / total) / denom
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def binomial_tail_at_least(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0 if k <= 0 else 0.0
    if p >= 1.0:
        return 1.0 if k <= n else 0.0
    return sum(comb(n, i) * (p**i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1))


def count_from_frequency(freq: float, total: int) -> int:
    return int(round(freq * total))


def row_audit(
    row: dict[str, Any],
    graph_reader_runs: int,
    label_null_trials: int,
    rewire_null_trials: int,
    min_lift: float,
    alpha: float,
) -> dict[str, Any]:
    observed = count_from_frequency(float(row["observed_graph_bridge_frequency"]), graph_reader_runs)
    label_null = count_from_frequency(float(row["label_shuffle_bridge_frequency"]), label_null_trials)
    rewire_null = count_from_frequency(float(row["degree_rewire_bridge_frequency"]), rewire_null_trials)

    obs_rate = observed / graph_reader_runs if graph_reader_runs else 0.0
    label_rate = label_null / label_null_trials if label_null_trials else 0.0
    rewire_rate = rewire_null / rewire_null_trials if rewire_null_trials else 0.0
    label_lift = obs_rate - label_rate
    rewire_lift = obs_rate - rewire_rate
    min_actual_lift = min(label_lift, rewire_lift)

    label_p = binomial_tail_at_least(observed, graph_reader_runs, label_rate)
    rewire_p = binomial_tail_at_least(observed, graph_reader_runs, rewire_rate)

    positive_lift_unthresholded = (
        row.get("classical_audit_state") == "graph_only_bridge"
        and label_lift > 0.0
        and rewire_lift > 0.0
    )
    threshold_pass = (
        positive_lift_unthresholded
        and observed == graph_reader_runs
        and min_actual_lift >= min_lift
        and label_p <= alpha
        and rewire_p <= alpha
    )

    return {
        "domain_window": row["domain_window"],
        "domain": row["domain"],
        "source_domain_type": row["source_domain_type"],
        "classical_audit_state": row["classical_audit_state"],
        "observed_successes": observed,
        "observed_total": graph_reader_runs,
        "observed_rate": round(obs_rate, 6),
        "observed_wilson_95": wilson_interval(observed, graph_reader_runs),
        "label_null_successes": label_null,
        "label_null_total": label_null_trials,
        "label_null_rate": round(label_rate, 6),
        "label_null_wilson_95": wilson_interval(label_null, label_null_trials),
        "label_lift": round(label_lift, 6),
        "label_binomial_tail_p": round(label_p, 6),
        "rewire_null_successes": rewire_null,
        "rewire_null_total": rewire_null_trials,
        "rewire_null_rate": round(rewire_rate, 6),
        "rewire_null_wilson_95": wilson_interval(rewire_null, rewire_null_trials),
        "rewire_lift": round(rewire_lift, 6),
        "rewire_binomial_tail_p": round(rewire_p, 6),
        "min_lift_against_nulls": round(min_actual_lift, 6),
        "positive_lift_unthresholded": positive_lift_unthresholded,
        "threshold_pass": threshold_pass,
        "threshold_failure_reasons": [
            reason
            for reason, failed in [
                ("not_graph_only_bridge", row.get("classical_audit_state") != "graph_only_bridge"),
                ("not_all_observed_runs", observed != graph_reader_runs),
                ("min_lift_below_threshold", min_actual_lift < min_lift),
                ("label_p_above_alpha", label_p > alpha),
                ("rewire_p_above_alpha", rewire_p > alpha),
                ("non_positive_lift", not positive_lift_unthresholded),
            ]
            if failed
        ],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    data = load_json(Path(args.input))
    params = data.get("params", {})
    graph_reader_runs = int(params["graph_reader_runs"])
    label_null_trials = int(params["label_null_trials"])
    rewire_null_trials = int(params["rewire_null_trials"])

    rows = [
        row_audit(
            row,
            graph_reader_runs,
            label_null_trials,
            rewire_null_trials,
            args.min_lift,
            args.alpha,
        )
        for row in data.get("rows", [])
    ]
    graph_only_rows = [row for row in rows if row["classical_audit_state"] == "graph_only_bridge"]
    positive_rows = [row for row in rows if row["positive_lift_unthresholded"]]
    threshold_rows = [row for row in rows if row["threshold_pass"]]

    output = {
        "experiment": "boundary_graph_residue_threshold_audit",
        "source_experiment": args.input,
        "observables_used": [
            "observed_successes",
            "label_null_successes",
            "rewire_null_successes",
            "observed_wilson_95",
            "label_null_wilson_95",
            "rewire_null_wilson_95",
            "label_binomial_tail_p",
            "rewire_binomial_tail_p",
            "min_lift_against_nulls",
            "positive_lift_unthresholded",
            "threshold_pass",
        ],
        "threshold_preregistered": {
            "min_observed_successes": f"{graph_reader_runs}/{graph_reader_runs}",
            "min_lift_against_each_null": args.min_lift,
            "alpha_each_null": args.alpha,
            "decision": "graph_specific_residue_after_nulls only if all threshold clauses pass; otherwise positive_lift_unthresholded at most",
        },
        "observable_contract": {
            "claim": "graph-only rows become thresholded residues only with raw-count separation from both graph nulls",
            "observable": "raw graph bridge successes and null successes with Wilson intervals and binomial-tail p-values",
            "operator": "post-audit of row-aligned graph-null output; no graph-reader rerun",
            "generator": data.get("observable_contract", {}).get("generator", ""),
            "denominator": f"13 rows; observed denominator {graph_reader_runs}, label-null denominator {label_null_trials}, rewire-null denominator {rewire_null_trials}",
            "non_possible": "residue claim if either null p-value exceeds alpha or min lift is below the preregistered threshold",
            "not_tested": "new graph geometry, new physical systems, asymptotic universality",
        },
        "summary": {
            "rows_analyzed": len(rows),
            "graph_only_rows": [row["domain_window"] for row in graph_only_rows],
            "positive_lift_unthresholded_rows": [row["domain_window"] for row in positive_rows],
            "thresholded_graph_specific_residue_rows": [row["domain_window"] for row in threshold_rows],
            "thresholded_graph_specific_residue_count": len(threshold_rows),
            "two_reader_boundary_confirmed": data.get("summary", {}).get("two_reader_boundary_confirmed"),
            "two_reader_boundary_rows": data.get("summary", {}).get("two_reader_boundary_rows"),
        },
        "rows": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tools/data/boundary_graph_null_audit_20260516_0330.json")
    parser.add_argument("--out", default="tools/data/boundary_graph_residue_threshold_audit_20260516_0720.json")
    parser.add_argument("--min-lift", type=float, default=0.10)
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
